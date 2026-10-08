"""
limitador.py — Cuántas preguntas admite la demo pública por minuto.

Sólo actúa con `DEMO_PUBLICA=1` (ver el porqué de los números en
`rag/config.py`). Vive en memoria, y basta: el servidor es un solo proceso
(`web/__main__.py`), así que no hay otros procesos con los que repartir la
cuenta.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

VENTANA_S = 60.0


class VentanaDeslizante:
    """Como mucho `limite` sucesos por clave en los últimos `ventana_s` segundos."""

    def __init__(self, limite: int, ventana_s: float = VENTANA_S,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self.limite = limite
        self.ventana_s = ventana_s
        self.reloj = reloj
        self._sucesos: dict[str, deque[float]] = defaultdict(deque)

    def _vigentes(self, clave: str, ahora: float) -> deque[float]:
        sucesos = self._sucesos[clave]
        while sucesos and ahora - sucesos[0] >= self.ventana_s:
            sucesos.popleft()
        return sucesos

    def cabe(self, clave: str) -> bool:
        return len(self._vigentes(clave, self.reloj())) < self.limite

    def anotar(self, clave: str) -> None:
        self._sucesos[clave].append(self.reloj())


class LimitesDemo:
    """El cupo global (protege la clave) y el de cada visitante (reparte el global)."""

    def __init__(self, por_minuto: int, por_minuto_ip: int,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self.global_ = VentanaDeslizante(por_minuto, reloj=reloj)
        self.por_ip = VentanaDeslizante(por_minuto_ip, reloj=reloj)
        self._cerrojo = threading.Lock()

    def admitir(self, ip: str) -> str | None:
        """Anota la pregunta si cabe; si no, devuelve el motivo para enseñarlo."""
        with self._cerrojo:
            if not self.por_ip.cabe(ip):
                return (f"Has llegado al máximo de esta demo ({self.por_ip.limite} "
                        f"preguntas por minuto). Prueba de nuevo en unos segundos.")
            if not self.global_.cabe("*"):
                return ("La demo está recibiendo muchas preguntas a la vez. "
                        "Prueba de nuevo en un minuto.")
            self.por_ip.anotar(ip)
            self.global_.anotar("*")
            return None
