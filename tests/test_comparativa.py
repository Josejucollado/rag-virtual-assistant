"""
Tests de la aritmética del informe comparativo.

No leen ningún fichero ni llaman a ninguna API: construyen los DataFrames a mano
y comprueban el alineado, la política de exclusión y los estadísticos.

Lo que protegen es que los números del informe signifiquen lo que dicen. Un
delta calculado sobre conjuntos de preguntas distintos, o un NaN del juez
contado como un cero del RAG, darían una comparativa perfectamente presentable y
completamente falsa.

    pytest -q
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from eval_ragas.comparar import (
    alinear,
    bloque_operacion,
    comparar_metrica,
    holm,
    pares_validos,
    solape_fragmentos,
    wilcoxon_pareado,
)
from eval_ragas.graficas import fmt_signo


def corrida(notas, resultados=None, fragmentos=None, ids=None) -> pd.DataFrame:
    """Un entregable mínimo: una métrica, `faithfulness`, y lo imprescindible."""
    n = len(notas)
    ids = ids or [str(i) for i in range(1, n + 1)]
    return pd.DataFrame({
        "ID": ids,
        "Categoria": ["PREGUNTAS DIRECTAS"] * n,
        "user_input": [f"pregunta {i}" for i in ids],
        "faithfulness": notas,
        "resultado": resultados or ["OK"] * n,
        "fragmentos": fragmentos or ["a.md#0001 | b.md#0002"] * n,
    })


# ── Alineado ──────────────────────────────────────────────────────────────────
class TestAlinear:
    def test_empareja_por_id(self):
        par, _, _ = alinear(corrida([0.1, 0.2]), corrida([0.3, 0.4]))
        assert list(par["ID"]) == ["1", "2"]
        assert list(par["faithfulness_a"]) == [0.1, 0.2]
        assert list(par["faithfulness_b"]) == [0.3, 0.4]

    def test_señala_los_ids_desparejados(self):
        a = corrida([0.1, 0.2, 0.3], ids=["1", "2", "3"])
        b = corrida([0.4, 0.5], ids=["2", "9"])
        par, solo_a, solo_b = alinear(a, b)
        assert list(par["ID"]) == ["2"]
        assert solo_a == ["1", "3"]
        assert solo_b == ["9"]

    def test_empareja_aunque_las_filas_vayan_en_otro_orden(self):
        # Cada corrida se reanuda por su cuenta y puede acabar desordenada.
        a = corrida([0.1, 0.2], ids=["1", "2"])
        b = corrida([0.9, 0.8], ids=["2", "1"])
        par, _, _ = alinear(a, b)
        assert list(par["ID"]) == ["1", "2"]
        assert list(par["faithfulness_b"]) == [0.8, 0.9]

    def test_ordena_los_ids_numericamente(self):
        # "10" va después de "9", no antes como en orden alfabético.
        ids = ["10", "9", "1"]
        par, _, _ = alinear(corrida([0.1] * 3, ids=ids), corrida([0.2] * 3, ids=ids))
        assert list(par["ID"]) == ["1", "9", "10"]


# ── Política de exclusión ─────────────────────────────────────────────────────
class TestParesValidos:
    def test_un_error_en_un_lado_tumba_el_par_entero(self):
        # Una media sobre 3 preguntas frente a otra sobre 2 no sería pareada.
        a = corrida([0.5, 0.6, 0.7])
        b = corrida([0.5, 0.6, 0.7], resultados=["OK", "ERROR", "OK"])
        par, _, _ = alinear(a, b)
        x, y = pares_validos(par, "faithfulness")
        assert len(x) == 2 and len(y) == 2

    def test_un_rechazo_se_conserva(self):
        # Las 94 preguntas están en el corpus: negarse a responder es un fallo
        # del sistema, no un dato que falte.
        a = corrida([0.5, 0.0])
        b = corrida([0.5, 0.9], resultados=["OK", "RECHAZO"])
        par, _, _ = alinear(a, b)
        assert len(pares_validos(par, "faithfulness")[0]) == 2

    def test_solo_ok_deja_fuera_los_rechazos(self):
        a = corrida([0.5, 0.0])
        b = corrida([0.5, 0.9], resultados=["OK", "RECHAZO"])
        par, _, _ = alinear(a, b)
        assert len(pares_validos(par, "faithfulness", solo_ok=True)[0]) == 1

    def test_un_nan_descarta_el_par_solo_en_esa_metrica(self):
        # Un NaN es un fallo del juez, no del RAG. Rellenarlo con 0 convertiría
        # una caída de la API en una regresión del sistema.
        a = corrida([0.5, float("nan"), 0.7])
        a["answer_relevancy"] = [0.1, 0.2, 0.3]
        b = corrida([0.5, 0.6, 0.7])
        b["answer_relevancy"] = [0.4, 0.5, 0.6]
        par, _, _ = alinear(a, b)
        assert len(pares_validos(par, "faithfulness")[0]) == 2
        assert len(pares_validos(par, "answer_relevancy")[0]) == 3

    def test_una_metrica_ausente_no_revienta(self):
        par, _, _ = alinear(corrida([0.5]), corrida([0.6]))
        assert pares_validos(par, "no_existe") == ([], [])


# ── Estadísticos ──────────────────────────────────────────────────────────────
class TestCompararMetrica:
    def test_el_delta_es_b_menos_a(self):
        par, _, _ = alinear(corrida([0.2, 0.4]), corrida([0.5, 0.7]))
        assert comparar_metrica(par, "faithfulness")["delta"] == pytest.approx(0.3)

    def test_cuenta_en_que_proporcion_gana_b(self):
        par, _, _ = alinear(corrida([0.5, 0.5, 0.5, 0.5]),
                            corrida([0.9, 0.9, 0.9, 0.1]))
        assert comparar_metrica(par, "faithfulness")["gana_b"] == pytest.approx(0.75)

    def test_la_n_es_la_de_los_pares_usados(self):
        a = corrida([0.5, float("nan"), 0.7])
        b = corrida([0.5, 0.6, 0.7])
        par, _, _ = alinear(a, b)
        assert comparar_metrica(par, "faithfulness")["n"] == 2

    def test_sin_pares_devuelve_todo_a_none(self):
        a = corrida([0.5], resultados=["ERROR"])
        par, _, _ = alinear(a, corrida([0.6]))
        fila = comparar_metrica(par, "faithfulness")
        assert fila["n"] == 0 and fila["delta"] is None and fila["p"] is None

    def test_el_porcentaje_se_calla_si_la_base_es_casi_cero(self):
        # Pasar de 0,001 a 0,002 imprimiría «+100 %», que engaña más que informa.
        par, _, _ = alinear(corrida([0.001, 0.001]), corrida([0.002, 0.002]))
        assert comparar_metrica(par, "faithfulness")["delta_pct"] is None

    def test_el_porcentaje_sale_si_la_base_es_suficiente(self):
        par, _, _ = alinear(corrida([0.4, 0.4]), corrida([0.5, 0.5]))
        assert comparar_metrica(par, "faithfulness")["delta_pct"] == pytest.approx(0.25)

    def test_la_mediana_de_las_diferencias_es_el_tamaño_del_efecto(self):
        par, _, _ = alinear(corrida([0.1, 0.2, 0.3]), corrida([0.2, 0.5, 0.4]))
        assert comparar_metrica(par, "faithfulness")["mediana_delta"] == pytest.approx(0.1)


class TestWilcoxon:
    def test_todas_las_diferencias_a_cero_no_revienta(self):
        # scipy lanza ValueError; aquí tiene que salir «no hay nada que contrastar».
        assert wilcoxon_pareado([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]) == (None, None)

    def test_sin_datos_devuelve_none(self):
        assert wilcoxon_pareado([], []) == (None, None)

    def test_una_diferencia_sistematica_da_un_p_pequeño(self):
        x = [0.1 * i for i in range(1, 11)]
        y = [v + 0.2 for v in x]
        _, p = wilcoxon_pareado(x, y)
        assert p is not None and p < 0.05


class TestHolm:
    def test_multiplica_por_el_numero_de_contrastes_restantes(self):
        # Con m=3: el menor por 3, el siguiente por 2, el mayor por 1.
        assert holm([0.01, 0.02, 0.60]) == pytest.approx([0.03, 0.04, 0.60])

    def test_es_monotono(self):
        # Un p ajustado nunca puede quedar por debajo del de otro con p crudo menor.
        ajustados = holm([0.02, 0.021, 0.5])
        assert ajustados == sorted(ajustados)

    def test_nunca_pasa_de_uno(self):
        assert all(v <= 1.0 for v in holm([0.4, 0.5, 0.6]))

    def test_nunca_baja_del_p_crudo(self):
        crudos = [0.01, 0.2, 0.7]
        assert all(a >= c for c, a in zip(crudos, holm(crudos)))

    def test_ignora_los_huecos_y_conserva_las_posiciones(self):
        ajustados = holm([0.01, None, 0.02])
        assert ajustados[1] is None
        assert ajustados[0] is not None and ajustados[2] is not None

    def test_sin_ningun_p_devuelve_huecos(self):
        assert holm([None, None]) == [None, None]


# ── Solape de fragmentos ──────────────────────────────────────────────────────
class TestSolapeFragmentos:
    def test_contextos_identicos_dan_uno(self):
        par, _, _ = alinear(corrida([0.5], fragmentos=["a#1 | b#2"]),
                            corrida([0.5], fragmentos=["a#1 | b#2"]))
        assert solape_fragmentos(par) == [1.0]

    def test_contextos_disjuntos_dan_cero(self):
        par, _, _ = alinear(corrida([0.5], fragmentos=["a#1"]),
                            corrida([0.5], fragmentos=["z#9"]))
        assert solape_fragmentos(par) == [0.0]

    def test_es_jaccard_interseccion_entre_union(self):
        par, _, _ = alinear(corrida([0.5], fragmentos=["a#1 | b#2"]),
                            corrida([0.5], fragmentos=["b#2 | c#3"]))
        assert solape_fragmentos(par) == [pytest.approx(1 / 3)]

    def test_el_orden_de_los_fragmentos_no_importa(self):
        par, _, _ = alinear(corrida([0.5], fragmentos=["a#1 | b#2"]),
                            corrida([0.5], fragmentos=["b#2 | a#1"]))
        assert solape_fragmentos(par) == [1.0]

    def test_las_celdas_vacias_no_cuentan(self):
        par, _, _ = alinear(corrida([0.5], fragmentos=[""]),
                            corrida([0.5], fragmentos=[""]))
        assert solape_fragmentos(par) == []

    def test_un_error_no_se_cuenta_como_contexto_vacio(self):
        a = corrida([0.5], resultados=["OK"], fragmentos=["a#1 | b#2"])
        b = corrida([0.5], resultados=["ERROR"], fragmentos=[""])
        par, _, _ = alinear(a, b)
        assert solape_fragmentos(par) == []


class TestBloqueOperacion:
    def test_excluye_errores_de_medias_y_rechazos(self):
        a = corrida([0.5, 0.6], resultados=["OK", "OK"])
        b = corrida([0.6, 0.0], resultados=["OK", "ERROR"])
        par, _, _ = alinear(a, b)
        par["latencia_s_a"] = [10.0, 100.0]
        par["latencia_s_b"] = [20.0, 0.0]
        par["n_citas_a"] = [3, 9]
        par["n_citas_b"] = [4, 0]

        html = bloque_operacion(par, ("a", "b"))

        assert "10,00 s" in html
        assert "20,00 s" in html
        assert "3,00" in html
        assert "4,00" in html
        assert "<td>1</td>" in html  # El error sigue visible en su propia fila.


# ── Formateo del delta ────────────────────────────────────────────────────────
class TestFmtSigno:
    def test_el_signo_va_siempre(self):
        assert fmt_signo(0.012) == "+0,012"
        assert fmt_signo(-0.012) == "-0,012"

    def test_coma_decimal(self):
        assert "," in fmt_signo(1.5) and "." not in fmt_signo(1.5)

    def test_sin_valor_una_raya(self):
        assert fmt_signo(None) == "—"
        assert fmt_signo(math.nan) == "—"
