"""
catalogo.py — Las corridas de la memoria.

La configuración de referencia (el sistema final) y las corridas que se comparan
con ella, cada una cambiando UNA sola cosa: (corrida, grupo, etiqueta), en el
orden de la memoria. Es lo que dibuja la figura resumen de `figuras_memoria`;
tenerlo en un solo sitio evita que cada informe se haga su lista.
"""

CORRIDA_REFERENCIA = "libre_conciso"

CORRIDAS_TFG = (
    (CORRIDA_REFERENCIA, "Referencia", "Sistema final"),
    ("libre_base", "Generación", "Estilo explicativo"),
    ("libre_minimo", "Generación", "Estilo mínimo"),
    ("libre_apertus", "Generación", "Generador Apertus-8B"),
    ("pago_gpt51", "Generación", "Generador GPT-5.1 (de pago)"),
    ("libre_conciso_bge", "Recuperación", "Reordenado bge-reranker-v2-m3"),
    ("libre_sin_reranker", "Recuperación", "Sin reordenado"),
    ("libre_k3", "Recuperación", "3 chunks al contexto"),
    ("libre_k8", "Recuperación", "8 chunks al contexto"),
    ("libre_conciso_stemming", "Recuperación", "Stemming en BM25"),
)
