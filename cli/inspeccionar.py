"""
inspeccionar.py — Ver por dentro el troceado, la recuperación y ChromaDB.

No reimplementa nada: usa las mismas piezas que el chat, importadas del paquete
`rag`. Lo que se ve aquí es lo que pasa de verdad.

En concreto, las tres etapas de la recuperación las calcula
`rag.analizar_recuperacion()`, que devuelve datos y no texto para poder probar
su paridad con producción (`tests/test_analizar.py`). Este módulo sólo se ocupa
de pintarlas en la terminal.

Uso:
    # Qué hay guardado en ChromaDB
    python -m cli.inspeccionar --db
    python -m cli.inspeccionar --db --doc "05 Memoria"

    # Todos los chunks de un documento, en orden
    python -m cli.inspeccionar --doc "05 Memoria"
    python -m cli.inspeccionar --doc "05 Memoria" --texto     # con el contenido entero

    # Un chunk concreto, entero y con sus metadatos
    python -m cli.inspeccionar --chunk "05 Memoria. Gestión de Memoria.md#0012"

    # Las tres etapas de la recuperación para una consulta
    python -m cli.inspeccionar "¿qué es la paginación de memoria?"
    python -m cli.inspeccionar "..." --texto      # además, el texto de los finalistas
"""

from __future__ import annotations

import argparse

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rag import (
    CHROMA_ACTIVO,
    CLAVE_META_MODELO,
    COLLECTION,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    RERANK_K,
    RETRIEVER_K,
    ErrorConfiguracion,
    analizar_recuperacion,
    build_hibrido,
    build_vectordb,
    chunk_id,
    construir_cross_encoder,
    cuerpo_sin_encabezados,
    describir_fuente,
    recortar,
    tokenizar_es,
)

console = Console()

# Caracteres de la vista previa de un chunk en las tablas.
ANCHO_VISTA_PREVIA = 76

# Caracteres del texto que se enseña del registro de ejemplo en --db.
ANCHO_REGISTRO_EJEMPLO = 700

# Cómo se pinta cada estado que devuelve `analizar_recuperacion`.
_ORIGEN = {
    "ambos": "[cyan]ambos[/cyan]",
    "bm25":  "[yellow]BM25[/yellow]",
    "denso": "[green]denso[/green]",
}
_ESTADO = {
    "contexto":  "[bold green]AL CONTEXTO[/bold green]",
    "duplicado": "[yellow]duplicado de sección[/yellow]",
    "no_cabe":   f"[dim]no cabe (tope {RERANK_K})[/dim]",
    "peor":      "[dim]peor puntuado[/dim]",
}


# ── Qué hay en ChromaDB ───────────────────────────────────────────────────────
def ver_base_de_datos(filtro_doc: str | None) -> None:
    """La colección entera: sello, metadatos, reparto por documento y un registro."""
    vectordb = build_vectordb()
    raw = vectordb.get(include=["documents", "metadatas", "embeddings"])
    ids, docs = raw["ids"], raw["documents"]
    metas = raw["metadatas"]
    vectores = np.asarray(raw["embeddings"])

    _panel_coleccion(vectordb._collection.metadata or {}, len(ids), vectores)
    _tabla_por_documento(docs, metas, filtro_doc)
    _registro_ejemplo(ids, docs, metas, vectores, filtro_doc)


def _panel_coleccion(meta_coleccion: dict, n_chunks: int, vectores: np.ndarray) -> None:
    espacio = meta_coleccion.get("hnsw:space", "?")

    # El sello dice con qué modelo se indexó de verdad, frente a `EMBEDDING_MODEL`,
    # que es sólo lo que dice la configuración de ahora. Éste es el sitio para
    # verlos juntos: las colecciones anteriores al sello no lo tienen, y ahí lo
    # único que se puede afirmar es que la dimensión y la distancia cuadran.
    sellado = meta_coleccion.get(CLAVE_META_MODELO)
    if sellado is None:
        linea_sello = "[dim]sin sello (colección anterior al sello)[/dim]"
    elif sellado == EMBEDDING_MODEL:
        linea_sello = f"[green]{sellado}[/green]"
    else:
        linea_sello = f"[red]{sellado} — NO es el modelo configurado[/red]"

    console.print(Panel.fit(
        f"[bold]Proveedor:[/bold] {EMBEDDING_PROVIDER}  [dim]({CHROMA_ACTIVO.name}/)[/dim]\n"
        f"[bold]Colección:[/bold] {COLLECTION}\n"
        f"[bold]Chunks:[/bold] {n_chunks}\n"
        f"[bold]Embeddings:[/bold] {EMBEDDING_MODEL}, {vectores.shape[1]} dimensiones\n"
        f"[bold]Indexada con:[/bold] {linea_sello}\n"
        f"[bold]Distancia:[/bold] {espacio}\n"
        f"[bold]Norma de los vectores:[/bold] "
        f"{np.linalg.norm(vectores, axis=1).mean():.4f} (1.0 = normalizados)",
        title="ChromaDB", border_style="cyan",
    ))


def _tabla_por_documento(docs: list[str], metas: list[dict], filtro_doc: str | None) -> None:
    # Qué campos de metadatos hay realmente guardados.
    campos: dict[str, int] = {}
    for m in metas:
        for k in (m or {}):
            campos[k] = campos.get(k, 0) + 1
    console.print("[bold]Metadatos por chunk:[/bold] " +
                  ", ".join(f"{k} ({v})" for k, v in sorted(campos.items())))

    # Reparto por documento.
    por_doc: dict[str, list[int]] = {}
    for d, m in zip(docs, metas):
        por_doc.setdefault((m or {}).get("source", "?"), []).append(len(d))

    tabla = Table(title="Chunks por documento", header_style="bold")
    tabla.add_column("documento", overflow="fold")
    tabla.add_column("chunks", justify="right")
    tabla.add_column("caracteres", justify="right")
    tabla.add_column("media", justify="right")
    for fuente, tam in sorted(por_doc.items()):
        if filtro_doc and filtro_doc.lower() not in fuente.lower():
            continue
        tabla.add_row(fuente, str(len(tam)), f"{sum(tam):,}",
                      f"{sum(tam)//len(tam):,}")
    console.print(tabla)


def _registro_ejemplo(ids: list[str], docs: list[str], metas: list[dict],
                      vectores: np.ndarray, filtro_doc: str | None) -> None:
    """Un registro completo, para ver exactamente qué se guarda."""
    objetivo = 0
    if filtro_doc:
        for i, m in enumerate(metas):
            if filtro_doc.lower() in (m or {}).get("source", "").lower():
                objetivo = i
                break
    texto = docs[objetivo]
    console.print(Panel(
        f"[bold]id:[/bold] {ids[objetivo]}\n"
        f"[bold]metadatos:[/bold] {metas[objetivo]}\n"
        f"[bold]vector:[/bold] [{', '.join(f'{v:+.4f}' for v in vectores[objetivo][:6])}, …] "
        f"({vectores.shape[1]} dims)\n\n"
        f"[bold]texto ({len(texto)} caracteres):[/bold]\n{texto[:ANCHO_REGISTRO_EJEMPLO]}"
        + ("\n[dim]…[/dim]" if len(texto) > ANCHO_REGISTRO_EJEMPLO else ""),
        title="Un registro completo, tal cual se guarda", border_style="dim",
    ))


def ver_documento(filtro: str, mostrar_texto: bool) -> None:
    """Todos los chunks de un documento, en el orden en que se trocearon."""
    vectordb = build_vectordb()
    raw = vectordb.get(include=["documents", "metadatas"])

    encontrados = [
        (cid, texto, meta or {})
        for cid, texto, meta in zip(raw["ids"], raw["documents"], raw["metadatas"])
        if filtro.lower() in (meta or {}).get("source", "").lower()
    ]
    if not encontrados:
        console.print(f"[red]Ningún documento contiene «{filtro}».[/red]\n")
        console.print("[bold]Documentos disponibles:[/bold]")
        for fuente in sorted({(m or {}).get("source", "?") for m in raw["metadatas"]}):
            console.print(f"[dim]  · {fuente}[/dim]")
        return

    # El chunk_id lleva el índice con ceros ("...md#0007"), así que ordenar como
    # cadena ya deja los chunks en el orden del documento original.
    encontrados.sort(key=lambda e: e[0])

    por_fuente: dict[str, list] = {}
    for cid, texto, meta in encontrados:
        por_fuente.setdefault(meta.get("source", "?"), []).append((cid, texto, meta))

    for fuente, items in por_fuente.items():
        caracteres = sum(len(t) for _, t, _ in items)
        tabla = Table(title=f"{fuente}  ·  {len(items)} chunks  ·  {caracteres:,} caracteres",
                      header_style="bold")
        tabla.add_column("nº", justify="right")
        tabla.add_column("sección (h2)", overflow="fold")
        tabla.add_column("car.", justify="right")
        tabla.add_column("comienzo del contenido", overflow="fold")
        for cid, texto, meta in items:
            tabla.add_row(
                cid.rsplit("#", 1)[-1],
                meta.get("h2") or "[dim](sin ##)[/dim]",
                f"{len(texto):,}",
                recortar(cuerpo_sin_encabezados(texto), ANCHO_VISTA_PREVIA),
            )
        console.print(tabla)

    if mostrar_texto:
        for cid, texto, meta in encontrados:
            console.print(Panel(texto.strip(),
                                title=f"{cid}  ·  {meta.get('h2') or '(sin ##)'}",
                                border_style="dim"))
    else:
        console.print("\n[dim]--texto para ver el contenido completo de cada chunk.[/dim]")


def ver_chunk(identificador: str) -> None:
    """Un chunk entero, con sus metadatos."""
    vectordb = build_vectordb()
    raw = vectordb.get(ids=[identificador], include=["documents", "metadatas"])
    if not raw["ids"]:
        console.print(f"[red]No existe el chunk {identificador}[/red]")
        console.print("[dim]Usa --db para listar los documentos y sus ids.[/dim]")
        return
    console.print(Panel(
        raw["documents"][0],
        title=f"{identificador}  ·  {raw['metadatas'][0]}",
        border_style="cyan",
    ))


# ── Las etapas de la recuperación ─────────────────────────────────────────────
def ver_recuperacion(consulta: str, mostrar_texto: bool) -> None:
    """Pinta las tres etapas que calcula `rag.analizar_recuperacion()`."""
    # La consulta se enseña antes de trabajar: cargar el cross-encoder tarda, y
    # así se ve de inmediato qué se está buscando y qué palabras ve BM25.
    console.print(Panel.fit(
        f"[bold]{consulta}[/bold]\n"
        f"[dim]BM25 ve: {' '.join(tokenizar_es(consulta))}[/dim]",
        title="Consulta", border_style="yellow",
    ))

    hibrido = build_hibrido(build_vectordb())
    with console.status("[dim]Recuperando y puntuando con el cross-encoder...[/dim]"):
        analisis = analizar_recuperacion(consulta, hibrido, construir_cross_encoder())

    _tabla_etapa1(analisis)
    _tabla_etapas23(analisis)
    _efecto_reranker(analisis["resumen"])

    if mostrar_texto:
        for i, d in enumerate(analisis["finalistas"], start=1):
            console.print(Panel(d.page_content.strip(),
                                title=f"[{i}] {describir_fuente(d)}  ·  {chunk_id(d)}",
                                border_style="dim"))


def _tabla_etapa1(analisis: dict) -> None:
    """Etapa 1: qué aportó cada mitad del híbrido."""
    resumen = analisis["resumen"]
    tabla = Table(
        title=f"Etapa 1 · candidatos del híbrido (BM25 k={RETRIEVER_K} + "
              f"denso k={RETRIEVER_K}, fusión RRF)",
        header_style="bold")
    tabla.add_column("#", justify="right")
    tabla.add_column("origen")
    tabla.add_column("documento › sección", overflow="fold")
    for fila in analisis["etapa1"]:
        tabla.add_row(str(fila["posicion"]), _ORIGEN[fila["origen"]], fila["descripcion"])
    console.print(tabla)
    console.print(f"[dim]{resumen['n_candidatos']} candidatos únicos · "
                  f"solo BM25: {resumen['solo_bm25']} · "
                  f"solo denso: {resumen['solo_denso']} · "
                  f"en ambos: {resumen['en_ambos']}[/dim]\n")


def _tabla_etapas23(analisis: dict) -> None:
    """Etapas 2 y 3: reordenado por el cross-encoder y deduplicado por sección."""
    tabla2 = Table(
        title=f"Etapa 2 y 3 · reordenado por el cross-encoder y deduplicado (top {RERANK_K})",
        header_style="bold")
    tabla2.add_column("nuevo", justify="right")
    tabla2.add_column("antes", justify="right")
    tabla2.add_column("mov.", justify="center")
    tabla2.add_column("score", justify="right")
    tabla2.add_column("estado")
    tabla2.add_column("documento › sección", overflow="fold")

    for fila in analisis["etapa23"]:
        salto = fila["salto"]
        mov = (f"[green]▲{salto}[/green]" if salto > 0
               else f"[red]▼{-salto}[/red]" if salto < 0 else "[dim]=[/dim]")
        tabla2.add_row(str(fila["posicion"]), str(fila["antes"]), mov,
                       f"{fila['score']:+.3f}", _ESTADO[fila["estado"]],
                       fila["descripcion"])
    console.print(tabla2)


def _efecto_reranker(resumen: dict) -> None:
    """Lo que de verdad importa: ¿cambió el orden el reranker?"""
    if resumen["usar_reranker"]:
        console.print(f"\n[bold]Efecto del reranking:[/bold] de los {RERANK_K} que el híbrido "
                      f"habría mandado al contexto, el reranker conserva "
                      f"{resumen['conserva']} y cambia {resumen['cambia']}.")
        if resumen["cambia_el_primero"]:
            console.print("[green]El primer resultado cambia gracias al reranker.[/green]")
    else:
        # USAR_RERANKER=0: el contexto marcado es el del híbrido deduplicado y la
        # tabla del reordenado sólo dice qué haría el cross-encoder.
        console.print(f"\n[bold]Reranker desactivado:[/bold] al contexto van los {RERANK_K} "
                      f"primeros del híbrido, deduplicados. Si se activara, conservaría "
                      f"{resumen['conserva']} y cambiaría {resumen['cambia']}.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("consulta", nargs="?", help="Consulta a inspeccionar")
    p.add_argument("--db", action="store_true", help="Ver qué hay guardado en ChromaDB")
    p.add_argument("--doc", help="Listar los chunks de un documento (o filtrar --db)")
    p.add_argument("--chunk", help="Ver un chunk concreto por su id")
    p.add_argument("--texto", action="store_true",
                   help="Mostrar el contenido completo de los chunks")
    args = p.parse_args()

    try:
        if args.chunk:
            ver_chunk(args.chunk)
        elif args.db:
            ver_base_de_datos(args.doc)
        elif args.doc:
            ver_documento(args.doc, args.texto)
        elif args.consulta:
            ver_recuperacion(args.consulta, args.texto)
        else:
            p.print_help()
    except ErrorConfiguracion as exc:
        console.print(f"[red]❌ {exc}[/red]")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
