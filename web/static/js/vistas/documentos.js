/**
 * documentos.js — Biblioteca del corpus: ver, previsualizar y descargar.
 *
 * La previsualización usa el visor de PDF nativo del navegador en un <iframe>:
 * cero librerías, cero CDN. Al lado se enseña lo que de verdad se indexó de ese
 * PDF —secciones y fragmentos—, que es lo que el RAG llega a leer.
 */

import { pedir, el, vaciar, icono, ICONOS, nBytes, nMiles, bloqueClicable } from '../api.js';

const ORDEN_FAMILIAS = ['Teoría', 'Prácticas', 'Guiones', 'Problemas', 'Otros'];

// El visor se cuelga de <body>, fuera de la vista: si se cambia de sección con
// él abierto (el botón «atrás» del navegador), hay que cerrarlo a mano.
let cerrarVisorAbierto = null;

export async function vistaDocumentos(raiz) {
  raiz.append(cabecera());

  const contenedor = el('div');
  raiz.append(el('div', { clase: 'cargando' }, [el('span', { clase: 'girador' }), 'Leyendo el corpus…']));

  let datos;
  try {
    datos = await pedir('/api/documentos');
  } catch (e) {
    vaciar(raiz).append(cabecera(), el('div', { clase: 'aviso aviso-error', texto: e.message }));
    return;
  }

  raiz.querySelector('.cargando').remove();
  raiz.append(contenedor);

  const estado = { texto: '', familia: null };
  const rejilla = el('div', { clase: 'rejilla-docs' });

  const familias = ORDEN_FAMILIAS.filter((f) => datos.documentos.some((d) => d.familia === f));

  const buscador = el('input', {
    type: 'search',
    placeholder: 'Buscar por nombre de documento…',
    'aria-label': 'Buscar documento',
    oninput: (ev) => { estado.texto = sinTildes(ev.target.value.trim()); pintar(); },
  });

  const chips = el('div', { clase: 'chips' }, [
    chip('Todos', null, estado, pintar),
    ...familias.map((f) => chip(f, f, estado, pintar)),
  ]);

  contenedor.append(
    resumenCorpus(datos.totales),
    el('div', { clase: 'barra-filtros' }, [
      el('div', { clase: 'buscador' }, [icono(ICONOS.buscar, 15), buscador]),
      chips,
    ]),
    rejilla,
  );

  function pintar() {
    for (const c of chips.querySelectorAll('.chip')) {
      c.setAttribute('aria-pressed', String((c.dataset.familia || '') === (estado.familia || '')));
    }

    const visibles = datos.documentos.filter((d) => {
      if (estado.familia && d.familia !== estado.familia) return false;
      if (estado.texto && !sinTildes(d.titulo || d.nombre).includes(estado.texto)) return false;
      return true;
    });

    vaciar(rejilla);
    if (!visibles.length) {
      rejilla.append(el('p', { clase: 'vacio', texto: 'Ningún documento coincide con la búsqueda.' }));
      return;
    }
    for (const d of visibles) rejilla.append(tarjetaDoc(d));
  }

  pintar();
  return () => { if (cerrarVisorAbierto) cerrarVisorAbierto(); };
}

/* ── Piezas ──────────────────────────────────────────────────────────────── */
function sinTildes(texto) {
  return String(texto).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

function cabecera() {
  return el('header', { clase: 'cabecera' }, [
    el('div', { clase: 'migas', html: 'corpus / <b>documentos</b>' }),
    el('h1', { texto: 'Documentos de la asignatura' }),
    el('p', {
      texto: 'Todo el material que el sistema tiene indexado. Cada ficha enseña qué se '
           + 'extrajo del PDF y en cuántos fragmentos se troceó para la búsqueda.',
    }),
  ]);
}

function resumenCorpus(t) {
  const tarjeta = (valor, etiqueta, nota, tono = '') =>
    el('div', { clase: `tarjeta ${tono}` }, [
      el('div', { clase: 'tarjeta-valor', texto: valor }),
      el('div', { clase: 'tarjeta-etiqueta', texto: etiqueta }),
      el('div', { clase: 'tarjeta-nota', texto: nota }),
    ]);

  return el('div', { clase: 'tarjetas', style: 'margin-bottom:20px' }, [
    tarjeta(t.n_documentos, 'Documentos', `${t.n_pdf} PDF · ${t.n_md} Markdown`, 'tono-acento'),
    tarjeta(nMiles(t.n_chunks), 'Fragmentos indexados', 'en la colección de Chroma'),
    tarjeta(nBytes(t.bytes_pdf), 'Tamaño del corpus', 'PDF originales'),
    tarjeta(nMiles(t.n_caracteres), 'Caracteres indexados', 'texto que ve el recuperador'),
  ]);
}

function chip(etiqueta, familia, estado, pintar) {
  return el('button', {
    clase: 'chip', type: 'button', 'aria-pressed': 'false',
    dataset: { familia: familia || '' },
    onclick: () => { estado.familia = familia; pintar(); },
  }, [etiqueta]);
}

function tarjetaDoc(d) {
  const acciones = el('div', { clase: 'doc-acciones' }, [
    el('button', {
      clase: 'boton boton-acento', type: 'button',
      onclick: () => abrirVisor(d),
    }, [icono(ICONOS.ojo), 'Previsualizar']),
    d.tiene_pdf && el('a', {
      clase: 'boton', href: `/api/documentos/${d.slug}/pdf?descargar=1`,
      title: `Descargar ${d.nombre}.pdf`,
    }, [icono(ICONOS.descarga), 'PDF']),
    d.tiene_md && el('a', {
      clase: 'boton', href: `/api/documentos/${d.slug}/md?descargar=1`,
      title: 'Descargar el Markdown que se indexó',
    }, [icono(ICONOS.descarga), 'MD']),
  ]);

  return el('article', { clase: 'tarjeta-doc' }, [
    el('div', { clase: 'doc-cabecera' }, [
      el('div', { clase: 'doc-icono' }, [el('span', { texto: 'PDF' })]),
      el('div', {}, [
        el('div', { clase: 'doc-nombre', texto: d.titulo || d.nombre, title: d.nombre }),
        el('div', { clase: 'doc-familia', texto: `${d.familia} · ${nBytes(d.bytes_pdf)}` }),
      ]),
    ]),
    el('div', { clase: 'doc-cifras' }, [
      el('span', { clase: 'doc-cifra', texto: `${d.n_chunks} fragmentos` }),
      el('span', { clase: 'doc-cifra', texto: `${d.n_secciones} secciones` }),
      el('span', { clase: 'doc-cifra', texto: `${nMiles(d.n_caracteres)} car.` }),
      !d.indexado && el('span', { clase: 'etiqueta etiqueta-aviso', texto: 'sin indexar' }),
    ]),
    acciones,
  ]);
}

/* ── Visor a pantalla partida ────────────────────────────────────────────── */
async function abrirVisor(resumen) {
  const lateral = el('div', { clase: 'visor-lateral' });
  const visor = el('div', {
    clase: 'visor', role: 'dialog', 'aria-modal': 'true',
    'aria-label': `Documento ${resumen.titulo || resumen.nombre}`,
  }, [
    el('iframe', {
      clase: 'visor-pdf', src: `/api/documentos/${resumen.slug}/pdf#view=FitH`,
      title: `Vista previa de ${resumen.titulo || resumen.nombre}`,
    }),
    lateral,
  ]);

  // El foco vuelve al botón que abrió el visor: con teclado, cerrar no debe
  // devolver al usuario al principio de la página.
  const origen = document.activeElement;
  const cerrar = () => {
    visor.remove();
    document.removeEventListener('keydown', alPulsar);
    if (cerrarVisorAbierto === cerrar) cerrarVisorAbierto = null;
    if (origen && origen.isConnected) origen.focus();
  };
  const alPulsar = (ev) => { if (ev.key === 'Escape') cerrar(); };
  document.addEventListener('keydown', alPulsar);
  visor.addEventListener('mousedown', (ev) => { if (ev.target === visor) cerrar(); });
  if (cerrarVisorAbierto) cerrarVisorAbierto();
  cerrarVisorAbierto = cerrar;

  const cuerpo = el('div', { clase: 'visor-cuerpo' }, [
    el('div', { clase: 'cargando' }, [el('span', { clase: 'girador' }), 'Cargando la ficha…']),
  ]);

  lateral.append(
    el('div', { clase: 'visor-cabecera' }, [
      el('div', {}, [
        el('div', { clase: 'migas', texto: resumen.familia }),
        el('h2', { style: 'font-size:0.98rem;line-height:1.35', texto: resumen.titulo || resumen.nombre }),
      ]),
      el('button', { clase: 'cerrar', type: 'button', 'aria-label': 'Cerrar', onclick: cerrar },
        [icono(ICONOS.cerrar)]),
    ]),
    cuerpo,
  );

  document.body.append(visor);
  lateral.querySelector('.cerrar').focus();

  let ficha;
  try {
    ficha = await pedir(`/api/documentos/${resumen.slug}`);
  } catch (e) {
    vaciar(cuerpo).append(el('div', { clase: 'aviso aviso-error', texto: e.message }));
    return;
  }

  vaciar(cuerpo).append(
    el('div', { clase: 'doc-acciones', style: 'margin-bottom:18px' }, [
      ficha.tiene_pdf && el('a', {
        clase: 'boton boton-acento', href: `/api/documentos/${ficha.slug}/pdf?descargar=1`,
      }, [icono(ICONOS.descarga), 'Descargar PDF']),
      ficha.tiene_md && el('a', {
        clase: 'boton', href: `/api/documentos/${ficha.slug}/md?descargar=1`,
      }, [icono(ICONOS.descarga), 'Descargar Markdown']),
      el('a', {
        clase: 'boton', href: `/api/documentos/${ficha.slug}/pdf`, target: '_blank',
        rel: 'noopener',
      }, [icono(ICONOS.externo), 'Abrir aparte']),
    ]),

    el('dl', { clase: 'tabla-config', style: 'margin:0 0 20px' }, [
      fila('Fichero indexado', ficha.fuente),
      fila('Fragmentos', String(ficha.n_chunks)),
      fila('Secciones', String(ficha.secciones.length)),
      fila('Caracteres', nMiles(ficha.n_caracteres)),
      fila('Tamaño PDF', nBytes(ficha.bytes_pdf)),
      fila('Tamaño Markdown', nBytes(ficha.bytes_md)),
    ]),

    ficha.secciones.length ? el('section', { style: 'margin-bottom:20px' }, [
      el('div', { clase: 'panel-titulo', texto: 'Índice de secciones' }),
      el('ol', { clase: 'lista-secciones' }, ficha.secciones.map((s, i) =>
        el('li', {}, [
          el('span', { clase: 'sec-n', texto: String(i + 1).padStart(2, '0') }),
          el('span', { clase: 'sec-titulo', texto: s.titulo }),
          el('span', {
            clase: 'sec-car',
            texto: s.n_chunks > 1 ? `${s.n_chunks} frag.` : `${nMiles(s.n_caracteres)} car.`,
          }),
        ]))),
    ]) : null,

    ficha.chunks.length ? el('section', {}, [
      el('div', { clase: 'panel-titulo', texto: `Fragmentos indexados (${ficha.chunks.length})` }),
      el('div', { clase: 'lista-chunks' }, ficha.chunks.map(filaChunk)),
    ]) : el('p', { clase: 'aviso' }, [
      'Este documento no tiene fragmentos en el índice. Ejecuta: ',
      el('code', { texto: 'python -m cli.process_md' }),
    ]),
  );
}

function fila(clave, valor) {
  return el('div', { style: 'display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05)' }, [
    el('span', { style: 'color:var(--muted);font-size:0.8rem', texto: clave }),
    el('span', { clase: 'dato', style: 'text-align:right;overflow-wrap:anywhere', texto: valor }),
  ]);
}

function filaChunk(c) {
  const detalle = el('div', { hidden: true, style: 'margin-top:9px' });

  // El texto completo se pide sólo al desplegar: la ficha de un documento largo
  // trae 50 fragmentos y cargarlos todos de golpe no compensa.
  return bloqueClicable({ clase: 'chunk-fila' }, [
    el('div', { clase: 'chunk-meta' }, [
      el('span', { clase: 'chunk-id', texto: `#${c.indice}` }),
      c.h2 && el('span', { clase: 'chunk-h2', texto: c.h2 }),
      el('span', { clase: 'doc-cifra', texto: `${nMiles(c.n_caracteres)} car.` }),
    ]),
    el('div', { clase: 'chunk-previa', texto: c.vista_previa }),
    detalle,
  ], async () => {
    if (!detalle.hidden) { detalle.hidden = true; return; }
    detalle.hidden = false;
    if (detalle.dataset.cargado) return;
    detalle.append(el('div', { clase: 'cargando', style: 'padding:10px' }, [
      el('span', { clase: 'girador' }), 'Cargando fragmento…',
    ]));
    try {
      const d = await pedir(`/api/chunks/${encodeURIComponent(c.chunk_id)}`);
      vaciar(detalle).append(el('pre', { clase: 'texto-chunk', texto: d.texto }));
      detalle.dataset.cargado = '1';
    } catch (e) {
      vaciar(detalle).append(el('div', { clase: 'aviso aviso-error', texto: e.message }));
    }
  });
}
