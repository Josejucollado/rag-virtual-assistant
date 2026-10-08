"""
Tests de la fase 1 (`eval_ragas.generar_respuestas`) con el RAG sustituido por
dobles: sin API, sin Chroma y sin cross-encoder.

Protegen lo que hace a una corrida fiable y barata:
  - que no se reanude con otra configuración (mezclaría dos sistemas en un CSV);
  - que el tope de gasto pare antes de pasarse, y que la corrida se reanude;
  - que cada respuesta deje su fila de consumo, también las que fallan.

    python -m pytest -q tests/test_generar.py
"""

from __future__ import annotations

import csv
import sys

import pytest
from langchain_core.documents import Document

from eval_ragas import generar_respuestas as G
from eval_ragas.comun import ERROR, OK, RECHAZO
from rag import REFUSAL_TEXT

PREGUNTAS = [{"ID": str(i), "Categoria": "PREGUNTAS DIRECTAS",
              "user_input": f"pregunta {i}", "reference": f"ref {i}"} for i in range(1, 6)]
DOCS = [Document(page_content="texto", metadata={"chunk_id": "a.md#0001", "source": "a.md", "h2": "S"})]


class Recuperador:
    def invoke(self, pregunta):
        return DOCS


class Generador:
    def __init__(self, respuesta="Respuesta [1]."):
        self.respuesta = respuesta

    def invoke(self, entrada):
        if self.respuesta is None:
            raise ValueError("Error code: 400 - bad request")
        return self.respuesta


@pytest.fixture
def corrida(tmp_path, monkeypatch):
    """Una corrida en un directorio temporal, con el RAG y el banco falsos."""
    rutas = {"RESPUESTAS_CSV": tmp_path / "respuestas_rag.csv",
             "CONFIGURACION_TXT": tmp_path / "configuracion.txt",
             "CONSUMO_CSV": tmp_path / "consumo.csv"}
    for nombre, ruta in rutas.items():
        monkeypatch.setattr(G, nombre, ruta)
    monkeypatch.setattr(G, "leer_banco", lambda: [dict(p) for p in PREGUNTAS])
    monkeypatch.setattr(G, "resumen_config", lambda: "configuración A")
    monkeypatch.setattr(G, "build_retriever", Recuperador)
    monkeypatch.setattr(G, "build_generador", Generador)
    monkeypatch.setattr(G.time, "sleep", lambda s: None)
    return rutas


def lanzar(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["generar_respuestas", "--delay", "0", *args])
    return G.main()


def filas(ruta):
    with ruta.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ── fila_resultado ────────────────────────────────────────────────────────────
def test_fila_de_una_respuesta_con_citas():
    salida = {"docs": DOCS, "respuesta": "Sí [1] y también [7].", "latencia_s": 1.5}
    fila = G.fila_resultado(PREGUNTAS[0], salida, None)
    assert fila["resultado"] == OK
    assert fila["n_citas"] == 1          # el [7] no apunta a ningún fragmento
    assert fila["n_docs"] == 1
    assert '"a.md#0001"' in fila["fuentes"]


def test_fila_de_un_rechazo():
    salida = {"docs": DOCS, "respuesta": REFUSAL_TEXT, "latencia_s": 1.0}
    fila = G.fila_resultado(PREGUNTAS[0], salida, None)
    assert fila["resultado"] == RECHAZO and fila["es_rechazo"] is True


def test_fila_de_un_error():
    fila = G.fila_resultado(PREGUNTAS[0], None, "TimeoutError: x")
    assert fila["resultado"] == ERROR
    assert fila["n_docs"] == 0 and fila["latencia_s"] == 0.0


# ── Configuración ─────────────────────────────────────────────────────────────
def test_guarda_la_configuracion_y_todas_las_respuestas(corrida, monkeypatch):
    assert lanzar(monkeypatch) == 0
    assert corrida["CONFIGURACION_TXT"].read_text(encoding="utf-8").strip() == "configuración A"
    assert [f["ID"] for f in filas(corrida["RESPUESTAS_CSV"])] == ["1", "2", "3", "4", "5"]


def test_no_reanuda_con_otra_configuracion(corrida, monkeypatch):
    assert lanzar(monkeypatch, "--limit", "2") == 0
    monkeypatch.setattr(G, "resumen_config", lambda: "configuración B")
    with pytest.raises(G.ErrorConfiguracion, match="otra configuración"):
        lanzar(monkeypatch)
    assert len(filas(corrida["RESPUESTAS_CSV"])) == 2


def test_reanuda_sin_repetir_lo_hecho(corrida, monkeypatch):
    lanzar(monkeypatch, "--limit", "2")
    lanzar(monkeypatch)
    assert [f["ID"] for f in filas(corrida["RESPUESTAS_CSV"])] == ["1", "2", "3", "4", "5"]


# ── Consumo y tope de gasto ───────────────────────────────────────────────────
def test_cada_respuesta_deja_su_fila_de_consumo_aunque_falle(corrida, monkeypatch):
    monkeypatch.setattr(G, "build_generador", lambda: Generador(None))
    lanzar(monkeypatch, "--limit", "2")
    assert [f["resultado"] for f in filas(corrida["RESPUESTAS_CSV"])] == [ERROR, ERROR]
    assert [f["ID"] for f in filas(corrida["CONSUMO_CSV"])] == ["1", "2"]


@pytest.fixture
def de_pago(corrida, monkeypatch):
    """Generador de pago que cuesta 0,01 $ por pregunta, con tope de 0,035 $."""
    monkeypatch.setattr(G, "PROVEEDOR_RAG", "openai")
    monkeypatch.setattr(G, "PRESUPUESTO_USD", 0.035)
    monkeypatch.setattr(G, "consumo_de", lambda uso, modelo: {
        "tokens_entrada": 2600, "tokens_entrada_cache": 0, "tokens_salida": 700,
        "tokens_razonamiento": 500, "coste_usd": 0.01})
    return corrida


def test_el_tope_para_antes_de_pasarse(de_pago, monkeypatch):
    lanzar(monkeypatch)
    # Tras 3 preguntas van 0,03 $; la cuarta llevaría a 0,04 $ > 0,035 $.
    assert len(filas(de_pago["RESPUESTAS_CSV"])) == 3
    assert G.gasto_acumulado(de_pago["CONSUMO_CSV"]) == pytest.approx(0.03)


def test_el_tope_cuenta_lo_gastado_en_lanzamientos_anteriores(de_pago, monkeypatch):
    lanzar(monkeypatch, "--limit", "2")
    lanzar(monkeypatch)
    assert len(filas(de_pago["RESPUESTAS_CSV"])) == 3


def test_subiendo_el_tope_se_reanuda(de_pago, monkeypatch):
    lanzar(monkeypatch)
    monkeypatch.setattr(G, "PRESUPUESTO_USD", 1.0)
    lanzar(monkeypatch)
    assert len(filas(de_pago["RESPUESTAS_CSV"])) == 5


def test_un_generador_gratuito_no_tiene_tope(corrida, monkeypatch):
    monkeypatch.setattr(G, "PRESUPUESTO_USD", 0.0)
    lanzar(monkeypatch)
    assert len(filas(corrida["RESPUESTAS_CSV"])) == 5


@pytest.mark.parametrize("gastado,hechas,tope,para", [
    (0.0, 0, 2.0, False),     # nada hecho: sólo para si el tope ya está agotado
    (0.0, 0, 0.0, False),
    (1.98, 99, 2.0, False),   # 1,98 + 0,02 = 2,00: cabe justo
    (1.99, 99, 2.0, True),    # la siguiente (~0,0201) se pasaría
    (2.5, 0, 2.0, True),
])
def test_supera_presupuesto(gastado, hechas, tope, para):
    assert G.supera_presupuesto(gastado, hechas, tope) is para
