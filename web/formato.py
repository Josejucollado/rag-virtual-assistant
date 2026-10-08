"""formato.py — Presentación compartida por las rutas: nombres legibles."""

from __future__ import annotations

import re


def nombre_corto(modelo: str | None) -> str | None:
    """'01 - GPT-OSS-120b - an open model released by…' -> 'GPT-OSS-120b'.

    Blablador nombra sus modelos «NN - Nombre - descripción» o «NN - Nombre,
    descripción», y en la barra lateral el generador ocupaba cuatro líneas. Se
    quitan también el proveedor delante («openai/…», «cross-encoder/…») y las
    notas entre paréntesis del `configuracion.txt` («(razonamiento=low)»). El
    identificador completo se sigue enviando aparte: es el que dice qué modelo
    respondió de verdad, porque los alias de Blablador se reapuntan.
    """
    if not modelo:
        return modelo
    partes = [p.strip() for p in modelo.split(" - ")]
    nombre = partes[1] if len(partes) >= 2 and partes[0].isdigit() else partes[0]
    nombre = nombre.split(",")[0]
    nombre = re.sub(r"\s*\(.*\)\s*$", "", nombre)
    nombre = nombre.rsplit("/", 1)[-1].strip()
    return nombre or modelo
