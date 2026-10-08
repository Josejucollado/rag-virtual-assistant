"""
Tests de la fusión de resultados al reanudar la fase 2 (`eval_ragas.puntuar`).

`fusionar_y_guardar` mezcla lo recién puntuado con el CSV previo. Se prueba
contra un CSV temporal, sin API. Protege un fallo real: al ampliar
prueba10_conciso de 10 a 24 preguntas, las 14 filas nuevas se guardaron sólo con
ID y notas, sin pregunta, respuesta ni categoría.

Importa `ragas` (a través de `metricas`), así que tarda unos segundos en cargar.

    python -m pytest -q tests/test_puntuar.py
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from eval_ragas import puntuar


@pytest.fixture
def csv_temporal(tmp_path, monkeypatch):
    ruta = tmp_path / "resultados_ragas.csv"
    monkeypatch.setattr(puntuar, "RESULTADOS_CSV", ruta)
    return ruta


def fila(id_: str, categoria: str = "PREGUNTAS DIRECTAS", **notas) -> dict:
    return {"ID": id_, "Categoria": categoria, "user_input": f"pregunta {id_}",
            "response": f"respuesta {id_}", **notas}


def test_las_filas_nuevas_conservan_sus_columnas_al_reanudar(csv_temporal):
    previas = pd.DataFrame([fila("1", faithfulness=0.9)])
    nuevas = [fila("41", "SÍNTESIS / MULTIHOP", faithfulness=0.8)]

    df = puntuar.fusionar_y_guardar(previas, nuevas, ["faithfulness"])

    nueva = df[df["ID"] == "41"].iloc[0]
    assert nueva["Categoria"] == "SÍNTESIS / MULTIHOP"
    assert nueva["user_input"] == "pregunta 41"
    assert nueva["faithfulness"] == 0.8


def test_un_hueco_de_una_fila_previa_se_rellena_sin_tocar_lo_demas(csv_temporal):
    previas = pd.DataFrame([fila("1", faithfulness=math.nan, context_recall=1.0)])
    nuevas = [fila("1", faithfulness=0.7)]

    df = puntuar.fusionar_y_guardar(previas, nuevas, ["faithfulness"])

    assert len(df) == 1
    assert df.iloc[0]["faithfulness"] == 0.7
    assert df.iloc[0]["context_recall"] == 1.0
    assert df.iloc[0]["Categoria"] == "PREGUNTAS DIRECTAS"


def test_una_metrica_nueva_se_anade_como_columna(csv_temporal):
    previas = pd.DataFrame([fila("1", faithfulness=0.9), fila("2", faithfulness=0.5)])
    nuevas = [fila("1", factual_recall=1.0), fila("2", factual_recall=0.5)]

    df = puntuar.fusionar_y_guardar(previas, nuevas, ["factual_recall"])

    assert list(df["factual_recall"]) == [1.0, 0.5]
    assert list(df["faithfulness"]) == [0.9, 0.5]


def test_ordena_por_id_numerico_y_escribe_el_csv(csv_temporal):
    previas = pd.DataFrame([fila("10", faithfulness=0.1)])
    nuevas = [fila("9", faithfulness=0.9), fila("41", faithfulness=0.4)]

    df = puntuar.fusionar_y_guardar(previas, nuevas, ["faithfulness"])

    assert list(df["ID"]) == ["9", "10", "41"]
    assert len(pd.read_csv(csv_temporal)) == 3


# ── mapear_columnas: la trampa de las columnas a NaN ──────────────────────────
# RAGAS no nombra las columnas como uno pide. Mapear a ciegas por el nombre
# corto llenaba de NaN dos columnas sin ningún error.
from types import SimpleNamespace  # noqa: E402

ENTRADA = ["user_input", "retrieved_contexts", "response", "reference"]


def metrica(nombre, modo=None):
    return SimpleNamespace(name=nombre, mode=modo) if modo else SimpleNamespace(name=nombre)


def notas_con(columnas):
    return pd.DataFrame([{c: 0.5 for c in ENTRADA + columnas}])


def test_mapea_los_nombres_reales_de_ragas():
    notas = notas_con(["faithfulness", "llm_context_precision_with_reference",
                       "factual_correctness(mode=f1)", "factual_correctness(mode=recall)"])
    mapa = puntuar.mapear_columnas(
        notas,
        [metrica("faithfulness"), metrica("llm_context_precision_with_reference"),
         metrica("factual_correctness", "f1"), metrica("factual_correctness", "recall")],
        ["faithfulness", "context_precision", "factual_correctness", "factual_recall"],
    )
    assert mapa == {
        "faithfulness": "faithfulness",
        "context_precision": "llm_context_precision_with_reference",
        "factual_correctness": "factual_correctness(mode=f1)",
        "factual_recall": "factual_correctness(mode=recall)",
    }


def test_las_dos_caras_factuales_no_se_cruzan_aunque_cambie_el_orden():
    notas = notas_con(["factual_correctness(mode=recall)", "factual_correctness(mode=f1)"])
    mapa = puntuar.mapear_columnas(
        notas, [metrica("factual_correctness", "f1"), metrica("factual_correctness", "recall")],
        ["factual_correctness", "factual_recall"],
    )
    assert mapa["factual_correctness"] == "factual_correctness(mode=f1)"
    assert mapa["factual_recall"] == "factual_correctness(mode=recall)"


def test_sin_nombre_reconocible_cae_a_la_posicion():
    notas = notas_con(["columna_rara"])
    mapa = puntuar.mapear_columnas(notas, [metrica("otra_cosa")], ["semantic_similarity"])
    assert mapa == {"semantic_similarity": "columna_rara"}


def test_las_columnas_de_entrada_nunca_se_toman_por_notas():
    mapa = puntuar.mapear_columnas(notas_con([]), [metrica("faithfulness")], ["faithfulness"])
    assert mapa == {}


# ── planificar: la reanudación consciente de columnas ─────────────────────────
def respuestas(*ids):
    return pd.DataFrame([{"ID": i, "user_input": f"p{i}"} for i in ids])


def test_sin_nada_previo_se_puntua_todo():
    pend, metricas = puntuar.planificar(respuestas("1", "2", "3"), pd.DataFrame(),
                                        ["faithfulness", "context_recall"], None)
    assert list(pend["ID"]) == ["1", "2", "3"]
    assert metricas == ["faithfulness", "context_recall"]


def test_el_limite_recorta_las_pendientes():
    pend, _ = puntuar.planificar(respuestas("1", "2", "3"), pd.DataFrame(), ["faithfulness"], 2)
    assert list(pend["ID"]) == ["1", "2"]


def test_las_filas_nuevas_se_puntuan_con_todas_las_metricas():
    previas = pd.DataFrame([{"ID": "1", "faithfulness": 0.9, "context_recall": 1.0}])
    pend, metricas = puntuar.planificar(respuestas("1", "2"), previas,
                                        ["faithfulness", "context_recall"], None)
    assert list(pend["ID"]) == ["2"]
    assert metricas == ["faithfulness", "context_recall"]


def test_una_metrica_nueva_se_calcula_sola_sobre_lo_hecho():
    previas = pd.DataFrame([{"ID": "1", "faithfulness": 0.9}, {"ID": "2", "faithfulness": 0.8}])
    pend, metricas = puntuar.planificar(respuestas("1", "2"), previas,
                                        ["faithfulness", "factual_recall"], None)
    assert metricas == ["factual_recall"]
    assert set(pend["ID"]) == {"1", "2"}


def test_un_hueco_se_reintenta_solo_en_su_fila_y_su_metrica():
    previas = pd.DataFrame([{"ID": "1", "faithfulness": 0.9, "context_precision": math.nan},
                            {"ID": "2", "faithfulness": 0.8, "context_precision": 0.5}])
    pend, metricas = puntuar.planificar(respuestas("1", "2"), previas,
                                        ["faithfulness", "context_precision"], None)
    assert metricas == ["context_precision"]
    assert list(pend["ID"]) == ["1"]


def test_si_todo_esta_hecho_no_hay_nada_que_puntuar():
    previas = pd.DataFrame([{"ID": "1", "faithfulness": 0.9}])
    pend, metricas = puntuar.planificar(respuestas("1"), previas, ["faithfulness"], None)
    assert pend.empty and metricas == []


# ── comprobar_juez: el invariante 6 en la fase 2 ──────────────────────────────
def test_mismo_juez_sigue_sin_avisos():
    assert puntuar.comprobar_juez("juez=Q", "juez=Q", hay_resultados=True) is None


def test_otro_juez_no_puede_reanudar():
    with pytest.raises(puntuar.ErrorConfiguracion, match="otro juez"):
        puntuar.comprobar_juez("juez=Q", "juez=GPT", hay_resultados=True)


def test_notas_sin_constancia_avisan_pero_no_paran():
    aviso = puntuar.comprobar_juez(None, "juez=Q", hay_resultados=True)
    assert aviso and "puntuacion.txt" in aviso


def test_una_corrida_nueva_no_avisa():
    assert puntuar.comprobar_juez(None, "juez=Q", hay_resultados=False) is None
