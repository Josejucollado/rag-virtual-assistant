/**
 * sistema.js — Cómo funciona el sistema, con los parámetros que están en vigor.
 *
 * Todas las cifras de configuración salen de `/api/estado`, no están escritas a
 * mano: si alguien cambia RERANK_K por variable de entorno, esta página lo
 * refleja.
 */

import { pedir, el, nMiles, nBytes } from '../api.js';
import { ESTADO } from '../app.js';

export async function vistaSistema(raiz) {
  const d = ESTADO.datos || await pedir('/api/estado');
  const m = d.modelos;
  const r = d.recuperacion;
  const i = d.indice;
  const c = d.corpus;
  const g = d.generacion;
  const generador = m.generador_corto || m.generador;
  const reranker = m.reranker_corto || m.reranker;

  raiz.append(
    el('header', { clase: 'cabecera' }, [
      el('div', { clase: 'migas', html: 'acerca de / <b>sistema</b>' }),
      el('h1', { texto: 'Cómo funciona' }),
      el('p', {
        texto: 'El recorrido completo, desde los PDF de la asignatura hasta la respuesta '
             + 'citada. Los valores son los que el servidor tiene cargados ahora mismo.',
      }),
    ]),

    el('div', { clase: 'tarjetas', style: 'margin-bottom:26px' }, [
      tarjeta(c.n_documentos, 'Documentos', 'PDF de la asignatura', 'tono-acento'),
      tarjeta(nMiles(c.n_chunks), 'Fragmentos', 'vectores en Chroma'),
      tarjeta(i.dimensiones, 'Dimensiones', 'por vector'),
      tarjeta(nBytes(c.bytes_pdf), 'Corpus', 'tamaño de los PDF'),
    ]),

    el('section', { style: 'margin-bottom:26px' }, [
      el('h2', { style: 'font-size:1.05rem;margin-bottom:14px', texto: 'El pipeline, paso a paso' }),
      el('div', { clase: 'tuberia' }, [
        paso('01', 'Extracción', [
          'Cada PDF se convierte a Markdown con Docling, con detección de tablas en modo ',
          'preciso. La conversión es incremental: sólo se rehace lo que ha cambiado, ',
          'comparando el MD5 del PDF.',
        ], ['docling', 'TableFormer ACCURATE', 'data/documentacion_md']),

        paso('02', 'Troceado', [
          `El texto se parte por encabezados, no por número de caracteres: así un fragmento `
          + `coincide con una sección del temario. Las secciones cortas se fusionan hasta `
          + `${nMiles(i.min_chunk)} caracteres y sólo las que pasan de ${nMiles(i.chunk_size)} `
          + `se subdividen, con solapamiento.`,
        ], [
          `chunk_size ${nMiles(i.chunk_size)}`,
          `overlap ${nMiles(i.chunk_overlap)}`,
          `min_chunk ${nMiles(i.min_chunk)}`,
        ]),

        paso('03', 'Indexado', [
          `Cada fragmento se convierte en un vector de ${i.dimensiones} dimensiones con `
          + `${m.embeddings}. Documentos y consultas se embeben de forma asimétrica —la `
          + `consulta lleva un prefijo de instrucción—, que es como el modelo espera que se use.`,
        ], [m.embeddings_proveedor, m.embeddings, `${i.dimensiones} dims`,
            `colección «${i.coleccion}»`, i.distancia]),

        paso('04', 'Recuperación híbrida', [
          `Dos búsquedas en paralelo sobre los mismos fragmentos: BM25 (léxico, encuentra el `
          + `término exacto) y densa (semántica, encuentra el concepto aunque cambien las `
          + `palabras). Se fusionan con RRF, ${r.retriever_k} candidatos por rama. Reducir las `
          + `palabras a su raíz (stemming) en BM25 se midió y no cambia nada: `
          + `${r.bm25_stemming ? 'aun así, este servidor lo tiene activado' : 'sigue apagado'}.`,
        ], [`BM25 ${nDec(r.pesos_hibrido.bm25)}`, `denso ${nDec(r.pesos_hibrido.denso)}`,
            `k=${r.retriever_k}`, `stemming ${r.bm25_stemming ? 'sí' : 'no'}`]),

        paso('05', 'Reordenado', [
          m.reranker
            ? `Un cross-encoder local lee la pregunta y cada fragmento a la vez —no por separado, `
              + `como los embeddings— y los reordena. Medido sobre las 94 preguntas, cambia mucho `
              + `lo que lee el generador, pero no mejora la respuesta: sin él, la corrección factual `
              + `es la misma y el sistema responde en menos de la mitad de tiempo. Se mantiene para `
              + `no mover la línea base de las comparaciones. Un modelo mayor, bge-reranker-v2-m3, `
              + `apunta a una mejora, pero es ocho veces más lento sin tarjeta gráfica.`
            : 'El reranker está desactivado: los candidatos del híbrido pasan directos al '
              + 'deduplicado. Medido sobre las 94 preguntas, la corrección factual es la misma que '
              + 'con él y el sistema responde en menos de la mitad de tiempo.',
        ], m.reranker ? [reranker, 'local, sin coste de API'] : ['desactivado']),

        paso('06', 'Deduplicado', [
          `Una sección larga se troceó en varios fragmentos contiguos que puntúan parecido y `
          + `se cuelan juntos. Se deja uno por sección y se recorta a los ${r.rerank_k} mejores, `
          + `que son los que verá el modelo. Con 3, 5 y 8 fragmentos, más contexto trae más `
          + `información útil pero también más relleno, y la respuesta apenas cambia: 5 es el equilibrio.`,
        ], [`top ${r.rerank_k}`, 'uno por sección']),

        paso('07', 'Generación', [
          `${generador} responde sólo con lo que hay en esos fragmentos, en estilo `
          + `«${g.estilo}», y cita cada afirmación con [n]. Si la información no está, devuelve `
          + `un texto de rechazo fijo en lugar de improvisar. Se midieron alternativas: el estilo `
          + `explicativo responde de más, un modelo pequeño (Apertus-8B) se inventa información y `
          + `un modelo comercial de pago (GPT-5.1) no mejora al gratuito.`,
        // Los razonadores de OpenAI no admiten temperatura (ver opciones_generador).
        ], [generador, m.generador_proveedor, `estilo ${g.estilo}`,
            m.generador_proveedor === 'openai' ? 'razonamiento bajo' : `temperatura ${g.temperatura}`],
        true),
      ]),
    ]),

    el('div', { clase: 'dos-columnas' }, [
      el('section', { clase: 'panel' }, [
        el('div', { clase: 'panel-titulo', texto: 'Configuración en vigor' }),
        el('table', { clase: 'tabla-config' }, [el('tbody', {}, [
          filaConfig('Generador', `${generador} (${m.generador_proveedor})`, m.generador),
          filaConfig('Estilo de respuesta', g.estilo),
          filaConfig('Reescritor de consultas', m.reescritor_corto || m.reescritor, m.reescritor),
          filaConfig('Embeddings', `${m.embeddings} · ${i.dimensiones}d`),
          filaConfig('Reranker', reranker || 'desactivado', m.reranker),
          filaConfig('Candidatos por rama (k)', String(r.retriever_k)),
          filaConfig('Fragmentos al contexto', String(r.rerank_k)),
          filaConfig('Stemming en BM25', r.bm25_stemming ? 'sí' : 'no'),
          filaConfig('Distancia', i.distancia),
          filaConfig('Temperatura', String(g.temperatura)),
        ])]),
      ]),

      el('section', { clase: 'panel' }, [
        el('div', { clase: 'panel-titulo', texto: 'Qué garantiza el sistema' }),
        el('ul', { clase: 'lista-garantias' }, [
          el('li', {}, [el('strong', { texto: 'Sólo el corpus. ' }),
            'El modelo tiene prohibido usar conocimiento propio o citar fuentes externas.']),
          el('li', {}, [el('strong', { texto: 'Trazabilidad. ' }),
            'Se recupera una sola vez por pregunta, así que los fragmentos que se enseñan son '
            + 'exactamente los que el modelo leyó.']),
          el('li', {}, [el('strong', { texto: 'Rechazo explícito. ' }),
            'Si la respuesta no está en el material, lo dice: ',
            el('em', { texto: `«${g.texto_rechazo}»` })]),
          el('li', {}, [el('strong', { texto: 'Sin subida de ficheros. ' }),
            'La ingesta es un proceso offline; desde la web sólo se consulta y se descarga.']),
          el('li', {}, [el('strong', { texto: 'La clave no sale del servidor. ' }),
            'El navegador nunca ve las credenciales de la API.']),
        ]),
      ]),
    ]),

    el('section', { clase: 'panel', style: 'margin-top:16px' }, [
      el('div', { clase: 'panel-titulo', texto: 'Regenerar el índice' }),
      el('p', { style: 'margin:0 0 10px;font-size:0.87rem;color:var(--text-secondary)' }, [
        'La web es de sólo lectura. Para añadir documentos, se dejan los PDF en ',
        el('code', { texto: 'data/documentacion_pdf/' }), ' y se ejecuta, desde la terminal:',
      ]),
      el('pre', {
        clase: 'texto-chunk',
        texto: 'python -m cli.pdf_to_md            # convierte sólo los PDF nuevos o cambiados\n'
             + 'python -m cli.process_md --reset   # rehace el índice completo (gratis, unos minutos)\n'
             + 'python -m web                      # y reiniciar el servidor',
      }),
      el('p', { clase: 'mini-nota' }, [
        'Sin --reset, los fragmentos de un documento que ha cambiado se quedarían con su versión '
        + 'anterior: Chroma no sobrescribe un identificador que ya existe.',
      ]),
    ]),
  );
}

/* ── Piezas ──────────────────────────────────────────────────────────────── */
function nDec(v) {
  return String(v).replace('.', ',');
}

function tarjeta(valor, etiqueta, nota, tono = '') {
  return el('div', { clase: `tarjeta ${tono}` }, [
    el('div', { clase: 'tarjeta-valor', texto: String(valor) }),
    el('div', { clase: 'tarjeta-etiqueta', texto: etiqueta }),
    el('div', { clase: 'tarjeta-nota', texto: nota }),
  ]);
}

function paso(n, titulo, texto, datos, ultimo = false) {
  return el('div', { clase: 'paso-tuberia' }, [
    el('div', { clase: 'paso-carril' }, [
      el('div', { clase: 'paso-punto', texto: n }),
      !ultimo && el('div', { clase: 'paso-linea' }),
    ]),
    el('div', { clase: 'paso-cuerpo' }, [
      el('div', { clase: 'paso-titulo', texto: titulo }),
      el('p', { clase: 'paso-texto' }, texto),
      el('div', { clase: 'paso-datos' }, datos.map((t) => el('span', { clase: 'doc-cifra', texto: t }))),
    ]),
  ]);
}

function filaConfig(clave, valor, completo = null) {
  return el('tr', {}, [
    el('td', { texto: clave }),
    el('td', { title: completo || valor }, [
      valor,
      completo && completo !== valor ? el('div', { clase: 'config-completo', texto: completo }) : null,
    ]),
  ]);
}
