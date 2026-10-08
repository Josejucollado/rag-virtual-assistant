/**
 * app.js — Arranque, estado compartido y router por hash.
 *
 * El núcleo del RAG tarda unos segundos en cargarse (índice BM25 con los 762
 * fragmentos + cross-encoder de torch), así que la web se abre con una pantalla
 * de arranque que consulta `/api/estado` hasta que el servidor dice `listo`.
 * Si el núcleo falla, se puede seguir sin el chat: Documentos y Sistema no lo
 * necesitan.
 */

import { pedir, el, vaciar } from './api.js';
import { vistaDocumentos } from './vistas/documentos.js';
import { vistaChat } from './vistas/chat.js';
import { vistaSistema } from './vistas/sistema.js';

export const ESTADO = { datos: null };

const RUTAS = {
  documentos: vistaDocumentos,
  chat: vistaChat,
  sistema: vistaSistema,
};

const TITULOS = {
  documentos: 'Documentos',
  chat: 'Chat',
  sistema: 'Sistema',
};

const vista = document.getElementById('vista');
const nav = document.getElementById('nav');
const arranque = document.getElementById('arranque');
const app = document.getElementById('app');

let limpiarVistaActual = null;

/* ── Router ──────────────────────────────────────────────────────────────── */
// Una ruta que ya no existe (un marcador antiguo a #/evaluacion o #/inspector)
// cae en Documentos en vez de dejar la página en blanco.
function rutaActual() {
  const bruta = (location.hash || '#/documentos').replace(/^#\/?/, '').split('/')[0];
  return RUTAS[bruta] ? bruta : 'documentos';
}

async function pintarRuta() {
  const ruta = rutaActual();

  for (const enlace of nav.querySelectorAll('a')) {
    const activo = enlace.dataset.ruta === ruta;
    enlace.classList.toggle('activo', activo);
    if (activo) enlace.setAttribute('aria-current', 'page');
    else enlace.removeAttribute('aria-current');
  }

  // Cada vista puede devolver una función de limpieza (abortar un flujo SSE,
  // quitar un listener global...). Sin esto, salir del chat a media respuesta
  // dejaría el stream vivo escribiendo sobre nodos ya desechados.
  if (limpiarVistaActual) { limpiarVistaActual(); limpiarVistaActual = null; }

  vaciar(vista);
  window.scrollTo(0, 0);
  document.title = `${TITULOS[ruta]} · RAG Sistemas Operativos`;
  limpiarVistaActual = (await RUTAS[ruta](vista)) || null;
}

/* ── Estado del núcleo ───────────────────────────────────────────────────── */
function pintarEstadoLateral() {
  const d = ESTADO.datos;
  if (!d) return;

  const caja = document.getElementById('estado-nucleo');
  const punto = caja.querySelector('.punto');
  const texto = caja.querySelector('.estado-texto');
  punto.dataset.estado = d.estado;
  texto.textContent = { listo: 'sistema listo', arrancando: d.paso, error: 'error' }[d.estado] || d.estado;
  caja.title = d.error || d.paso;

  // Los nombres cortos: el identificador completo del generador ocupaba cuatro
  // líneas. Sigue en el `title` y en la página Sistema.
  const m = d.modelos;
  const config = document.getElementById('config-mini');
  vaciar(config);
  const filas = [
    ['generador', m.generador_corto || m.generador, m.generador],
    ['reranker', m.reranker_corto || 'desactivado', m.reranker || 'desactivado'],
    ['recuperación', `k=${d.recuperacion.retriever_k} → ${d.recuperacion.rerank_k}`],
    ['corpus', `${d.corpus.n_documentos} docs · ${d.corpus.n_chunks || '…'} frag.`],
  ];
  for (const [k, v, completo] of filas) {
    config.append(el('div', {}, [el('dt', { texto: k }), el('dd', { texto: v, title: completo || v })]));
  }

  // En la demo pública (DEMO_PUBLICA=1) el chat tiene un cupo por minuto: se
  // avisa antes de que alguien se lo encuentre a mitad de una pregunta.
  const demo = d.demo || {};
  const aviso = document.getElementById('aviso-demo');
  aviso.hidden = !demo.activa;
  if (demo.activa) {
    aviso.textContent = `Demo pública: hasta ${demo.preguntas_por_minuto_ip} preguntas `
      + `por minuto, de ${demo.max_caracteres} caracteres como mucho.`;
  }
}

async function refrescarEstado() {
  ESTADO.datos = await pedir('/api/estado');
  pintarEstadoLateral();
  return ESTADO.datos;
}

/** Espera a que el núcleo termine de cargar, actualizando la pantalla de arranque. */
async function esperarNucleo() {
  const paso = document.getElementById('arranque-paso');
  paso.textContent = 'Contactando con el servidor…';

  for (;;) {
    let d;
    try {
      d = await refrescarEstado();
    } catch (e) {
      paso.textContent = 'Sin respuesta del servidor. Reintentando…';
      await new Promise((r) => setTimeout(r, 1200));
      continue;
    }

    if (d.estado === 'listo') return;

    if (d.estado === 'error') {
      paso.textContent = 'El núcleo del RAG no ha podido arrancar.';
      document.querySelector('.barra-indeterminada').hidden = true;
      const ya = arranque.querySelector('.arranque-error');
      if (!ya) {
        arranque.querySelector('.arranque-caja').append(
          el('pre', { clase: 'arranque-error', texto: d.error || 'Error desconocido' }),
          el('button', {
            clase: 'boton', style: 'margin-top:14px',
            onclick: () => { arranque.hidden = true; app.hidden = false; pintarRuta(); },
          }, ['Continuar sin el chat']),
        );
      }
      return;
    }

    paso.textContent = `${d.paso}…`;
    await new Promise((r) => setTimeout(r, 700));
  }
}

/* ── Arranque ────────────────────────────────────────────────────────────── */
window.addEventListener('hashchange', pintarRuta);

(async () => {
  // La marca que espera el vigilante de index.html: los módulos han cargado.
  window.interfazArrancada = true;
  await esperarNucleo();

  if (ESTADO.datos && ESTADO.datos.estado === 'listo') {
    arranque.hidden = true;
    app.hidden = false;
    await pintarRuta();
  }

  // El estado se refresca de fondo: si el núcleo cae, el punto del lateral lo
  // refleja sin recargar la página.
  setInterval(() => { refrescarEstado().catch(() => {}); }, 20000);
})();
