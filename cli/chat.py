"""
chat.py — Chat interactivo del RAG.

Toda la lógica vive en el paquete `rag`: el recuperador, el prompt y el texto de
rechazo son los mismos que usan la evaluación y la web, así que lo que se ve
aquí es exactamente lo que se mide allí.

Por cada pregunta:
    1. Si hay historial, la reescribe para que se entienda sola.
    2. Recupera UNA vez (híbrido -> reranker -> deduplicado).
    3. Genera la respuesta en streaming, obligando a citar [n].
    4. Muestra solo las fuentes que la respuesta ha citado de verdad.

Órdenes: /fuentes  /limpiar  /ayuda  y  salir
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from rag import (
    MODEL_RAG,
    RERANK_K,
    RERANKER_MODEL,
    USAR_RERANKER,
    ErrorConfiguracion,
    build_generador,
    build_reescritor,
    build_retriever,
    consulta_de_busqueda,
    describir_fuente,
    entrada_generador,
    es_rechazo,
    extraer_citas,
)

console = Console()

SALIR = {"salir", "exit", "quit", "q"}
ORDENES_AYUDA = {"/ayuda", "/help", "?"}

# Repintados por segundo de la respuesta en streaming: de sobra para leer, y
# sin que `rich` vuelva a renderizar el Markdown entero a cada token.
REFRESCOS_POR_SEGUNDO = 8

AYUDA = """\
[bold]Órdenes[/bold]
  [cyan]/fuentes[/cyan]   muestra el texto completo de los fragmentos de la última respuesta
  [cyan]/limpiar[/cyan]   olvida el historial de la conversación
  [cyan]/ayuda[/cyan]     muestra esta ayuda
  [cyan]salir[/cyan]      termina el chat\
"""


def mostrar_cabecera() -> None:
    reranker = RERANKER_MODEL.split("/")[-1] if USAR_RERANKER else "desactivado"
    console.print(Panel.fit(
        f"[bold cyan]Sistema RAG — Chat interactivo[/bold cyan]\n"
        f"[dim]Modelo:    {MODEL_RAG}\n"
        f"Reranker:  {reranker}\n"
        f"Fragmentos por respuesta: {RERANK_K}\n"
        f"'/ayuda' para las órdenes  ·  'salir' para terminar.[/dim]",
        border_style="cyan",
    ))


def mostrar_fuentes(docs, citados) -> None:
    """Pie de fuentes: solo lo que la respuesta ha citado."""
    if not docs:
        return

    if not citados:
        console.print("\n[yellow]⚠️  La respuesta no cita ningún fragmento; "
                      "trátala con cautela.[/yellow]")
        return

    console.print("\n[bold dim]📚 Fuentes[/bold dim]")
    for n in citados:
        console.print(f"[dim]  [{n}] {describir_fuente(docs[n - 1])}[/dim]")

    no_citados = len(docs) - len(citados)
    if no_citados:
        console.print(f"[dim]  ({no_citados} fragmento(s) recuperado(s) sin citar; "
                      f"/fuentes para verlos)[/dim]")


def mostrar_fragmentos(docs) -> None:
    """Texto completo de los fragmentos recuperados, para depurar."""
    if not docs:
        console.print("[yellow]Todavía no hay fragmentos que mostrar.[/yellow]")
        return
    for i, d in enumerate(docs, start=1):
        console.print(Panel(
            d.page_content.strip(),
            title=f"[{i}] {describir_fuente(d)}",
            border_style="dim",
        ))


@dataclass
class Sesion:
    """Lo que el chat recuerda entre preguntas."""

    historial: list[tuple[str, str]] = field(default_factory=list)
    ultimos_docs: list = field(default_factory=list)   # para /fuentes


def ejecutar_orden(texto: str, sesion: Sesion) -> bool:
    """Atiende /ayuda, /limpiar y /fuentes. Devuelve si era una orden."""
    orden = texto.lower()
    if orden in ORDENES_AYUDA:
        console.print(AYUDA)
    elif orden == "/limpiar":
        sesion.historial.clear()
        console.print("[dim]Historial olvidado.[/dim]")
    elif orden == "/fuentes":
        mostrar_fragmentos(sesion.ultimos_docs)
    else:
        return False
    return True


def responder(pregunta: str, sesion: Sesion, retriever, generador, reescritor) -> None:
    """Un turno completo: buscar, generar en streaming y enseñar las fuentes."""
    # 1. Se busca con la pregunta autónoma (reescrita si es de seguimiento).
    consulta = consulta_de_busqueda(reescritor, sesion.historial, pregunta)
    if consulta != pregunta:
        console.print(f"[dim]↻ Busco: {consulta}[/dim]")

    # 2. Una sola recuperación: los fragmentos que se citan son exactamente los
    #    que ha visto el modelo.
    docs = retriever.invoke(consulta)
    sesion.ultimos_docs = docs

    # 3. Generación en streaming, con la pregunta ORIGINAL.
    console.print("\n[bold green]Asistente:[/bold green]")
    respuesta = ""
    with Live(console=console, refresh_per_second=REFRESCOS_POR_SEGUNDO,
              vertical_overflow="visible") as live:
        for trozo in generador.stream(entrada_generador(docs, pregunta)):
            respuesta += trozo
            live.update(Markdown(respuesta))

    # 4. Fuentes sólo si ha respondido de verdad.
    if es_rechazo(respuesta):
        sesion.ultimos_docs = []
    else:
        mostrar_fuentes(docs, extraer_citas(respuesta, len(docs)))
        sesion.historial.append((pregunta, respuesta))


def main() -> int:
    mostrar_cabecera()

    try:
        with console.status("[dim]Cargando recuperador y reranker...[/dim]"):
            retriever  = build_retriever()
            generador  = build_generador()
            reescritor = build_reescritor()
    except ErrorConfiguracion as exc:
        console.print(f"[red]❌ {exc}[/red]")
        return 1

    sesion = Sesion()
    while True:
        try:
            pregunta = console.input("\n[bold yellow]Tú:[/bold yellow] ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not pregunta:
            continue
        if pregunta.lower() in SALIR:
            break
        if ejecutar_orden(pregunta, sesion):
            continue

        try:
            responder(pregunta, sesion, retriever, generador, reescritor)
        except (EOFError, KeyboardInterrupt):
            break
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")

    console.print("[dim]Cerrando el chat. ¡Hasta pronto![/dim]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
