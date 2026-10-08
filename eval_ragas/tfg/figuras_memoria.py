"""figuras_memoria.py — Las figuras de la memoria, a partir de las corridas ya hechas.

Dibuja en PDF vectorial (para LaTeX) las siete figuras del capítulo de
Resultados, en el orden en que aparecen: el ruido de la medida, la nota de cada
pregunta del sistema final, el reordenado frente a la latencia, el número de
fragmentos, los generadores por calidad del contexto, el desglose del coste del
generador de pago y el resumen de todas las comparaciones. No llama a ninguna
API: lee los entregables de `data/ragas/` y reutiliza la misma aritmética que
los informes HTML (`comparar`, `comparativa_recuperacion`,
`comparativa_generadores`), así que una cifra de una figura es exactamente la
del informe.

Las gráficas de los informes HTML no sirven tal cual: son SVG en línea que toman
los colores de variables CSS. Aquí se redibujan con la misma paleta categórica
(azul, naranja, aguamarina: validada con el validador de paletas, CVD ΔE ≥ 9,2
entre las tres), fondo blanco para imprimir y coma decimal.

    python -m eval_ragas.tfg.figuras_memoria
    python -m eval_ragas.tfg.figuras_memoria --salida thesis/imagenes
"""

from __future__ import annotations

import argparse
import re
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana: sólo se escriben ficheros
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

from eval_ragas.comparar import (  # noqa: E402
    alinear,
    cargar_corrida,
    contextos_identicos,
    ruido_de_referencia,
)
from eval_ragas.comun import (  # noqa: E402
    ERROR,
    PROJECT_DIR,
    RAGAS_DIR,
    leer_configuracion,
)
from eval_ragas.estadistica import banda_ruido  # noqa: E402
from eval_ragas.tfg import comparativa_generadores as CG  # noqa: E402
from eval_ragas.tfg.catalogo import CORRIDA_REFERENCIA, CORRIDAS_TFG  # noqa: E402
from eval_ragas.tfg.comparativa_recuperacion import (  # noqa: E402
    _analisis_binario,
    construir_datos_k,
    filas_validas_k,
)
from rag import precio_modelo  # noqa: E402

warnings.filterwarnings("ignore")

SALIDA_PREDETERMINADA = PROJECT_DIR / "thesis" / "imagenes"

REFERENCIA = CORRIDA_REFERENCIA   # la configuración de referencia del capítulo

# ── Estilo ────────────────────────────────────────────────────────────────────
# Paleta de referencia: los tres primeros huecos categóricos, los únicos que
# pasan el validador comparando todos los pares entre sí. La aguamarina queda
# por debajo de 3:1 de contraste, así que toda serie lleva etiqueta visible.
AZUL, NARANJA, AGUAMARINA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA_2, TENUE = "#0b0b0b", "#52514e", "#898781"
REJILLA, EJE, BANDA = "#e1e0d9", "#c3c2b7", "#f0efec"

# El color sigue a la entidad, no al orden: GPT-OSS es la referencia en todas
# las figuras y siempre es azul.
COLOR_GENERADOR = {"GPT-OSS-120B": AZUL, "GPT-5.1": NARANJA, "Apertus-8B": AGUAMARINA}

ANCHO_TEXTO_IN = 6.3   # \textwidth con A4 y márgenes de 2,5 cm

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.edgecolor": EJE,
    "axes.labelcolor": TINTA_2,
    "axes.linewidth": 0.8,
    "xtick.color": TINTA_2,
    "ytick.color": TINTA_2,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "axes.grid": True,
    "grid.color": REJILLA,
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})


def coma(v: float, dec: int = 2) -> str:
    """Número con coma decimal, como el resto de la memoria."""
    if round(v, dec) == 0:
        v = 0.0   # sin «−0,0» en un eje que pasa por el cero
    return f"{v:.{dec}f}".replace(".", ",").replace("-", "−")


def coma_signo(v: float, dec: int = 3) -> str:
    return (f"{v:+.{dec}f}").replace(".", ",").replace("-", "−")


def formato_coma(dec: int = 2) -> FuncFormatter:
    return FuncFormatter(lambda v, _: coma(v, dec))


def miles(v: float) -> str:
    """Entero con espacio de millares: 2 503."""
    return f"{v:,.0f}".replace(",", " ")


def banda_f1(n: int) -> float:
    """La banda de ruido de la F1 media sobre n preguntas, la de los informes."""
    _, ruido = ruido_de_referencia(["factual_correctness"])
    return banda_ruido(ruido["factual_correctness"]["sd"], n)


def guardar(fig, salida: Path, nombre: str) -> Path:
    ruta = salida / nombre
    fig.savefig(ruta)
    plt.close(fig)
    return ruta


# ── Figura 1: el ruido, medido donde nada cambió ──────────────────────────────
def figura_ruido(salida: Path) -> Path:
    """Nota de cada pregunta en una evaluación frente a la otra, con el mismo contexto.

    Antes era un histograma de las diferencias, que obligaba a leer «cambio de
    nota» en abscisas. Así se ve directamente: si la medida fuera repetible, todos
    los puntos estarían sobre la diagonal. Al lado, la media de cada evaluación:
    las notas sueltas se mueven mucho, las medias casi nada.
    """
    par, _, _ = alinear(cargar_corrida(REFERENCIA), cargar_corrida("libre_conciso_stemming"))
    util = par[(par["resultado_a"] != ERROR) & (par["resultado_b"] != ERROR)]
    util = util[contextos_identicos(util)]
    util = util.dropna(subset=["factual_correctness_a", "factual_correctness_b"])
    a = util["factual_correctness_a"].to_numpy()
    b = util["factual_correctness_b"].to_numpy()
    sd = float(np.std(b - a, ddof=1))
    una = 1.96 * sd

    fig, (ax, axm) = plt.subplots(1, 2, figsize=(ANCHO_TEXTO_IN * 0.86, 3.0), sharey=True,
                                  gridspec_kw={"width_ratios": [3.2, 1], "wspace": 0.08})

    # Margen de una pregunta suelta alrededor de la diagonal.
    x = np.array([0, 1])
    ax.fill_between(x, x - una, x + una, color=BANDA, zorder=0)
    ax.plot(x, x, color=EJE, linewidth=1, zorder=1)

    # Las notas son fracciones (1/3, 2/3…) y muchas coinciden: un círculo por
    # pareja de notas, con el área proporcional a cuántas preguntas caen en ella.
    parejas: dict[tuple[float, float], int] = {}
    for va, vb in zip(a.round(3), b.round(3)):
        parejas[(va, vb)] = parejas.get((va, vb), 0) + 1
    for (va, vb), n in parejas.items():
        igual = abs(va - vb) < 1e-9
        ax.scatter([va], [vb], s=22 * n, color=TENUE if igual else AZUL, alpha=0.85,
                   edgecolor="white", linewidth=0.8, zorder=3 if igual else 2)
    iguales = int((np.abs(a - b) < 1e-9).sum())
    ax.scatter([], [], s=30, color=TENUE, label=f"misma nota ({iguales})")
    ax.scatter([], [], s=30, color=AZUL, label=f"nota distinta ({len(a) - iguales})")
    ax.plot([], [], color=EJE, linewidth=1, label="diagonal: misma nota")
    ax.fill_between([], [], [], color="#e2e0da", label=f"azar de una pregunta: ±{coma(una, 2)}")
    # Debajo de la figura: dentro tapaba puntos de la esquina superior.
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(0.5, 0.0),
               ncol=2, handlelength=1.2, fontsize=7, columnspacing=1.5)
    ax.set_xlim(-0.04, 1.04)
    ax.set_ylim(-0.04, 1.04)
    ax.set_aspect("equal", adjustable="box")
    ax.xaxis.set_major_formatter(formato_coma(1))
    ax.yaxis.set_major_formatter(formato_coma(1))
    ax.set_xlabel("Nota en la primera evaluación")
    ax.set_ylabel("Nota en la segunda evaluación")
    ax.set_title("Cada pregunta", fontsize=8.5, color=TINTA, loc="left")

    # La media de las mismas preguntas en cada evaluación.
    medias = (float(a.mean()), float(b.mean()))
    # El mismo azar, pero de la media de estas preguntas: unas diez veces menor.
    banda = banda_ruido(sd, len(a))
    axm.axhspan(medias[0] - banda, medias[0] + banda, color=BANDA, zorder=0)
    axm.text(0.5, medias[0] - banda - 0.03, f"±{coma(banda, 3)}\n(azar)", ha="center",
             va="top", fontsize=6.8, color=TINTA_2)
    axm.plot([0, 1], medias, color=AZUL, linewidth=1.5, zorder=2)
    axm.scatter([0, 1], medias, s=40, color=AZUL, edgecolor="white", linewidth=1.5, zorder=3)
    for xm, m in zip((0, 1), medias):
        axm.text(xm, m + 0.05, coma(m, 3), ha="center", fontsize=7, color=TINTA)
    axm.set_xticks([0, 1], ["1.ª", "2.ª"])
    axm.set_xlim(-0.5, 1.5)
    axm.grid(axis="x", visible=False)
    axm.set_xlabel("Evaluación")
    axm.set_title(f"La media ({len(a)})", fontsize=8.5, color=TINTA, loc="left")
    return guardar(fig, salida, "fig_ruido.pdf")


# ── Figura 2: la nota de cada pregunta del sistema final ──────────────────────
def figura_distribucion(salida: Path) -> Path:
    """F1 de cada pregunta del sistema final, según si el contexto estaba completo.

    Lo que la media no enseña: si 0,62 son preguntas todas regulares o una mezcla
    de aciertos y fallos, y en qué grupo caen los fallos. El umbral de «contexto
    completo» es el de la comparativa de generadores.
    """
    d = cargar_corrida(REFERENCIA)
    d = d[d["resultado"] != ERROR]
    completo = d["context_recall"] >= CG.UMBRAL_CONTEXTO_COMPLETO
    bordes = np.linspace(0, 1, 11)   # np.histogram cierra la última: [0,9, 1] incluye el 1

    fig, ax = plt.subplots(figsize=(ANCHO_TEXTO_IN * 0.8, 2.6))
    base = np.zeros(len(bordes) - 1)
    medias = []
    for etiqueta, mascara, color in (("Contexto completo", completo, AZUL),
                                     ("Contexto parcial", ~completo, NARANJA)):
        f1 = d.loc[mascara, "factual_correctness"].dropna()
        h, _ = np.histogram(f1, bins=bordes)
        ax.bar(bordes[:-1], h, width=0.1, bottom=base, align="edge", color=color,
               edgecolor="white", linewidth=1, label=f"{etiqueta} ({len(f1)} preguntas)")
        base += h
        medias.append((float(f1.mean()), color))

    # La media de cada grupo, como marca encima de las barras: una línea vertical
    # del color del grupo desaparecía al cruzar las barras de ese mismo color.
    tope = float(base.max())
    for m, color in medias:
        ax.scatter([m], [tope + 1.1], marker="v", s=42, color=color, edgecolor="white",
                   linewidth=1, zorder=4)
        ax.text(m, tope + 1.9, f"media {coma(m)}", ha="center", va="bottom", fontsize=7,
                color=TINTA)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, tope + 4.5)
    ax.set_xticks(np.linspace(0, 1, 6))
    ax.xaxis.set_major_formatter(formato_coma(1))
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))
    ax.yaxis.set_major_formatter(formato_coma(0))
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("Corrección factual (F1) de cada pregunta")
    ax.set_ylabel("Preguntas")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handlelength=1,
              columnspacing=1.6)
    return guardar(fig, salida, "fig_distribucion.pdf")


# ── Figura 3: el precio del reordenado ────────────────────────────────────────
def figura_reordenado(salida: Path) -> Path:
    """F1 frente a latencia mediana: sin reordenado, mMiniLM y bge.

    La franja es la banda de ruido centrada en la configuración elegida: un
    punto dentro de ella no se distingue de relanzar la elegida.
    """
    import pandas as pd

    # (etiqueta, corrida, desplazamiento de la etiqueta en puntos)
    puntos = (("Sin reordenado", "libre_sin_reranker", (0, 10)),
              ("mmarco-mMiniLMv2 (elegido)", REFERENCIA, (0, -24)),
              ("bge-reranker-v2-m3", "libre_conciso_bge", (0, 10)))
    referencia = cargar_corrida(REFERENCIA)
    f1_ref = float(referencia["factual_correctness"].mean())
    banda = banda_f1(len(referencia))

    fig, ax = plt.subplots(figsize=(ANCHO_TEXTO_IN * 0.66, 2.5))
    ax.axhspan(f1_ref - banda, f1_ref + banda, color=BANDA, zorder=0)
    ax.text(75, f1_ref - banda + 0.002, f"banda de ruido (±{coma(banda, 3)})", ha="right",
            va="bottom", fontsize=6.5, color=TINTA_2)
    for etiqueta, corrida, desp in puntos:
        resp = pd.read_csv(RAGAS_DIR / corrida / "respuestas_rag.csv")
        lat = float(pd.to_numeric(resp.loc[resp["resultado"] != ERROR, "latencia_s"]).median())
        f1 = float(cargar_corrida(corrida)["factual_correctness"].mean())
        ax.scatter([lat], [f1], s=46, color=AZUL, edgecolor="white", linewidth=1.5, zorder=3)
        ax.annotate(f"{etiqueta}\n{coma(lat, 1)} s · F1 {coma(f1, 3)}", (lat, f1),
                    textcoords="offset points", xytext=desp, ha="center", fontsize=7,
                    color=TINTA)
    ax.text(1.6, 0.717, "↖ mejor y más rápido", ha="left", va="top", fontsize=7, color=TENUE)
    ax.set_xscale("log")
    ax.set_xticks([2, 5, 10, 20, 50], ["2", "5", "10", "20", "50"])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlim(1.5, 80)
    ax.set_ylim(0.56, 0.72)
    ax.yaxis.set_major_formatter(formato_coma(2))
    ax.set_xlabel("Tiempo de respuesta, mediana (s, escala logarítmica, CPU)")
    ax.set_ylabel("Corrección factual (F1)")
    return guardar(fig, salida, "fig_reordenado.pdf")


# ── Figura 4: número de chunks ────────────────────────────────────────────────
def figura_k(salida: Path) -> Path:
    """Precisión y cobertura del contexto y F1 frente a K = 3, 5, 8."""
    datos = construir_datos_k()
    ks = (3, 5, 8)
    # (etiqueta, métrica, color, desplazamiento vertical del valor en puntos)
    series = (
        ("Cobertura del contexto", "context_recall", AZUL, 6),
        ("Precisión del contexto", "context_precision", NARANJA, -12),
        ("Corrección factual (F1)", "factual_correctness", AGUAMARINA, 6),
    )
    fig, ax = plt.subplots(figsize=(ANCHO_TEXTO_IN * 0.62, 2.6))
    for etiqueta, metrica, color, dy in series:
        v = filas_validas_k(datos, metrica)
        medias = [float(v[f"{metrica}_K={k}"].mean()) for k in ks]
        ax.plot(ks, medias, color=color, linewidth=2, marker="o", markersize=5,
                markeredgecolor="white", markeredgewidth=1.5)
        for k, m in zip(ks, medias):
            ax.annotate(coma(m, 3), (k, m), textcoords="offset points", xytext=(0, dy),
                        ha="center", fontsize=6.5, color=TINTA_2)
        ax.text(8.45, medias[-1], etiqueta, va="center", color=TINTA, fontsize=7.5)
    ax.set_xticks(ks, [f"K = {k}" for k in ks])
    ax.set_xlim(2.4, 8.4)
    ax.set_ylim(0.55, 0.95)
    ax.yaxis.set_major_formatter(formato_coma(2))
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("Chunks que llegan al generador")
    ax.set_ylabel("Media sobre 94 preguntas")
    return guardar(fig, salida, "fig_k.pdf")


# ── Figura 5: generadores, por calidad del contexto ───────────────────────────
def figura_generadores(salida: Path) -> Path:
    """F1 y fidelidad de cada generador con el contexto completo y parcial."""
    concursantes, _ = CG.presentes()
    nombres = [c.nombre for c in concursantes]
    # Orden de las barras: referencia primero, luego el de pago y el pequeño.
    orden = [n for n in ("GPT-OSS-120B", "GPT-5.1", "Apertus-8B") if n in nombres]
    estratos = CG.estratos_contexto(CG.tabla_ancha(concursantes), nombres)
    grupos = ("Contexto completo", "Contexto parcial")
    n_grupo = {g: next(e["n"] for e in estratos if e["estrato"] == g and e["generador"] == "GPT-OSS-120B")
               for g in grupos}

    fig, ejes = plt.subplots(1, 2, figsize=(ANCHO_TEXTO_IN, 2.6), sharey=True)
    ancho = 0.26
    for ax, (metrica, titulo) in zip(ejes, (("factual_correctness", "Corrección factual (F1)"),
                                             ("faithfulness", "Fidelidad"))):
        for j, gen in enumerate(orden):
            valores = [next(e[metrica] for e in estratos
                            if e["estrato"] == g and e["generador"] == gen) for g in grupos]
            xs = np.arange(len(grupos)) + (j - (len(orden) - 1) / 2) * (ancho + 0.02)
            ax.bar(xs, valores, width=ancho, color=COLOR_GENERADOR[gen], label=gen,
                   edgecolor="white", linewidth=1)
            for x, v in zip(xs, valores):
                ax.text(x, v + 0.015, coma(v), ha="center", va="bottom", fontsize=6.5, color=TINTA)
        ax.set_xticks(range(len(grupos)), [f"{g}\n({n_grupo[g]} preguntas)" for g in grupos],
                      color=TINTA)
        ax.set_title(titulo, fontsize=8.5, color=TINTA, loc="left")
        ax.set_ylim(0, 1.08)
        ax.yaxis.set_major_formatter(formato_coma(1))
        ax.grid(axis="x", visible=False)
    ejes[0].legend(loc="upper center", bbox_to_anchor=(1.05, -0.2), ncol=len(orden),
                   handlelength=1, columnspacing=1.6)
    return guardar(fig, salida, "fig_generadores.pdf")


# ── Figura 6: en qué se va el dinero del generador de pago ────────────────────
def figura_coste(salida: Path) -> Path:
    """Tokens y coste de una respuesta media de GPT-5.1, por partes.

    La entrada (instrucciones, pregunta y fragmentos) es casi todo el volumen; la
    salida es 8 veces más cara por token y aun así no llega a la mitad del coste.
    Precios de `PRECIOS_USD_MTOK`, los mismos que usa el tope de gasto; el total
    coincide con la media de `coste_usd` de `consumo.csv`.
    """
    corrida = "pago_gpt51"
    consumo = CG.leer_consumo(corrida)
    encontrado = re.search(r"openai/(\S+)", leer_configuracion(RAGAS_DIR / corrida) or "")
    p_entrada, p_cache, p_salida = precio_modelo(encontrado.group(1) if encontrado else "gpt-5.1")
    n = len(consumo)
    entrada = consumo["tokens_entrada"].sum() / n
    cache = consumo["tokens_entrada_cache"].sum() / n
    razonamiento = consumo["tokens_razonamiento"].sum() / n
    visible = consumo["tokens_salida"].sum() / n - razonamiento
    partes = (
        ("Entrada: instrucciones,\npregunta y 5 chunks", entrada,
         ((entrada - cache) * p_entrada + cache * p_cache) / 1e6),
        ("Razonamiento oculto", razonamiento, razonamiento * p_salida / 1e6),
        ("Respuesta visible", visible, visible * p_salida / 1e6),
    )
    total_tokens = sum(p[1] for p in partes)
    total_coste = sum(p[2] for p in partes)

    fig, ejes = plt.subplots(1, 2, figsize=(ANCHO_TEXTO_IN * 0.92, 1.75), sharey=True)
    ys = np.arange(len(partes))[::-1]
    paneles = (
        (f"Tokens por respuesta (media: {miles(total_tokens)})",
         [p[1] for p in partes], lambda v: f"{miles(v)} tokens", total_tokens),
        (f"Coste por respuesta (media: {coma(total_coste, 4)} $)",
         [p[2] for p in partes], lambda v: f"{coma(v, 4)} $", total_coste),
    )
    for ax, (titulo, valores, rotulo, total) in zip(ejes, paneles):
        for y, v in zip(ys, valores):
            pct = 100 * v / total
            ax.barh(y, pct, height=0.6, color=AZUL, edgecolor="white", linewidth=1)
            texto = f"{rotulo(v)} · {pct:.0f} %"
            if pct > 60:   # dentro de la barra, en blanco: fuera no cabría
                ax.text(pct - 2, y, texto, va="center", ha="right", fontsize=7, color="white")
            else:
                ax.text(pct + 2, y, texto, va="center", ha="left", fontsize=7, color=TINTA)
        ax.set_title(titulo, fontsize=8, color=TINTA, loc="left")
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 50, 100], ["0 %", "50 %", "100 %"])
        ax.grid(axis="y", visible=False)
    ejes[0].set_yticks(ys, [p[0] for p in partes], color=TINTA)
    fig.subplots_adjust(wspace=0.22)
    return guardar(fig, salida, "fig_coste.pdf")


# ── Figura 7: todas las comparaciones frente a la referencia ──────────────────
# (etiqueta, corrida, grupo). Cada una cambia UNA cosa respecto a la referencia;
# salen del catálogo `CORRIDAS_TFG` de `tfg/catalogo.py`.
ABLACIONES = tuple((etiqueta, corrida, grupo) for corrida, grupo, etiqueta in CORRIDAS_TFG
                   if corrida != REFERENCIA)


def figura_ablaciones(salida: Path) -> Path:
    """ΔF1 de cada variante frente a libre_conciso, con IC, banda de ruido y p de Holm.

    El p es el del informe de la comparativa: Wilcoxon con Holm entre las 7
    métricas del par. Va al lado del Δ porque el criterio del capítulo pide las
    dos cosas a la vez: salir de la banda y p < 0,05.
    """
    filas = []
    for etiqueta, corrida, grupo in ABLACIONES:
        if not (RAGAS_DIR / corrida / "resultados_ragas.csv").exists():
            continue
        comp = _analisis_binario(etiqueta, "referencia", REFERENCIA, etiqueta, corrida)
        f1 = next(f for f in comp["filas"] if f["metrica"] == "factual_correctness")
        filas.append((etiqueta, grupo, f1["delta"], f1["ic"], f1["p_holm"], f1["n"]))
    banda = banda_f1(max(f[5] for f in filas))

    # Más estrecha que el texto: las etiquetas de la izquierda y las columnas de
    # la derecha quedan fuera del área de dibujo y `bbox="tight"` las suma.
    fig, ax = plt.subplots(figsize=(ANCHO_TEXTO_IN - 2.4, 0.36 * len(filas) + 1.1))
    ax.axvspan(-banda, banda, color=BANDA, zorder=0)
    ax.axvline(0, color=EJE, linewidth=0.9, zorder=1)
    ys = np.arange(len(filas))[::-1]
    columnas = blended_transform_factory(ax.transAxes, ax.transData)
    for y, (etiqueta, grupo, delta, ic, p, _) in zip(ys, filas):
        ax.plot(ic, [y, y], color=AZUL, linewidth=1.6, solid_capstyle="round", zorder=2)
        ax.scatter([delta], [y], s=34, color=AZUL, edgecolor="white", linewidth=1.5, zorder=3)
        ax.text(1.17, y, coma_signo(delta), transform=columnas, va="center", ha="right",
                color=TINTA, fontsize=8)
        ax.text(1.40, y, coma(p, 3) if p < 0.995 else "1", transform=columnas, va="center",
                ha="right", color=TINTA, fontsize=8, fontweight="bold" if p < 0.05 else "normal")
    ax.set_yticks(ys, [f[0] for f in filas], color=TINTA)
    x_min, x_max = -0.22, 0.13
    # Separador entre los dos grupos, con su rótulo.
    corte = sum(1 for f in filas if f[1] == "Generación")
    ax.axhline(ys[corte - 1] - 0.62, color=EJE, linewidth=0.8)
    for grupo, y in (("Generación", ys[0] + 0.42), ("Recuperación", ys[corte] + 0.42)):
        ax.text(x_min + 0.005, y, grupo.upper(), fontsize=6.5, color=TENUE, va="bottom",
                ha="left", fontweight="bold")
    y_cabecera = ys[0] + 0.95
    ax.text(0, y_cabecera, f"banda de ruido ±{coma(banda, 3)}", color=TINTA_2, fontsize=7,
            va="top", ha="center")
    for x, texto in ((1.17, "Δ"), (1.40, "p (Holm)")):
        ax.text(x, y_cabecera, texto, transform=columnas, va="top", ha="right",
                color=TINTA_2, fontsize=7.5)
    # Hacia dónde es mejor, para no tener que deducirlo del signo.
    y_pie = ys[-1] - 0.95
    ax.text(x_min + 0.005, y_pie, "← empeora", fontsize=7, color=TENUE, va="center", ha="left")
    ax.text(x_max - 0.005, y_pie, "mejora →", fontsize=7, color=TENUE, va="center", ha="right")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(ys[-1] - 1.3, ys[0] + 1.0)
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(formato_coma(2))
    ax.set_xlabel("Δ corrección factual (F1) frente a la configuración de referencia")
    return guardar(fig, salida, "fig_ablaciones.pdf")


FIGURAS = (figura_ruido, figura_distribucion, figura_reordenado, figura_k,
           figura_generadores, figura_coste, figura_ablaciones)


def main() -> int:
    ap = argparse.ArgumentParser(description="Figuras de la memoria, sin llamar a ninguna API.")
    ap.add_argument("--salida", type=Path, default=SALIDA_PREDETERMINADA,
                    help="directorio donde escribir los PDF")
    args = ap.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    for figura in FIGURAS:
        print(f"Escrita {figura(args.salida)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
