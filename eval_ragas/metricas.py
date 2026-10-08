"""
metricas.py — Definición de las siete métricas y su carga en español.

Se centraliza aquí para que `adaptar_prompts.py` (que las traduce) y
`puntuar.py` (que las usa) trabajen exactamente sobre el mismo conjunto. Si
cada script instanciara las suyas, se podrían adaptar unas plantillas y
puntuar con otras sin que nada avisara.
"""

from __future__ import annotations

import asyncio
import math
import typing as t
import warnings
from dataclasses import dataclass, field

# `ragas.metrics` avisa de deprecación a favor de `ragas.metrics.collections`,
# pero `ragas.evaluate()` —la vía que documentan los tutoriales— sigue esperando
# estas clases. Se silencia el aviso para que no ensucie la salida.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="ragas")

from ragas.metrics import (  # noqa: E402
    FactualCorrectness,
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
    SemanticSimilarity,
)
from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.metrics.base import MetricType  # noqa: E402

from rag import ErrorConfiguracion  # noqa: E402

IDIOMA = "spanish"


# ── Corrección factual, con dos arreglos sobre la de RAGAS ────────────────────
def puntuacion_factual(respaldo_respuesta: t.Sequence[bool],
                       respaldo_referencia: t.Sequence[bool], modo: str) -> float:
    """Precisión, cobertura o F1 a partir de los veredictos del juez.

    `respaldo_respuesta`: por cada afirmación de la respuesta, ¿la respalda el
    ground truth? `respaldo_referencia`: por cada afirmación del ground truth,
    ¿la respalda la respuesta?

    La cobertura es la proporción de afirmaciones del ground truth que están en
    la respuesta, y sale sólo de `respaldo_referencia`. RAGAS la calcula como
    tp / (tp + fn) con tp contado sobre las afirmaciones de la RESPUESTA:
    mezcla los dos sentidos, así que premia la verbosidad (10 afirmaciones
    respaldadas y 1 de 2 del ground truth cubierta dan 10/11 y no 1/2) y da 0 a
    una respuesta que cubre el ground truth entero si el juez no respalda ninguna
    de las suyas. Visto en prueba10: las preguntas 3 y 4 cubrían 1/1 y 2/2 del
    ground truth y RAGAS les daba 0.

    Una respuesta sin afirmaciones no es precisa (0). Un ground truth sin
    afirmaciones es un fallo del juez al descomponerlo: NaN, para que se vea y
    no baje la media en silencio.
    """
    respaldo_respuesta = [bool(v) for v in respaldo_respuesta]
    respaldo_referencia = [bool(v) for v in respaldo_referencia]
    precision = (sum(respaldo_respuesta) / len(respaldo_respuesta)
                 if respaldo_respuesta else 0.0)
    if modo == "precision":
        return precision
    if not respaldo_referencia:
        return math.nan
    cobertura = sum(respaldo_referencia) / len(respaldo_referencia)
    if modo == "recall":
        return cobertura
    return (2 * precision * cobertura / (precision + cobertura)
            if precision + cobertura else 0.0)


@dataclass
class CorreccionFactual(FactualCorrectness):
    """`FactualCorrectness` de RAGAS con dos arreglos medidos sobre este banco.

    1. La cobertura se calcula de verdad (ver `puntuacion_factual`), y la F1 es
       la media armónica de la precisión y esa cobertura.
    2. Al verificar la respuesta contra el ground truth, el juez ve también la
       pregunta. Los ground truth están escritos como respuesta a su pregunta y
       se apoyan en ella («En este contexto…», «Realiza dos funciones…», sin
       decir quién): leídos solos, el juez no puede confirmar nada de lo que la
       respuesta dice del sujeto. Medido en prueba10 (preguntas 3 y 4): sin la
       pregunta rechazaba 12 de 12 y 3 de 3 afirmaciones, incluida una casi
       literal al ground truth; con ella aceptaba justo las que coinciden (2 y 1)
       y seguía rechazando los detalles que el ground truth no trae.

    Conserva el `name` de RAGAS a propósito: las plantillas en español se
    buscan por él, y `puntuar.mapear_columnas` distingue las dos caras por él y
    por el `mode`. De paso, en modo recall hace 2 llamadas al juez y no 4.
    """

    # RAGAS le quita a cada muestra las columnas que la métrica no declara:
    # sin `user_input` aquí, la pregunta no llegaría.
    _required_columns: t.Dict[MetricType, t.Set[str]] = field(
        default_factory=lambda: {
            MetricType.SINGLE_TURN: {"user_input", "response", "reference"}
        }
    )

    async def _respaldo(self, texto: str, premisa: str, callbacks) -> list[bool]:
        afirmaciones = await self.decompose_claims(texto, callbacks)
        if not afirmaciones:
            return []
        veredictos = await self.verify_claims(
            premise=premisa, hypothesis_list=afirmaciones, callbacks=callbacks
        )
        return [bool(v) for v in veredictos]

    async def _single_turn_ascore(self, sample: SingleTurnSample, callbacks) -> float:
        assert self.llm is not None, "LLM must be set"
        tareas = {}
        if self.mode != "recall":
            con_pregunta = f"Pregunta: {sample.user_input}\nRespuesta: {sample.reference}"
            tareas["respuesta"] = self._respaldo(sample.response, con_pregunta, callbacks)
        if self.mode != "precision":
            tareas["referencia"] = self._respaldo(sample.reference, sample.response, callbacks)
        resultados = dict(zip(tareas, await asyncio.gather(*tareas.values())))
        return puntuacion_factual(
            resultados.get("respuesta", []), resultados.get("referencia", []), self.mode
        )

# Nombre corto -> (clase, kwargs). El nombre corto es el que se usa en --metricas
# y el que acaba como columna en el CSV de resultados.
CATALOGO = {
    # ── Calidad de la generación ──
    "faithfulness":         (Faithfulness, {}),
    # strictness=1 y no el 3 por defecto: con 3, RAGAS pide tres candidatos en
    # una sola llamada (`n=3`) y Gemini responde
    # "Multiple candidates is not enabled for this model" (400). El síntoma es
    # traicionero: unas filas quedaban en NaN y otras se puntuaban con una sola
    # generación, así que la métrica salía calculada sobre una base distinta en
    # cada fila. Con 1 la llamada es válida y comparable en todas. Con el juez
    # de Blablador se mantiene: 3 candidatos triplicarían el coste en peticiones
    # contra un límite de pocas por minuto.
    "answer_relevancy":     (ResponseRelevancy, {"strictness": 1}),
    # ── Calidad de la recuperación ──
    "context_precision":    (LLMContextPrecisionWithReference, {}),
    "context_recall":       (LLMContextRecall, {}),
    # ── Acierto frente al ground truth ──
    # Las dos caras de la misma métrica, y hacen falta las dos. El ground truth
    # del banco son respuestas de una o dos frases, mientras que el RAG contesta
    # con explicaciones ~6 veces más largas. En modo f1, cada afirmación correcta
    # que el RAG añade de más cuenta como falso positivo y hunde la nota: mide
    # tanto la verbosidad como el acierto. En modo recall solo se pregunta si la
    # respuesta cubre lo que dice la referencia, que es lo que interesa saber.
    # Con `CorreccionFactual` y no con la de RAGAS: la de RAGAS no calcula esa
    # cobertura (ver `puntuacion_factual`).
    "factual_correctness":  (CorreccionFactual, {"mode": "f1"}),
    "factual_recall":       (CorreccionFactual, {"mode": "recall"}),
    "semantic_similarity":  (SemanticSimilarity, {}),   # sin coste de LLM
}

# Orden estable para columnas y gráficas.
ORDEN = list(CATALOGO)

# Etiquetas legibles para el informe.
ETIQUETAS = {
    "faithfulness":        "Fidelidad",
    "answer_relevancy":    "Relevancia",
    "context_precision":   "Precisión del contexto",
    "context_recall":      "Cobertura del contexto",
    "factual_correctness": "Corrección factual (F1)",
    "factual_recall":      "Cobertura factual",
    "semantic_similarity": "Similitud semántica",
}

DESCRIPCIONES = {
    "faithfulness":        "¿Cada afirmación de la respuesta se sostiene en el contexto recuperado? Detecta alucinación.",
    "answer_relevancy":    "¿La respuesta contesta realmente a la pregunta formulada?",
    "context_precision":   "¿Los fragmentos recuperados son relevantes y están bien ordenados? Evalúa el reranker.",
    "context_recall":      "¿El contexto contiene todo lo necesario para construir la respuesta de referencia?",
    "factual_correctness": "Media armónica de la precisión (afirmaciones de la respuesta que respalda el ground truth) y la cobertura factual. Penaliza responder de más.",
    "factual_recall":      "Qué parte de las afirmaciones del ground truth aparece en la respuesta. No penaliza responder de más.",
    "semantic_similarity": "Similitud coseno entre la respuesta y el ground truth (sin LLM).",
}


def construir(nombres: list[str] | None = None) -> list:
    """Instancia las métricas pedidas (todas, por defecto)."""
    nombres = nombres or ORDEN
    desconocidas = set(nombres) - set(CATALOGO)
    if desconocidas:
        raise ErrorConfiguracion(
            f"Métrica(s) desconocida(s): {', '.join(sorted(desconocidas))}.\n"
            f"Disponibles: {', '.join(ORDEN)}"
        )
    return [CATALOGO[n][0](**CATALOGO[n][1]) for n in nombres]


def usa_llm(metrica) -> bool:
    """¿La métrica tiene plantillas de prompt que traducir?"""
    return hasattr(metrica, "get_prompts") and bool(metrica.get_prompts())


def cargar_es(metricas: list, directorio) -> list[str]:
    """Inyecta las plantillas en español ya cacheadas. Devuelve las cargadas.

    Si faltan los ficheros de alguna métrica se avisa y esa métrica se queda en
    inglés, en lugar de reventar la corrida: es preferible puntuar con un aviso
    visible a no puntuar.
    """
    cargadas: list[str] = []
    for m in metricas:
        if not usa_llm(m):
            continue
        try:
            m.set_prompts(**m.load_prompts(str(directorio), language=IDIOMA))
            cargadas.append(m.name)
        except (ValueError, FileNotFoundError) as exc:
            print(f"   ! {m.name}: sin plantillas en español ({exc.__class__.__name__}), "
                  f"se usarán las originales en inglés. "
                  f"Ejecuta: python -m eval_ragas.adaptar_prompts")
    return cargadas
