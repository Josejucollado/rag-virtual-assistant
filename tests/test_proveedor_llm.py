"""
Tests del proveedor del generador (Blablador gratuito u OpenAI de pago) y de la
cuenta del gasto.

Sin API: se construyen los objetos `ChatOpenAI` con claves falsas, que no hacen
ninguna petición al crearse, y se comprueba qué se les pasa.

Lo que protegen, por orden de gravedad:
  - que el juez no se mude nunca a OpenAI (invariante 6);
  - que con OpenAI no se pueda gastar sin haber elegido modelo;
  - que las corridas `libre_*` sigan construyéndose exactamente igual;
  - que el coste no se cuente dos veces (el razonamiento va dentro de la salida).

    python -m pytest -q tests/test_proveedor_llm.py
"""

from __future__ import annotations

import pytest

from rag import (
    MAX_TOKENS_SALIDA_RAG,
    MODEL_JUDGE,
    PROVEEDORES_LLM,
    TEMPERATURA,
    ErrorConfiguracion,
    construir_llm,
    construir_llm_juez,
    coste_usd,
    es_razonador_openai,
    opciones_generador,
    precio_modelo,
    resolver_modelo_rag,
)
from rag.config import MODELO_RAG_BLABLADOR, URL_BLABLADOR


# ── Qué modelo genera ─────────────────────────────────────────────────────────
class TestResolverModeloRag:
    def test_blablador_por_defecto_es_gpt_oss(self):
        assert resolver_modelo_rag("blablador", {}) == MODELO_RAG_BLABLADOR

    def test_blablador_se_puede_cambiar(self):
        assert resolver_modelo_rag("blablador", {"BLABLADOR_MODEL_RAG": "x"}) == "x"

    def test_openai_sin_modelo_es_error_y_no_gasta(self):
        with pytest.raises(ErrorConfiguracion, match="OPENAI_MODEL_RAG"):
            resolver_modelo_rag("openai", {})

    def test_openai_con_modelo_en_blanco_tambien_es_error(self):
        with pytest.raises(ErrorConfiguracion):
            resolver_modelo_rag("openai", {"OPENAI_MODEL_RAG": "   "})

    def test_openai_usa_el_modelo_pedido(self):
        assert resolver_modelo_rag("openai", {"OPENAI_MODEL_RAG": "gpt-5.1-2025-11-13"}) \
            == "gpt-5.1-2025-11-13"

    def test_proveedor_desconocido_lista_los_disponibles(self):
        with pytest.raises(ErrorConfiguracion, match="blablador"):
            resolver_modelo_rag("gemini", {})


def test_solo_openai_es_de_pago():
    assert PROVEEDORES_LLM["openai"].de_pago
    assert not PROVEEDORES_LLM["blablador"].de_pago


# ── Parámetros según el modelo ────────────────────────────────────────────────
@pytest.mark.parametrize("modelo,esperado", [
    ("gpt-5.1-2025-11-13", True),
    ("gpt-5-mini-2025-08-07", True),
    ("gpt-5-chat-latest", False),   # el -chat no razona
    ("o3-mini", True),
    ("gpt-4.1-2025-04-14", False),
    ("openai", False),              # empieza por «o» pero no es un o-número
])
def test_detecta_los_razonadores(modelo, esperado):
    assert es_razonador_openai(modelo) is esperado


def test_blablador_recibe_exactamente_lo_de_siempre():
    # Las corridas libre_* se hicieron con temperatura 0 y nada más: si esto
    # cambiara, dejarían de ser reproducibles con el código actual.
    assert opciones_generador("blablador", MODELO_RAG_BLABLADOR) == {"temperature": TEMPERATURA}


def test_un_razonador_de_openai_no_lleva_temperatura():
    op = opciones_generador("openai", "gpt-5.1-2025-11-13")
    assert "temperature" not in op
    assert op["reasoning_effort"] == "low"
    assert op["max_completion_tokens"] == MAX_TOKENS_SALIDA_RAG


def test_un_modelo_de_openai_sin_razonamiento_va_a_temperatura_cero():
    op = opciones_generador("openai", "gpt-4.1-2025-04-14")
    assert op["temperature"] == TEMPERATURA
    assert "reasoning_effort" not in op


# ── Construcción de los modelos ───────────────────────────────────────────────
@pytest.fixture
def claves_falsas(monkeypatch):
    monkeypatch.setenv("BLABLADOR_API_KEY", "clave-blablador-falsa")
    monkeypatch.setenv("OPENAI_API_KEY", "clave-openai-falsa")


def test_el_juez_se_queda_en_blablador(claves_falsas):
    juez = construir_llm_juez()
    assert juez.openai_api_base == URL_BLABLADOR
    assert juez.model_name == MODEL_JUDGE
    assert juez.temperature == TEMPERATURA
    assert juez.openai_api_key.get_secret_value() == "clave-blablador-falsa"


def test_el_generador_de_openai_va_al_endpoint_oficial(claves_falsas):
    llm = construir_llm("gpt-5.1-2025-11-13", "openai")
    assert llm.openai_api_base is None
    assert llm.openai_api_key.get_secret_value() == "clave-openai-falsa"
    assert llm.reasoning_effort == "low"
    assert llm.max_tokens == MAX_TOKENS_SALIDA_RAG
    assert llm.temperature is None


def test_las_opciones_explicitas_mandan(claves_falsas):
    llm = construir_llm(MODELO_RAG_BLABLADOR, timeout=12)
    assert llm.request_timeout == 12
    assert llm.openai_api_base == URL_BLABLADOR


def test_sin_clave_de_openai_es_error_de_configuracion(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ErrorConfiguracion, match="OPENAI_API_KEY"):
        construir_llm("gpt-5.1-2025-11-13", "openai")


def test_un_proveedor_de_chat_desconocido_es_error(claves_falsas):
    with pytest.raises(ErrorConfiguracion):
        construir_llm("x", "gemini")


# ── Precios y coste ───────────────────────────────────────────────────────────
def test_gana_el_prefijo_mas_largo():
    # «gpt-5» es prefijo de «gpt-5-mini»: con el primero que encajara, la mini
    # se contaría al precio del modelo grande.
    assert precio_modelo("gpt-5-mini-2025-08-07") == (0.25, 0.025, 2.0)
    assert precio_modelo("gpt-5.1-2025-11-13") == (1.25, 0.125, 10.0)


def test_un_modelo_sin_precio_es_gratis():
    assert precio_modelo(MODELO_RAG_BLABLADOR) is None
    assert coste_usd(MODELO_RAG_BLABLADOR, 10_000, 5_000) == 0.0


def test_coste_de_una_llamada():
    # 2600 de entrada a 1,25 $/M y 700 de salida (razonamiento incluido) a 10 $/M.
    assert coste_usd("gpt-5.1-x", 2600, 700) == pytest.approx(0.00325 + 0.007)


def test_la_entrada_en_cache_se_cobra_a_su_precio():
    sin = coste_usd("gpt-5.1-x", 1000, 0)
    con = coste_usd("gpt-5.1-x", 1000, 0, entrada_cache=1000)
    assert con == pytest.approx(sin / 10)


def test_el_peor_caso_de_una_corrida_cabe_en_el_credito():
    # 109 preguntas agotando el tope de salida, con ~2800 tokens de entrada:
    # es la cuenta que justifica MAX_TOKENS_SALIDA_RAG frente a un crédito de 5 $.
    peor = 109 * coste_usd("gpt-5.1-x", 2800, MAX_TOKENS_SALIDA_RAG)
    assert peor < 5.0
