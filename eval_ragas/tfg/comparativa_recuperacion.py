"""Comparativa local de K, reranker y stemming sobre corridas existentes.

No llama al juez ni al generador. Alinea por ID, excluye errores de API y valores
NaN por métrica, y produce un HTML con el contraste triple K=3/5/8, las ablaciones
del reranker y del stemming, y una sensibilidad global para F1.

    python -m eval_ragas.tfg.comparativa_recuperacion
    python -m eval_ragas.tfg.comparativa_recuperacion --salida data/ragas/recuperacion.html
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from eval_ragas import graficas as G
from eval_ragas.graficas import esc
from eval_ragas.comparar import (
    alinear,
    cargar_corrida,
    ruido_de_referencia,
    solape_fragmentos,
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
    OK,
    ORDEN_CAT,
    RAGAS_DIR,
    RECHAZO,
    ErrorConfiguracion,
    campos_configuracion,
)
from eval_ragas.estilo import CSS
from eval_ragas.metricas import ETIQUETAS, ORDEN
from rag.generacion import quitar_citas


SALIDA_PREDETERMINADA = RAGAS_DIR / "comparativa_recuperacion.html"

CORRIDAS_K = (("K=3", "libre_k3"), ("K=5", "libre_conciso"), ("K=8", "libre_k8"))
PARES_DOS_VIAS = (
    ("Estilo", "Conciso", "libre_conciso", "Explicativo", "libre_base"),
    ("Estilo", "Conciso", "libre_conciso", "Mínimo", "libre_minimo"),
    ("Modelo de reranker", "mMiniLM", "libre_conciso", "BGE", "libre_conciso_bge"),
    ("Reranker", "Con reranker", "libre_conciso", "Sin reranker", "libre_sin_reranker"),
    ("Generador", "GPT-OSS", "libre_conciso", "Apertus", "libre_apertus"),
    ("Stemming BM25", "Desactivado", "libre_conciso", "Activado", "libre_conciso_stemming"),
)
METRICAS_CATEGORIA = ("factual_correctness", "context_precision", "context_recall")
CORRIDAS_OPERACION = tuple(dict.fromkeys(
    [nombre for _, nombre in CORRIDAS_K]
    + ["libre_sin_reranker", "libre_conciso_stemming", "libre_conciso_bge",
       "libre_base", "libre_minimo", "libre_apertus"]
))


def filas_validas_k(datos: pd.DataFrame, metrica: str,
                    etiquetas: tuple[str, ...] = ("K=3", "K=5", "K=8")) -> pd.DataFrame:
    """Casos completos para el contraste pareado de una métrica entre todos los K."""
    mascara = pd.Series(True, index=datos.index)
    for etiqueta in etiquetas:
        mascara &= datos[f"resultado_{etiqueta}"] != ERROR
        mascara &= datos[f"{metrica}_{etiqueta}"].notna()
    return datos.loc[mascara].copy()


def construir_datos_k() -> pd.DataFrame:
    """Alinea K3, K5 y K8 por ID y conserva sus métricas y estados."""
    corridas = {etiqueta: cargar_corrida(nombre) for etiqueta, nombre in CORRIDAS_K}
    ids = set.intersection(*(set(df["ID"]) for df in corridas.values()))
    if not ids:
        raise ErrorConfiguracion("K3, K5 y K8 no comparten preguntas por ID.")
    ids = sorted(ids, key=int)
    referencia = corridas["K=5"].set_index("ID").loc[ids]
    datos = pd.DataFrame({"ID": ids, "Categoria": referencia["Categoria"].to_numpy()})
    for etiqueta, df in corridas.items():
        alineada = df.set_index("ID").loc[ids]
        datos[f"resultado_{etiqueta}"] = alineada["resultado"].to_numpy()
        for metrica in ORDEN:
            datos[f"{metrica}_{etiqueta}"] = alineada[metrica].to_numpy()
    return datos


def _filas_pareadas_validas(par: pd.DataFrame, metrica: str) -> pd.DataFrame:
    """Pares utilizables para una métrica de un informe binario."""
    mascara = ((par["resultado_a"] != ERROR) & (par["resultado_b"] != ERROR)
               & par[f"{metrica}_a"].notna() & par[f"{metrica}_b"].notna())
    return par.loc[mascara].copy()


def _resumen_par_binario(a: str, b: str, metrica: str, *, semilla: int) -> tuple[dict, pd.DataFrame]:
    par, _, _ = alinear(cargar_corrida(a), cargar_corrida(b))
    validas = _filas_pareadas_validas(par, metrica)
    resultado = resumen_pareado(
        validas[f"{metrica}_a"].to_numpy(), validas[f"{metrica}_b"].to_numpy(),
        validas["Categoria_a"].to_numpy(), semilla=semilla,
    )
    return resultado, validas


def _resumen_k(datos: pd.DataFrame) -> tuple[list[dict], dict[str, list[dict]]]:
    ombibus, posthoc = [], {}
    pares_k = (("K=3", "K=5"), ("K=8", "K=5"), ("K=3", "K=8"))
    for indice, metrica in enumerate(ORDEN):
        validas = filas_validas_k(datos, metrica)
        series = [validas[f"{metrica}_{k}"].to_numpy() for k, _ in CORRIDAS_K]
        estadistico, p = friedman_pareado(series)
        ombibus.append({"metrica": metrica, "n": len(validas), "medias": {
            k: float(validas[f"{metrica}_{k}"].mean()) if len(validas) else None
            for k, _ in CORRIDAS_K
        }, "estadistico": estadistico, "p": p})

        contrastes = []
        for j, (ka, kb) in enumerate(pares_k):
            r = resumen_pareado(
                validas[f"{metrica}_{ka}"].to_numpy(),
                validas[f"{metrica}_{kb}"].to_numpy(),
                validas["Categoria"].to_numpy(),
                semilla=SEMILLA_BOOTSTRAP + indice * 13 + j,
            )
            contrastes.append({"a": ka, "b": kb, **r})
        posthoc[metrica] = anotar_holm(contrastes)

    return anotar_holm(ombibus), posthoc


def _analisis_binario(nombre: str, etiqueta_a: str, corrida_a: str,
                      etiqueta_b: str, corrida_b: str) -> dict:
    filas, ic_por_metrica = [], {}
    for i, metrica in enumerate(ORDEN):
        estadistica, validas = _resumen_par_binario(
            corrida_a, corrida_b, metrica, semilla=SEMILLA_BOOTSTRAP + i,
        )
        filas.append({"metrica": metrica, **estadistica})
        ic_por_metrica[metrica] = estadistica["ic"]
    anotar_holm(filas)
    return {
        "nombre": nombre,
        "etiqueta_a": etiqueta_a,
        "corrida_a": corrida_a,
        "etiqueta_b": etiqueta_b,
        "corrida_b": corrida_b,
        "filas": filas,
        "ic": ic_por_metrica,
    }


def _prueba_f1_global(k_omnibus: list[dict], binarios: list[dict]) -> list[dict]:
    """Holm exploratorio entre hipótesis primarias de las decisiones del pipeline."""
    p_k = next(f["p"] for f in k_omnibus if f["metrica"] == "factual_correctness")
    hipotesis = [{"nombre": "RERANK_K: K3/K5/K8", "p": p_k, "tipo": "Friedman"}]
    for comp in binarios:
        f1 = next(f for f in comp["filas"] if f["metrica"] == "factual_correctness")
        hipotesis.append({"nombre": comp["nombre"], "p": f1["p"], "tipo": "Wilcoxon pareado"})
    return anotar_holm(hipotesis, destino="p_holm_global")


def _medias_categoria_binaria(corrida_a: str, corrida_b: str, metrica: str) -> list[dict]:
    par, _, _ = alinear(cargar_corrida(corrida_a), cargar_corrida(corrida_b))
    validas = _filas_pareadas_validas(par, metrica)
    salida = []
    for categoria in ORDEN_CAT:
        parte = validas[validas["Categoria_a"] == categoria]
        if parte.empty:
            continue
        salida.append({
            "categoria": categoria,
            "n": len(parte),
            "media_a": float(parte[f"{metrica}_a"].mean()),
            "media_b": float(parte[f"{metrica}_b"].mean()),
        })
    return salida


def _medias_categoria_k(datos: pd.DataFrame, metrica: str) -> list[dict]:
    validas = filas_validas_k(datos, metrica)
    salida = []
    for categoria in ORDEN_CAT:
        parte = validas[validas["Categoria"] == categoria]
        if parte.empty:
            continue
        salida.append({
            "categoria": categoria,
            "n": len(parte),
            **{k: float(parte[f"{metrica}_{k}"].mean()) for k, _ in CORRIDAS_K},
        })
    return salida


def _latencias_y_estados(corridas: tuple[str, ...]) -> list[dict]:
    salida = []
    for nombre in corridas:
        ruta = RAGAS_DIR / nombre / "respuestas_rag.csv"
        if not ruta.exists():
            continue
        df = pd.read_csv(ruta)
        utilizables = df[df["resultado"] != ERROR]
        lat = pd.to_numeric(utilizables["latencia_s"], errors="coerce").dropna()
        salida.append({
            "corrida": nombre,
            "n": len(utilizables),
            "lat_media": float(lat.mean()) if len(lat) else None,
            "lat_mediana": float(lat.median()) if len(lat) else None,
            "rechazos": int((df["resultado"] == RECHAZO).sum()),
            "errores": int((df["resultado"] == ERROR).sum()),
            "n_total": len(df),
        })
    return salida


def _solapes() -> list[dict]:
    pares = [("K=3", "libre_k3", "K=5", "libre_conciso"),
             ("K=8", "libre_k8", "K=5", "libre_conciso"),
             ("K=3", "libre_k3", "K=8", "libre_k8"),
             ("Con reranker", "libre_conciso", "Sin reranker", "libre_sin_reranker"),
             ("Sin stemming", "libre_conciso", "Con stemming", "libre_conciso_stemming")]
    salida = []
    for et_a, a, et_b, b in pares:
        par, _, _ = alinear(cargar_corrida(a), cargar_corrida(b))
        valores = solape_fragmentos(par)
        salida.append({
            "a": et_a, "b": et_b, "n": len(valores),
            "media": float(np.mean(valores)) if valores else None,
            "mediana": float(np.median(valores)) if valores else None,
            "identicos": sum(v == 1 for v in valores),
        })
    return salida


def _rechazos_fuera_corpus() -> list[dict]:
    nombres = CORRIDAS_OPERACION
    salida = []
    for nombre in nombres:
        ruta = RAGAS_DIR / f"{nombre}_fuera_corpus" / "respuestas_rag.csv"
        if not ruta.exists():
            continue
        df = pd.read_csv(ruta)
        n = len(df)
        rechazos = int((df["resultado"] == RECHAZO).sum())
        ic = intervalo_wilson(rechazos, n)
        salida.append({"corrida": nombre, "n": n, "rechazos": rechazos,
                       "proporcion": rechazos / n if n else None, "ic": ic})
    return salida


def _longitud_respuestas() -> list[dict]:
    """Longitud en palabras frente a la referencia; excluye rechazos y errores."""
    salida = []
    for nombre in ("libre_conciso", "libre_base", "libre_minimo"):
        ruta = RAGAS_DIR / nombre / "respuestas_rag.csv"
        if not ruta.exists():
            continue
        df = pd.read_csv(ruta)
        df = df[df["resultado"] == OK]
        palabras, razones = [], []
        for _, fila in df.iterrows():
            respuesta = quitar_citas(str(fila["response"] or ""))
            referencia = str(fila["reference"] or "")
            n_resp = len(respuesta.split())
            n_ref = len(referencia.split())
            if n_ref:
                palabras.append(n_resp)
                razones.append(n_resp / n_ref)
        salida.append({
            "corrida": nombre, "n": len(razones),
            "mediana_palabras": float(np.median(palabras)) if palabras else None,
            "mediana_razon": float(np.median(razones)) if razones else None,
        })
    return salida


def auditar_configuraciones() -> list[str]:
    """Comprueba que cada ablación guardada cambia sólo el parámetro previsto."""
    def campos(nombre):
        ruta = RAGAS_DIR / nombre / "configuracion.txt"
        if not ruta.exists():
            raise ErrorConfiguracion(f"Falta {ruta}; no se puede auditar la comparación.")
        return campos_configuracion(ruta.read_text(encoding="utf-8").strip())

    def comprobar(base, variante, clave):
        a, b = campos(base), campos(variante)
        diferentes = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
        if diferentes != {clave}:
            raise ErrorConfiguracion(
                f"La comparación {base} / {variante} no aísla {clave}: "
                f"difieren {', '.join(sorted(diferentes)) or 'ningún campo'}.")

    comprobar("libre_conciso", "libre_k3", "RERANK_K")
    comprobar("libre_conciso", "libre_k8", "RERANK_K")
    comprobar("libre_conciso", "libre_conciso_bge", "reranker")
    comprobar("libre_conciso", "libre_sin_reranker", "reranker")
    comprobar("libre_conciso", "libre_conciso_stemming", "stemming BM25")
    comprobar("libre_conciso", "libre_base", "estilo")
    comprobar("libre_conciso", "libre_minimo", "estilo")
    comprobar("libre_conciso", "libre_apertus", "modelo RAG")
    return [
        "K3/K5/K8: misma configuración salvo RERANK_K.",
        "BGE y reranker sí/no: misma configuración salvo la variante de reranker.",
        "Stemming: misma configuración salvo stemming BM25.",
        "Las corridas de estilo y generador también están aisladas para la sensibilidad global de F1.",
    ]


def _tabla_k(ombibus: list[dict], posthoc: dict[str, list[dict]]) -> str:
    filas = []
    for resumen in ombibus:
        metric = resumen["metrica"]
        celdas_posthoc = []
        for contraste in posthoc[metric]:
            celdas_posthoc.append(
            f"<td>{esc(contraste['a'])}→{esc(contraste['b'])}: "
                f"{G.fmt_signo(contraste['delta'])} {G.fmt_ic(contraste['ic'])}; "
                f"pHolm₃={G.fmt_p(contraste['p_holm'])}</td>"
            )
        filas.append(
            f"<tr><th>{esc(ETIQUETAS[metric])}</th><td>{resumen['n']}</td>"
            f"<td>{G.fmt(resumen['medias']['K=3'])}</td>"
            f"<td>{G.fmt(resumen['medias']['K=5'])}</td>"
            f"<td>{G.fmt(resumen['medias']['K=8'])}</td>"
            f"<td>{G.fmt_p(resumen['p'])}</td><td>{G.fmt_p(resumen['p_holm'])}</td>"
            f"{''.join(celdas_posthoc)}</tr>"
        )
    return """<div class='tabla-scroll'><table><thead><tr>
      <th>Métrica</th><th>n</th><th>K=3</th><th>K=5</th><th>K=8</th>
      <th>p Friedman</th><th>p Holm₇ (ómnibus)</th>
      <th>K3→K5</th><th>K8→K5</th><th>K3→K8</th>
    </tr></thead><tbody>""" + "".join(filas) + "</tbody></table></div>"


def _tabla_binarios(comp: dict, ruido: dict | None = None) -> str:
    ruido = ruido or {}
    filas = []
    for f in comp["filas"]:
        r = ruido.get(f["metrica"])
        banda = banda_ruido(r["sd"] if r else None, f["n"])
        if banda is None or f["delta"] is None:
            celda_ruido = "—"
        else:
            marca = "fuera" if abs(f["delta"]) > banda else "dentro"
            celda_ruido = f"±{G.fmt(banda)} ({marca})"
        filas.append(
            f"<tr><th>{esc(ETIQUETAS[f['metrica']])}</th><td>{f['n']}</td>"
            f"<td>{G.fmt(f['media_a'])}</td><td>{G.fmt(f['media_b'])}</td>"
            f"<td>{G.fmt_signo(f['delta'])}</td><td>{G.fmt_ic(f['ic'])}</td>"
            f"<td>{G.fmt_signo(f['mediana_delta'])}</td>"
            f"<td>{G.pct(f['gana_b'])}</td><td>{G.fmt_p(f['p_holm'])}</td>"
            f"<td>{celda_ruido}</td></tr>"
        )
    return """<div class='tabla-scroll'><table><thead><tr>
      <th>Métrica</th><th>n</th><th>A</th><th>B</th><th>Δ B−A</th>
      <th>IC pareado 95 %</th><th>Mediana Δ</th><th>Gana B</th><th>p Holm₇</th>
      <th>Banda de ruido</th>
    </tr></thead><tbody>""" + "".join(filas) + "</tbody></table></div>"


def _tabla_categorias_k(datos: pd.DataFrame, metrica: str) -> str:
    filas = []
    for fila in _medias_categoria_k(datos, metrica):
        filas.append(
            f"<tr><th>{esc(CAT_CORTA.get(fila['categoria'], fila['categoria']))}</th>"
            f"<td>{fila['n']}</td><td>{G.fmt(fila['K=3'])}</td>"
            f"<td>{G.fmt(fila['K=5'])}</td><td>{G.fmt(fila['K=8'])}</td></tr>"
        )
    return (f"<h4>{esc(ETIQUETAS[metrica])}</h4><div class='tabla-scroll'><table>"
            "<thead><tr><th>Categoría</th><th>n</th><th>K=3</th><th>K=5</th><th>K=8</th></tr></thead>"
            f"<tbody>{''.join(filas)}</tbody></table></div>")


def _tabla_categorias_binaria(comp: dict, metrica: str) -> str:
    filas = []
    for fila in _medias_categoria_binaria(comp["corrida_a"], comp["corrida_b"], metrica):
        filas.append(
            f"<tr><th>{esc(CAT_CORTA.get(fila['categoria'], fila['categoria']))}</th>"
            f"<td>{fila['n']}</td><td>{G.fmt(fila['media_a'])}</td>"
            f"<td>{G.fmt(fila['media_b'])}</td>"
            f"<td>{G.fmt_signo(fila['media_b']-fila['media_a'])}</td></tr>"
        )
    return (f"<h4>{esc(ETIQUETAS[metrica])}</h4><div class='tabla-scroll'><table>"
            "<thead><tr><th>Categoría</th><th>n</th><th>A</th><th>B</th><th>Δ</th></tr></thead>"
            f"<tbody>{''.join(filas)}</tbody></table></div>")


def _grafica_k(ombibus: list[dict]) -> str:
    metrics = ("factual_correctness", "context_precision", "context_recall")
    categorias = [ETIQUETAS[m] for m in metrics]
    series = [(k, [next(f for f in ombibus if f["metrica"] == m)["medias"][k]
                   for m in metrics]) for k, _ in CORRIDAS_K]
    return G.leyenda_series([k for k, _ in CORRIDAS_K]) + G.barras_agrupadas(
        categorias, series, alto=310,
    )


def _grafica_categoria_k(datos: pd.DataFrame, metrica: str) -> str:
    filas = _medias_categoria_k(datos, metrica)
    categorias = [CAT_CORTA.get(f["categoria"], f["categoria"]) for f in filas]
    series = [(k, [f[k] for f in filas]) for k, _ in CORRIDAS_K]
    leyenda = G.leyenda_series([k for k, _ in CORRIDAS_K])
    return leyenda + G.barras_agrupadas(categorias, series, alto=300)


def _grafica_categoria_binaria(comp: dict, metrica: str) -> str:
    filas = _medias_categoria_binaria(comp["corrida_a"], comp["corrida_b"], metrica)
    categorias = [CAT_CORTA.get(f["categoria"], f["categoria"]) for f in filas]
    series = [
        (comp["etiqueta_a"], [f["media_a"] for f in filas]),
        (comp["etiqueta_b"], [f["media_b"] for f in filas]),
    ]
    leyenda = G.leyenda_series([comp["etiqueta_a"], comp["etiqueta_b"]])
    return leyenda + G.barras_agrupadas(categorias, series, alto=300)


def _tabla_global_f1(hipotesis: list[dict]) -> str:
    filas = []
    for h in hipotesis:
        filas.append(
            f"<tr><th>{esc(h['nombre'])}</th><td>{esc(h['tipo'])}</td>"
            f"<td>{G.fmt_p(h['p'])}</td><td>{G.fmt_p(h['p_holm_global'])}</td></tr>"
        )
    return """<div class='tabla-scroll'><table><thead><tr>
      <th>Decisión primaria</th><th>Prueba</th><th>p sin ajustar</th><th>p Holm global</th>
    </tr></thead><tbody>""" + "".join(filas) + "</tbody></table></div>"


def _bloque_diagnostico(reranker: dict, stemming: dict, solapes: list[dict]) -> str:
    def fila(comp, metrica):
        return next(f for f in comp["filas"] if f["metrica"] == metrica)

    f1_r = fila(reranker, "factual_correctness")
    cp_r = fila(reranker, "context_precision")
    f1_s = fila(stemming, "factual_correctness")
    cp_s = fila(stemming, "context_precision")
    cr_s = fila(stemming, "context_recall")
    sol_r = next(s["media"] for s in solapes if s["a"] == "Con reranker")
    sol_s = next(s["media"] for s in solapes if s["a"] == "Sin stemming")

    return f"""
<section id="diagnostico"><h2>¿Hay un fallo de implementación?</h2>
<p>La inspección estática confirma que <code>BM25_STEMMING</code> llega a
<code>tokenizar_es</code> mediante <code>BM25Retriever.preprocess_func</code>; sólo
afecta a la rama léxica y filtra palabras vacías antes de reducir raíces. Las
configuraciones registradas de stemming sí/no difieren únicamente en ese campo.
Que la mejora sea nula es plausible: la rama densa (60 % del híbrido) no cambia,
y el stemming puede tanto unir variantes como colapsar términos distintos.</p>
<p>La ablación del reranker también mantiene el híbrido y la deduplicación con el
mismo límite final. Con reranker frente a sin reranker, F1 es
{G.fmt(f1_r['media_a'])} / {G.fmt(f1_r['media_b'])} (Δ
{G.fmt_signo(f1_r['delta'])}, pHolm₇={G.fmt_p(f1_r['p_holm'])}); la precisión de
contexto es {G.fmt(cp_r['media_a'])} / {G.fmt(cp_r['media_b'])}
(pHolm₇={G.fmt_p(cp_r['p_holm'])}). El solape medio de contextos es {G.pct(sol_r)}:
cambia lo que lee el generador, pero no se observa una mejora final significativa.
Un reranker está diseñado para ordenar mejor candidatos, no garantiza mayor F1;
sólo ordena los candidatos recuperados y mMiniLM trunca parte de los fragmentos.</p>
<p>Con stemming sí/no, F1 es {G.fmt(f1_s['media_a'])} /
{G.fmt(f1_s['media_b'])} (Δ {G.fmt_signo(f1_s['delta'])},
pHolm₇={G.fmt_p(f1_s['p_holm'])}); precisión de contexto Δ
{G.fmt_signo(cp_s['delta'])}, cobertura Δ {G.fmt_signo(cr_s['delta'])}, y solape
medio {G.pct(sol_s)}. Los tamaños del efecto pequeños y el solape alto concuerdan
con que el stemming no haya alterado de forma relevante este banco.</p>
<aside class="nota"><strong>Lectura:</strong> los resultados no indican un error en
los interruptores. Indican que estas variantes no han demostrado una mejora
estadística en las métricas finales de este conjunto.</aside></section>"""


def _tabla_operacion(latencias: list[dict], fuera: list[dict]) -> str:
    fuera_por_nombre = {f["corrida"]: f for f in fuera}
    filas = []
    for r in latencias:
        f = fuera_por_nombre.get(r["corrida"])
        rechazos_fuera = (f"{f['rechazos']}/{f['n']} ({G.pct(f['proporcion'])}; "
                           f"IC95 {G.fmt_ic(f['ic'])})" if f else "—")
        filas.append(
            f"<tr><th>{esc(r['corrida'])}</th><td>{r['n']}/{r['n_total']}</td>"
            f"<td>{G.fmt(r['lat_mediana'], 2)} s</td><td>{G.fmt(r['lat_media'], 2)} s</td>"
            f"<td>{r['rechazos']}</td><td>{r['errores']}</td><td>{rechazos_fuera}</td></tr>"
        )
    return """<div class='tabla-scroll'><table><thead><tr>
      <th>Corrida</th><th>respuestas válidas</th><th>latencia mediana</th>
      <th>latencia media</th><th>rechazos in-corpus</th><th>errores</th>
      <th>rechazos fuera de corpus</th></tr></thead><tbody>""" + "".join(filas) + "</tbody></table></div>"


def _tabla_solape(solapes: list[dict]) -> str:
    filas = []
    for s in solapes:
        filas.append(
            f"<tr><th>{esc(s['a'])} / {esc(s['b'])}</th><td>{s['n']}</td>"
            f"<td>{G.pct(s['media'])}</td><td>{G.pct(s['mediana'])}</td>"
            f"<td>{s['identicos']}</td></tr>"
        )
    return """<div class='tabla-scroll'><table><thead><tr>
      <th>Comparación</th><th>n</th><th>solape medio</th><th>mediana</th>
      <th>contextos idénticos</th></tr></thead><tbody>""" + "".join(filas) + "</tbody></table></div>"


def _tabla_longitud() -> str:
    filas = []
    for fila in _longitud_respuestas():
        filas.append(
            f"<tr><th>{esc(fila['corrida'])}</th><td>{fila['n']}</td>"
            f"<td>{G.fmt(fila['mediana_palabras'], 1)}</td>"
            f"<td>{G.fmt(fila['mediana_razon'], 2)}×</td></tr>"
        )
    return """<div class='tabla-scroll'><table><thead><tr>
      <th>Estilo</th><th>n (respuestas de contenido)</th><th>mediana de palabras</th>
      <th>mediana respecto al ground truth</th></tr></thead><tbody>""" + "".join(filas) + "</tbody></table></div>"


def construir_html() -> str:
    auditoria = auditar_configuraciones()
    datos_k = construir_datos_k()
    omnibus_k, posthoc_k = _resumen_k(datos_k)
    binarios = [_analisis_binario(*par) for par in PARES_DOS_VIAS]
    global_f1 = _prueba_f1_global(omnibus_k, binarios)
    latencias = _latencias_y_estados(CORRIDAS_OPERACION)
    fuera = _rechazos_fuera_corpus()
    solapes = _solapes()
    reranker = next(c for c in binarios if c["nombre"] == "Reranker")
    stemming = next(c for c in binarios if c["nombre"] == "Stemming BM25")
    diagnostico = _bloque_diagnostico(reranker, stemming, solapes)
    fuente_ruido, ruido = ruido_de_referencia(list(ORDEN))

    secciones_categoria = []
    for metrica in METRICAS_CATEGORIA:
        secciones_categoria.append(
            f"<section><h3>K=3/5/8 · {esc(ETIQUETAS[metrica])}</h3>"
            f"{_grafica_categoria_k(datos_k, metrica)}"
            f"{_tabla_categorias_k(datos_k, metrica)}</section>"
        )
    for comp in binarios:
        for metrica in METRICAS_CATEGORIA:
            secciones_categoria.append(
                f"<section><h3>{esc(comp['nombre'])}: {esc(ETIQUETAS[metrica])}</h3>"
                f"{_grafica_categoria_binaria(comp, metrica)}"
                f"{_tabla_categorias_binaria(comp, metrica)}</section>"
            )

    secciones_binarias = []
    for comp in binarios:
        secciones_binarias.append(
            f"<section><h3>{esc(comp['nombre'])}: {esc(comp['etiqueta_a'])} / "
            f"{esc(comp['etiqueta_b'])}</h3>"
            f"<p>Δ positivo favorece B ({esc(comp['etiqueta_b'])}). Los IC son bootstrap "
            f"pareados puntuales al 95 % para el delta medio; no son simultáneos ni "
            f"sustituyen la corrección de p. Wilcoxon contrasta los rangos de las "
            f"diferencias, por lo que su p puede no coincidir con el IC de la media. "
            f"pHolm₇ corrige las siete métricas de este contraste.</p>"
            f"{_tabla_binarios(comp, ruido)}</section>"
        )

    k_omnibus = []
    for f in omnibus_k:
        k_omnibus.append(
            f"<tr><th>{esc(ETIQUETAS[f['metrica']])}</th><td>{f['n']}</td>"
            f"<td>{G.fmt(f['medias']['K=3'])}</td><td>{G.fmt(f['medias']['K=5'])}</td>"
            f"<td>{G.fmt(f['medias']['K=8'])}</td><td>{G.fmt_p(f['p'])}</td>"
            f"<td>{G.fmt_p(f['p_holm'])}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ablaciones de recuperación — comparativa</title><style>{CSS}
body {{ margin:0; }} .envoltorio {{ max-width:1180px; margin:0 auto; padding:28px; }}
.tabla-scroll {{ overflow-x:auto; margin:16px 0 24px; }} table {{ width:100%; border-collapse:collapse; }}
th,td {{ text-align:left; padding:9px 11px; border-bottom:1px solid var(--border); white-space:nowrap; }}
th {{ color:var(--text-strong); }} section {{ margin:30px 0; }} h1,h2,h3,h4 {{ color:var(--text-strong); }}
.nota {{ padding:14px 18px; border-left:3px solid var(--accent); background:var(--surface-1); margin:18px 0; }}
.muted {{ color:var(--muted); }} code {{ overflow-wrap:anywhere; }}
</style></head><body><main class="envoltorio">
<header><p class="eyebrow">Análisis local · sin llamadas al juez ni al generador</p>
<h1>Ablaciones de recuperación y contraste de K</h1>
<p>Comparación de K=3/5/8 y de las ablaciones de reranker y stemming, reutilizando los entregables existentes.</p></header>

<section id="auditoria"><h2>Auditoría de las configuraciones</h2><ul>{''.join(f'<li>{G.esc(x)}</li>' for x in auditoria)}</ul>
<aside class="nota"><strong>Interpretación de K:</strong> variar RERANK_K cambia tanto el límite de fragmentos del contexto como el top_n del cross-encoder (3×K). Esta comparativa evalúa ese paquete de configuración, no sólo la cantidad final de fragmentos.</aside></section>

<section id="k"><h2>K=3, K=5 y K=8</h2>
<p>Friedman es el contraste ómnibus repetido por pregunta. Holm₇ corrige esos siete contrastes ómnibus. Los post hoc Wilcoxon se presentan con Holm₃ entre los tres pares de K; sus diferencias e IC son descriptivos si el ómnibus de esa métrica no es significativo. Los IC son puntuales y bootstrap del delta medio; Wilcoxon contrasta rangos, así que ambos indicadores pueden diferir.</p>
{_grafica_k(omnibus_k)}
<div class="tabla-scroll"><table><thead><tr><th>Métrica</th><th>n completo</th><th>K=3</th><th>K=5</th><th>K=8</th><th>p Friedman</th><th>p Holm₇</th></tr></thead><tbody>{''.join(k_omnibus)}</tbody></table></div>
{_tabla_k(omnibus_k, posthoc_k)}</section>

<section id="ablaciones"><h2>Ablaciones de dos configuraciones</h2>
<p><strong>Banda de ruido:</strong> Δ medio que saldría al 95 % sin cambiar nada, con la desviación típica del ruido medida en {esc(fuente_ruido or '—')}. «Dentro» significa indistinguible de relanzar la misma configuración, aunque el p sea bajo.</p>
<p>A y B responden a las mismas preguntas. Cada tabla excluye ERROR y NaN por métrica; el IC bootstrap remuestrea preguntas pareadas, estratificadas por categoría. Los IC describen variación entre preguntas observadas, no la variabilidad de volver a ejecutar modelos no deterministas.</p>
{''.join(secciones_binarias)}</section>

<section id="global-f1"><h2>Sensibilidad global del resultado factual</h2>
<p>Holm se aplica a siete hipótesis primarias: estilo explicativo frente a conciso, mínimo frente a conciso, modelo de reranker, reranker sí/no, K ómnibus, generador y stemming. Es una sensibilidad exploratoria para controlar la selección entre decisiones; no sustituye a los Holm₇ de cada comparativa.</p>
{_tabla_global_f1(global_f1)}</section>

<section id="categorias"><h2>Por categoría (descriptivo)</h2>
<p>Se muestran F1, precisión y cobertura del contexto. Inferencia tiene 15 preguntas (14 para Apertus); estas medias sirven para localizar patrones, no para declarar significación por categoría.</p>
{''.join(secciones_categoria)}</section>

<section id="operacion"><h2>Contextos, latencia y rechazos</h2>
<h3>Solape de fragmentos</h3><p>Jaccard medio y mediano de los fragmentos finales compartidos; ERROR queda excluido.</p>{_tabla_solape(solapes)}
<h3>Calidad operacional observada</h3><p>Latencia de extremo a extremo, excluyendo ERROR. Es indicativa: combina el pipeline local con Blablador y la carga del servicio puede variar entre corridas.</p>{_tabla_operacion(latencias, fuera)}</section>

<section id="estilo"><h2>Diagnóstico de longitud del estilo</h2><p>Conteo de palabras sin marcas de cita y razón frente a la referencia, sólo para respuestas OK. Es una descripción local de las respuestas ya generadas.</p>{_tabla_longitud()}</section>

{diagnostico}

<section id="lectura"><h2>Qué dice y qué no dice el resultado</h2>
<ul><li>Un p no significativo indica evidencia insuficiente para distinguir configuraciones; no demuestra igualdad.</li>
<li>El reranker reordena candidatos, pero no añade candidatos que falten. La ausencia de mejora en F1 no implica por sí sola que su implementación esté rota.</li>
<li>Stemming sólo altera los tokens de BM25; dense y reranker siguen activos y pueden amortiguar el efecto léxico.</li>
<li>En el reranker mMiniLM, el truncamiento a 512 tokens afecta a parte de los fragmentos; BGE cambia el perfil calidad/latencia pero su diferencia F1 no queda respaldada en la corrección existente.</li>
<li>Las categorías y los IC bootstrap describen variación entre preguntas; no capturan por sí solos la variabilidad de nuevas llamadas a los modelos.</li></ul></section>

<footer class="muted"><p>Fuente: CSV de respuestas, resultados RAGAS y configuracion.txt en data/ragas. No se han realizado llamadas a la API.</p></footer>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comparativa local de K, reranker y stemming a partir de corridas existentes."
    )
    parser.add_argument("--salida", type=Path, default=SALIDA_PREDETERMINADA,
                        help="Fichero HTML de salida")
    args = parser.parse_args()
    try:
        html = construir_html()
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(html, encoding="utf-8")
    except (ErrorConfiguracion, FileNotFoundError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    print(f"Comparativa local escrita en {args.salida}")
    print("Corridas: K3/K5/K8, reranker sí/no y stemming sí/no; no se llamó a ninguna API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
