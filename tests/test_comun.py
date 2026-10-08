"""
Tests de las utilidades compartidas de la evaluación (`eval_ragas.comun`).

Sin API ni ragas. Protegen cuatro cosas que, si fallan, no dan error sino datos
falsos: cómo se clasifica cada fila (un rechazo contado como OK inflaría las
medias), qué se reintenta (reintentar un 400 sólo quema tiempo; no reintentar un
429 pierde la fila), cómo se cuenta el gasto de una corrida de pago y que la
línea de configuración de las corridas gratuitas no cambie ni un byte.

    python -m pytest -q tests/test_comun.py
"""

from __future__ import annotations

import pytest

from eval_ragas import comun
from eval_ragas.comun import (
    ERROR,
    OK,
    RECHAZO,
    append_filas,
    clasificar,
    con_reintentos,
    consumo_de,
    es_transitorio,
    etiqueta_generador,
    gasto_acumulado,
    huella_plantillas,
    leer_configuracion,
    resumen_juez,
)
from rag import REFUSAL_TEXT
from rag.config import MODELO_RAG_BLABLADOR


# ── Clasificación de filas ────────────────────────────────────────────────────
class TestClasificar:
    def test_respuesta_de_contenido(self):
        assert clasificar("La paginación divide la memoria en marcos [1].") == OK

    def test_el_rechazo_exacto(self):
        assert clasificar(REFUSAL_TEXT) == RECHAZO

    def test_el_rechazo_con_una_tilde_cambiada(self):
        assert clasificar(REFUSAL_TEXT.replace("información", "informacion")) == RECHAZO

    def test_una_excepcion_es_error_aunque_haya_texto(self):
        assert clasificar("algo", error="TimeoutError: ...") == ERROR

    @pytest.mark.parametrize("vacia", ["", "   \n ", None])
    def test_una_respuesta_vacia_es_error(self, vacia):
        # Es lo que llega cuando un razonador agota MAX_TOKENS_SALIDA_RAG
        # pensando: tiene que verse como ERROR, no puntuarse como respuesta.
        assert clasificar(vacia) == ERROR


# ── Reintentos ────────────────────────────────────────────────────────────────
class TestTransitorio:
    @pytest.mark.parametrize("mensaje", [
        "Error code: 429 - rate limit", "503 Service Unavailable",
        "Request timeout", "RESOURCE_EXHAUSTED",
    ])
    def test_merecen_reintento(self, mensaje):
        assert es_transitorio(RuntimeError(mensaje))

    @pytest.mark.parametrize("mensaje", [
        "Error code: 400 - bad request", "Error code: 404 - model not found",
        "Error code: 401 - invalid api key",
    ])
    def test_no_merecen_reintento(self, mensaje):
        assert not es_transitorio(RuntimeError(mensaje))

    def test_mira_tambien_el_nombre_de_la_excepcion(self):
        class DEADLINE_EXCEEDED(Exception):  # noqa: N801 - imita a la de gRPC
            pass
        assert es_transitorio(DEADLINE_EXCEEDED("sin más texto"))


class TestConReintentos:
    @pytest.fixture(autouse=True)
    def sin_esperas(self, monkeypatch):
        self.esperas = []
        monkeypatch.setattr(comun.time, "sleep", self.esperas.append)

    def test_reintenta_lo_transitorio_con_espera_creciente(self):
        intentos = iter([RuntimeError("429"), RuntimeError("503"), "ok"])

        def fn():
            valor = next(intentos)
            if isinstance(valor, Exception):
                raise valor
            return valor

        assert con_reintentos(fn, espera_inicial=4) == "ok"
        assert self.esperas == [4, 8]

    def test_un_error_nuestro_se_relanza_sin_esperar(self):
        def fn():
            raise ValueError("Error code: 400")

        with pytest.raises(ValueError):
            con_reintentos(fn)
        assert self.esperas == []

    def test_se_rinde_tras_los_intentos(self):
        llamadas = []

        def fn():
            llamadas.append(1)
            raise RuntimeError("429")

        with pytest.raises(RuntimeError):
            con_reintentos(fn, intentos=3)
        assert len(llamadas) == 3
        assert len(self.esperas) == 2


# ── Banco de preguntas ────────────────────────────────────────────────────────
def test_leer_banco_tolera_el_bom_de_excel(tmp_path, monkeypatch):
    banco = tmp_path / "banco.csv"
    banco.write_text(
        '"ID","Categoría","Pregunta","Respuesta Correcta (Ground Truth)"\n'
        '"1","PREGUNTAS DIRECTAS","¿Qué es un SO?","Un programa."\n'
        '"","PREGUNTAS DIRECTAS","sin id","x"\n',
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(comun, "BANCO_CSV", banco)
    filas = comun.leer_banco()
    assert filas == [{"ID": "1", "Categoria": "PREGUNTAS DIRECTAS",
                      "user_input": "¿Qué es un SO?", "reference": "Un programa."}]


# ── Configuración de la corrida ───────────────────────────────────────────────
class TestEtiquetaGenerador:
    def test_blablador_no_cambia_ni_un_byte(self):
        # Es el campo `modelo RAG` de todos los configuracion.txt libre_*: si
        # cambiara, `auditar_configuraciones` vería distinto el generador en
        # corridas que usaron el mismo.
        assert etiqueta_generador("blablador", MODELO_RAG_BLABLADOR, "low") == \
            "01 - GPT-OSS-120b - an open model released by OpenAI in August 2025"

    def test_openai_lleva_proveedor_y_razonamiento(self):
        assert etiqueta_generador("openai", "gpt-5.1-2025-11-13", "low") == \
            "openai/gpt-5.1-2025-11-13 (razonamiento=low)"

    def test_sin_razonamiento_no_se_inventa_el_campo(self):
        assert etiqueta_generador("openai", "gpt-4.1-2025-04-14", "low") == \
            "openai/gpt-4.1-2025-04-14"


def test_leer_configuracion(tmp_path):
    assert leer_configuracion(tmp_path) is None
    (tmp_path / "configuracion.txt").write_text("modelo RAG=x · juez=y\n", encoding="utf-8")
    assert leer_configuracion(tmp_path) == "modelo RAG=x · juez=y"


# ── El instrumento de medida ──────────────────────────────────────────────────
class TestHuellaPlantillas:
    def test_es_estable(self, tmp_path):
        (tmp_path / "a.json").write_text('{"x": 1}', encoding="utf-8")
        assert huella_plantillas(tmp_path) == huella_plantillas(tmp_path)

    def test_cambia_si_se_retoca_una_plantilla(self, tmp_path):
        ruta = tmp_path / "a.json"
        ruta.write_text('{"x": 1}', encoding="utf-8")
        antes = huella_plantillas(tmp_path)
        ruta.write_text('{"x": 2}', encoding="utf-8")
        assert huella_plantillas(tmp_path) != antes

    def test_las_plantillas_versionadas_existen(self):
        # Sin ellas la huella sería la de un directorio vacío y no protegería nada.
        assert list(comun.PROMPTS_ES_DIR.glob("*.json"))


def test_el_resumen_del_juez_nombra_juez_y_plantillas():
    texto = resumen_juez()
    assert texto.startswith(f"juez={comun.MODEL_JUDGE} · razonamiento=no")
    assert f"español ({huella_plantillas()})" in texto
    assert "inglés" in resumen_juez(ingles=True)


# ── Consumo y gasto ───────────────────────────────────────────────────────────
USO_GPT51 = {"gpt-5.1-2025-11-13": {
    "input_tokens": 2600, "output_tokens": 700, "total_tokens": 3300,
    "input_token_details": {"cache_read": 0},
    "output_token_details": {"reasoning": 550},
}}


def test_consumo_de_una_respuesta():
    c = consumo_de(USO_GPT51, "gpt-5.1-2025-11-13")
    assert (c["tokens_entrada"], c["tokens_salida"], c["tokens_razonamiento"]) == (2600, 700, 550)
    # El razonamiento ya va dentro de los 700 de salida: no se cobra aparte.
    assert c["coste_usd"] == pytest.approx(2600 * 1.25e-6 + 700 * 10e-6)


def test_sin_uso_no_hay_coste():
    assert consumo_de({}, "gpt-5.1-x")["coste_usd"] == 0
    assert consumo_de(None, "gpt-5.1-x")["tokens_entrada"] == 0


def test_el_gasto_se_suma_del_fichero(tmp_path):
    ruta = tmp_path / "consumo.csv"
    assert gasto_acumulado(ruta) == 0.0
    append_filas(ruta, [{"ID": "1", "coste_usd": 0.01}, {"ID": "2", "coste_usd": 0.0125}],
                 comun.CAMPOS_CONSUMO)
    assert gasto_acumulado(ruta) == pytest.approx(0.0225)


# ── configuracion.txt ─────────────────────────────────────────────────────────
def test_campos_configuracion():
    texto = "modelo RAG=01 - GPT-OSS · reranker=mmarco · RERANK_K=5 · nota libre"
    assert comun.campos_configuracion(texto) == {
        "modelo RAG": "01 - GPT-OSS", "reranker": "mmarco", "RERANK_K": "5"}


def test_campos_configuracion_sin_fichero():
    assert comun.campos_configuracion(None) == {}
