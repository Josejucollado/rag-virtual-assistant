/**
 * chat.js — Conversación con el RAG.
 *
 * Reproduce lo que hace `cli/chat.py` en la terminal: reescribe la pregunta si hay
 * historial, recupera UNA vez, genera en streaming y enseña sólo los fragmentos
 * que la respuesta ha citado de verdad. Si el modelo rechaza por falta de
 * información, el panel de fuentes se oculta: enseñar cinco citas bajo un
 * "no lo sé" invita a creerse una respuesta que no existe.
 *
 * Cada turno guarda SUS fuentes. Antes el panel sólo tenía las de la última
 * pregunta, y pulsar la cita [3] de una respuesta anterior abría el fragmento 3
 * de la última: otro documento, justo lo contrario de la trazabilidad que el
 * sistema promete.
 *
 * La conversación vive aquí (sessionStorage): el backend es sin estado.
 */

import { flujoChat, el, vaciar, icono, ICONOS } from '../api.js';
import { pintar as pintarMd } from '../markdown.js';

const CLAVE = 'rag-conversacion';
const CLAVE_ANTIGUA = 'rag-historial';   // formato anterior: [[pregunta, respuesta], …]
const MAX_TURNOS_GUARDADOS = 10;
// El reescritor usa los 2 últimos (MAX_TURNOS_HISTORIAL en rag/generacion.py);
// se mandan unos pocos más de margen y el servidor recorta.
const TURNOS_AL_SERVIDOR = 4;

const SUGERENCIAS = [
  '¿Qué es la paginación de memoria y qué problema resuelve?',
  'Diferencias entre un proceso y un hilo',
  '¿Cómo funciona la planificación Round Robin?',
  '¿Para qué sirve el comando grep en el shell?',
];

export function vistaChat(raiz) {
  const turnos = leerTurnos();
  let abortar = null;

  /* ── Estructura ────────────────────────────────────────────────────────── */
  const hilo = el('div', { clase: 'chat-hilo', id: 'hilo', 'aria-live': 'polite' });
  const listaFuentes = el('div', { clase: 'fuentes-lista' });
  const notaFuentes = el('p', { clase: 'fuentes-nota' });

  const entrada = el('textarea', {
    rows: '1', placeholder: 'Pregunta sobre la documentación de Sistemas Operativos…',
    'aria-label': 'Tu pregunta',
  });
  const botonEnviar = el('button', {
    clase: 'enviar', type: 'submit', 'aria-label': 'Enviar pregunta', disabled: true,
  }, [icono(ICONOS.enviar, 16)]);

  const formulario = el('form', { clase: 'caja-consulta' }, [entrada, botonEnviar]);

  const botonLimpiar = el('button', {
    clase: 'boton', type: 'button',
    onclick: () => {
      if (abortar) { abortar(); abortar = null; }
      turnos.length = 0;
      guardarTurnos(turnos);
      pintarBienvenida();
      mostrarFuentes(null);
      actualizarBarra();
      botonEnviar.disabled = !entrada.value.trim();
    },
  }, [icono(ICONOS.papelera), 'Limpiar conversación']);

  const contadorTurnos = el('span', { clase: 'dato' });

  raiz.append(
    el('div', { clase: 'chat' }, [
      el('div', { clase: 'chat-col' }, [
        el('div', { clase: 'chat-barra' }, [
          el('div', {}, [
            el('div', { clase: 'migas', html: 'asistente / <b>chat</b>' }),
            contadorTurnos,
          ]),
          botonLimpiar,
        ]),
        hilo,
        el('div', { clase: 'chat-entrada' }, [
          formulario,
          el('p', {
            clase: 'pista',
            texto: 'Enter envía · Mayús+Enter salta de línea · las citas [n] abren el fragmento',
          }),
        ]),
      ]),
      el('aside', { clase: 'fuentes-panel', 'aria-label': 'Fuentes de la respuesta' }, [
        el('div', { clase: 'fuentes-cabecera' }, [
          el('div', { clase: 'panel-titulo', style: 'margin:0', texto: 'Fuentes' }),
          notaFuentes,
        ]),
        listaFuentes,
      ]),
    ]),
  );

  /* ── Pintado ───────────────────────────────────────────────────────────── */
  function historialParaServidor() {
    // Como `cli/chat.py`: un rechazo no entra en el historial del reescritor.
    return turnos.filter((t) => !t.rechazo)
      .slice(-TURNOS_AL_SERVIDOR)
      .map((t) => [t.pregunta, t.respuesta]);
  }

  function actualizarBarra() {
    const n = turnos.filter((t) => !t.rechazo).length;
    contadorTurnos.textContent = turnos.length
      ? `${n} turno${n === 1 ? '' : 's'} en memoria · se usan los 2 últimos para reescribir`
      : 'conversación nueva';
    botonLimpiar.disabled = !turnos.length;
  }

  function pintarBienvenida() {
    vaciar(hilo);
    hilo.append(el('div', { clase: 'bienvenida' }, [
      el('h2', { texto: 'Pregunta a la documentación' }),
      el('p', {
        texto: 'El asistente responde únicamente con lo que hay en los apuntes indexados y '
             + 'cita cada afirmación. Si algo no está en el material, lo dice en vez de '
             + 'inventárselo.',
      }),
      el('div', { clase: 'sugerencias' }, SUGERENCIAS.map((s) =>
        el('button', {
          clase: 'sugerencia', type: 'button',
          onclick: () => { entrada.value = s; entrada.dispatchEvent(new Event('input')); entrada.focus(); },
        }, [s]))),
    ]));
  }

  /**
   * Pinta en el panel las fuentes del turno i (null: ninguno) y resalta la n.
   * Un turno sin fuentes guardadas (rechazo, o conversación de una versión
   * anterior) lo dice en vez de enseñar las de otra pregunta.
   */
  function mostrarFuentes(i, destacar = null) {
    vaciar(listaFuentes);
    for (const t of hilo.querySelectorAll('.turno[data-turno]')) {
      t.classList.toggle('en-panel', i !== null && Number(t.dataset.turno) === i);
    }

    const turno = i === null ? null : turnos[i];
    if (!turno) {
      notaFuentes.textContent = 'Los fragmentos que el modelo lee para responder.';
      listaFuentes.append(el('p', {
        clase: 'vacio', style: 'padding:22px 10px',
        texto: 'Todavía no hay fragmentos que mostrar.',
      }));
      return;
    }

    notaFuentes.textContent = `Lo que el modelo leyó para: «${recortarTexto(turno.pregunta, 90)}»`;
    if (turno.rechazo || !turno.fuentes.length) {
      listaFuentes.append(el('p', {
        clase: 'vacio', style: 'padding:22px 10px',
        texto: turno.rechazo
          ? 'El modelo no encontró la respuesta en los fragmentos recuperados, así que no se enseñan.'
          : 'Las fuentes de esta pregunta no se guardaron.',
      }));
      return;
    }

    const citadas = new Set(turno.citas);
    for (const f of turno.fuentes) {
      const citada = !turno.citas.length || citadas.has(f.n);
      const det = el('details', {
        clase: `fuente${citada ? '' : ' no-citada'}`,
        id: `fuente-${f.n}`,
      }, [
        el('summary', {}, [
          el('span', { clase: 'fuente-n', texto: String(f.n) }),
          el('span', { clase: 'fuente-titulo' }, [
            el('div', { clase: 'fuente-doc', texto: f.source }),
            f.h2 && el('div', { clase: 'fuente-sec', texto: f.h2 }),
            !citada && el('div', { clase: 'fuente-sec', texto: 'leído, pero no citado' }),
          ]),
        ]),
        el('div', { clase: 'fuente-cuerpo' }, [
          el('pre', { clase: 'texto-chunk', texto: f.texto }),
          el('div', { clase: 'fuente-acciones' }, [
            f.slug && el('a', {
              clase: 'boton', href: `/api/documentos/${f.slug}/pdf`, target: '_blank', rel: 'noopener',
            }, [icono(ICONOS.ojo), 'Ver el PDF']),
            el('span', { clase: 'etiqueta', texto: f.chunk_id }),
          ]),
        ]),
      ]);
      if (destacar !== null && f.n === destacar) {
        det.open = true;
        det.classList.add('destacada');
      }
      listaFuentes.append(det);
    }
    const marcada = listaFuentes.querySelector('.destacada');
    if (marcada) marcada.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function turnoUsuario(texto) {
    return el('div', { clase: 'turno turno-usuario' }, [
      el('div', { clase: 'burbuja-usuario', texto }),
    ]);
  }

  /** El turno del asistente: cabecera, reescritura, cuerpo y pie. */
  function turnoAgente(i, estado) {
    const cuerpo = el('div', { clase: 'md respuesta' });
    const pie = el('div', { clase: 'pie-turno' });
    const reescritura = el('div', { hidden: true });
    const linea = el('span', { clase: 'dato', texto: estado });
    const nodo = el('div', { clase: 'turno', dataset: { turno: String(i) } }, [
      el('div', { clase: 'linea-agente' }, [el('span', { clase: 'avatar', texto: 'RAG' }), linea]),
      reescritura, cuerpo, pie,
    ]);
    return { nodo, cuerpo, pie, reescritura, linea };
  }

  /** El pie de un turno terminado: el aviso de rechazo o las citas. */
  function pintarPie(pie, i) {
    const t = turnos[i];
    vaciar(pie);
    if (t.migrado) {
      pie.append(el('span', { clase: 'etiqueta', texto: 'turno anterior: sus fuentes no se guardaron' }));
      return;
    }
    if (t.rechazo) {
      pie.append(el('span', { clase: 'etiqueta etiqueta-aviso', texto: 'sin información en el corpus' }));
      return;
    }
    if (!t.citas.length) {
      pie.append(el('span', {
        clase: 'etiqueta etiqueta-aviso',
        texto: 'la respuesta no cita ningún fragmento: trátala con cautela',
      }));
    } else {
      pie.append(el('span', {
        clase: 'etiqueta etiqueta-ok',
        texto: `${t.citas.length} de ${t.fuentes.length || t.n_docs || '?'} fragmentos citados`,
      }));
      for (const n of t.citas) {
        pie.append(el('button', {
          clase: 'cita', type: 'button', dataset: { cita: String(n) },
          title: `Ver el fragmento ${n}`,
        }, [String(n)]));
      }
    }
    if (t.fuentes.length) {
      pie.append(el('button', {
        clase: 'enlace-fuentes', type: 'button', dataset: { verFuentes: '1' },
      }, ['ver las fuentes']));
    }
  }

  /* ── Envío ─────────────────────────────────────────────────────────────── */
  function preguntar(pregunta) {
    if (!pregunta || abortar) return;

    if (!turnos.length) vaciar(hilo);
    hilo.append(turnoUsuario(pregunta));

    // El índice que tendrá el turno cuando termine. Si falla, no se guarda.
    const i = turnos.length;
    const vista = turnoAgente(i, 'recuperando fragmentos…');
    const cursor = el('span', { clase: 'cursor-escritura' });
    hilo.append(vista.nodo);
    vista.cuerpo.append(cursor);
    hilo.scrollTop = hilo.scrollHeight;

    entrada.value = '';
    entrada.style.height = 'auto';
    botonEnviar.disabled = true;

    let respuesta = '';
    let fuentes = [];
    // Sólo se sigue el scroll mientras el usuario esté abajo del todo: si se ha
    // subido a releer, el streaming no debe arrastrarlo.
    const pegado = () => hilo.scrollHeight - hilo.scrollTop - hilo.clientHeight < 90;

    abortar = flujoChat({ pregunta, historial: historialParaServidor() }, (evento, datos) => {
      switch (evento) {
        case 'consulta':
          vista.reescritura.hidden = false;
          vista.reescritura.append(el('div', {
            clase: 'reescritura', texto: `↻ Busco: ${datos.consulta}`,
            title: 'La pregunta de seguimiento se reescribe con el historial para buscar; '
                 + 'el modelo responde a la pregunta original.',
          }));
          break;

        case 'fuentes':
          fuentes = datos.docs;
          vista.linea.textContent = `${fuentes.length} fragmentos · generando…`;
          break;

        case 'token': {
          const abajo = pegado();
          respuesta += datos.t;
          pintarMd(vista.cuerpo, respuesta);
          vista.cuerpo.append(cursor);
          if (abajo) hilo.scrollTop = hilo.scrollHeight;
          break;
        }

        case 'fin': {
          cursor.remove();
          pintarMd(vista.cuerpo, respuesta);
          vista.linea.textContent = `${String(datos.latencia_s).replace('.', ',')} s`;
          turnos.push({
            pregunta,
            respuesta,
            // Sin respuesta de contenido no se guardan fuentes: no hay nada que citar.
            fuentes: datos.rechazo ? [] : fuentes,
            citas: datos.rechazo ? [] : datos.citas,
            rechazo: Boolean(datos.rechazo),
            n_docs: datos.n_docs,
          });
          guardarTurnos(turnos);
          pintarPie(vista.pie, i);
          mostrarFuentes(i);
          actualizarBarra();
          abortar = null;
          botonEnviar.disabled = !entrada.value.trim();
          if (pegado()) hilo.scrollTop = hilo.scrollHeight;
          break;
        }

        case 'error':
          cursor.remove();
          vista.linea.textContent = 'error';
          vista.pie.append(el('div', { clase: 'aviso aviso-error', texto: datos.mensaje }));
          abortar = null;
          botonEnviar.disabled = !entrada.value.trim();
          break;

        default:
          break;
      }
    });
  }

  /* ── Eventos ───────────────────────────────────────────────────────────── */
  formulario.addEventListener('submit', (ev) => {
    ev.preventDefault();
    preguntar(entrada.value.trim());
  });

  entrada.addEventListener('input', () => {
    entrada.style.height = 'auto';
    entrada.style.height = `${Math.min(entrada.scrollHeight, 190)}px`;
    botonEnviar.disabled = !entrada.value.trim() || abortar !== null;
  });

  entrada.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) {
      ev.preventDefault();
      preguntar(entrada.value.trim());
    }
  });

  // Las citas [n] del cuerpo las pinta el renderizador de Markdown como botones
  // y se regeneran en cada token: se enganchan por delegación. Cada una abre la
  // fuente de SU turno, no la de la última pregunta.
  hilo.addEventListener('click', (ev) => {
    const turno = ev.target.closest('.turno[data-turno]');
    if (!turno) return;
    const i = Number(turno.dataset.turno);
    if (i >= turnos.length) return;          // aún generando: sus fuentes no están
    const chip = ev.target.closest('.cita[data-cita]');
    if (chip) { mostrarFuentes(i, Number(chip.dataset.cita)); return; }
    if (ev.target.closest('[data-ver-fuentes]')) mostrarFuentes(i);
  });

  /* ── Estado inicial ────────────────────────────────────────────────────── */
  if (turnos.length) {
    vaciar(hilo);
    turnos.forEach((t, i) => {
      hilo.append(turnoUsuario(t.pregunta));
      const vista = turnoAgente(i, 'turno anterior');
      pintarMd(vista.cuerpo, t.respuesta);
      pintarPie(vista.pie, i);
      hilo.append(vista.nodo);
    });
    hilo.scrollTop = hilo.scrollHeight;
    mostrarFuentes(turnos.length - 1);
  } else {
    pintarBienvenida();
    mostrarFuentes(null);
  }

  actualizarBarra();
  entrada.focus();

  // Salir de la vista a media respuesta no debe dejar el flujo escribiendo
  // sobre nodos que ya no están en el documento.
  return () => { if (abortar) abortar(); };
}

/* ── Conversación guardada ───────────────────────────────────────────────── */
function recortarTexto(texto, max) {
  const t = String(texto || '').replace(/\s+/g, ' ').trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

function turnoValido(t) {
  return t && typeof t.pregunta === 'string' && typeof t.respuesta === 'string'
    && Array.isArray(t.fuentes) && Array.isArray(t.citas);
}

function leerTurnos() {
  try {
    const bruto = sessionStorage.getItem(CLAVE);
    if (bruto) {
      const datos = JSON.parse(bruto);
      return Array.isArray(datos) ? datos.filter(turnoValido) : [];
    }
    // Conversación guardada por la versión anterior: sólo pregunta y respuesta.
    const antiguo = JSON.parse(sessionStorage.getItem(CLAVE_ANTIGUA) || '[]');
    sessionStorage.removeItem(CLAVE_ANTIGUA);
    return Array.isArray(antiguo)
      ? antiguo.filter((t) => Array.isArray(t) && t.length === 2)
        .map(([pregunta, respuesta]) => ({
          pregunta, respuesta, fuentes: [], citas: [], rechazo: false, migrado: true,
        }))
      : [];
  } catch {
    return [];
  }
}

function guardarTurnos(turnos) {
  // Sólo se recorta lo que se guarda. En memoria no: cada turno pintado apunta
  // a su posición en la lista, y quitar los primeros movería todos los índices.
  try {
    sessionStorage.setItem(CLAVE, JSON.stringify(turnos.slice(-MAX_TURNOS_GUARDADOS)));
  } catch {
    /* Modo privado o almacenamiento lleno: la conversación sigue en memoria. */
  }
}
