"""
recuperacion.py — De la pregunta a los fragmentos que verá el modelo.

La recuperación tiene cuatro pasos:

    1. Híbrido: BM25 (léxico) + denso (semántico), fusionados con RRF, k=20.
    2. Reordenado por un cross-encoder, que sí mira pregunta y documento juntos.
    3. Deduplicado de sub-chunks de una misma sección.
    4. Los RERANK_K mejores van al contexto.

Las etapas se construyen por separado (`build_hibrido`, `build_compresor`) para
poder observarlas una a una. `analizar_recuperacion()` hace justamente eso y es
lo que alimenta al inspector de la terminal (`cli/inspeccionar.py`): reutiliza las
mismas piezas que producción, en vez de tener su propia copia de la lógica que
podría divergir sin que nadie lo notara.
"""

from __future__ import annotations

import re
import warnings
from typing import Any

from chromadb.errors import NotFoundError
from langchain_chroma import Chroma
from langchain_classic.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain_classic.retrievers.document_compressors import (
    CrossEncoderReranker,
    DocumentCompressorPipeline,
)
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor

import snowballstemmer

from .config import (
    BM25_STEMMING,
    CHROMA_ACTIVO,
    CLAVE_META_CHUNKS,
    CLAVE_META_DIMS,
    CLAVE_META_MODELO,
    COLLECTION,
    EMBEDDING_PROVIDER,
    FACTOR_CANDIDATOS_RERANKER,
    PESOS_HIBRIDO,
    RERANK_K,
    RERANKER_MODEL,
    RETRIEVER_K,
    USAR_RERANKER,
    ErrorConfiguracion,
    comprobar_identidad,
    construir_embeddings,
    sin_tildes,
)

# ── Tokenización para BM25 ────────────────────────────────────────────────────
# BM25 tokeniza por espacios y no filtra nada. Con preguntas en castellano
# ("¿qué es...?", "¿para qué sirve...?", "¿cómo se hace...?") eso significa que
# las palabras vacías puntúan igual que los términos técnicos, y BM25 acaba
# devolviendo documentos que no comparten con la pregunta más que los "de" y los
# "que". Medido sobre este corpus: sin filtrar, el híbrido pasaba de 3 a 9
# ficheros distintos en el top-k sin aportar ni un acierto nuevo.
_STOPWORDS_ES = {
    "a", "al", "algo", "alguna", "algunas", "alguno", "algunos", "ante", "antes",
    "como", "con", "contra", "cual", "cuales", "cuando", "de", "del",
    "desde", "donde", "dos", "el", "ella", "ellas", "ello", "ellos", "en", "entre",
    "era", "es", "esa", "esas", "ese", "eso", "esos", "esta", "estan", "estas",
    "este", "esto", "estos", "ha", "hace", "hacer", "hacia", "han", "hay", "la",
    "las", "le", "les", "lo", "los", "mas", "me", "mi", "mucho", "muy", "no",
    "nos", "o", "para", "pero", "poco", "por", "porque", "que", "quien", "se",
    "sea", "ser", "si", "sin", "sobre", "son", "su", "sus", "tambien", "tan",
    "tanto", "te", "tiene", "tienen", "todo", "todos", "tu", "un", "una", "uno",
    "unos", "y", "ya",
    # Verbos y muletillas que aparecen en casi toda pregunta de examen.
    "define", "definir", "diferencia", "diferencias", "explica",
    "explicar", "indica", "indique", "sirve", "sirven",
}
# OJO al ampliar esta lista: "cuanto" estuvo aquí como interrogativo y rompía las
# preguntas sobre Round Robin, porque en este corpus *el cuanto* es el quantum de
# planificación. Antes de añadir una palabra, comprobar con
# `python -m cli.inspeccionar "<consulta>"` que no es término técnico del temario.

_TOKEN = re.compile(r"\w+", re.UNICODE)
_STEMMER = snowballstemmer.stemmer("spanish")


def tokenizar_es(texto: str, stemming: bool | None = None) -> list[str]:
    """Tokenizador para BM25: minúsculas, sin tildes y sin palabras vacías.

    Con `stemming` (por defecto, `BM25_STEMMING`) reduce además cada palabra a
    su raíz. Las vacías se filtran antes, sobre la palabra entera.
    """
    tokens = [t for t in _TOKEN.findall(sin_tildes(texto)) if t not in _STOPWORDS_ES]
    if BM25_STEMMING if stemming is None else stemming:
        return _STEMMER.stemWords(tokens)
    return tokens


# ── Presentación de fragmentos ────────────────────────────────────────────────
def describir_fuente(doc: Document) -> str:
    """'fichero.md › sección', o sólo el fichero si no hay sección."""
    fuente = doc.metadata.get("source", "desconocido")
    seccion = doc.metadata.get("h2")
    return f"{fuente} › {seccion}" if seccion else fuente


def chunk_id(doc: Document) -> str:
    """El identificador estable del fragmento, o '?' si no lo lleva."""
    return (doc.metadata or {}).get("chunk_id", "?")


def clave_seccion(doc: Document) -> tuple[str | None, str | None]:
    """(fichero, sección): lo que tienen en común los sub-chunks de una sección."""
    meta = doc.metadata or {}
    return meta.get("source"), meta.get("h2")


def cuerpo_sin_encabezados(texto: str) -> str:
    """El chunk sin la ruta de encabezados que le antepone el troceado.

    Para las vistas previas: si no se quitan, todas las filas empiezan igual
    ("# 05 Memoria...") y no se distingue un chunk de otro.
    """
    lineas = texto.split("\n")
    i = 0
    while i < len(lineas) and (lineas[i].startswith("#") or not lineas[i].strip()):
        i += 1
    return "\n".join(lineas[i:])


def recortar(texto: str, n: int) -> str:
    """Una sola línea de como mucho `n` caracteres, con puntos suspensivos."""
    limpio = " ".join(texto.split())
    return limpio[:n] + ("…" if len(limpio) > n else "")


# ── Etapa 3: deduplicado ──────────────────────────────────────────────────────
class DeduplicadorSecciones(BaseDocumentCompressor):
    """
    Deja un solo fragmento por sección y recorta a `limite`.

    Una sección larga se troceó en varios sub-chunks contiguos y solapados, así
    que suelen puntuar parecido y colarse juntos en el top-k. Sin esto, dos o
    tres de los huecos del contexto se van en decir lo mismo, y las citas salen
    repetidas. Como llega ya reordenado, quedarse con el primero de cada sección
    es quedarse con el mejor.

    El recorte final va aquí y no en el reranker: al reranker se le pide de más
    justamente para que después de deduplicar sigan quedando `limite`.
    """

    limite: int = RERANK_K

    def compress_documents(self, documents, query, callbacks=None):
        vistos = set()
        unicos = []
        for d in documents:
            clave = clave_seccion(d)
            if clave in vistos:
                continue
            vistos.add(clave)
            unicos.append(d)
            if len(unicos) >= self.limite:
                break
        return unicos


# ── Construcción de las etapas ────────────────────────────────────────────────
def _todos_los_docs(vectordb: Chroma) -> list[Document]:
    raw = vectordb.get(include=["documents", "metadatas"])
    metadatas = raw.get("metadatas") or [{}] * len(raw["documents"])
    return [Document(page_content=c, metadata=m or {})
            for c, m in zip(raw["documents"], metadatas)]


def _identidad_coleccion(vectordb: Chroma) -> dict:
    """Lo que la colección tiene grabado: cuántos vectores, de qué dimensión,
    con qué distancia y —si es posterior al sello— con qué modelo se indexó.

    Todo sale de campos que Chroma ya tiene materializados en memoria: no toca
    el índice HNSW ni lee un solo vector, así que cuesta microsegundos frente a
    los segundos que ya pagan el BM25 y el cross-encoder de la línea siguiente.
    """
    meta = vectordb._collection.metadata or {}
    return {
        "n_vectores": vectordb._collection.count(),
        # `dimension` es None mientras la colección esté vacía: Chroma la fija
        # con el primer `add`.
        "dims_reales": vectordb._collection.get_model().dimension,
        "espacio": meta.get("hnsw:space"),
        "modelo_sellado": meta.get(CLAVE_META_MODELO),
        "dims_selladas": meta.get(CLAVE_META_DIMS),
        "chunks_sellados": meta.get(CLAVE_META_CHUNKS),
    }


def build_vectordb(embeddings=None, *, verificar: bool = True) -> Chroma:
    """La colección de Chroma ya indexada, contrastada con la configuración activa.

    `verificar=False` sólo tiene sentido en los tests y cuando se inyectan unos
    embeddings de otro proveedor: la comprobación mira las constantes globales,
    que en ese caso no describen el objeto inyectado.

    No crea la colección si no existe, a propósito: bastaría lanzar el chat antes
    de indexar para dejar una colección vacía con la distancia por defecto de
    Chroma, y a partir de ahí `process_md` sin `--reset` indexaría dentro de ella
    —Chroma ignora `collection_metadata` en una colección que ya existe—, así que
    se acabaría midiendo con otra distancia sin que nada lo dijera.
    """
    try:
        vectordb = Chroma(
            collection_name=COLLECTION,
            persist_directory=str(CHROMA_ACTIVO),
            embedding_function=embeddings or construir_embeddings(),
            create_collection_if_not_exists=False,
        )
    except NotFoundError as exc:
        raise ErrorConfiguracion(
            f'No existe la colección "{COLLECTION}" en {CHROMA_ACTIVO}. '
            f"Indexa con: EMBEDDING_PROVIDER={EMBEDDING_PROVIDER} "
            f"python -m cli.process_md --reset"
        ) from exc

    if verificar:
        aviso = comprobar_identidad(coleccion=COLLECTION, **_identidad_coleccion(vectordb))
        if aviso:
            warnings.warn(aviso, stacklevel=2)

    return vectordb


def build_hibrido(vectordb: Chroma | None = None) -> EnsembleRetriever:
    """Etapa 1: BM25 (léxico) + denso (semántico), fusionados con RRF."""
    vectordb = vectordb if vectordb is not None else build_vectordb()

    dense = vectordb.as_retriever(search_kwargs={"k": RETRIEVER_K})
    bm25 = BM25Retriever.from_documents(
        _todos_los_docs(vectordb),
        preprocess_func=tokenizar_es,
    )
    bm25.k = RETRIEVER_K

    # El orden importa: `analizar_recuperacion` desempaqueta `retrievers` como
    # (bm25, denso) para poder enseñar qué mitad aportó cada candidato.
    return EnsembleRetriever(
        retrievers=[bm25, dense],
        weights=[PESOS_HIBRIDO["bm25"], PESOS_HIBRIDO["denso"]],
    )


def construir_cross_encoder() -> HuggingFaceCrossEncoder:
    """El cross-encoder de la etapa 2. Lo comparten producción y el inspector."""
    return HuggingFaceCrossEncoder(model_name=RERANKER_MODEL)


def build_compresor() -> DocumentCompressorPipeline:
    """Etapas 2 y 3: reordenar con el cross-encoder y deduplicar secciones."""
    return DocumentCompressorPipeline(transformers=[
        CrossEncoderReranker(
            model=construir_cross_encoder(),
            top_n=RERANK_K * FACTOR_CANDIDATOS_RERANKER,
        ),
        DeduplicadorSecciones(),
    ])


def build_retriever(embeddings=None, usar_reranker: bool | None = None, *,
                    vectordb: Chroma | None = None) -> ContextualCompressionRetriever:
    """Híbrido BM25 + denso, reordenado por cross-encoder y deduplicado.

    `vectordb` permite reutilizar una colección ya abierta (la web la tiene
    abierta para su catálogo); si no se pasa, se abre con `embeddings`.
    """
    if usar_reranker is None:
        usar_reranker = USAR_RERANKER
    if vectordb is None:
        vectordb = build_vectordb(embeddings)

    # Sin cross-encoder se conserva el mismo deduplicado y el mismo recorte a
    # RERANK_K, en el orden en que los fusionó RRF. Si se devolviera el híbrido
    # tal cual, el generador recibiría los 25-35 candidatos, y comparar con y sin
    # reranker cambiaría a la vez el orden y el tamaño del contexto.
    compresor = build_compresor() if usar_reranker else DeduplicadorSecciones()
    return ContextualCompressionRetriever(
        base_compressor=compresor,
        base_retriever=build_hibrido(vectordb),
    )


# ── Inspección: las tres etapas, como datos ───────────────────────────────────
def _ficha(doc: Document) -> dict:
    """Los campos con los que se identifica un fragmento en las tablas."""
    meta = doc.metadata or {}
    return {
        "chunk_id": chunk_id(doc),
        "descripcion": describir_fuente(doc),
        "source": meta.get("source"),
        "h2": meta.get("h2"),
    }


def _etapa_hibrido(candidatos: list[Document], ids_bm25: set, ids_denso: set) -> list[dict]:
    """Etapa 1: los candidatos en el orden de RRF y qué mitad aportó cada uno."""
    etapa1 = []
    for posicion, doc in enumerate(candidatos, start=1):
        cid = chunk_id(doc)
        if cid in ids_bm25 and cid in ids_denso:
            origen = "ambos"
        elif cid in ids_bm25:
            origen = "bm25"
        else:
            origen = "denso"
        etapa1.append({"posicion": posicion, "origen": origen, **_ficha(doc)})
    return etapa1


def _etapa_reordenado(candidatos: list[Document], puntuaciones, orden: list[int],
                      finalistas: list[Document], usar_reranker: bool) -> list[dict]:
    """Etapas 2 y 3: el orden del cross-encoder y por qué cada uno entró o no."""
    ids_finalistas = {chunk_id(d) for d in finalistas}
    # Secciones que ya tienen un representante entre los finalistas: sirve para
    # distinguir "lo tiró el deduplicador" de "simplemente no cabía".
    secciones_finalistas = {clave_seccion(d) for d in finalistas}
    # Posición del último que entró: a partir de ahí, lo que no es duplicado se
    # queda fuera sólo porque el contexto ya está lleno.
    ultimo = max(
        (n for n, i in enumerate(orden, start=1) if chunk_id(candidatos[i]) in ids_finalistas),
        default=0,
    )

    etapa23 = []
    for posicion, idx in enumerate(orden, start=1):
        doc = candidatos[idx]
        antes = idx + 1
        if chunk_id(doc) in ids_finalistas:
            estado = "contexto"
        elif clave_seccion(doc) in secciones_finalistas:
            estado = "duplicado"
        # Sin reranker el corte lo pone el orden de RRF, no esta tabla: lo que
        # no entró ni repite sección es que llegó después de llenarse.
        elif not usar_reranker or posicion > ultimo:
            estado = "no_cabe"
        else:
            estado = "peor"
        etapa23.append({
            "posicion": posicion,
            "antes": antes,
            "salto": antes - posicion,
            # Sin redondear: quien presenta decide los decimales. Redondear aquí
            # a 4 y volver a formatear a 3 en la terminal daba -0,419 donde el
            # valor real es -0,4195, es decir -0,420.
            "score": float(puntuaciones[idx]),
            "estado": estado,
            **_ficha(doc),
        })
    return etapa23


def analizar_recuperacion(consulta: str, hibrido: EnsembleRetriever,
                          cross_encoder: Any, usar_reranker: bool | None = None) -> dict:
    """
    Ejecuta la recuperación paso a paso y devuelve qué pasó en cada etapa.

    Devuelve datos planos (listas de diccionarios), no texto ni HTML, para que
    quien llama decida cómo presentarlos (`cli/inspeccionar.py` pinta tablas en
    la terminal) y para que los tests puedan comprobar, sin terminal, que enseña
    exactamente lo que hace producción.

    Claves de la salida:
      · `etapa1`   — candidatos del híbrido, en el orden en que los fusionó RRF,
                     con `origen` ∈ {bm25, denso, ambos}.
      · `etapa23`  — los mismos, ya reordenados por el cross-encoder, con su
                     `score`, cuánto se movieron (`salto`) y por qué acabaron
                     dentro o fuera: `estado` ∈ {contexto, duplicado, no_cabe,
                     peor}.
      · `finalistas` — los Document que van al contexto, los mismos que manda
                     `build_retriever`: con reranker, los del reordenado; sin él
                     (`USAR_RERANKER=0`), el híbrido deduplicado. El reordenado
                     se calcula igualmente: enseña qué haría el cross-encoder.
      · `resumen`  — cuánto aportó cada mitad del híbrido, cuánto cambia el
                     reranker y con cuál de los dos caminos se marcó el contexto.
    """
    if usar_reranker is None:
        usar_reranker = USAR_RERANKER

    bm25, denso = hibrido.retrievers
    ids_bm25 = {chunk_id(d) for d in bm25.invoke(consulta)}
    ids_denso = {chunk_id(d) for d in denso.invoke(consulta)}

    candidatos = hibrido.invoke(consulta)
    puntuaciones = cross_encoder.score([(consulta, d.page_content) for d in candidatos])
    orden = sorted(range(len(candidatos)), key=lambda i: -puntuaciones[i])
    reordenados = [candidatos[i] for i in orden]

    # El recorte a RERANK_K × FACTOR antes de deduplicar es el mismo que hace
    # `build_compresor` (CrossEncoderReranker con ese `top_n`). Sin él, cuando
    # entre los 15 primeros hay menos de 5 secciones distintas, el inspector
    # rellenaría el contexto con candidatos que producción ya ha descartado y
    # enseñaría 5 finalistas donde el generador recibe menos.
    con_reranker = DeduplicadorSecciones().compress_documents(
        reordenados[:RERANK_K * FACTOR_CANDIDATOS_RERANKER], consulta
    )
    # Lo que manda producción sin reranker (`build_retriever` con
    # `usar_reranker=False`): el híbrido deduplicado, en el orden de RRF.
    sin_reranker = DeduplicadorSecciones().compress_documents(candidatos, consulta)
    # Se marca el contexto del camino que está activo: con USAR_RERANKER=0 el
    # generador no recibe el reordenado, y enseñarlo como contexto mentiría.
    finalistas = con_reranker if usar_reranker else sin_reranker

    etapa1 = _etapa_hibrido(candidatos, ids_bm25, ids_denso)
    etapa23 = _etapa_reordenado(candidatos, puntuaciones, orden, finalistas, usar_reranker)

    # Lo que de verdad importa: ¿cambió el orden el reranker? La referencia es
    # lo que mandaría el sistema sin reranker (`build_retriever` con
    # `usar_reranker=False`): el híbrido ya deduplicado, no su top-5 en crudo,
    # que podía contar dos veces una misma sección. Compara siempre los dos
    # caminos, esté o no activo el reranker.
    antes_top = [chunk_id(d) for d in sin_reranker]
    despues_top = [chunk_id(d) for d in con_reranker]
    conserva = len(set(antes_top) & set(despues_top))

    return {
        "consulta": consulta,
        "tokens_bm25": tokenizar_es(consulta),
        "etapa1": etapa1,
        "etapa23": etapa23,
        "finalistas": finalistas,
        "resumen": {
            "n_candidatos": len(candidatos),
            "solo_bm25": len(ids_bm25 - ids_denso),
            "solo_denso": len(ids_denso - ids_bm25),
            "en_ambos": len(ids_bm25 & ids_denso),
            "rerank_k": RERANK_K,
            "retriever_k": RETRIEVER_K,
            "conserva": conserva,
            "cambia": RERANK_K - conserva,
            "cambia_el_primero": bool(
                antes_top and despues_top and antes_top[0] != despues_top[0]
            ),
            "usar_reranker": usar_reranker,
        },
    }
