"""
Tests del truncado Matryoshka y del prefijo de instrucción de Qwen3.

Sólo funciones puras: no construyen ningún cliente ni llaman a ninguna API.

Lo que protegen son dos fallos que no dan error, sólo peores resultados: truncar
un vector por donde no toca, y mandarle al modelo un prompt distinto del
documentado porque los ficheros de este repositorio llevan CRLF.

    pytest -q
"""

from __future__ import annotations

import math

import pytest

from rag import ErrorConfiguracion, consulta_con_instruccion
from rag.config import (
    PLANTILLA_CONSULTA_QWEN,
    TAREA_QWEN,
    _normalizar,
    _truncar,
)


def norma(vector) -> float:
    return math.sqrt(sum(c * c for c in vector))


# ── Truncado ──────────────────────────────────────────────────────────────────
class TestTruncar:
    """Matryoshka trunca por prefijo: las primeras componentes, no otras."""

    def test_deja_la_dimension_pedida(self):
        assert len(_truncar([[0.5] * 4096], 1536)[0]) == 1536

    def test_es_un_prefijo_y_no_una_submuestra(self):
        # Quedarse con otras componentes cualesquiera destruiría el vector sin
        # dar ningún error.
        assert _truncar([[0.0, 1.0, 2.0, 3.0]], 2) == [[0.0, 1.0]]

    def test_respeta_el_orden_de_los_vectores(self):
        assert _truncar([[1.0, 9.0], [2.0, 9.0]], 1) == [[1.0], [2.0]]

    def test_no_toca_un_vector_que_ya_mide_lo_pedido(self):
        assert _truncar([[1.0, 2.0]], 2) == [[1.0, 2.0]]

    def test_vector_mas_corto_de_lo_pedido_es_error_de_configuracion(self):
        # Pasaría si el proveedor reapuntara su alias a un modelo más pequeño.
        with pytest.raises(ErrorConfiguracion):
            _truncar([[0.1, 0.2]], 1536)

    def test_el_error_dice_cuantas_componentes_llegaron(self):
        with pytest.raises(ErrorConfiguracion) as exc:
            _truncar([[0.1, 0.2]], 1536)
        assert "2" in str(exc.value) and "1536" in str(exc.value)


# ── Renormalización ───────────────────────────────────────────────────────────
class TestNormalizar:
    """Truncar rompe la norma unitaria y hay que rehacerla a mano."""

    def test_deja_norma_uno(self):
        assert norma(_normalizar([[3.0, 4.0]])[0]) == pytest.approx(1.0, abs=1e-6)

    def test_tras_truncar_la_norma_vuelve_a_ser_uno(self):
        largo = [1.0] * 4096
        assert norma(_normalizar(_truncar([largo], 1536))[0]) == pytest.approx(1.0, abs=1e-6)

    def test_el_vector_cero_no_divide_por_cero(self):
        assert _normalizar([[0.0, 0.0]])[0] == [0.0, 0.0]

    def test_conserva_la_direccion(self):
        v = _normalizar([[3.0, 4.0]])[0]
        assert v[1] / v[0] == pytest.approx(4.0 / 3.0, rel=1e-5)


# ── Prefijo de instrucción de Qwen3 ───────────────────────────────────────────
class TestConsultaConInstruccion:
    """Asimetría consulta/documento por instrucción."""

    def test_la_plantilla_no_lleva_retorno_de_carro(self):
        # El test que blinda la trampa: escrita como cadena triple, en un
        # fichero con CRLF la plantilla se llevaría un \r y se le estaría
        # mandando al modelo un prompt distinto del documentado.
        assert "\r" not in PLANTILLA_CONSULTA_QWEN
        assert PLANTILLA_CONSULTA_QWEN.count("\n") == 1

    def test_formato_exacto(self):
        assert consulta_con_instruccion("¿qué es la paginación?") == (
            f"Instruct: {TAREA_QWEN}\nQuery: ¿qué es la paginación?"
        )

    def test_la_consulta_va_al_final_y_sin_recortar(self):
        salida = consulta_con_instruccion("  con espacios  ")
        assert salida.endswith("Query:   con espacios  ")

    def test_el_resultado_tampoco_lleva_retorno_de_carro(self):
        assert "\r" not in consulta_con_instruccion("una consulta")

    def test_la_tarea_va_en_ingles(self):
        # Es el idioma en el que se instruyó al modelo; la consulta va en
        # castellano, como el corpus.
        assert TAREA_QWEN.startswith("Given a question")
