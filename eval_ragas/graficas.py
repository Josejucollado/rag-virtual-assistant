"""
graficas.py — Generadores de SVG en línea para el informe.

Todo se dibuja como SVG incrustado, sin librerías externas: el informe tiene que
poder abrirse desde el disco y publicarse como Artifact sin depender de ninguna
CDN.

La paleta es la de referencia del sistema de diseño. Se usan solo los tres
primeros slots categóricos —el subconjunto documentado como válido para gráficas
de todos-contra-todos, como la dispersión— y la paleta de estado, que es fija,
para OK / RECHAZO / ERROR y, en `barras_divergentes`, para mejora / regresión:
también es un estado, no una categoría. No se inventan colores nuevos.
"""

from __future__ import annotations

import math
from html import escape

# ── Paleta (roles, no hex sueltos) ────────────────────────────────────────────
SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"]
ESTADO_COLOR = {
    "OK":      "var(--status-good)",
    "RECHAZO": "var(--status-critical)",
    "ERROR":   "var(--status-warning)",
}
# El color de estado nunca va solo: siempre acompañado de icono y etiqueta.
ESTADO_ICONO = {"OK": "●", "RECHAZO": "▲", "ERROR": "■"}


# Estos tres formateadores son públicos porque `informe.py` los comparte: antes
# cada módulo tenía su copia y se desviaban en los detalles (una toleraba NaN y
# la otra no). Todos usan coma decimal, como manda el español.
def esc(t) -> str:
    """Texto listo para incrustar en HTML o en un atributo."""
    return escape(str(t), quote=True)


def _es_nulo(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def fmt(v, dec: int = 3) -> str:
    """Número con `dec` decimales, o una raya si no hay valor."""
    if _es_nulo(v):
        return "—"
    return f"{v:.{dec}f}".replace(".", ",")


def fmt_signo(v, dec: int = 3) -> str:
    """Número con el signo SIEMPRE explícito, o una raya si no hay valor.

    Los deltas entre dos corridas se leen mal sin el `+`: un «0,012» y un
    «-0,012» se distinguen por un carácter fácil de pasar por alto, y en una
    tabla de siete filas eso basta para leer al revés el resultado.
    """
    if _es_nulo(v):
        return "—"
    return f"{v:+.{dec}f}".replace(".", ",")


def pct(v, dec: int = 1) -> str:
    """Porcentaje con espacio antes del signo, o una raya si no hay valor."""
    if _es_nulo(v):
        return "—"
    return f"{v * 100:.{dec}f}".replace(".", ",") + " %"


def fmt_p(valor) -> str:
    """Un p con tres decimales, «<0,001» si es menor, o una raya si no hay."""
    if valor is None or not math.isfinite(float(valor)):
        return "—"
    if valor < 0.001:
        return "<0,001"
    return fmt(valor, 3)


def fmt_ic(ic) -> str:
    """Un intervalo [inferior, superior], o una raya si no hay."""
    if ic is None:
        return "—"
    return f"[{fmt(ic[0])}, {fmt(ic[1])}]"


def barras_horizontales(datos, *, ancho=680, alto_barra=34, max_val=1.0,
                        color=SERIES[0]) -> str:
    """Magnitud de una sola serie: una barra por categoría, todas del mismo color.

    Un degradado por valor doblaría el encoding (la longitud ya dice el tamaño)
    y gastaría el único canal libre, así que todas las barras van en el slot 1.
    """
    m_izq, m_der, m_sup = 190, 62, 8
    alto = m_sup + len(datos) * alto_barra + 8
    ancho_plot = ancho - m_izq - m_der

    partes = [
        f'<svg viewBox="0 0 {ancho} {alto}" role="img" class="grafica" '
        f'preserveAspectRatio="xMinYMin meet">'
    ]

    # Rejilla: líneas finas, sólidas, un tono por encima de la superficie.
    for frac in (0.25, 0.5, 0.75, 1.0):
        x = m_izq + ancho_plot * frac
        partes.append(
            f'<line x1="{x:.1f}" y1="{m_sup}" x2="{x:.1f}" y2="{alto - 8}" '
            f'stroke="var(--grid)" stroke-width="1"/>'
        )
        partes.append(
            f'<text x="{x:.1f}" y="{alto - 0}" text-anchor="middle" '
            f'class="tick">{fmt(frac, 2)}</text>'
        )

    for i, (etiqueta, valor, sub) in enumerate(datos):
        y = m_sup + i * alto_barra
        alto_m = alto_barra - 10       # marca fina, con aire entre barras
        v = 0.0 if valor is None or (isinstance(valor, float) and math.isnan(valor)) else valor
        w = max(0.0, min(v / max_val, 1.0)) * ancho_plot

        partes.append(
            f'<text x="{m_izq - 12}" y="{y + alto_m / 2 + 4}" text-anchor="end" '
            f'class="etiqueta-eje">{esc(etiqueta)}</text>'
        )
        partes.append(
            f'<rect x="{m_izq}" y="{y}" width="{ancho_plot}" height="{alto_m}" '
            f'rx="4" fill="var(--track)"/>'
        )
        if w > 0:
            partes.append(
                f'<rect x="{m_izq}" y="{y}" width="{w:.1f}" height="{alto_m}" '
                f'rx="4" fill="{color}"><title>{esc(etiqueta)}: {fmt(valor)}'
                f'{" · " + esc(sub) if sub else ""}</title></rect>'
            )
        # Etiqueta directa fuera de la barra: nunca recortada por una barra corta.
        partes.append(
            f'<text x="{m_izq + ancho_plot + 8}" y="{y + alto_m / 2 + 4}" '
            f'class="valor">{fmt(valor)}</text>'
        )

    partes.append("</svg>")
    return "".join(partes)


def barras_divergentes(datos, *, ancho=680, alto_barra=34, max_abs=None,
                       color_pos="var(--status-good)",
                       color_neg="var(--status-critical)") -> str:
    """Magnitudes CON SIGNO, desde un cero central. `datos` = [(etiqueta, valor, sub)].

    Hace falta una función aparte porque `barras_horizontales` y
    `barras_agrupadas` recortan con `max(0.0, min(v / max_val, 1.0))`: no pueden
    dibujar un valor negativo. La entrada tiene la misma forma que la de
    `barras_horizontales` para que sean intercambiables.

    `max_abs=None` toma el mayor valor absoluto y lo redondea hacia arriba, en
    vez de fijar la escala en 1,0: los deltas entre dos corridas son del orden de
    centésimas y con la escala de las notas no se vería ninguno.

    Usa la paleta de estado y no la categórica, a propósito: un delta positivo es
    una mejora y uno negativo una regresión, y eso es una codificación de estado,
    no de categoría. Y como el color nunca va solo, cada barra lleva al lado su
    valor con el signo explícito.
    """
    m_izq, m_der, m_sup = 190, 72, 8
    alto = m_sup + len(datos) * alto_barra + 20
    ancho_plot = ancho - m_izq - m_der
    centro = m_izq + ancho_plot / 2

    if max_abs is None:
        vistos = [abs(v) for _, v, _ in datos if not _es_nulo(v)]
        # El techo mínimo evita que una corrida idéntica a otra dibuje barras
        # enormes a partir de ruido de la cuarta cifra decimal.
        max_abs = max([*vistos, 0.01])
        max_abs = math.ceil(max_abs * 100) / 100

    partes = [
        f'<svg viewBox="0 0 {ancho} {alto}" role="img" class="grafica" '
        f'preserveAspectRatio="xMinYMin meet">'
    ]

    # Rejilla simétrica: los mismos cortes a un lado y al otro del cero.
    for frac in (-1.0, -0.5, 0.5, 1.0):
        x = centro + (ancho_plot / 2) * frac
        partes.append(
            f'<line x1="{x:.1f}" y1="{m_sup}" x2="{x:.1f}" y2="{alto - 20}" '
            f'stroke="var(--grid)" stroke-width="1"/>'
        )
        partes.append(
            f'<text x="{x:.1f}" y="{alto - 6}" text-anchor="middle" '
            f'class="tick">{fmt_signo(frac * max_abs, 2)}</text>'
        )

    for i, (etiqueta, valor, sub) in enumerate(datos):
        y = m_sup + i * alto_barra
        alto_m = alto_barra - 10
        partes.append(
            f'<text x="{m_izq - 12}" y="{y + alto_m / 2 + 4}" text-anchor="end" '
            f'class="etiqueta-eje">{esc(etiqueta)}</text>'
        )
        if _es_nulo(valor):
            continue
        # Se recorta al techo para que un valor atípico no se salga del lienzo.
        frac = max(-1.0, min(valor / max_abs, 1.0))
        w = abs(frac) * (ancho_plot / 2)
        x = centro if frac >= 0 else centro - w
        partes.append(
            f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{alto_m}" rx="3" '
            f'fill="{color_pos if frac >= 0 else color_neg}">'
            f'<title>{esc(etiqueta)}: {fmt_signo(valor)}'
            f'{" · " + esc(sub) if sub else ""}</title></rect>'
        )

    # El cero va después de las barras para que quede por encima de ellas.
    partes.append(
        f'<line x1="{centro:.1f}" y1="{m_sup}" x2="{centro:.1f}" '
        f'y2="{alto - 20}" stroke="var(--axis)" stroke-width="1.5"/>'
    )

    # Etiqueta directa a la derecha, fuera del área de barras: igual que en
    # `barras_horizontales`, nunca la recorta una barra corta.
    for i, (_, valor, _) in enumerate(datos):
        y = m_sup + i * alto_barra
        partes.append(
            f'<text x="{ancho - m_der + 8}" y="{y + (alto_barra - 10) / 2 + 4}" '
            f'class="valor">{fmt_signo(valor)}</text>'
        )

    partes.append("</svg>")
    return "".join(partes)


def barras_agrupadas(categorias, series, *, ancho=680, alto=300, max_val=1.0) -> str:
    """Varias series por categoría. `series` = [(nombre, [valores...]), ...]."""
    m_izq, m_der, m_sup, m_inf = 44, 12, 12, 58
    ancho_plot = ancho - m_izq - m_der
    alto_plot = alto - m_sup - m_inf
    n_grupos = len(categorias)
    n_series = len(series)

    ancho_grupo = ancho_plot / max(n_grupos, 1)
    hueco = ancho_grupo * 0.22
    ancho_barra = (ancho_grupo - hueco) / max(n_series, 1)

    partes = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" class="grafica" '
              f'preserveAspectRatio="xMinYMin meet">']

    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = m_sup + alto_plot * (1 - frac)
        partes.append(
            f'<line x1="{m_izq}" y1="{y:.1f}" x2="{ancho - m_der}" y2="{y:.1f}" '
            f'stroke="var(--grid)" stroke-width="1"/>'
        )
        partes.append(f'<text x="{m_izq - 8}" y="{y + 4:.1f}" text-anchor="end" '
                      f'class="tick">{fmt(frac, 2)}</text>')

    for g, cat in enumerate(categorias):
        x0 = m_izq + g * ancho_grupo + hueco / 2
        for s, (_, valores) in enumerate(series):
            v = valores[g]
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            h = max(0.0, min(v / max_val, 1.0)) * alto_plot
            # 2px de separación entre barras adyacentes: hueco de superficie,
            # no un borde dibujado.
            x = x0 + s * ancho_barra + 1
            w = max(ancho_barra - 2, 1)
            y = m_sup + alto_plot - h
            partes.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'rx="4" fill="{SERIES[s % len(SERIES)]}">'
                f'<title>{esc(series[s][0])} · {esc(cat)}: {fmt(v)}</title></rect>'
            )
        partes.append(
            f'<text x="{m_izq + g * ancho_grupo + ancho_grupo / 2:.1f}" '
            f'y="{m_sup + alto_plot + 18}" text-anchor="middle" class="tick-x">'
            f'{esc(cat)}</text>'
        )

    partes.append(f'<line x1="{m_izq}" y1="{m_sup + alto_plot}" '
                  f'x2="{ancho - m_der}" y2="{m_sup + alto_plot}" '
                  f'stroke="var(--axis)" stroke-width="1"/>')
    partes.append("</svg>")
    return "".join(partes)


def histograma(valores, *, bins=10, ancho=310, alto=150, color=SERIES[0]) -> str:
    """Distribución de una métrica. Revela los ceros que una media esconde."""
    limpios = [v for v in valores
               if v is not None and not (isinstance(v, float) and math.isnan(v))]
    m_izq, m_der, m_sup, m_inf = 30, 8, 10, 26
    ancho_plot, alto_plot = ancho - m_izq - m_der, alto - m_sup - m_inf

    cubos = [0] * bins
    for v in limpios:
        idx = min(int(max(0.0, min(v, 1.0)) * bins), bins - 1)
        cubos[idx] += 1
    tope = max(cubos) if cubos and max(cubos) else 1

    partes = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" class="grafica" '
              f'preserveAspectRatio="xMinYMin meet">']
    partes.append(f'<text x="{m_izq - 6}" y="{m_sup + 8}" text-anchor="end" '
                  f'class="tick">{tope}</text>')
    partes.append(f'<text x="{m_izq - 6}" y="{m_sup + alto_plot}" text-anchor="end" '
                  f'class="tick">0</text>')

    w = ancho_plot / bins
    for i, n in enumerate(cubos):
        h = (n / tope) * alto_plot
        x = m_izq + i * w + 1
        y = m_sup + alto_plot - h
        partes.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w - 2, 1):.1f}" '
            f'height="{h:.1f}" rx="3" fill="{color}">'
            f'<title>{fmt(i / bins, 1)}–{fmt((i + 1) / bins, 1)}: {n} preguntas</title></rect>'
        )

    partes.append(f'<line x1="{m_izq}" y1="{m_sup + alto_plot}" x2="{ancho - m_der}" '
                  f'y2="{m_sup + alto_plot}" stroke="var(--axis)" stroke-width="1"/>')
    for frac, txt in ((0.0, "0"), (0.5, "0,5"), (1.0, "1")):
        x = m_izq + ancho_plot * frac
        partes.append(f'<text x="{x:.1f}" y="{alto - 8}" text-anchor="middle" '
                      f'class="tick">{txt}</text>')
    partes.append("</svg>")
    return "".join(partes)


def barras_apiladas(filas, *, ancho=680, alto_barra=40) -> str:
    """Reparto OK / RECHAZO / ERROR. `filas` = [(etiqueta, {estado: n}), ...]."""
    m_izq, m_der, m_sup = 190, 70, 6
    alto = m_sup + len(filas) * alto_barra + 6
    ancho_plot = ancho - m_izq - m_der

    partes = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" class="grafica" '
              f'preserveAspectRatio="xMinYMin meet">']

    for i, (etiqueta, conteo) in enumerate(filas):
        total = sum(conteo.values()) or 1
        y = m_sup + i * alto_barra
        h = alto_barra - 12
        x = m_izq
        partes.append(
            f'<text x="{m_izq - 12}" y="{y + h / 2 + 4}" text-anchor="end" '
            f'class="etiqueta-eje">{esc(etiqueta)}</text>'
        )
        for estado in ("OK", "RECHAZO", "ERROR"):
            n = conteo.get(estado, 0)
            if not n:
                continue
            w = (n / total) * ancho_plot
            partes.append(
                f'<rect x="{x:.1f}" y="{y}" width="{max(w - 2, 1):.1f}" height="{h}" '
                f'rx="4" fill="{ESTADO_COLOR[estado]}">'
                f'<title>{esc(etiqueta)} · {estado}: {n} de {total} '
                f'({pct(n / total, 1)})</title></rect>'
            )
            if w > 46:   # solo se etiqueta dentro si el texto cabe con holgura
                partes.append(
                    f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + 4}" '
                    f'text-anchor="middle" class="valor-dentro">{n}</text>'
                )
            x += w
        pct_ok = conteo.get("OK", 0) / total
        partes.append(
            f'<text x="{ancho - m_der + 8}" y="{y + h / 2 + 4}" class="valor">'
            f'{pct(pct_ok, 0)}</text>'
        )

    partes.append("</svg>")
    return "".join(partes)


def dispersion(puntos, *, ancho=680, alto=330, x_max=1.0, y_max=1.0,
               x_label="", y_label="", grupos=None, diagonal: bool = False) -> str:
    """`puntos` = [(x, y, grupo, tooltip), ...]. Marcas >=8px con anillo de 2px.

    `diagonal=True` dibuja la recta y=x. Es lo que hace legible un gráfico que
    enfrenta dos corridas: sin la línea de empate, «por encima gana la de arriba»
    —que es todo el mensaje— hay que deducirlo punto a punto. Va apagado por
    defecto para que las dispersiones que ya existen salgan idénticas.
    """
    m_izq, m_der, m_sup, m_inf = 46, 14, 14, 46
    ancho_plot = ancho - m_izq - m_der
    alto_plot = alto - m_sup - m_inf
    grupos = grupos or []
    idx_grupo = {g: i for i, g in enumerate(grupos)}

    partes = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" class="grafica" '
              f'preserveAspectRatio="xMinYMin meet">']

    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = m_sup + alto_plot * (1 - frac)
        partes.append(f'<line x1="{m_izq}" y1="{y:.1f}" x2="{ancho - m_der}" '
                      f'y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        partes.append(f'<text x="{m_izq - 8}" y="{y + 4:.1f}" text-anchor="end" '
                      f'class="tick">{fmt(frac * y_max, 2)}</text>')
        x = m_izq + ancho_plot * frac
        partes.append(f'<line x1="{x:.1f}" y1="{m_sup}" x2="{x:.1f}" '
                      f'y2="{m_sup + alto_plot}" stroke="var(--grid)" stroke-width="1"/>')
        partes.append(f'<text x="{x:.1f}" y="{m_sup + alto_plot + 18}" '
                      f'text-anchor="middle" class="tick">{fmt(frac * x_max, 2)}</text>')

    # Antes de los puntos, para que quede por debajo y no tape ninguna marca.
    if diagonal:
        partes.append(
            f'<line x1="{m_izq}" y1="{m_sup + alto_plot}" '
            f'x2="{m_izq + ancho_plot}" y2="{m_sup}" stroke="var(--axis)" '
            f'stroke-width="1" stroke-dasharray="4 4"/>'
        )

    for x_v, y_v, grupo, tip in puntos:
        if x_v is None or y_v is None:
            continue
        if (isinstance(x_v, float) and math.isnan(x_v)) or (isinstance(y_v, float) and math.isnan(y_v)):
            continue
        cx = m_izq + (min(x_v, x_max) / x_max) * ancho_plot
        cy = m_sup + alto_plot - (min(y_v, y_max) / y_max) * alto_plot
        color = SERIES[idx_grupo.get(grupo, 0) % len(SERIES)]
        partes.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="{color}" '
            f'fill-opacity="0.82" stroke="var(--surface-1)" stroke-width="2">'
            f'<title>{esc(tip)}</title></circle>'
        )

    partes.append(f'<text x="{m_izq + ancho_plot / 2:.1f}" y="{alto - 8}" '
                  f'text-anchor="middle" class="eje-titulo">{esc(x_label)}</text>')
    partes.append(f'<text x="14" y="{m_sup + alto_plot / 2:.1f}" '
                  f'text-anchor="middle" class="eje-titulo" '
                  f'transform="rotate(-90 14 {m_sup + alto_plot / 2:.1f})">'
                  f'{esc(y_label)}</text>')
    partes.append("</svg>")
    return "".join(partes)


def leyenda_series(nombres) -> str:
    """Leyenda de varias series, cada una con su color de `SERIES` en orden."""
    return leyenda([(n, SERIES[i % len(SERIES)], None) for i, n in enumerate(nombres)])


def leyenda(entradas) -> str:
    """`entradas` = [(etiqueta, color, icono|None), ...]. Identidad nunca solo por color."""
    items = []
    for etiqueta, color, icono in entradas:
        marca = f'<span class="ley-icono" style="color:{color}">{icono}</span>' if icono else \
                f'<span class="ley-punto" style="background:{color}"></span>'
        items.append(f'<span class="ley-item">{marca}{esc(etiqueta)}</span>')
    return f'<div class="leyenda">{"".join(items)}</div>'
