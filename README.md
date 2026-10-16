# bot_joseluis

Backend local para analizar documentos grandes (PDF digitales y escaneados) con un modelo de lenguaje que corre en CPU, sin enviar datos a servicios externos.

Stack: Python 3.12 + uv, FastAPI, Ollama (`qwen2.5:3b` y `qwen2.5:7b`). Open WebUI queda como interfaz en una fase posterior.

## Qué hace

1. Extrae el texto de un PDF por páginas (con OCR opcional para escaneados, reconstruyendo tablas).
2. Lo parte en fragmentos y genera notas con viñetas por fragmento, conservando el rango de páginas.
3. Guarda las notas en disco por huella (SHA-256), de modo que una corrida interrumpida se reanuda y los fragmentos sin cambios se reutilizan.
4. Bajo demanda, reduce las notas a un resumen con citas de páginas.
5. Verifica sin modelo que las cifras y siglas de cada nota aparezcan literalmente en el fragmento.

## Arquitectura

Hexagonal y "screaming": el código se organiza por capacidad del negocio, no por tipo técnico.

```
backend/src/
  app/                 composición de FastAPI y manejo de errores
  document_analysis/
    domain/            modelos, puertos, texto paginado, layout de OCR
    application/       casos de uso (chunk, analyze, summarize, verify)
    infrastructure/    adaptadores: Ollama, chunker, OCR, almacén JSON
    api/               endpoints
  shared/              config, constantes, enums, errores, utilidades
```

## Puesta en marcha

```bash
cd backend
uv venv && uv pip install -r requirements-dev.txt
cp .env.example .env
ollama pull qwen2.5:3b && ollama pull qwen2.5:7b
```

Los perfiles de modelo y los prompts se editan en `backend/config/` (`models.toml` y `prompts/*.md`). El perfil activo se cambia con `active_profile` o con la variable `APP_ACTIVE_PROFILE`.

Análisis de un PDF de prueba:

```bash
.venv/bin/python -I experiments/analyze.py ruta/al.pdf --store data/notes \
  --summary "Resume el documento" --report reporte.json   # --ocr para escaneados
```

## Calidad

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Las convenciones (sin comentarios ni docstrings, sin excepciones genéricas, sin `else` tras `return`, anidamiento máximo 2, funciones de hasta 60 líneas, sin `os.environ`, sin imports relativos) las hacen cumplir tests de AST en `backend/tests/conventions`.

## Documentación

- `backend/docs/reglas-de-desarrollo-backend.md`: reglas y buenas prácticas del backend.
- `backend/docs/referencia-de-funciones.md`: referencia de funciones por módulo.
- `backend/docs/variables-de-entorno.md`: configuración, prompts y variables de entorno.
- `backend/odd/tasks/analyze-large-documents.md`: especificación, tareas y bitácora de la funcionalidad de análisis.

## Estado

Hecho: extracción, OCR con reconstrucción de tablas, chunker, cliente Ollama, análisis jerárquico con reanudación, resumen, verificación literal de datos.

Pendiente: endpoints HTTP y trabajos en segundo plano con progreso, integración con Open WebUI, Word/Excel, embeddings sobre las notas.

Nota: los PDFs de muestra y los datos generados (`data/`) no se versionan.
