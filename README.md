# bot_joseluis

Backend local para analizar documentos grandes (PDF digitales y escaneados) con un modelo de lenguaje que corre en la propia máquina (CPU, o GPU NVIDIA si hay), sin enviar datos a servicios externos.

Stack: Python 3.12 + uv, FastAPI, SQLite, Ollama (`qwen3.5:4b` para las notas y `qwen3.5:9b` para el resumen, con el modo de razonamiento apagado) y Open WebUI como interfaz. La GPU es opcional.

## Qué hace

1. Extrae el texto de un PDF por páginas (con OCR opcional para escaneados, reconstruyendo tablas).
2. Lo parte en fragmentos y genera notas con viñetas por fragmento, conservando el rango de páginas.
3. Guarda las notas en disco por huella (SHA-256), de modo que una corrida interrumpida se reanuda y los fragmentos sin cambios se reutilizan.
4. Bajo demanda, reduce las notas a un resumen con citas de páginas.
5. Verifica sin modelo que las cifras y siglas de cada nota aparezcan literalmente en el fragmento.
6. Expone una API HTTP: se sube un PDF, se recibe un identificador de trabajo y se consulta su estado hasta obtener el resumen. Un único hilo en segundo plano procesa los trabajos de a uno, en orden de llegada.

## Arquitectura

Hexagonal y "screaming": el código se organiza por capacidad del negocio, no por tipo técnico.

```
backend/src/
  app/                 composición de FastAPI, manejo de errores, ciclo de vida y procesador de trabajos
  document_analysis/
    domain/            modelos, puertos, texto paginado, layout de OCR
    application/       casos de uso (chunk, analyze, summarize, verify, trabajos)
    infrastructure/    adaptadores: Ollama, chunker, OCR, almacén JSON, PDF subidos, SQLite y migraciones
    api/               endpoints de trabajos y sus DTO
  shared/              config, constantes, enums, errores, utilidades
```

## Puesta en marcha

```bash
cd backend
uv venv && uv pip install -r requirements-dev.txt
cp .env.example .env
ollama pull qwen3.5:4b && ollama pull qwen3.5:9b
.venv/bin/uvicorn src.app.main:build_default_app --factory
```

Al arrancar, el servidor crea `data/app.db`, aplica las migraciones pendientes de `backend/migrations/`, devuelve a la cola los trabajos que quedaron a medias y arranca el procesador de trabajos. `GET /health` responde `{"status": "ok"}`.

Los perfiles de modelo y los prompts se editan en `backend/config/` (`models.toml` y `prompts/*.md`). El perfil activo se cambia con `active_profile` o con la variable `APP_ACTIVE_PROFILE`. `summary_batch_chars` (obligatorio en cada perfil) fija cuántos caracteres de notas entran en cada llamada de resumen; se usa el del perfil de resumen y no puede superar `(num_ctx - max_output_tokens) × 3`. El detalle está en `backend/docs/variables-de-entorno.md`.

## API

| Método y ruta | Recibe | Responde |
|---|---|---|
| `GET /health` | — | 200 `{"status": "ok"}` |
| `POST /jobs` | `multipart/form-data`: `file` (PDF, obligatorio), `request` (texto, opcional; vacío o ausente equivale a `Resume el documento`), `ocr` (`true`/`false`, por defecto `false`) | 202 `{jobId, status, statusUrl}` si se creó un trabajo nuevo; 200 con el mismo cuerpo si ya existía uno idéntico. 400 `EMPTY_FILE` si el archivo está vacío; 400 `VALIDATION_ERROR` si falta `file` u `ocr` no es booleano |
| `GET /jobs/{jobId}` | `jobId` en formato UUID | 200 `{jobId, documentName, status, progress, result, error, createdAt, updatedAt}`. 400 `VALIDATION_ERROR` si el identificador no es un UUID; 404 `JOB_NOT_FOUND` si no existe |

Ejemplo:

```bash
curl -F file=@ley.pdf -F "request=¿Qué plazos fija?" http://127.0.0.1:8000/jobs
curl http://127.0.0.1:8000/jobs/<jobId>
```

Estados de un trabajo: `queued` → `extracting` → `analyzing` → `summarizing` → `completed`, o `failed` desde cualquiera de los intermedios.

- `progress` es `{done, total}` mientras el estado es `analyzing` o `summarizing`, y es `null` hasta que termina la primera unidad de esa etapa. En `analyzing` cuenta trozos ya anotados sobre el total; en `summarizing`, llamadas de resumen hechas sobre los lotes de la ronda en curso (el resumen reduce por rondas y `total` cambia en cada una; la última llamada informa `1/1`). Al pasar a `summarizing` el progreso del análisis se borra. En cualquier otro estado es `null`.
- `result` solo existe en `completed`: `summary`, `summaryTruncated`, `notes` (`index`, `firstPage`, `lastPage`, `text`, `unverifiedFacts`), `generatedCount`, `reusedCount`, `failedIndexes` y `scannedPages`. `summaryTruncated` es `true` cuando la respuesta final llegó al límite de `max_output_tokens` del perfil de resumen y Ollama la cortó, así que `summary` puede terminar a mitad de frase. Los trabajos completados antes de que existiera el campo lo devuelven en `false`.
- `error` solo existe en `failed` y tiene la misma forma que los errores de la API (`statusCode`, `errorCode`, `message`, `timestamp`, `path = /jobs/{jobId}`). Un fallo no previsto se guarda como `INTERNAL_ERROR` con el mensaje genérico; el detalle real va solo al log.

### Cómo se comporta la cola

- **Reinicio a mitad de un trabajo.** Al arrancar, todo trabajo en `extracting`, `analyzing` o `summarizing` vuelve a `queued` antes de que empiece el procesador. Al reprocesarse, las notas ya guardadas se reutilizan (se guardan por huella apenas se generan), así que solo se repite lo que faltaba.
- **El mismo envío dos veces.** Si llega el mismo archivo (mismo SHA-256, aunque cambie el nombre) con la misma solicitud (se ignoran los espacios de los extremos), el mismo valor de `ocr` y la misma configuración (prompts de notas y resumen, opciones de los dos perfiles y `summary_batch_chars` del perfil de resumen), se devuelve el trabajo existente con 200, en el estado en que esté. No se crea otro ni se reprocesa.
- **Otra solicitud u otra configuración.** Cambiar la solicitud, `ocr`, un prompt o un perfil de modelo crea un trabajo nuevo (202) sobre el mismo documento. Las notas que no dependen de lo cambiado se reutilizan.
- **Reenviar un trabajo fallido.** Un trabajo en `failed` no bloquea: el mismo envío crea un trabajo nuevo (202) y el fallido queda como registro.
- **Archivo nuevo.** Un SHA-256 que no se conocía crea un documento nuevo, con el nombre del archivo como nombre del documento, y su versión 1. El archivo se guarda una sola vez en `data/uploads/<sha256>.pdf`. La detección de versiones de un mismo documento todavía no existe.

La clave de idempotencia es el SHA-256 de la lista JSON `[sha256 del archivo, solicitud normalizada, ocr, prompt de notas, prompt de resumen, opciones del perfil activo, opciones del perfil de resumen, summary_batch_chars del perfil de resumen]`. Cambiar `summary_batch_chars` crea trabajos nuevos, pero las notas guardadas se reutilizan: no forma parte de su huella. La base admite un solo trabajo no fallido por clave (índice único parcial), y el alta de documento, versión y trabajo ocurre en una sola transacción.

El procesador es un hilo dentro del mismo proceso: se despierta al llegar un trabajo y, si no hay nada, revisa la cola cada 30 s por si acaso. Por eso el servicio debe correr **con un solo proceso** (sin `--workers` mayor que 1): un segundo proceso devolvería a la cola, al arrancar, los trabajos que el primero está procesando.

## Docker

Levanta tres servicios en una red privada: `ollama`, `backend` y `open-webui`. Solo Open WebUI publica un puerto, en `http://localhost:3000`.

1. Crear los dos archivos de entorno a partir de los ejemplos:

   ```bash
   cp .env.example .env                  # raíz: definir WEBUI_SECRET_KEY (obligatoria)
   cp backend/.env.example backend/.env  # opcional: sobrescribe valores de backend/config/models.toml
   ```

   `WEBUI_SECRET_KEY` debe ser un valor largo y aleatorio, por ejemplo la salida de `openssl rand -hex 32`. Sin ella, `docker compose` no arranca.

2. Levantar los servicios:

   ```bash
   docker compose up -d
   ```

   Con GPU NVIDIA (requiere que Docker vea la GPU: NVIDIA Container Toolkit en Linux, o Docker Desktop con WSL 2 en Windows):

   ```bash
   docker compose -f docker-compose.yml -f compose.gpu.yaml up -d
   ```

3. Descargar los modelos. **Es un requisito del despliegue:** la imagen de Ollama arranca sin modelos y todo análisis falla con `LLM_UNAVAILABLE` hasta que estén.

   ```bash
   docker compose exec ollama ollama pull qwen3.5:4b
   docker compose exec ollama ollama pull qwen3.5:9b
   ```

Los modelos, la base y los PDF subidos al backend (`/app/data`) y los datos de Open WebUI viven en volúmenes con nombre (`ollama-models`, `backend-data`, `open-webui-data`) y sobreviven a `docker compose down`.

En una máquina de desarrollo que ya tiene Ollama instalado con los dos modelos, `compose.local.yaml` apaga el contenedor de Ollama y apunta `backend` y `open-webui` al Ollama del equipo (`http://host.docker.internal:11434`):

```bash
docker compose -f docker-compose.yml -f compose.local.yaml up -d --build
```

Open WebUI guarda la URL de Ollama en su base la primera vez que arranca. Si el volumen `open-webui-data` se creó con la otra configuración, la URL se cambia en Admin Panel → Settings → Connections.

## Open WebUI

El backend se usa desde Open WebUI con una Function de tipo Pipe, `integrations/open_webui/document_analysis_pipe.py`, que aparece como el modelo **Analizador de documentos**. Envía el PDF adjunto a `POST /jobs`, consulta `GET /jobs/{jobId}` cada 3 s mostrando el estado (en cola, extrayendo, fragmento n/m, redactando) y responde con el resumen, más avisos si la respuesta se cortó por su longitud (`summaryTruncated`), si hubo fragmentos sin analizar o si hay datos de las notas que no aparecen literalmente en el documento.

1. Levantar el stack (en local, con el Ollama del equipo):

   ```bash
   docker compose -f docker-compose.yml -f compose.local.yaml up -d --build
   ```

2. Abrir `http://localhost:3000` y crear la cuenta de administrador (la primera cuenta registrada lo es).
3. Instalar la Pipe: Admin Panel → Functions → **+** → pegar el contenido de `integrations/open_webui/document_analysis_pipe.py`, guardar y activarla.
4. En un chat nuevo, elegir el modelo **Analizador de documentos**, adjuntar un PDF y escribir la pregunta (vacía equivale a `Resume el documento`).

Comportamiento:

- Se analiza el último archivo adjuntado en el chat; los PDF de mensajes anteriores siguen disponibles en los turnos siguientes. Si el último adjunto no es un PDF, la Pipe lo dice y no envía nada.
- Si el backend no responde mientras se espera, muestra «Reconectando con el servicio de análisis…» y sigue consultando hasta `max_wait_seconds` (1 hora). Si se agota, reenviar el mismo archivo con la misma pregunta retoma el mismo trabajo, gracias a la idempotencia de `POST /jobs`.
- Las tareas en segundo plano de Open WebUI (título, etiquetas, sugerencias) no crean trabajos.
- Ajustes (Valves, en el engranaje de la Function): `backend_url` (`http://backend:8000`), `poll_interval_seconds` (3), `max_wait_seconds` (3600), `request_timeout_seconds` (30) y `ocr` (`false`; activarlo para PDF escaneados).
- Open WebUI sigue extrayendo e indexando el PDF al subirlo, porque lo hace para cualquier archivo; la Pipe no usa ese texto. Para que además no haga la búsqueda en el documento al responder, en Admin Panel → Settings → Models → **Analizador de documentos** → Capabilities se desmarca **File Context** (dejando **File Upload** activo).

Pruebas de la Pipe (desde la raíz del repositorio):

```bash
backend/.venv/bin/python -m pytest integrations/open_webui -q
backend/.venv/bin/ruff check integrations && backend/.venv/bin/ruff format --check integrations
```

## Variables de entorno

| Variable | Archivo | Valor por defecto | Si falta |
|---|---|---|---|
| `WEBUI_SECRET_KEY` | `.env` (raíz) | Ninguno | `docker compose` no arranca |
| `APP_ACTIVE_PROFILE` | `backend/.env` | `qwen4b` (`active_profile` en `models.toml`) | Se usa el del archivo |
| `APP_SUMMARY_PROFILE` | `backend/.env` | `qwen9b` (`summary_profile` en `models.toml`) | Se usa el del archivo |
| `APP_OLLAMA__BASE_URL` | `backend/.env` | `http://127.0.0.1:11434`; en Docker, `http://ollama:11434` | Se usa el del archivo |
| `APP_STORAGE__DATABASE_FILE` | `backend/.env` | `data/app.db` | Se usa el del archivo |
| `APP_STORAGE__UPLOADS_DIR` | `backend/.env` (opcional) | `data/uploads` | Se usa el del archivo |

Prioridad: variable de entorno, después `backend/.env`, después `backend/config/models.toml`. El detalle está en `backend/docs/variables-de-entorno.md`.

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
- `backend/docs/analisis-estado-backend.md`: estado, fallas de la última iteración y pendientes priorizados.
- `backend/odd/tasks/analyze-large-documents.md`: especificación, tareas y bitácora de la funcionalidad de análisis.

## Estado

Hecho: extracción, OCR con reconstrucción de tablas, chunker, cliente Ollama, análisis jerárquico con reanudación, resumen, verificación literal de datos, base SQLite con migraciones al arrancar, `GET /health`, despliegue con Docker Compose (con variante local que usa el Ollama del equipo), la API de trabajos (`POST /jobs`, `GET /jobs/{jobId}`) con cola persistente, progreso, idempotencia y recuperación al reiniciar, y la Pipe de Open WebUI que usa esa API.

Pendiente: detección de versiones de un mismo documento y diferencias entre versiones, cancelar y listar trabajos, límite de tamaño de archivo, autenticación entre Open WebUI y el backend, Word/Excel, embeddings sobre las notas.

Nota: los PDFs de muestra y los datos generados (`data/`) no se versionan.
