"""
config.py — Toda la configuración del RAG en un único sitio.

Este módulo es la base de la que dependen los demás: no contiene lógica de
negocio, sólo constantes, rutas y la fábrica de embeddings. El orden de
dependencias del paquete es estricto y sigue al del propio pipeline:

    config  <-  recuperacion  <-  generacion

Por qué los parámetros de indexado viven aquí y no en `cli/process_md.py`: indexar
con un modelo de embeddings y consultar con otro **no da error**. Da un
recuperador que devuelve basura en silencio, y no hay forma de darse cuenta
mirando la salida. Teniendo `COLLECTION`, `EMBEDDING_MODEL` y
`construir_embeddings()` en un único módulo que importan tanto el script que
indexa como el que consulta, eso no puede pasar.

Esa definición única es la entrada de `PROVEEDORES_EMBEDDINGS`: el modelo, las
dimensiones, la colección y el directorio de Chroma viajan juntos, así que no se
pueden descasar. Y como aun así se puede consultar un índice construido antes,
la colección graba con qué modelo se indexó (`CLAVE_META_MODELO`) y
`comprobar_identidad()` lo contrasta al abrirla: el desajuste no es silencioso.

Todos los modelos remotos —embeddings, generador, reescritor y juez— los sirve
Blablador (Helmholtz, FZ Jülich), gratuito y compatible con OpenAI. Lo único
que corre en local es el cross-encoder del reranker.
"""

from __future__ import annotations

import os
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

# override=True para que el .env tenga prioridad sobre las variables ya
# presentes en el entorno: si no, una variable vieja de la sesión pisaría al
# fichero y costaría entender por qué.
load_dotenv(override=True)
# En Windows sin modo desarrollador, Hugging Face avisa en cada descarga de que
# su caché no puede usar enlaces simbólicos. Funciona igual (copia en vez de
# enlazar), y el aviso sólo ensucia la salida de cada orden.
warnings.filterwarnings("ignore", message=".*symlinks.*")
os.environ.setdefault("LANGSMITH_TRACING", "false")


# ── Rutas ─────────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR    = PROJECT_DIR / "data"
PDF_DIR     = DATA_DIR / "documentacion_pdf"
MD_DIR      = DATA_DIR / "documentacion_md"
HASHES_JSON = DATA_DIR / "pdf_hashes.json"
# El índice no se versiona: rehacerlo es gratis (`python -m cli.process_md
# --reset`) y tarda unos minutos.
CHROMA_DIR_BLABLADOR = PROJECT_DIR / "chroma_db_blablador"


# ── Errores ───────────────────────────────────────────────────────────────────
class ErrorConfiguracion(RuntimeError):
    """Falta algo imprescindible para arrancar (una clave, un directorio...).

    Es una excepción normal, y no `SystemExit`, a propósito: `SystemExit` hereda
    de `BaseException`, así que un `except Exception` no la captura. Cuando la
    lanzaba `get_api_key()`, el hilo de arranque de la web moría sin marcar el
    estado como error y la interfaz se quedaba cargando para siempre. Los
    `main()` de los scripts sí la capturan y la convierten en un mensaje legible
    y un código de salida.
    """


def get_api_key(variable: str = "BLABLADOR_API_KEY") -> str:
    """La clave de la API pedida, o un error legible si no está puesta."""
    clave = os.environ.get(variable)
    if not clave:
        raise ErrorConfiguracion(
            f"Falta la variable de entorno {variable}. "
            f"Defínela en el fichero .env de la raíz del proyecto."
        )
    return clave


# ── Lectura del entorno ───────────────────────────────────────────────────────
def _env_int(nombre: str, defecto: int) -> int:
    return int(os.environ.get(nombre, str(defecto)))


def _env_bool(nombre: str, defecto: bool) -> bool:
    """Verdadero salvo que la variable diga 0/false; `defecto` si no está."""
    valor = os.environ.get(nombre)
    if valor is None:
        return defecto
    return valor not in {"0", "false", "False"}


# ── Proveedores de los modelos de chat ────────────────────────────────────────
URL_BLABLADOR = "https://api.blablador.fz-juelich.de/v1"


@dataclass(frozen=True)
class ProveedorLLM:
    """A qué servicio se le habla y con qué credencial.

    Congelado por lo mismo que `ProveedorEmbeddings`: la URL y la clave tienen
    que viajar juntas. Mandar la clave de OpenAI a Blablador (o al revés) no da
    un error claro, da un 401 que parece un problema de la cuenta.
    """

    nombre: str
    base_url: str | None   # None = el endpoint oficial del SDK de OpenAI
    var_clave: str
    de_pago: bool          # activa la contabilidad de coste y el tope de gasto


PROVEEDORES_LLM: dict[str, ProveedorLLM] = {
    "blablador": ProveedorLLM("blablador", URL_BLABLADOR, "BLABLADOR_API_KEY", False),
    # Sólo para el generador, y sólo para medir gratuito frente a de pago. El
    # juez nunca sale de Blablador (invariante 6): ver `construir_llm_juez`.
    "openai": ProveedorLLM("openai", None, "OPENAI_API_KEY", True),
}


# ── Modelos ───────────────────────────────────────────────────────────────────
# Modelos de chat de Blablador, por su identificador concreto (el que lista
# /v1/models) y no por su `alias-*`: los alias se reapuntan sin aviso, y dos
# corridas dejarían de ser comparables sin que nada fallase. Si retiran o
# renombran uno de estos, la llamada falla con un 404 en vez de cambiar de
# modelo en silencio, que es justo lo que se busca. Comprobado el 24-09-2026.
#
# GPT-OSS-120B: devuelve el razonamiento en un campo aparte, así que el texto de
# la respuesta llega limpio.
MODELO_RAG_BLABLADOR = "01 - GPT-OSS-120b - an open model released by OpenAI in August 2025"


def resolver_modelo_rag(proveedor: str, entorno) -> str:
    """El identificador del generador para ese proveedor, leído de `entorno`.

    Pura (recibe el entorno como diccionario) para que los tests la prueben sin
    recargar el módulo. Con OpenAI el modelo es OBLIGATORIO y no tiene defecto,
    a propósito: un defecto haría que bastara con escribir PROVEEDOR_RAG=openai
    para empezar a gastar crédito con un modelo que nadie ha elegido. Se pide
    por su instantánea con fecha (p. ej. `gpt-5.1-2025-11-13`) y no por el
    nombre corto, por la misma razón que en Blablador se evitan los alias.
    """
    if proveedor not in PROVEEDORES_LLM:
        raise ErrorConfiguracion(
            f"PROVEEDOR_RAG={proveedor!r} no existe. "
            f"Disponibles: {', '.join(PROVEEDORES_LLM)}."
        )
    if proveedor == "openai":
        modelo = (entorno.get("OPENAI_MODEL_RAG") or "").strip()
        if not modelo:
            raise ErrorConfiguracion(
                "Con PROVEEDOR_RAG=openai hay que decir qué modelo usar con "
                "OPENAI_MODEL_RAG, por su instantánea con fecha (la lista "
                "GET https://api.openai.com/v1/models)."
            )
        return modelo
    return entorno.get("BLABLADOR_MODEL_RAG", MODELO_RAG_BLABLADOR)


# Quién redacta las respuestas. Blablador por defecto; OpenAI sólo para la
# corrida de pago. Se pasa por la shell, nunca por el .env (que pisa a la shell).
PROVEEDOR_RAG = os.environ.get("PROVEEDOR_RAG", "blablador").strip().lower()
MODEL_RAG = resolver_modelo_rag(PROVEEDOR_RAG, os.environ)

# Esfuerzo de razonamiento del generador de pago. "low" y no el defecto
# ("medium"): GPT-OSS también razona, así que no se le quita al de pago, pero el
# razonamiento se factura como salida a 10 $/M y es la única parte del coste que
# no se puede prever. Estimado sobre 109 preguntas: ~0,8-1,4 $ con "low" frente
# a ~2,1-3,2 $ con "medium", con un crédito total de 5 $.
ESFUERZO_RAZONAMIENTO_RAG = os.environ.get("ESFUERZO_RAZONAMIENTO_RAG", "low").strip().lower()

# Tope de tokens de salida por llamada, razonamiento incluido. Convierte el peor
# caso en aritmética: 109 llamadas × 3000 tokens × 10 $/M = 3,27 $ más ~0,37 $ de
# entrada, por debajo de los 5 $ aunque todas lo agotaran. Holgado: las
# respuestas visibles miden de media ~130 tokens (509 caracteres en
# libre_conciso), así que quedan más de 2500 para razonar. Si alguna lo agota,
# la respuesta llega vacía y `clasificar` la marca como ERROR: se ve, no miente.
MAX_TOKENS_SALIDA_RAG = _env_int("MAX_TOKENS_SALIDA_RAG", 3000)

# Lo más estable posible, pero NO determinista: Blablador agrupa peticiones de
# varios usuarios. Medido en las 68 preguntas en que libre_conciso y
# libre_conciso_stemming recibieron exactamente el mismo contexto, en el mismo
# orden: sólo 3 respuestas salieron idénticas y la F1 cambió en 47. Por eso las
# corridas se comparan con un test pareado sobre todas las preguntas y con la
# banda de ruido de `eval_ragas.comparar.ruido_por_metrica`, nunca pregunta a
# pregunta. Los razonadores de OpenAI no admiten temperatura (ver
# `opciones_generador`).
TEMPERATURA = 0

# Precios en dólares por millón de tokens: (entrada, entrada en caché, salida).
# Sirven para llevar la cuenta del gasto mientras se genera y para el tope
# `PRESUPUESTO_USD`; la factura real es la del panel de OpenAI, y el piloto de 5
# preguntas se contrasta con ella. Se buscan por prefijo del identificador, así
# que la instantánea con fecha encuentra su familia. De la página de precios de
# OpenAI: VOLVER A COMPROBAR antes de cada corrida de pago y anotar la fecha.
PRECIOS_USD_MTOK: dict[str, tuple[float, float, float]] = {
    "gpt-5.1": (1.25, 0.125, 10.0),
    "gpt-5-mini": (0.25, 0.025, 2.0),
    "gpt-5": (1.25, 0.125, 10.0),
}


def precio_modelo(modelo: str) -> tuple[float, float, float] | None:
    """Los precios del modelo, por el prefijo más largo que encaje; None si no hay.

    El más largo primero porque «gpt-5» es prefijo de «gpt-5.1» y de «gpt-5-mini»:
    con el primero que encajara, la mini se contaría al precio del grande.
    """
    for prefijo in sorted(PRECIOS_USD_MTOK, key=len, reverse=True):
        if modelo.startswith(prefijo):
            return PRECIOS_USD_MTOK[prefijo]
    return None


def coste_usd(modelo: str, entrada: int, salida: int, entrada_cache: int = 0) -> float:
    """Coste de una llamada. Los tokens de razonamiento ya van dentro de `salida`.

    OpenAI cuenta el razonamiento dentro de `completion_tokens`, así que sumarlo
    aparte lo cobraría dos veces. Un modelo sin precio conocido cuesta 0: es el
    caso de Blablador, que es gratuito.
    """
    precios = precio_modelo(modelo)
    if precios is None:
        return 0.0
    p_entrada, p_cache, p_salida = precios
    sin_cache = max(entrada - entrada_cache, 0)
    return (sin_cache * p_entrada + entrada_cache * p_cache + salida * p_salida) / 1e6


def es_razonador_openai(modelo: str) -> bool:
    """¿Es un modelo de razonamiento de OpenAI (gpt-5*, o1/o3/o4)?

    Estos rechazan `temperature` distinta de 1 y aceptan `reasoning_effort`. Los
    `gpt-5*-chat` son la excepción: no razonan y sí admiten temperatura.
    """
    m = modelo.lower()
    if m.startswith("gpt-5"):
        return "chat" not in m
    return len(m) > 1 and m[0] == "o" and m[1].isdigit()


def opciones_generador(proveedor: str, modelo: str) -> dict:
    """Los parámetros de `ChatOpenAI` que dependen del proveedor y del modelo.

    Pura para poder probarla. Con Blablador devuelve exactamente lo de siempre
    (temperatura 0 y nada más), para que las corridas `libre_*` sigan siendo
    reproducibles con el mismo código.
    """
    if proveedor != "openai":
        return {"temperature": TEMPERATURA}
    opciones = {"max_completion_tokens": MAX_TOKENS_SALIDA_RAG}
    if es_razonador_openai(modelo):
        # Sin temperatura, y explícitamente: langchain-openai 1.1 la quita en
        # silencio para gpt-5, pero así el código dice lo que de verdad se envía.
        opciones["reasoning_effort"] = ESFUERZO_RAZONAMIENTO_RAG
    else:
        opciones["temperature"] = TEMPERATURA
    return opciones


# Reescritura de las preguntas de seguimiento y juez de la evaluación. De otra
# familia que el generador a propósito: un juez tiende a puntuar mejor las
# respuestas de su propia familia. Qwen3.8-Flash-Next.
# Se descartó MiniMax-M2.7 (`alias-huge`): mete su razonamiento `<think>…</think>`
# dentro de la respuesta, con lo que el JSON que RAGAS espera del juez no se
# puede leer y el reescritor buscaría con el razonamiento en vez de la pregunta.
MODEL_JUDGE = os.environ.get(
    "BLABLADOR_MODEL_JUDGE",
    "02 - Qwen3.8-Flash-Next-NVFP4, general purpose large model",
)

# El juez contesta sin razonar antes. Qwen3.8 razona si no se le dice lo
# contrario, y lo que se le pide aquí no lo necesita: sacar afirmaciones de un
# texto y marcar si otro las respalda. Medido el 24-09-2026 con una llamada del
# tamaño de las de faithfulness: 123 s y 8466 tokens de razonamiento con él,
# 8,5 s sin él, y el mismo JSON válido. Con razonamiento, faithfulness (dos
# llamadas) pasaba del límite de 180 s de RAGAS y dejaba la celda en NaN. Si se
# cambia de juez, una plantilla que no use `enable_thinking` lo ignora, pero
# hay que medir que el nuevo no razone por su cuenta.
JUEZ_SIN_RAZONAMIENTO = {"chat_template_kwargs": {"enable_thinking": False}}

# Peticiones por minuto que se le permiten al juez. Blablador da a los usuarios
# externos 15 por minuto en los modelos grandes, y cada exceso bloquea la clave
# 60 s, el doble a la siguiente, hasta una hora. La evaluación lanza el juez en
# paralelo, así que sin este freno el primer lote ya lo superaría.
RPM_JUEZ = 12

# Cross-encoder multilingüe. A diferencia del embedding, que comprime cada texto
# en un vector por separado, este mira pregunta y fragmento a la vez, así que
# distingue mucho mejor lo relevante de lo que sólo comparte palabras. Es local:
# no gasta API.
RERANKER_MODEL = os.environ.get(
    "RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
)

# Tope de espera por llamada al generador, en segundos. Sin él, una generación
# que no termina congela la corrida entera: Apertus-8B se quedó 34 min en la
# pregunta 89 de `libre_apertus` sin devolver nada. Con el tope, la llamada
# falla y la fase 1 la registra como ERROR y sigue. Holgado a propósito: la
# respuesta más lenta de todas las corridas tardó 72 s, así que ninguna
# respuesta que acabe cambia.
TIMEOUT_GENERADOR_S = 180


# ── Recuperación ──────────────────────────────────────────────────────────────
# Candidatos que se le pasan al reranker. Conviene que sea generoso: el reranker
# sólo puede reordenar lo que el híbrido haya sacado.
RETRIEVER_K = _env_int("RETRIEVER_K", 20)

# Fragmentos que acaban en el contexto (y que son citables).
RERANK_K = _env_int("RERANK_K", 5)

# Se puede desactivar el reranker para comparar con y sin, de cara a la memoria.
USAR_RERANKER = _env_bool("USAR_RERANKER", True)

# Stemming en español (Snowball) para la mitad léxica del híbrido, para que
# «proceso» y «procesos» cuenten como la misma palabra. Apagado hasta medirlo:
# también funde términos que en este temario son distintos (proceso, procesador
# y procesamiento dan todos «proces»; página y paginación, «pagin»).
BM25_STEMMING = _env_bool("BM25_STEMMING", False)


# ── Generación ────────────────────────────────────────────────────────────────
# Cómo se le pide al generador que redacte. "conciso" es el estilo adoptado;
# los otros dos se conservan para que las corridas que los midieron sigan
# siendo reproducibles.
#  - "explicativo", el prompt original: respuestas 5 veces más largas que el
#    ground truth y precisión factual 0,37. Con "conciso", sobre las mismas 10
#    preguntas, la F1 pasó de 0,45 a 0,65 (Wilcoxon p = 0,002) sin perder
#    cobertura (0,84 → 0,90). Descartado por la longitud.
#  - "minimo" limita los datos y no las frases. Sobre 24 preguntas
#    estratificadas empató con "conciso" en F1 (0,634 frente a 0,609, p = 0,41)
#    y perdió cobertura en síntesis (−0,08): en las preguntas de varios pasos,
#    quedarse con «la idea principal» dejaba fuera lo que se preguntaba.
# Con "conciso" sobre las 94: F1 0,621, y 0,619 en las 70 que no se usaron
# para afinarlo. Los textos de cada estilo viven con el prompt, en
# `rag/generacion.py`. Un valor mal escrito revienta al importar, a propósito:
# una corrida etiquetada con un estilo que en realidad usara otro falsearía la
# comparativa sin avisar.
ESTILOS_RESPUESTA = ("explicativo", "conciso", "minimo")
ESTILO_RESPUESTA = os.environ.get("ESTILO_RESPUESTA", "conciso")
if ESTILO_RESPUESTA not in ESTILOS_RESPUESTA:
    raise ErrorConfiguracion(
        f"ESTILO_RESPUESTA={ESTILO_RESPUESTA!r} no existe. "
        f"Disponibles: {', '.join(ESTILOS_RESPUESTA)}."
    )

# Reparto entre la mitad léxica y la semántica del híbrido. Se lee de aquí tanto
# al construir el recuperador como al mostrar la configuración en la web: con
# los números escritos a mano en los dos sitios, cambiar uno hacía que la
# interfaz informara de unos pesos que el sistema ya no estaba usando.
PESOS_HIBRIDO = {"bm25": 0.4, "denso": 0.6}

# Al reranker se le piden más de RERANK_K candidatos porque después el
# deduplicador elimina fragmentos: si se recortara ya a 5, quedarían menos de 5
# en el contexto.
FACTOR_CANDIDATOS_RERANKER = 3


# ── Demo pública de la web ────────────────────────────────────────────────────
# Con DEMO_PUBLICA=1 la web limita cuánto se le puede preguntar. No es por
# coste (Blablador es gratuito) sino por la clave: Blablador da a los usuarios
# externos unas 30 peticiones por minuto, 15 en los modelos grandes como el
# generador, y castiga cada exceso bloqueando la clave 60 s, el doble a la
# siguiente, hasta una hora. Una pregunta gasta una llamada al generador más el
# embedding de la consulta (y la reescritura si es de seguimiento): 8 preguntas
# por minuto son 8 generaciones, por debajo de 15, y como mucho 24 peticiones en
# total, por debajo de 30. En local no se limita nada.
DEMO_PUBLICA = _env_bool("DEMO_PUBLICA", False)
DEMO_PREGUNTAS_POR_MINUTO = _env_int("DEMO_PREGUNTAS_POR_MINUTO", 8)
# Por visitante: que una sola persona no pueda agotar el cupo de todos.
DEMO_PREGUNTAS_POR_MINUTO_IP = _env_int("DEMO_PREGUNTAS_POR_MINUTO_IP", 3)
# Una pregunta de examen cabe de sobra; un texto pegado entero es un prompt caro.
DEMO_MAX_CARACTERES_PREGUNTA = 500


# ── Texto de rechazo ──────────────────────────────────────────────────────────
# Fuente única de verdad. El prompt lo inyecta, el chat lo detecta para no
# imprimir fuentes y la evaluación lo usa para distinguir un rechazo legítimo de
# un fallo. Si cada sitio tuviera su propia copia, un acento de diferencia
# contaría como fallo todos los rechazos correctos.
REFUSAL_TEXT = "No tengo la suficiente información para contestar a su pregunta."


# ── Índice: proveedores de embeddings ─────────────────────────────────────────
# Familia de API: la clave que elige la fábrica en `_FABRICAS_EMBEDDINGS`.
API_OPENAI = "openai"   # cualquier endpoint compatible con OpenAI


@dataclass(frozen=True)
class ProveedorEmbeddings:
    """Todo lo que distingue a un proveedor de embeddings de otro.

    Va junto y congelado a propósito. El modelo, las dimensiones, la colección y
    el directorio tienen que viajar en el mismo objeto: en cuanto se pueden
    descasar, alguien indexa con uno y consulta con otro y el recuperador
    devuelve basura sin dar ningún error.
    """

    nombre: str           # clave del registro, y nombre de la corrida de evaluación
    api: str             # API_OPENAI -> qué fábrica lo construye
    modelo: str
    dims: int             # dimensión FINAL, tras el truncado Matryoshka
    dims_nativas: int     # lo que devuelve el servidor antes de truncar
    coleccion: str
    directorio: Path      # persist_directory de Chroma
    lote: int             # textos por petición al indexar
    var_clave: str        # variable de entorno con la credencial
    base_url: str | None  # None = SDK nativo del proveedor


# Un único proveedor. El registro se conserva porque sigue siendo la única
# definición de modelo, dimensión, colección y directorio: el script que indexa
# y el recuperador leen la misma entrada, y no se pueden descasar.
PROVEEDORES_EMBEDDINGS: dict[str, ProveedorEmbeddings] = {
    "blablador": ProveedorEmbeddings(
        nombre="blablador",
        api=API_OPENAI,
        # Qwen3-Embedding-8B. Blablador no le da identificador concreto, sólo
        # alias, así que se usa el que lleva el modelo en el nombre y no el
        # genérico `alias-embeddings`: comprobado el 24-09-2026, los dos
        # devuelven el mismo vector (coseno 1,000000) y /v1/models da la misma
        # raíz, `Qwen/Qwen3-Embedding-8B`. El genérico es el que reapuntarían
        # al cambiar de modelo, y el sello de la colección no lo detectaría
        # porque la cadena no cambia (sólo un cambio de dimensión).
        modelo="alias-qwen3-8b-embeddings",
        # La dimensión nativa: no hay motivo para tirar información, y con 762
        # fragmentos el tamaño del índice no importa.
        dims=4096,
        dims_nativas=4096,
        coleccion="documentacion_blablador",
        directorio=CHROMA_DIR_BLABLADOR,
        # Conservador, no medido: el servicio es gratuito y compartido, y un
        # lote de 100 fragmentos son ~250 kB de petición y ~3 MB de respuesta.
        # Si aparecen 413 o timeouts, bajarlo; si va sobrado, medirlo con
        # `--only` antes de subirlo.
        lote=32,
        var_clave="BLABLADOR_API_KEY",
        base_url=URL_BLABLADOR,
    ),
}


# Esta función va aquí arriba, rompiendo el «constantes primero, funciones
# después» del resto del fichero, porque las constantes de justo debajo la
# llaman. Es deliberado, no un descuido de orden.
def resolver_proveedor(nombre: str | None = None) -> ProveedorEmbeddings:
    """El proveedor de embeddings pedido, o el activo si no se pide ninguno.

    Es una función pura sobre el registro, y ese es el punto: los tests pueden
    preguntar por cualquier proveedor sin recargar el módulo. Recargarlo no
    serviría —`load_dotenv(override=True)` volvería a meter el .env real de
    quien ejecute los tests, y `rag/__init__` seguiría viendo las constantes del
    módulo viejo.
    """
    clave = (nombre or EMBEDDING_PROVIDER).strip().lower()
    if clave not in PROVEEDORES_EMBEDDINGS:
        raise ErrorConfiguracion(
            f'Proveedor de embeddings desconocido: "{clave}". '
            f"Disponibles: {', '.join(PROVEEDORES_EMBEDDINGS)}. "
            f"Se elige con EMBEDDING_PROVIDER en el .env de la raíz."
        )
    return PROVEEDORES_EMBEDDINGS[clave]


EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "blablador").strip().lower()
_PROVEEDOR = resolver_proveedor(EMBEDDING_PROVIDER)

# Vistas del proveedor activo. Siguen siendo la única definición de cada valor:
# lo que ha cambiado es que la definición vive ahora en la entrada del registro,
# y tanto el script que indexa como el que consulta leen la misma entrada.
COLLECTION      = _PROVEEDOR.coleccion
EMBEDDING_MODEL = _PROVEEDOR.modelo
EMBEDDING_DIMS  = _PROVEEDOR.dims
BATCH_SIZE      = _PROVEEDOR.lote
CHROMA_ACTIVO   = _PROVEEDOR.directorio

# Fuera del registro a propósito: la distancia es parte del protocolo de
# comparación, no del proveedor. Si cada uno pudiera traer la suya, las dos
# corridas medirían con reglas distintas y el Δ no significaría nada.
# Los vectores van normalizados, así que coseno y L2 ordenan igual, pero coseno
# deja las distancias en [0, 2] y son legibles al depurar.
DISTANCIA = "cosine"

# El sello que `cli/process_md.py` graba en la colección y que `rag/recuperacion.py`
# contrasta al abrirla. Con nombre porque lo escribe un fichero y lo lee otro:
# un literal repetido en dos sitios es exactamente el fallo silencioso que todo
# esto viene a evitar.
CLAVE_META_MODELO = "modelo_embeddings"
CLAVE_META_DIMS   = "dims_embeddings"
CLAVE_META_CHUNKS = "n_chunks"


# ── Troceado ──────────────────────────────────────────────────────────────────
# Tamaño máximo de un chunk. 2500 caracteres son ~600 tokens al ratio real
# medido sobre este corpus (4,2 car/token en prosa castellana). Por debajo de
# este umbral la sección se indexa entera, sin tocar.
CHUNK_SIZE = 2500

# 15 % de solapamiento. Sólo se aplica al subdividir secciones grandes: las
# secciones que caben enteras no necesitan redundancia con sus vecinas.
CHUNK_OVERLAP = 375

# Las secciones contiguas se van fusionando mientras el resultado no pase de
# aquí. Ataca el 31 % de secciones de menos de 400 caracteres ("Sitio:",
# "Curso:", restos de listas), que como vector suelto sólo aportan ruido.
MIN_CHUNK = 1200

# Ratio medido sobre este corpus con un tokenizador real (el de Gemini, en la
# primera etapa del proyecto). `process_md --dry-run` lo usa para estimar
# tokens sin hacer ni una llamada.
CARACTERES_POR_TOKEN = 4.2


# ── Utilidad de texto compartida ──────────────────────────────────────────────
def sin_tildes(texto: str) -> str:
    """Minúsculas y sin diacríticos.

    Vive en la base del paquete porque la usan las dos mitades del sistema: la
    recuperación, para tokenizar en BM25, y la generación, para reconocer el
    texto de rechazo aunque el modelo le cambie un acento.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    ).lower()


# ── Embeddings ────────────────────────────────────────────────────────────────
def _normalizar(vectores: list[list[float]]) -> list[list[float]]:
    """Renormaliza a norma 1 tras el truncado Matryoshka."""
    arr = np.asarray(vectores, dtype=np.float32)
    normas = np.linalg.norm(arr, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return (arr / normas).tolist()


def _truncar(vectores: list[list[float]], dims: int) -> list[list[float]]:
    """Truncado Matryoshka en cliente: las `dims` PRIMERAS componentes.

    Con la dimensión nativa no recorta nada, pero sigue comprobando que el
    servidor devuelve vectores del tamaño esperado. Si se baja `dims`, es un prefijo, no una submuestra: en un modelo entrenado con Matryoshka son
    las primeras componentes las que concentran la información, y quedarse con
    otras cualesquiera destruiría el vector sin dar ningún error.

    Se trunca aquí y no se le pide al servidor (el parámetro `dimensions` de la
    API de OpenAI) porque el servidor no renormaliza después, y sin norma 1 el
    coseno deja de ordenar igual que el producto escalar.
    """
    for v in vectores:
        if len(v) < dims:
            raise ErrorConfiguracion(
                f"El servidor ha devuelto vectores de {len(v)} componentes y se "
                f"esperaban al menos {dims}. Si el proveedor ha reapuntado su "
                f"alias a otro modelo, hay que reindexar contra el nuevo."
            )
    return [v[:dims] for v in vectores]


# Qwen3-Embedding es asimétrico por INSTRUCCIÓN, no por un parámetro de la API:
# la consulta se envuelve en "Instruct: {tarea}\nQuery: {consulta}" y el
# documento se manda crudo, porque un texto que se indexa y una pregunta que lo
# busca no deben proyectarse igual. La tarea va en inglés porque es el idioma en
# el que se instruyó al modelo; la consulta va en castellano, como el corpus.
TAREA_QWEN = (
    "Given a question about an Operating Systems course, retrieve the passages "
    "from the course notes that answer it"
)

# En una sola línea y con el \n escapado a propósito. Los ficheros de este
# repositorio llevan CRLF: escrita como cadena triple, la plantilla se llevaría
# el \r y se le estaría mandando al modelo un prompt distinto del documentado,
# sin que nada lo avisara.
PLANTILLA_CONSULTA_QWEN = "Instruct: {tarea}\nQuery: {consulta}"


def consulta_con_instruccion(consulta: str) -> str:
    """La consulta envuelta en el prefijo de instrucción de Qwen3."""
    return PLANTILLA_CONSULTA_QWEN.format(tarea=TAREA_QWEN, consulta=consulta)


def _embeddings_openai(prov: ProveedorEmbeddings):
    """
    Embeddings por un endpoint compatible con OpenAI (Blablador / Qwen3).

    Chroma llama a embed_documents/embed_query sin argumentos, así que la única
    manera de que la consulta lleve su instrucción y el documento no es
    sobrescribir los dos métodos. Import diferido: leer una constante de
    `rag.config` tiene que seguir siendo instantáneo.
    """
    from langchain_openai import OpenAIEmbeddings

    clave = get_api_key(prov.var_clave)

    class QwenRetrievalEmbeddings(OpenAIEmbeddings):
        def embed_documents(self, texts, **kwargs):
            brutos = super().embed_documents(texts, **kwargs)
            return _normalizar(_truncar(brutos, prov.dims))

        def embed_query(self, text, **kwargs):
            # `super().embed_documents`, y NO `super().embed_query`: el
            # embed_query de OpenAIEmbeddings está implementado como
            # `self.embed_documents([text])[0]`, así que por despacho dinámico
            # rebotaría al método de aquí arriba y el vector se truncaría y
            # renormalizaría dos veces. Es idempotente y no fallaría; sólo haría
            # que el código mintiera sobre lo que hace.
            brutos = super().embed_documents([consulta_con_instruccion(text)], **kwargs)
            return _normalizar(_truncar(brutos, prov.dims))[0]

    return QwenRetrievalEmbeddings(
        model=prov.modelo,
        api_key=clave,
        base_url=prov.base_url,
        chunk_size=prov.lote,
        # Obligatorio. Con el defecto (True), langchain-openai tokeniza con
        # tiktoken (cl100k_base) y manda arrays de tokens en lugar de texto. El
        # servidor de Qwen los decodificaría con SU tokenizador, que no es el
        # mismo: saldrían vectores de un texto que nadie ha escrito, sin error
        # ni aviso. Con False se manda el texto crudo, en lotes de chunk_size.
        check_embedding_ctx_length=False,
        # `dimensions` se deja sin poner a propósito: si se pusiera, el truncado
        # lo haría el servidor y nadie renormalizaría después. Se trunca en
        # cliente con `_truncar`, igual que se renormaliza con `_normalizar`.
    )


_FABRICAS_EMBEDDINGS = {
    API_OPENAI: _embeddings_openai,
}


def construir_embeddings(proveedor: str | None = None):
    """Los embeddings del proveedor activo, o de uno concreto si se pide."""
    prov = resolver_proveedor(proveedor)
    return _FABRICAS_EMBEDDINGS[prov.api](prov)


def construir_llm(modelo: str, proveedor: str = "blablador", **opciones):
    """Un modelo de chat del proveedor pedido (Blablador si no se dice otro).

    Los parámetros que dependen del modelo (temperatura, razonamiento, tope de
    salida) los decide `opciones_generador`. `opciones` pasa tal cual a
    `ChatOpenAI` y manda sobre ellos; la evaluación la usa para frenar al juez
    con un `rate_limiter`.
    """
    from langchain_openai import ChatOpenAI

    if proveedor not in PROVEEDORES_LLM:
        raise ErrorConfiguracion(
            f"Proveedor de chat desconocido: {proveedor!r}. "
            f"Disponibles: {', '.join(PROVEEDORES_LLM)}."
        )
    prov = PROVEEDORES_LLM[proveedor]
    return ChatOpenAI(
        model=modelo,
        api_key=get_api_key(prov.var_clave),
        base_url=prov.base_url,
        **{**opciones_generador(proveedor, modelo), **opciones},
    )


def construir_llm_juez(**opciones):
    """El modelo del juez, sin razonamiento previo (ver `JUEZ_SIN_RAZONAMIENTO`).

    Lo usan el juez de RAGAS y el reescritor de preguntas de seguimiento. Una sola
    fábrica para los dos, para que no pueda uno razonar y el otro no.

    El proveedor va fijo a Blablador y no sigue a `PROVEEDOR_RAG`, a propósito:
    la corrida de pago cambia el generador y nada más. Si el juez se mudara con
    él, la comparativa mediría a la vez dos cosas (invariante 6), y además un
    juez de OpenAI puntuaría a GPT-OSS y a GPT-5.1, dos modelos de su familia.
    """
    return construir_llm(
        MODEL_JUDGE, "blablador", extra_body=JUEZ_SIN_RAZONAMIENTO, **opciones,
    )


# ── Identidad de la colección ─────────────────────────────────────────────────
def comprobar_identidad(
    *,
    coleccion: str,
    n_vectores: int,
    dims_reales: int | None,
    espacio: str | None,
    modelo_sellado: str | None = None,
    dims_selladas: int | None = None,
    chunks_sellados: int | None = None,
) -> str | None:
    """Contrasta lo que la colección tiene grabado con la configuración activa.

    Devuelve `None` si todo cuadra, o el texto de un aviso si la colección está
    en un estado raro pero utilizable (el indexado quedó a medias, la creó algo
    que no fue `cli/process_md.py`). Lanza `ErrorConfiguracion` cuando la
    discrepancia es real y seguir adelante daría resultados falsos.

    Es pura —recibe datos, no un objeto de Chroma— para que se pueda probar sin
    abrir una base de datos. Quien sabe de Chroma es
    `rag.recuperacion._identidad_coleccion`.
    """
    indexa = (f"Indexa con: EMBEDDING_PROVIDER={EMBEDDING_PROVIDER} "
              f"python -m cli.process_md --reset")

    if n_vectores == 0:
        raise ErrorConfiguracion(
            f'La colección "{coleccion}" está vacía. {indexa}'
        )

    # La dimensión la sabe Chroma siempre, esté o no el sello: es la única
    # comprobación que también protege a las colecciones anteriores al sello.
    if dims_reales is not None and dims_reales != EMBEDDING_DIMS:
        raise ErrorConfiguracion(
            f'La colección "{coleccion}" guarda vectores de {dims_reales} '
            f"dimensiones y la configuración activa produce {EMBEDDING_DIMS} "
            f"({EMBEDDING_PROVIDER} / {EMBEDDING_MODEL}). {indexa}"
        )

    if espacio is not None and espacio != DISTANCIA:
        raise ErrorConfiguracion(
            f'La colección "{coleccion}" se creó con la distancia "{espacio}" y '
            f'el sistema compara con "{DISTANCIA}". {indexa}'
        )

    avisos = []

    # Sin `hnsw:space` la colección no la creó `cli/process_md.py`. No es fatal
    # —con vectores normalizados coseno y L2 ordenan igual— pero sí señal de que
    # alguien la creó por accidente al consultar antes de indexar.
    if espacio is None:
        avisos.append(
            f'La colección "{coleccion}" no declara distancia, así que usa la '
            f"de por defecto de Chroma en vez de {DISTANCIA}."
        )

    # Que falte el sello NO genera aviso. Toda colección creada con
    # `python -m cli.process_md --reset` lo lleva, y lo que protege de verdad —dimensiones
    # y distancia— ya se ha comprobado arriba, con sello o sin él;
    # `python -m cli.inspeccionar --db` enseña el sello para quien quiera mirarlo.
    if modelo_sellado is not None and modelo_sellado != EMBEDDING_MODEL:
        raise ErrorConfiguracion(
            f'La colección "{coleccion}" se indexó con "{modelo_sellado}" y se '
            f'está consultando con "{EMBEDDING_MODEL}". No da error por sí solo: '
            f"da un recuperador que devuelve basura. {indexa}"
        )

    if dims_selladas is not None and dims_selladas != EMBEDDING_DIMS:
        raise ErrorConfiguracion(
            f'La colección "{coleccion}" se indexó a {dims_selladas} dimensiones '
            f"y la configuración activa produce {EMBEDDING_DIMS}. {indexa}"
        )

    # El híbrido monta BM25 sobre los documentos de la colección, así que un
    # índice a medias (un 429 a mitad del indexado) cambia también la mitad
    # léxica, no sólo la densa.
    if chunks_sellados is not None and chunks_sellados != n_vectores:
        avisos.append(
            f'La colección "{coleccion}" se selló con {chunks_sellados} '
            f"fragmentos y tiene {n_vectores}: el indexado quedó a medias. "
            f"Relanzar `python -m cli.process_md` sin --reset lo completa."
        )

    return " ".join(avisos) if avisos else None
