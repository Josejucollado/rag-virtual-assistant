"""
estadistica.py — Los contrastes con los que se comparan las corridas.

Funciones puras sobre listas de números: no saben de corridas, de CSV ni de
HTML. Las usan la comparativa de dos corridas (`comparar.py`) y los informes de
la memoria (`eval_ragas/tfg/`), así que un mismo Δ se calcula siempre igual.

Por qué estos contrastes y no otros:

  - Pareados, porque todas las corridas responden a las MISMAS preguntas: cada
    pregunta es su propio control, y la varianza entre preguntas (las hay que
    puntúan 1,0 en cualquier configuración y otras 0 en todas) se cancela.
  - No paramétricos, porque las notas de RAGAS están acotadas en [0, 1], son muy
    poco normales y varias son casi discretas.
  - Con Holm sobre cada familia de métricas: con 7 métricas a 0,05, la
    probabilidad de que al menos una salga «significativa» por azar ronda el 30 %.
  - Con una banda de ruido: ni el generador ni el juez son deterministas, así
    que dos corridas idénticas tampoco dan las mismas notas.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd

# Por debajo de esta n el p de Wilcoxon se marca: el test existe, pero con tan
# pocos pares no distingue una diferencia real del ruido.
MIN_PARES_WILCOXON = 10

# Con menos pares la desviación típica del ruido es demasiado inestable para
# trazar una banda con ella.
MIN_PARES_RUIDO = 10

# 1,96: la banda es un intervalo al 95 % del Δ medio bajo la hipótesis de que
# no ha cambiado nada.
Z_BANDA = 1.96

# El cuantil exacto, para los intervalos de Wilson.
Z_95 = 1.959963984540054

# El remuestreo sólo describe la variación entre preguntas observadas; no estima
# la variabilidad adicional de ejecutar de nuevo modelos no deterministas.
N_REPLICAS_BOOTSTRAP = 10_000
SEMILLA_BOOTSTRAP = 20260929


def wilcoxon_pareado(x: list[float], y: list[float]) -> tuple[float | None, float | None]:
    """Estadístico y p del test de rangos con signo. `(None, None)` si no aplica.

    Pareado porque las dos corridas responden a las MISMAS preguntas con el mismo
    generador, el mismo juez y el mismo reranker: cada pregunta es su propio
    control. La varianza entre preguntas domina —hay preguntas que puntúan 1,0 en
    cualquier configuración y otras que puntúan 0 en todas—, y un test no pareado
    la trataría como ruido, tirando casi toda la potencia por la borda.

    No paramétrico porque las notas de RAGAS están acotadas en [0, 1], son muy
    poco normales y varias son casi discretas (un F1 sobre pocas afirmaciones
    atómicas toma pocos valores). Wilcoxon sólo pide simetría de las diferencias.
    """
    from scipy.stats import wilcoxon

    if not x:
        return None, None

    # Si no hay ni una diferencia, no hay nada que contrastar. Hay que mirarlo
    # antes de llamar a scipy: unas versiones lanzan ValueError y otras —1.18
    # entre ellas— siguen adelante, dividen 0//0 con un RuntimeWarning por el
    # camino y devuelven p = 1,0. Ese 1,0 sale de un cálculo inválido, así que
    # vale menos que decir «—».
    if all(va == vb for va, vb in zip(x, y)):
        return None, None

    try:
        # zsplit y no el "wilcox" por defecto: con "wilcox" los empates exactos
        # se descartan, y en métricas como context_recall —donde muchas preguntas
        # dan 1,0 en las dos corridas— la n efectiva se hundiría. zsplit los
        # conserva repartiendo sus rangos: es conservador y mantiene la n honesta.
        resultado = wilcoxon(x, y, zero_method="zsplit")
    except ValueError:
        # Cinturón y tirantes para las versiones de scipy que sí se quejan.
        return None, None
    return float(resultado.statistic), float(resultado.pvalue)


def holm(pes: list[float | None]) -> list[float | None]:
    """Corrección de Holm-Bonferroni, conservando el orden de entrada.

    Holm y no Bonferroni a secas porque es uniformemente más potente sin pedir
    nada a cambio: controla la misma tasa de error por familia y rechaza al menos
    lo mismo.
    """
    indices = [i for i, p in enumerate(pes) if p is not None]
    ajustados: list[float | None] = [None] * len(pes)
    if not indices:
        return ajustados

    m = len(indices)
    anterior = 0.0
    for rango, i in enumerate(sorted(indices, key=lambda j: pes[j])):
        # El max() impone la monotonía: un p ajustado nunca puede quedar por
        # debajo del de una métrica con un p crudo menor.
        anterior = max(min(1.0, (m - rango) * pes[i]), anterior)
        ajustados[i] = anterior
    return ajustados


def anotar_holm(filas: list[dict], *, clave_p: str = "p", destino: str = "p_holm") -> list[dict]:
    """Corrige con Holm los p de una familia de filas y lo anota en cada una."""
    for fila, ajustado in zip(filas, holm([f[clave_p] for f in filas])):
        fila[destino] = ajustado
    return filas


def banda_ruido(sd: float | None, n: int) -> float | None:
    """Semiancho de la banda al 95 % del Δ medio de n pares bajo ruido puro."""
    if sd is None or n <= 0:
        return None
    return Z_BANDA * sd / n ** 0.5


def bootstrap_ic_pareado(valores_a, valores_b, categorias=None, *,
                         replicas: int = N_REPLICAS_BOOTSTRAP,
                         semilla: int = SEMILLA_BOOTSTRAP) -> tuple[float, float] | None:
    """IC percentile del delta medio, remuestreando las mismas preguntas.

    Si se dan categorías, se remuestrea dentro de cada una y se conservan sus
    proporciones observadas. Así el IC no cambia por azar la mezcla 40/39/15 del
    banco.
    """
    a = np.asarray(valores_a, dtype=float)
    b = np.asarray(valores_b, dtype=float)
    if len(a) != len(b) or len(a) < 2:
        return None
    diferencias = b - a
    rng = np.random.default_rng(semilla)

    if categorias is None:
        grupos = [np.arange(len(diferencias))]
    else:
        etiquetas = np.asarray(categorias, dtype=object)
        if len(etiquetas) != len(diferencias):
            raise ValueError("Las categorías deben alinearse con los pares.")
        grupos = [np.flatnonzero(etiquetas == c) for c in pd.unique(etiquetas)]
        grupos = [grupo for grupo in grupos if len(grupo)]

    muestras = np.zeros(replicas, dtype=float)
    for grupo in grupos:
        indices = rng.integers(0, len(grupo), size=(replicas, len(grupo)))
        medias = diferencias[grupo][indices].mean(axis=1)
        muestras += medias * (len(grupo) / len(diferencias))

    inferior, superior = np.quantile(muestras, [0.025, 0.975])
    return float(inferior), float(superior)


def resumen_pareado(valores_a, valores_b, categorias=None, *, semilla=SEMILLA_BOOTSTRAP) -> dict:
    """Medias, Δ, mediana del Δ, % en que gana B, p de Wilcoxon e IC bootstrap."""
    a = np.asarray(valores_a, dtype=float)
    b = np.asarray(valores_b, dtype=float)
    if len(a) != len(b):
        raise ValueError("Las series deben contener los mismos pares.")
    n = len(a)
    if not n:
        return {"n": 0, "media_a": None, "media_b": None, "delta": None,
                "mediana_delta": None, "gana_b": None, "p": None, "ic": None}

    diferencias = b - a
    _, p = (wilcoxon_pareado(a.tolist(), b.tolist())
            if n >= MIN_PARES_WILCOXON else (None, None))
    return {
        "n": n,
        "media_a": float(a.mean()),
        "media_b": float(b.mean()),
        "delta": float(diferencias.mean()),
        "mediana_delta": float(np.median(diferencias)),
        "gana_b": float(np.mean(diferencias > 0)),
        "p": p,
        "ic": bootstrap_ic_pareado(a, b, categorias, semilla=semilla),
    }


def friedman_pareado(series: list[list[float] | np.ndarray]) -> tuple[float | None, float | None]:
    """Contraste ómnibus de tres o más configuraciones sobre los mismos IDs."""
    from scipy.stats import friedmanchisquare

    arrays = [np.asarray(s, dtype=float) for s in series]
    if len(arrays) < 3 or not arrays or len({len(a) for a in arrays}) != 1 or not len(arrays[0]):
        return None, None
    if all(np.array_equal(arrays[0], a) for a in arrays[1:]):
        return 0.0, 1.0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            resultado = friedmanchisquare(*arrays)
    except ValueError:
        return None, None
    if not math.isfinite(float(resultado.pvalue)):
        return None, None
    return float(resultado.statistic), float(resultado.pvalue)


def intervalo_wilson(aciertos: int, n: int, z: float = Z_95) -> tuple[float, float] | None:
    """IC Wilson para una proporción, más informativo que el porcentaje solo."""
    if n <= 0:
        return None
    p = aciertos / n
    denominador = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denominador
    radio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominador
    return max(0.0, centro - radio), min(1.0, centro + radio)
