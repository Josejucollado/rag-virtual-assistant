"""
comun.py — Cimientos compartidos por las cuatro fases de la evaluación.

Aquí vive todo lo que no es ni generar respuestas ni puntuarlas: rutas de
entrada y salida, la fábrica del LLM juez, la clasificación de resultados, los
reintentos y las utilidades de CSV con columnas JSON.

Regla de oro del módulo: la evaluación NO reimplementa nada del RAG. Todo lo que
tenga que ver con recuperar, formatear contexto o detectar un rechazo se importa
del paquete `rag`, que es el mismo código que ejecutan `cli/chat.py` y la web. Si la
evaluación tuviera su propia copia, mediría un sistema que no es el que usa el
usuario.
"""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Sequence

# Importar `rag` deja el entorno listo (carga el .env, silencia avisos) además
# de dar acceso a la configuración del sistema que se está midiendo.
from rag import (
    BM25_STEMMING,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    ESFUERZO_RAZONAMIENTO_RAG,
    ESTILO_RESPUESTA,
    MODEL_JUDGE,
    MODEL_RAG,
    PROVEEDOR_RAG,
    RERANK_K,
    RERANKER_MODEL,
    RETRIEVER_K,
    RPM_JUEZ,
    USAR_RERANKER,
    ErrorConfiguracion,
)

# ── Rutas ─────────────────────────────────────────────────────────────────────
EVAL_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EVAL_DIR.parent

# EVAL_BANCO permite lanzar la fase 1 contra el banco fuera de corpus
# (`data/BancoPreguntas_FueraCorpus.csv`), donde un rechazo es un ACIERTO. Va en
# un fichero aparte para no mezclarlo con la regla «rechazo = fallo» del banco
# principal, que es la que asumen `puntuar` y `comparar`.
BANCO_CSV      = PROJECT_DIR / os.environ.get("EVAL_BANCO", "data/BancoPreguntas_GroundTruth.csv")
PROMPTS_ES_DIR = EVAL_DIR / "prompts_es"

# Cada configuración escribe en su propio directorio. Sin esto, evaluar con otro
# proveedor de embeddings sobrescribiría el CSV de la corrida anterior, que es
# justo el fichero con el que hay que compararla.
#
# El defecto es el proveedor activo, así que no hay nada que recordar: cambiar
# EMBEDDING_PROVIDER cambia también dónde se escribe. EVAL_CORRIDA existe para
# poder nombrar una corrida que varíe otra cosa (una ablación del reranker, por
# ejemplo) sin tocar el proveedor.
EVAL_CORRIDA = os.environ.get("EVAL_CORRIDA", EMBEDDING_PROVIDER).strip().lower()

RAGAS_DIR      = PROJECT_DIR / "data" / "ragas"
SALIDA_DIR     = RAGAS_DIR / EVAL_CORRIDA
RESPUESTAS_CSV = SALIDA_DIR / "respuestas_rag.csv"
RESULTADOS_CSV = SALIDA_DIR / "resultados_ragas.csv"
INFORME_HTML   = SALIDA_DIR / "informe_ragas.html"

# Con qué se generó cada corrida (modelos, reranker, stemming…). Blablador sólo
# garantiza sus alias por un tiempo, así que es la constancia de qué modelo
# respondió de verdad, y lo que `comparar` enseña en la portada.
NOMBRE_CONFIGURACION = "configuracion.txt"
CONFIGURACION_TXT    = SALIDA_DIR / NOMBRE_CONFIGURACION

# Con qué juez se puntuó (fase 2). Es el gemelo de `configuracion.txt`, que sólo
# dice con qué se GENERÓ: sin él, el invariante 6 (el instrumento de medida no se
# mueve) se cumplía por convención y nada impedía reanudar una puntuación a
# medias con otro juez.
NOMBRE_PUNTUACION = "puntuacion.txt"
PUNTUACION_TXT    = SALIDA_DIR / NOMBRE_PUNTUACION

# Tokens y coste de cada respuesta de la fase 1. Fichero aparte, y no columnas
# nuevas de `respuestas_rag.csv`, para no cambiar el esquema de las corridas ya
# hechas: `append_filas` escribe con la cabecera de la versión que lo abrió.
NOMBRE_CONSUMO = "consumo.csv"
CONSUMO_CSV    = SALIDA_DIR / NOMBRE_CONSUMO

# Gasto máximo de una corrida de pago, en dólares. Al superarlo la fase 1 se
# para limpia, y se reanuda con el mismo comando. 2 $ porque el crédito total es
# de 5 $ y la corrida completa (94 + 15 preguntas) se estima en 0,8-1,4 $: el
# tope sólo salta si algo va mucho peor de lo previsto, y aun entonces deja
# crédito para otra corrida.
PRESUPUESTO_USD = float(os.environ.get("PRESUPUESTO_USD", "2.0"))

# La comparativa no pertenece a ninguna corrida: vive por encima de todas.
COMPARATIVA_HTML  = RAGAS_DIR / "comparativa.html"
NOMBRE_RESULTADOS = "resultados_ragas.csv"   # una sola definición del nombre


def ruta_corrida(corrida: str) -> Path:
    """El directorio de salida de una corrida cualquiera, no sólo de la activa."""
    return RAGAS_DIR / corrida.strip().lower()


def leer_configuracion(directorio: Path, nombre: str = NOMBRE_CONFIGURACION) -> str | None:
    """Lo que dejó escrito una corrida (`configuracion.txt` o `puntuacion.txt`).

    Las fases 2 y 3 describen la corrida con esto y no con `resumen_config()`:
    el entorno de quien las lanza no tiene por qué ser el que la generó. Sin
    exportar USAR_RERANKER=0, el informe de `libre_sin_reranker` decía
    «reranker=sí».
    """
    ruta = Path(directorio) / nombre
    if not ruta.exists():
        return None
    return ruta.read_text(encoding="utf-8").strip() or None


def campos_configuracion(texto: str | None) -> dict[str, str]:
    """La línea de `configuracion.txt` como {campo: valor}.

    El formato es el de `resumen_config()`: "modelo RAG=… · reranker=… · …".
    Los tramos sin "=" (texto libre) se ignoran.
    """
    campos = {}
    for tramo in (texto or "").split(" · "):
        if "=" in tramo:
            clave, valor = tramo.split("=", 1)
            campos[clave.strip()] = valor.strip()
    return campos


# ── Categorías del banco de preguntas ─────────────────────────────────────────
# Viven aquí, y no en `metricas.py`, a propósito: `metricas` importa `ragas`, que
# tarda varios segundos en cargar, y quien sólo necesita estos nombres (los
# informes, los tests) no tiene por qué pagar ese coste.
ORDEN_CAT = ["PREGUNTAS DIRECTAS", "SÍNTESIS / MULTIHOP", "INFERENCIA / CASOS DE BORDE"]
CAT_CORTA = {
    "PREGUNTAS DIRECTAS": "Directas",
    "SÍNTESIS / MULTIHOP": "Síntesis / Multihop",
    "INFERENCIA / CASOS DE BORDE": "Inferencia / Borde",
}


def categorias_presentes(vistas: Sequence[str]) -> list[str]:
    """Las categorías observadas, en el orden canónico y con las nuevas al final."""
    return ([c for c in ORDEN_CAT if c in vistas]
            + [c for c in vistas if c not in ORDEN_CAT])


# ── Clasificación del resultado de cada fila ──────────────────────────────────
# Las preguntas del banco son todas *in-corpus*: la información está en los
# documentos. Por eso un rechazo NUNCA es una respuesta válida aquí, es un fallo
# del sistema, y hay que poder distinguirlo de una respuesta de contenido con
# total fiabilidad.
OK      = "OK"        # el RAG produjo una respuesta de contenido
RECHAZO = "RECHAZO"   # dijo que no tenía información -> respuesta fallida
ERROR   = "ERROR"     # excepción de la API tras agotar reintentos


def clasificar(respuesta: str | None, error: str | None = None) -> str:
    """Etiqueta una fila como OK / RECHAZO / ERROR.

    Se apoya en `es_rechazo()` del paquete `rag` en lugar de comparar con `==`
    contra el texto de rechazo: esa función normaliza tildes, mayúsculas y el
    punto final, así que no da falsos negativos cuando el modelo cambia un
    acento o la puntuación. Y al ser la misma función que usa `cli/chat.py`, la
    evaluación clasifica igual que el chat.
    """
    from rag import es_rechazo

    if error:
        return ERROR
    if not respuesta or not respuesta.strip():
        return ERROR
    return RECHAZO if es_rechazo(respuesta) else OK


# ── Modelo juez ───────────────────────────────────────────────────────────────
def build_juez():
    """El LLM que puntúa, frenado a `RPM_JUEZ` peticiones por minuto.

    Tiene que ser el mismo modelo en todas las corridas que se comparen: si el
    juez cambiara, una diferencia entre dos corridas podría venir de la regla
    con la que se mide y no del sistema medido.
    """
    from langchain_core.rate_limiters import InMemoryRateLimiter

    from rag import construir_llm_juez

    return construir_llm_juez(
        rate_limiter=InMemoryRateLimiter(requests_per_second=RPM_JUEZ / 60),
    )


def build_embeddings_juez():
    """Los embeddings con los que RAGAS puntúa: los mismos Qwen3 del índice.

    Dos de las siete métricas los usan: `semantic_similarity` (coseno respuesta
    ↔ referencia) y `answer_relevancy` (coseno entre la pregunta y las que el
    juez regenera a partir de la respuesta).
    """
    from rag import construir_embeddings

    return construir_embeddings()


def huella_plantillas(directorio: Path = PROMPTS_ES_DIR) -> str:
    """Un resumen corto (SHA-256, 12 caracteres) de las plantillas del juez.

    Las plantillas en español son parte del instrumento de medida tanto como el
    modelo: si alguien las retocara, dos corridas puntuadas antes y después no
    serían comparables aunque el juez fuera el mismo. El orden de los ficheros
    es fijo y el contenido se lee en binario, así que el resultado no depende
    del sistema operativo.
    """
    import hashlib

    h = hashlib.sha256()
    for ruta in sorted(Path(directorio).glob("*.json")):
        h.update(ruta.name.encode("utf-8"))
        h.update(ruta.read_bytes())
    return h.hexdigest()[:12]


def resumen_juez(ingles: bool = False) -> str:
    """Con qué se puntúa: juez, su configuración y las plantillas."""
    plantillas = "inglés (originales de RAGAS)" if ingles else f"español ({huella_plantillas()})"
    return (
        f"juez={MODEL_JUDGE} · razonamiento=no · RPM={RPM_JUEZ} · "
        f"embeddings={EMBEDDING_PROVIDER}/{EMBEDDING_MODEL} ({EMBEDDING_DIMS}d) · "
        f"plantillas={plantillas}"
    )


# ── Consumo de tokens y coste ─────────────────────────────────────────────────
def consumo_de(uso: dict, modelo: str) -> dict:
    """Tokens y coste de una respuesta, a partir de lo que cuenta LangChain.

    `uso` es el diccionario de `get_usage_metadata_callback().usage_metadata`:
    {modelo: {input_tokens, output_tokens, input_token_details,
    output_token_details}}. Se suman todas las llamadas de todos los modelos
    (normalmente una), y el coste se calcula con el precio de `modelo`.
    """
    from rag import coste_usd

    entrada = salida = razonamiento = cache = 0
    for datos in (uso or {}).values():
        entrada += int(datos.get("input_tokens") or 0)
        salida += int(datos.get("output_tokens") or 0)
        razonamiento += int((datos.get("output_token_details") or {}).get("reasoning") or 0)
        cache += int((datos.get("input_token_details") or {}).get("cache_read") or 0)
    return {
        "tokens_entrada": entrada,
        "tokens_entrada_cache": cache,
        "tokens_salida": salida,
        "tokens_razonamiento": razonamiento,
        "coste_usd": round(coste_usd(modelo, entrada, salida, cache), 6),
    }


CAMPOS_CONSUMO = ["ID", "tokens_entrada", "tokens_entrada_cache", "tokens_salida",
                  "tokens_razonamiento", "coste_usd"]


def gasto_acumulado(path: Path) -> float:
    """Lo ya gastado en una corrida, sumando `consumo.csv`. 0 si no existe."""
    if not path.exists() or path.stat().st_size == 0:
        return 0.0
    with path.open(newline="", encoding="utf-8") as fh:
        return sum(float(f.get("coste_usd") or 0) for f in csv.DictReader(fh))


# ── Reintentos ────────────────────────────────────────────────────────────────
# Códigos que merecen reintento: cuota agotada o caída puntual del servicio. Un
# 400 o un 404 son errores nuestros y reintentarlos solo hace perder tiempo.
TRANSITORIOS = (
    "429", "RESOURCE_EXHAUSTED", "quota",
    "500", "502", "503", "504",
    "UNAVAILABLE", "DEADLINE_EXCEEDED", "timeout",
)


def es_transitorio(exc: BaseException) -> bool:
    texto = f"{type(exc).__name__}: {exc}"
    return any(marca.lower() in texto.lower() for marca in TRANSITORIOS)


def con_reintentos(fn: Callable[[], Any], *, intentos: int = 5,
                   espera_inicial: float = 4.0, etiqueta: str = "") -> Any:
    """Ejecuta `fn` reintentando los fallos transitorios con backoff exponencial.

    Devuelve el resultado, o relanza la última excepción si se agotan los
    intentos o el fallo no es transitorio.
    """
    espera = espera_inicial
    for intento in range(1, intentos + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - se reclasifica justo debajo
            if not es_transitorio(exc) or intento == intentos:
                raise
            print(f"   ! {etiqueta} fallo transitorio ({exc.__class__.__name__}), "
                  f"reintento {intento}/{intentos - 1} en {espera:.0f}s")
            time.sleep(espera)
            espera *= 2
    raise RuntimeError("inalcanzable")


# ── CSV con columnas JSON ─────────────────────────────────────────────────────
# Los contextos recuperados son texto largo con saltos de línea, comas y
# comillas. Guardarlos en crudo rompería el CSV al releerlo, así que las listas
# viajan serializadas como JSON en una sola celda.
def dump_json(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False)


def load_json(celda: str | float | None, por_defecto: Any = None) -> Any:
    if celda is None or celda == "" or celda != celda:  # NaN != NaN
        return [] if por_defecto is None else por_defecto
    if isinstance(celda, (list, dict)):
        return celda
    try:
        return json.loads(celda)
    except (json.JSONDecodeError, TypeError):
        return [] if por_defecto is None else por_defecto


def ref_fragmentos(fuentes) -> str:
    """Los fragmentos recuperados como referencia corta, no como texto completo.

    El entregable es una tabla que se abre en Excel y se lee a mano: meter ahí
    los 5 fragmentos íntegros son ~9.500 caracteres por fila que hacen la hoja
    inservible. El `chunk_id` ya identifica el fragmento de forma única y lleva
    dentro el fichero de origen, así que basta para ir a buscarlo en
    `respuestas_rag.csv` (que sí guarda el texto) o con `cli/inspeccionar.py`.
    """
    lista = load_json(fuentes, [])
    ids = [f.get("chunk_id") or f.get("source") or "?"
           for f in lista if isinstance(f, dict)]
    return " | ".join(ids)


def append_filas(path: Path, filas: Sequence[dict], campos: Sequence[str]) -> None:
    """Añade filas al CSV, escribiendo la cabecera solo si el fichero es nuevo.

    Se escribe incrementalmente a propósito: con 94 preguntas contra un servicio
    gratuito y con límite de peticiones, un 429 a mitad de corrida no puede
    tirar por la borda todo lo ya calculado.
    """
    if not filas:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(campos), extrasaction="ignore")
        if nuevo:
            writer.writeheader()
        for fila in filas:
            writer.writerow(fila)


def ids_existentes(path: Path, columna: str = "ID") -> set[str]:
    """IDs ya presentes en un CSV de salida, para poder reanudar sin repetir."""
    if not path.exists() or path.stat().st_size == 0:
        return set()
    with path.open(newline="", encoding="utf-8") as fh:
        return {fila[columna] for fila in csv.DictReader(fh) if fila.get(columna)}


def leer_banco() -> list[dict]:
    """El banco de preguntas, con las columnas ya renombradas a las de RAGAS."""
    if not BANCO_CSV.exists():
        raise ErrorConfiguracion(f"No encuentro el banco de preguntas en {BANCO_CSV}")

    filas: list[dict] = []
    # utf-8-sig porque el CSV viene de Excel y trae BOM: sin esto, la primera
    # columna se llamaría "﻿ID" y `leer_banco` devolvería todo vacío.
    with BANCO_CSV.open(newline="", encoding="utf-8-sig") as fh:
        for fila in csv.DictReader(fh):
            filas.append({
                "ID":         (fila.get("ID") or "").strip(),
                "Categoria":  (fila.get("Categoría") or fila.get("Categoria") or "").strip(),
                "user_input": (fila.get("Pregunta") or "").strip(),
                "reference":  (fila.get("Respuesta Correcta (Ground Truth)") or "").strip(),
            })
    return [f for f in filas if f["ID"] and f["user_input"]]


def etiqueta_generador(proveedor: str = PROVEEDOR_RAG, modelo: str = MODEL_RAG,
                       esfuerzo: str = ESFUERZO_RAZONAMIENTO_RAG) -> str:
    """El valor del campo `modelo RAG` de `configuracion.txt`.

    Con Blablador es el identificador tal cual, byte a byte como en todas las
    corridas `libre_*` ya hechas: si cambiara, `auditar_configuraciones` vería
    distinto el campo en corridas que usaron el mismo generador. Con OpenAI lleva
    el proveedor y el esfuerzo de razonamiento, que también es parte del sistema
    medido.
    """
    if proveedor == "blablador":
        return modelo
    from rag import es_razonador_openai

    extra = f" (razonamiento={esfuerzo})" if es_razonador_openai(modelo) else ""
    return f"{proveedor}/{modelo}{extra}"


def resumen_config() -> str:
    """Configuración efectiva del RAG, para dejar constancia en cada corrida."""
    # El proveedor va en tercer lugar, y la posición importa: `informe.py` hace
    # `resumen_config().split(' · ', 2)[2]` para quedarse con todo menos los dos
    # primeros campos. En tercera posición el dato entra en la cabecera del
    # informe, que es lo que se quiere; en primera o segunda la rompería sin que
    # ningún test lo pillara.
    return (
        f"modelo RAG={etiqueta_generador()} · juez={MODEL_JUDGE} · "
        f"embeddings={EMBEDDING_PROVIDER}/{EMBEDDING_MODEL} ({EMBEDDING_DIMS}d) · "
        f"reranker={'sí' if USAR_RERANKER else 'no'} ({RERANKER_MODEL.split('/')[-1]}) · "
        f"RETRIEVER_K={RETRIEVER_K} · RERANK_K={RERANK_K} · "
        f"stemming BM25={'sí' if BM25_STEMMING else 'no'} · "
        f"estilo={ESTILO_RESPUESTA}"
    )
