"""
adaptar_prompts.py — Fase 0: traduce al español las plantillas del juez.

Las plantillas internas de RAGAS vienen en inglés, pero el corpus, las preguntas
y las respuestas de este RAG son en español. Pedirle a un juez que descomponga
en afirmaciones un texto en español siguiendo instrucciones en inglés añade
ruido innecesario.

`MetricWithLLM` hereda de `PromptMixin`, que ofrece `adapt_prompts()` para
traducirlas con un LLM y `save_prompts()` / `load_prompts()` para cachearlas.

Se ejecuta UNA vez y el resultado se versiona en git. Así las plantillas quedan
fijas y auditables entre corridas: si se retradujeran en cada evaluación, dos
corridas podrían no ser comparables sin que nada lo indicara.

Uso:
    python -m eval_ragas.adaptar_prompts
    python -m eval_ragas.adaptar_prompts --forzar
"""

from __future__ import annotations

import argparse
import asyncio
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from eval_ragas import metricas as M  # noqa: E402
from eval_ragas.comun import (  # noqa: E402
    MODEL_JUDGE,
    PROMPTS_ES_DIR,
    build_juez,
)


def envolver_juez():
    """El juez, en la interfaz que espera `adapt_prompts()`.

    `adapt_prompts` necesita un `BaseRagasLLM`, no un modelo de LangChain suelto,
    así que hay que envolverlo explícitamente (`evaluate()` sí lo hace solo).
    """
    from ragas.llms import LangchainLLMWrapper

    return LangchainLLMWrapper(build_juez())


async def adaptar(forzar: bool) -> None:
    PROMPTS_ES_DIR.mkdir(parents=True, exist_ok=True)
    juez = envolver_juez()

    print(f"Traduciendo las plantillas de RAGAS al español con {MODEL_JUDGE}")
    print(f"Destino: {PROMPTS_ES_DIR}\n")

    total = 0
    for metrica in M.construir():
        if not M.usa_llm(metrica):
            print(f"- {metrica.name}: no usa LLM, nada que traducir.")
            continue

        nombres = list(metrica.get_prompts())
        ficheros = [PROMPTS_ES_DIR / f"{metrica.name}_{p}_{M.IDIOMA}.json"
                    for p in nombres]

        if all(f.exists() for f in ficheros) and not forzar:
            print(f"- {metrica.name}: ya traducida ({len(nombres)} plantillas), se omite.")
            continue

        # `save_prompts()` lanza FileExistsError en lugar de sobrescribir, así
        # que al reintentar hay que limpiar antes.
        for f in ficheros:
            f.unlink(missing_ok=True)

        print(f"- {metrica.name}: traduciendo {len(nombres)} plantilla(s)...")
        # `adapt_instruction=True` es deliberado: por defecto RAGAS traduce solo
        # los ejemplos few-shot y deja la instrucción en inglés. Traducir también
        # la instrucción deja el juez íntegramente en español, que es el idioma
        # del corpus, de las preguntas y de las respuestas que va a puntuar.
        adaptadas = await metrica.adapt_prompts(
            language=M.IDIOMA, llm=juez, adapt_instruction=True,
        )
        metrica.set_prompts(**adaptadas)
        metrica.save_prompts(str(PROMPTS_ES_DIR))
        total += len(adaptadas)
        print(f"  guardadas: {', '.join(adaptadas)}")

    print(f"\nHecho. {total} plantilla(s) traducidas en esta ejecución.")
    print("Revisa los .json y versiónalos en git para que la evaluación sea reproducible.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 0: traduce las plantillas del juez al español.")
    ap.add_argument("--forzar", action="store_true",
                    help="retraduce aunque ya existan los ficheros cacheados")
    args = ap.parse_args()
    asyncio.run(adaptar(args.forzar))


if __name__ == "__main__":
    main()
