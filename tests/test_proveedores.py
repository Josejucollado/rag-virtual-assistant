"""
Tests del registro de proveedores de embeddings.

Sólo funciones puras sobre `PROVEEDORES_EMBEDDINGS`: no construyen ningún
cliente, no piden ninguna clave y no tocan la red.

Lo que protegen es el invariante que da sentido a todo el registro: que el
modelo, las dimensiones, la colección y el directorio de un proveedor no se
puedan descasar. Indexar con un modelo y consultar con otro no da error, sólo un
recuperador que devuelve basura, así que una errata de copiar y pegar entre dos
entradas del registro sería invisible sin estos tests.

    pytest -q
"""

from __future__ import annotations

import pytest

from rag import (
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    PROVEEDORES_EMBEDDINGS,
    COLLECTION,
    ErrorConfiguracion,
    resolver_proveedor,
)
from rag.config import _FABRICAS_EMBEDDINGS


# ── Resolución ────────────────────────────────────────────────────────────────
class TestResolverProveedor:
    """`resolver_proveedor` es el único punto de entrada al registro."""

    def test_sin_argumento_devuelve_el_activo(self):
        assert resolver_proveedor().nombre == EMBEDDING_PROVIDER

    def test_por_nombre(self):
        assert resolver_proveedor("blablador").nombre == "blablador"

    def test_normaliza_espacios_y_mayusculas(self):
        assert resolver_proveedor("  BLABLADOR ").nombre == "blablador"

    def test_desconocido_es_error_de_configuracion(self):
        # Y no un KeyError: los errores de configuración se presentan como un
        # mensaje legible, no como una traza.
        with pytest.raises(ErrorConfiguracion):
            resolver_proveedor("inventado")

    def test_el_error_lista_los_disponibles(self):
        with pytest.raises(ErrorConfiguracion) as exc:
            resolver_proveedor("inventado")
        for nombre in PROVEEDORES_EMBEDDINGS:
            assert nombre in str(exc.value)

    def test_el_error_dice_como_elegirlo(self):
        with pytest.raises(ErrorConfiguracion) as exc:
            resolver_proveedor("inventado")
        assert "EMBEDDING_PROVIDER" in str(exc.value)


# ── Contenido del registro ────────────────────────────────────────────────────
class TestRegistro:
    def test_blablador_apunta_al_endpoint_compatible(self):
        blablador = PROVEEDORES_EMBEDDINGS["blablador"]
        assert blablador.base_url is not None
        assert blablador.base_url.endswith("/v1")
        assert blablador.var_clave == "BLABLADOR_API_KEY"

    def test_blablador_usa_la_dimension_nativa(self):
        blablador = PROVEEDORES_EMBEDDINGS["blablador"]
        assert blablador.dims == blablador.dims_nativas

    def test_cada_nombre_coincide_con_su_clave(self):
        for clave, proveedor in PROVEEDORES_EMBEDDINGS.items():
            assert proveedor.nombre == clave

    def test_las_colecciones_son_todas_distintas(self):
        colecciones = [p.coleccion for p in PROVEEDORES_EMBEDDINGS.values()]
        assert len(set(colecciones)) == len(colecciones)

    def test_los_directorios_son_todos_distintos(self):
        # Dos proveedores compartiendo directorio no daría error: daría dos
        # colecciones en el mismo chroma.sqlite3.
        directorios = [p.directorio for p in PROVEEDORES_EMBEDDINGS.values()]
        assert len(set(directorios)) == len(directorios)

    def test_nunca_se_trunca_hacia_arriba(self):
        for proveedor in PROVEEDORES_EMBEDDINGS.values():
            assert proveedor.dims <= proveedor.dims_nativas

    def test_cada_api_tiene_fabrica(self):
        for proveedor in PROVEEDORES_EMBEDDINGS.values():
            assert proveedor.api in _FABRICAS_EMBEDDINGS

    def test_el_registro_es_inmutable(self):
        with pytest.raises(Exception):
            PROVEEDORES_EMBEDDINGS["blablador"].dims = 999


# ── Vistas derivadas ──────────────────────────────────────────────────────────
class TestVistasDerivadas:
    """Las constantes de módulo son vistas del proveedor activo, no copias."""

    def test_coinciden_con_el_proveedor_activo(self):
        activo = resolver_proveedor()
        assert (COLLECTION, EMBEDDING_MODEL, EMBEDDING_DIMS) == (
            activo.coleccion, activo.modelo, activo.dims
        )
