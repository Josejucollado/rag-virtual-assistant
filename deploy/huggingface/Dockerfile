# La demo pública en Hugging Face Spaces parte de la imagen que publica
# .github/workflows/docker.yml. Cambia el nombre si el repositorio se renombra
# (siempre en minúsculas), y haz público el paquete en GHCR para que el Space
# pueda descargarlo.
FROM ghcr.io/josejucollado/rag-docente-virtual:latest

# Cupo por minuto en la web: protege la clave de Blablador (ver rag/config.py).
ENV DEMO_PUBLICA=1
