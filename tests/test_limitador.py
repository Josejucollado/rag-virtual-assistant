"""
Tests del cupo de la demo pública (`web/limitador.py`), con un reloj falso.

Protegen la clave de Blablador: un exceso de peticiones la bloquea minutos, y
con ella la demo entera y las evaluaciones de su dueño.

    python -m pytest -q tests/test_limitador.py
"""

from __future__ import annotations

from web.limitador import LimitesDemo, VentanaDeslizante


class Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_la_ventana_admite_hasta_el_limite():
    reloj = Reloj()
    ventana = VentanaDeslizante(2, reloj=reloj)
    for _ in range(2):
        assert ventana.cabe("a")
        ventana.anotar("a")
    assert not ventana.cabe("a")


def test_la_ventana_se_vacia_al_pasar_el_minuto():
    reloj = Reloj()
    ventana = VentanaDeslizante(1, reloj=reloj)
    ventana.anotar("a")
    reloj.t = 59.9
    assert not ventana.cabe("a")
    reloj.t = 60.0
    assert ventana.cabe("a")


def test_cada_visitante_tiene_su_cupo():
    limites = LimitesDemo(por_minuto=10, por_minuto_ip=2, reloj=Reloj())
    assert limites.admitir("1.1.1.1") is None
    assert limites.admitir("1.1.1.1") is None
    assert "2 preguntas" in limites.admitir("1.1.1.1")
    assert limites.admitir("2.2.2.2") is None


def test_el_cupo_global_protege_la_clave():
    limites = LimitesDemo(por_minuto=2, por_minuto_ip=5, reloj=Reloj())
    assert limites.admitir("1.1.1.1") is None
    assert limites.admitir("2.2.2.2") is None
    assert "muchas preguntas" in limites.admitir("3.3.3.3")


def test_un_rechazo_no_gasta_cupo():
    """Si se anotara también lo rechazado, un visitante insistente se bloquearía para siempre."""
    reloj = Reloj()
    limites = LimitesDemo(por_minuto=10, por_minuto_ip=1, reloj=reloj)
    assert limites.admitir("1.1.1.1") is None
    for _ in range(5):
        assert limites.admitir("1.1.1.1") is not None
    reloj.t = 60.0
    assert limites.admitir("1.1.1.1") is None
