"""
Tests de `analizar_recuperacion`, la función que alimenta al inspector de la
terminal (`cli/inspeccionar.py`).

Sin API, sin Chroma y sin cross-encoder real: los recuperadores y el reranker son
dobles que devuelven listas fijas. Lo que protegen es la promesa del inspector
—enseña lo que hace producción— y la clasificación de cada candidato.

El test de paridad reproduce un desajuste real: producción recorta a
RERANK_K × FACTOR candidatos ANTES de deduplicar (el `top_n` del
CrossEncoderReranker) y el inspector deduplicaba sobre todos, así que con muchos
sub-chunks de pocas secciones enseñaba 5 finalistas donde el generador recibía 3.

    python -m pytest -q tests/test_analizar.py
"""

from __future__ import annotations

from types import SimpleNamespace

from langchain_classic.retrievers.document_compressors import (
    CrossEncoderReranker,
    DocumentCompressorPipeline,
)
from langchain_classic.retrievers.document_compressors.cross_encoder import BaseCrossEncoder
from langchain_core.documents import Document

from rag import RERANK_K, DeduplicadorSecciones, analizar_recuperacion
from rag.config import FACTOR_CANDIDATOS_RERANKER


def doc(cid: str, seccion: str, fuente: str = "a.md") -> Document:
    return Document(page_content=f"texto {cid}",
                    metadata={"chunk_id": cid, "source": fuente, "h2": seccion})


class CrossEncoderFijo(BaseCrossEncoder):
    """Puntúa cada fragmento con el número que se le diga por chunk_id."""

    def __init__(self, notas: dict[str, float]):
        self.notas = notas

    def score(self, pares):
        return [self.notas[texto.removeprefix("texto ")] for _, texto in pares]


def hibrido_fijo(candidatos, ids_bm25, ids_denso):
    por_id = {d.metadata["chunk_id"]: d for d in candidatos}
    bm25 = SimpleNamespace(invoke=lambda q: [por_id[i] for i in ids_bm25])
    denso = SimpleNamespace(invoke=lambda q: [por_id[i] for i in ids_denso])
    return SimpleNamespace(retrievers=(bm25, denso), invoke=lambda q: list(candidatos))


# ── Escenario básico: 8 candidatos de 6 secciones ─────────────────────────────
CANDIDATOS = [doc("c1", "S1"), doc("c2", "S1"), doc("c3", "S2"), doc("c4", "S3"),
              doc("c5", "S4"), doc("c6", "S5"), doc("c7", "S6"), doc("c8", "S2")]
NOTAS = {"c1": 0.1, "c2": 0.9, "c3": 0.8, "c4": 0.7, "c5": 0.6,
         "c6": 0.5, "c7": 0.05, "c8": 0.95}


def analizar_basico(usar_reranker: bool = True):
    # Explícito: el defecto sale de USAR_RERANKER, y con esa variable puesta en
    # la shell estos tests medirían el otro camino.
    hibrido = hibrido_fijo(CANDIDATOS, ["c1", "c2", "c3"], ["c3", "c4", "c5", "c6", "c7", "c8"])
    return analizar_recuperacion("q", hibrido, CrossEncoderFijo(NOTAS), usar_reranker=usar_reranker)


def ids(docs):
    return [d.metadata["chunk_id"] for d in docs]


def test_los_finalistas_salen_en_orden_del_reranker_y_sin_secciones_repetidas():
    r = analizar_basico()
    ids = [d.metadata["chunk_id"] for d in r["finalistas"]]
    # c8 (S2) va primero; c3 es también S2 y queda fuera como duplicado.
    assert ids[:5] == ["c8", "c2", "c4", "c5", "c6"][:RERANK_K]


def test_clasifica_cada_candidato():
    r = analizar_basico()
    estado = {f["chunk_id"]: f["estado"] for f in r["etapa23"]}
    assert estado["c8"] == "contexto"
    assert estado["c3"] == "duplicado"   # S2 ya está dentro con c8
    assert estado["c1"] == "duplicado"   # S1 ya está dentro con c2
    assert estado["c7"] == "no_cabe"     # sección nueva, pero el contexto ya está lleno


def test_el_salto_es_antes_menos_despues():
    r = analizar_basico()
    c8 = next(f for f in r["etapa23"] if f["chunk_id"] == "c8")
    assert (c8["antes"], c8["posicion"], c8["salto"]) == (8, 1, 7)


def test_el_origen_dice_que_mitad_del_hibrido_lo_trajo():
    r = analizar_basico()
    origen = {f["chunk_id"]: f["origen"] for f in r["etapa1"]}
    assert origen["c1"] == "bm25"
    assert origen["c3"] == "ambos"
    assert origen["c8"] == "denso"


def test_la_referencia_sin_reranker_es_el_hibrido_ya_deduplicado():
    # Sin reranker, producción manda el híbrido deduplicado: c1, c3, c4, c5, c6
    # (c2 y c8 repiten sección). De esos, el reranker conserva c4, c5 y c6.
    r = analizar_basico()
    assert r["resumen"]["conserva"] == 3
    assert r["resumen"]["cambia_el_primero"] is True


# ── Paridad con producción ────────────────────────────────────────────────────
def escenario_pocas_secciones():
    """20 candidatos: los 15 mejores son sub-chunks de sólo 3 secciones."""
    candidatos, notas = [], {}
    for i in range(15):
        cid = f"p{i:02d}"
        candidatos.append(doc(cid, f"S{i % 3}"))
        notas[cid] = 1.0 - i * 0.01
    for i in range(5):
        cid = f"q{i}"
        candidatos.append(doc(cid, f"T{i}"))
        notas[cid] = 0.1 - i * 0.01
    return candidatos, notas


def test_el_inspector_ensena_lo_mismo_que_produccion():
    candidatos, notas = escenario_pocas_secciones()
    ce = CrossEncoderFijo(notas)

    produccion = DocumentCompressorPipeline(transformers=[
        CrossEncoderReranker(model=ce, top_n=RERANK_K * FACTOR_CANDIDATOS_RERANKER),
        DeduplicadorSecciones(),
    ]).compress_documents(candidatos, "q")

    r = analizar_recuperacion("q", hibrido_fijo(candidatos, [], []), ce, usar_reranker=True)

    assert ids(r["finalistas"]) == ids(produccion)


def test_con_pocas_secciones_el_contexto_lleva_menos_de_rerank_k():
    candidatos, notas = escenario_pocas_secciones()
    r = analizar_recuperacion("q", hibrido_fijo(candidatos, [], []), CrossEncoderFijo(notas),
                              usar_reranker=True)
    assert len(r["finalistas"]) == 3


# ── Sin reranker (USAR_RERANKER=0) ────────────────────────────────────────────
def test_sin_reranker_el_contexto_es_el_del_hibrido_deduplicado():
    # Es lo que manda `build_retriever(usar_reranker=False)`: c1, c3, c4, c5, c6
    # en el orden de RRF. Antes el inspector marcaba igualmente los del
    # reordenado, un contexto que el generador no recibía.
    r = analizar_basico(usar_reranker=False)
    assert ids(r["finalistas"]) == ids(DeduplicadorSecciones().compress_documents(CANDIDATOS, "q"))
    assert ids(r["finalistas"]) == ["c1", "c3", "c4", "c5", "c6"][:RERANK_K]
    assert r["resumen"]["usar_reranker"] is False


def test_sin_reranker_cada_candidato_se_clasifica_contra_ese_contexto():
    estado = {f["chunk_id"]: f["estado"] for f in analizar_basico(usar_reranker=False)["etapa23"]}
    assert estado["c1"] == "contexto"    # el cross-encoder lo hunde, pero sin él entra
    assert estado["c8"] == "duplicado"   # S2 ya entra con c3
    assert estado["c7"] == "no_cabe"


def test_el_efecto_del_reranker_se_mide_igual_este_o_no_activo():
    # `conserva` compara siempre los dos caminos: con el reranker apagado dice
    # qué cambiaría al encenderlo.
    con, sin = analizar_basico(True)["resumen"], analizar_basico(False)["resumen"]
    assert (con["conserva"], con["cambia"]) == (sin["conserva"], sin["cambia"])
