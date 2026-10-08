"""
cli — Las órdenes de consola del proyecto, en el orden del pipeline.

Se lanzan desde la raíz del repositorio con `python -m`:

    python -m cli.pdf_to_md       # 1. PDF -> Markdown (Docling), incremental
    python -m cli.process_md      # 2. Markdown -> fragmentos -> ChromaDB
    python -m cli.chat            # 3. chat con el RAG en la terminal
    python -m cli.inspeccionar    #    ChromaDB, el troceado y la recuperación por dentro

Toda la lógica del RAG vive en `rag/`; aquí sólo hay entrada y salida.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rag.config import PROJECT_DIR


def consola_utf8() -> None:
    """Fuerza UTF-8 en la salida estándar y la de errores.

    La consola de Windows usa cp1252 por defecto y revienta con los emojis y los
    acentos de los mensajes: sin esto, el primer print lanzaría un
    UnicodeEncodeError.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def resolver(ruta: str | Path) -> Path:
    """Una ruta relativa, resuelta contra la raíz del proyecto.

    Así las órdenes se comportan igual se lancen desde donde se lancen: las rutas
    que llegan por línea de órdenes cuelgan de la raíz, no del directorio de
    trabajo.
    """
    p = Path(ruta)
    return p if p.is_absolute() else PROJECT_DIR / p


# Antes que cualquier otro import de las órdenes: `rich` decide la codificación
# de su consola al crearla.
consola_utf8()
