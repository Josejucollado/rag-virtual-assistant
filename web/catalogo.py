"""
catalogo.py — Los documentos del corpus, listos para enseñar y descargar.

Los nombres reales llevan espacios, tildes y hasta un espacio de más
(`P11-shell-cadenas .pdf`), así que el cliente nunca manda rutas: manda un
`slug` que este módulo resuelve contra un mapa construido al arrancar. Cualquier
ruta que no cuelgue de `data/` se rechaza.

El puente PDF <-> Markdown <-> Chroma es el nombre base del fichero: `X.pdf` se
convierte en `X.md` y ese `X.md` es exactamente el metadato `source` de cada
chunk indexado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from rag import DATA_DIR, MD_DIR, PDF_DIR, cuerpo_sin_encabezados, recortar, sin_tildes

from .nucleo import NUCLEO

# Caracteres de la vista previa de un chunk en la ficha de un documento.
ANCHO_VISTA_PREVIA = 180


def hacer_slug(nombre: str) -> str:
    """'05 Memoria. Gestión de Memoria' -> '05-memoria-gestion-de-memoria'."""
    limpio = re.sub(r"[^a-z0-9]+", "-", sin_tildes(nombre)).strip("-")
    return limpio or "documento"


def clasificar(nombre: str) -> str:
    """Familia del documento, deducida del nombre. Sirve para filtrar en la web.

    «practica2», «sesion10-monitores-almacen» y la «Relación de ejercicios…»
    caían en «Otros» por no seguir el patrón P07…P11 ni decir «Problemas».
    """
    n = sin_tildes(nombre).upper()
    if re.match(r"^\d\d\s", nombre):
        return "Teoría"
    if re.match(r"^P\d", n) or n.startswith(("PRACTICA", "SESION")):
        return "Prácticas"
    if "PROBLEMAS" in n or "EJERCICIOS" in n:
        return "Problemas"
    if "PLATEA" in n:
        return "Guiones"
    return "Otros"


def titulo_legible(nombre: str) -> str:
    """El nombre para enseñar: 'practica2.md' (de «practica2.md.pdf») -> 'practica2'.

    Sólo para la vista: las descargas y el `source` de Chroma siguen usando el
    nombre real del fichero.
    """
    return re.sub(r"\.md$", "", nombre, flags=re.IGNORECASE).strip() or nombre


@dataclass
class Documento:
    slug: str
    nombre: str                      # nombre base, sin extensión
    fuente: str                      # "<nombre>.md", el `source` de Chroma
    familia: str
    pdf: Path | None
    md: Path | None
    bytes_pdf: int = 0
    bytes_md: int = 0
    n_chunks: int = 0
    n_caracteres: int = 0
    secciones: list[dict] = field(default_factory=list)

    @property
    def indexado(self) -> bool:
        return self.n_chunks > 0

    def resumen(self) -> dict:
        return {
            "slug": self.slug,
            "nombre": self.nombre,
            "titulo": titulo_legible(self.nombre),
            "fuente": self.fuente,
            "familia": self.familia,
            "tiene_pdf": self.pdf is not None,
            "tiene_md": self.md is not None,
            "bytes_pdf": self.bytes_pdf,
            "bytes_md": self.bytes_md,
            "n_chunks": self.n_chunks,
            "n_caracteres": self.n_caracteres,
            "n_secciones": len(self.secciones),
            "indexado": self.indexado,
        }


class Catalogo:
    """Mapa slug -> Documento, con las estadísticas de indexado ya resueltas."""

    def __init__(self) -> None:
        self.documentos: dict[str, Documento] = {}

    def construir(self) -> None:
        docs: dict[str, Documento] = {}

        # Un documento existe si tiene PDF o MD. Se recorren los dos directorios
        # para no ocultar una conversión huérfana ni un PDF sin convertir.
        nombres: dict[str, dict[str, Path]] = {}
        for directorio, clave in ((PDF_DIR, "pdf"), (MD_DIR, "md")):
            if not directorio.is_dir():
                continue
            for ruta in sorted(directorio.iterdir()):
                if not ruta.is_file():
                    continue
                if clave == "pdf" and ruta.suffix.lower() != ".pdf":
                    continue
                if clave == "md" and ruta.suffix.lower() != ".md":
                    continue
                nombres.setdefault(ruta.stem, {})[clave] = ruta

        for nombre, rutas in sorted(nombres.items()):
            slug = hacer_slug(nombre)
            # Con 33 ficheros no debería haber colisiones, pero si el corpus
            # crece, un sufijo evita que un documento tape a otro en silencio.
            base, n = slug, 2
            while slug in docs:
                slug = f"{base}-{n}"
                n += 1

            pdf, md = rutas.get("pdf"), rutas.get("md")
            docs[slug] = Documento(
                slug=slug,
                nombre=nombre,
                fuente=f"{nombre}.md",
                familia=clasificar(nombre),
                pdf=pdf,
                md=md,
                bytes_pdf=pdf.stat().st_size if pdf else 0,
                bytes_md=md.stat().st_size if md else 0,
            )

        self.documentos = docs
        self.refrescar_estadisticas()

    def refrescar_estadisticas(self) -> None:
        """Chunks, caracteres e índice de secciones, desde el snapshot de Chroma."""
        if not NUCLEO.snapshot["ids"]:
            return
        for doc in self.documentos.values():
            trozos = NUCLEO.documentos_de(doc.fuente)
            doc.n_chunks = len(trozos)
            doc.n_caracteres = sum(len(t) for _, t, _ in trozos)

            # Una entrada por sección (h2), en orden de documento, agrupando los
            # sub-chunks en que se partió una sección larga.
            secciones: list[dict] = []
            for cid, texto, meta in trozos:
                titulo = meta.get("h2") or meta.get("h1") or "(sin sección)"
                if secciones and secciones[-1]["titulo"] == titulo:
                    secciones[-1]["n_chunks"] += 1
                    secciones[-1]["n_caracteres"] += len(texto)
                    continue
                secciones.append({
                    "titulo": titulo,
                    "h1": meta.get("h1"),
                    "chunk_id": cid,
                    "n_chunks": 1,
                    "n_caracteres": len(texto),
                })
            doc.secciones = secciones

    # ── Consultas ─────────────────────────────────────────────────────────────
    def listar(self) -> list[dict]:
        return [d.resumen() for d in self.documentos.values()]

    def obtener(self, slug: str) -> Documento | None:
        return self.documentos.get(slug)

    def por_fuente(self, fuente: str) -> Documento | None:
        for doc in self.documentos.values():
            if doc.fuente == fuente:
                return doc
        return None

    def ficha(self, slug: str) -> dict | None:
        """Resumen + índice de secciones + lista de chunks con vista previa."""
        doc = self.obtener(slug)
        if doc is None:
            return None
        chunks = [
            {
                "chunk_id": cid,
                "indice": cid.rsplit("#", 1)[-1],
                "h1": meta.get("h1"),
                "h2": meta.get("h2"),
                "n_caracteres": len(texto),
                "vista_previa": recortar(cuerpo_sin_encabezados(texto), ANCHO_VISTA_PREVIA),
            }
            for cid, texto, meta in NUCLEO.documentos_de(doc.fuente)
        ]
        return {**doc.resumen(), "secciones": doc.secciones, "chunks": chunks}

    def totales(self) -> dict:
        docs = list(self.documentos.values())
        return {
            "n_documentos": len(docs),
            "n_pdf": sum(1 for d in docs if d.pdf),
            "n_md": sum(1 for d in docs if d.md),
            "n_indexados": sum(1 for d in docs if d.indexado),
            "bytes_pdf": sum(d.bytes_pdf for d in docs),
            "n_chunks": sum(d.n_chunks for d in docs),
            "n_caracteres": sum(d.n_caracteres for d in docs),
        }


def ruta_segura(ruta: Path) -> Path:
    """Comprueba que el fichero cuelga de `data/` antes de servirlo."""
    resuelta = ruta.resolve()
    if not resuelta.is_relative_to(DATA_DIR.resolve()):
        raise ValueError(f"Ruta fuera de data/: {resuelta}")
    if not resuelta.is_file():
        raise FileNotFoundError(resuelta)
    return resuelta


CATALOGO = Catalogo()
