"""
puntuar.py — Fase 2: puntúa con RAGAS las respuestas ya generadas.

Lee `data/ragas/respuestas_rag.csv` (fase 1) y produce el entregable,
`data/ragas/resultados_ragas.csv`: una fila por pregunta con la pregunta, el
ground truth, la respuesta del RAG y una columna por métrica.

No vuelve a ejecutar el RAG. Eso permite reajustar métricas sin repetir el coste
de generación.

Uso:
    python -m eval_ragas.puntuar
    python -m eval_ragas.puntuar --limit 3
    python -m eval_ragas.puntuar --metricas faithfulness,context_recall
    python -m eval_ragas.puntuar --reset
"""

from __future__ import annotations

import argparse
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="ragas")

import pandas as pd  # noqa: E402

from eval_ragas import metricas as M  # noqa: E402
from eval_ragas.comun import (  # noqa: E402
    PROMPTS_ES_DIR,
    PUNTUACION_TXT,
    RESPUESTAS_CSV,
    RESULTADOS_CSV,
    SALIDA_DIR,
    build_embeddings_juez,
    build_juez,
    leer_configuracion,
    load_json,
    ref_fragmentos,
    resumen_juez,
)
from rag import ErrorConfiguracion, quitar_citas  # noqa: E402

# Columnas que se arrastran desde la fase 1 al entregable.
#
# Va `fragmentos` (los chunk_id separados por " | ") y NO `retrieved_contexts`
# con el texto íntegro: son ~9.500 caracteres por fila que dejan la hoja de
# cálculo ilegible. El texto completo sigue en `respuestas_rag.csv`, y el
# chunk_id es la referencia para ir a buscarlo allí o con `cli/inspeccionar.py`.
COLS_BASE = [
    "ID", "Categoria", "user_input", "reference", "response",
    "fragmentos", "resultado", "es_rechazo",
    "n_citas", "n_docs", "latencia_s",
]

CAMPOS_ENTRADA = {"user_input", "retrieved_contexts", "response", "reference"}


def mapear_columnas(notas: pd.DataFrame, metricas: list, nombres: list[str]) -> dict[str, str]:
    """Nombre corto -> columna real que ha devuelto RAGAS.

    RAGAS no nombra las columnas como uno pide: `LLMContextPrecisionWithReference`
    sale como `llm_context_precision_with_reference` y `FactualCorrectness(mode="f1")`
    como `factual_correctness(mode=f1)`. Mapear a ciegas por el nombre corto
    llenaría de NaN esas dos columnas sin dar ningún error.

    Se resuelve en cuatro pasadas: nombre con el modo exacto (imprescindible
    porque `factual_correctness` en modo f1 y en modo recall comparten `.name` y
    solo el sufijo `(mode=...)` las distingue), nombre exacto, nombre con
    cualquier sufijo, y por último posición (RAGAS conserva el orden de `metrics`).
    """
    disponibles = [c for c in notas.columns if c not in CAMPOS_ENTRADA]
    mapa: dict[str, str] = {}
    usadas: set[str] = set()

    for corto, metrica in zip(nombres, metricas):
        real = getattr(metrica, "name", corto)
        modo = getattr(metrica, "mode", None)

        candidatos = []
        if modo:
            candidatos.append(f"{real}(mode={modo})")
        candidatos.append(real)
        candidatos += [c for c in disponibles if c.startswith(f"{real}(")]

        for cand in candidatos:
            if cand in disponibles and cand not in usadas:
                mapa[corto] = cand
                usadas.add(cand)
                break

    faltan = [n for n in nombres if n not in mapa]
    sobran = [c for c in disponibles if c not in mapa.values()]
    for corto, col in zip(faltan, sobran):
        mapa[corto] = col

    sin_resolver = [n for n in nombres if n not in mapa]
    if sin_resolver:
        print(f"   ! sin columna en la salida de RAGAS: {', '.join(sin_resolver)}")
    return mapa


def cargar_respuestas() -> pd.DataFrame:
    if not RESPUESTAS_CSV.exists():
        raise ErrorConfiguracion(
            f"No existe {RESPUESTAS_CSV}.\n"
            f"Ejecuta primero: python -m eval_ragas.generar_respuestas"
        )
    df = pd.read_csv(RESPUESTAS_CSV, dtype={"ID": str})
    df["retrieved_contexts"] = df["retrieved_contexts"].apply(load_json)
    # El juez sigue viendo el texto completo (retrieved_contexts); al entregable
    # solo baja la referencia.
    df["fragmentos"] = df["fuentes"].apply(ref_fragmentos)
    return df


def cargar_previas() -> pd.DataFrame:
    """Lo ya puntuado en corridas anteriores, indexado por ID."""
    if not RESULTADOS_CSV.exists() or RESULTADOS_CSV.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(RESULTADOS_CSV, dtype={"ID": str})


def planificar(respuestas: pd.DataFrame, previas: pd.DataFrame,
               nombres: list[str], limit: int | None) -> tuple[pd.DataFrame, list[str]]:
    """Qué filas hay que puntuar y con qué métricas.

    La reanudación es consciente de las columnas, no solo de los IDs. Así, al
    añadir una métrica nueva al catálogo, se puntúa **solo esa** sobre las filas
    ya hechas en lugar de repetir las seis: con 94 preguntas eso es la diferencia
    entre una llamada por fila y siete.

    Un hueco suelto dentro de una columna que ya existe también cuenta como
    pendiente, así que volver a lanzar el comando reintenta las filas que el juez
    dejó en NaN por un fallo puntual de la API.
    """
    if previas.empty:
        return (respuestas.head(limit) if limit else respuestas), nombres

    ya_hechas = set(previas["ID"])
    nuevas = respuestas[~respuestas["ID"].isin(ya_hechas)]
    if not nuevas.empty:
        # Filas nuevas: hay que calcularles todas las métricas pedidas.
        return (nuevas.head(limit) if limit else nuevas), nombres

    # Métricas con algún valor por rellenar, y los IDs a los que les falta.
    a_calcular, ids_pendientes = [], set()
    for n in nombres:
        if n not in previas.columns:
            a_calcular.append(n)
            ids_pendientes |= ya_hechas
            continue
        huecos = previas.loc[previas[n].isna(), "ID"]
        if not huecos.empty:
            a_calcular.append(n)
            ids_pendientes |= set(huecos)

    if not a_calcular:
        return respuestas.iloc[0:0], []

    pendientes = respuestas[respuestas["ID"].isin(ids_pendientes)]
    return (pendientes.head(limit) if limit else pendientes), a_calcular


def fusionar_y_guardar(previas: pd.DataFrame, nuevas: list[dict],
                       columnas: list[str]) -> pd.DataFrame:
    """Mezcla lo recién puntuado con lo previo por ID y reescribe el CSV.

    Se reescribe entero en vez de añadir al final porque una métrica nueva
    inserta una columna: un append dejaría filas con distinto número de campos.

    Las filas de un ID que ya estaba sólo aportan notas; las de un ID nuevo
    entran enteras. Antes todas entraban sólo con ID y notas, y una fila nueva
    añadida al reanudar se quedaba sin pregunta, respuesta ni categoría: visto
    al ampliar prueba10_conciso de 10 a 24 preguntas, las 14 nuevas salían sin
    categoría en el informe. Una corrida de 94 cortada por un 429 a mitad habría
    perdido así todo lo puntuado después de reanudar.
    """
    df_nuevas = pd.DataFrame(nuevas)
    if previas.empty:
        fusionado = df_nuevas
    else:
        ya_estaban = df_nuevas["ID"].isin(set(previas["ID"]))
        solo_notas = [c for c in df_nuevas.columns if c in columnas]
        fusionado = previas.merge(
            df_nuevas.loc[ya_estaban, ["ID"] + solo_notas], on="ID", how="left",
            suffixes=("", "_nuevo"),
        )
        # Si la métrica ya existía, el valor nuevo manda sobre el hueco antiguo.
        for c in solo_notas:
            if f"{c}_nuevo" in fusionado.columns:
                fusionado[c] = fusionado[f"{c}_nuevo"].combine_first(fusionado[c])
                fusionado = fusionado.drop(columns=[f"{c}_nuevo"])
        fusionado = pd.concat([fusionado, df_nuevas.loc[~ya_estaban]], ignore_index=True)

    fusionado = fusionado.sort_values("ID", key=lambda s: s.astype(int))
    orden = [c for c in COLS_BASE if c in fusionado.columns]
    orden += [c for c in M.ORDEN if c in fusionado.columns]
    orden += [c for c in fusionado.columns if c not in orden]
    fusionado = fusionado[orden]

    RESULTADOS_CSV.parent.mkdir(parents=True, exist_ok=True)
    fusionado.to_csv(RESULTADOS_CSV, index=False, encoding="utf-8")
    return fusionado


def evaluar_lote(lote: pd.DataFrame, metricas: list, juez, embeddings) -> pd.DataFrame:
    from ragas import EvaluationDataset, RunConfig, evaluate

    muestras = [{
        "user_input":         fila["user_input"],
        "retrieved_contexts": list(fila["retrieved_contexts"]),
        "response":           quitar_citas(fila["response"]),
        "reference":          fila["reference"],
    } for _, fila in lote.iterrows()]

    resultado = evaluate(
        dataset=EvaluationDataset.from_list(muestras),
        metrics=metricas,
        llm=juez,
        embeddings=embeddings,
        run_config=RunConfig(
            # 4 y no los 16 por defecto. El ritmo real lo marca el limitador
            # del juez (`RPM_JUEZ`); más hilos sólo harían más cola.
            max_workers=4,
            timeout=180,
            max_retries=10,
            max_wait=60,
        ),
        # Una fila que falle da NaN en vez de tumbar la corrida entera.
        raise_exceptions=False,
        show_progress=True,
    )
    return resultado.to_pandas()


def comprobar_juez(previo: str | None, actual: str, *, hay_resultados: bool) -> str | None:
    """¿Se puede seguir puntuando esta corrida con el juez actual?

    El gemelo de la comprobación de `configuracion.txt` en la fase 1, pero para
    el instrumento de medida (invariante 6). Lanza `ErrorConfiguracion` si la
    corrida ya se empezó a puntuar con otro juez u otras plantillas: mezclar
    dos jueces en un mismo CSV daría medias que no son de ninguno. Devuelve un
    aviso, sin parar, si hay notas pero no constancia de con qué se pusieron:
    son las corridas anteriores a `puntuacion.txt`, que no se pueden comprobar.
    """
    if previo is not None and previo != actual:
        raise ErrorConfiguracion(
            f"Esta corrida se empezó a puntuar con otro juez:\n  {previo}\n"
            f"y ahora es:\n  {actual}\n"
            f"Repuntúala entera con --reset, o vuelve al juez anterior."
        )
    if previo is None and hay_resultados:
        return ("Hay notas previas sin puntuacion.txt (corrida anterior a él): no "
                "consta con qué juez se pusieron. Se registra el actual a partir de ahora.")
    return None


def _argumentos() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fase 2: puntúa las respuestas con RAGAS.")
    ap.add_argument("--limit", type=int, help="puntúa solo las N primeras pendientes")
    ap.add_argument("--metricas", help=f"lista separada por comas. Por defecto: {','.join(M.ORDEN)}")
    ap.add_argument("--reset", action="store_true", help="borra el CSV de resultados y empieza de cero")
    ap.add_argument("--batch", type=int, default=10, help="filas por lote antes de guardar (def. 10)")
    ap.add_argument("--en", action="store_true", help="usa las plantillas originales en inglés")
    return ap.parse_args()


def _borrar_puntuacion() -> None:
    for ruta in (RESULTADOS_CSV, PUNTUACION_TXT):
        if ruta.exists():
            ruta.unlink()
            print(f"Borrado {ruta.name}")


def _juez_de_la_corrida(en_ingles: bool) -> str:
    """El juez con el que se va a puntuar, comprobado contra el que ya puntuó."""
    juez_actual = resumen_juez(en_ingles)
    previo = (PUNTUACION_TXT.read_text(encoding="utf-8").strip()
              if PUNTUACION_TXT.exists() else None)
    aviso = comprobar_juez(previo, juez_actual, hay_resultados=RESULTADOS_CSV.exists())
    if aviso:
        print(f"   ! {aviso}")
    print(f"Juez:     {juez_actual}")
    return juez_actual


def _puntuar_por_lotes(pendientes: pd.DataFrame, previas: pd.DataFrame, metricas,
                       a_calcular: list[str], tam_lote: int) -> None:
    juez = build_juez()
    # Los mismos en todas las corridas: son el instrumento de medida, no el
    # sistema medido. Ver `comun.py`.
    embeddings = build_embeddings_juez()
    acumuladas: list[dict] = []

    total_lotes = (len(pendientes) + tam_lote - 1) // tam_lote
    for inicio in range(0, len(pendientes), tam_lote):
        lote = pendientes.iloc[inicio:inicio + tam_lote]
        print(f"-- Lote {inicio // tam_lote + 1}/{total_lotes} ({len(lote)} filas) --")

        notas = evaluar_lote(lote, metricas, juez, embeddings)
        mapa = mapear_columnas(notas, metricas, a_calcular)

        for (_, origen), (_, nota) in zip(lote.iterrows(), notas.iterrows()):
            fila = {c: origen[c] for c in COLS_BASE if c in origen}
            for m in a_calcular:
                fila[m] = nota.get(mapa.get(m, m))
            acumuladas.append(fila)

        # Checkpoint por lote, mismo motivo que en la fase 1: si se agota la
        # cuota a mitad, lo calculado hasta aquí queda en disco.
        df = fusionar_y_guardar(previas, acumuladas, a_calcular)
        print(f"   guardadas {len(acumuladas)} filas en {RESULTADOS_CSV.name} "
              f"({len(df)} en total)\n")


def main() -> int:
    args = _argumentos()
    if args.reset:
        _borrar_puntuacion()

    pedidas = [n.strip() for n in args.metricas.split(",")] if args.metricas else M.ORDEN

    # La configuración que se enseña es la de la corrida, leída de su fichero,
    # y no la del entorno: puntuar no depende del RAG, así que nadie exporta
    # USAR_RERANKER=0 o PROVEEDOR_RAG=openai para esta fase, y el entorno
    # describiría otro sistema.
    print(f"Corrida:  {leer_configuracion(SALIDA_DIR) or '(sin configuracion.txt)'}")
    juez_actual = _juez_de_la_corrida(args.en)

    respuestas = cargar_respuestas()
    previas = cargar_previas()
    pendientes, a_calcular = planificar(respuestas, previas, pedidas, args.limit)

    if pendientes.empty or not a_calcular:
        print(f"\nNada que puntuar: las {len(previas)} filas ya tienen "
              f"{', '.join(pedidas)}.")
        return 0

    if len(a_calcular) < len(pedidas):
        print(f"Métricas por calcular: {', '.join(a_calcular)} "
              f"(el resto ya está en el CSV)")
    else:
        print(f"Métricas: {', '.join(a_calcular)}")

    metricas = M.construir(a_calcular)
    if args.en:
        print("Plantillas: originales en inglés (--en)")
    else:
        cargadas = M.cargar_es(metricas, PROMPTS_ES_DIR)
        print(f"Plantillas: español ({len(cargadas)} métricas adaptadas)")

    print(f"Filas pendientes: {len(pendientes)}\n")

    # Se escribe justo antes de la primera llamada al juez, no al principio: un
    # «nada que puntuar» no debe dejar constancia de un juez que no ha puntuado.
    PUNTUACION_TXT.parent.mkdir(parents=True, exist_ok=True)
    PUNTUACION_TXT.write_text(juez_actual + "\n", encoding="utf-8")

    _puntuar_por_lotes(pendientes, previas, metricas, a_calcular, args.batch)

    df = pd.read_csv(RESULTADOS_CSV)
    print("Medias globales:")
    for m in pedidas:
        if m in df:
            print(f"  {M.ETIQUETAS.get(m, m):<26} {df[m].mean():.3f}")
    print(f"\nEntregable: {RESULTADOS_CSV}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ErrorConfiguracion as exc:
        raise SystemExit(f"ERROR: {exc}")
