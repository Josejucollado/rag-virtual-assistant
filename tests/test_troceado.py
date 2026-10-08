"""
Tests del troceado de `cli/process_md.py`.

Cubren las tres correcciones que el troceado aplica sobre la estructura que
Docling extrae —descartar portadas e índices, fusionar secciones pequeñas y
subdividir las grandes sin romper tablas ni bloques de código— porque son
decisiones ajustadas a mano contra este corpus y un cambio accidental no daría
error: sólo empeoraría la recuperación en silencio.

No tocan ni la API ni ChromaDB.

    pytest -q
"""

from __future__ import annotations

from langchain_core.documents import Document

from cli.process_md import (
    _cabecera_tabla_abierta,
    _es_separador,
    _fusionar_pequenas,
    _reparar_bloques,
    es_portada_o_indice,
    quitar_filas_de_indice,
    ratio_caracteres_raros,
    rescatar_prosa,
    trocear,
)
from rag import MIN_CHUNK


def seccion(texto: str, source: str = "t.md", h1: str = "Tema", h2: str = "S") -> Document:
    return Document(page_content=texto, metadata={"source": source, "h1": h1, "h2": h2})


# ── Calidad de la conversión ──────────────────────────────────────────────────
class TestRatioCaracteresRaros:
    def test_texto_normal_es_legible(self):
        assert ratio_caracteres_raros("La paginación divide la memoria.") < 0.01

    def test_texto_sin_tabla_tounicode(self):
        """Un PDF cuya fuente no trae ToUnicode se extrae como símbolos."""
        assert ratio_caracteres_raros("❯❳❡❨❯❳❡❨❯❳❡❨") > 0.5

    def test_texto_vacio(self):
        assert ratio_caracteres_raros("") == 0.0


# ── Portadas e índices ────────────────────────────────────────────────────────
class TestPortadasEIndices:
    def test_detecta_portada_por_campos_del_curso(self):
        sec = seccion("Sitio: PLATEA\nCurso: SSOO\nLibro: Tema 1\n", h2="Tema 1")
        assert es_portada_o_indice(sec)

    def test_detecta_indice_por_titulo_completo(self):
        assert es_portada_o_indice(seccion("lo que sea", h2="Tabla de contenidos"))
        assert es_portada_o_indice(seccion("lo que sea", h2="Índice"))

    def test_no_confunde_un_ejercicio_que_empieza_por_indice(self):
        """«Índice invertido de n-gramas» es un ejercicio de shell, no el índice.

        Por eso el título del índice se exige completo y no como prefijo.
        """
        assert not es_portada_o_indice(
            seccion("Escribe un script...", h2="Índice invertido de n-gramas")
        )

    def test_detecta_autoria_como_prefijo(self):
        assert es_portada_o_indice(seccion("x", h2="Autor: Lina García-Cabrera"))


class TestRescatarProsa:
    def test_conserva_la_presentacion_del_modulo(self):
        """Tirar la sección entera se llevaba por delante la introducción del tema."""
        texto = (
            "Sitio: PLATEA\n"
            "Curso: Sistemas Operativos\n"
            "1. Introducción....4\n"
            "Un computador es una máquina que permite procesar la información de "
            "forma rápida y automática, y su interfaz resulta compleja al "
            "pensamiento humano habitual.\n"
        )
        rescatado = rescatar_prosa(texto)
        assert rescatado.startswith("Un computador")
        assert "Sitio:" not in rescatado

    def test_portada_pura_no_deja_nada(self):
        assert rescatar_prosa("Sitio: PLATEA\nCurso: SSOO\nDía: 3\n") == ""

    def test_descarta_la_linea_de_licencia(self):
        texto = (
            "Esta obra se distribuye bajo licencia Creative Commons "
            "reconocimiento no comercial compartir igual cuatro punto cero "
            "internacional para todos\n"
        )
        assert rescatar_prosa(texto) == ""


class TestQuitarFilasDeIndice:
    def test_quita_filas_con_puntos_guia(self):
        texto = "| 1. Introducción........... | 4 |\n| contenido normal | x |"
        salida = quitar_filas_de_indice(texto)
        assert "Introducción" not in salida
        assert "contenido normal" in salida

    def test_conserva_texto_con_pocos_puntos(self):
        texto = "| algo ... | 4 |"
        assert "algo" in quitar_filas_de_indice(texto)


# ── Tablas ────────────────────────────────────────────────────────────────────
class TestTablas:
    def test_reconoce_el_separador(self):
        assert _es_separador("|---|---|")
        assert _es_separador("| :--- | ---: |")
        assert not _es_separador("| a | b |")
        assert not _es_separador("")

    def test_cabecera_de_tabla_abierta(self):
        texto = "prosa\n\n| a | b |\n|---|---|\n| 1 | 2 |"
        assert _cabecera_tabla_abierta(texto) == ["| a | b |", "|---|---|"]

    def test_sin_tabla_al_final_no_hay_cabecera(self):
        assert _cabecera_tabla_abierta("sólo prosa") == []


class TestRepararBloques:
    def test_cierra_y_reabre_un_bloque_de_codigo_partido(self):
        trozos = [
            Document(page_content="```bash\necho hola", metadata={}),
            Document(page_content="echo adios\n```", metadata={}),
        ]
        reparados = _reparar_bloques(trozos)
        # El primero se cierra y el segundo se reabre: ninguno queda a medias.
        assert reparados[0].page_content.endswith("```")
        assert reparados[1].page_content.startswith("```")

    def test_repite_la_cabecera_de_la_tabla_en_la_continuacion(self):
        trozos = [
            Document(page_content="| col | val |\n|---|---|\n| a | 1 |", metadata={}),
            Document(page_content="| b | 2 |", metadata={}),
        ]
        reparados = _reparar_bloques(trozos)
        # Sin esto, el segundo chunk son columnas de números sin nombre.
        assert reparados[1].page_content.startswith("| col | val |")


# ── Fusión de secciones pequeñas ──────────────────────────────────────────────
class TestFusionarPequenas:
    def test_fusiona_contiguas_del_mismo_tema(self):
        salida = _fusionar_pequenas([seccion("aaa", h2="S1"), seccion("bbb", h2="S2")])
        assert len(salida) == 1
        # El H2 de la absorbida se conserva dentro del texto.
        assert "## S2" in salida[0].page_content

    def test_no_fusiona_documentos_distintos(self):
        salida = _fusionar_pequenas([seccion("aaa", source="a.md"), seccion("bbb", source="b.md")])
        assert len(salida) == 2

    def test_no_fusiona_temas_distintos(self):
        salida = _fusionar_pequenas([seccion("aaa", h1="Tema 1"), seccion("bbb", h1="Tema 2")])
        assert len(salida) == 2

    def test_no_fusiona_si_se_pasa_de_min_chunk(self):
        grande = "x" * MIN_CHUNK
        assert len(_fusionar_pequenas([seccion(grande), seccion(grande)])) == 2


# ── Troceado completo ─────────────────────────────────────────────────────────
class TestTrocear:
    def test_antepone_los_encabezados_y_asigna_id_estable(self):
        doc = Document(
            page_content="# Tema 5\n\n## Paginación\n\n" + "contenido. " * 40,
            metadata={"source": "05.md"},
        )
        chunks = trocear([doc])
        assert chunks
        assert chunks[0].page_content.startswith("# Tema 5\n## Paginación")
        # El id lleva el índice con ceros para que ordenar como cadena respete
        # el orden del documento original.
        assert chunks[0].metadata["chunk_id"] == "05.md#0000"

    def test_los_ids_son_correlativos_por_documento(self):
        doc = Document(
            page_content="# T\n\n## A\n\n" + "a. " * 600 + "\n\n## B\n\n" + "b. " * 600,
            metadata={"source": "x.md"},
        )
        ids = [c.metadata["chunk_id"] for c in trocear([doc])]
        assert ids == sorted(ids)
        assert ids[0] == "x.md#0000"

    def test_los_metadatos_no_llevan_none(self):
        """Chroma rechaza un None en los metadatos."""
        doc = Document(page_content="# T\n\ntexto suelto sin H2\n", metadata={"source": "x.md"})
        for chunk in trocear([doc]):
            assert None not in chunk.metadata.values()
