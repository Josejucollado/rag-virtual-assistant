"""comparativa_generadores.py — Generador gratuito frente a generador de pago.

Enfrenta a los generadores medidos con TODO lo demás idéntico: el mismo índice,
la misma recuperación (y por tanto los mismos fragmentos en cada pregunta), el
mismo prompt y el mismo juez gratuito. Lo único que cambia es quién redacta.

    Apertus-8B    gratuito, pesos abiertos, pequeño        libre_apertus
    GPT-OSS-120B  gratuito, pesos abiertos (el adoptado)    libre_conciso
    GPT-5.1       de pago, cerrado                          pago_gpt51

No llama a ninguna API: lee los entregables, `consumo.csv` y las corridas fuera
de corpus que haya. Un concursante sin corrida se omite con un aviso, así que el
informe se puede rehacer en cualquier punto del experimento.

    python -m eval_ragas.tfg.comparativa_generadores
    python -m eval_ragas.tfg.comparativa_generadores --salida data/ragas/generadores.html
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from eval_ragas import graficas as G
from eval_ragas.comparar import (
    alinear,
    cargar_corrida,
    contextos_identicos,
    ficha_corrida,
    ficha_juez,
    ruido_de_referencia,
    ruido_por_metrica,
)
from eval_ragas.estadistica import (
    SEMILLA_BOOTSTRAP,
    anotar_holm,
    banda_ruido,
    friedman_pareado,
    intervalo_wilson,
    resumen_pareado,
)
from eval_ragas.comun import (
    CAT_CORTA,
    ERROR,
    NOMBRE_CONSUMO,
    OK,
    ORDEN_CAT,
    RAGAS_DIR,
    RECHAZO,
    ErrorConfiguracion,
)
from eval_ragas.estilo import CSS
from eval_ragas.graficas import esc
from eval_ragas.metricas import ETIQUETAS, ORDEN
from rag.generacion import quitar_citas

SALIDA_PREDETERMINADA = RAGAS_DIR / "comparativa_generadores.html"


@dataclass(frozen=True)
class Concursante:
    nombre: str
    corrida: str
    acceso: str          # "gratuito" / "de pago"
    pesos: str           # "abiertos" / "cerrados"
    nota: str


# El orden es el de la tabla y el de las series de las gráficas: de menor a mayor
# capacidad esperada. GPT-OSS-120B es la referencia porque es el sistema adoptado.
CONCURSANTES = (
    Concursante("Apertus-8B", "libre_apertus", "gratuito", "abiertos",
                "8 mil millones de parámetros, septiembre de 2025 (Blablador)"),
    Concursante("GPT-OSS-120B", "libre_conciso", "gratuito", "abiertos",
                "el generador adoptado, agosto de 2025 (Blablador)"),
    Concursante("GPT-5.1", "pago_gpt51", "de pago", "cerrados",
                "razonamiento bajo, tope de 3000 tokens de salida (OpenAI)"),
)
REFERENCIA = "GPT-OSS-120B"

# Réplica A/A de cada concursante, si se lanzó: la misma configuración otra vez.
# Mide cuánto se mueve cada generador sin cambiar nada, y deja comparar si el de
# pago es más estable que el gratuito.
REPLICAS = {"libre_conciso": "libre_conciso_r2", "pago_gpt51": "pago_gpt51_r2"}

# Las tres que responden a «¿redacta mejor?». Las de contexto no dependen del
# generador y se enseñan aparte, como control.
METRICAS_CLAVE = ("factual_correctness", "factual_recall", "faithfulness")
METRICAS_CONTEXTO = ("context_precision", "context_recall")

# Una pregunta tiene el «contexto completo» si el juez dio cobertura del
# contexto 1 en la corrida de referencia. Los fragmentos son los mismos para
# todos los generadores, así que el estrato es el mismo para todos. En
# libre_conciso: 71 de 94 preguntas completas (F1 0,682) y 23 parciales (0,434).
UMBRAL_CONTEXTO_COMPLETO = 0.999

N_DISCREPANCIAS = 8


# ── Carga ─────────────────────────────────────────────────────────────────────
def presentes() -> tuple[list[Concursante], list[str]]:
    """Los concursantes con entregable, y avisos de los que faltan."""
    hay, faltan = [], []
    for c in CONCURSANTES:
        if (RAGAS_DIR / c.corrida / "resultados_ragas.csv").exists():
            hay.append(c)
        else:
            faltan.append(f"{c.nombre} ({c.corrida}): sin resultados todavía; se omite.")
    return hay, faltan


def tabla_ancha(concursantes: list[Concursante]) -> pd.DataFrame:
    """Una fila por ID común a todos, con `<métrica>|<nombre>` por concursante."""
    datos = {c.nombre: cargar_corrida(c.corrida).set_index("ID") for c in concursantes}
    ids = sorted(set.intersection(*(set(d.index) for d in datos.values())), key=int)
    if not ids:
        raise ErrorConfiguracion("Los generadores no comparten ninguna pregunta por ID.")
    ref = datos.get(REFERENCIA, next(iter(datos.values())))
    ancha = pd.DataFrame({"ID": ids, "Categoria": ref.loc[ids, "Categoria"].to_numpy()})
    for nombre, df in datos.items():
        fila = df.loc[ids]
        ancha[f"resultado|{nombre}"] = fila["resultado"].to_numpy()
        ancha[f"response|{nombre}"] = fila["response"].to_numpy()
        for m in ORDEN:
            if m in fila.columns:
                ancha[f"{m}|{nombre}"] = pd.to_numeric(fila[m], errors="coerce").to_numpy()
    ancha["user_input"] = ref.loc[ids, "user_input"].to_numpy()
    ancha["reference"] = ref.loc[ids, "reference"].to_numpy()
    return ancha


def validas(ancha: pd.DataFrame, metrica: str, nombres: list[str]) -> pd.DataFrame:
    """Casos completos: sin ERROR en nadie y con la métrica puntuada en todos."""
    mascara = pd.Series(True, index=ancha.index)
    for n in nombres:
        mascara &= ancha[f"resultado|{n}"] != ERROR
        col = f"{metrica}|{n}"
        mascara &= ancha[col].notna() if col in ancha.columns else False
    return ancha.loc[mascara]


def leer_consumo(corrida: str) -> pd.DataFrame | None:
    ruta = RAGAS_DIR / corrida / NOMBRE_CONSUMO
    return pd.read_csv(ruta, dtype={"ID": str}) if ruta.exists() else None


def leer_respuestas(corrida: str) -> pd.DataFrame | None:
    ruta = RAGAS_DIR / corrida / "respuestas_rag.csv"
    return pd.read_csv(ruta, dtype={"ID": str}) if ruta.exists() else None


# ── Análisis ──────────────────────────────────────────────────────────────────
def omnibus(ancha: pd.DataFrame, nombres: list[str]) -> list[dict]:
    """Friedman por métrica sobre las mismas preguntas, con Holm entre las 7."""
    filas = []
    for m in ORDEN:
        v = validas(ancha, m, nombres)
        series = [v[f"{m}|{n}"].to_numpy() for n in nombres]
        est, p = friedman_pareado(series) if len(nombres) >= 3 else (None, None)
        filas.append({"metrica": m, "n": len(v), "p": p,
                      "medias": {n: float(v[f"{m}|{n}"].mean()) if len(v) else None
                                 for n in nombres}})
    return anotar_holm(filas)


def pares(ancha: pd.DataFrame, nombres: list[str]) -> list[dict]:
    """Cada concursante frente a la referencia, las 7 métricas, Holm dentro del par."""
    if REFERENCIA not in nombres:
        return []
    salida = []
    for j, otro in enumerate(n for n in nombres if n != REFERENCIA):
        filas = []
        for i, m in enumerate(ORDEN):
            v = validas(ancha, m, [REFERENCIA, otro])
            r = resumen_pareado(v[f"{m}|{REFERENCIA}"].to_numpy(), v[f"{m}|{otro}"].to_numpy(),
                                v["Categoria"].to_numpy(),
                                semilla=SEMILLA_BOOTSTRAP + 100 * j + i)
            filas.append({"metrica": m, **r})
        salida.append({"otro": otro, "filas": anotar_holm(filas)})
    return salida


def estratos_contexto(ancha: pd.DataFrame, nombres: list[str]) -> list[dict]:
    """Métricas clave con contexto completo frente a contexto parcial.

    Separa lo que puede arreglar un generador mejor (usar bien lo que tiene) de
    lo que no (inventar lo que no se recuperó, que además baja la fidelidad).
    """
    col_ref = f"context_recall|{REFERENCIA if REFERENCIA in nombres else nombres[0]}"
    salida = []
    for etiqueta, completo in (("Contexto completo", True), ("Contexto parcial", False)):
        mascara = (ancha[col_ref] >= UMBRAL_CONTEXTO_COMPLETO) if completo \
            else (ancha[col_ref] < UMBRAL_CONTEXTO_COMPLETO)
        parte = ancha[mascara]
        for n in nombres:
            util = parte[parte[f"resultado|{n}"] != ERROR]
            salida.append({"estrato": etiqueta, "generador": n, "n": len(util),
                           **{m: float(util[f"{m}|{n}"].mean()) if len(util) else None
                              for m in METRICAS_CLAVE}})
    return salida


def por_categoria(ancha: pd.DataFrame, nombres: list[str], metrica: str) -> list[dict]:
    v = validas(ancha, metrica, nombres)
    salida = []
    for cat in ORDEN_CAT:
        parte = v[v["Categoria"] == cat]
        if len(parte):
            salida.append({"categoria": cat, "n": len(parte),
                           **{n: float(parte[f"{metrica}|{n}"].mean()) for n in nombres}})
    return salida


def operacion(c: Concursante) -> dict:
    """Coste, latencia, rechazos, formato de las citas y longitud."""
    resp = leer_respuestas(c.corrida)
    cons = leer_consumo(c.corrida)
    fuera = leer_respuestas(f"{c.corrida}_fuera_corpus")
    cons_fuera = leer_consumo(f"{c.corrida}_fuera_corpus")

    datos = {"nombre": c.nombre, "n": 0}
    if resp is not None:
        util = resp[resp["resultado"] != ERROR]
        ok = resp[resp["resultado"] == OK]
        razones = []
        for _, f in ok.iterrows():
            n_ref = len(str(f["reference"] or "").split())
            if n_ref:
                razones.append(len(quitar_citas(str(f["response"] or "")).split()) / n_ref)
        datos.update({
            "n": len(resp),
            "errores": int((resp["resultado"] == ERROR).sum()),
            "rechazos": int((resp["resultado"] == RECHAZO).sum()),
            "lat_mediana": float(pd.to_numeric(util["latencia_s"], errors="coerce").median()),
            "sin_citas": int((pd.to_numeric(ok["n_citas"], errors="coerce") == 0).sum()),
            "con_corchete_gpt": int(ok["response"].astype(str).str.contains("【").sum()),
            "n_ok": len(ok),
            "razon_longitud": float(np.median(razones)) if razones else None,
        })
    if fuera is not None and len(fuera):
        rech = int((fuera["resultado"] == RECHAZO).sum())
        datos.update({"fuera_n": len(fuera), "fuera_rechazos": rech,
                      "fuera_ic": intervalo_wilson(rech, len(fuera))})
    if cons is not None and len(cons):
        total = float(cons["coste_usd"].sum()) + (
            float(cons_fuera["coste_usd"].sum()) if cons_fuera is not None else 0.0)
        datos.update({
            "coste_total": total,
            "coste_pregunta": float(cons["coste_usd"].mean()),
            "tokens_entrada": float(cons["tokens_entrada"].mean()),
            "tokens_salida": float(cons["tokens_salida"].mean()),
            "tokens_razonamiento": float(cons["tokens_razonamiento"].mean()),
        })
    elif c.acceso == "gratuito":
        datos.update({"coste_total": 0.0, "coste_pregunta": 0.0})
    return datos


def replica(c: Concursante) -> dict | None:
    """Cuánto se mueve el generador consigo mismo, si hay réplica A/A."""
    otra = REPLICAS.get(c.corrida)
    if not otra or not (RAGAS_DIR / otra / "resultados_ragas.csv").exists():
        return None
    par, _, _ = alinear(cargar_corrida(c.corrida), cargar_corrida(otra))
    util = par[(par["resultado_a"] != ERROR) & (par["resultado_b"] != ERROR)]
    iguales = (util["response_a"].astype(str).str.strip()
               == util["response_b"].astype(str).str.strip())
    return {
        "nombre": c.nombre, "replica": otra, "n": len(util),
        "identicas": int(iguales.sum()),
        "contexto_identico": int(contextos_identicos(util).sum()),
        "ruido": ruido_por_metrica(par, list(ORDEN), todas=True),
    }


# ── Presentación ──────────────────────────────────────────────────────────────
def _tabla(cabecera: list[str], filas: list[list[str]]) -> str:
    th = "".join(f"<th>{h}</th>" for h in cabecera)
    cuerpo = "".join("<tr>" + "".join(
        f"<th>{c}</th>" if i == 0 else f"<td>{c}</td>" for i, c in enumerate(f)) + "</tr>"
        for f in filas)
    return (f"<div class='tabla-scroll'><table><thead><tr>{th}</tr></thead>"
            f"<tbody>{cuerpo}</tbody></table></div>")


def _dolares(v, dec=4) -> str:
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{G.fmt(v, dec)} $"


def bloque_concursantes(concursantes: list[Concursante]) -> str:
    filas = []
    for c in concursantes:
        juez = ficha_juez(c.corrida) or "no consta (anterior a puntuacion.txt)"
        filas.append([esc(c.nombre), f"<code>{esc(c.corrida)}</code>", esc(c.acceso),
                      esc(c.pesos), esc(c.nota),
                      f"<span class='muted'>{esc(ficha_corrida(c.corrida))}<br>"
                      f"juez: {esc(juez)}</span>"])
    return _tabla(["Generador", "Corrida", "Acceso", "Pesos", "Notas", "Configuración registrada"], filas)


def bloque_omnibus(filas: list[dict], nombres: list[str]) -> str:
    cuerpo = [[esc(ETIQUETAS[f["metrica"]]), str(f["n"]),
               *[G.fmt(f["medias"][n]) for n in nombres],
               G.fmt_p(f["p"]), G.fmt_p(f["p_holm"])] for f in filas]
    return _tabla(["Métrica", "n", *[esc(n) for n in nombres], "p Friedman", "p Holm₇"], cuerpo)


def bloque_par(par: dict, ruido: dict, fuente: str | None) -> str:
    cuerpo = []
    for f in par["filas"]:
        r = ruido.get(f["metrica"])
        banda = banda_ruido(r["sd"] if r else None, f["n"])
        lectura = "—" if banda is None or f["delta"] is None else (
            f"±{G.fmt(banda)} · " + ("fuera del ruido" if abs(f["delta"]) > banda else "dentro del ruido"))
        cuerpo.append([esc(ETIQUETAS[f["metrica"]]), str(f["n"]), G.fmt(f["media_a"]),
                       G.fmt(f["media_b"]), G.fmt_signo(f["delta"]), G.fmt_ic(f["ic"]),
                       G.pct(f["gana_b"]), G.fmt_p(f["p_holm"]), lectura])
    return (f"<h3>{esc(par['otro'])} frente a {esc(REFERENCIA)}</h3>"
            f"<p class='muted'>Δ positivo favorece a {esc(par['otro'])}. Banda de ruido "
            f"medida en {esc(fuente or '—')}.</p>"
            + _tabla(["Métrica", "n", esc(REFERENCIA), esc(par["otro"]), "Δ", "IC 95 %",
                      "Gana", "p Holm₇", "Banda de ruido"], cuerpo))


def bloque_estratos(estratos: list[dict]) -> str:
    cuerpo = [[esc(e["estrato"]), esc(e["generador"]), str(e["n"]),
               *[G.fmt(e[m]) for m in METRICAS_CLAVE]] for e in estratos]
    return _tabla(["Estrato", "Generador", "n", *[esc(ETIQUETAS[m]) for m in METRICAS_CLAVE]], cuerpo)


def bloque_categorias(ancha: pd.DataFrame, nombres: list[str]) -> str:
    partes = []
    for m in ("factual_correctness", "faithfulness"):
        filas = por_categoria(ancha, nombres, m)
        if not filas:
            continue
        series = [(n, [f[n] for f in filas]) for n in nombres]
        leyenda = G.leyenda_series(nombres)
        cuerpo = [[esc(CAT_CORTA.get(f["categoria"], f["categoria"])), str(f["n"]),
                   *[G.fmt(f[n]) for n in nombres]] for f in filas]
        partes.append(f"<h3>{esc(ETIQUETAS[m])}</h3>{leyenda}"
                      f"{G.barras_agrupadas([CAT_CORTA.get(f['categoria'], f['categoria']) for f in filas], series, alto=300)}"
                      + _tabla(["Categoría", "n", *[esc(n) for n in nombres]], cuerpo))
    return "".join(partes)


def bloque_dispersion(ancha: pd.DataFrame, nombres: list[str]) -> str:
    otros = [n for n in nombres if n != REFERENCIA]
    if REFERENCIA not in nombres or not otros:
        return ""
    m = "factual_correctness"
    puntos = []
    for otro in otros:
        v = validas(ancha, m, [REFERENCIA, otro])
        puntos += [(f[f"{m}|{REFERENCIA}"], f[f"{m}|{otro}"], otro,
                    f"#{f['ID']} · {REFERENCIA} {G.fmt(f[f'{m}|{REFERENCIA}'], 2)} · "
                    f"{otro} {G.fmt(f[f'{m}|{otro}'], 2)}") for _, f in v.iterrows()]
    leyenda = G.leyenda_series(otros)
    return (leyenda + G.dispersion(puntos, grupos=otros, diagonal=True,
                                   x_label=f"F1 de {REFERENCIA}", y_label="F1 del otro generador")
            + "<p class='muted'>Cada punto es una pregunta. Por encima de la diagonal gana "
              "el otro generador; por debajo, GPT-OSS-120B.</p>")


def bloque_operacion(datos: list[dict]) -> str:
    cuerpo = []
    for d in datos:
        fuera = (f"{d['fuera_rechazos']}/{d['fuera_n']} (IC95 {G.fmt_ic(d['fuera_ic'])})"
                 if "fuera_n" in d else "—")
        cuerpo.append([
            esc(d["nombre"]),
            f"{d.get('n', 0)} · {d.get('errores', '—')} errores",
            str(d.get("rechazos", "—")),
            fuera,
            f"{G.fmt(d.get('lat_mediana'), 1)} s",
            _dolares(d.get("coste_pregunta")),
            _dolares(d.get("coste_total"), 3),
            G.fmt(d.get("tokens_razonamiento"), 0) if "tokens_razonamiento" in d else "—",
            f"{d.get('sin_citas', '—')}/{d.get('n_ok', '—')}",
            f"{d.get('con_corchete_gpt', '—')}/{d.get('n_ok', '—')}",
            f"{G.fmt(d.get('razon_longitud'), 2)}×",
        ])
    return _tabla(["Generador", "Respuestas", "Rechazos (in-corpus, fallo)",
                   "Rechazos fuera de corpus (acierto)", "Latencia mediana",
                   "Coste por pregunta", "Coste total (94 + 15)", "Tokens de razonamiento (media)",
                   "Sin ninguna cita", "Citas con 【】", "Longitud / ground truth (mediana)"], cuerpo)


def bloque_replicas(reps: list[dict]) -> str:
    if not reps:
        return ("<p class='muted'>Sin réplicas A/A todavía (<code>libre_conciso_r2</code>, "
                "<code>pago_gpt51_r2</code>). Con ellas, esta sección compara cuánto se mueve "
                "cada generador sin cambiar nada.</p>")
    cuerpo = []
    for r in reps:
        sd = lambda m: G.fmt(r["ruido"][m]["sd"]) if m in r["ruido"] else "—"  # noqa: E731
        cuerpo.append([esc(r["nombre"]), f"<code>{esc(r['replica'])}</code>", str(r["n"]),
                       f"{r['identicas']}/{r['n']}", f"{r['contexto_identico']}/{r['n']}",
                       *[sd(m) for m in METRICAS_CLAVE]])
    return _tabla(["Generador", "Réplica", "n", "Respuestas idénticas", "Contexto idéntico",
                   *[f"DT ruido {esc(ETIQUETAS[m])}" for m in METRICAS_CLAVE]], cuerpo)


def bloque_control_contexto(pares_: list[dict]) -> str:
    cuerpo = []
    for par in pares_:
        for f in par["filas"]:
            if f["metrica"] in METRICAS_CONTEXTO:
                cuerpo.append([esc(f"{par['otro']} − {REFERENCIA}"), esc(ETIQUETAS[f["metrica"]]),
                               str(f["n"]), G.fmt_signo(f["delta"]), G.fmt_p(f["p_holm"])])
    if not cuerpo:
        return ""
    return _tabla(["Par", "Métrica", "n", "Δ", "p Holm₇"], cuerpo)


def bloque_discrepancias(ancha: pd.DataFrame, nombres: list[str]) -> str:
    otros = [n for n in nombres if n != REFERENCIA and n != "Apertus-8B"] or \
            [n for n in nombres if n != REFERENCIA]
    if REFERENCIA not in nombres or not otros:
        return ""
    otro, m = otros[-1], "factual_correctness"
    v = validas(ancha, m, [REFERENCIA, otro]).copy()
    v["_d"] = v[f"{m}|{otro}"] - v[f"{m}|{REFERENCIA}"]
    top = v.reindex(v["_d"].abs().sort_values(ascending=False).index).head(N_DISCREPANCIAS)
    filas = "".join(
        f"<tr><td>#{esc(f['ID'])}</td><td>{G.fmt_signo(f['_d'])}</td>"
        f"<td><p><strong>{esc(f['user_input'])}</strong></p>"
        f"<p class='muted'>Referencia: {esc(f['reference'])}</p>"
        f"<div class='par'><div><h4>{esc(REFERENCIA)} · F1 {G.fmt(f[f'{m}|{REFERENCIA}'], 2)}</h4>"
        f"<p>{esc(f[f'response|{REFERENCIA}'])}</p></div>"
        f"<div><h4>{esc(otro)} · F1 {G.fmt(f[f'{m}|{otro}'], 2)}</h4>"
        f"<p>{esc(f[f'response|{otro}'])}</p></div></div></td></tr>"
        for _, f in top.iterrows())
    return (f"<p class='muted'>Las {N_DISCREPANCIAS} preguntas con mayor |ΔF1| entre "
            f"{esc(otro)} y {esc(REFERENCIA)}, con las dos respuestas. Mismo contexto en las dos: "
            f"la diferencia es de redacción.</p>"
            f"<div class='tabla-scroll'><table><thead><tr><th>ID</th><th>ΔF1</th>"
            f"<th>Pregunta y respuestas</th></tr></thead><tbody>{filas}</tbody></table></div>")


CSS_EXTRA = """
body { margin:0; } .envoltorio { max-width:1180px; margin:0 auto; padding:28px; }
.tabla-scroll { overflow-x:auto; margin:16px 0 24px; } table { width:100%; border-collapse:collapse; }
th,td { text-align:left; padding:9px 11px; border-bottom:1px solid var(--border); vertical-align:top; }
th { color:var(--text-strong); } section { margin:30px 0; } h1,h2,h3,h4 { color:var(--text-strong); }
.nota { padding:14px 18px; border-left:3px solid var(--accent); background:var(--surface-1); margin:18px 0; }
.muted { color:var(--muted); } code { overflow-wrap:anywhere; }
.par { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.par > div { min-width:0; } .par h4 { margin:6px 0; font-size:0.85rem; }
@media (max-width: 700px) { .par { grid-template-columns:1fr; } .envoltorio { padding:16px; } }
"""


def construir_html() -> str:
    concursantes, faltan = presentes()
    if len(concursantes) < 2:
        raise ErrorConfiguracion(
            "Hacen falta al menos dos generadores con resultados. " + " ".join(faltan))
    nombres = [c.nombre for c in concursantes]
    ancha = tabla_ancha(concursantes)
    fuente_ruido, ruido = ruido_de_referencia(list(ORDEN))
    # Si hay réplica A/A de la referencia, es la mejor medida del ruido.
    ref = next((c for c in concursantes if c.nombre == REFERENCIA), None)
    rep_ref = replica(ref) if ref else None
    if rep_ref and rep_ref["ruido"]:
        fuente_ruido, ruido = f"{ref.corrida} / {rep_ref['replica']} (réplica A/A)", rep_ref["ruido"]

    omni = omnibus(ancha, nombres)
    pares_ = pares(ancha, nombres)
    reps = [r for r in (replica(c) for c in concursantes) if r]
    avisos = "".join(f"<li>{esc(f)}</li>" for f in faltan)

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Generadores gratuito y de pago</title><style>{CSS}{CSS_EXTRA}</style></head>
<body><main class="envoltorio">
<header><p class="eyebrow">Análisis local · sin llamadas a ninguna API</p>
<h1>¿Mejora pagar por el generador?</h1>
<p>Mismo índice, mismos fragmentos en cada pregunta, mismo prompt y mismo juez gratuito
(Qwen3.8 sin razonamiento). Sólo cambia quién redacta la respuesta. {len(ancha)} preguntas comunes.</p>
{f"<aside class='nota'><ul>{avisos}</ul></aside>" if avisos else ""}</header>

<section id="concursantes"><h2>Los generadores</h2>{bloque_concursantes(concursantes)}</section>

<section id="omnibus"><h2>Las siete métricas</h2>
<p>Friedman contrasta a la vez todos los generadores sobre las mismas preguntas (sólo con tres o
más); Holm₇ corrige las siete métricas. Medias sobre los casos completos: sin ERROR en ninguno y
con la métrica puntuada en todos.</p>{bloque_omnibus(omni, nombres)}</section>

<section id="pares"><h2>Cada generador frente a GPT-OSS-120B</h2>
<p>Wilcoxon pareado, IC bootstrap estratificado por categoría y la <strong>banda de ruido</strong>:
el Δ medio que saldría al 95 % relanzando la misma configuración. Un Δ dentro de la banda no se
puede distinguir de relanzar, aunque su p sea bajo.</p>
{"".join(bloque_par(p, ruido, fuente_ruido) for p in pares_)}
{bloque_dispersion(ancha, nombres)}</section>

<section id="estratos"><h2>¿Dónde puede ganar un generador mejor?</h2>
<p>Con el contexto completo (cobertura del contexto 1 en la corrida de referencia) un generador
mejor puede ganar usando mejor lo que tiene. Con el contexto parcial no debería poder: la
información no se recuperó, y si la pone la saca de su propio conocimiento, lo que el juez castiga
como falta de fidelidad. El techo lo pone la recuperación.</p>{bloque_estratos(estratos_contexto(ancha, nombres))}</section>

<section id="categorias"><h2>Por categoría (descriptivo)</h2>{bloque_categorias(ancha, nombres)}</section>

<section id="operacion"><h2>Coste, latencia, rechazos y formato</h2>
<p>Coste medido con los tokens que devuelve la API (el razonamiento va dentro de la salida) y los
precios de <code>rag.config.PRECIOS_USD_MTOK</code>; la factura real es la del panel de OpenAI.
Latencia de punta a punta, indicativa: servicios distintos con cargas distintas. Fuera de corpus,
rechazar es acertar: es la prueba de alucinación.</p>{bloque_operacion([operacion(c) for c in concursantes])}</section>

<section id="replicas"><h2>¿Es más estable el de pago?</h2>{bloque_replicas(reps)}</section>

<section id="control"><h2>Control: las métricas de contexto</h2>
<p>La precisión y la cobertura del contexto no dependen de la respuesta, y los fragmentos son los
mismos para todos los generadores. Su Δ tendría que ser nulo: lo que se vea aquí es ruido del
juez, y da la escala de lo que el juez mueve por sí solo.</p>{bloque_control_contexto(pares_)}</section>

<section id="discrepancias"><h2>Dónde más discrepan</h2>{bloque_discrepancias(ancha, nombres)}</section>

<footer class="muted"><p>Generado con <code>python -m eval_ragas.tfg.comparativa_generadores</code> a partir
de los entregables de data/ragas. No se ha llamado a ninguna API.</p></footer>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generador gratuito frente a generador de pago.")
    parser.add_argument("--salida", type=Path, default=SALIDA_PREDETERMINADA,
                        help="Fichero HTML de salida")
    args = parser.parse_args()
    try:
        html = construir_html()
    except ErrorConfiguracion as exc:
        print(f"[ERROR] {exc}")
        return 1
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(html, encoding="utf-8")
    concursantes, faltan = presentes()
    print(f"Comparativa de generadores escrita en {args.salida}")
    print(f"  Generadores: {', '.join(c.nombre for c in concursantes)}")
    for f in faltan:
        print(f"  ! {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
