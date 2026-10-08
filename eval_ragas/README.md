# eval_ragas — Evaluación del RAG con RAGAS

Mide la calidad del RAG sobre el banco de preguntas con respuesta de referencia
(`data/BancoPreguntas_GroundTruth.csv`): 94 preguntas — 40 directas (ID 1–40),
39 de síntesis/multihop (41–79) y 15 de inferencia/casos de borde (80–94). Un
segundo banco, `data/BancoPreguntas_FueraCorpus.csv`, trae 15 preguntas cuya
respuesta **no** está en el temario: ahí lo correcto es negarse.

No reimplementa nada del RAG: importa el recuperador, el prompt y el generador del
paquete `rag`, que es el mismo código que ejecuta `cli/chat.py`. Lo que se mide es
exactamente lo que ve el usuario.

Todo es gratuito: el generador, el juez y los embeddings los sirve Blablador
(Helmholtz, FZ Jülich). La única excepción, opcional, es la corrida de pago
(`pago_gpt51`), en la que redacta GPT-5.1 de OpenAI; el juez sigue siendo el
gratuito. Para el recorrido completo del sistema, ver
[`../docs/PIPELINE.md`](../docs/PIPELINE.md).

## Cómo se ejecuta

Cada evaluación es una **corrida** con nombre, y escribe en su propio directorio,
`data/ragas/<corrida>/`. Lo que varía entre corridas se pasa por la shell, en la
misma línea:

```bash
EVAL_CORRIDA=libre_conciso python -m eval_ragas.generar_respuestas  # 1. el RAG contra las 94
EVAL_CORRIDA=libre_conciso python -m eval_ragas.puntuar             # 2. RAGAS  -> ENTREGABLE
EVAL_CORRIDA=libre_conciso python -m eval_ragas.informe             # 3. informe HTML
python -m eval_ragas.comparar --corridas libre_conciso,libre_bge   # 4. dos corridas, sin API

# Fuera de corpus: sólo la fase 1; la métrica es el % de RECHAZO que imprime al final
EVAL_BANCO=data/BancoPreguntas_FueraCorpus.csv EVAL_CORRIDA=libre_conciso_fuera_corpus \
  python -m eval_ragas.generar_respuestas
```

Comparativas locales de varias corridas a la vez (no llaman a la API):

```bash
python -m eval_ragas.tfg.comparativa_recuperacion   # K3/K5/K8, reranker, stemming, estilo, Apertus
python -m eval_ragas.tfg.comparativa_generadores    # Apertus-8B, GPT-OSS-120B y GPT-5.1 (de pago)
```

Generador de pago (OpenAI). Sólo cambia el generador; la puntuación es la de
siempre, gratuita:

```bash
PROVEEDOR_RAG=openai OPENAI_MODEL_RAG=gpt-5.1-AAAA-MM-DD EVAL_CORRIDA=pago_gpt51 \
  python -m eval_ragas.generar_respuestas --limit 5          # piloto: ~0,05 $
PROVEEDOR_RAG=openai OPENAI_MODEL_RAG=gpt-5.1-AAAA-MM-DD EVAL_CORRIDA=pago_gpt51 \
  python -m eval_ragas.generar_respuestas                    # el resto (tope: PRESUPUESTO_USD)
EVAL_CORRIDA=pago_gpt51 python -m eval_ragas.puntuar
```

En PowerShell: `$env:EVAL_CORRIDA="libre_conciso"; python -m eval_ragas.puntuar`.

> ⚠️ Ninguna de estas variables (`EVAL_CORRIDA`, `EVAL_BANCO`, `ESTILO_RESPUESTA`,
> `RERANKER_MODEL`, `RERANK_K`, `BM25_STEMMING`, `PROVEEDOR_RAG`, `OPENAI_MODEL_RAG`,
> `PRESUPUESTO_USD`) se escribe en el `.env`:
> `rag/config.py` hace `load_dotenv(override=True)`, el `.env` pisaría a la shell
> y todas las corridas acabarían en el mismo directorio.

La fase 0 (`adaptar_prompts`, plantillas del juez al español) ya está hecha y
versionada en `prompts_es/`: no hay que repetirla.

Las fases 1 y 2 van separadas para poder reajustar métricas o rehacer el informe
sin volver a generar. Ambas guardan por lotes y **se reanudan solas**: si Blablador
corta a mitad (un 429, una caída), basta con volver a lanzar el mismo comando.

- **La fase 1 guarda `configuracion.txt`** con los modelos y parámetros de la
  corrida (generador, juez, embeddings, reranker, `RETRIEVER_K`, `RERANK_K`,
  stemming y estilo de respuesta), y **se niega a reanudar** una corrida con otra
  configuración: mezclaría dos sistemas en un mismo CSV sin que nada lo reflejara.
  `--categoria MULTIHOP --limit 10` permite ampliar una corrida por partes.
- **Con un generador de pago, la fase 1 lleva la cuenta del gasto** en
  `consumo.csv` (tokens de entrada, salida y razonamiento, y coste por pregunta)
  y se para limpia antes de superar `PRESUPUESTO_USD` (2 $ por defecto). El tope
  vale para la corrida entera aunque se reanude: lo gastado se lee del fichero.
- **La fase 2 guarda `puntuacion.txt`**: el juez (sin razonamiento), su ritmo, los
  embeddings y una huella de las plantillas de `prompts_es/`. Se niega a reanudar
  una puntuación con otro juez u otras plantillas (invariante 6), y `comparar`
  avisa si dos corridas se puntuaron con jueces distintos. Las corridas anteriores
  a este fichero no dejan constancia, y el aviso lo dice.
- **La reanudación de `puntuar` es consciente de las columnas**, no sólo de los IDs.
  Una métrica nueva se calcula sólo sobre las filas ya hechas; un hueco `NaN` que el
  juez dejó por un fallo puntual se reintenta al volver a lanzar el comando. Con
  `--metricas context_precision` se reintentan sólo los huecos de esa métrica, sin
  volver a tirar las notas que ya eran válidas.

## Salidas

| Fichero | Qué es |
|---|---|
| `data/ragas/<corrida>/configuracion.txt` | Con qué se generó la corrida. Lo leen también `comparar.py` y el informe, que ya no describen la corrida con el entorno de quien los lanza. |
| `data/ragas/<corrida>/puntuacion.txt` | Con qué juez y qué plantillas se puntuó. |
| `data/ragas/<corrida>/consumo.csv` | Tokens y coste de cada respuesta de la fase 1 (0 $ con Blablador). |
| `data/ragas/<corrida>/respuestas_rag.csv` | Intermedio: respuesta del RAG + **texto completo** de los fragmentos recuperados. |
| `data/ragas/<corrida>/resultados_ragas.csv` | **Entregable.** Una fila por pregunta con las siete métricas. |
| `data/ragas/<corrida>/informe_ragas.html` | Informe con gráficas, tablas y análisis de errores. |
| `data/ragas/comparativa*.html` | Dos corridas enfrentadas (`--salida` para darle nombre). |
| `data/ragas/comparativa_recuperacion.html` | K3/K5/K8, reranker y stemming en un informe local; Friedman, post hoc, IC bootstrap y banda de ruido. |
| `data/ragas/comparativa_generadores.html` | Generador gratuito frente a de pago: métricas, estratos de contexto, coste, rechazos fuera de corpus, formato de las citas y réplicas. |

## Las siete métricas

| Columna | Qué mide |
|---|---|
| `faithfulness` | ¿Cada afirmación se sostiene en el contexto recuperado? Detecta alucinación. |
| `answer_relevancy` | ¿La respuesta contesta a lo que se preguntó? |
| `context_precision` | ¿Los fragmentos recuperados son relevantes y están bien ordenados? Evalúa el reranker. |
| `context_recall` | ¿El contexto trae todo lo necesario para construir la referencia? Evalúa la recuperación. |
| `factual_correctness` | Media armónica de la precisión factual y la cobertura factual. Penaliza responder de más. |
| `factual_recall` | Qué parte de las afirmaciones del ground truth aparece en la respuesta. No penaliza responder de más. |
| `semantic_similarity` | Coseno respuesta ↔ referencia. Sin coste de LLM. |

Las cuatro primeras son el *RAG triad*; las tres últimas puntúan contra el ground
truth.

**Las dos factuales hacen falta a la vez.** El ground truth del banco son respuestas
de una o dos frases. Cada afirmación correcta que el RAG añade de más baja la
precisión, y con ella la F1: la F1 mide tanto la verbosidad como el acierto. La
cobertura sólo pregunta si la respuesta dice lo que dice la referencia. Leer sólo la
F1 lleva a concluir que el RAG falla mucho más de lo que falla.

### La corrección factual es propia, no la de RAGAS

Las dos caras usan `CorreccionFactual` (en `metricas.py`), una subclase de la
`FactualCorrectness` de RAGAS con dos arreglos, ambos medidos en `prueba10`:

1. **La cobertura se calcula de verdad.** El «recall» de RAGAS es
   tp / (tp + fn), con tp contado sobre las afirmaciones **de la respuesta**:
   mezcla los dos sentidos. Daba 0 a respuestas que cubrían el ground truth entero
   (preguntas 3 y 4: 1/1 y 2/2) si el juez no respaldaba ninguna de las suyas, y
   premia la verbosidad (10 afirmaciones respaldadas y 1 de 2 cubierta dan 10/11,
   no 1/2). `puntuacion_factual()` calcula la proporción de afirmaciones del ground
   truth que respalda la respuesta, y la F1 como media armónica de esa cobertura y
   la precisión. De paso, la cobertura hace 2 llamadas al juez y no 4.
2. **El juez ve la pregunta.** Los ground truth están escritos como respuesta a su
   pregunta y se apoyan en ella («En este contexto…», «Realiza dos funciones…», sin
   decir quién). Leídos solos, el juez rechazaba afirmaciones casi literales: 12 de
   12 y 3 de 3 en las preguntas 3 y 4. Con «Pregunta + ground truth» como premisa
   aceptaba justo las que coinciden y seguía rechazando los detalles que el ground
   truth no trae.

Conserva el `name` de RAGAS a propósito: las plantillas en español se cargan por él.
Tiene sus tests en `tests/test_factual.py`.

Una limitación que **no** se ha tocado: el juez descompone con atomicidad baja y
agrupa varios datos en una afirmación («guarda el PC y la PSW en un lugar seguro de
la memoria»), así que un detalle que falte la anula entera. Se aplica igual a todas
las corridas.

## Los fragmentos van por referencia, no por texto

El entregable trae una columna `fragmentos` con los `chunk_id` separados por `|`, no
el texto de los fragmentos:

```
00 SSOO Conceptos Generales.md#0001 | 01 SSOO Estructuras.md#0014 | ...
```

Los cinco fragmentos íntegros son unos 9.500 caracteres por fila y dejan la hoja de
cálculo ilegible. El `chunk_id` identifica el fragmento y lleva dentro el fichero de
origen, así que sirve para ir a buscarlo:

```bash
python -m cli.inspeccionar --chunk "00 SSOO Conceptos Generales.md#0001"
```

El texto completo sigue en `respuestas_rag.csv` (columna `retrieved_contexts`), que
es de donde lo lee el juez: **puntúa siempre sobre el contenido real**.

## Rechazo = fallo (y al revés fuera de corpus)

Las 94 preguntas son *in-corpus*, así que responder
«No tengo la suficiente información para contestar a su pregunta» es siempre un
**fallo**. Cada fila lleva una columna `resultado`:

- `OK` — respuesta de contenido.
- `RECHAZO` — se negó a responder. Cuenta como fallo.
- `ERROR` — excepción de la API tras agotar reintentos. Excluido de las medias.

Se clasifica con `es_rechazo()` del paquete `rag`, que normaliza tildes y puntuación.
Busca la frase de rechazo **dentro** de la respuesta: una respuesta parcial que
además añade la frase cuenta como rechazo (visto en la pregunta 76). El informe da
las medias sobre todas las preguntas y sólo sobre las `OK`, para separar «responde
mal» de «no responde».

En el banco fuera de corpus es al revés: el rechazo es el acierto, y la métrica es el
porcentaje de `RECHAZO`.

## Comparar dos corridas

`comparar.py` lee los entregables ya producidos y no recalcula nada, así que se
ejecuta sin clave de API. Tres decisiones que condicionan lo que sale:

**Se alinea por `ID`, no por posición.** Las preguntas que no estén en las dos
quedan fuera y el informe lo dice: dos medias sobre conjuntos distintos no son
comparables.

**Qué se descarta y qué no.** Un `ERROR` en cualquiera de los dos lados tumba el
par entero. Un `RECHAZO` se conserva, porque negarse a responder es un fallo del
sistema, no un dato que falte. Un `NaN` descarta el par **sólo para esa métrica**:
es un fallo del juez, no del RAG, y rellenarlo con cero convertiría una caída de la
API en una regresión. Por eso cada fila de la tabla lleva su propio `n`.

**Wilcoxon pareado, y con Holm.** Pareado porque las dos corridas responden a las
mismas preguntas: cada pregunta es su propio control, y la variación entre preguntas
fáciles y difíciles se cancela. No paramétrico porque las notas están acotadas en
[0, 1] y son poco normales. Con siete métricas a la vez hay cerca de un 30 % de
probabilidad de que alguna salga «significativa» por azar: la columna **p (Holm)**
lo corrige. Con menos de 10 pares no se calcula (se marca con `*`).

El bloque que no usa ningún LLM es el **solape de fragmentos** entre las dos
corridas: mide directamente lo que cambió en la recuperación, sin ruido del juez.

### El ruido del instrumento, medido

Ni el generador ni el juez de Blablador son deterministas, aunque vayan a
temperatura 0: el servidor agrupa peticiones de varios usuarios. Repuntuar las
mismas 10 respuestas cambió 4 de 50 celdas (hasta 0,5 en una fila de precisión del
contexto) y movió las medias hasta 0,07.

La medida buena salió gratis de dos corridas ya hechas. `libre_conciso` y
`libre_conciso_stemming` usan el mismo generador, y en **68 de las 94 preguntas
recibieron exactamente el mismo contexto, en el mismo orden**. En esas 68 todo lo
que cambie es ruido:

| Métrica | Preguntas que cambiaron | DT de la diferencia | Banda al 95 % con n = 94 |
|---|---|---|---|
| Corrección factual (F1) | 47 de 68 | 0,176 | ±0,036 |
| Cobertura factual | 23 de 68 | 0,158 | ±0,032 |
| Fidelidad | 29 de 67 | 0,112 | ±0,023 |
| Relevancia | 68 de 68 | 0,148 | ±0,030 |
| Cobertura del contexto | 5 de 68 | 0,160 | ±0,032 |
| Precisión del contexto | 8 de 68 | 0,054 | ±0,011 |
| Similitud semántica | 66 de 68 | 0,029 | ±0,006 |

Sólo 3 de las 68 respuestas salieron idénticas. Las dos métricas de contexto no
dependen de la respuesta, así que sus cambios son ruido **del juez** por sí solo.

`comparar`, `comparativa_recuperacion` y `comparativa_generadores` ponen esta
**banda de ruido** junto a cada Δ (`comparar.ruido_por_metrica`): un Δ dentro de la
banda no se distingue de relanzar la misma configuración aunque su p sea bajo. Si
existe la réplica A/A `libre_conciso_r2`, la banda sale de ella.

## Corridas hechas

Los resultados de todas las corridas de la memoria (estilo, K, reranker,
stemming, generadores gratuitos y de pago) están en
[`../thesis/RESULTADOS.md`](../thesis/RESULTADOS.md).

## Los módulos

| Módulo | Responsabilidad |
|---|---|
| `comun.py` | Rutas por corrida, `configuracion.txt`, categorías del banco, juez (con limitador), embeddings del juez, reintentos y utilidades de CSV. No importa `ragas`. |
| `metricas.py` | Catálogo de las siete métricas, carga de las plantillas en español y `CorreccionFactual`. |
| `adaptar_prompts.py` | Fase 0: traduce las plantillas del juez. |
| `generar_respuestas.py` | Fase 1: ejecuta el RAG contra el banco. |
| `puntuar.py` | Fase 2: puntúa con RAGAS. Produce el entregable. |
| `informe.py` | Fase 3: informe HTML autocontenido de una corrida. |
| `comparar.py` | Fase 4: informe HTML que enfrenta dos corridas. No llama a ninguna API. |
| `estadistica.py` | Los contrastes: Wilcoxon pareado, Holm, banda de ruido, IC bootstrap, Friedman e IC de Wilson. Funciones puras. |
| `tfg/` | Los experimentos de la memoria: catálogo de corridas, `comparativa_recuperacion`, `comparativa_generadores` y las figuras en PDF (`figuras_memoria`, `figuras_planificacion`). |
| `graficas.py` | SVG en línea, sin CDN, para los informes HTML. |
| `estilo.py` | La hoja de estilo que comparten los informes HTML. No importa nada. |

`ORDEN_CAT` y `CAT_CORTA` viven en `comun.py` y no en `metricas.py` a propósito:
`metricas` importa `ragas`, que tarda varios segundos en cargar, y la web necesita
esos nombres para pintar etiquetas sin pagar ese coste.

## Configuración del juez

- **Modelo:** Qwen3.8-Flash-Next (`BLABLADOR_MODEL_JUDGE`), por su identificador
  concreto y no por un alias `alias-*`, que Blablador reapunta sin aviso. De otra
  familia que el generador (GPT-OSS) a propósito: un juez tiende a puntuar mejor a
  su propia familia.
- **Sin razonamiento** (`construir_llm_juez()`): con él, una llamada del tamaño de
  faithfulness tardaba 123 s y 8.466 tokens de razonamiento, contra 8,5 s sin él, y
  faithfulness pasaba del límite de 180 s de RAGAS.
- **A 12 peticiones por minuto** (`RPM_JUEZ`): Blablador da a los usuarios externos
  15 por minuto en los modelos grandes, y cada exceso bloquea la clave, cada vez más
  tiempo. Ese limitador marca la duración de la fase 2: unas 3 h para las 94.
- **Descartado MiniMax-M2.7** (`alias-huge`): mete su razonamiento `<think>…</think>`
  dentro de la respuesta y RAGAS no puede leer su JSON.

### El instrumento de medida se queda quieto

El juez y sus embeddings (los mismos Qwen3-Embedding-8B del índice, que usan
`semantic_similarity` y `answer_relevancy`) son idénticos en todas las corridas que
se comparan. Si cambiaran, un 0,80 frente a un 0,78 no diría nada del RAG: serían
dos reglas con las marcas en sitios distintos. Si se cambia el juez, su
razonamiento o la corrección factual, hay que repuntuar con ellos todas las corridas
antes de compararlas.

Las plantillas traducidas viven en `prompts_es/` y **se versionan en git**: fijas y
auditables, para que la evaluación sea reproducible.

## Detalles que costaron un rato

- `answer_relevancy` usa `strictness=1`. Con el 3 por defecto, RAGAS pide varios
  candidatos en una llamada, que no todos los modelos admiten, y triplica las
  peticiones.
- RAGAS no nombra las columnas como uno pide: `LLMContextPrecisionWithReference`
  sale como `llm_context_precision_with_reference` y las dos caras factuales como
  `factual_correctness(mode=...)`. `puntuar.mapear_columnas()` lo resuelve; sin eso,
  esas columnas se llenan de `NaN` en silencio.
- Se puntúa sobre la respuesta sin las marcas de cita. `quitar_citas()` reconoce
  `[n]` y también `【n†L4-L7】`, el formato que GPT-OSS trae de su entrenamiento: en
  `libre_conciso` aparece en 25 de las 92 respuestas de contenido (en las
  primeras pruebas se había visto en 1 de cada 13).
- **Al reanudar, las filas nuevas perdían sus columnas.** `fusionar_y_guardar`
  guardaba las de IDs nuevos sólo con ID y notas, sin pregunta, respuesta ni
  categoría. Arreglado y con tests (`tests/test_puntuar.py`).
- `context_precision` hace una llamada al juez por fragmento (5 por pregunta) y,
  con la cola del limitador llena, a veces no cabe en los 180 s de RAGAS: deja
  huecos `TimeoutError` (9 de 94 en `libre_conciso`). Se rellenan con
  `puntuar --metricas context_precision`, con la cola ya vacía.
- `max_workers=4` en vez de los 16 por defecto: el ritmo lo marca el limitador del
  juez, y más hilos sólo harían más cola.
