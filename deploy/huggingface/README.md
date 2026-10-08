---
title: Docente virtual de Sistemas Operativos
emoji: 🎓
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: RAG tutor with cited answers for an Operating Systems course
---

# Docente virtual de Sistemas Operativos

Public demo of a RAG assistant that answers questions about the Operating
Systems course of the Universidad de Jaén, citing the fragment behind every
claim. Source code and evaluation: see the GitHub repository.

## Deploying this Space

These two files (`README.md` and `Dockerfile`) are the whole Space.

1. **Check first** that Blablador's terms of use allow serving a public app with
   your personal token.
2. Run the `indice` workflow on GitHub and set the repository variable
   `INDICE_URL` to the URL it prints. Then let the `docker` workflow publish the
   image, and make the GHCR package public.
3. Create a Space with the Docker SDK and upload these two files.
4. In the Space settings, add the secret `BLABLADOR_API_KEY`.

The demo limits questions per minute (`DEMO_PUBLICA=1`) so that visitors cannot
get the API key rate-limited.
