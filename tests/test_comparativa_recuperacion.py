"""Pruebas de la estadística local para las ablaciones de recuperación."""

import numpy as np
import pandas as pd
import pytest

from eval_ragas.tfg.comparativa_recuperacion import filas_validas_k
from eval_ragas.estadistica import bootstrap_ic_pareado, friedman_pareado


class TestFriedmanPareado:
    def test_detecta_orden_consistente_en_tres_configuraciones(self):
        base = np.arange(1.0, 13.0)
        estadistico, p = friedman_pareado([base, base + 1, base + 2])
        assert estadistico is not None and estadistico > 0
        assert p is not None and p < 0.05

    def test_empate_total_devuelve_p_uno(self):
        notas = np.array([0.0, 0.5, 1.0])
        estadistico, p = friedman_pareado([notas, notas.copy(), notas.copy()])
        assert estadistico == 0.0
        assert p == 1.0

    def test_no_acepta_series_desparejadas(self):
        assert friedman_pareado([[1, 2, 3], [1, 2], [1, 2, 3]]) == (None, None)


class TestBootstrapPareado:
    def test_delta_constante_tiene_intervalo_degenerado(self):
        a = [0.1, 0.2, 0.3, 0.4]
        b = [0.2, 0.3, 0.4, 0.5]
        ic = bootstrap_ic_pareado(a, b, ["directa", "directa", "síntesis", "síntesis"],
                                  replicas=500, semilla=7)
        assert ic == pytest.approx((0.1, 0.1))

    def test_respetar_categorias_no_altera_delta_constante(self):
        ic = bootstrap_ic_pareado([1, 2, 3], [1, 2, 3], ["d", "s", "i"],
                                  replicas=300, semilla=19)
        assert ic == (0.0, 0.0)


class TestFilasValidasK:
    def test_excluye_error_y_nan_de_cualquiera_de_los_tres_k(self):
        datos = pd.DataFrame({
            "ID": ["1", "2", "3"],
            "resultado_K=3": ["OK", "OK", "OK"],
            "resultado_K=5": ["OK", "ERROR", "OK"],
            "resultado_K=8": ["OK", "OK", "OK"],
            "factual_correctness_K=3": [0.5, 0.6, 0.7],
            "factual_correctness_K=5": [0.5, 0.6, np.nan],
            "factual_correctness_K=8": [0.6, 0.7, 0.8],
        })
        validas = filas_validas_k(datos, "factual_correctness")
        assert list(validas["ID"]) == ["1"]
