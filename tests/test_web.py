"""
Tests de la web: nombres legibles, familias de documentos y estáticos.

Sin API, sin Chroma y sin arrancar el núcleo: el cliente de FastAPI se usa sin
`with`, así que el ciclo de vida (que cargaría el índice y el cross-encoder) no
se ejecuta. Lo que protegen:

  · que un navegador nunca mezcle módulos viejos y nuevos tras actualizar la
    web (estáticos con huella en la ruta y sin caché);
  · que ningún módulo importe un fichero que ya no existe, que deja la pantalla
    de arranque colgada;
  · los nombres que enseña la interfaz.

    python -m pytest -q tests/test_web.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.catalogo import clasificar, hacer_slug, titulo_legible
from web.formato import nombre_corto


# ── Nombres legibles ──────────────────────────────────────────────────────────
class TestNombreCorto:
    def test_quita_el_numero_y_la_descripcion_de_blablador(self):
        assert nombre_corto("01 - GPT-OSS-120b - an open model released by OpenAI in August 2025") \
            == "GPT-OSS-120b"
        assert nombre_corto("02 - Qwen3.8-Flash-Next-NVFP4, general purpose large model") \
            == "Qwen3.8-Flash-Next-NVFP4"

    def test_quita_el_proveedor_y_las_notas_de_configuracion(self):
        assert nombre_corto("openai/gpt-5.1-2025-11-13 (razonamiento=low)") == "gpt-5.1-2025-11-13"
        assert nombre_corto("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1") == "mmarco-mMiniLMv2-L12-H384-v1"

    def test_un_nombre_ya_corto_no_cambia(self):
        assert nombre_corto("alias-qwen3-8b-embeddings") == "alias-qwen3-8b-embeddings"
        assert nombre_corto(None) is None


# ── Documentos ────────────────────────────────────────────────────────────────
class TestFamilias:
    @pytest.mark.parametrize("nombre, familia", [
        ("05 Memoria. Gestión de Memoria", "Teoría"),
        ("P09-shell-listas-bucles", "Prácticas"),
        ("practica2.md", "Prácticas"),
        ("sesion10-monitores-almacen", "Prácticas"),
        ("Problemas tema 1 SSOO", "Problemas"),
        ("Relación de ejercicios de programación en Bash", "Problemas"),
        ("Programación en shell Bash _ PLATEA", "Guiones"),
        ("S03 Aprendiendo Linux_ El Sistema de Ficheros _ PLATEA", "Guiones"),
    ])
    def test_cada_documento_cae_en_su_familia(self, nombre, familia):
        # Los tres de «Otros» (practica2, sesion10 y la relación de ejercicios)
        # eran material de prácticas y problemas mal clasificado.
        assert clasificar(nombre) == familia

    def test_el_titulo_quita_la_extension_que_lleva_el_propio_nombre(self):
        assert titulo_legible("practica2.md") == "practica2"
        assert titulo_legible("05 Memoria. Gestión de Memoria") == "05 Memoria. Gestión de Memoria"

    def test_el_slug_no_cambia(self):
        # Los enlaces ya compartidos a un documento dependen de él.
        assert hacer_slug("05 Memoria. Gestión de Memoria") == "05-memoria-gestion-de-memoria"
        assert hacer_slug("P11-shell-cadenas ") == "p11-shell-cadenas"


# ── Estáticos ─────────────────────────────────────────────────────────────────
# Al quitar la vista del inspector, un navegador con el app.js viejo en caché
# seguía pidiendo `vistas/inspector.js`, recibía un 404 y la pantalla de
# arranque se quedaba en «Contactando con el servidor…» sin decir nada.
ESTATICOS = Path(__file__).resolve().parent.parent / "web" / "static"


class TestEstaticos:
    def test_la_portada_apunta_a_los_estaticos_versionados_y_no_se_cachea(self):
        from web.api import PREFIJO_ESTATICOS, app
        r = TestClient(app).get("/")
        assert r.headers["cache-control"] == "no-cache"
        assert f'src="{PREFIJO_ESTATICOS}/js/app.js"' in r.text
        assert f'href="{PREFIJO_ESTATICOS}/css/estilos.css"' in r.text
        assert '"/static/js' not in r.text

    def test_los_modulos_se_revalidan_con_y_sin_version(self):
        from web.api import PREFIJO_ESTATICOS, app
        cliente = TestClient(app)
        for url in (f"{PREFIJO_ESTATICOS}/js/app.js", "/static/js/app.js"):
            r = cliente.get(url)
            assert r.status_code == 200 and r.headers["cache-control"] == "no-cache", url

    def test_la_huella_cambia_si_cambia_un_fichero(self, tmp_path):
        from web.api import huella_estaticos
        (tmp_path / "js").mkdir()
        (tmp_path / "js" / "a.js").write_text("uno", encoding="utf-8")
        antes = huella_estaticos(tmp_path)
        assert huella_estaticos(tmp_path) == antes
        (tmp_path / "js" / "a.js").write_text("dos", encoding="utf-8")
        assert huella_estaticos(tmp_path) != antes

    def test_ningun_modulo_importa_un_fichero_que_no_existe(self):
        # Un import a un fichero borrado tumba el grafo de módulos entero.
        modulos = list((ESTATICOS / "js").rglob("*.js"))
        assert modulos
        for js in modulos:
            for destino in re.findall(r"from\s+'(\.{1,2}/[^']+)'", js.read_text(encoding="utf-8")):
                assert (js.parent / destino).resolve().is_file(), f"{js.name} importa {destino}"

    def test_el_vigilante_del_arranque_sigue_en_su_sitio(self):
        # Si los módulos no arrancan, index.html lo dice a los 10 s en vez de
        # dejar la pantalla de carga colgada; app.js pone la marca que espera.
        assert "interfazArrancada" in (ESTATICOS / "index.html").read_text(encoding="utf-8")
        assert "window.interfazArrancada = true" in (ESTATICOS / "js" / "app.js").read_text(encoding="utf-8")
