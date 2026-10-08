/**
 * markdown.js — Renderizador Markdown mínimo para las respuestas del modelo.
 *
 * Se escribe a mano en vez de traer una librería por dos motivos concretos:
 *
 * 1. La aplicación tiene que funcionar sin internet (salvo las llamadas a Blablador),
 *    y las CDN quedan descartadas.
 * 2. NADA de renderizado matemático. El corpus está lleno de sintaxis de shell
 *    ($*, $@, $1, $?) y cualquier plugin de LaTeX la destroza. Es el mismo
 *    problema que obligó a poner `markdown.math.enabled: false` en
 *    `.vscode/settings.json`.
 *
 * Todo el texto se escapa ANTES de convertirse en HTML: lo que llega es salida
 * de un modelo, y nunca se inserta sin sanear.
 */

// Marcador de hueco para el código apartado: NUL no aparece en la salida del
// modelo y `escapar` no lo toca. Con un marcador de dígitos sueltos, un
// "de 3 a 5" del propio texto se confundiría con un hueco.
const SEP = '\u0000';
const RE_HUECO = /\u0000(\d+)\u0000/g;

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escapar(t) {
  return String(t ?? '').replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

/* ── En línea ────────────────────────────────────────────────────────────── */
function enLinea(texto, { citas = true } = {}) {
  // El código va primero y se aparta: dentro de `código` no se aplica ni
  // negrita ni cursiva ni citas, porque `[1]` o `*` pueden ser código de verdad.
  const apartados = [];
  let s = String(texto).replace(/`([^`]+)`/g, (_, cod) => {
    apartados.push(`<code>${escapar(cod)}</code>`);
    return `${SEP}${apartados.length - 1}${SEP}`;
  });

  s = escapar(s);

  // Enlaces [texto](url), sólo http(s) para no abrir la puerta a javascript:.
  s = s.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_, t, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`);

  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s.,;:)]|$)/g, '$1<em>$2</em>');
  s = s.replace(/(^|[\s(])_([^_\n]+)_(?=[\s.,;:)]|$)/g, '$1<em>$2</em>');

  // Citas [n] -> chip pulsable. El manejador lo engancha `chat.js`. También la
  // marca 【n†L4-L7】 que GPT-OSS trae de su entrenamiento: la misma que
  // reconoce `_CITA` en rag/generacion.py, para que chip y pie de fuentes cuadren.
  if (citas) {
    s = s.replace(/\[(\d{1,2})\]|【(\d{1,2})(?:†[^】]*)?】/g,
      (_, a, b) => { const n = a || b;
        return `<button type="button" class="cita" data-cita="${n}" title="Ver fragmento ${n}">${n}</button>`; });
  }

  return s.replace(RE_HUECO, (_, i) => apartados[Number(i)]);
}

/* ── Tablas ──────────────────────────────────────────────────────────────── */
function celdas(linea) {
  return linea.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map((c) => c.trim());
}

const ES_SEPARADOR = /^\s*\|?[\s:-]*-[-\s:|]*\|?\s*$/;

/* ── Bloques ─────────────────────────────────────────────────────────────── */
export function renderizar(md, opciones = {}) {
  const lineas = String(md ?? '').replace(/\r\n?/g, '\n').split('\n');
  const salida = [];
  let i = 0;

  const parrafo = [];
  const cerrarParrafo = () => {
    if (!parrafo.length) return;
    salida.push(`<p>${enLinea(parrafo.join(' '), opciones)}</p>`);
    parrafo.length = 0;
  };

  while (i < lineas.length) {
    const linea = lineas[i];

    // Bloque de código: se toma literal, sin tocar nada de lo de dentro.
    const valla = linea.match(/^\s*```+\s*([\w+-]*)\s*$/);
    if (valla) {
      cerrarParrafo();
      const cuerpo = [];
      i += 1;
      while (i < lineas.length && !/^\s*```+\s*$/.test(lineas[i])) {
        cuerpo.push(lineas[i]);
        i += 1;
      }
      i += 1;
      const lang = valla[1] ? ` class="lenguaje-${escapar(valla[1])}"` : '';
      salida.push(`<pre><code${lang}>${escapar(cuerpo.join('\n'))}</code></pre>`);
      continue;
    }

    if (!linea.trim()) { cerrarParrafo(); i += 1; continue; }

    const cabecera = linea.match(/^(#{1,6})\s+(.*)$/);
    if (cabecera) {
      cerrarParrafo();
      const n = Math.min(cabecera[1].length + 1, 6);   // h1 del modelo -> h2
      salida.push(`<h${n}>${enLinea(cabecera[2], opciones)}</h${n}>`);
      i += 1;
      continue;
    }

    if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(linea)) {
      cerrarParrafo();
      salida.push('<hr>');
      i += 1;
      continue;
    }

    if (/^\s*>/.test(linea)) {
      cerrarParrafo();
      const cuerpo = [];
      while (i < lineas.length && /^\s*>/.test(lineas[i])) {
        cuerpo.push(lineas[i].replace(/^\s*>\s?/, ''));
        i += 1;
      }
      salida.push(`<blockquote>${renderizar(cuerpo.join('\n'), opciones)}</blockquote>`);
      continue;
    }

    // Tabla: cabecera + fila de guiones. Sin la segunda no es tabla.
    if (linea.includes('|') && i + 1 < lineas.length && ES_SEPARADOR.test(lineas[i + 1])
        && lineas[i + 1].includes('-')) {
      cerrarParrafo();
      const enc = celdas(linea);
      i += 2;
      const filas = [];
      while (i < lineas.length && lineas[i].includes('|') && lineas[i].trim()) {
        filas.push(celdas(lineas[i]));
        i += 1;
      }
      const th = enc.map((c) => `<th>${enLinea(c, opciones)}</th>`).join('');
      const tb = filas.map((f) =>
        `<tr>${f.map((c) => `<td>${enLinea(c, opciones)}</td>`).join('')}</tr>`).join('');
      salida.push(`<table><thead><tr>${th}</tr></thead><tbody>${tb}</tbody></table>`);
      continue;
    }

    const vinieta = linea.match(/^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/);
    if (vinieta) {
      cerrarParrafo();
      const ordenada = /\d/.test(vinieta[2]);
      const items = [];
      let actual = null;
      const sangriaBase = vinieta[1].length;

      while (i < lineas.length) {
        const m = lineas[i].match(/^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/);
        if (m && m[1].length <= sangriaBase + 1) {
          if (actual) items.push(actual);
          actual = [m[3]];
          i += 1;
          continue;
        }
        // Continuación del item: línea sangrada o sublista.
        if (actual && lineas[i].trim() && /^\s{2,}/.test(lineas[i])) {
          actual.push(lineas[i].replace(/^\s{2}/, ''));
          i += 1;
          continue;
        }
        break;
      }
      if (actual) items.push(actual);

      const html = items.map((bloque) => {
        const [primera, ...resto] = bloque;
        const anidado = resto.length ? renderizar(resto.join('\n'), opciones) : '';
        return `<li>${enLinea(primera, opciones)}${anidado}</li>`;
      }).join('');
      salida.push(ordenada ? `<ol>${html}</ol>` : `<ul>${html}</ul>`);
      continue;
    }

    parrafo.push(linea.trim());
    i += 1;
  }

  cerrarParrafo();
  return salida.join('\n');
}

/** Pinta Markdown dentro de un nodo, ya saneado. */
export function pintar(nodo, md, opciones) {
  nodo.innerHTML = renderizar(md, opciones);
  return nodo;
}
