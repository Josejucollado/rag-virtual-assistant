"""
rag — El núcleo del sistema RAG sobre la documentación de Sistemas Operativos.

Este paquete es la única implementación del RAG. Las órdenes de consola
(`cli/`), la evaluación (`eval_ragas/`) y la web (`web/`) lo importan; ninguna
reimplementa nada. Así, lo que se ve en el navegador es exactamente lo que se
mide en la evaluación.

    from rag import build_retriever, build_generador, es_rechazo, RERANK_K

Los módulos siguen el orden del pipeline y dependen en ese mismo sentido:

    config        constantes, rutas y fábricas de modelos; no depende de nadie
    recuperacion  BM25 + denso -> cross-encoder -> deduplicado
    generacion    prompt, respuesta citada y reescritura de seguimiento
"""

from .config import (
    BATCH_SIZE,
    BM25_STEMMING,
    CARACTERES_POR_TOKEN,
    CHROMA_ACTIVO,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CLAVE_META_CHUNKS,
    CLAVE_META_DIMS,
    CLAVE_META_MODELO,
    COLLECTION,
    DATA_DIR,
    DEMO_MAX_CARACTERES_PREGUNTA,
    DEMO_PREGUNTAS_POR_MINUTO,
    DEMO_PREGUNTAS_POR_MINUTO_IP,
    DEMO_PUBLICA,
    DISTANCIA,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    ESFUERZO_RAZONAMIENTO_RAG,
    ESTILO_RESPUESTA,
    ESTILOS_RESPUESTA,
    HASHES_JSON,
    MAX_TOKENS_SALIDA_RAG,
    MD_DIR,
    MIN_CHUNK,
    MODEL_JUDGE,
    MODEL_RAG,
    PDF_DIR,
    PESOS_HIBRIDO,
    PROJECT_DIR,
    PROVEEDOR_RAG,
    PROVEEDORES_EMBEDDINGS,
    PROVEEDORES_LLM,
    REFUSAL_TEXT,
    RERANK_K,
    RERANKER_MODEL,
    RETRIEVER_K,
    RPM_JUEZ,
    TEMPERATURA,
    USAR_RERANKER,
    ErrorConfiguracion,
    comprobar_identidad,
    construir_embeddings,
    construir_llm,
    construir_llm_juez,
    consulta_con_instruccion,
    coste_usd,
    es_razonador_openai,
    opciones_generador,
    precio_modelo,
    resolver_modelo_rag,
    resolver_proveedor,
    sin_tildes,
)

# En el orden del pipeline: `generacion` depende de `recuperacion`.
from .recuperacion import (
    DeduplicadorSecciones,
    analizar_recuperacion,
    build_compresor,
    build_hibrido,
    build_retriever,
    build_vectordb,
    chunk_id,
    construir_cross_encoder,
    cuerpo_sin_encabezados,
    describir_fuente,
    recortar,
    tokenizar_es,
)
from .generacion import (
    MAX_CHARS_RESPUESTA_HISTORIAL,
    RAG_TEMPLATE,
    build_generador,
    build_reescritor,
    consulta_de_busqueda,
    entrada_generador,
    es_rechazo,
    extraer_citas,
    formatear_contexto,
    formatear_historial,
    plantilla_rag,
    quitar_citas,
)

__all__ = [
    # Rutas y constantes
    "PROJECT_DIR", "DATA_DIR", "PDF_DIR", "MD_DIR", "HASHES_JSON", "CHROMA_ACTIVO",
    "COLLECTION", "DISTANCIA", "EMBEDDING_MODEL", "EMBEDDING_DIMS", "BATCH_SIZE",
    "CHUNK_SIZE", "CHUNK_OVERLAP", "MIN_CHUNK", "CARACTERES_POR_TOKEN",
    "MODEL_RAG", "MODEL_JUDGE", "RPM_JUEZ", "RERANKER_MODEL", "TEMPERATURA",
    "RETRIEVER_K", "RERANK_K", "USAR_RERANKER", "BM25_STEMMING", "PESOS_HIBRIDO",
    "ESTILO_RESPUESTA", "ESTILOS_RESPUESTA", "REFUSAL_TEXT",
    "ErrorConfiguracion", "sin_tildes",
    # Demo pública de la web
    "DEMO_PUBLICA", "DEMO_PREGUNTAS_POR_MINUTO", "DEMO_PREGUNTAS_POR_MINUTO_IP",
    "DEMO_MAX_CARACTERES_PREGUNTA",
    # Proveedor del generador (Blablador gratuito u OpenAI de pago) y del juez
    "PROVEEDOR_RAG", "PROVEEDORES_LLM", "resolver_modelo_rag",
    "ESFUERZO_RAZONAMIENTO_RAG", "MAX_TOKENS_SALIDA_RAG",
    "precio_modelo", "coste_usd", "es_razonador_openai", "opciones_generador",
    "construir_llm", "construir_llm_juez",
    # Proveedores de embeddings y sello de la colección
    "EMBEDDING_PROVIDER", "PROVEEDORES_EMBEDDINGS", "resolver_proveedor",
    "construir_embeddings", "consulta_con_instruccion", "comprobar_identidad",
    "CLAVE_META_MODELO", "CLAVE_META_DIMS", "CLAVE_META_CHUNKS",
    # Recuperación
    "tokenizar_es", "DeduplicadorSecciones", "build_vectordb", "build_hibrido",
    "build_compresor", "build_retriever", "analizar_recuperacion",
    "construir_cross_encoder", "describir_fuente", "chunk_id",
    "cuerpo_sin_encabezados", "recortar",
    # Generación
    "RAG_TEMPLATE", "plantilla_rag", "build_generador", "build_reescritor",
    "consulta_de_busqueda", "entrada_generador", "formatear_contexto",
    "formatear_historial", "extraer_citas", "es_rechazo", "quitar_citas",
    "MAX_CHARS_RESPUESTA_HISTORIAL",
]
