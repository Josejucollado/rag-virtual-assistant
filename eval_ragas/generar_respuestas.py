"""
generar_respuestas.py — Fase 1: ejecuta el RAG sobre el banco de preguntas.

Recorre el banco de preguntas (`EVAL_BANCO`), lanza cada pregunta contra el RAG
real y guarda pregunta, ground truth, respuesta y **el texto completo de los
fragmentos recuperados** en `data/ragas/<corrida>/respuestas_rag.csv`.

Se separa de la puntuación porque generar es caro: así se pueden reajustar las
métricas o rehacer el informe sin volver a pagar las llamadas de generación.

Uso:
    python -m eval_ragas.generar_respuestas
    python -m eval_ragas.generar_respuestas --limit 3
    python -m eval_ragas.generar_respuestas --categoria MULTIHOP
    python -m eval_ragas.generar_respuestas --reset
"""

from __future__ import annotations

import argparse
import time

from langchain_core.callbacks import get_usage_metadata_callback

from eval_ragas.comun import (
    CAMPOS_CONSUMO,
    CONFIGURACION_TXT,
    CONSUMO_CSV,
    ERROR,
    OK,
    PRESUPUESTO_USD,
    RECHAZO,
    RESPUESTAS_CSV,
    append_filas,
    clasificar,
    con_reintentos,
    consumo_de,
    dump_json,
    gasto_acumulado,
    ids_existentes,
    leer_banco,
    resumen_config,
)
# El RAG se importa de `rag`, no de `comun`: es exactamente el mismo código que
# ejecuta el chat, y que la dependencia se vea aquí lo deja claro.
from rag import (
    MODEL_RAG,
    PROVEEDOR_RAG,
    PROVEEDORES_LLM,
    ErrorConfiguracion,
    build_generador,
    build_retriever,
    entrada_generador,
    extraer_citas,
)

CAMPOS = [
    "ID", "Categoria", "user_input", "reference", "response",
    "retrieved_contexts", "fuentes",
    "n_docs", "n_citas", "resultado", "es_rechazo",
    "latencia_s", "error",
]


def responder(retriever, generador, pregunta: str) -> dict:
    """Una pregunta -> respuesta + los fragmentos exactos que vio el modelo.

    El mismo turno que el chat y la web: se recupera UNA sola vez y se le pasa
    ese mismo contexto al generador, de modo que lo que se registra como
    `retrieved_contexts` es literalmente lo que el modelo leyó. Sin reescritura:
    cada pregunta del banco se entiende por sí sola.
    """
    t0 = time.perf_counter()

    docs = con_reintentos(lambda: retriever.invoke(pregunta), etiqueta="recuperación")
    entrada = entrada_generador(docs, pregunta)
    respuesta = con_reintentos(lambda: generador.invoke(entrada), etiqueta="generación")

    return {
        "docs": docs,
        "respuesta": respuesta,
        "latencia_s": round(time.perf_counter() - t0, 2),
    }


def fila_resultado(pregunta: dict, salida: dict | None, error: str | None) -> dict:
    docs = salida["docs"] if salida else []
    respuesta = salida["respuesta"] if salida else ""
    estado = clasificar(respuesta, error)

    return {
        **pregunta,
        "response": respuesta,
        # El texto real del chunk, no solo el nombre del fichero: faithfulness,
        # context_precision y context_recall necesitan el contenido.
        "retrieved_contexts": dump_json([d.page_content for d in docs]),
        "fuentes": dump_json([{
            "chunk_id": d.metadata.get("chunk_id"),
            "source":   d.metadata.get("source"),
            "h2":       d.metadata.get("h2"),
        } for d in docs]),
        "n_docs":     len(docs),
        "n_citas":    len(extraer_citas(respuesta, len(docs))) if respuesta else 0,
        "resultado":  estado,
        "es_rechazo": estado == RECHAZO,
        "latencia_s": salida["latencia_s"] if salida else 0.0,
        "error":      error or "",
    }


def supera_presupuesto(gastado: float, n_hechas: int, presupuesto: float) -> bool:
    """¿La siguiente pregunta haría pasar la corrida del presupuesto?

    La siguiente se estima con el coste medio de las ya hechas: parar cuando lo
    gastado ya ha superado el tope dejaría pasarse siempre en una pregunta, y
    con un crédito prepago de 5 $ el margen importa. Sin preguntas hechas no hay
    con qué estimar, así que sólo para si el tope ya está agotado.
    """
    siguiente = gastado / n_hechas if n_hechas else 0.0
    return gastado + siguiente > presupuesto


def _argumentos() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fase 1: genera las respuestas del RAG.")
    ap.add_argument("--limit", type=int, help="procesa solo las N primeras pendientes")
    ap.add_argument("--categoria", help="filtra por categoría (subcadena, sin distinguir mayúsculas)")
    ap.add_argument("--reset", action="store_true", help="borra el CSV y empieza de cero")
    ap.add_argument("--delay", type=float, default=0.5, help="pausa entre preguntas (s)")
    return ap.parse_args()


def _borrar_corrida() -> None:
    for ruta in (RESPUESTAS_CSV, CONFIGURACION_TXT, CONSUMO_CSV):
        if ruta.exists():
            ruta.unlink()
            print(f"Borrado {ruta.name}")


def _fijar_configuracion(config: str) -> None:
    """Graba la configuración de la corrida, o comprueba que no ha cambiado.

    Reanudar con otra configuración mezclaría dos sistemas en una misma corrida
    sin que el CSV lo reflejara: se para en vez de seguir.
    """
    if CONFIGURACION_TXT.exists():
        previa = CONFIGURACION_TXT.read_text(encoding="utf-8").strip()
        if previa != config:
            raise ErrorConfiguracion(
                f"Esta corrida empezó con otra configuración:\n  {previa}\n"
                f"y ahora es:\n  {config}\n"
                f"Usa otro EVAL_CORRIDA o empieza de cero con --reset."
            )
    else:
        CONFIGURACION_TXT.parent.mkdir(parents=True, exist_ok=True)
        CONFIGURACION_TXT.write_text(config + "\n", encoding="utf-8")


def _procesar(pregunta: dict, retriever, generador) -> tuple[dict, dict]:
    """Responde una pregunta y devuelve su fila de resultados y su consumo."""
    # El contador envuelve también los fallos: una llamada que agota el tope de
    # salida y llega vacía se factura igual.
    with get_usage_metadata_callback() as contador:
        try:
            salida, error = responder(retriever, generador, pregunta["user_input"]), None
        except Exception as exc:  # noqa: BLE001 - se registra y se sigue
            salida, error = None, f"{type(exc).__name__}: {exc}"
    return fila_resultado(pregunta, salida, error), consumo_de(contador.usage_metadata, MODEL_RAG)


def _imprimir_resumen(conteo: dict, de_pago: bool, gastado: float) -> None:
    total = sum(conteo.values())
    if not total:
        return
    print(f"\nResumen de esta corrida ({total} preguntas):")
    for estado, n in conteo.items():
        print(f"  {estado:<8} {n:>3}  ({n / total:.1%})")
    if de_pago:
        print(f"  Gasto acumulado de la corrida: {gastado:.4f} $ (detalle en {CONSUMO_CSV.name})")
    print(f"\nGuardado en {RESPUESTAS_CSV}")


def main() -> int:
    args = _argumentos()
    if args.reset:
        _borrar_corrida()

    preguntas = leer_banco()
    if args.categoria:
        aguja = args.categoria.lower()
        preguntas = [p for p in preguntas if aguja in p["Categoria"].lower()]

    hechas = ids_existentes(RESPUESTAS_CSV)
    pendientes = [p for p in preguntas if p["ID"] not in hechas]
    if args.limit:
        pendientes = pendientes[:args.limit]

    config = resumen_config()
    print(f"Configuración: {config}")
    print(f"Banco: {len(preguntas)} preguntas · ya hechas: {len(hechas)} · "
          f"pendientes en esta corrida: {len(pendientes)}\n")

    if not pendientes:
        print("Nada que hacer.")
        return 0
    _fijar_configuracion(config)

    # Lo gastado sale de `consumo.csv`, no de un contador en memoria: así el
    # tope vale para la corrida entera aunque se reanude diez veces.
    de_pago = PROVEEDORES_LLM[PROVEEDOR_RAG].de_pago
    gastado = gasto_acumulado(CONSUMO_CSV)
    n_con_coste = len(ids_existentes(CONSUMO_CSV))
    if de_pago:
        print(f"Generador de pago ({PROVEEDOR_RAG}): gastado hasta ahora "
              f"{gastado:.4f} $ de un tope de {PRESUPUESTO_USD:.2f} $ (PRESUPUESTO_USD).\n")

    # Fuera del bucle a propósito: build_hibrido() carga los 762 documentos en
    # memoria para BM25 y build_compresor() carga el cross-encoder. Construirlo
    # por pregunta multiplicaría el coste por 94.
    print("Construyendo el retriever (BM25 + denso + cross-encoder)...")
    retriever = build_retriever()
    generador = build_generador()
    print("Listo.\n")

    conteo = {OK: 0, RECHAZO: 0, ERROR: 0}
    for i, pregunta in enumerate(pendientes, start=1):
        if de_pago and supera_presupuesto(gastado, n_con_coste, PRESUPUESTO_USD):
            print(f"\nTope de gasto alcanzado: {gastado:.4f} $ de {PRESUPUESTO_USD:.2f} $. "
                  f"Se para aquí; lo hecho está en disco. Para seguir, sube "
                  f"PRESUPUESTO_USD y relanza el mismo comando.")
            break

        fila, consumo = _procesar(pregunta, retriever, generador)
        conteo[fila["resultado"]] += 1

        # Checkpoint por fila: si la cuota se agota en la pregunta 60, las 59
        # anteriores ya están en disco y la próxima corrida las salta. El
        # consumo va primero: si algo fallara entre las dos escrituras, es mejor
        # contar de más una pregunta que volver a pagarla sin saberlo.
        append_filas(CONSUMO_CSV, [{"ID": pregunta["ID"], **consumo}], CAMPOS_CONSUMO)
        append_filas(RESPUESTAS_CSV, [fila], CAMPOS)
        gastado += consumo["coste_usd"]
        n_con_coste += 1

        marca = {OK: "ok", RECHAZO: "RECHAZO", ERROR: "ERROR"}[fila["resultado"]]
        coste = f" · {consumo['coste_usd']:.4f} $ (total {gastado:.3f} $)" if de_pago else ""
        print(f"[{i}/{len(pendientes)}] ID {pregunta['ID']} {marca:>7} · {fila['n_docs']} frags · "
              f"{fila['n_citas']} citas · {fila['latencia_s']}s{coste} · "
              f"{pregunta['user_input'][:55]}")
        if fila["error"]:
            print(f"   -> {fila['error'][:160]}")

        time.sleep(args.delay)

    _imprimir_resumen(conteo, de_pago, gastado)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ErrorConfiguracion as exc:
        raise SystemExit(f"ERROR: {exc}")
