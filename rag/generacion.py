"""
generacion.py — De los fragmentos recuperados a la respuesta citada.

Contiene el prompt del RAG, las cadenas de LangChain que lo ejecutan y las
utilidades que rodean a una respuesta: numerar el contexto para que se pueda
citar, extraer las citas que el modelo usó de verdad y reconocer el texto de
rechazo.

La generación va deliberadamente separada de la recuperación. Quien llama
recupera **una sola vez** y le pasa esos mismos fragmentos al generador, de modo
que las fuentes que se enseñan al usuario son exactamente las que leyó el
modelo. Si la cadena recuperase por dentro, no habría forma de saberlo.

Los modelos de chat los construye `rag.config.construir_llm()`, igual que los
embeddings salen de `construir_embeddings()`: un único sitio sabe a qué servicio
se habla.
"""

from __future__ import annotations

import re
from typing import Sequence

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from .config import (
    ESTILO_RESPUESTA,
    MODEL_RAG,
    PROVEEDOR_RAG,
    REFUSAL_TEXT,
    TIMEOUT_GENERADOR_S,
    construir_llm,
    construir_llm_juez,
    sin_tildes,
)
from .recuperacion import describir_fuente


# ── Detección del rechazo ─────────────────────────────────────────────────────
_RECHAZO_NORMALIZADO = sin_tildes(REFUSAL_TEXT).strip().rstrip(".")


def es_rechazo(texto: str) -> bool:
    """¿La respuesta es el rechazo por falta de información?

    Se compara sin tildes y sin puntuación final porque el modelo, aun con la
    instrucción de responder literalmente, a veces cambia una tilde o el punto.
    Una comparación con `==` daría por buenas respuestas que son un rechazo.
    """
    if not isinstance(texto, str):
        return False
    normalizado = sin_tildes(texto).strip().rstrip(".").strip()
    return _RECHAZO_NORMALIZADO in normalizado


# ── Contexto y citas ──────────────────────────────────────────────────────────
def formatear_contexto(docs: Sequence[Document]) -> str:
    """
    Numera los fragmentos para que el modelo pueda citarlos como [n].

    La cabecera de cada fragmento lleva fichero y sección: es lo que después se
    enseña al usuario como fuente, así que tiene que ser legible por sí sola.
    """
    return "\n\n".join(
        f"[{i}] ({describir_fuente(d)})\n{d.page_content}"
        for i, d in enumerate(docs, start=1)
    )


# La marca pedida, [n], y la que GPT-OSS trae de su entrenamiento, 【n†L4-L7】
# (número de fragmento, † y un rango de líneas). Medido con GPT-OSS-120B: 1 de
# 13 respuestas citó así pese a que el prompt pide [n]. Sin reconocerla, esa
# respuesta contaba como «sin citas», el pie de fuentes salía vacío y la marca
# llegaba entera al juez de RAGAS. Se arregla aquí y no en el prompt a
# propósito: añadir al prompt «nada de 【】» lo empeoró, 5 de 10 respuestas.
_CITA = re.compile(r"\[(\d+)\]|【(\d+)(?:†[^】]*)?】")


def extraer_citas(respuesta: str, n_docs: int) -> list[int]:
    """Índices (1-based) realmente citados, en orden de aparición.

    Se descartan los que se salen del rango: si el modelo inventa un [9] cuando
    sólo hay 5 fragmentos, esa cita no apunta a nada.
    """
    vistos: list[int] = []
    for m in _CITA.finditer(respuesta):
        n = int(m.group(1) or m.group(2))
        if 1 <= n <= n_docs and n not in vistos:
            vistos.append(n)
    return vistos


def quitar_citas(texto: str) -> str:
    """La respuesta sin las marcas [n], en una sola línea de espacios normales.

    Se usa al puntuar: los `[n]` son ruido sintáctico y, al descomponer la
    respuesta en afirmaciones, el juez los arrastra dentro de las frases y
    ensucia la comparación con un ground truth que no los lleva.
    """
    if not isinstance(texto, str):
        return ""
    return re.sub(r"\s+", " ", _CITA.sub("", texto)).strip()


# ── Prompt del RAG ────────────────────────────────────────────────────────────
# Lo único que cambia entre estilos (`ESTILO_RESPUESTA`): el objetivo y la regla
# 6. El resto del prompt es idéntico, para que una comparativa entre estilos
# mida sólo eso. "explicativo" reproduce letra por letra el prompt de siempre.
_ESTILOS = {
    "explicativo": (
        "claras, precisas y bien explicadas",
        "Sé claro y ordenado. Usa listas cuando ayuden.",
    ),
    "conciso": (
        "claras, precisas y concisas",
        "Responde de forma directa a lo que se pregunta, en pocas frases.\n"
        "   No añadas contexto, ejemplos ni detalles que la pregunta no pida.",
    ),
    # Limita los datos, no las frases. La segunda parte protege la cobertura en
    # las preguntas de síntesis, que sí piden pasos o elementos.
    "minimo": (
        "claras, precisas y ceñidas a lo que se pregunta",
        "Responde sólo a lo que se pregunta, con la idea principal. Si la pregunta\n"
        "   pide pasos, elementos o diferencias, dalos todos, pero no añadas\n"
        "   características, componentes, ejemplos ni consecuencias que no se pidan.",
    ),
}

_PLANTILLA_RAG = """\
Eres un asistente experto en los documentos proporcionados.
Tu objetivo es proporcionar respuestas <objetivo>.

Reglas:
1. Responde únicamente con información del Contexto. Puedes combinar e inferir a
   partir de varios fragmentos.
2. Cita SIEMPRE de dónde sacas cada afirmación con la marca [n] del fragmento,
   colocada al final de la frase correspondiente. Si una frase se apoya en
   varios fragmentos, cítalos todos: [1][3].
3. Si el Contexto contiene información PARCIAL relacionada con la pregunta,
   responde con lo que sí puedas afirmar, citándolo.
4. Si la información no está en el Contexto, responde EXACTAMENTE y sin añadir
   nada más:
   "{refusal}"
5. No inventes datos, no cites fuentes externas y no uses conocimiento propio.
6. <regla_estilo>

Contexto:
{context}

Pregunta: {input}
Respuesta:"""


def plantilla_rag(estilo: str = ESTILO_RESPUESTA) -> str:
    """El prompt del RAG con el estilo de respuesta pedido.

    Los huecos del estilo van con `<…>` y no con `{…}` a propósito: las llaves
    son de PromptTemplate, y un hueco sin rellenar se convertiría en una
    variable más que nadie pasa.
    """
    objetivo, regla = _ESTILOS[estilo]
    return (_PLANTILLA_RAG
            .replace("<objetivo>", objetivo)
            .replace("<regla_estilo>", regla))


# El prompt activo, el que usan el chat, la web y la evaluación.
RAG_TEMPLATE = plantilla_rag()


def build_rag_llm():
    """El modelo que redacta las respuestas, del proveedor de `PROVEEDOR_RAG`.

    El prompt es el mismo con cualquier proveedor: la corrida de pago compara
    modelos, no prompts.
    """
    return construir_llm(MODEL_RAG, PROVEEDOR_RAG, timeout=TIMEOUT_GENERADOR_S)


def build_generador(llm=None):
    """Cadena de generación: recibe `entrada_generador(...)` y devuelve texto."""
    llm = llm or build_rag_llm()
    prompt = PromptTemplate.from_template(RAG_TEMPLATE).partial(refusal=REFUSAL_TEXT)
    return prompt | llm | StrOutputParser()


def entrada_generador(docs: Sequence[Document], pregunta: str) -> dict:
    """Lo que recibe el generador: los fragmentos ya recuperados y la pregunta.

    `pregunta` es la ORIGINAL del usuario, nunca la reescrita: la reescritura
    sólo sirve para buscar. Y `docs` son los que ya se recuperaron una vez, los
    mismos que se enseñan como fuentes; el generador no recupera por su cuenta.
    """
    return {"context": formatear_contexto(docs), "input": pregunta}


# ── Reescritura de preguntas de seguimiento ───────────────────────────────────
REESCRITURA_TEMPLATE = """\
Reescribe la última pregunta del usuario para que se entienda por sí sola, sin
el historial. Resuelve los pronombres y las referencias implícitas usando el
historial. No la respondas y no añadas nada: devuelve solo la pregunta
reescrita. Si ya se entiende por sí sola, devuélvela tal cual.

Historial:
{historial}

Última pregunta: {pregunta}
Pregunta reescrita:"""


def build_reescritor(llm=None):
    """
    Cadena que convierte "¿y en LRU?" en una pregunta autónoma.

    Sin esto, una pregunta de seguimiento se manda al recuperador tal cual y
    devuelve cualquier cosa: "¿y sus desventajas?" no se parece a nada del
    corpus. Usa el modelo del juez, también sin razonamiento: es una tarea
    mecánica, y razonando cada pregunta de seguimiento esperaría un minuto.
    """
    llm = llm or construir_llm_juez()
    return PromptTemplate.from_template(REESCRITURA_TEMPLATE) | llm | StrOutputParser()


# Las respuestas se recortan a propósito. El reescritor sólo necesita saber de
# qué se venía hablando para resolver un "sus" o un "eso"; no necesita la
# respuesta entera. Medido: con las respuestas completas y 3 turnos, la llamada
# de reescritura gastaba 4.638 tokens de entrada, más que la propia generación
# (2.231). Recortando, baja a unos pocos cientos sin perder el referente.
MAX_CHARS_RESPUESTA_HISTORIAL = 300

# Turnos de conversación que se le enseñan al reescritor.
MAX_TURNOS_HISTORIAL = 2


def formatear_historial(historial: Sequence[tuple[str, str]],
                        max_turnos: int = MAX_TURNOS_HISTORIAL) -> str:
    """Los últimos turnos como texto plano para el reescritor."""
    lineas = []
    for pregunta, respuesta in list(historial)[-max_turnos:]:
        resumen = " ".join(respuesta.split())[:MAX_CHARS_RESPUESTA_HISTORIAL]
        if len(resumen) == MAX_CHARS_RESPUESTA_HISTORIAL:
            resumen += "..."
        lineas.append(f"Usuario: {pregunta}\nAsistente: {resumen}")
    return "\n".join(lineas)


def consulta_de_busqueda(reescritor, historial: Sequence[tuple[str, str]],
                         pregunta: str) -> str:
    """La consulta con la que se recupera: la pregunta, autónoma si hace falta.

    Sin historial es la pregunta tal cual. Con historial, una de seguimiento
    ("¿y en LRU?") no se parece a nada del corpus hasta que se reescribe. Si el
    reescritor devuelve vacío, se busca con la original.
    """
    if not historial:
        return pregunta
    reescrita = reescritor.invoke({
        "historial": formatear_historial(historial),
        "pregunta": pregunta,
    }).strip()
    return reescrita or pregunta
