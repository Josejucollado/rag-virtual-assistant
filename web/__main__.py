"""
__main__.py — Arranque del servidor web.

    python -m web
    python -m web --puerto 8080
    python -m web --host 0.0.0.0        # expone a la red local, a conciencia

Por defecto escucha sólo en 127.0.0.1: la aplicación no tiene autenticación y
habla con la API de Blablador con la clave del `.env`, así que no debe quedar
abierta a la red sin querer. En un contenedor, donde hay que escuchar en
0.0.0.0, se dice con `WEB_HOST` (y el puerto con `WEB_PUERTO`).
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser

import uvicorn


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=os.environ.get("WEB_HOST", "127.0.0.1"))
    p.add_argument("--puerto", type=int, default=int(os.environ.get("WEB_PUERTO", "8000")))
    p.add_argument("--recargar", action="store_true",
                   help="Recarga al cambiar el código (desarrollo)")
    p.add_argument("--sin-navegador", action="store_true",
                   help="No abrir el navegador al arrancar")
    args = p.parse_args()

    url = f"http://{'localhost' if args.host == '127.0.0.1' else args.host}:{args.puerto}"
    print(f"\n  Sistema RAG — Sistemas Operativos\n  {url}\n")

    # Sin terminal (un contenedor, un servicio) no hay nadie delante de un
    # navegador que abrir.
    if not args.sin_navegador and not args.recargar and sys.stdout.isatty():
        webbrowser.open(url)

    # Un solo proceso a propósito: el núcleo del RAG (BM25 en memoria y el
    # cross-encoder) es un objeto del proceso, y cada worker de más lo cargaría
    # entero otra vez.
    uvicorn.run(
        "web.api:app",
        host=args.host,
        port=args.puerto,
        reload=args.recargar,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
