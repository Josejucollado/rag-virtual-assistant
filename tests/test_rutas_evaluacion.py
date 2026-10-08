"""
Tests de las rutas de salida de la evaluación, una por corrida.

Sin API y sin tocar el disco: sólo se comprueba cómo se derivan las rutas y qué
forma tiene la línea de configuración que acaba en la cabecera del informe.

Lo que protegen es que dos corridas no se pisen. Evaluar con otro proveedor
escribiendo en el mismo fichero destruiría el entregable de la corrida anterior,
que es justo aquel con el que hay que compararla.

    pytest -q
"""

from __future__ import annotations

from eval_ragas.comun import (
    COMPARATIVA_HTML,
    EVAL_CORRIDA,
    INFORME_HTML,
    NOMBRE_RESULTADOS,
    RAGAS_DIR,
    RESPUESTAS_CSV,
    RESULTADOS_CSV,
    SALIDA_DIR,
    ruta_corrida,
    resumen_config,
)
from rag import EMBEDDING_MODEL, EMBEDDING_PROVIDER


# ── Derivación de las rutas ───────────────────────────────────────────────────
class TestRutasPorCorrida:
    def test_la_salida_cuelga_de_la_corrida(self):
        assert SALIDA_DIR.name == EVAL_CORRIDA
        assert SALIDA_DIR.parent == RAGAS_DIR

    def test_la_corrida_por_defecto_es_el_proveedor_activo(self):
        # Así no hay nada que recordar: cambiar EMBEDDING_PROVIDER cambia también
        # dónde se escribe.
        assert EVAL_CORRIDA == EMBEDDING_PROVIDER

    def test_los_tres_entregables_cuelgan_de_la_corrida(self):
        for ruta in (RESPUESTAS_CSV, RESULTADOS_CSV, INFORME_HTML):
            assert ruta.parent == SALIDA_DIR

    def test_el_nombre_del_entregable_tiene_una_sola_definicion(self):
        # `comparar.py` busca los CSV de otras corridas por este nombre.
        assert RESULTADOS_CSV.name == NOMBRE_RESULTADOS

    def test_la_comparativa_no_pertenece_a_ninguna_corrida(self):
        assert COMPARATIVA_HTML.parent == RAGAS_DIR
        assert COMPARATIVA_HTML.parent != SALIDA_DIR


class TestRutaCorrida:
    def test_normaliza_espacios_y_mayusculas(self):
        assert ruta_corrida("  BLABLADOR ").name == "blablador"

    def test_cuelga_del_directorio_de_evaluacion(self):
        assert ruta_corrida("libre_base").parent == RAGAS_DIR


# ── La línea de configuración del informe ─────────────────────────────────────
class TestResumenConfig:
    def test_incluye_el_proveedor_y_el_modelo(self):
        resumen = resumen_config()
        assert EMBEDDING_PROVIDER in resumen
        assert EMBEDDING_MODEL in resumen

    def test_el_troceado_por_puntos_sigue_dando_tres_campos(self):
        # `informe.py` hace `resumen_config().split(' · ', 2)[2]` para tirar los
        # dos primeros campos y pintar el resto en la portada. Si el dato de
        # embeddings se moviera a primera o segunda posición, esa línea se
        # rompería sin que nada lo avisara.
        assert len(resumen_config().split(" · ")) >= 3

    def test_los_embeddings_entran_en_la_cabecera_del_informe(self):
        assert "embeddings=" in resumen_config().split(" · ", 2)[2]
