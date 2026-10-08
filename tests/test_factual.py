"""
Tests de la corrección factual propia (`eval_ragas.metricas.CorreccionFactual`).

La cuenta vive en `puntuacion_factual`, que es pura: recibe los veredictos del
juez y devuelve la nota, así que se prueba sin API. Los casos salen de prueba10,
donde la cobertura de RAGAS daba 0 a respuestas que cubrían el ground truth
entero.

Importa `ragas` (a través de `metricas`), así que tarda unos segundos en cargar.

    python -m pytest -q tests/test_factual.py
"""

from __future__ import annotations

import math

import pytest

from eval_ragas.metricas import CATALOGO, CorreccionFactual, puntuacion_factual


class TestCobertura:
    def test_cubrir_todo_el_ground_truth_es_1(self):
        # Pregunta 4 de prueba10: el juez no respaldaba ninguna afirmación de la
        # respuesta, pero la respuesta sí cubría las 2 del ground truth. RAGAS: 0.
        assert puntuacion_factual([False, False, False], [True, True], "recall") == 1.0

    def test_no_premia_la_verbosidad(self):
        # Con la fórmula de RAGAS, 10 afirmaciones respaldadas y 1 de 2 del
        # ground truth cubierta darían 10/11. La cobertura real es la mitad.
        assert puntuacion_factual([True] * 10, [True, False], "recall") == 0.5

    def test_no_depende_de_la_respuesta(self):
        assert (puntuacion_factual([], [True, False], "recall")
                == puntuacion_factual([True, True], [True, False], "recall"))


class TestPrecisionYF1:
    def test_precision(self):
        assert puntuacion_factual([True, False, False, False], [True], "precision") == 0.25

    def test_f1_es_la_media_armonica(self):
        # Pregunta 4 con la pregunta en la premisa: 1 de 3 respaldadas, 2 de 2 cubiertas.
        assert puntuacion_factual([True, False, False], [True, True], "f1") == pytest.approx(0.5)

    def test_responder_de_mas_baja_la_f1(self):
        concisa = puntuacion_factual([True], [True], "f1")
        larga = puntuacion_factual([True] + [False] * 9, [True], "f1")
        assert concisa == 1.0 and larga < 0.25

    def test_sin_nada_en_comun_es_0(self):
        assert puntuacion_factual([False, False], [False], "f1") == 0.0


class TestCasosLimite:
    def test_respuesta_sin_afirmaciones_no_es_precisa(self):
        assert puntuacion_factual([], [True], "precision") == 0.0
        assert puntuacion_factual([], [True], "f1") == 0.0

    def test_ground_truth_sin_afirmaciones_es_nan(self):
        # Es un fallo del juez al descomponer: tiene que verse, no contar como 0.
        assert math.isnan(puntuacion_factual([True], [], "recall"))
        assert math.isnan(puntuacion_factual([True], [], "f1"))

    def test_acepta_arrays_de_numpy(self):
        np = pytest.importorskip("numpy")
        assert puntuacion_factual(np.array([True, False]), np.array([True]), "f1") == pytest.approx(2 / 3)


class TestMetrica:
    def test_la_pregunta_llega_a_la_metrica(self):
        # RAGAS le quita a la muestra las columnas no declaradas: sin esto, la
        # premisa con la pregunta se construiría con `None`.
        from ragas.metrics.base import MetricType

        requeridas = CorreccionFactual()._required_columns[MetricType.SINGLE_TURN]
        assert "user_input" in requeridas

    def test_conserva_el_nombre_de_ragas(self):
        # Las plantillas en español y `mapear_columnas` la encuentran por él.
        assert CorreccionFactual().name == "factual_correctness"

    def test_las_dos_caras_usan_la_version_propia(self):
        for corto in ("factual_correctness", "factual_recall"):
            assert CATALOGO[corto][0] is CorreccionFactual
