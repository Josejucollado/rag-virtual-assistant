"""
Conversión incremental de PDF a Markdown usando Docling.

Prioriza dos cosas sobre la salida:
  1. La estructura del documento (encabezados, listas, orden de lectura), que es
     lo que aprovecha el troceado por encabezados de `cli/process_md.py`.
  2. La fidelidad de las tablas, mediante el modelo TableFormer en modo ACCURATE
     con emparejamiento de celdas contra el texto real del PDF.

Es incremental: guarda el hash MD5 de cada PDF y solo reconvierte los que son
nuevos o han cambiado. Es un convertidor puro; la indexación en ChromaDB sigue
siendo responsabilidad de `cli/process_md.py`.

Necesita las dependencias de ingesta (`pip install -r requirements-ingesta.txt`).

Uso:
    python -m cli.pdf_to_md                   # convierte lo que falte
    python -m cli.pdf_to_md --force           # reconvierte todo
    python -m cli.pdf_to_md --ocr             # activa OCR (PDFs escaneados)
    python -m cli.pdf_to_md --pdf-folder otra/ruta --md-folder otra/salida

    # PDF con capa de texto corrupta (fuente sin ToUnicode: extrae ❯❳❡❨ en vez
    # de letras). Rasteriza la página e ignora esa capa:
    python -m cli.pdf_to_md --force-ocr --only "Problemas tema 1"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from rich import print

from cli import resolver
# Los directorios del corpus son los mismos que usa el resto del proyecto.
from rag.config import HASHES_JSON, MD_DIR, PDF_DIR, ErrorConfiguracion

# Por debajo de este número de caracteres por página se sospecha que el PDF es
# una imagen escaneada y se avisa de que hay que reejecutar con --ocr.
MIN_CARACTERES_POR_PAGINA = 50

# Marcador que Docling deja donde había una figura.
PLACEHOLDER_IMAGEN = "<!-- image -->"

# Margen (en puntos) que se añade al recorte de una región marcada como imagen.
# Sin él, PyMuPDF pierde la línea inferior de la rejilla y devuelve solo la
# primera fila de la tabla.
MARGEN_RESCATE = 4.0

# Proporción mínima de celdas con contenido para aceptar una rejilla como tabla.
# Es lo que distingue una tabla real de un diagrama: los cronogramas de Gantt de
# las relaciones de problemas (barras P1/P2 sobre ejes dispositivo/tiempo) tienen
# rejilla y engañan a find_tables, pero se quedan entre el 50% y el 75% de
# relleno, mientras que las tablas de verdad llegan al 100%. Reconstruir un Gantt
# como tabla pierde los ejes y produce datos engañosos: es peor que dejar la
# figura sin tocar.
MIN_RELLENO_TABLA = 0.85

# Una figura que se solapa en más de esta fracción de su área con una tabla ya
# extraída es la misma región marcada dos veces, no una tabla nueva.
MAX_SOLAPE_CON_TABLA = 0.5

# Escala a la que RapidOCR rasteriza la página con --force-ocr: más resolución
# para los caracteres pequeños, a cambio de más tiempo por página.
ESCALA_OCR = 3.0

# El modelo latino de RapidOCR: el que trae por defecto es chino y destroza los
# acentos y los signos ¿¡ del castellano.
IDIOMA_OCR = "latin"


# ── Utilidades de hashes ──────────────────────────────────────────────────────
def get_file_hash(file_path: str | Path) -> str:
    """Calcula el hash MD5 de un archivo para detectar cambios."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for bloque in iter(lambda: f.read(8192), b""):
            hasher.update(bloque)
    return hasher.hexdigest()


def cargar_hashes(hashes_path: Path) -> dict:
    """Carga el diccionario de hashes existente desde disco."""
    if hashes_path.exists():
        with open(hashes_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_hashes(hashes: dict, hashes_path: Path) -> None:
    """Persiste el diccionario de hashes en disco."""
    hashes_path.parent.mkdir(parents=True, exist_ok=True)
    with open(hashes_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(hashes, f, indent=2, ensure_ascii=False)


# ── Configuración de Docling ──────────────────────────────────────────────────
def construir_conversor(usar_ocr: bool, num_hilos: int,
                        forzar_ocr: bool = False, ocr_lang: str = IDIOMA_OCR):
    """
    Crea el DocumentConverter una única vez.

    Los imports van dentro de la función porque cargar Docling arrastra torch y
    tarda varios segundos: sólo se paga si hay algo que convertir.
    """
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        RapidOcrOptions,
        TableFormerMode,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()

    # Sin OCR: casi todos los PDFs de la asignatura tienen capa de texto real, así
    # que el OCR solo aportaría lentitud y errores de transcripción.
    opts.do_ocr = usar_ocr or forzar_ocr

    # OCR de página completa. Hace falta cuando el PDF *sí* tiene capa de texto
    # pero es basura: si la fuente incrustada no trae tabla ToUnicode, la
    # extracción devuelve símbolos (❯❳❡❨) en vez de letras. Con `do_ocr` a secas
    # Docling da prioridad a esa capa de texto y el OCR nunca llega a actuar;
    # `force_full_page_ocr` rasteriza la página y la ignora por completo.
    if forzar_ocr:
        opts.ocr_options = RapidOcrOptions(
            lang=[ocr_lang], force_full_page_ocr=True, scale=ESCALA_OCR
        )

    # Prioridad 1: estructura. El modelo de layout etiqueta cada bloque
    # (section_header, list_item, table, caption...) y de ahí salen los # y ##.
    # Prioridad 2: tablas. ACCURATE usa el TableFormer grande, mucho mejor con
    # celdas combinadas y bordes implícitos; do_cell_matching toma el texto de
    # cada celda del PDF original en lugar de predecirlo.
    opts.do_table_structure = True
    opts.table_structure_options.mode = TableFormerMode.ACCURATE
    opts.table_structure_options.do_cell_matching = True

    # No hacen falta imágenes de página: las figuras se exportan como <!-- image -->.
    opts.generate_page_images = False

    opts.accelerator_options = AcceleratorOptions(
        num_threads=num_hilos,
        device=AcceleratorDevice.AUTO,
    )

    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def exportar_markdown(documento, titulo: str) -> str:
    """
    Exporta el documento a Markdown.

    escape_html y escape_underscores se desactivan a propósito: con los valores
    por defecto, `uniq_all.sh` se convierte en `uniq\\_all.sh` y los operadores
    `<`, `>` y `&&` en `&lt;`, `&gt;` y `&amp;&amp;`. En documentación de shell y
    sistemas operativos eso ensucia el texto y perjudica a la recuperación.
    """
    md = documento.export_to_markdown(
        escape_html=False,
        escape_underscores=False,
        image_placeholder=PLACEHOLDER_IMAGEN,
    ).strip()

    # Docling suele empezar en nivel ##. Un H1 con el nombre del tema queda en
    # los metadatos de todas las secciones al trocear, y `process_md` lo antepone
    # a cada chunk: sin él, un chunk sobre "páginas" no diría de qué tema es.
    if not md.startswith("# "):
        md = f"# {titulo}\n\n{md}"

    return md


# ── Rescate de regiones mal etiquetadas como imagen ───────────────────────────
# El modelo de layout a veces clasifica como `picture` una tabla pequeña sin
# bordes exteriores (p. ej. las rejillas de índices de las prácticas de shell).
# Cuando eso pasa, TableFormer nunca la analiza y su texto se pierde: en el
# Markdown solo queda un <!-- image -->. Como el texto sigue estando en el PDF,
# se recupera con PyMuPDF, que además reconstruye la rejilla si tiene líneas.
def _rect_de_bbox(documento, fitz_doc, item, margen: float):
    """Traduce el bbox de un item de Docling a un rectángulo de PyMuPDF."""
    import fitz
    from docling_core.types.doc.base import CoordOrigin

    prov = item.prov[0]
    pagina = fitz_doc[prov.page_no - 1]
    tam = documento.pages[prov.page_no].size
    bb = prov.bbox

    # Docling mide desde abajo-izquierda; PyMuPDF desde arriba-izquierda.
    if bb.coord_origin == CoordOrigin.BOTTOMLEFT:
        y_sup, y_inf = tam.height - bb.t, tam.height - bb.b
    else:
        y_sup, y_inf = bb.t, bb.b

    sx = pagina.rect.width / tam.width
    sy = pagina.rect.height / tam.height

    rect = fitz.Rect(bb.l * sx - margen, y_sup * sy - margen,
                     bb.r * sx + margen, y_inf * sy + margen)
    return pagina, rect & pagina.rect


def _pisa_una_tabla_ya_extraida(documento, fitz_doc, item, rect) -> bool:
    """
    ¿La figura se solapa con una tabla que Docling ya ha extraído?

    A veces el modelo de layout marca la misma región dos veces, como tabla y
    como figura. Sin esta comprobación el rescate duplicaría en el Markdown
    contenido que Docling ya había puesto.
    """
    pagina_no = item.prov[0].page_no
    for tabla in documento.tables:
        if not getattr(tabla, "prov", None) or tabla.prov[0].page_no != pagina_no:
            continue
        try:
            _, rect_tabla = _rect_de_bbox(documento, fitz_doc, tabla, 0.0)
        except Exception:
            continue
        interseccion = rect & rect_tabla
        if (not interseccion.is_empty
                and interseccion.get_area() > MAX_SOLAPE_CON_TABLA * rect.get_area()):
            return True
    return False


def _filas_a_markdown(filas: list[list]) -> str | None:
    """
    Convierte las filas devueltas por PyMuPDF en Markdown.

    Devuelve una tabla si quedan al menos dos columnas con contenido, una lista
    si solo queda una (es el caso de las preguntas tipo test con casillas, que
    PyMuPDF ve como una rejilla de una sola columna útil) o None si no hay nada
    aprovechable.
    """
    def celda(v) -> str:
        return (v or "").replace("\n", " ").replace("|", "\\|").strip()

    ancho = max(len(f) for f in filas)
    norm  = [[celda(c) for c in f] + [""] * (ancho - len(f)) for f in filas]

    # Descartar columnas vacías en todas las filas: las rejillas de las figuras
    # suelen traer columnas fantasma que solo añaden ruido.
    utiles = [j for j in range(ancho) if any(fila[j] for fila in norm)]
    norm   = [[fila[j] for j in utiles] for fila in norm]
    norm   = [fila for fila in norm if any(fila)]

    if not norm:
        return None

    # Filtro anti-diagrama: una rejilla medio vacía casi nunca es una tabla.
    llenas = sum(1 for fila in norm for c in fila if c)
    if llenas / (len(norm) * len(utiles)) < MIN_RELLENO_TABLA:
        return None

    if len(utiles) == 1:
        if len(norm) < 2:
            return None
        return "\n".join(f"- {fila[0]}" for fila in norm)

    cabecera, cuerpo = norm[0], norm[1:]
    lineas = ["| " + " | ".join(cabecera) + " |",
              "|" + "|".join(["---"] * len(utiles)) + "|"]
    lineas += ["| " + " | ".join(f) + " |" for f in cuerpo]
    return "\n".join(lineas)


def rescatar_tablas_en_figuras(documento, ruta_pdf: Path, md: str) -> tuple[str, int]:
    """
    Sustituye los marcadores de figura por la tabla real, cuando lo es.

    Devuelve (markdown, nº de tablas recuperadas).
    """
    import fitz
    from docling_core.types.doc.labels import DocItemLabel

    figuras = [it for it, _ in documento.iterate_items()
               if getattr(it, "label", None) == DocItemLabel.PICTURE and getattr(it, "prov", None)]

    # Si los marcadores no cuadran con las figuras no se pueden emparejar sin
    # riesgo de desalinear el documento: en ese caso no se toca nada.
    if not figuras or md.count(PLACEHOLDER_IMAGEN) != len(figuras):
        return md, 0

    bloques = []
    with fitz.open(str(ruta_pdf)) as fitz_doc:
        for item in figuras:
            try:
                pagina, rect = _rect_de_bbox(documento, fitz_doc, item, MARGEN_RESCATE)
                if _pisa_una_tabla_ya_extraida(documento, fitz_doc, item, rect):
                    bloques.append(None)
                    continue
                tablas = pagina.find_tables(clip=rect, strategy="lines").tables
                filas  = tablas[0].extract() if tablas else []
                filas  = [f for f in filas if any((c or "").strip() for c in f)]
                bloques.append(_filas_a_markdown(filas) if len(filas) >= 2 else None)
            except Exception:
                bloques.append(None)

    partes = md.split(PLACEHOLDER_IMAGEN)
    salida = partes[0]
    for bloque, resto in zip(bloques, partes[1:]):
        salida += (bloque or PLACEHOLDER_IMAGEN) + resto

    return salida, sum(b is not None for b in bloques)


# ── Proceso principal ─────────────────────────────────────────────────────────
# Hilos para el acelerador de Docling: todos los núcleos disponibles.
HILOS_POR_DEFECTO = os.cpu_count() or 4


def _purgar_hashes(hashes: dict, archivos_pdf: list[str], dir_md: Path) -> None:
    """Quita del registro los PDF que ya no están en el directorio de entrada."""
    presentes = set(archivos_pdf)
    for k in [k for k in hashes if k not in presentes]:
        del hashes[k]
        print(f"[dim]🗑  \"{k}\" ya no está en el directorio de PDFs, se elimina del registro de hashes[/dim]")
        md_huerfano = dir_md / (Path(k).stem + ".md")
        if md_huerfano.exists():
            print(f"[dim]   (queda un .md huérfano: {md_huerfano.name} — bórralo a mano si no lo quieres)[/dim]")


def _pendientes(archivos_pdf: list[str], dir_pdf: Path, dir_md: Path,
                hashes: dict, reconvertir: bool) -> dict[str, str]:
    """Los PDF que hay que convertir, cada uno con su hash actual.

    El hash se devuelve para registrarlo después de convertir sin volver a leer
    el PDF. `reconvertir` (--force o --force-ocr) convierte aunque el hash no
    haya cambiado: con --force-ocr cambia la forma de extraer el texto.
    """
    pendientes: dict[str, str] = {}
    for archivo in archivos_pdf:
        ruta_md = dir_md / (Path(archivo).stem + ".md")
        hash_actual = get_file_hash(dir_pdf / archivo)

        if reconvertir:
            pendientes[archivo] = hash_actual
        elif hashes.get(archivo) == hash_actual and ruta_md.exists():
            print(f"[dim]✔  Documento \"{archivo}\" ya procesado, se omite[/dim]")
        elif archivo not in hashes:
            print(f"[cyan]📄 Documento \"{archivo}\" no procesado, se convertirá[/cyan]")
            pendientes[archivo] = hash_actual
        elif hashes.get(archivo) != hash_actual:
            print(f"[yellow]♻️  Documento \"{archivo}\" ha cambiado, se reconvertirá[/yellow]")
            pendientes[archivo] = hash_actual
        else:  # hash igual pero falta el .md
            print(f"[cyan]📄 Documento \"{archivo}\" sin Markdown en destino, se convertirá[/cyan]")
            pendientes[archivo] = hash_actual
    return pendientes


def _convertir_uno(conversor, ruta_pdf: Path, ruta_md: Path, usar_ocr: bool) -> bool:
    """Convierte un PDF y escribe su Markdown. Devuelve si ha ido bien."""
    t_doc = time.time()
    try:
        documento = conversor.convert(str(ruta_pdf)).document
        md_texto = exportar_markdown(documento, titulo=ruta_pdf.stem)
        md_texto, rescatadas = rescatar_tablas_en_figuras(documento, ruta_pdf, md_texto)
    except Exception as e:  # noqa: BLE001 - un PDF roto no para el lote
        print(f"[red]❌ Error al convertir \"{ruta_pdf.name}\": {e}[/red]")
        return False

    if not md_texto.strip():
        print(f"[red]❌ No se pudo extraer texto de \"{ruta_pdf.name}\"[/red]")
        return False

    ruta_md.write_text(md_texto, encoding="utf-8")

    n_paginas = len(documento.pages) or 1
    n_tablas  = len(documento.tables)
    extra = f", +{rescatadas} rescatada(s) de figuras" if rescatadas else ""
    print(f"[green]✅ \"{ruta_pdf.name}\" → \"{ruta_md.name}\"[/green] "
          f"[dim]({n_paginas} págs, {n_tablas} tablas{extra}, {time.time() - t_doc:.1f}s)[/dim]")

    if not usar_ocr and len(md_texto) / n_paginas < MIN_CARACTERES_POR_PAGINA:
        print(f"[yellow]⚠️  \"{ruta_pdf.name}\" ha producido muy poco texto "
              f"({len(md_texto)} caracteres en {n_paginas} págs). "
              f"¿Es un PDF escaneado? Reejecuta con --ocr[/yellow]")
    return True


def pdf_a_md(directorio_pdf: str | Path = PDF_DIR,
             directorio_md:  str | Path = MD_DIR,
             hashes_path:    str | Path = HASHES_JSON,
             forzar:   bool = False,
             usar_ocr: bool = False,
             num_hilos: int = HILOS_POR_DEFECTO,
             forzar_ocr: bool = False,
             ocr_lang: str = IDIOMA_OCR,
             solo: str | None = None) -> None:
    """Convierte a Markdown los PDFs nuevos o modificados del directorio de entrada."""
    dir_pdf = resolver(directorio_pdf)
    dir_md  = resolver(directorio_md)
    ruta_hashes = resolver(hashes_path)

    if not dir_pdf.is_dir():
        raise ErrorConfiguracion(f"No existe el directorio de PDFs: {dir_pdf}")
    dir_md.mkdir(parents=True, exist_ok=True)

    todos = sorted(f for f in os.listdir(dir_pdf) if f.lower().endswith(".pdf"))
    if not todos:
        print("[yellow]⚠️  No se encontraron archivos PDF en el directorio de entrada.[/yellow]")
        return

    hashes = cargar_hashes(ruta_hashes)

    # `--only` restringe el trabajo a los PDFs cuyo nombre contiene el patrón,
    # pero la limpieza de hashes mira la lista completa para no borrar del
    # registro los PDFs que simplemente no encajan con el filtro.
    archivos_pdf = todos
    if solo:
        archivos_pdf = [f for f in todos if solo.lower() in f.lower()]
        if not archivos_pdf:
            print(f"[yellow]⚠️  Ningún PDF coincide con --only \"{solo}\".[/yellow]")
            return
        print(f"[dim]🔎 --only \"{solo}\": {len(archivos_pdf)} PDF(s) seleccionado(s)[/dim]")

    _purgar_hashes(hashes, todos, dir_md)

    # Se decide qué hay que convertir antes de cargar los modelos de Docling.
    pendientes = _pendientes(archivos_pdf, dir_pdf, dir_md, hashes,
                             reconvertir=forzar or forzar_ocr)
    if not pendientes:
        print()
        print("[bold green]✅ Todo al día: no hay documentos que convertir.[/bold green]")
        guardar_hashes(hashes, ruta_hashes)
        return

    print()
    if forzar_ocr:
        modo_ocr = f"forzado a página completa (lang={ocr_lang})"
    elif usar_ocr:
        modo_ocr = "activado"
    else:
        modo_ocr = "desactivado"

    print(f"[bold cyan]Cargando Docling ({len(pendientes)} documento(s) por convertir, "
          f"OCR {modo_ocr}, {num_hilos} hilos)...[/bold cyan]")
    print("[dim]La primera ejecución descarga los modelos de layout y TableFormer.[/dim]")

    conversor = construir_conversor(usar_ocr=usar_ocr, num_hilos=num_hilos,
                                    forzar_ocr=forzar_ocr, ocr_lang=ocr_lang)

    procesados = 0
    errores    = 0
    t_inicio   = time.time()

    for i, (archivo, hash_pdf) in enumerate(pendientes.items(), start=1):
        print(f"[cyan][{i}/{len(pendientes)}] Convirtiendo \"{archivo}\"...[/cyan]")
        ruta_md = dir_md / (Path(archivo).stem + ".md")
        if not _convertir_uno(conversor, dir_pdf / archivo, ruta_md, usar_ocr):
            errores += 1
            continue

        # El hash solo se registra tras escribir el .md con éxito, y se persiste
        # tras cada documento para no perder el progreso si se interrumpe.
        hashes[archivo] = hash_pdf
        guardar_hashes(hashes, ruta_hashes)
        procesados += 1

    guardar_hashes(hashes, ruta_hashes)

    omitidos = len(archivos_pdf) - len(pendientes)
    print()
    print(f"[bold green]Conversión completada:[/bold green] "
          f"{procesados} procesados, {omitidos} omitidos, {errores} errores "
          f"[dim](total {time.time() - t_inicio:.1f}s)[/dim]")
    print(f"[dim]Markdown en: {dir_md}[/dim]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convierte PDFs a Markdown con Docling, de forma incremental.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--pdf-folder", default=str(PDF_DIR),
                        help="Directorio de entrada con los PDFs")
    parser.add_argument("--md-folder", default=str(MD_DIR),
                        help="Directorio de salida para los Markdown (se crea si no existe)")
    parser.add_argument("--hashes", default=str(HASHES_JSON),
                        help="Ruta del JSON donde se registran los hashes de los PDFs")
    parser.add_argument("--force", action="store_true",
                        help="Reconvierte todos los PDFs, ignorando los hashes")
    parser.add_argument("--ocr", action="store_true",
                        help="Activa el OCR (necesario solo para PDFs escaneados)")
    parser.add_argument("--force-ocr", action="store_true",
                        help="OCR de página completa, ignorando la capa de texto del PDF. "
                             "Para PDFs cuya fuente incrustada no tiene ToUnicode y "
                             "extraen símbolos en vez de letras. Implica reconversión.")
    parser.add_argument("--ocr-lang", default=IDIOMA_OCR,
                        help="Modelo de idioma de RapidOCR ('latin' para castellano)")
    parser.add_argument("--only", default=None,
                        help="Procesa solo los PDFs cuyo nombre contenga este texto")
    parser.add_argument("--threads", type=int, default=HILOS_POR_DEFECTO,
                        help="Hilos para el acelerador de Docling")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        pdf_a_md(
            directorio_pdf=args.pdf_folder,
            directorio_md=args.md_folder,
            hashes_path=args.hashes,
            forzar=args.force,
            usar_ocr=args.ocr,
            num_hilos=args.threads,
            forzar_ocr=args.force_ocr,
            ocr_lang=args.ocr_lang,
            solo=args.only,
        )
    except ErrorConfiguracion as exc:
        print(f"[red]❌ {exc}[/red]")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
