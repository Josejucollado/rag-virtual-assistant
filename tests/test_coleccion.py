"""
Tests de la guardia que contrasta la colección con la configuración activa.

`comprobar_identidad` es pura a propósito: recibe datos, no un objeto de Chroma,
así que estos tests no abren ninguna base de datos. Quien sabe de Chroma es
`rag.recuperacion._identidad_coleccion`, que sólo lee campos ya materializados.

Lo que protegen es la frontera entre «avisar» y «negarse»: una colección anterior
al sello tiene que seguir funcionando —es la que viaja con el repositorio, y
sellarla costaría dinero—, pero una discrepancia real tiene que parar el proceso
antes de producir respuestas construidas sobre fragmentos equivocados.

    pytest -q
"""

from __future__ import annotations

import pytest

from rag import (
    DISTANCIA,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    ErrorConfiguracion,
    comprobar_identidad,
)

# Una colección que cuadra con la configuración activa en todo.
CORRECTA = {
    "coleccion": "documentacion",
    "n_vectores": 762,
    "dims_reales": EMBEDDING_DIMS,
    "espacio": DISTANCIA,
    "modelo_sellado": EMBEDDING_MODEL,
    "dims_selladas": EMBEDDING_DIMS,
    "chunks_sellados": 762,
}


def identidad(**cambios):
    return {**CORRECTA, **cambios}


# ── Todo en orden ─────────────────────────────────────────────────────────────
class TestCuadra:
    def test_sin_discrepancias_no_dice_nada(self):
        assert comprobar_identidad(**CORRECTA) is None

    def test_sin_sello_pero_consistente_tampoco_avisa(self):
        # Las dimensiones y la distancia, que son lo que protege de verdad, ya se
        # comprueban sin sello.
        assert comprobar_identidad(**identidad(
            modelo_sellado=None, dims_selladas=None, chunks_sellados=None,
        )) is None


# ── Discrepancias que tienen que parar el proceso ─────────────────────────────
class TestErrores:
    def test_coleccion_vacia(self):
        with pytest.raises(ErrorConfiguracion):
            comprobar_identidad(**identidad(n_vectores=0))

    def test_la_coleccion_vacia_dice_como_indexar(self):
        with pytest.raises(ErrorConfiguracion) as exc:
            comprobar_identidad(**identidad(n_vectores=0))
        assert "python -m cli.process_md --reset" in str(exc.value)

    def test_dimension_distinta(self):
        with pytest.raises(ErrorConfiguracion):
            comprobar_identidad(**identidad(dims_reales=3072))

    def test_la_dimension_se_comprueba_aunque_no_haya_sello(self):
        # Es la única comprobación que también protege a la colección heredada:
        # Chroma siempre sabe de cuántas componentes son sus vectores.
        with pytest.raises(ErrorConfiguracion):
            comprobar_identidad(**identidad(
                dims_reales=768, modelo_sellado=None, dims_selladas=None,
            ))

    def test_distancia_distinta(self):
        with pytest.raises(ErrorConfiguracion):
            comprobar_identidad(**identidad(espacio="l2"))

    def test_modelo_sellado_distinto(self):
        with pytest.raises(ErrorConfiguracion):
            comprobar_identidad(**identidad(modelo_sellado="otro-modelo"))

    def test_el_error_del_modelo_nombra_los_dos(self):
        with pytest.raises(ErrorConfiguracion) as exc:
            comprobar_identidad(**identidad(modelo_sellado="otro-modelo"))
        mensaje = str(exc.value)
        assert "otro-modelo" in mensaje and EMBEDDING_MODEL in mensaje

    def test_dimension_sellada_distinta(self):
        with pytest.raises(ErrorConfiguracion):
            comprobar_identidad(**identidad(dims_selladas=768))

    def test_nunca_lanza_system_exit(self):
        # SystemExit hereda de BaseException, así que un `except Exception` no la
        # vería y el hilo de arranque de la web se quedaría cargando para siempre.
        with pytest.raises(ErrorConfiguracion):
            comprobar_identidad(**identidad(modelo_sellado="otro-modelo"))


# ── Estados raros pero utilizables ────────────────────────────────────────────
class TestAvisos:
    def test_sin_distancia_declarada_avisa(self):
        # Sólo puede pasar si la colección no la creó `cli/process_md.py`. No es
        # fatal —con vectores normalizados coseno y L2 ordenan igual— pero sí
        # señal de que alguien la creó por accidente al consultar.
        aviso = comprobar_identidad(**identidad(espacio=None))
        assert isinstance(aviso, str) and "distancia" in aviso

    def test_indexado_a_medias_avisa(self):
        aviso = comprobar_identidad(**identidad(n_vectores=500, chunks_sellados=762))
        assert isinstance(aviso, str)
        assert "500" in aviso and "762" in aviso

    def test_el_aviso_de_indexado_a_medias_dice_como_completarlo(self):
        aviso = comprobar_identidad(**identidad(n_vectores=500, chunks_sellados=762))
        assert "process_md" in aviso

    def test_los_avisos_se_acumulan(self):
        aviso = comprobar_identidad(**identidad(
            espacio=None, n_vectores=500, chunks_sellados=762,
        ))
        assert "distancia" in aviso and "500" in aviso
