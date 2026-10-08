"""
Tests del núcleo del RAG: rechazo, citas, tokenización y deduplicado.

Sólo funciones puras. No llaman a ninguna API, no abren ChromaDB y no
cargan el cross-encoder, así que la suite entera tarda menos de un segundo y no
cuesta dinero.

Lo que protegen es la equivalencia de comportamiento: son las piezas cuya
semántica exacta se decidió a base de medir sobre este corpus, y donde un
cambio silencioso no da error, sólo peores respuestas.

    pytest -q
"""

from __future__ import annotations

from langchain_core.documents import Document

from rag import (
    MAX_CHARS_RESPUESTA_HISTORIAL,
    REFUSAL_TEXT,
    DeduplicadorSecciones,
    consulta_de_busqueda,
    cuerpo_sin_encabezados,
    describir_fuente,
    entrada_generador,
    es_rechazo,
    extraer_citas,
    formatear_contexto,
    formatear_historial,
    quitar_citas,
    recortar,
    tokenizar_es,
)


# ── Estilos del prompt ────────────────────────────────────────────────────────
class TestEstilosDelPrompt:
    def test_explicativo_es_el_prompt_de_siempre(self):
        # La corrida base se mide con este prompt: si cambiara al añadir estilos,
        # ya no sería comparable con lo generado antes.
        from rag import plantilla_rag

        p = plantilla_rag("explicativo")
        assert "Tu objetivo es proporcionar respuestas claras, precisas y bien explicadas." in p
        assert "6. Sé claro y ordenado. Usa listas cuando ayuden.\n\nContexto:" in p

    def test_el_prompt_activo_es_el_del_estilo_configurado(self):
        from rag import ESTILO_RESPUESTA, RAG_TEMPLATE, plantilla_rag

        # "conciso" por defecto, salvo que la shell pida otro: entonces es ese.
        assert RAG_TEMPLATE == plantilla_rag(ESTILO_RESPUESTA)

    def test_el_estilo_por_defecto_es_conciso(self):
        # Es el adoptado tras medirlo: el chat y la web tienen que usarlo sin
        # que nadie ponga la variable. Se lee el defecto del código fuente: con
        # importlib.reload se crearía otra ErrorConfiguracion y fallarían los
        # tests que capturan la de siempre, y un subproceso tendría que cargar
        # torch sólo para esto (la suite pasaba de 15 s a 47 s).
        import ast
        import inspect

        import rag.config

        defectos = [
            nodo.args[1].value
            for nodo in ast.walk(ast.parse(inspect.getsource(rag.config)))
            if isinstance(nodo, ast.Call) and len(nodo.args) == 2
            and isinstance(nodo.args[0], ast.Constant)
            and nodo.args[0].value == "ESTILO_RESPUESTA"
        ]
        assert defectos == ["conciso"]

    def test_todos_los_estilos_dejan_las_mismas_variables(self):
        from langchain_core.prompts import PromptTemplate

        from rag import ESTILOS_RESPUESTA, plantilla_rag

        for estilo in ESTILOS_RESPUESTA:
            variables = set(PromptTemplate.from_template(plantilla_rag(estilo)).input_variables)
            assert variables == {"context", "input", "refusal"}, estilo

    def test_los_estilos_solo_cambian_objetivo_y_regla_6(self):
        # Si un estilo tocara otra regla, la comparativa entre estilos ya no
        # mediría sólo la forma de redactar.
        from rag import ESTILOS_RESPUESTA, plantilla_rag

        def sin_estilo(plantilla: str) -> list[str]:
            lineas = plantilla.splitlines()
            regla_6 = next(i for i, ln in enumerate(lineas) if ln.startswith("6. "))
            contexto = lineas.index("Contexto:")
            return ([ln for ln in lineas[:regla_6] if not ln.startswith("Tu objetivo")]
                    + lineas[contexto:])

        base = plantilla_rag("explicativo")
        for estilo in ESTILOS_RESPUESTA:
            assert sin_estilo(plantilla_rag(estilo)) == sin_estilo(base), estilo
            if estilo != "explicativo":
                assert plantilla_rag(estilo) != base, estilo

    def test_cada_estilo_de_la_configuracion_tiene_texto(self):
        from rag import ESTILOS_RESPUESTA
        from rag.generacion import _ESTILOS

        assert set(_ESTILOS) == set(ESTILOS_RESPUESTA)


def doc(texto: str, source: str = "a.md", h2: str | None = None, **extra) -> Document:
    meta = {"source": source, **extra}
    if h2 is not None:
        meta["h2"] = h2
    return Document(page_content=texto, metadata=meta)


# ── es_rechazo ────────────────────────────────────────────────────────────────
class TestEsRechazo:
    """El rechazo se detecta pese a que el modelo altere tildes o puntuación.

    Es crítico: la evaluación cuenta cada rechazo como un fallo, así que un
    falso negativo aquí puntuaría como buena una respuesta que no lo es.
    """

    def test_texto_exacto(self):
        assert es_rechazo(REFUSAL_TEXT)

    def test_sin_tildes(self):
        assert es_rechazo("No tengo la suficiente informacion para contestar a su pregunta.")

    def test_sin_punto_final(self):
        assert es_rechazo("No tengo la suficiente información para contestar a su pregunta")

    def test_mayusculas_distintas(self):
        assert es_rechazo("NO TENGO LA SUFICIENTE INFORMACIÓN PARA CONTESTAR A SU PREGUNTA.")

    def test_respuesta_de_contenido_no_es_rechazo(self):
        assert not es_rechazo("La paginación divide la memoria física en marcos [1].")

    def test_valores_no_texto(self):
        assert not es_rechazo(None)
        assert not es_rechazo(123)
        assert not es_rechazo("")


# ── Citas ─────────────────────────────────────────────────────────────────────
class TestExtraerCitas:
    def test_orden_de_aparicion_y_sin_repetir(self):
        assert extraer_citas("Primero [3], luego [1] y otra vez [3].", 5) == [3, 1]

    def test_descarta_fuera_de_rango(self):
        # El modelo a veces inventa un [9] cuando sólo se le dieron 5 fragmentos:
        # esa cita no apunta a nada y no debe enseñarse como fuente.
        assert extraer_citas("Válida [2], inventada [9], cero [0].", 5) == [2]

    def test_sin_citas(self):
        assert extraer_citas("Una respuesta sin ninguna marca.", 5) == []

    def test_citas_consecutivas(self):
        assert extraer_citas("Se apoya en [1][3].", 3) == [1, 3]

    def test_formato_de_gpt_oss(self):
        # GPT-OSS cita a veces como en su entrenamiento aunque se le pida [n].
        assert extraer_citas("Abstracción【1†L4-L7】【2†L9-L12】 y más [1].", 5) == [1, 2]

    def test_formato_de_gpt_oss_sin_lineas(self):
        assert extraer_citas("Dato【3】.", 5) == [3]


class TestQuitarCitas:
    def test_quita_marcas_y_colapsa_espacios(self):
        assert quitar_citas("Uno [1] y  dos [2].") == "Uno y dos ."

    def test_quita_el_formato_de_gpt_oss(self):
        # Si llegara al juez, la marca se colaría dentro de las afirmaciones.
        assert quitar_citas("Abstracción【1†L4-L7】【2†L9-L12】.") == "Abstracción."

    def test_valores_no_texto(self):
        assert quitar_citas(None) == ""


# ── Tokenización para BM25 ────────────────────────────────────────────────────
class TestTokenizarEs:
    def test_quita_vacias_y_tildes(self):
        assert tokenizar_es("¿Qué es la paginación de memoria?") == ["paginacion", "memoria"]

    def test_conserva_cuanto_que_es_termino_tecnico(self):
        """En este corpus *el cuanto* es el quantum de planificación.

        Estuvo en la lista de palabras vacías como interrogativo y rompía todas
        las preguntas sobre Round Robin. Este test existe para que no vuelva.
        """
        assert "cuanto" in tokenizar_es("¿Cuál es el cuanto en Round Robin?")

    def test_quita_verbos_de_enunciado(self):
        assert tokenizar_es("Explica la diferencia entre proceso e hilo") == [
            "proceso", "e", "hilo"
        ]

    def test_stemming_funde_singular_y_plural(self):
        assert (tokenizar_es("procesos", stemming=True)
                == tokenizar_es("proceso", stemming=True))

    def test_stemming_filtra_vacias_antes_de_reducir(self):
        assert tokenizar_es("¿Qué es la paginación?", stemming=True) == ["pagin"]


# ── Deduplicador de secciones ─────────────────────────────────────────────────
class TestDeduplicadorSecciones:
    def test_deja_solo_el_primero_de_cada_seccion(self):
        docs = [
            doc("a", "05.md", "Paginación"),
            doc("b", "05.md", "Paginación"),   # mismo (source, h2): duplicado
            doc("c", "05.md", "Segmentación"),
        ]
        salida = DeduplicadorSecciones(limite=5).compress_documents(docs, "q")
        assert [d.page_content for d in salida] == ["a", "c"]

    def test_respeta_el_limite(self):
        docs = [doc(str(i), "05.md", f"Sección {i}") for i in range(10)]
        assert len(DeduplicadorSecciones(limite=3).compress_documents(docs, "q")) == 3

    def test_misma_seccion_en_documentos_distintos_no_es_duplicado(self):
        docs = [doc("a", "05.md", "Introducción"), doc("b", "06.md", "Introducción")]
        assert len(DeduplicadorSecciones(limite=5).compress_documents(docs, "q")) == 2

    def test_conserva_el_orden_de_entrada(self):
        """Llega ya reordenado por el cross-encoder: el primero es el mejor."""
        docs = [doc("mejor", "a.md", "X"), doc("peor", "a.md", "Y")]
        salida = DeduplicadorSecciones(limite=5).compress_documents(docs, "q")
        assert salida[0].page_content == "mejor"


# ── Presentación de fragmentos ────────────────────────────────────────────────
class TestPresentacion:
    def test_describir_fuente_con_seccion(self):
        assert describir_fuente(doc("x", "05.md", "Paginación")) == "05.md › Paginación"

    def test_describir_fuente_sin_seccion(self):
        assert describir_fuente(doc("x", "05.md")) == "05.md"

    def test_cuerpo_sin_encabezados(self):
        texto = "# 05 Memoria\n## Paginación\n\nLa paginación divide..."
        assert cuerpo_sin_encabezados(texto) == "La paginación divide..."

    def test_recortar_anade_puntos_suspensivos(self):
        assert recortar("abcdefghij", 4) == "abcd…"

    def test_recortar_no_toca_lo_que_cabe(self):
        assert recortar("corto", 20) == "corto"

    def test_formatear_contexto_numera_desde_uno(self):
        contexto = formatear_contexto([doc("uno", "a.md", "S1"), doc("dos", "b.md")])
        assert contexto == "[1] (a.md › S1)\nuno\n\n[2] (b.md)\ndos"


# ── Historial del reescritor ──────────────────────────────────────────────────
class TestFormatearHistorial:
    def test_solo_los_ultimos_turnos(self):
        historial = [("p1", "r1"), ("p2", "r2"), ("p3", "r3")]
        texto = formatear_historial(historial, max_turnos=2)
        assert "p1" not in texto
        assert "p2" in texto and "p3" in texto

    def test_recorta_respuestas_largas(self):
        """Con las respuestas enteras, reescribir costaba más tokens que generar."""
        largo = "x" * (MAX_CHARS_RESPUESTA_HISTORIAL + 500)
        texto = formatear_historial([("p", largo)])
        assert texto.endswith("...")
        assert len(texto) < MAX_CHARS_RESPUESTA_HISTORIAL + 100

    def test_historial_vacio(self):
        assert formatear_historial([]) == ""


# ── El turno del chat: con qué se busca y con qué se genera ───────────────────
class ReescritorFalso:
    """Devuelve una respuesta fija y apunta con qué se le llamó."""

    def __init__(self, respuesta: str):
        self.respuesta = respuesta
        self.llamadas: list[dict] = []

    def invoke(self, entrada: dict) -> str:
        self.llamadas.append(entrada)
        return self.respuesta


class TestTurnoDelChat:
    def test_sin_historial_no_se_reescribe(self):
        reescritor = ReescritorFalso("otra cosa")
        assert consulta_de_busqueda(reescritor, [], "¿qué es LRU?") == "¿qué es LRU?"
        assert reescritor.llamadas == []

    def test_con_historial_se_busca_con_la_reescrita(self):
        reescritor = ReescritorFalso("  ¿Qué desventajas tiene LRU?  ")
        consulta = consulta_de_busqueda(reescritor, [("¿qué es LRU?", "Un algoritmo")], "¿y sus desventajas?")
        assert consulta == "¿Qué desventajas tiene LRU?"
        assert reescritor.llamadas[0]["pregunta"] == "¿y sus desventajas?"

    def test_reescritura_vacia_vuelve_a_la_original(self):
        reescritor = ReescritorFalso("   ")
        assert consulta_de_busqueda(reescritor, [("p", "r")], "¿y eso?") == "¿y eso?"

    def test_se_genera_con_la_pregunta_original(self):
        """Invariante 4: la reescrita sólo sirve para buscar."""
        docs = [doc("uno", "a.md", "S1")]
        entrada = entrada_generador(docs, "¿y sus desventajas?")
        assert entrada == {"context": formatear_contexto(docs), "input": "¿y sus desventajas?"}
