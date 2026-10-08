"""
comparar.py — Informe comparativo entre dos corridas de la evaluación.

Lee `data/ragas/<corrida>/resultados_ragas.csv` de dos corridas, las alinea
pregunta a pregunta y produce `data/ragas/comparativa.html`, autocontenido.

No recalcula ninguna métrica: compara entregables ya producidos. Eso significa
que se puede ejecutar sin clave de API y sin gastar un céntimo.

Lo que hace comparables a las dos corridas es que todo menos una cosa es
idéntico: el mismo banco de 94 preguntas, el mismo índice, el mismo generador,
el mismo prompt y el mismo juez con los mismos embeddings. La variable es lo que
se esté probando (el reranker, el stemming…), y la configuración de cada
corrida (`configuracion.txt`) sale en la portada para comprobarlo.

Uso:
    python -m eval_ragas.comparar --corridas libre_base,libre_bge
    python -m eval_ragas.comparar --salida data/ragas/comparativa.html
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import pandas as pd

from eval_ragas import graficas as G
from eval_ragas import metricas as M
from eval_ragas.comun import (
    CAT_CORTA,
    COMPARATIVA_HTML,
    ERROR,
    NOMBRE_CONFIGURACION,
    NOMBRE_PUNTUACION,
    NOMBRE_RESULTADOS,
    OK,
    RAGAS_DIR,
    RECHAZO,
    campos_configuracion,
    categorias_presentes as _categorias_presentes,
    ruta_corrida,
)
from eval_ragas.estadistica import (
    MIN_PARES_RUIDO,
    MIN_PARES_WILCOXON,
    banda_ruido,
    holm,
    wilcoxon_pareado,
)
from eval_ragas.estilo import CSS, FUENTES
from eval_ragas.graficas import esc, fmt, fmt_signo, pct
from rag import ErrorConfiguracion

# ── Constantes del análisis ───────────────────────────────────────────────────
# Nivel de significación. Con 7 métricas a 0,05 la probabilidad de que al menos
# una salga «significativa» por azar ronda el 30 %, así que el informe da también
# el p corregido por Holm-Bonferroni y es ése el que hay que mirar.
ALFA = 0.05

# Un delta relativo sobre una media casi nula no informa de nada: pasar de 0,001
# a 0,002 imprimiría «+100 %». Por debajo de este umbral se deja en blanco.
MEDIA_MINIMA_PARA_PORCENTAJE = 0.01

# Las dos que encabezan el informe: una mide alucinación y la otra acierto.
METRICAS_CABECERA = ("faithfulness", "factual_correctness")

# Las que dependen directamente de qué se recuperó. Si el cambio que se prueba
# toca la recuperación (reranker, stemming), es aquí donde tiene que verse.
METRICAS_RECUPERACION = ("context_recall", "context_precision")


# ── Carga y alineado ──────────────────────────────────────────────────────────
def _clave_id(valor):
    """Orden numérico de los ID, con respaldo alfabético.

    `puntuar.py` ordena con `astype(int)` porque el banco numera del 1 al 94.
    Aquí se es tolerante a propósito: la comparativa lee ficheros ya escritos y
    no debería reventar por un ID que no sea un entero.
    """
    try:
        return (0, int(valor), "")
    except (TypeError, ValueError):
        return (1, 0, str(valor))


def descubrir_corridas() -> list[str]:
    """Las corridas que tienen entregable, en orden alfabético.

    El orden importa: la primera es la línea base (A) y los deltas son B − A.
    Para elegirlo a mano, `--corridas A,B`.
    """
    if not RAGAS_DIR.exists():
        return []
    return sorted(
        d.name for d in RAGAS_DIR.iterdir()
        if d.is_dir() and (d / NOMBRE_RESULTADOS).exists()
    )


def cargar_corrida(nombre: str) -> pd.DataFrame:
    """El entregable de una corrida, con ID como texto y métricas numéricas."""
    ruta = ruta_corrida(nombre) / NOMBRE_RESULTADOS
    if not ruta.exists():
        raise ErrorConfiguracion(
            f'No hay resultados de la corrida "{nombre}" en {ruta}.\n'
            f"Prodúcelos con:\n"
            f"  EVAL_CORRIDA={nombre} python -m eval_ragas.generar_respuestas\n"
            f"  EVAL_CORRIDA={nombre} python -m eval_ragas.puntuar"
        )
    df = pd.read_csv(ruta, dtype={"ID": str})
    for columna in [*M.ORDEN, "latencia_s", "n_citas", "n_docs"]:
        if columna in df.columns:
            df[columna] = pd.to_numeric(df[columna], errors="coerce")
    if "Categoria" in df.columns:
        df["Categoria"] = df["Categoria"].fillna("(sin categoría)")
    return df


def alinear(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Las filas comunes por ID, y los ID que sobran en cada lado.

    Se alinea por ID y no por posición: cada corrida se reanuda por su cuenta y
    puede tener las filas en otro orden o faltarle alguna. Sólo las comunes
    entran en las estadísticas; si no, las dos medias se calcularían sobre
    conjuntos de preguntas distintos y el delta no significaría nada.
    """
    ids_a, ids_b = set(a["ID"]), set(b["ID"])
    solo_a = sorted(ids_a - ids_b, key=_clave_id)
    solo_b = sorted(ids_b - ids_a, key=_clave_id)
    par = a.merge(b, on="ID", suffixes=("_a", "_b"))
    par = par.sort_values("ID", key=lambda s: s.map(_clave_id)).reset_index(drop=True)
    return par, solo_a, solo_b


# ── Aritmética de la comparación ──────────────────────────────────────────────
def pares_validos(par: pd.DataFrame, metrica: str, *,
                  solo_ok: bool = False) -> tuple[list[float], list[float]]:
    """Los pares (A, B) utilizables de una métrica, con la política de exclusión.

    Tres reglas, y cada una tiene su motivo:

    - Un `ERROR` en cualquiera de los dos lados tumba el par ENTERO. El informe
      de una corrida ya excluye los errores de sus medias, pero aquí hay que ir
      más lejos: una media sobre 94 preguntas frente a otra sobre 92 no es una
      comparación pareada.
    - Un `RECHAZO` se conserva. Las 94 preguntas son *in-corpus*, así que negarse
      a responder es un fallo del sistema, no un dato que falte. Con `solo_ok` se
      puede ver además la comparación restringida a donde ambas respondieron.
    - Un `NaN` descarta el par sólo para ESA métrica: es un fallo del juez, no del
      RAG, y rellenarlo con 0 convertiría una caída de la API en una regresión.
      De ahí que cada fila de la tabla lleve su propio n.
    """
    col_a, col_b = f"{metrica}_a", f"{metrica}_b"
    if col_a not in par.columns or col_b not in par.columns:
        return [], []

    util = par[(par["resultado_a"] != ERROR) & (par["resultado_b"] != ERROR)]
    if solo_ok:
        util = util[(util["resultado_a"] == OK) & (util["resultado_b"] == OK)]
    util = util[util[col_a].notna() & util[col_b].notna()]
    return util[col_a].tolist(), util[col_b].tolist()


def _sin_errores(par: pd.DataFrame) -> pd.DataFrame:
    """Pares comunes con una ejecución utilizable en ambos lados.

    Una fila `ERROR` no contiene una respuesta ni un contexto recuperado
    verificables; en fase 1 su latencia queda en 0. Incluirla en gráficas de
    fragmentos u operación convertiría ese fallo técnico en un dato del RAG.
    """
    if not {"resultado_a", "resultado_b"} <= set(par.columns):
        return par
    return par[(par["resultado_a"] != ERROR) & (par["resultado_b"] != ERROR)]


def comparar_metrica(par: pd.DataFrame, metrica: str, *, solo_ok: bool = False) -> dict:
    """Medias, delta, tamaño del efecto y test de una métrica."""
    x, y = pares_validos(par, metrica, solo_ok=solo_ok)
    n = len(x)
    if n == 0:
        return {"metrica": metrica, "n": 0, "media_a": None, "media_b": None,
                "delta": None, "delta_pct": None, "mediana_delta": None,
                "gana_b": None, "empates": None, "w": None, "p": None}

    media_a = sum(x) / n
    media_b = sum(y) / n
    delta = media_b - media_a
    diferencias = [vb - va for va, vb in zip(x, y)]
    w, p = wilcoxon_pareado(x, y)

    return {
        "metrica": metrica,
        "n": n,
        "media_a": media_a,
        "media_b": media_b,
        "delta": delta,
        # Sólo si la base no es casi cero; si no, el porcentaje engaña más que informa.
        "delta_pct": (delta / media_a) if media_a >= MEDIA_MINIMA_PARA_PORCENTAJE else None,
        # La mediana de las diferencias pareadas es el tamaño del efecto que el
        # p no da: dice cuánto, no sólo si.
        "mediana_delta": statistics.median(diferencias),
        "gana_b": sum(1 for d in diferencias if d > 0) / n,
        "empates": sum(1 for d in diferencias if d == 0) / n,
        "w": w,
        "p": p,
    }


def _conjunto_fragmentos(celda) -> set[str]:
    """Los chunk_id de una celda `fragmentos` ("id | id | id")."""
    if not isinstance(celda, str):
        return set()
    return {t.strip() for t in celda.split("|") if t.strip()}


def solape_fragmentos(par: pd.DataFrame) -> list[float]:
    """Por pregunta, |A ∩ B| / |A ∪ B| sobre los fragmentos recuperados.

    Es la única medida del informe que compara los dos recuperadores SIN pasar
    por el juez: no depende de ningún LLM, no tiene varianza de muestreo y no
    cuesta nada. Si el solape fuera 1,0, las dos corridas habrían leído
    exactamente lo mismo y cualquier diferencia en las métricas sería ruido del
    juez.
    """
    if "fragmentos_a" not in par.columns or "fragmentos_b" not in par.columns:
        return []
    valores = []
    util = _sin_errores(par)
    for celda_a, celda_b in zip(util["fragmentos_a"], util["fragmentos_b"]):
        sa, sb = _conjunto_fragmentos(celda_a), _conjunto_fragmentos(celda_b)
        if not sa and not sb:
            continue
        valores.append(len(sa & sb) / len(sa | sb))
    return valores


# ── Banda de ruido ────────────────────────────────────────────────────────────
# Ni el generador ni el juez son deterministas, así que dos corridas IDÉNTICAS
# tampoco dan las mismas notas. Para saber si un Δ es un efecto o ruido hay que
# medir cuánto se mueve la nota cuando no cambia nada. Dos fuentes, por orden
# de preferencia:
#  - una réplica A/A (la misma configuración lanzada dos veces): todas sus
#    preguntas son ruido puro;
#  - dos corridas con el mismo generador cuyas preguntas recibieron EXACTAMENTE
#    el mismo contexto: en esas, lo que cambie es ruido del generador y del juez.
#    Medido en libre_conciso frente a libre_conciso_stemming: 68 de 94 preguntas
#    con el mismo contexto en el mismo orden, sólo 3 respuestas idénticas y la F1
#    movida en 47, con una desviación típica por pregunta de 0,176.
CORRIDAS_RUIDO = (
    ("libre_conciso", "libre_conciso_r2", True),         # réplica A/A: todas
    ("libre_conciso", "libre_conciso_stemming", False),  # sólo contextos idénticos
)


def contextos_identicos(par: pd.DataFrame) -> pd.Series:
    """Por fila, ¿las dos corridas llevaron la misma lista ordenada de fragmentos?

    Ordenada, no como conjunto: el orden decide qué número [n] lleva cada
    fragmento en el prompt, así que dos contextos con los mismos fragmentos en
    otro orden no son el mismo prompt.
    """
    if "fragmentos_a" not in par.columns or "fragmentos_b" not in par.columns:
        return pd.Series(False, index=par.index)

    def lista(celda):
        return [t.strip() for t in celda.split("|")] if isinstance(celda, str) else None

    return pd.Series([
        la is not None and la == lb
        for la, lb in zip(par["fragmentos_a"].map(lista), par["fragmentos_b"].map(lista))
    ], index=par.index)


def ruido_por_metrica(par: pd.DataFrame, metricas: list[str], *,
                      todas: bool = False) -> dict[str, dict]:
    """Desviación típica de las diferencias pareadas cuando nada ha cambiado.

    Con `todas=False` usa sólo las filas con contexto idéntico (ver
    `contextos_identicos`); con `todas=True`, todas, que es lo correcto para
    una réplica A/A. Excluye ERROR y NaN como el resto de la comparativa.
    Devuelve {métrica: {"n", "sd"}} sólo para las que tienen al menos
    `MIN_PARES_RUIDO` pares.
    """
    util = _sin_errores(par)
    if not todas:
        util = util[contextos_identicos(util)]
    salida = {}
    for m in metricas:
        col_a, col_b = f"{m}_a", f"{m}_b"
        if col_a not in util.columns or col_b not in util.columns:
            continue
        dif = (util[col_b] - util[col_a]).dropna()
        if len(dif) >= MIN_PARES_RUIDO:
            salida[m] = {"n": int(len(dif)), "sd": float(dif.std(ddof=1))}
    return salida


def ruido_de_referencia(metricas: list[str]) -> tuple[str | None, dict[str, dict]]:
    """La mejor estimación de ruido disponible en `data/ragas/`, y de dónde sale."""
    for base, otra, todas in CORRIDAS_RUIDO:
        try:
            par, _, _ = alinear(cargar_corrida(base), cargar_corrida(otra))
        except ErrorConfiguracion:
            continue
        ruido = ruido_por_metrica(par, metricas, todas=todas)
        if ruido:
            modo = "réplica A/A" if todas else "preguntas con contexto idéntico"
            return f"{base} / {otra} ({modo})", ruido
    return None, {}


def mismo_generador(a: str, b: str) -> bool:
    """¿Las dos corridas generaron con el mismo modelo y el mismo estilo?

    Sólo entonces las preguntas con contexto idéntico son ruido: si cambió el
    generador (la comparativa de pago frente a gratuito), el contexto es el mismo
    en todas y la diferencia es justamente el efecto que se mide.
    """
    ca, cb = campos_configuracion(ficha_corrida(a)), campos_configuracion(ficha_corrida(b))
    return bool(ca) and all(ca.get(k) == cb.get(k) for k in ("modelo RAG", "estilo"))


# ── Presentación ──────────────────────────────────────────────────────────────
def ficha_corrida(nombre: str) -> str:
    """La configuración con la que se generó una corrida, para la portada."""
    ruta = ruta_corrida(nombre) / NOMBRE_CONFIGURACION
    if not ruta.exists():
        return "configuración no registrada"
    return ruta.read_text(encoding="utf-8").strip()


def ficha_juez(nombre: str) -> str | None:
    """Con qué juez se puntuó una corrida (`puntuacion.txt`), o None si no consta."""
    ruta = ruta_corrida(nombre) / NOMBRE_PUNTUACION
    return ruta.read_text(encoding="utf-8").strip() if ruta.exists() else None


def aviso_jueces(a: str, b: str) -> str | None:
    """Un aviso si las dos corridas no se puntuaron con el mismo juez.

    Es el invariante 6 visto desde la comparativa: si el metro cambió, el Δ
    mezcla el sistema con la regla. Las corridas anteriores a `puntuacion.txt`
    no dejan constancia, y eso también se dice en lugar de suponerlo.
    """
    ja, jb = ficha_juez(a), ficha_juez(b)
    if ja and jb and ja != jb:
        return (f"Las dos corridas se puntuaron con jueces o plantillas distintos "
                f"(A: {ja} — B: {jb}). Las diferencias no son atribuibles sólo al RAG: "
                f"repuntúa una de las dos con el juez de la otra.")
    if not ja or not jb:
        return ("Alguna de las dos corridas es anterior a puntuacion.txt, así que no "
                "consta con qué juez se puntuó. Todas las corridas libre_* se "
                "puntuaron con Qwen3.8 sin razonamiento, pero no queda registrado.")
    return None


def _texto_fragmentos(fila, sufijo: str) -> str:
    """La celda `fragmentos` de un lado, o una raya.

    No vale `fila.get(col) or "—"`: una celda vacía llega de pandas como `NaN`,
    que es un float y es *verdadero*, así que se colaría un «nan» en la tabla.
    """
    valor = fila.get(f"fragmentos_{sufijo}")
    return valor if isinstance(valor, str) and valor.strip() else "—"


def _clase_delta(valor) -> str:
    if valor is None or valor == 0:
        return ""
    return "delta-pos" if valor > 0 else "delta-neg"


def _marca_p(fila: dict) -> str:
    """El p con su asterisco si la n es demasiado pequeña para fiarse."""
    if fila["p"] is None:
        return "—"
    texto = f"{fila['p']:.3f}".replace(".", ",")
    if fila["n"] < MIN_PARES_WILCOXON:
        return f"{texto} <abbr title='n &lt; {MIN_PARES_WILCOXON} pares'>*</abbr>"
    return texto


# Estilos propios de este informe. Lo demás sale de `estilo.py`, compartido con
# el informe de una corrida.
CSS_EXTRA = """
.delta-pos { color:var(--status-good); font-weight:600; }
.delta-neg { color:var(--status-critical); font-weight:600; }
.sig { font-weight:600; }
.tabla-comparativa td, .tabla-comparativa th { white-space:nowrap; }
.tabla-comparativa td.metrica { white-space:normal; }
.par-frags { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:6px; }
.par-frags > div { min-width:0; }
.par-frags h4 { margin:0 0 4px; font-size:0.78rem; text-transform:uppercase;
  letter-spacing:0.04em; color:var(--muted); }
"""


def bloque_portada(corridas: tuple[str, str], par: pd.DataFrame,
                   solo_a: list[str], solo_b: list[str]) -> str:
    a, b = corridas
    desparejados = ""
    if solo_a or solo_b:
        detalle = []
        if solo_a:
            detalle.append(f"{len(solo_a)} sólo en {esc(a)} "
                           f"({esc(', '.join(solo_a[:8]))}{'…' if len(solo_a) > 8 else ''})")
        if solo_b:
            detalle.append(f"{len(solo_b)} sólo en {esc(b)} "
                           f"({esc(', '.join(solo_b[:8]))}{'…' if len(solo_b) > 8 else ''})")
        desparejados = f"""
<aside class="nota tono-aviso">
  <p class="nota-titulo">Las dos corridas no cubren las mismas preguntas</p>
  <p>{'; '.join(detalle)}. Esas preguntas quedan fuera de la comparación: una media
     sobre un conjunto y otra sobre otro no serían comparables. Para cerrarlas,
     relanza la fase que falte —se reanuda sola.</p>
</aside>"""

    aviso_juez = aviso_jueces(a, b)
    if aviso_juez:
        desparejados += f"""
<aside class="nota tono-aviso">
  <p class="nota-titulo">El instrumento de medida</p>
  <p>{esc(aviso_juez)}</p>
</aside>"""

    preguntas_validas = len(_sin_errores(par))
    return f"""
<header class="portada">
  <p class="eyebrow">Comparativa entre dos corridas</p>
  <h1>{esc(a)} frente a {esc(b)}</h1>
  <p class="subtitulo">Hay {len(par)} IDs comunes; {preguntas_validas} preguntas
     comparables tras excluir las filas con <code>ERROR</code>. Entre una corrida y
     la otra debe cambiar <strong>una sola cosa</strong>: compruébalo en la
     configuración de cada una.</p>
  <p class="config">A · <code>{esc(a)}</code> — {esc(ficha_corrida(a))}</p>
  <p class="config">B · <code>{esc(b)}</code> — {esc(ficha_corrida(b))}</p>
</header>

<section id="protocolo">
  <h2>Qué se ha mantenido fijo</h2>
  <p class="intro">Una comparación sólo significa algo si todo lo demás es idéntico:</p>
  <ul>
    <li><strong>El corpus y el índice</strong>: los mismos fragmentos, troceados
        igual, con el mismo modelo de embeddings, la misma dimensión y la misma
        distancia.</li>
    <li><strong>El generador y el prompt</strong>, con temperatura 0.</li>
    <li><strong>El juez y sus embeddings</strong>. Si cambiaran, una diferencia
        podría venir de la regla con la que se mide y no del sistema medido. El
        sistema bajo prueba cambia; el metro, nunca.</li>
  </ul>
</section>
{desparejados}"""


def bloque_tarjetas(par: pd.DataFrame, filas: list[dict]) -> str:
    por_metrica = {f["metrica"]: f for f in filas}
    tarjetas = []

    for metrica in METRICAS_CABECERA:
        fila = por_metrica.get(metrica)
        if not fila or fila["delta"] is None:
            continue
        tono = "tono-ok" if fila["delta"] > 0 else ("tono-mal" if fila["delta"] < 0 else "")
        tarjetas.append(
            f'<div class="tarjeta {tono}"><div class="tarjeta-valor">'
            f'{fmt_signo(fila["delta"])}</div>'
            f'<div class="tarjeta-etiqueta">{esc(M.ETIQUETAS[metrica])}</div>'
            f'<div class="tarjeta-nota">{fmt(fila["media_a"])} → {fmt(fila["media_b"])}</div></div>'
        )

    validos = [f for f in filas if f["gana_b"] is not None]
    if validos:
        media_gana = sum(f["gana_b"] for f in validos) / len(validos)
        tarjetas.append(
            f'<div class="tarjeta"><div class="tarjeta-valor">{pct(media_gana)}</div>'
            f'<div class="tarjeta-etiqueta">Gana B</div>'
            f'<div class="tarjeta-nota">de las comparaciones pregunta a pregunta</div></div>'
        )

    solapes = solape_fragmentos(par)
    if solapes:
        tarjetas.append(
            f'<div class="tarjeta"><div class="tarjeta-valor">'
            f'{pct(sum(solapes) / len(solapes))}</div>'
            f'<div class="tarjeta-etiqueta">Solape de fragmentos</div>'
            f'<div class="tarjeta-nota">de lo que recupera cada una</div></div>'
        )

    tarjetas.append(
        f'<div class="tarjeta"><div class="tarjeta-valor">{len(_sin_errores(par))}</div>'
        f'<div class="tarjeta-etiqueta">Pares sin ERROR</div>'
        f'<div class="tarjeta-nota">comunes y utilizables en ambas corridas</div></div>'
    )
    return f'<div class="tarjetas">{"".join(tarjetas)}</div>'


def bloque_tabla_principal(filas: list[dict], corridas: tuple[str, str],
                           filas_ok: list[dict]) -> str:
    a, b = corridas
    pes_holm = holm([f["p"] for f in filas])
    deltas = [(M.ETIQUETAS[f["metrica"]], f["delta"],
               f"n={f['n']}") for f in filas]

    etiquetas = [M.ETIQUETAS[f["metrica"]] for f in filas]
    series = [
        (a, [f["media_a"] for f in filas]),
        (b, [f["media_b"] for f in filas]),
    ]

    cuerpo = []
    for fila, p_holm in zip(filas, pes_holm):
        significativo = p_holm is not None and p_holm < ALFA
        cuerpo.append(
            f"<tr><td class='metrica'>{esc(M.ETIQUETAS[fila['metrica']])}</td>"
            f"<td>{fmt(fila['media_a'])}</td>"
            f"<td>{fmt(fila['media_b'])}</td>"
            f"<td class='{_clase_delta(fila['delta'])}'>{fmt_signo(fila['delta'])}</td>"
            f"<td>{pct(fila['delta_pct']) if fila['delta_pct'] is not None else '—'}</td>"
            f"<td>{fmt_signo(fila['mediana_delta'])}</td>"
            f"<td>{pct(fila['gana_b'])}</td>"
            f"<td>{fila['n']}</td>"
            f"<td>{_marca_p(fila)}</td>"
            f"<td class='{'sig' if significativo else ''}'>"
            f"{fmt(p_holm) if p_holm is not None else '—'}</td></tr>"
        )

    cuerpo_ok = "".join(
        f"<tr><th scope='row'>{esc(M.ETIQUETAS[f['metrica']])}</th>"
        f"<td>{fmt(f['media_a'])}</td><td>{fmt(f['media_b'])}</td>"
        f"<td class='{_clase_delta(f['delta'])}'>{fmt_signo(f['delta'])}</td>"
        f"<td>{f['n']}</td></tr>"
        for f in filas_ok
    )

    return f"""
<section id="tabla">
  <h2>Métrica a métrica</h2>
  <p class="intro">Δ es <strong>B − A</strong>: positivo significa que
     {esc(b)} puntúa más alto. Cada fila lleva su propio número de
     pares porque un fallo del juez en una métrica no invalida las demás.</p>
  {G.barras_divergentes(deltas)}
  <div class="envoltorio-tabla"><table class="tabla-comparativa">
    <thead><tr>
      <th>Métrica</th>
      <th>A · {esc(a)}</th>
      <th>B · {esc(b)}</th>
      <th>Δ</th><th>Δ %</th><th>Mediana Δ</th><th>Gana B</th><th>n</th>
      <th>p</th><th>p (Holm)</th>
    </tr></thead>
    <tbody>{"".join(cuerpo)}</tbody>
  </table></div>

  <aside class="nota">
    <p class="nota-titulo">Cómo leer el p</p>
    <p>Test de Wilcoxon de rangos con signo, <strong>pareado</strong>: las dos corridas
       responden a las mismas preguntas, así que cada pregunta es su propio control y
       la enorme variación entre preguntas fáciles y difíciles se cancela por
       construcción. Se contrastan siete métricas a la vez, y con α = {fmt(ALFA, 2)}
       eso deja cerca de un 30 % de probabilidad de que alguna salga «significativa»
       por azar: la columna <strong>p (Holm)</strong> ya lo corrige, y es la que hay
       que mirar. Un Δ pequeño con p alto significa «no se ha podido distinguir del
       ruido», no «son iguales».</p>
  </aside>

  <h3>Las medias, lado a lado</h3>
  {G.leyenda_series([a, b])}
  {G.barras_agrupadas(etiquetas, series)}

  <details class="tabla-vista"><summary>Ver sólo las preguntas que ambas respondieron</summary>
    <p class="intro">Un rechazo es un fallo —las 94 preguntas están en el corpus—, así
       que cuenta en la tabla de arriba. Esta segunda vista deja fuera los pares en los
       que alguna de las dos se negó a responder, para separar «recupera peor» de
       «recupera tan mal que ni lo intenta».</p>
    <div class="envoltorio-tabla"><table>
      <thead><tr><th>Métrica</th><th>A</th><th>B</th><th>Δ</th><th>n</th></tr></thead>
      <tbody>{cuerpo_ok}</tbody>
    </table></div>
  </details>
</section>"""


def bloque_por_categoria(par: pd.DataFrame, corridas: tuple[str, str]) -> str:
    a, b = corridas
    util = _sin_errores(par)
    cats = _categorias_presentes(sorted(set(util["Categoria_a"].dropna())))
    if not cats:
        return ""

    secciones = []
    for metrica in METRICAS_RECUPERACION:
        col_a, col_b = f"{metrica}_a", f"{metrica}_b"
        if col_a not in par.columns:
            continue
        series = [
            (a, [util[util["Categoria_a"] == c][col_a].mean() for c in cats]),
            (b, [util[util["Categoria_a"] == c][col_b].mean() for c in cats]),
        ]
        secciones.append(
            f"<h3>{esc(M.ETIQUETAS[metrica])}</h3>"
            f"<p class='intro'>{esc(M.DESCRIPCIONES[metrica])}</p>"
            + G.barras_agrupadas([CAT_CORTA.get(c, c) for c in cats], series)
        )

    if not secciones:
        return ""

    return f"""
<section id="categorias">
  <h2>Dónde se nota, por tipo de pregunta</h2>
  <p class="intro">Éstas son las métricas que dependen directamente de qué fragmentos
     se recuperaron. Un cambio en la recuperación no tiene por qué afectar igual a
     todas las categorías: las preguntas de síntesis y de inferencia comparten menos
     palabras con los apuntes, así que dependen más de la búsqueda semántica y del
     reordenado.</p>
  {G.leyenda_series([a, b])}
  {"".join(secciones)}
</section>"""


def bloque_dispersion(par: pd.DataFrame, corridas: tuple[str, str]) -> str:
    a, b = corridas
    util = _sin_errores(par)
    cats = _categorias_presentes(sorted(set(util["Categoria_a"].dropna())))
    graficas = []

    for metrica in (*METRICAS_CABECERA, *METRICAS_RECUPERACION):
        col_a, col_b = f"{metrica}_a", f"{metrica}_b"
        if col_a not in par.columns:
            continue
        datos = util[util[col_a].notna() & util[col_b].notna()]
        puntos = [
            (fila[col_a], fila[col_b], fila["Categoria_a"],
             f"#{fila['ID']} · {CAT_CORTA.get(fila['Categoria_a'], fila['Categoria_a'])}\n"
             f"A {fmt(fila[col_a])} · B {fmt(fila[col_b])}")
            for _, fila in datos.iterrows()
        ]
        graficas.append(
            f"<div><h3>{esc(M.ETIQUETAS[metrica])}</h3>"
            + G.dispersion(puntos, grupos=cats, diagonal=True,
                           x_label=f"A · {a}",
                           y_label=f"B · {b}")
            + "</div>"
        )

    if not graficas:
        return ""

    return f"""
<section id="dispersion">
  <h2>Pregunta a pregunta</h2>
  <p class="intro">Cada punto es una pregunta: su nota en A contra su nota en B. La
     línea de puntos es el empate, así que todo lo que queda <strong>por encima</strong>
     es una pregunta en la que gana {esc(b)}. Una media puede esconder
     que las dos corridas aciertan y fallan en preguntas distintas; aquí se ve.</p>
  {G.leyenda_series([CAT_CORTA.get(c, c) for c in cats])}
  {"".join(graficas)}
</section>"""


def elegir_ruido(par: pd.DataFrame, corridas: tuple[str, str],
                 metricas: list[str]) -> tuple[str | None, dict[str, dict]]:
    """La estimación de ruido para esta comparativa, y de dónde sale.

    Si las dos corridas generan igual y comparten bastantes contextos idénticos,
    la propia comparativa trae su ruido, que es el más pertinente. Si no, se usa
    la referencia de `CORRIDAS_RUIDO`.
    """
    a, b = corridas
    if mismo_generador(a, b):
        propio = ruido_por_metrica(par, metricas)
        if propio:
            return "esta misma comparativa (preguntas con contexto idéntico)", propio
    return ruido_de_referencia(metricas)


def bloque_ruido(filas: list[dict], fuente: str | None, ruido: dict[str, dict]) -> str:
    if not ruido:
        return ""
    cuerpo = []
    for f in filas:
        r = ruido.get(f["metrica"])
        banda = banda_ruido(r["sd"] if r else None, f["n"])
        if banda is None or f["delta"] is None:
            veredicto, texto_banda = "—", "—"
        else:
            texto_banda = f"±{fmt(banda)}"
            veredicto = ("fuera: mayor que el ruido" if abs(f["delta"]) > banda
                         else "dentro: indistinguible de relanzar")
        cuerpo.append(
            f"<tr><td class='metrica'>{esc(M.ETIQUETAS[f['metrica']])}</td>"
            f"<td>{f['n']}</td><td class='{_clase_delta(f['delta'])}'>{fmt_signo(f['delta'])}</td>"
            f"<td>{texto_banda}</td><td>{fmt(r['sd']) if r else '—'}</td>"
            f"<td>{esc(veredicto)}</td></tr>"
        )
    return f"""
<section id="ruido">
  <h2>¿Es más grande que el ruido?</h2>
  <p class="intro">Ni el generador ni el juez son deterministas: la misma
     configuración lanzada dos veces tampoco da las mismas notas. La banda es el Δ
     medio que saldría al 95 % <em>sin cambiar nada</em>, con la desviación típica
     del ruido medida en {esc(fuente or '—')}. Un Δ dentro de la banda no es un
     efecto aunque su p sea bajo; uno fuera, sí supera lo que da relanzar.</p>
  <div class="envoltorio-tabla"><table class="tabla-comparativa">
    <thead><tr><th>Métrica</th><th>n</th><th>Δ B−A</th><th>Banda de ruido</th>
      <th>DT del ruido</th><th>Lectura</th></tr></thead>
    <tbody>{''.join(cuerpo)}</tbody>
  </table></div>
</section>"""


def bloque_solape(par: pd.DataFrame, corridas: tuple[str, str]) -> str:
    solapes = solape_fragmentos(par)
    if not solapes:
        return ""
    a, b = corridas
    identicos = sum(1 for s in solapes if s == 1.0)
    disjuntos = sum(1 for s in solapes if s == 0.0)

    return f"""
<section id="solape">
  <h2>¿Recuperan lo mismo?</h2>
  <p class="intro">La medida más limpia del informe, y la única que no pasa por el juez:
     de los fragmentos que cada corrida llevó al contexto, qué proporción comparten
     (intersección entre unión). No depende de ningún LLM y no tiene varianza de
     muestreo: si saliera 100 %, las dos corridas habrían leído exactamente lo mismo y
     cualquier diferencia en las métricas sería ruido del juez, no del recuperador.</p>
  <div class="tarjetas">
    <div class="tarjeta"><div class="tarjeta-valor">{pct(sum(solapes) / len(solapes))}</div>
      <div class="tarjeta-etiqueta">Solape medio</div></div>
    <div class="tarjeta"><div class="tarjeta-valor">{pct(statistics.median(solapes))}</div>
      <div class="tarjeta-etiqueta">Mediana</div></div>
    <div class="tarjeta"><div class="tarjeta-valor">{identicos}</div>
      <div class="tarjeta-etiqueta">Idénticos</div>
      <div class="tarjeta-nota">mismo contexto exacto</div></div>
    <div class="tarjeta"><div class="tarjeta-valor">{disjuntos}</div>
      <div class="tarjeta-etiqueta">Sin nada en común</div>
      <div class="tarjeta-nota">ni un fragmento compartido</div></div>
  </div>
  {G.histograma(solapes, ancho=680, alto=200)}
  <p class="mini-nota">Distribución del solape sobre las {len(solapes)} preguntas
     pareadas. A la izquierda, preguntas donde {esc(a)} y
     {esc(b)} leyeron cosas distintas; a la derecha, donde
     coincidieron.</p>
</section>"""


def bloque_operacion(par: pd.DataFrame, corridas: tuple[str, str]) -> str:
    a, b = corridas
    utilizables = _sin_errores(par)

    def celda(sufijo: str, columna: str, formateador=fmt):
        col = f"{columna}_{sufijo}"
        if col not in utilizables.columns:
            return "—"
        return formateador(utilizables[col].mean())

    def cuenta(sufijo: str, estado: str) -> int:
        # Los errores se muestran aparte; los rechazos sólo cuentan entre los
        # pares que sí se pueden comparar.
        datos = par if estado == ERROR else utilizables
        return int((datos[f"resultado_{sufijo}"] == estado).sum())

    filas = [
        ("Latencia media por respuesta",
         f"{celda('a', 'latencia_s', lambda v: fmt(v, 2))} s",
         f"{celda('b', 'latencia_s', lambda v: fmt(v, 2))} s"),
        ("Citas por respuesta",
         celda("a", "n_citas", lambda v: fmt(v, 2)),
         celda("b", "n_citas", lambda v: fmt(v, 2))),
        ("Rechazos", str(cuenta("a", RECHAZO)), str(cuenta("b", RECHAZO))),
        ("Errores de la API", str(cuenta("a", ERROR)), str(cuenta("b", ERROR))),
    ]
    cuerpo = "".join(
        f"<tr><th scope='row'>{esc(t)}</th><td>{esc(va)}</td><td>{esc(vb)}</td></tr>"
        for t, va, vb in filas
    )

    return f"""
<section id="operacion">
  <h2>Coste y operación</h2>
  <div class="envoltorio-tabla"><table>
    <thead><tr><th></th><th>A · {esc(a)}</th>
      <th>B · {esc(b)}</th></tr></thead>
    <tbody>{cuerpo}</tbody>
  </table></div>
  <aside class="nota">
    <p class="nota-titulo">La latencia es indicativa, no concluyente</p>
    <p>Es de punta a punta, y el generador es el mismo en las dos corridas, así que la
       diferencia <em>debería</em> venir de lo que cambia en la recuperación (un
       reranker más grande, por ejemplo). Pero son dos corridas ejecutadas en momentos
       distintos, contra un servicio compartido con carga distinta: sirve para detectar
       un orden de magnitud, no para afirmar que una es más rápida que la otra.</p>
  </aside>
</section>"""


def bloque_discrepancias(par: pd.DataFrame, corridas: tuple[str, str], top: int) -> str:
    a, b = corridas
    secciones = []
    util = _sin_errores(par)

    for metrica in METRICAS_CABECERA:
        col_a, col_b = f"{metrica}_a", f"{metrica}_b"
        if col_a not in par.columns:
            continue
        datos = util[util[col_a].notna() & util[col_b].notna()].copy()
        if datos.empty:
            continue
        datos["_delta"] = datos[col_b] - datos[col_a]
        peores = datos.reindex(datos["_delta"].abs().sort_values(ascending=False).index).head(top)

        filas = "".join(
            f"<tr><td class='col-id'>#{esc(f['ID'])}</td>"
            f"<td class='col-nota'>{fmt(f[col_a])}</td>"
            f"<td class='col-nota'>{fmt(f[col_b])}</td>"
            f"<td class='col-nota {_clase_delta(f['_delta'])}'>{fmt_signo(f['_delta'])}</td>"
            f"<td><p class='p-preg'>{esc(f['user_input_a'])}</p>"
            f"<div class='par-frags'>"
            f"<div><h4>A · {esc(a)}</h4>"
            f"<p class='p-frags'>{esc(_texto_fragmentos(f, 'a'))}</p></div>"
            f"<div><h4>B · {esc(b)}</h4>"
            f"<p class='p-frags'>{esc(_texto_fragmentos(f, 'b'))}</p></div>"
            f"</div></td></tr>"
            for _, f in peores.iterrows()
        )
        secciones.append(
            f"<h3>{esc(M.ETIQUETAS[metrica])}</h3>"
            f"<div class='envoltorio-tabla'><table class='tabla-peores'>"
            f"<thead><tr><th>ID</th><th>A</th><th>B</th><th>Δ</th>"
            f"<th>Pregunta y fragmentos recuperados</th></tr></thead>"
            f"<tbody>{filas}</tbody></table></div>"
        )

    if not secciones:
        return ""

    return f"""
<section id="discrepancias">
  <h2>Dónde más discrepan</h2>
  <p class="intro">Las {top} preguntas con mayor |Δ| en cada métrica de cabecera, con los
     fragmentos que llevó cada corrida al contexto. Es la parte del informe que dice
     <em>por qué</em>: comparando las dos listas de fragmentos se ve qué trajo una
     corrida que la otra no llevó al contexto.</p>
  {"".join(secciones)}
</section>"""


def construir_html(par: pd.DataFrame, corridas: tuple[str, str],
                   solo_a: list[str], solo_b: list[str],
                   metricas: list[str], top: int) -> str:
    filas = [comparar_metrica(par, m) for m in metricas]
    filas_ok = [comparar_metrica(par, m, solo_ok=True) for m in metricas]
    a, b = corridas
    fuente_ruido, ruido = elegir_ruido(par, corridas, metricas)

    return f"""<title>{esc(a)} frente a {esc(b)} — comparativa</title>
{FUENTES}
<style>{CSS}{CSS_EXTRA}</style>
<div class="envoltorio">
{bloque_portada(corridas, par, solo_a, solo_b)}
{bloque_tarjetas(par, filas)}
{bloque_tabla_principal(filas, corridas, filas_ok)}
{bloque_ruido(filas, fuente_ruido, ruido)}
{bloque_solape(par, corridas)}
{bloque_por_categoria(par, corridas)}
{bloque_dispersion(par, corridas)}
{bloque_operacion(par, corridas)}
{bloque_discrepancias(par, corridas, top)}
<footer>
  <p>Generado con <code>python -m eval_ragas.comparar</code> a partir de los entregables
     de cada corrida. No se ha recalculado ninguna métrica: este informe no llama a
     ninguna API.</p>
  <p>Corrida A: <code>data/ragas/{esc(a)}/{esc(NOMBRE_RESULTADOS)}</code> ·
     corrida B: <code>data/ragas/{esc(b)}/{esc(NOMBRE_RESULTADOS)}</code>.</p>
</footer>
</div>"""


# ── CLI ───────────────────────────────────────────────────────────────────────
def elegir_corridas(pedidas: str | None) -> tuple[str, str]:
    """Las dos corridas a comparar, pedidas o descubiertas."""
    if pedidas:
        nombres = [n.strip().lower() for n in pedidas.split(",") if n.strip()]
        if len(nombres) != 2:
            raise ErrorConfiguracion(
                f"Se comparan dos corridas a la vez y se han pedido {len(nombres)}: "
                f"{', '.join(nombres) or 'ninguna'}. La forma es --corridas A,B."
            )
        return nombres[0], nombres[1]

    disponibles = descubrir_corridas()
    if len(disponibles) != 2:
        cuantas = f"{len(disponibles)} ({', '.join(disponibles)})" if disponibles else "ninguna"
        pista = ("Elige cuáles con --corridas A,B."
                 if len(disponibles) > 2 else
                 "Cada corrida se produce poniendo EVAL_CORRIDA=<nombre> delante "
                 "de `python -m eval_ragas.generar_respuestas` y de "
                 "`python -m eval_ragas.puntuar`.")
        raise ErrorConfiguracion(
            f"Se comparan dos corridas y en data/ragas/ hay {cuantas}.\n{pista}"
        )
    return disponibles[0], disponibles[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Informe HTML que compara dos corridas de la evaluación.",
    )
    parser.add_argument("--corridas", default=None,
                        help="Las dos corridas a comparar, separadas por coma "
                             "(por defecto, las dos que haya en data/ragas/)")
    parser.add_argument("--salida", type=Path, default=COMPARATIVA_HTML,
                        help="Fichero HTML de salida")
    parser.add_argument("--top-discrepancias", type=int, default=10,
                        help="Cuántas preguntas listar en «dónde más discrepan»")
    args = parser.parse_args()

    try:
        a, b = elegir_corridas(args.corridas)
        df_a, df_b = cargar_corrida(a), cargar_corrida(b)
        par, solo_a, solo_b = alinear(df_a, df_b)

        if par.empty:
            raise ErrorConfiguracion(
                f'Las corridas "{a}" y "{b}" no comparten ninguna pregunta por ID. '
                f"¿Se han generado contra el mismo banco?"
            )

        metricas = [m for m in M.ORDEN if f"{m}_a" in par.columns and f"{m}_b" in par.columns]
        if not metricas:
            raise ErrorConfiguracion(
                "Ninguna de las dos corridas tiene métricas puntuadas en común. "
                "Ejecuta `python -m eval_ragas.puntuar` en cada una."
            )

        html = construir_html(par, (a, b), solo_a, solo_b, metricas, args.top_discrepancias)
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(html, encoding="utf-8")
    except ErrorConfiguracion as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"Comparativa de «{a}» y «{b}»: {len(par)} IDs comunes, "
          f"{len(_sin_errores(par))} preguntas sin ERROR, {len(metricas)} métricas.")
    if solo_a or solo_b:
        print(f"  Sin parear: {len(solo_a)} sólo en {a}, {len(solo_b)} sólo en {b}.")
    print(f"Informe escrito en {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
