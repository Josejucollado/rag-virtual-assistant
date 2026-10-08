"""
nucleo.py — Puente entre la web y el RAG, con las piezas caras cargadas una vez.

Construir el recuperador cuesta varios segundos —mete los 762 chunks en BM25 y
carga un cross-encoder de torch—, así que se hace una sola vez, en un hilo de
fondo, y la web enseña mientras tanto una pantalla de arranque.

Todo lo que viene del RAG entra por el paquete `rag`, que es el mismo código que
ejecutan el chat de la terminal y la evaluación.
"""

from __future__ import annotations

import threading
import traceback
from typing import Any, Sequence

from rag import (
    USAR_RERANKER,
    build_generador,
    build_reescritor,
    build_retriever,
    build_vectordb,
    describir_fuente,
)

# Estados posibles del arranque.
ARRANCANDO = "arrancando"
LISTO = "listo"
ERROR = "error"


class Nucleo:
    """Las piezas del RAG, construidas una vez y compartidas por las peticiones."""

    def __init__(self) -> None:
        self.estado: str = ARRANCANDO
        self.error: str | None = None
        self.paso: str = "esperando"

        self.vectordb = None
        self.retriever = None
        self.generador = None
        self.reescritor = None

        # ids / documents / metadatas de la colección entera. Se cachea porque el
        # catálogo, la ficha de cada documento y las estadísticas lo piden
        # continuamente y es un `get()` de 762 filas.
        self.snapshot: dict[str, list] = {"ids": [], "documents": [], "metadatas": []}

        # El cross-encoder es CPU-bound: solapar inferencias de torch no acelera
        # nada y multiplica la memoria. Una recuperación cada vez.
        self.cerrojo = threading.Lock()
        self._hilo: threading.Thread | None = None

    # ── Arranque ──────────────────────────────────────────────────────────────
    def arrancar_en_segundo_plano(self) -> None:
        if self._hilo is not None:
            return
        self._hilo = threading.Thread(target=self._construir, name="nucleo-rag", daemon=True)
        self._hilo.start()

    def _construir(self) -> None:
        try:
            self.paso = "abriendo la colección de Chroma"
            self.vectordb = build_vectordb()

            self.paso = "leyendo los fragmentos indexados"
            crudo = self.vectordb.get(include=["documents", "metadatas"])
            self.snapshot = {
                "ids": list(crudo.get("ids") or []),
                "documents": list(crudo.get("documents") or []),
                "metadatas": [m or {} for m in (crudo.get("metadatas") or [])],
            }

            self.paso = ("construyendo el índice BM25 y cargando el cross-encoder"
                         if USAR_RERANKER else "construyendo el índice BM25")
            # El mismo recuperador que el chat y la evaluación, sobre la colección
            # que ya está abierta para el snapshot del catálogo.
            self.retriever = build_retriever(vectordb=self.vectordb)

            self.paso = "preparando las cadenas de generación"
            self.generador = build_generador()
            self.reescritor = build_reescritor()

            self.paso = LISTO
            self.estado = LISTO
        except Exception as exc:                      # noqa: BLE001
            # Cualquier fallo del arranque tiene que quedar registrado en el
            # estado, no sólo en la consola: es lo único que la interfaz puede
            # enseñar cuando la pantalla de carga no avanza. Por eso los errores
            # de configuración del paquete `rag` son `ErrorConfiguracion`
            # (una `Exception`) y no `SystemExit`, que este `except` no vería.
            self.estado = ERROR
            self.error = f"{exc.__class__.__name__}: {exc}"
            self.paso = ERROR
            traceback.print_exc()

    # ── Acceso ────────────────────────────────────────────────────────────────
    def exigir_listo(self) -> None:
        if self.estado == ERROR:
            raise RuntimeError(f"El núcleo del RAG no arrancó — {self.error}")
        if self.estado != LISTO:
            raise RuntimeError("El núcleo del RAG todavía se está cargando.")

    def recuperar(self, consulta: str) -> list[Any]:
        """Una recuperación completa, serializada por el cerrojo."""
        self.exigir_listo()
        with self.cerrojo:
            return self.retriever.invoke(consulta)

    def documentos_de(self, fuente: str) -> list[tuple[str, str, dict]]:
        """(chunk_id, texto, metadatos) de un documento, en el orden del original.

        El `chunk_id` lleva el índice con ceros ("...md#0007"), así que ordenar
        como cadena ya deja los chunks en su orden — el truco de `cli/inspeccionar.py`.
        """
        s = self.snapshot
        encontrados = [
            (cid, texto, meta)
            for cid, texto, meta in zip(s["ids"], s["documents"], s["metadatas"])
            if meta.get("source") == fuente
        ]
        encontrados.sort(key=lambda e: e[0])
        return encontrados

    def chunk(self, chunk_id: str) -> tuple[str, dict] | None:
        s = self.snapshot
        for cid, texto, meta in zip(s["ids"], s["documents"], s["metadatas"]):
            if cid == chunk_id:
                return texto, meta
        return None

    def describir(self, docs: Sequence[Any]) -> list[dict]:
        """Los fragmentos recuperados, en la forma que espera el frontend."""
        salida = []
        for i, d in enumerate(docs, start=1):
            meta = d.metadata or {}
            salida.append({
                "n": i,
                "chunk_id": meta.get("chunk_id", ""),
                "source": meta.get("source", "desconocido"),
                "h1": meta.get("h1"),
                "h2": meta.get("h2"),
                "descripcion": describir_fuente(d),
                "texto": d.page_content,
                "n_chars": len(d.page_content),
            })
        return salida


NUCLEO = Nucleo()
