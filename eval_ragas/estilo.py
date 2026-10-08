"""
estilo.py — La hoja de estilo que comparten los informes HTML.

Vive aparte, y no dentro de `informe.py`, porque hay dos informes que la usan:
el de una corrida (`informe.py`) y el que compara dos (`comparar.py`). Con una
copia en cada uno, se desviarían en los detalles a la primera retoque.

No importa nada, igual que `graficas.py`: así la hoja está disponible sin
arrastrar `ragas`, que es lo que tarda varios segundos en cargar.
"""

FUENTES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=IBM+Plex+Mono:wght@400;600&'
    'family=IBM+Plex+Sans:wght@400;500;600;700&'
    'family=IBM+Plex+Serif:ital,wght@0,400;0,600;1,400&display=swap">'
)

CSS = """
/* Superfamilia IBM Plex: diseñada para documentación técnica, así que encaja con
   un informe sobre apuntes de Sistemas Operativos. Sans para titulares, interfaz
   y texto de las gráficas; Serif para la prosa, que se lee seguida como una
   memoria; Mono para cifras y ejes, donde importa que los dígitos se alineen. */
:root {
  --sans:  "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --serif: "IBM Plex Serif", Georgia, "Times New Roman", serif;
  --mono:  "IBM Plex Mono", ui-monospace, SFMono-Regular, Consolas, monospace;
  color-scheme: light;
  --page:#f9f9f7; --surface-1:#fcfcfb;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --track:#eeede8;
  --border:rgba(11,11,11,0.10);
  --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a;
  --status-good:#0ca30c; --status-warning:#fab219; --status-critical:#d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page:#0d0d0d; --surface-1:#1a1a19;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --track:#242422;
    --border:rgba(255,255,255,0.10);
    --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page:#0d0d0d; --surface-1:#1a1a19;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --track:#242422;
  --border:rgba(255,255,255,0.10);
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70;
}

* { box-sizing:border-box; }
body {
  margin:0; padding:0 20px 80px;
  background:var(--page); color:var(--text-primary);
  font-family:var(--sans);
  font-size:16px; line-height:1.55;
  -webkit-font-smoothing:antialiased;
}
.envoltorio { max-width:860px; margin:0 auto; }

header.portada { padding:60px 0 30px; border-bottom:1px solid var(--border); margin-bottom:8px; }
.eyebrow {
  font-family:var(--mono); font-size:0.72rem; letter-spacing:0.12em;
  text-transform:uppercase; color:var(--muted); margin:0 0 14px;
}
h1 { font-size:2.1rem; line-height:1.15; margin:0 0 12px; letter-spacing:-0.02em;
  font-weight:600; text-wrap:balance; }
.subtitulo { font-family:var(--serif); color:var(--text-secondary);
  margin:0 0 20px; font-size:1.06rem; line-height:1.5; max-width:60ch; }
.config { color:var(--muted); font-size:0.8rem; margin:0; font-family:var(--mono); }
.config code { background:var(--track); padding:1px 5px; border-radius:4px;
  font-size:0.95em; font-family:var(--mono); color:var(--text-secondary); }

section { margin:52px 0 0; }
h2 { font-size:1.34rem; margin:0 0 8px; letter-spacing:-0.015em; font-weight:600;
  text-wrap:balance; }
h3 { font-size:1.04rem; margin:36px 0 8px; font-weight:600; letter-spacing:-0.01em; }
.intro { font-family:var(--serif); color:var(--text-secondary);
  margin:0 0 20px; font-size:0.95rem; line-height:1.6; max-width:66ch; }
.intro q { font-style:italic; }
.intro code { font-family:var(--mono); font-size:0.88em; background:var(--track);
  padding:1px 4px; border-radius:3px; }

.tarjetas { display:grid; grid-template-columns:repeat(auto-fit,minmax(152px,1fr)); gap:12px; margin:30px 0 0; }
.tarjeta { background:var(--surface-1); border:1px solid var(--border); border-radius:12px; padding:16px 15px; }
/* Cifra grande: sans proporcional, nunca tabular — a este tamaño los dígitos de
   ancho fijo dejan huecos raros. */
.tarjeta-valor { font-size:1.9rem; font-weight:600; line-height:1.1; letter-spacing:-0.025em; }
.tarjeta-etiqueta { font-size:0.85rem; margin-top:6px; color:var(--text-primary); font-weight:500; }
.tarjeta-nota { font-size:0.75rem; color:var(--muted); margin-top:3px; font-family:var(--mono); }
.tono-ok .tarjeta-valor { color:var(--status-good); }
.tono-mal .tarjeta-valor { color:var(--status-critical); }
.tono-aviso .tarjeta-valor { color:var(--status-warning); }

.grafica { width:100%; height:auto; display:block; background:var(--surface-1);
  border:1px solid var(--border); border-radius:12px; padding:10px 6px; overflow:visible; }
.grafica text { font-family:var(--sans); }
.tick, .tick-x { font-family:var(--mono); font-size:10.5px; fill:var(--muted); }
.etiqueta-eje { font-size:12.5px; fill:var(--text-secondary); }
.valor { font-family:var(--mono); font-size:12px; fill:var(--text-primary); }
.valor-dentro { font-family:var(--mono); font-size:11px; fill:#ffffff; font-weight:600; }
.eje-titulo { font-size:11.5px; fill:var(--text-secondary); letter-spacing:0.01em; }

.leyenda { display:flex; flex-wrap:wrap; gap:16px; margin:0 0 12px; font-size:0.82rem; color:var(--text-secondary); }
.ley-item { display:inline-flex; align-items:center; gap:7px; }
.ley-punto { width:11px; height:11px; border-radius:3px; display:inline-block; }
.ley-icono { font-size:0.8rem; }

.rejilla-mini { display:grid; grid-template-columns:repeat(auto-fit,minmax(252px,1fr)); gap:16px; }
.mini { margin:0; }
.mini figcaption { font-size:0.85rem; font-weight:600; margin-bottom:6px; }
.mini-nota { font-size:0.73rem; color:var(--muted); margin:6px 0 0; font-family:var(--mono); }

.tabla-vista { margin-top:16px; }
.tabla-vista summary { cursor:pointer; font-size:0.83rem; color:var(--text-secondary);
  padding:6px 0; font-family:var(--mono); }
.tabla-vista summary:focus-visible { outline:2px solid var(--series-1); outline-offset:3px; border-radius:3px; }
.envoltorio-tabla { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:0.85rem; margin-top:8px; }
th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:top; }
thead th { color:var(--muted); font-weight:600; font-size:0.72rem; font-family:var(--mono);
  text-transform:uppercase; letter-spacing:0.07em; }
/* tabular-nums solo aquí: son columnas de cifras que deben alinearse en vertical. */
tbody td { font-family:var(--mono); font-variant-numeric:tabular-nums; }
tbody th { font-weight:500; font-family:var(--sans); }
td.desc { color:var(--muted); font-size:0.78rem; font-family:var(--serif); }

.tabla-peores { margin-top:12px; }
.tabla-peores .col-id { color:var(--muted); width:46px; }
.tabla-peores .col-nota { width:58px; font-weight:600; }
.tabla-peores td:last-child { font-family:var(--sans); }
.p-preg { margin:0 0 10px; font-weight:600; font-size:0.9rem; }
.p-eti { margin:10px 0 3px; font-size:0.68rem; text-transform:uppercase;
  letter-spacing:0.08em; color:var(--muted); font-family:var(--mono); }
.p-txt { margin:0; color:var(--text-secondary); font-size:0.84rem;
  font-family:var(--serif); line-height:1.5; }
/* Solo la referencia al fragmento, nunca su texto: la tabla se lee de un vistazo
   y el chunk_id permite ir a buscarlo cuando hace falta. */
.p-frags { margin:0; padding-left:1.5em; font-family:var(--mono);
  font-size:0.74rem; color:var(--muted); line-height:1.6; }
.p-frags li { overflow-wrap:anywhere; }

.nota { margin:20px 0 0; padding:15px 17px; background:var(--surface-1);
  border:1px solid var(--border); border-left:3px solid var(--series-2);
  border-radius:8px; }
.nota-titulo { margin:0 0 7px; font-weight:600; font-size:0.88rem; }
.nota p { margin:0; font-family:var(--serif); font-size:0.88rem;
  color:var(--text-secondary); line-height:1.6; max-width:66ch; }

footer { margin-top:60px; padding-top:22px; border-top:1px solid var(--border);
  color:var(--muted); font-size:0.8rem; font-family:var(--serif); }
footer code { font-family:var(--mono); font-size:0.9em; }
footer p { margin:0 0 8px; max-width:66ch; }
"""
