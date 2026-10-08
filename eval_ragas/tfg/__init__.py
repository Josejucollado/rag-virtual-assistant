"""
tfg — Los experimentos concretos de la memoria del TFG.

El resto de `eval_ragas` es una herramienta general: genera, puntúa y compara
corridas cualesquiera. Aquí está lo que sólo tiene sentido para la memoria, con
los nombres de sus corridas escritos a mano:

    catalogo.py                  las corridas de la memoria y la de referencia
    comparativa_recuperacion.py  K=3/5/8, reranker, stemming, estilo (informe HTML)
    comparativa_generadores.py   generadores gratuitos frente al de pago (informe HTML)
    figuras_memoria.py           las figuras en PDF del capítulo de Resultados
    figuras_planificacion.py     el Gantt y la curva de esfuerzo de la Planificación

Todo es local: lee corridas ya puntuadas en `data/ragas/` y no llama a ninguna API.

    python -m eval_ragas.tfg.comparativa_recuperacion
    python -m eval_ragas.tfg.comparativa_generadores
    python -m eval_ragas.tfg.figuras_memoria          # -> thesis/imagenes/
    python -m eval_ragas.tfg.figuras_planificacion    # -> thesis/imagenes/
"""
