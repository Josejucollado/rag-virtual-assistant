"""esquemas.py — Cuerpos de petición de la API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PeticionChat(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2000)
    # El historial vive en el cliente: el backend es sin estado. Cada turno es
    # (pregunta, respuesta), igual que la lista que maneja `cli/chat.py`.
    historial: list[tuple[str, str]] = Field(default_factory=list, max_length=20)
