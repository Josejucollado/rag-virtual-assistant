/**
 * api.js — Cliente de la API y utilidades de DOM.
 *
 * El chat se consume con fetch + ReadableStream en vez de EventSource porque
 * hace falta un POST (la pregunta y el historial no caben en una URL) y
 * EventSource sólo sabe hacer GET.
 */

/* ── Peticiones ──────────────────────────────────────────────────────────── */
export async function pedir(ruta, opciones = {}) {
  const r = await fetch(ruta, opciones);
  if (!r.ok) {
    let detalle = `Error ${r.status}`;
    try {
      const cuerpo = await r.json();
      if (cuerpo && cuerpo.detail) detalle = cuerpo.detail;
    } catch { /* respuesta sin JSON: nos quedamos con el código */ }
    throw new Error(detalle);
  }
  return r.json();
}

/**
 * Consume el flujo SSE del chat.
 *
 * `al` recibe (evento, datos) por cada mensaje: consulta | fuentes | token |
 * fin | error, en ese orden. Devuelve una función para abortar.
 */
export function flujoChat({ pregunta, historial }, al) {
  const control = new AbortController();

  (async () => {
    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta, historial }),
        signal: control.signal,
      });
      if (!r.ok || !r.body) throw new Error(`El servidor respondió ${r.status}`);

      const lector = r.body.getReader();
      const deco = new TextDecoder();
      let resto = '';

      for (;;) {
        const { value, done } = await lector.read();
        if (done) break;
        resto += deco.decode(value, { stream: true });

        // Los mensajes SSE se separan por una línea en blanco. Lo que quede
        // suelto al final del trozo es un mensaje a medias: se guarda.
        const partes = resto.split('\n\n');
        resto = partes.pop();
        for (const bruto of partes) {
          let evento = 'message';
          const datos = [];
          for (const linea of bruto.split('\n')) {
            if (linea.startsWith('event:')) evento = linea.slice(6).trim();
            else if (linea.startsWith('data:')) datos.push(linea.slice(5).trim());
          }
          if (!datos.length) continue;
          try { al(evento, JSON.parse(datos.join('\n'))); }
          catch { /* trozo ilegible: se ignora en vez de romper el flujo */ }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') al('error', { mensaje: e.message });
    }
  })();

  return () => control.abort();
}

/* ── DOM ─────────────────────────────────────────────────────────────────── */
export function el(etiqueta, props = {}, hijos = []) {
  const nodo = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'clase') nodo.className = v;
    else if (k === 'texto') nodo.textContent = v;
    else if (k === 'html') nodo.innerHTML = v;      // sólo texto fijo del propio código (las migas)
    else if (k.startsWith('on')) nodo.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'dataset') Object.assign(nodo.dataset, v);
    else nodo.setAttribute(k, v === true ? '' : v);
  }
  for (const h of [].concat(hijos)) {
    if (h === null || h === undefined || h === false) continue;
    nodo.append(h.nodeType ? h : document.createTextNode(String(h)));
  }
  return nodo;
}

/**
 * Bloque pulsable que contiene otros bloques.
 *
 * Un <button> sólo admite contenido en línea: meterle un <div> o un <pre>
 * —como necesita la ficha de un fragmento— es HTML inválido y cada navegador lo
 * maqueta a su manera. Un div con rol de botón se ve y se comporta igual, pero
 * hay que devolverle a mano el teclado.
 */
export function bloqueClicable(props, hijos, alPulsar) {
  const nodo = el('div', { ...props, role: 'button', tabindex: '0' }, hijos);
  nodo.addEventListener('click', alPulsar);
  nodo.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' || ev.key === ' ') {
      ev.preventDefault();
      alPulsar(ev);
    }
  });
  return nodo;
}

export function vaciar(nodo) {
  while (nodo.firstChild) nodo.removeChild(nodo.firstChild);
  return nodo;
}

export function icono(d, tam = 14) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', tam);
  svg.setAttribute('height', tam);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.innerHTML = d;
  return svg;
}

export const ICONOS = {
  ojo: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  descarga: '<path d="M12 3v12"/><path d="m7 11 5 5 5-5"/><path d="M4 21h16"/>',
  cerrar: '<path d="M6 6l12 12M18 6 6 18"/>',
  enviar: '<path d="M4 12h15"/><path d="m13 6 6 6-6 6"/>',
  papelera: '<path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="M6 7l1 13h10l1-13"/>',
  externo: '<path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  buscar: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4.3-4.3"/>',
};

/* ── Formato ─────────────────────────────────────────────────────────────── */
export function nBytes(b) {
  if (!b) return '—';
  const u = ['B', 'KB', 'MB', 'GB'];
  let i = 0, v = b;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0).replace('.', ',')} ${u[i]}`;
}

export function nMiles(n) {
  return (n ?? 0).toLocaleString('es-ES');
}
