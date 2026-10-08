"""
Tests de la comparativa de generadores (`eval_ragas.tfg.comparativa_generadores`).

Sin API: una tabla ancha hecha a mano. Protegen las dos decisiones que más
cambian la lectura: qué preguntas cuentan como caso completo (un ERROR en
cualquiera de los generadores saca la pregunta para todos) y cómo se forman los
estratos de contexto completo / parcial (con la cobertura del contexto de la
referencia, la misma para todos, porque los fragmentos son los mismos).

    python -m pytest -q tests/test_comparativa_generadores.py
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from eval_ragas.tfg import comparativa_generadores as CG

A, B = CG.REFERENCIA, "GPT-5.1"


def ancha():
    filas = [
        # ID, cobertura contexto ref, F1 ref, F1 pago, resultado pago
        ("1", 1.0, 0.6, 0.8, "OK"),
        ("2", 1.0, 0.7, math.nan, "OK"),
        ("3", 0.5, 0.4, 0.5, "OK"),
        ("4", 0.5, 0.3, 0.9, "ERROR"),
    ]
    datos = []
    for id_, cr, fa, fb, rb in filas:
        datos.append({
            "ID": id_, "Categoria": "PREGUNTAS DIRECTAS",
            f"resultado|{A}": "OK", f"resultado|{B}": rb,
            f"context_recall|{A}": cr, f"context_recall|{B}": cr,
            f"factual_correctness|{A}": fa, f"factual_correctness|{B}": fb,
            f"factual_recall|{A}": fa, f"factual_recall|{B}": fb,
            f"faithfulness|{A}": 1.0, f"faithfulness|{B}": 0.9,
        })
    return pd.DataFrame(datos)


def test_un_error_o_un_hueco_en_cualquiera_saca_la_pregunta():
    v = CG.validas(ancha(), "factual_correctness", [A, B])
    assert list(v["ID"]) == ["1", "3"]


def test_una_metrica_que_falta_no_revienta():
    assert CG.validas(ancha(), "semantic_similarity", [A, B]).empty


def test_los_estratos_se_forman_con_la_referencia():
    estratos = CG.estratos_contexto(ancha(), [A, B])
    completo_a = next(e for e in estratos if e["estrato"] == "Contexto completo" and e["generador"] == A)
    parcial_b = next(e for e in estratos if e["estrato"] == "Contexto parcial" and e["generador"] == B)
    assert completo_a["n"] == 2
    assert completo_a["factual_correctness"] == pytest.approx(0.65)
    # El ERROR de la pregunta 4 no entra en la media del de pago.
    assert parcial_b["n"] == 1
    assert parcial_b["factual_correctness"] == 0.5


def test_los_concursantes_van_de_menor_a_mayor_y_la_referencia_existe():
    nombres = [c.nombre for c in CG.CONCURSANTES]
    assert CG.REFERENCIA in nombres
    assert nombres.index("Apertus-8B") < nombres.index(CG.REFERENCIA) < nombres.index("GPT-5.1")
