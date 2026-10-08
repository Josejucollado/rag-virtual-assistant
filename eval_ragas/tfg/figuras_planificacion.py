"""figuras_planificacion.py — Diagrama de Gantt y curva de esfuerzo y coste del proyecto.

Genera las dos figuras de la sección «Planificación temporal y presupuesto»
(`thesis/imagenes/fig_gantt.pdf` y `thesis/imagenes/fig_esfuerzo.pdf`) a partir
de las fases y del presupuesto definidos aquí, que son los mismos que recogen
las tablas del capítulo. Si se cambia una fecha, unas horas o un coste, basta con
editarlo aquí, volver a ejecutar el script y actualizar la tabla con lo que
imprime.

    python -m eval_ragas.tfg.figuras_planificacion
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

SALIDA = Path(__file__).resolve().parents[2] / "thesis" / "imagenes"

INICIO, FIN = date(2026, 7, 1), date(2026, 9, 30)

# ── Fases: (nombre, bloque, inicio, fin, horas) ───────────────────────────────
FASES = (
    ("1. Estudio del estado del arte", "Estudio", date(2026, 7, 1), date(2026, 7, 19), 36),
    ("2. Requisitos y selección del corpus", "Estudio", date(2026, 7, 13), date(2026, 7, 26), 14),
    ("3. Prototipo inicial", "Desarrollo", date(2026, 7, 20), date(2026, 8, 7), 32),
    ("4. Cadena de datos", "Desarrollo", date(2026, 7, 27), date(2026, 8, 28), 48),
    ("5. Cadena RAG", "Desarrollo", date(2026, 8, 17), date(2026, 9, 6), 42),
    ("6. Banco de preguntas y evaluación", "Evaluación", date(2026, 8, 21), date(2026, 9, 6), 30),
    ("7. Interfaz de usuario", "Desarrollo", date(2026, 8, 31), date(2026, 9, 18), 28),
    ("8. Migración a Blablador", "Desarrollo", date(2026, 9, 7), date(2026, 9, 20), 22),
    ("9. Experimentos y comparativas", "Evaluación", date(2026, 9, 21), date(2026, 9, 30), 30),
    ("10. Redacción de la memoria", "Documentación", date(2026, 7, 1), date(2026, 9, 30), 38),
)

HITOS = (
    ("Prototipo funcional", date(2026, 8, 7)),
    ("Primera evaluación", date(2026, 8, 30)),
    ("Sistema en Blablador", date(2026, 9, 20)),
    ("Evaluación final", date(2026, 9, 30)),
)

# ── Presupuesto estimado ──────────────────────────────────────────────────────
TARIFA_DESARROLLO = 20.0     # €/h, coste para la empresa de un ingeniero junior
HORAS_TUTOR, TARIFA_TUTOR = 20, 40.0
AMORTIZACION_EQUIPO = 1000.0 / 48 * 3   # portátil de 1 000 €, 4 años, 3 meses
ELECTRICIDAD_INTERNET = 3 * 15.0
API_OPENAI = 0.80            # 0,87 $ del experimento con el generador de pago
INDIRECTOS = 0.10

# ── Estilo (el mismo que las figuras de resultados) ───────────────────────────
AZUL, NARANJA, AGUAMARINA, GRIS = "#2a78d6", "#eb6834", "#1baf7a", "#898781"
TINTA, TINTA_2, REJILLA, EJE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
COLOR_BLOQUE = {"Estudio": AZUL, "Desarrollo": NARANJA, "Evaluación": AGUAMARINA,
                "Documentación": GRIS}
MESES = {7: "jul", 8: "ago", 9: "sep", 10: "oct"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5,
    "axes.edgecolor": EJE, "axes.labelcolor": TINTA_2, "axes.linewidth": 0.8,
    "xtick.color": TINTA_2, "ytick.color": TINTA_2,
    "xtick.major.size": 0, "ytick.major.size": 0,
    "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "pdf.fonttype": 42,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
})


def euros(v: float, dec: int = 0) -> str:
    texto = f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")
    return f"{texto} €"


def fecha_corta(d) -> str:
    d = mdates.num2date(d) if not isinstance(d, date) else d
    return f"{d.day} {MESES[d.month]}"


def dias(inicio: date, fin: date):
    d = inicio
    while d <= fin:
        yield d
        d += timedelta(days=1)


def esfuerzo_diario() -> dict[date, float]:
    """Horas de desarrollo de cada día, repartiendo cada fase por igual."""
    horas: dict[date, float] = {d: 0.0 for d in dias(INICIO, FIN)}
    for _, _, ini, fin, h in FASES:
        n = (fin - ini).days + 1
        for d in dias(ini, fin):
            horas[d] += h / n
    return horas


def coste_diario(horas: dict[date, float]) -> dict[date, float]:
    """Coste de cada día, con indirectos: personal + parte proporcional del resto."""
    n = len(horas)
    fijo_diario = (HORAS_TUTOR * TARIFA_TUTOR + AMORTIZACION_EQUIPO + ELECTRICIDAD_INTERNET) / n
    coste = {d: (h * TARIFA_DESARROLLO + fijo_diario) for d, h in horas.items()}
    coste[FIN] += API_OPENAI  # el experimento de pago se hizo la última semana
    return {d: c * (1 + INDIRECTOS) for d, c in coste.items()}


def figura_gantt() -> Path:
    # Más estrecha que el texto: las etiquetas de las fases quedan fuera del área
    # de dibujo y `bbox="tight"` las suma después (resultado: ~16 cm).
    fig, ax = plt.subplots(figsize=(4.95, 3.5))
    ys = list(range(len(FASES)))[::-1]
    for y, (nombre, bloque, ini, fin, h) in zip(ys, FASES):
        ax.barh(y, (fin - ini).days + 1, left=mdates.date2num(ini), height=0.56,
                color=COLOR_BLOQUE[bloque], edgecolor="white", linewidth=1)
        ax.text(mdates.date2num(fin) + 1.5, y, f"{h} h", va="center", fontsize=7, color=TINTA_2)
    ax.set_yticks(ys, [f[0] for f in FASES], color=TINTA)
    y_hitos = -1.3
    # Etiquetas en dos alturas alternas: los dos últimos hitos están a diez días.
    for i, (nombre, d) in enumerate(HITOS):
        x = mdates.date2num(d)
        ax.axvline(x, color=EJE, linewidth=0.8, zorder=0)
        ax.scatter([x], [y_hitos], marker="D", s=26, color=TINTA, zorder=3)
        ax.text(x, y_hitos - 0.55 - 1.45 * (i % 2), f"{nombre}\n{fecha_corta(d)}",
                ha="center", va="top", fontsize=6.5, color=TINTA)
    ax.set_ylim(y_hitos - 3.0, len(FASES) - 0.4)
    inicio_eje = mdates.date2num(INICIO) - 2
    ax.set_xlim(inicio_eje, mdates.date2num(FIN) + 9)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fecha_corta(v)))
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.grid(axis="x", which="minor", color=REJILLA, linewidth=0.4)
    ax.grid(axis="y", visible=False)
    ax.text(inicio_eje + 0.5, y_hitos, "Hitos", va="center", fontsize=7.5, color=TINTA_2,
            fontweight="bold")
    manejadores = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COLOR_BLOQUE.values()]
    ax.legend(manejadores, list(COLOR_BLOQUE), loc="upper center", ncol=4,
              bbox_to_anchor=(0.45, 1.1), handlelength=1, columnspacing=1.6)
    ruta = SALIDA / "fig_gantt.pdf"
    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def figura_esfuerzo(horas: dict[date, float], coste: dict[date, float]) -> Path:
    # Semanas de lunes a domingo; la primera y la última son parciales.
    lunes = sorted({d - timedelta(days=d.weekday()) for d in horas})
    horas_semana = [sum(h for d, h in horas.items() if d - timedelta(days=d.weekday()) == lu)
                    for lu in lunes]
    acumulado, total = [], 0.0
    fechas = sorted(coste)
    for d in fechas:
        total += coste[d]
        acumulado.append(total)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.3, 3.6), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1.2], "hspace": 0.35})
    ax1.bar([mdates.date2num(lu) + 3.5 for lu in lunes], horas_semana, width=6,
            color=AZUL, edgecolor="white", linewidth=1)
    ax1.set_ylabel("Horas por semana")
    ax1.set_title("Esfuerzo semanal", fontsize=8.5, color=TINTA, loc="left")
    ax1.grid(axis="x", visible=False)

    ax2.plot([mdates.date2num(d) for d in fechas], acumulado, color=AZUL, linewidth=2)
    ax2.scatter([mdates.date2num(fechas[-1])], [acumulado[-1]], s=30, color=AZUL,
                edgecolor="white", linewidth=1.5, zorder=3)
    ax2.annotate(euros(acumulado[-1]), (mdates.date2num(fechas[-1]), acumulado[-1]),
                 textcoords="offset points", xytext=(-6, 4), ha="right", fontsize=7.5, color=TINTA)
    ax2.set_ylabel("Coste acumulado")
    ax2.set_title("Coste acumulado estimado", fontsize=8.5, color=TINTA, loc="left")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: euros(v)))
    ax2.set_ylim(0, acumulado[-1] * 1.15)
    ax2.grid(axis="x", visible=False)
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    ax2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fecha_corta(v)))
    ax2.set_xlim(mdates.date2num(INICIO) - 3, mdates.date2num(FIN) + 3)
    ruta = SALIDA / "fig_esfuerzo.pdf"
    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    horas = esfuerzo_diario()
    coste = coste_diario(horas)
    print("Escrita", figura_gantt())
    print("Escrita", figura_esfuerzo(horas, coste))

    # Para cotejar con las tablas del capítulo.
    total_h = sum(f[4] for f in FASES)
    personal = total_h * TARIFA_DESARROLLO + HORAS_TUTOR * TARIFA_TUTOR
    subtotal = personal + AMORTIZACION_EQUIPO + ELECTRICIDAD_INTERNET + API_OPENAI
    print(f"Horas de desarrollo: {total_h} h")
    print(f"Personal: {personal:.2f} €  Subtotal: {subtotal:.2f} €  "
          f"Indirectos: {subtotal * INDIRECTOS:.2f} €  Total: {subtotal * (1 + INDIRECTOS):.2f} €  "
          f"(personal = {personal / subtotal:.1%} del subtotal)")
    semanas = {}
    for d, h in horas.items():
        semanas.setdefault(d - timedelta(days=d.weekday()), 0.0)
        semanas[d - timedelta(days=d.weekday())] += h
    print("Horas por semana:", [round(v, 1) for _, v in sorted(semanas.items())])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
