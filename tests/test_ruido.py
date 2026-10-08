"""
Tests de la banda de ruido, del aviso de jueces distintos y de la cabecera del
informe. Todo local: DataFrames hechos a mano y corridas en directorios
temporales.

La banda existe porque ni el generador ni el juez son deterministas: con el
mismo contexto, en el mismo orden, libre_conciso y libre_conciso_stemming
dieron sólo 3 respuestas idénticas de 68 y la F1 se movió en 47. Un Δ medio
por debajo de la banda es indistinguible de relanzar la misma configuración.

    python -m pytest -q tests/test_ruido.py
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from eval_ragas import comparar as C
from eval_ragas.tfg import comparativa_recuperacion as CR
from eval_ragas.estadistica import intervalo_wilson
from eval_ragas import informe


def par(filas):
    """Un par alineado mínimo: fragmentos, resultado y una métrica por lado."""
    return pd.DataFrame([{
        "ID": str(i), "resultado_a": ra, "resultado_b": rb,
        "fragmentos_a": fa, "fragmentos_b": fb,
        "factual_correctness_a": a, "factual_correctness_b": b,
    } for i, (fa, fb, a, b, ra, rb) in enumerate(filas, start=1)])


# ── Contextos idénticos ───────────────────────────────────────────────────────
def test_mismos_fragmentos_en_el_mismo_orden_son_identicos():
    p = par([("x#1 | x#2", "x#1 | x#2", 0.5, 0.5, "OK", "OK")])
    assert C.contextos_identicos(p).tolist() == [True]


def test_el_orden_importa():
    # El orden decide el [n] de cada fragmento: otro orden es otro prompt.
    p = par([("x#1 | x#2", "x#2 | x#1", 0.5, 0.5, "OK", "OK")])
    assert C.contextos_identicos(p).tolist() == [False]


def test_una_celda_vacia_no_es_identica_a_nada():
    p = par([(math.nan, math.nan, 0.5, 0.5, "OK", "OK")])
    assert C.contextos_identicos(p).tolist() == [False]


# ── Desviación típica del ruido ───────────────────────────────────────────────
def filas_ruido(n, identicos=True, error=False):
    salida = []
    for i in range(n):
        frag_b = "x#1" if identicos else f"y#{i}"
        salida.append(("x#1", frag_b, 0.5, 0.5 + (0.1 if i % 2 else -0.1),
                       "ERROR" if error else "OK", "OK"))
    return salida


def test_mide_el_ruido_solo_donde_el_contexto_es_identico():
    p = par(filas_ruido(12) + filas_ruido(12, identicos=False))
    r = C.ruido_por_metrica(p, ["factual_correctness"])
    assert r["factual_correctness"]["n"] == 12
    assert r["factual_correctness"]["sd"] == pytest.approx(pd.Series([0.1, -0.1] * 6).std())


def test_en_una_replica_cuentan_todas():
    p = par(filas_ruido(12, identicos=False))
    assert C.ruido_por_metrica(p, ["factual_correctness"]) == {}
    assert C.ruido_por_metrica(p, ["factual_correctness"], todas=True)["factual_correctness"]["n"] == 12


def test_con_pocos_pares_no_hay_banda():
    p = par(filas_ruido(C.MIN_PARES_RUIDO - 1))
    assert C.ruido_por_metrica(p, ["factual_correctness"]) == {}


def test_los_errores_no_cuentan_como_ruido():
    p = par(filas_ruido(12, error=True) + filas_ruido(3))
    assert C.ruido_por_metrica(p, ["factual_correctness"]) == {}


def test_la_banda_es_z_por_el_error_tipico():
    # Las cifras reales: DT 0,176 de la F1 con n = 94 da ±0,036.
    assert C.banda_ruido(0.176, 94) == pytest.approx(0.0356, abs=1e-4)
    assert C.banda_ruido(None, 94) is None
    assert C.banda_ruido(0.1, 0) is None


# ── Cuándo el propio par sirve de ruido ───────────────────────────────────────
@pytest.fixture
def fichas(monkeypatch):
    datos = {}
    monkeypatch.setattr(C, "ficha_corrida", lambda n: datos.get(n, "configuración no registrada"))
    return datos


def test_mismo_generador_y_estilo(fichas):
    fichas["a"] = "modelo RAG=gpt-oss · juez=q · reranker=sí · estilo=conciso"
    fichas["b"] = "modelo RAG=gpt-oss · juez=q · reranker=no · estilo=conciso"
    assert C.mismo_generador("a", "b")


def test_otro_generador_no_es_ruido(fichas):
    # Pago frente a gratuito: el contexto es el mismo en todas las preguntas y
    # la diferencia es justo el efecto que se mide, no ruido.
    fichas["a"] = "modelo RAG=gpt-oss · juez=q · estilo=conciso"
    fichas["b"] = "modelo RAG=openai/gpt-5.1 (razonamiento=low) · juez=q · estilo=conciso"
    assert not C.mismo_generador("a", "b")


def test_sin_configuracion_no_se_supone_nada(fichas):
    assert not C.mismo_generador("a", "b")


# ── Aviso de jueces ───────────────────────────────────────────────────────────
@pytest.fixture
def jueces(monkeypatch):
    datos = {}
    monkeypatch.setattr(C, "ficha_juez", lambda n: datos.get(n))
    return datos


def test_mismo_juez_no_avisa(jueces):
    jueces["a"] = jueces["b"] = "juez=Q · plantillas=español (abc)"
    assert C.aviso_jueces("a", "b") is None


def test_jueces_distintos_avisan(jueces):
    jueces["a"], jueces["b"] = "juez=Q", "juez=GPT"
    assert "distintos" in C.aviso_jueces("a", "b")


def test_sin_constancia_tambien_se_dice(jueces):
    jueces["a"] = "juez=Q"
    assert "no consta" in C.aviso_jueces("a", "b")


# ── Cabecera del informe ──────────────────────────────────────────────────────
def test_la_cabecera_sale_de_la_configuracion_de_la_corrida():
    g, j, resto = informe.partes_configuracion(
        "modelo RAG=15 - Apertus-8B · juez=02 - Qwen3.8 · reranker=no (mmarco) · estilo=conciso")
    assert (g, j) == ("15 - Apertus-8B", "02 - Qwen3.8")
    assert resto == "reranker=no (mmarco) · estilo=conciso"


def test_sin_configuracion_se_dice_que_es_la_del_entorno():
    _, _, resto = informe.partes_configuracion(None)
    assert "sin configuracion.txt" in resto


# ── Auditoría de las ablaciones ───────────────────────────────────────────────
BASE = ("modelo RAG=gpt-oss · juez=q · reranker=sí (mmarco) · RETRIEVER_K=20 · "
        "RERANK_K=5 · stemming BM25=no · estilo=conciso")
VARIANTES = {
    "libre_k3": BASE.replace("RERANK_K=5", "RERANK_K=3"),
    "libre_k8": BASE.replace("RERANK_K=5", "RERANK_K=8"),
    "libre_conciso_bge": BASE.replace("(mmarco)", "(bge)"),
    "libre_sin_reranker": BASE.replace("reranker=sí", "reranker=no"),
    "libre_conciso_stemming": BASE.replace("stemming BM25=no", "stemming BM25=sí"),
    "libre_base": BASE.replace("conciso", "explicativo"),
    "libre_minimo": BASE.replace("conciso", "minimo"),
    "libre_apertus": BASE.replace("gpt-oss", "apertus"),
}


@pytest.fixture
def corridas(tmp_path, monkeypatch):
    monkeypatch.setattr(CR, "RAGAS_DIR", tmp_path)
    for nombre, texto in {"libre_conciso": BASE, **VARIANTES}.items():
        (tmp_path / nombre).mkdir()
        (tmp_path / nombre / "configuracion.txt").write_text(texto + "\n", encoding="utf-8")
    return tmp_path


def test_la_auditoria_pasa_si_cada_ablacion_cambia_una_cosa(corridas):
    assert CR.auditar_configuraciones()


def test_la_auditoria_para_si_una_ablacion_cambia_dos(corridas):
    (corridas / "libre_k3" / "configuracion.txt").write_text(
        VARIANTES["libre_k3"].replace("estilo=conciso", "estilo=minimo"), encoding="utf-8")
    with pytest.raises(CR.ErrorConfiguracion, match="no aísla RERANK_K"):
        CR.auditar_configuraciones()


def test_wilson_con_todo_acertado_no_llega_a_cero_de_incertidumbre():
    inferior, superior = intervalo_wilson(15, 15)
    assert superior == 1.0
    assert inferior == pytest.approx(0.796, abs=1e-3)
    assert intervalo_wilson(0, 0) is None
