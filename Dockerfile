# syntax=docker/dockerfile:1
#
# Dos imágenes desde el mismo Dockerfile:
#
#   web           (por defecto) la web y las órdenes de consola. Lleva dentro el
#                 modelo del reranker y, si se da INDICE_URL, el índice
#                 vectorial: arranca en segundos y sin descargar nada.
#   herramientas  web + ingesta (Docling) + evaluación (RAGAS) + tests. Sólo se
#                 construye cuando se pide (perfil `herramientas` de compose).
#
#   docker build -t docente-virtual .
#   docker build --build-arg INDICE_URL=<url del .tar.gz> -t docente-virtual .
#   docker build --target herramientas -t docente-virtual:herramientas .

# ── Base: Python y las dependencias del núcleo ────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/modelos

WORKDIR /app

# Torch de CPU antes que nada: si no, sentence-transformers trae el de CUDA,
# varios GB que el reranker no usa sin GPU.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 1000 app && mkdir -p /modelos && chown app:app /modelos

# ── web: lo que necesita la demo ──────────────────────────────────────────────
FROM base AS web

# El cross-encoder del reranker se descarga al construir, no al arrancar: así
# el contenedor no depende de Hugging Face en marcha y arranca en segundos.
ARG RERANKER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
USER app
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('${RERANKER_MODEL}')"
USER root

COPY --chown=app:app rag/ rag/
COPY --chown=app:app cli/ cli/
COPY --chown=app:app web/ web/
COPY --chown=app:app data/documentacion_pdf/ data/documentacion_pdf/
COPY --chown=app:app data/documentacion_md/ data/documentacion_md/

# El índice no se versiona en git; se publica como fichero de una release
# (.github/workflows/indice.yml). Si no se da la URL, la imagen sale sin índice
# y se construye dentro con `python -m cli.process_md --reset`.
ARG INDICE_URL=""
RUN if [ -n "$INDICE_URL" ]; then \
      python -c "import sys, tarfile, urllib.request; \
tarfile.open(fileobj=urllib.request.urlopen(sys.argv[1]), mode='r|gz').extractall('/app', filter='data')" \
        "$INDICE_URL"; \
    fi && mkdir -p /app/chroma_db_blablador && chown -R app:app /app/chroma_db_blablador

USER app

ENV HF_HUB_OFFLINE=1 \
    WEB_HOST=0.0.0.0 \
    WEB_PUERTO=8000
EXPOSE 8000

# Sano = el núcleo del RAG ha terminado de cargar, no sólo que responde HTTP.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import json, sys, urllib.request; \
d = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/estado', timeout=4)); \
sys.exit(0 if d['estado'] == 'listo' else 1)"

CMD ["python", "-m", "web", "--sin-navegador"]

# ── herramientas: ingesta, evaluación y tests ─────────────────────────────────
FROM web AS herramientas

USER root
COPY requirements-ingesta.txt requirements-eval.txt requirements-dev.txt ./
RUN pip install -r requirements-ingesta.txt -r requirements-dev.txt

COPY --chown=app:app eval_ragas/ eval_ragas/
COPY --chown=app:app tests/ tests/
COPY --chown=app:app pyproject.toml ./
COPY --chown=app:app data/*.csv data/pdf_hashes.json data/

USER app
# Docling y otros rerankers sí descargan modelos.
ENV HF_HUB_OFFLINE=0

CMD ["python", "-m", "pytest", "-q"]
