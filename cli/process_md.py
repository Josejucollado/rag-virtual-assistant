"""
Troceado e indexación de los Markdown en ChromaDB con embeddings de Qwen3 (Blablador).

Es la segunda mitad de la ingesta: `cli/pdf_to_md.py` produce los .md y este
script los convierte en chunks vectorizados listos para el RAG.

El troceado se apoya en la estructura que Docling ya extrajo. Un análisis del
corpus (33 documentos, ~1,06 M caracteres) da:

    - Solo hay encabezados de nivel 1 y 2. Ni un solo H3/H4.
    - 863 secciones H2: mediana 716 caracteres (~170 tokens), media 1237, p90
      2963, p99 6746, máximo 11578.
    - El 31 % de las secciones baja de 400 caracteres.
    - Solo el 4,8 % pasa de 4000.

Es decir: el documento ya viene troceado en unidades semánticas pequeñas. La
recomendación habitual de "chunks de 1000-2000 tokens" está pensada para prosa
técnica corrida; aquí obligaría a pegar ~9 secciones sin relación en un mismo
vector, y un embedding se diluye cuanto más largo es el texto. Así que la
estrategia es respetar la sección como unidad y corregir solo sus fallos:

    1. Portadas e índices            -> se recorta la chatarra línea a línea y
                                        se conserva la presentación del módulo,
                                        que cuelga del mismo encabezado.
    2. Secciones demasiado pequeñas  -> se fusionan con las contiguas.
    3. Secciones demasiado grandes   -> se subdividen con solapamiento,
                                        recomponiendo tablas y bloques de código.

Uso:
    python -m cli.process_md --dry-run             # estadísticas, sin gastar API
    python -m cli.process_md --only P09 --reset    # prueba con pocos documentos
    python -m cli.process_md --reset               # indexa el corpus completo
"""

from __future__ import annotations

import argparse
import re
import time
from collections import Counter
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from rich import print

from cli import resolver
# Los parámetros del índice (colección, modelo de embeddings, tamaños de chunk)
# viven en `rag.config` y se importan de allí. Es la misma configuración que usa
# el recuperador al consultar: si este script indexara con un modelo y el RAG
# preguntara con otro, no habría ningún error, sólo respuestas malas.
from rag import (
    BATCH_SIZE,
    CARACTERES_POR_TOKEN,
    CHROMA_ACTIVO,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CLAVE_META_CHUNKS,
    CLAVE_META_DIMS,
    CLAVE_META_MODELO,
    COLLECTION,
    DISTANCIA,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    MD_DIR,
    MIN_CHUNK,
    ErrorConfiguracion,
    construir_embeddings,
)

# ── Control de calidad de la conversión ───────────────────────────────────────
# Proporción máxima de caracteres "raros" (ni alfanuméricos, ni espacios, ni
# puntuación corriente) que se tolera en un documento. Un PDF cuya fuente
# incrustada no trae tabla ToUnicode se extrae como una ristra de símbolos
# (❯❳❡❨...) y supera el 79 %. Indexarlo es gastar tokens en basura y meter
# ruido en el recuperador. Se arregla con:
#     python -m cli.pdf_to_md --force-ocr --only "<nombre>"
MAX_RATIO_RAROS = 0.08

_PUNTUACION_OK = set(".,;:()[]{}<>/\\|-_=+*#$%&\"'`~!?@^¿¡ºª·€…—–“”‘’")


# ── 1. Carga ──────────────────────────────────────────────────────────────────
def ratio_caracteres_raros(texto: str) -> float:
    """Proporción de caracteres que no son texto legible normal."""
    if not texto:
        return 0.0
    legibles = sum(
        1 for c in texto if c.isalnum() or c.isspace() or c in _PUNTUACION_OK
    )
    return 1 - legibles / len(texto)


def cargar_documentos(directorio_md: str | Path = MD_DIR,
                      solo: str | None = None) -> list[Document]:
    """Carga los .md como Documents de LangChain, descartando los ilegibles."""
    dir_md = resolver(directorio_md)
    if not dir_md.is_dir():
        raise ErrorConfiguracion(f"No existe el directorio de Markdown: {dir_md}")

    rutas = sorted(dir_md.glob("*.md"))
    if solo:
        patrones = [p.strip().lower() for p in solo.split(",") if p.strip()]
        rutas = [r for r in rutas
                 if any(p in r.name.lower() for p in patrones)]

    if not rutas:
        raise ErrorConfiguracion(
            f"No hay Markdown que procesar en {dir_md}"
            + (f" con --only \"{solo}\"" if solo else "")
        )

    documentos: list[Document] = []
    for ruta in rutas:
        texto = ruta.read_text(encoding="utf-8")

        ratio = ratio_caracteres_raros(texto)
        if ratio > MAX_RATIO_RAROS:
            print(f"[red]⚠️  \"{ruta.name}\" descartado: {ratio:.0%} de caracteres "
                  f"ilegibles. Reconvierte con "
                  f"--force-ocr --only \"{ruta.stem}\"[/red]")
            continue

        # `source` es el nombre del fichero, no la ruta absoluta: es lo que el
        # chat, la web y la evaluación enseñan como fuente.
        documentos.append(Document(page_content=texto, metadata={"source": ruta.name}))

    return documentos


# ── 2. Troceado ───────────────────────────────────────────────────────────────
_HEADERS = [("#", "h1"), ("##", "h2")]


def _con_encabezados(doc: Document) -> str:
    """
    Antepone la ruta de encabezados al texto del chunk.

    Es la pieza que más rinde en recuperación sobre este corpus: "página",
    "planificación" o "proceso" aparecen en temas muy distintos, y sin el título
    del documento el chunk es ambiguo. Se reconstruye a mano (en vez de usar
    strip_headers=False) para que *todos* los sub-chunks de una sección larga lo
    lleven, no solo el primero.
    """
    lineas = []
    if h1 := doc.metadata.get("h1"):
        lineas.append(f"# {h1}")
    if h2 := doc.metadata.get("h2"):
        lineas.append(f"## {h2}")
    lineas.append("")
    lineas.append(doc.page_content)
    return "\n".join(lineas)


def _fusionar_pequenas(secciones: list[Document]) -> list[Document]:
    """
    Fusiona secciones contiguas mientras el resultado no pase de MIN_CHUNK.

    Solo fusiona dentro del mismo documento y bajo el mismo H1, para no juntar
    nunca contenido de temas distintos. El H2 resultante se queda con el de la
    primera sección, que es la que da contexto al bloque.
    """
    fusionadas: list[Document] = []
    for sec in secciones:
        if not fusionadas:
            fusionadas.append(sec)
            continue

        previa = fusionadas[-1]
        misma_rama = (
            previa.metadata.get("source") == sec.metadata.get("source")
            and previa.metadata.get("h1") == sec.metadata.get("h1")
        )
        cabe = len(previa.page_content) + len(sec.page_content) <= MIN_CHUNK

        if misma_rama and cabe:
            # El H2 de la sección absorbida se conserva dentro del texto para no
            # perder ese nivel de contexto.
            titulo = sec.metadata.get("h2")
            extra = f"## {titulo}\n\n{sec.page_content}" if titulo else sec.page_content
            previa.page_content = f"{previa.page_content}\n\n{extra}"
        else:
            fusionadas.append(sec)

    return fusionadas


# ── Portadas e índices ────────────────────────────────────────────────────────
# Los PDF exportados de PLATEA (Moodle) traen una portada con los campos del
# curso y, casi siempre, un índice con la lista de secciones del tema. Ninguna
# de las dos cosas responde a nada, y el índice además es un imán de palabras
# clave: contiene todos los títulos del tema, así que compite con el contenido
# real en cualquier búsqueda sobre ese tema.
#
# Se descartan *antes* de fusionar secciones. Si se hiciera después, un índice
# pequeño se habría fusionado ya con el contenido que le sigue, y ese contenido
# heredaría "Tabla de contenidos" como título: citas que engañan al lector.
#
# Ojo con lo que NO se descarta: las secciones "Descripción" se conservan. Son
# el resumen de una o dos frases de cada tema, y sí responden a preguntas del
# tipo "¿de qué trata el tema 8?".
#
# Y ojo sobre todo con esto: marcar la sección NO significa tirarla entera. Los
# libros de Moodle tienen esta forma, y Docling la respeta:
#
#     ## <Título del libro>    campos del curso                     (chatarra)
#     ## Tabla de contenidos   índice + autoría + licencia          (chatarra)
#                              + PRESENTACIÓN DEL MÓDULO            (contenido)
#     ## 1. Introducción       ...
#
# La presentación del módulo cuelga del mismo ## que el índice, así que tirar la
# sección entera se llevaba por delante la introducción de cada tema: 19.197
# caracteres del corpus, incluida la definición de qué es un sistema operativo.
# Por eso la chatarra se recorta por líneas y se conserva la prosa (ver
# `rescatar_prosa`).
_CAMPOS_PORTADA = ("Sitio:", "Curso:", "Libro:", "Imprimido por:", "Día:", "Copyright:")
_MIN_CAMPOS_PORTADA = 3

# Una línea es prosa si tiene al menos estas palabras. Las entradas de índice,
# los campos de portada y los pies de página se quedan todos por debajo.
_MIN_PALABRAS_PROSA = 15

# Lo rescatado tiene que dar para un vector con sentido; si no, la sección era
# chatarra de principio a fin.
MIN_PROSA_RESCATADA = 200

# El texto rescatado es siempre la presentación del módulo. Se le pone un título
# propio: heredar "Tabla de contenidos" es justo la cita engañosa que se quería
# evitar. No colisiona con las secciones "1. Introducción" que ya existen, así
# que el deduplicador de la recuperación no las confunde.
_H2_INTRO = "Introducción del módulo"

_LINEA_LICENCIA = re.compile(r"creative\s*commons|creativecommons\.org", re.IGNORECASE)

# Los guiones de prácticas traen su índice con puntos guía ("Introducción....4")
# maquetado como tabla, y colgando del título de la propia práctica: no hay
# detector por título que lo pille. Se exigen las DOS señales, fila de tabla y
# puntos guía, porque en P09 hay un comentario dentro de un script con ocho
# puntos seguidos que si no se iría por delante.
_FILA_INDICE = re.compile(r"^\s*\|.*\.{8,}")

# El título del índice se exige COMPLETO, no como prefijo. Con un prefijo,
# "Índice invertido de n-gramas" —un ejercicio de shell de la relación de
# problemas— se descartaba como si fuera el índice del documento.
_H2_INDICE = re.compile(
    r"^\s*(tabla\s+de\s+contenidos|contenidos|[íi]ndice(\s+de\s+contenidos)?)\s*$",
    re.IGNORECASE,
)
# Aquí sí vale el prefijo: el título es literalmente "Autor: Lina García-Cabrera".
_H2_AUTORIA = re.compile(r"^\s*(autor|copyright)\s*:", re.IGNORECASE)


def es_portada_o_indice(seccion: Document) -> bool:
    """¿La sección es portada del curso o índice de contenidos?"""
    h2 = (seccion.metadata.get("h2") or "").strip()
    if _H2_INDICE.match(h2) or _H2_AUTORIA.match(h2):
        return True
    campos = sum(1 for c in _CAMPOS_PORTADA if c in seccion.page_content)
    return campos >= _MIN_CAMPOS_PORTADA


def _es_prosa(linea: str) -> bool:
    """¿La línea es texto corrido, y no chatarra de portada?"""
    # El índice viene a veces maquetado como tabla ("| 6.5. Algoritmo LFU ..."),
    # y esas filas son largas: sin esta guarda pasarían por prosa.
    if linea.lstrip().startswith("|"):
        return False
    if _LINEA_LICENCIA.search(linea):
        return False
    return len(linea.split()) >= _MIN_PALABRAS_PROSA


def quitar_filas_de_indice(texto: str) -> str:
    """Quita las filas de índice con puntos guía, estén en la sección que estén."""
    lineas = [ln for ln in texto.split("\n") if not _FILA_INDICE.search(ln)]

    # Al quitarle las filas, el separador "|---|" de esa tabla se queda huérfano.
    limpias: list[str] = []
    for i, linea in enumerate(lineas):
        if linea.lstrip().startswith("|") and _es_separador(linea):
            siguiente = next((ln for ln in lineas[i + 1:] if ln.strip()), "")
            if not siguiente.lstrip().startswith("|"):
                continue
        limpias.append(linea)
    return "\n".join(limpias)


def rescatar_prosa(texto: str) -> str:
    """
    Devuelve el texto desde la primera línea de prosa de verdad.

    La chatarra de portada es siempre un *prefijo*: campos del curso, entradas
    de índice, autoría y licencia. Lo que venga después es la presentación del
    módulo y se conserva entera. Devuelve "" si no había prosa en ningún punto,
    que es el caso de las portadas puras.
    """
    lineas = texto.split("\n")
    for i, linea in enumerate(lineas):
        if _es_prosa(linea):
            return "\n".join(lineas[i:]).strip()
    return ""


def _es_separador(linea: str) -> bool:
    """¿Es la fila `|---|---|` que separa cabecera y cuerpo de una tabla?"""
    cuerpo = linea.replace("|", "").replace(" ", "")
    return bool(cuerpo) and set(cuerpo) <= set("-:")


def _cabecera_tabla_abierta(texto: str) -> list[str]:
    """
    Cabecera de la tabla que queda a medias al final del texto.

    Devuelve las dos líneas (títulos + separador) o [] si el texto no termina
    dentro de una tabla.
    """
    lineas = texto.split("\n")
    while lineas and not lineas[-1].strip():
        lineas.pop()
    if not lineas or not lineas[-1].startswith("|"):
        return []

    i = len(lineas) - 1
    while i > 0 and lineas[i - 1].startswith("|"):
        i -= 1
    bloque = lineas[i:]
    return bloque[:2] if len(bloque) >= 2 and _es_separador(bloque[1]) else []


def _reparar_bloques(trozos: list[Document]) -> list[Document]:
    """
    Recompone los bloques de código y las tablas que el corte por tamaño parte.

    Sin esto, subdividir una sección larga deja dos destrozos concretos:
      - Un chunk que abre ``` y nunca lo cierra (y el siguiente, que arranca a
        media orden de shell sin marca de que es código).
      - Un chunk que empieza con filas de tabla sin la fila de títulos, o sea
        columnas de números sin nombre: irrecuperable para el que lo lea.

    Se cierra el bloque de código al final y se reabre al principio del
    siguiente, y se repite la cabecera de la tabla en cada continuación.
    """
    cabecera: list[str] = []
    abierto = False

    for trozo in trozos:
        texto = trozo.page_content

        if abierto:
            texto = "```\n" + texto
        elif cabecera and texto.lstrip().startswith("|"):
            texto = "\n".join(cabecera) + "\n" + texto

        abierto = texto.count("```") % 2 == 1
        if abierto:
            texto = texto + "\n```"

        cabecera = _cabecera_tabla_abierta(texto)
        trozo.page_content = texto

    return trozos


def trocear(documentos: list[Document],
            chunk_size: int = CHUNK_SIZE,
            chunk_overlap: int = CHUNK_OVERLAP) -> list[Document]:
    """
    Trocea en tres fases: por encabezados, fusión de restos y subdivisión.

    La fase 3 solo toca las secciones que se pasan de tamaño (~5 % del corpus),
    así que el 95 % de los chunks son una sección H2 íntegra, con sus bloques de
    código y sus tablas sin cortar.
    """
    secciones = _fusionar_pequenas(_secciones_limpias(documentos))
    chunks = _subdividir(secciones, chunk_size, chunk_overlap)
    _asignar_ids(chunks)
    return chunks


def _secciones_limpias(documentos: list[Document]) -> list[Document]:
    """Fase 1: una sección por encabezado, sin portadas, índices ni filas de índice."""
    por_encabezados = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS,
        strip_headers=True,   # los reponemos en _con_encabezados()
    )

    secciones: list[Document] = []
    descartadas: list[Document] = []
    rescatadas: list[Document] = []
    for doc in documentos:
        for sec in por_encabezados.split_text(doc.page_content):
            if not sec.page_content.strip():
                continue
            sec.metadata = {**doc.metadata, **sec.metadata}

            sec.page_content = quitar_filas_de_indice(sec.page_content)
            if not sec.page_content.strip():
                continue

            if es_portada_o_indice(sec):
                prosa = rescatar_prosa(sec.page_content)
                if len(prosa) < MIN_PROSA_RESCATADA:
                    descartadas.append(sec)
                    continue
                # Se salva la presentación del módulo y se le da título propio.
                sec.page_content = prosa
                sec.metadata["h2"] = _H2_INTRO
                rescatadas.append(sec)

            secciones.append(sec)

    if descartadas:
        caracteres = sum(len(s.page_content) for s in descartadas)
        print(f"[dim]🧹 {len(descartadas)} sección(es) de portada/índice "
              f"descartada(s) ({caracteres:,} caracteres)[/dim]")
    if rescatadas:
        caracteres = sum(len(s.page_content) for s in rescatadas)
        print(f"[dim]💾 {len(rescatadas)} presentación(es) de módulo rescatada(s) "
              f"de esas secciones ({caracteres:,} caracteres)[/dim]")
    return secciones


def _subdividir(secciones: list[Document], chunk_size: int,
                chunk_overlap: int) -> list[Document]:
    """Fase 3: parte las secciones que no caben y antepone la ruta de encabezados."""
    # El orden de separadores busca cortar por párrafo antes que por línea, y
    # por línea antes que por frase. Cortar a mitad de palabra es el último
    # recurso.
    por_tamano = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks: list[Document] = []
    for sec in secciones:
        if len(sec.page_content) <= chunk_size:
            trozos = [sec]
        else:
            # El estado de _reparar_bloques se reinicia en cada sección: una
            # tabla nunca continúa de una sección a la siguiente.
            trozos = _reparar_bloques(por_tamano.split_documents([sec]))

        for trozo in trozos:
            texto = _con_encabezados(trozo)
            if not texto.strip():
                continue
            # Chroma no acepta None en los metadatos.
            meta = {k: v for k, v in trozo.metadata.items() if v is not None}
            meta["n_chars"] = len(texto)
            chunks.append(Document(page_content=texto, metadata=meta))
    return chunks


def _asignar_ids(chunks: list[Document]) -> None:
    """Un id estable por (documento, posición): "<fichero>.md#0007".

    Así reindexar actualiza los chunks en vez de duplicarlos, y ordenar los ids
    como cadena deja los chunks en el orden del documento.
    """
    por_fuente: dict[str, int] = {}
    for chunk in chunks:
        fuente = chunk.metadata.get("source", "?")
        idx = por_fuente.get(fuente, 0)
        por_fuente[fuente] = idx + 1
        chunk.metadata["chunk_id"] = f"{fuente}#{idx:04d}"


# ── 3. Indexado ───────────────────────────────────────────────────────────────
# Los embeddings los construye `rag.config.construir_embeddings()`: es la misma
# fábrica que usa el recuperador al consultar, con el mismo modelo y las mismas
# dimensiones. Ver la nota de ese módulo sobre por qué eso importa tanto.
def indexar(chunks: list[Document],
            chroma_dir: str | Path = CHROMA_ACTIVO,
            coleccion: str = COLLECTION,
            reiniciar: bool = False) -> None:
    """Vectoriza los chunks por lotes y los guarda en ChromaDB."""
    from langchain_chroma import Chroma

    embeddings = construir_embeddings()
    ruta_chroma = resolver(chroma_dir)

    # El sello deja constancia de con qué se construyó el índice, para que
    # `rag.recuperacion.build_vectordb` pueda negarse a consultarlo con otra
    # cosa. `n_chunks` va porque la mitad léxica del híbrido (BM25) se monta
    # sobre los documentos de la colección: si dos corridas no vieron el mismo
    # corpus, la diferencia entre ellas deja de ser atribuible al embedding.
    #
    # Ojo: Chroma sólo graba `collection_metadata` al CREAR la colección. En una
    # que ya existe lo ignora, así que el sello sólo entra con `--reset`.
    vectordb = Chroma(
        collection_name=coleccion,
        embedding_function=embeddings,
        persist_directory=str(ruta_chroma),
        collection_metadata={
            "hnsw:space": DISTANCIA,
            CLAVE_META_MODELO: EMBEDDING_MODEL,
            CLAVE_META_DIMS: EMBEDDING_DIMS,
            CLAVE_META_CHUNKS: len(chunks),
        },
    )

    if reiniciar:
        vectordb.reset_collection()
        print(f"[yellow]♻️  Colección \"{coleccion}\" reiniciada[/yellow]")

    total = len(chunks)
    t_inicio = time.time()

    for inicio in range(0, total, BATCH_SIZE):
        lote = chunks[inicio:inicio + BATCH_SIZE]
        ids = [c.metadata["chunk_id"] for c in lote]
        vectordb.add_documents(documents=lote, ids=ids)
        hechos = min(inicio + BATCH_SIZE, total)
        print(f"[dim]   {hechos}/{total} chunks indexados[/dim]")

    print(f"[bold green]✅ {total} chunks en \"{ruta_chroma}\"[/bold green] "
          f"[dim]({time.time() - t_inicio:.1f}s)[/dim]")


# ── Estadísticas ──────────────────────────────────────────────────────────────
def resumen(chunks: list[Document]) -> None:
    """Imprime la distribución de tamaños y los tokens estimados."""
    tam = sorted(len(c.page_content) for c in chunks)
    n = len(tam)
    if not n:
        print("[red]No se ha generado ningún chunk.[/red]")
        return

    def pct(p: float) -> int:
        return tam[int(p * (n - 1))]

    caracteres = sum(tam)
    tokens = caracteres / CARACTERES_POR_TOKEN

    print()
    print(f"[bold]Chunks:[/bold] {n}   [bold]caracteres:[/bold] {caracteres:,}"
          f"   [bold]tokens estimados:[/bold] {tokens:,.0f}")
    print(f"  min={tam[0]}  p25={pct(.25)}  mediana={pct(.5)}  "
          f"p75={pct(.75)}  p90={pct(.90)}  max={tam[-1]}")
    print(f"  media={caracteres // n} caracteres (~{caracteres / n / CARACTERES_POR_TOKEN:.0f} tokens)")

    fuentes = Counter(c.metadata.get("source", "?") for c in chunks)
    print(f"  {len(fuentes)} documento(s), "
          f"{min(fuentes.values())}-{max(fuentes.values())} chunks por documento")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trocea los Markdown e indexa los chunks en ChromaDB.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--md-folder", default=str(MD_DIR),
                        help="Directorio con los Markdown de entrada")
    parser.add_argument("--chroma-dir", default=str(CHROMA_ACTIVO),
                        help="Directorio de persistencia de ChromaDB")
    parser.add_argument("--collection", default=COLLECTION,
                        help="Nombre de la colección de ChromaDB")
    parser.add_argument("--only", default=None,
                        help="Procesa solo los .md cuyo nombre contenga alguno de "
                             "estos textos, separados por comas")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                        help="Tamaño máximo de chunk en caracteres")
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP,
                        help="Solapamiento al subdividir secciones grandes")
    parser.add_argument("--reset", action="store_true",
                        help="Vacía la colección antes de indexar")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo trocea y muestra estadísticas, sin llamar a la API")
    return parser.parse_args()


def main() -> int:
    """Punto de entrada de la CLI. Devuelve el código de salida del proceso."""
    args = parse_args()

    try:
        return _ejecutar(args)
    except ErrorConfiguracion as exc:
        # Los errores de configuración se cuentan como un mensaje claro, no como
        # una traza: casi siempre son una ruta mal escrita o la clave sin poner.
        print(f"[red]❌ {exc}[/red]")
        return 1


def _ejecutar(args: argparse.Namespace) -> int:
    # Lo primero de todo, antes de tocar nada: con qué se va a indexar y dónde.
    # `--reset` vacía la colección, y no debería ejecutarse a ciegas.
    print(f"[bold]Proveedor:[/bold] {EMBEDDING_PROVIDER} · {EMBEDDING_MODEL} · "
          f"{EMBEDDING_DIMS} dims · colección \"{args.collection}\" · "
          f"{args.chroma_dir}")

    documentos = cargar_documentos(args.md_folder, solo=args.only)
    print(f"[cyan]📄 {len(documentos)} documento(s) cargado(s)[/cyan]")

    chunks = trocear(documentos,
                     chunk_size=args.chunk_size,
                     chunk_overlap=args.chunk_overlap)
    resumen(chunks)

    if args.dry_run:
        print("\n[yellow]--dry-run: no se ha llamado a la API ni se ha tocado "
              "ChromaDB.[/yellow]")
        return 0

    print()
    indexar(chunks,
            chroma_dir=args.chroma_dir,
            coleccion=args.collection,
            reiniciar=args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
