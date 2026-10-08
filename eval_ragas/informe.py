"""
informe.py — Fase 3: informe visual a partir del CSV de resultados.

Agrega `data/ragas/resultados_ragas.csv` y produce `data/ragas/informe_ragas.html`,
autocontenido (SVG en línea, sin CDN) y listo para publicar como Artifact.

Uso:
    python -m eval_ragas.informe
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from eval_ragas import graficas as G
from eval_ragas import metricas as M
# Los formateadores (esc/fmt/pct) y las categorías se comparten con `graficas` y
# `comun`: tenerlos duplicados aquí hacía que se desviaran sin que se notara.
from eval_ragas.graficas import esc, fmt, pct
# La hoja de estilo vive en su propio módulo porque la comparte `comparar.py`.
from eval_ragas.estilo import CSS, FUENTES
from eval_ragas.comun import (
    CAT_CORTA,
    ERROR,
    INFORME_HTML,
    OK,
    RECHAZO,
    RESULTADOS_CSV,
    SALIDA_DIR,
    categorias_presentes as _categorias_presentes,
    leer_configuracion,
    resumen_config,
)
from rag import ErrorConfiguracion


def cargar() -> tuple[pd.DataFrame, list[str]]:
    if not RESULTADOS_CSV.exists():
        raise ErrorConfiguracion(
            f"No existe {RESULTADOS_CSV}.\n"
            f"Ejecuta antes: python -m eval_ragas.puntuar"
        )
    df = pd.read_csv(RESULTADOS_CSV, dtype={"ID": str})
    presentes = [m for m in M.ORDEN if m in df.columns]
    for m in presentes:
        df[m] = pd.to_numeric(df[m], errors="coerce")
    df["Categoria"] = df["Categoria"].fillna("(sin categoría)")
    return df, presentes


def categorias_presentes(df: pd.DataFrame) -> list[str]:
    """Las categorías del DataFrame, en el orden canónico del banco."""
    return _categorias_presentes(list(df["Categoria"].unique()))


# ── Bloques del informe ───────────────────────────────────────────────────────
def tarjetas(df: pd.DataFrame) -> str:
    total = len(df)
    conteo = df["resultado"].value_counts().to_dict()
    n_ok, n_rech, n_err = conteo.get(OK, 0), conteo.get(RECHAZO, 0), conteo.get(ERROR, 0)
    fc = df["factual_correctness"].mean() if "factual_correctness" in df else float("nan")
    fi = df["faithfulness"].mean() if "faithfulness" in df else float("nan")

    def tarjeta(valor, etiqueta, nota, tono=""):
        return (f'<div class="tarjeta {tono}"><div class="tarjeta-valor">{valor}</div>'
                f'<div class="tarjeta-etiqueta">{esc(etiqueta)}</div>'
                f'<div class="tarjeta-nota">{esc(nota)}</div></div>')

    return (
        '<div class="tarjetas">'
        + tarjeta(total, "Preguntas evaluadas", "banco con ground truth")
        + tarjeta(pct(n_ok / total if total else 0), "Respuestas de contenido",
                  f"{n_ok} de {total}", "tono-ok")
        + tarjeta(pct(n_rech / total if total else 0), "Rechazos indebidos",
                  f"{n_rech} preguntas sin responder", "tono-mal")
        + tarjeta(fmt(fi, 2), "Fidelidad media", "sin alucinación = 1,00")
        + tarjeta(fmt(fc, 2), "Corrección factual media", "F1 contra el ground truth")
        + (tarjeta(n_err, "Errores de API", "excluidos de las medias", "tono-aviso")
           if n_err else "")
        + '</div>'
    )


def aviso_verbosidad(df: pd.DataFrame) -> str:
    """Explica por qué la corrección factual F1 sale mucho más baja que el resto.

    Sin esta nota el informe induce a error: un 0,36 en F1 se lee como
    «el RAG acierta un tercio de las veces», cuando lo que dice en realidad es
    que responde con mucho más detalle que la referencia.
    """
    if "factual_correctness" not in df or "factual_recall" not in df:
        return ""

    largo_resp = df["response"].astype(str).str.len().mean()
    largo_ref = df["reference"].astype(str).str.len().mean()
    if not largo_ref:
        return ""
    ratio = largo_resp / largo_ref

    return f"""
  <aside class="nota">
    <p class="nota-titulo">Por qué la corrección factual (F1) sale tan baja</p>
    <p>Las respuestas del RAG son de media <strong>{fmt(ratio, 1)} veces más largas</strong>
       que las del ground truth ({int(largo_resp)} frente a {int(largo_ref)} caracteres).
       El F1 descompone ambas en afirmaciones y cuenta como error toda afirmación de la
       respuesta que no esté en la referencia: explicar de más penaliza igual que
       equivocarse. Por eso está también <strong>{esc(M.ETIQUETAS['factual_recall'])}</strong>
       ({fmt(df['factual_recall'].mean(), 2)}), que solo pregunta si la respuesta cubre lo
       que dice la referencia. Con una fidelidad de
       {fmt(df['faithfulness'].mean(), 2)}, el detalle de más está fundamentado en los
       documentos: es verbosidad, no invención.</p>
  </aside>"""


def bloque_medias(df: pd.DataFrame, metricas: list[str]) -> str:
    """Media global de cada métrica: una sola serie, barras horizontales."""
    datos = [(M.ETIQUETAS[m], df[m].mean(), M.DESCRIPCIONES[m]) for m in metricas]
    filas = "".join(
        f"<tr><th scope='row'>{esc(M.ETIQUETAS[m])}</th>"
        f"<td>{fmt(df[m].mean())}</td><td>{fmt(df[m].median())}</td>"
        f"<td>{fmt(df[m].std())}</td>"
        f"<td>{int(df[m].notna().sum())}</td>"
        f"<td class='desc'>{esc(M.DESCRIPCIONES[m])}</td></tr>"
        for m in metricas
    )
    return f"""
<section id="medias">
  <h2>Resultado global</h2>
  <p class="intro">Media de cada métrica sobre las {len(df)} preguntas del banco.
     Todas van de 0 a 1: más alto es mejor.</p>
  {G.barras_horizontales(datos)}
  {aviso_verbosidad(df)}
  <details class="tabla-vista"><summary>Ver como tabla</summary>
    <div class="envoltorio-tabla"><table>
      <thead><tr><th>Métrica</th><th>Media</th><th>Mediana</th><th>Desv. típica</th>
        <th>N</th><th>Qué mide</th></tr></thead>
      <tbody>{filas}</tbody>
    </table></div>
  </details>
</section>"""


def bloque_categorias(df: pd.DataFrame, metricas: list[str]) -> str:
    cats = categorias_presentes(df)
    series = [(CAT_CORTA.get(c, c), [df[df["Categoria"] == c][m].mean() for m in metricas])
              for c in cats]
    etiquetas = [M.ETIQUETAS[m] for m in metricas]

    encabezado = "".join(f"<th>{esc(CAT_CORTA.get(c, c))}</th>" for c in cats)
    filas = "".join(
        f"<tr><th scope='row'>{esc(M.ETIQUETAS[m])}</th>"
        + "".join(f"<td>{fmt(df[df['Categoria'] == c][m].mean())}</td>" for c in cats)
        + "</tr>"
        for m in metricas
    )
    conteos = "<tr><th scope='row'>Nº de preguntas</th>" + "".join(
        f"<td>{int((df['Categoria'] == c).sum())}</td>" for c in cats) + "</tr>"

    return f"""
<section id="categorias">
  <h2>Por tipo de pregunta</h2>
  <p class="intro">Las preguntas directas se responden con un solo fragmento; las de
     síntesis exigen combinar varios y las de inferencia, razonar más allá del texto.
     Es donde se ve si el sistema aguanta preguntas difíciles o solo las fáciles.</p>
  {G.leyenda_series([CAT_CORTA.get(c, c) for c in cats])}
  {G.barras_agrupadas(etiquetas, series)}
  <details class="tabla-vista"><summary>Ver como tabla</summary>
    <div class="envoltorio-tabla"><table>
      <thead><tr><th>Métrica</th>{encabezado}</tr></thead>
      <tbody>{filas}{conteos}</tbody>
    </table></div>
  </details>
</section>"""


def bloque_rechazos(df: pd.DataFrame, metricas: list[str]) -> str:
    """El bloque central: separar rechazo de respuesta real."""
    cats = categorias_presentes(df)
    filas_graf = [("Todas las preguntas", df["resultado"].value_counts().to_dict())]
    filas_graf += [(CAT_CORTA.get(c, c),
                    df[df["Categoria"] == c]["resultado"].value_counts().to_dict())
                   for c in cats]

    solo_ok = df[df["resultado"] == OK]
    validas = df[df["resultado"] != ERROR]

    pareadas = [
        ("Todas (incluye rechazos)", [validas[m].mean() for m in metricas]),
        ("Solo respuestas de contenido", [solo_ok[m].mean() for m in metricas]),
    ]
    etiquetas = [M.ETIQUETAS[m] for m in metricas]

    filas_tabla = "".join(
        f"<tr><th scope='row'>{esc(M.ETIQUETAS[m])}</th>"
        f"<td>{fmt(validas[m].mean())}</td><td>{fmt(solo_ok[m].mean())}</td>"
        f"<td>{fmt(solo_ok[m].mean() - validas[m].mean())}</td></tr>"
        for m in metricas
    )

    n_rech = int((df["resultado"] == RECHAZO).sum())
    total = len(df)
    diagnostico = (
        f"El RAG se ha negado a responder {n_rech} de {total} preguntas "
        f"({pct(n_rech / total)})."
        if n_rech else
        "El RAG ha respondido a todas las preguntas: no hay ningún rechazo indebido."
    )

    return f"""
<section id="rechazos">
  <h2>Rechazos: cuándo el RAG no responde</h2>
  <p class="intro">Las {total} preguntas del banco son <em>in-corpus</em>: la información
     está en los documentos. Por eso responder
     <q>No tengo la suficiente información para contestar a su pregunta</q>
     es siempre un <strong>fallo</strong>, nunca una respuesta válida.
     {esc(diagnostico)}</p>

  {G.leyenda([(nombre, G.ESTADO_COLOR[est], G.ESTADO_ICONO[est])
              for est, nombre in (("OK", "Respuesta de contenido"),
                                  ("RECHAZO", "Rechazo (fallo)"),
                                  ("ERROR", "Error de API"))
              if (df["resultado"] == est).any()])}
  {G.barras_apiladas(filas_graf)}

  <h3>Cuánto penaliza el rechazo</h3>
  <p class="intro">La primera barra de cada par es la nota real del sistema de punta a
     punta; la segunda, su calidad cuando sí se atreve a responder. Si están a la misma
     altura, el problema no es que el RAG se calle; si se separan, sí lo es.</p>
  {G.leyenda_series([n for n, _ in pareadas])}
  {G.barras_agrupadas(etiquetas, pareadas)}
  <details class="tabla-vista"><summary>Ver como tabla</summary>
    <div class="envoltorio-tabla"><table>
      <thead><tr><th>Métrica</th><th>Todas</th><th>Solo contenido</th><th>Diferencia</th></tr></thead>
      <tbody>{filas_tabla}</tbody>
    </table></div>
  </details>
</section>"""


def bloque_distribuciones(df: pd.DataFrame, metricas: list[str]) -> str:
    tarjetas_h = []
    for m in metricas:
        vals = df[m].dropna().tolist()
        ceros = sum(1 for v in vals if v < 0.05)
        perfectos = sum(1 for v in vals if v > 0.95)
        tarjetas_h.append(f"""
      <figure class="mini">
        <figcaption>{esc(M.ETIQUETAS[m])}</figcaption>
        {G.histograma(vals)}
        <p class="mini-nota">{perfectos} preguntas ≥ 0,95 · {ceros} preguntas ≤ 0,05</p>
      </figure>""")

    return f"""
<section id="distribucion">
  <h2>Distribución de las notas</h2>
  <p class="intro">La media sola engaña: un 0,80 puede ser <q>casi todo bien</q> o
     <q>la mayoría perfecto y un puñado a cero</q>. Cada barra cuenta cuántas preguntas
     caen en ese tramo de nota.</p>
  <div class="rejilla-mini">{"".join(tarjetas_h)}</div>
</section>"""


def bloque_diagnostico(df: pd.DataFrame, metricas: list[str]) -> str:
    bloques = []
    cats = categorias_presentes(df)

    if {"context_recall", "faithfulness"} <= set(metricas):
        puntos = [(r["context_recall"], r["faithfulness"], r["Categoria"],
                   f"[{r['ID']}] {str(r['user_input'])[:90]}")
                  for _, r in df.iterrows()]
        bloques.append(f"""
  <h3>¿Falla al recuperar o al redactar?</h3>
  <p class="intro">Cada punto es una pregunta. Abajo a la izquierda: el buscador no
     encontró lo necesario. Abajo a la derecha: lo encontró pero el modelo se lo inventó.
     Arriba a la derecha es lo deseable.</p>
  {G.leyenda_series([CAT_CORTA.get(c, c) for c in cats])}
  {G.dispersion(puntos, x_label="Cobertura del contexto (recuperación)",
                y_label="Fidelidad (generación)", grupos=cats)}""")

    if "faithfulness" in metricas and "n_citas" in df.columns:
        sub = df[["n_citas", "faithfulness", "Categoria", "ID", "user_input"]].dropna()
        # Si una de las dos series es constante la correlación no está definida
        # (numpy divide por una desviación típica de 0). Se comprueba antes para
        # no ensuciar la salida con RuntimeWarning y mostrar simplemente "—".
        variables = len(sub) > 2 and sub["n_citas"].std() > 0 and sub["faithfulness"].std() > 0
        corr = sub["n_citas"].corr(sub["faithfulness"]) if variables else float("nan")
        max_citas = max(int(sub["n_citas"].max()) if len(sub) else 1, 1)
        puntos = [(r["n_citas"], r["faithfulness"], r["Categoria"],
                   f"[{r['ID']}] {int(r['n_citas'])} citas · fidelidad {fmt(r['faithfulness'], 2)}")
                  for _, r in sub.iterrows()]
        bloques.append(f"""
  <h3>¿Sirve de algo obligar a citar?</h3>
  <p class="intro">El prompt exige marcar con <code>[n]</code> el fragmento del que sale
     cada afirmación. Si citar redujera la alucinación, los puntos subirían hacia la
     derecha. Correlación de Pearson: <strong>{fmt(corr, 2)}</strong>.</p>
  {G.dispersion(puntos, x_max=max_citas, x_label="Nº de fragmentos citados",
                y_label="Fidelidad", grupos=cats)}""")

    if not bloques:
        return ""
    return f'<section id="diagnostico"><h2>Diagnóstico</h2>{"".join(bloques)}</section>'


def ref_fragmentos_html(fila) -> str:
    """Los fragmentos recuperados como lista de identificadores, no como texto.

    En una tabla de análisis de errores lo que hace falta es saber *qué* se
    recuperó para poder ir a mirarlo; volcar los cinco fragmentos enteros
    (~9.500 caracteres) haría la tabla ilegible. El chunk_id basta para
    localizarlo en `respuestas_rag.csv` o con `cli/inspeccionar.py`.
    """
    bruto = fila.get("fragmentos") if hasattr(fila, "get") else None
    if not isinstance(bruto, str) or not bruto.strip():
        return ""
    ids = [t.strip() for t in bruto.split("|") if t.strip()]
    if not ids:
        return ""
    items = "".join(f"<li>{esc(i)}</li>" for i in ids)
    return (f'<p class="p-eti">Fragmentos recuperados</p>'
            f'<ol class="p-frags">{items}</ol>')


def bloque_peores(df: pd.DataFrame, metricas: list[str]) -> str:
    secciones = []
    for m in ("faithfulness", "factual_correctness"):
        if m not in metricas:
            continue
        peores = df.dropna(subset=[m]).nsmallest(10, m)
        filas = "".join(f"""
      <tr>
        <td class="col-id">{esc(r['ID'])}</td>
        <td class="col-nota">{fmt(r[m], 2)}</td>
        <td>
          <p class="p-preg">{esc(r['user_input'])}</p>
          <p class="p-eti">Referencia</p><p class="p-txt">{esc(str(r['reference'])[:320])}</p>
          <p class="p-eti">Respuesta del RAG{' · RECHAZO' if r['resultado'] == RECHAZO else ''}</p>
          <p class="p-txt">{esc(str(r['response'])[:320])}</p>
          {ref_fragmentos_html(r)}
        </td>
      </tr>""" for _, r in peores.iterrows())
        secciones.append(f"""
  <h3>Peores 10 en {esc(M.ETIQUETAS[m].lower())}</h3>
  <div class="envoltorio-tabla"><table class="tabla-peores">
    <thead><tr><th>ID</th><th>Nota</th><th>Pregunta, referencia y respuesta</th></tr></thead>
    <tbody>{filas}</tbody>
  </table></div>""")

    if not secciones:
        return ""
    return f"""
<section id="peores">
  <h2>Análisis de errores</h2>
  <p class="intro">Las preguntas donde el sistema falla más. Es el material para decidir
     qué tocar: el troceado, la recuperación o el prompt.</p>
  {"".join(secciones)}
</section>"""


def partes_configuracion(configuracion: str | None) -> tuple[str, str, str]:
    """(generador, juez, resto) de una línea de `configuracion.txt`.

    Sin fichero (corridas anteriores a él) se cae al entorno actual, que es lo
    único que hay, y se dice en el propio texto para que no pase por dato.
    """
    texto = configuracion or resumen_config()
    campos = texto.split(" · ", 2)
    valor = lambda campo: campo.split("=", 1)[1] if "=" in campo else campo  # noqa: E731
    generador = valor(campos[0]) if campos else "?"
    juez = valor(campos[1]) if len(campos) > 1 else "?"
    resto = campos[2] if len(campos) > 2 else ""
    if configuracion is None:
        resto += " (sin configuracion.txt: configuración del entorno actual)"
    return generador, juez, resto


def construir_html(df: pd.DataFrame, metricas: list[str],
                   configuracion: str | None = None) -> str:
    n_rech = int((df["resultado"] == RECHAZO).sum())
    generador, juez, resto = partes_configuracion(configuracion)
    return f"""<title>Evaluación del RAG de SSOO</title>
{FUENTES}
<style>{CSS}</style>
<div class="envoltorio">
<header class="portada">
  <p class="eyebrow">Evaluación con RAGAS</p>
  <h1>Qué tan bien responde el RAG</h1>
  <p class="subtitulo">{len(df)} preguntas sobre los apuntes de Sistemas Operativos,
     con respuesta de referencia escrita a mano, puntuadas por un modelo juez
     en siete dimensiones.</p>
  <p class="config">Generación <code>{esc(generador)}</code> ·
     juez <code>{esc(juez)}</code> con plantillas en español ·
     {esc(resto)}</p>
</header>

{tarjetas(df)}
{bloque_medias(df, metricas)}
{bloque_categorias(df, metricas)}
{bloque_rechazos(df, metricas)}
{bloque_distribuciones(df, metricas)}
{bloque_diagnostico(df, metricas)}
{bloque_peores(df, metricas)}

<footer>
  <p>Todas las métricas van de 0 a 1; más alto es mejor. Las notas las asigna un LLM juez
     con plantillas adaptadas al español, así que tienen algo de varianza entre corridas:
     sirven para comparar configuraciones, no como verdad absoluta.
     {'Los rechazos se cuentan como fallo porque todas las preguntas son in-corpus.'
      if n_rech else ''}</p>
  <p>Generado por <code>eval_ragas</code> a partir de <code>resultados_ragas.csv</code>.</p>
</footer>
</div>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Fase 3: informe visual de la evaluación.")
    ap.add_argument("--salida", help="ruta del HTML (por defecto data/ragas/informe_ragas.html)")
    args = ap.parse_args()

    df, metricas = cargar()
    destino = args.salida or INFORME_HTML
    html = construir_html(df, metricas, leer_configuracion(SALIDA_DIR))

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")

    print(f"Informe generado: {destino}")
    print(f"  {len(df)} preguntas · métricas: {', '.join(metricas)}")
    conteo = df["resultado"].value_counts().to_dict()
    print("  resultados: " + " · ".join(f"{k} {v}" for k, v in conteo.items()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ErrorConfiguracion as exc:
        raise SystemExit(f"ERROR: {exc}")
