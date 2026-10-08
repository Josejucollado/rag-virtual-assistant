"""
api.py — Las rutas de la web del RAG.

El chat va por SSE porque la generación llega en trozos: se emiten primero las
fuentes (que ya se conocen, la recuperación es anterior a la generación), después
los tokens, y al final las citas que la respuesta usó de verdad. Es el mismo
orden que sigue `cli/chat.py` en la terminal.
"""

from __future__ import annotations

import hashlib
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from rag import (
    BM25_STEMMING,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION,
    DEMO_MAX_CARACTERES_PREGUNTA,
    DEMO_PREGUNTAS_POR_MINUTO,
    DEMO_PREGUNTAS_POR_MINUTO_IP,
    DEMO_PUBLICA,
    DISTANCIA,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    ESTILO_RESPUESTA,
    MIN_CHUNK,
    MODEL_JUDGE,
    MODEL_RAG,
    PESOS_HIBRIDO,
    PROVEEDOR_RAG,
    REFUSAL_TEXT,
    RERANK_K,
    RERANKER_MODEL,
    RETRIEVER_K,
    TEMPERATURA,
    USAR_RERANKER,
    consulta_de_busqueda,
    entrada_generador,
    es_rechazo,
    extraer_citas,
)

from .catalogo import CATALOGO, ruta_segura
from .esquemas import PeticionChat
from .formato import nombre_corto
from .limitador import LimitesDemo
from .nucleo import NUCLEO

ESTATICOS = Path(__file__).resolve().parent / "static"

LIMITES_DEMO = LimitesDemo(DEMO_PREGUNTAS_POR_MINUTO, DEMO_PREGUNTAS_POR_MINUTO_IP)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # El catálogo se puede construir ya: sólo mira el disco. Las estadísticas de
    # indexado se rellenan cuando el núcleo termina de leer Chroma.
    CATALOGO.construir()
    NUCLEO.arrancar_en_segundo_plano()
    yield


app = FastAPI(
    title="RAG · Sistemas Operativos",
    description="Interfaz web del sistema RAG sobre la documentación de la asignatura.",
    lifespan=ciclo_de_vida,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


# ── Estado ────────────────────────────────────────────────────────────────────
@app.get("/api/estado")
async def estado() -> dict:
    """Configuración viva del sistema. Nunca incluye credenciales."""
    if NUCLEO.estado == "listo" and not any(d.n_chunks for d in CATALOGO.documentos.values()):
        CATALOGO.refrescar_estadisticas()

    return {
        "estado": NUCLEO.estado,
        "paso": NUCLEO.paso,
        "error": NUCLEO.error,
        "modelos": {
            "generador": MODEL_RAG,
            "generador_corto": nombre_corto(MODEL_RAG),
            "generador_proveedor": PROVEEDOR_RAG,
            "reescritor": MODEL_JUDGE,
            "reescritor_corto": nombre_corto(MODEL_JUDGE),
            "embeddings": EMBEDDING_MODEL,
            "embeddings_proveedor": EMBEDDING_PROVIDER,
            "reranker": RERANKER_MODEL if USAR_RERANKER else None,
            "reranker_corto": nombre_corto(RERANKER_MODEL) if USAR_RERANKER else None,
        },
        "recuperacion": {
            "retriever_k": RETRIEVER_K,
            "rerank_k": RERANK_K,
            "usar_reranker": USAR_RERANKER,
            "pesos_hibrido": PESOS_HIBRIDO,
            "bm25_stemming": BM25_STEMMING,
        },
        "indice": {
            "coleccion": COLLECTION,
            "dimensiones": EMBEDDING_DIMS,
            "distancia": DISTANCIA,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "min_chunk": MIN_CHUNK,
        },
        "generacion": {
            "temperatura": TEMPERATURA,
            "estilo": ESTILO_RESPUESTA,
            "texto_rechazo": REFUSAL_TEXT,
        },
        "corpus": CATALOGO.totales(),
        "demo": {
            "activa": DEMO_PUBLICA,
            "preguntas_por_minuto_ip": DEMO_PREGUNTAS_POR_MINUTO_IP,
            "max_caracteres": DEMO_MAX_CARACTERES_PREGUNTA,
        },
    }


# ── Documentos ────────────────────────────────────────────────────────────────
@app.get("/api/documentos")
async def listar_documentos() -> dict:
    if NUCLEO.estado == "listo":
        CATALOGO.refrescar_estadisticas()
    return {"documentos": CATALOGO.listar(), "totales": CATALOGO.totales()}


@app.get("/api/documentos/{slug}")
async def ficha_documento(slug: str) -> dict:
    ficha = CATALOGO.ficha(slug)
    if ficha is None:
        raise HTTPException(404, f"No existe el documento «{slug}».")
    return ficha


def _servir(ruta: Path | None, nombre: str, tipo: str, descargar: bool) -> FileResponse:
    if ruta is None:
        raise HTTPException(404, "Ese formato no está disponible para este documento.")
    try:
        segura = ruta_segura(ruta)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Fichero no encontrado.") from None

    disposicion = "attachment" if descargar else "inline"
    # El nombre lleva tildes y espacios: filename* (RFC 5987) es el único que los
    # transporta bien en todos los navegadores.
    cabecera = f"{disposicion}; filename*=UTF-8''{quote(nombre)}"
    return FileResponse(segura, media_type=tipo, headers={"Content-Disposition": cabecera})


@app.get("/api/documentos/{slug}/pdf")
async def pdf_documento(slug: str, descargar: bool = Query(False)) -> FileResponse:
    doc = CATALOGO.obtener(slug)
    if doc is None:
        raise HTTPException(404, f"No existe el documento «{slug}».")
    return _servir(doc.pdf, f"{doc.nombre}.pdf", "application/pdf", descargar)


@app.get("/api/documentos/{slug}/md")
async def md_documento(slug: str, descargar: bool = Query(False)) -> FileResponse:
    doc = CATALOGO.obtener(slug)
    if doc is None:
        raise HTTPException(404, f"No existe el documento «{slug}».")
    return _servir(doc.md, f"{doc.nombre}.md", "text/markdown; charset=utf-8", descargar)


@app.get("/api/chunks/{chunk_id:path}")
async def ver_chunk(chunk_id: str) -> dict:
    if NUCLEO.estado != "listo":
        raise HTTPException(503, "El índice todavía se está cargando.")
    encontrado = NUCLEO.chunk(chunk_id)
    if encontrado is None:
        raise HTTPException(404, f"No existe el fragmento «{chunk_id}».")
    texto, meta = encontrado
    doc = CATALOGO.por_fuente(meta.get("source", ""))
    return {
        "chunk_id": chunk_id,
        "texto": texto,
        "n_caracteres": len(texto),
        "metadatos": meta,
        "slug": doc.slug if doc else None,
    }


# ── Chat ──────────────────────────────────────────────────────────────────────
def _sse(evento: str, datos: dict) -> str:
    return f"event: {evento}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


def _flujo_chat(peticion: PeticionChat):
    """Reproduce paso por paso lo que hace `cli/chat.py` por cada pregunta."""
    t0 = time.perf_counter()
    pregunta = peticion.pregunta.strip()

    try:
        NUCLEO.exigir_listo()
    except RuntimeError as exc:
        yield _sse("error", {"mensaje": str(exc)})
        return

    try:
        # 1. Se busca con la pregunta autónoma (reescrita si es de seguimiento).
        consulta = consulta_de_busqueda(NUCLEO.reescritor, peticion.historial, pregunta)
        if consulta != pregunta:
            yield _sse("consulta", {"consulta": consulta})

        # 2. Una sola recuperación: los fragmentos que se citan son exactamente
        #    los que ha visto el modelo.
        docs = NUCLEO.recuperar(consulta)
        fuentes = NUCLEO.describir(docs)
        for f in fuentes:
            doc = CATALOGO.por_fuente(f["source"])
            f["slug"] = doc.slug if doc else None
        yield _sse("fuentes", {"docs": fuentes})

        # 3. Generación en streaming, con la pregunta ORIGINAL.
        respuesta = ""
        for trozo in NUCLEO.generador.stream(entrada_generador(docs, pregunta)):
            respuesta += trozo
            yield _sse("token", {"t": trozo})

        # 4. Fuentes sólo si ha respondido de verdad.
        rechazo = es_rechazo(respuesta)
        yield _sse("fin", {
            "rechazo": rechazo,
            "citas": [] if rechazo else extraer_citas(respuesta, len(docs)),
            "latencia_s": round(time.perf_counter() - t0, 2),
            "n_docs": len(docs),
        })
    except Exception as exc:                          # noqa: BLE001
        yield _sse("error", {"mensaje": f"{exc.__class__.__name__}: {exc}"})


def _ip_cliente(peticion: Request) -> str:
    """La IP del visitante. Detrás del proxy de un hosting llega en X-Forwarded-For.

    Se puede falsear, pero sólo sirve para repartir el cupo: lo que protege la
    clave es el límite global, que no depende de ella.
    """
    reenviada = peticion.headers.get("x-forwarded-for", "")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return peticion.client.host if peticion.client else "?"


def _motivo_rechazo_demo(peticion: PeticionChat, ip: str) -> str | None:
    """Por qué la demo pública no atiende esta pregunta, o None si la atiende."""
    if len(peticion.pregunta) > DEMO_MAX_CARACTERES_PREGUNTA:
        return (f"En esta demo las preguntas tienen un máximo de "
                f"{DEMO_MAX_CARACTERES_PREGUNTA} caracteres.")
    return LIMITES_DEMO.admitir(ip)


def _solo_error(mensaje: str):
    yield _sse("error", {"mensaje": mensaje})


@app.post("/api/chat")
async def chat(peticion: PeticionChat, request: Request) -> StreamingResponse:
    flujo = _flujo_chat(peticion)
    if DEMO_PUBLICA:
        motivo = _motivo_rechazo_demo(peticion, _ip_cliente(request))
        if motivo:
            flujo = _solo_error(motivo)
    return StreamingResponse(
        flujo,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Estáticos ─────────────────────────────────────────────────────────────────
def huella_estaticos(directorio: Path = ESTATICOS) -> str:
    """Huella del contenido de static/: cambia en cuanto cambia cualquier fichero.

    Va dentro de la ruta de los estáticos para que una versión nueva sea una URL
    nueva. Sin ella, el navegador reutilizaba de su caché un app.js viejo
    (StaticFiles sólo manda Last-Modified y, sin Cache-Control, el navegador lo
    da por bueno un rato): al quitar la vista del inspector, ese app.js seguía
    pidiendo `vistas/inspector.js`, recibía un 404 y la pantalla de arranque se
    quedaba en «Contactando con el servidor…» sin decir por qué.
    """
    huella = hashlib.sha256()
    for ruta in sorted(directorio.rglob("*")):
        if ruta.is_file():
            huella.update(ruta.relative_to(directorio).as_posix().encode())
            huella.update(ruta.read_bytes())
    return huella.hexdigest()[:12]


PREFIJO_ESTATICOS = f"/static/{huella_estaticos()}"


class EstaticosSinCache(StaticFiles):
    """Estáticos que el navegador revalida siempre: un 304 cuesta casi nada.

    La huella se calcula al arrancar, así que si se edita un .js sin reiniciar
    el servidor la URL no cambia: esto evita que se siga usando la copia vieja.
    """

    async def get_response(self, path: str, scope) -> Response:
        respuesta = await super().get_response(path, scope)
        respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta


@app.get("/", include_in_schema=False)
async def raiz() -> HTMLResponse:
    html = (ESTATICOS / "index.html").read_text(encoding="utf-8")
    # El HTML apunta a la versión actual de los estáticos, y las importaciones
    # relativas de los módulos heredan el mismo prefijo.
    html = html.replace('"/static/', f'"{PREFIJO_ESTATICOS}/')
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


app.mount(PREFIJO_ESTATICOS, EstaticosSinCache(directory=ESTATICOS), name="static")
# También sin versión, para lo que ya tenga esas rutas apuntadas.
app.mount("/static", EstaticosSinCache(directory=ESTATICOS), name="static-sin-version")
