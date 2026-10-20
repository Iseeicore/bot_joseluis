# Referencia de funciones

Cada función se documenta aquí y no dentro del código (reglas 43, 44 y 64). Se actualiza en el mismo cambio que la función.

## `src/shared/config/settings.py`

| Función o clase | Recibe | Devuelve | Variables que consume | Falla con |
|---|---|---|---|---|
| `load_settings(config_file, env_file)` | Ruta del TOML (por defecto `config/models.toml`) y del `.env` (por defecto `backend/.env`; si no existe, se ignora) | `Settings` ya validado | Variables `APP_*` (las anidadas con `__`, por ejemplo `APP_OLLAMA__BASE_URL`), el `.env` y el TOML, en ese orden de prioridad | `InvalidConfigurationError`, también si el `.env` trae una variable que no corresponde a ninguna opción |
| `settings_class_for(config_file, env_file)` | Ruta del TOML y del `.env` | Clase de configuración atada a esos archivos | — | — |
| `Settings.active` | — | `ModelProfile` del perfil activo | — | — |
| `Settings.database_file_path` | — | Ruta absoluta de la base SQLite (`storage.database_file` relativa a `backend/`; una ruta absoluta se respeta) | — | — |
| `Settings.uploads_dir_path` | — | Ruta absoluta de la carpeta de PDF recibidos (`storage.uploads_dir` relativa a `backend/`) | — | — |
| `ModelProfile` | Claves de un perfil | Perfil validado | — | `InvalidChunkOverlapError` si el solapamiento no es menor que el trozo; `SummaryBatchTooLargeError` si `summary_batch_chars` supera `(num_ctx - max_output_tokens) × CONSERVATIVE_CHARS_PER_TOKEN` |

## `src/app/error_handlers.py`

| Función | Recibe | Devuelve | Notas |
|---|---|---|---|
| `register_error_handlers(app, now)` | Aplicación FastAPI y un reloj | Nada | Registra los cuatro manejadores. El reloj entra por parámetro (regla 161) |
| `build_response(request, now, status_code, error_code, message, details)` | Datos del error | `JSONResponse` con el formato estándar | Formato: `success`, `statusCode`, `errorCode`, `message`, `timestamp`, `path`, `details` opcional |
| `to_details(error)` | `RequestValidationError` | Lista de `{path, message}` | `path` usa puntos: `body.amount` |

Códigos HTTP: `AppError` usa el suyo; validación de entrada 400; ruta inexistente 404; error no controlado 500 con mensaje genérico (el detalle real va solo al log).

## `src/app/main.py`

| Función | Recibe | Devuelve |
|---|---|---|
| `create_app(settings, system_prompt, now, lifespan, job_use_cases)` | Configuración, prompt del sistema, reloj, un ciclo de vida opcional y los casos de uso de trabajos opcionales | Aplicación FastAPI con manejadores, la ruta `GET /health`, `app.state.settings` y `app.state.system_prompt`. Con `job_use_cases`, además `POST /jobs` y `GET /jobs/{job_id}` (las pruebas inyectan casos de uso con dobles) |
| `build_default_app()` | — | Aplicación con la configuración real y el reloj UTC. **Al arrancar** (no al importar ni al construir) aplica las migraciones de `backend/migrations/`, devuelve a la cola los trabajos interrumpidos y arranca el procesador; al apagarse lo detiene. Falla al arrancar si la configuración, un prompt o una migración es inválida. Es la fábrica de `uvicorn src.app.main:build_default_app --factory` |

## `src/app/job_composition.py`

| Función | Recibe | Devuelve | Notas |
|---|---|---|---|
| `build_job_runtime(settings, now)` | Configuración y reloj | `JobRuntime(use_cases, recover, worker)` | Raíz de composición: transacciones SQLite, almacén de PDF, extractor de texto y extractor con `RapidOcrEngine` (creado una sola vez), chunker del perfil activo, almacén de notas, cliente Ollama (`base_url`, `timeout_seconds`), prompts de notas y resumen y opciones de los dos perfiles |
| `build_job_identity(settings)` | Configuración | `JobIdentity` con los prompts de notas y resumen, las opciones de los dos perfiles y `summary_batch_chars` del perfil de resumen | Lee los archivos de prompt |
| `build_job_use_cases(open_jobs, uploads, identity, now, wake_worker)` | Dependencias ya armadas | `JobUseCases(submit, get)` | Lo usan `build_job_runtime` y las pruebas de la API |
| `build_process_setup(settings, open_jobs, uploads, identity, now)` | Configuración y dependencias | `ProcessSetup` para el procesador | El resumen usa `identity.summary_batch_chars` (el `summary_batch_chars` del perfil de resumen) como tamaño de lote |

## `src/app/job_worker.py`

| Método | Qué hace |
|---|---|
| `JobWorker(process, idle_seconds)` | Procesador en segundo plano. `process` es `process_next_job` ya configurado; `idle_seconds` (30 s, `WORKER_IDLE_SECONDS`) es la espera máxima con la cola vacía |
| `start()` | Arranca un único hilo *daemon* que llama a `process` mientras devuelva `True` y, cuando devuelve `False`, duerme en un `threading.Event` hasta que lo despierten o pase `idle_seconds` |
| `wake()` | Despierta al hilo. Lo llama `submit_job` al crear un trabajo |
| `stop()` | Pide parar, despierta al hilo y espera hasta 5 s (`WORKER_STOP_TIMEOUT_SECONDS`). Si el hilo está en medio de un trabajo largo, el proceso sale igual y el trabajo se recupera en el próximo arranque |
| `is_running()` | Si el hilo está vivo |
| `process_safely()` | Una excepción que escape de `process` (por ejemplo, la base no responde) se registra en el log y el hilo sigue vivo |

Vive en `app/` y no en `infrastructure/` porque no adapta un puerto del dominio: es parte del ciclo de vida del proceso, igual que el `lifespan`.

## `src/app/database_lifespan.py` y `src/app/health_router.py`

| Función | Recibe | Devuelve | Notas |
|---|---|---|---|
| `migrate_on_startup(database_file, migrations_dir)` | Ruta de la base y carpeta de migraciones | Ciclo de vida (`lifespan`) para FastAPI | Al arrancar abre la base, aplica las migraciones pendientes y cierra la conexión; si una falla, la aplicación no arranca |
| `run_jobs_on_startup(database_file, migrations_dir, recover, worker)` | Ruta de la base, carpeta de migraciones, función de recuperación y procesador | Ciclo de vida para FastAPI | En orden: migra, llama a `recover` (trabajos interrumpidos a `queued`) y arranca el procesador. Al apagarse, detiene el procesador aunque algo haya fallado |
| `read_health()` | — | `{"status": "ok"}` con HTTP 200 (`HealthStatus.OK`) | Ruta `GET /health`, la usa el `HEALTHCHECK` de la imagen Docker |

## `src/document_analysis/application/build_analysis_messages.py`

| Función | Recibe | Devuelve | Notas |
|---|---|---|---|
| `build_analysis_messages(system_prompt, request, document_text)` | Prompt del sistema, solicitud del usuario y texto del documento | Dos mensajes: `system` con el prompt y `user` con la solicitud y el documento entre marcas | La solicitud y el documento nunca entran al mensaje `system` |
| `neutralize_tags(text)` | Texto no confiable | El mismo texto con las marcas `<documento>` y `<solicitud>` reemplazadas por `[etiqueta eliminada]` | Cubre mayúsculas y espacios (`</ DOCUMENTO >`). Evita que un documento cierre su marca para inyectar instrucciones |

## `src/shared/config/system_prompt.py`

| Función | Recibe | Devuelve | Falla con |
|---|---|---|---|
| `load_system_prompt(prompt_file)` | Ruta del archivo de prompt | Contenido sin espacios en los extremos | `InvalidConfigurationError` si falta o está vacío |

## `src/document_analysis/infrastructure/extractors/pdf_text_extractor.py`

| Función | Recibe | Devuelve | Falla con |
|---|---|---|---|
| `PdfTextExtractor(ocr_engine)` | Un `OcrEngine` opcional | El extractor. Sin motor OCR, las páginas escaneadas conservan su capa de texto | — |
| `extract(content, filename)` | Bytes del PDF y su nombre | `ExtractedDocument` con una `ExtractedPage` por página (las vacías se conservan) | `CorruptDocumentError` (vacío o no es PDF), `EncryptedDocumentError` (con contraseña), `DocumentWithoutTextError` (ninguna página tiene texto) |
| `read_page(page)` | Una página de pymupdf | `ExtractedPage` con `number` (desde 1), `text`, `scanned` y `source` | — |
| `largest_image_coverage(page)` | Una página | Fracción de la página (0 a 1) que cubre su imagen más grande | — |

**Cómo decide si una página está escaneada:** la imagen más grande cubre el 60 % o más de la página (`SCANNED_PAGE_MIN_COVERAGE`). Los logos y sellos pequeños no la marcan.

**Qué texto devuelve cada página**
- Página no escaneada: la capa de texto del PDF (`source = text_layer`).
- Página escaneada con motor OCR: el texto del OCR (`source = ocr`). Si el OCR devuelve vacío, se usa la capa de texto como respaldo.
- Página escaneada sin motor OCR: la capa de texto, y la página queda marcada `scanned = True` para que quien llame pueda avisar.

El nombre del archivo se guarda en el error para el registro, pero **no** se incluye en el mensaje al cliente.

## `src/document_analysis/infrastructure/ocr/rapid_ocr_engine.py`

| Función | Recibe | Devuelve |
|---|---|---|
| `RapidOcrEngine.read(image_png)` | Imagen PNG en bytes | Texto reconocido, una línea por renglón detectado; cadena vacía si no hay texto |

Los modelos de RapidOCR vienen dentro del paquete (`rapidocr/models`, unos 32 MB): no se descarga nada al ejecutar. Corre en CPU con `onnxruntime`.

## `src/document_analysis/application/assess_text_quality.py`

| Función | Recibe | Devuelve | Notas |
|---|---|---|---|
| `assess_text_quality(texts)` | Lista de textos (uno por página) | `TextQualityReport` con `verdict`, `letters` y `accents_per_100_letters` | Detecta una capa de texto dañada midiendo cuántos acentos conserva un texto en español |
| `stopword_share(text)` | Texto | Proporción de palabras que son palabras comunes del español (de, la, el, que...) | Sirve para saber si el texto está en español |

**Veredictos (`TextQuality`)**
- `good`: español con acentos normales (alrededor de 2.7 por cada 100 letras).
- `suspect`: parece español pero casi no tiene acentos (menos de 1 por cada 100 letras). Es la señal de un OCR antiguo que los perdió.
- `not_assessable`: menos de 1 500 letras, o el texto no parece español (un texto en inglés no se marca como sospechoso).

Umbrales en `src/shared/constants/limits/text_quality.py`. Calibrados con 4 documentos reales: capas sanas entre 2.68 y 2.85; capa dañada de la RM 164 en 0.04.

**Límite conocido:** un documento en español escrito todo en mayúsculas sin tilde de forma legítima se marcaría `suspect`. El costo sería una confirmación de OCR innecesaria.

## `src/app/generation_options.py`

| Función | Recibe | Devuelve |
|---|---|---|
| `to_generation_options(profile)` | `ModelProfile` de la configuración | `GenerationOptions` del dominio. Copia `model`, `num_ctx`, `temperature`, `top_p`, `keep_alive`, `max_output_tokens` y `think`; deja fuera los campos de trozos, que son del `Chunker`, y `summary_batch_chars`, que es del resumen (por eso cambiarlo no altera la huella de las notas) |

## Puertos (`src/document_analysis/domain/ports.py`)

| Puerto | Método | Quién lo implementa |
|---|---|---|
| `TextExtractor` | `extract(content, filename) -> ExtractedDocument` | `PdfTextExtractor` (Word y Excel, para otra versión) |
| `OcrEngine` | `read(image_png) -> str` | `RapidOcrEngine` |
| `LLMClient` | `generate(messages, options) -> Generation` (`Generation(text, truncated)`, en `domain/models.py`) | `OllamaLlmClient` |
| `Chunker` | `split(text) -> list[str]` | `RecursiveTextChunker` |
| `NotesStore` | `load(fingerprint)`, `save(fingerprint, note)` | `JsonNotesStore` |
| `UploadStore` | `save(content) -> StoredUpload`, `read(file_path) -> bytes` | `FileUploadStore` |
| `JobRepository` | Altas y consultas de documentos, versiones y trabajos (ver `persistence/`) | `SqliteJobRepository` |
| `JobTransaction` | Función sin argumentos que devuelve un administrador de contexto con un `JobRepository`: todo lo que se hace dentro es **una transacción** | `open_job_transaction(database_file)` |

## `src/shared/utils/utc_now.py`

| Función | Devuelve |
|---|---|
| `utc_now()` | Instante actual con zona UTC. Solo se usa en el punto de entrada |

## Errores propios (`src/shared/errors/`)

| Clase | Campos | Cuándo |
|---|---|---|
| `AppError` | `status_code`, `error_code`, `message`, `details` | Error de negocio que llega al cliente |
| `InvalidConfigurationError` | `reason`, `profile` | Configuración inválida al arrancar |
| `InvalidChunkOverlapError` | `overlap`, `size` | Solapamiento de trozos incoherente |
| `SummaryBatchTooLargeError` | `batch_chars`, `limit` | El lote de resumen no cabe en el contexto estimado del perfil |
| `MigrationError` | `problem` (`MigrationProblem`), `file_name` | Migración con nombre inválido, número repetido, hueco en la numeración o que falla al aplicarse |
| `DocumentWithoutTextError` | `filename` | HTTP 422, `DOCUMENT_WITHOUT_TEXT`: PDF sin texto extraíble |
| `CorruptDocumentError` | `filename` | HTTP 422, `CORRUPT_DOCUMENT`: archivo dañado o no válido |
| `EncryptedDocumentError` | `filename` | HTTP 422, `ENCRYPTED_DOCUMENT`: PDF con contraseña |
| `JobNotFoundError` | `job_id` | HTTP 404, `JOB_NOT_FOUND`: el trabajo consultado no existe |
| `EmptyUploadError` | — | HTTP 400, `EMPTY_FILE`: el archivo enviado a `POST /jobs` no tiene bytes |

## `src/document_analysis/infrastructure/chunking/recursive_text_chunker.py`

| Función o clase | Recibe | Devuelve | Notas |
|---|---|---|---|
| `RecursiveTextChunker(chunk_size_chars, chunk_overlap_chars)` | Tamaño de trozo y solapamiento, tomados del perfil activo | Adaptador del puerto `Chunker` | Usa `RecursiveCharacterTextSplitter`: corta primero por párrafo, luego por línea, luego por espacio |
| `split(text)` | Texto completo | Lista de trozos de a lo más `chunk_size_chars` caracteres | Texto vacío devuelve lista vacía. Trozos contiguos comparten hasta `chunk_overlap_chars` caracteres |

## `src/document_analysis/infrastructure/llm/ollama_llm_client.py`

| Función o clase | Recibe | Devuelve | Falla con |
|---|---|---|---|
| `OllamaLlmClient(client)` | Un cliente con método `chat` (en producción `ollama.Client(host, timeout)`, armado con `ollama.base_url` y `ollama.timeout_seconds`) | Adaptador del puerto `LLMClient` | — |
| `generate(messages, options)` | Mensajes y `GenerationOptions` del perfil activo | `Generation(text, truncated)`: texto de la respuesta (vacío si el modelo no devuelve contenido) y si Ollama la cortó por llegar a `max_output_tokens` (`done_reason = "length"`, `OllamaDoneReason.LENGTH`) | `LlmUnavailableError` (503, `LLM_UNAVAILABLE`) si Ollama no responde, se agota el tiempo o devuelve error HTTP |
| `warn_if_truncated(response, options)` | Respuesta de Ollama y `GenerationOptions` | — | Si la respuesta se cortó por el límite de salida, registra un aviso en el log con el modelo, `eval_count` y `num_predict` (también como campos del registro). Se registra en todas las llamadas: notas, rondas intermedias del resumen y respuesta final. No registra el contenido de la conversación |
| `warn_if_context_is_full(response, options)` | Respuesta de Ollama y `GenerationOptions` | — | Si `prompt_eval_count` (+ `eval_count` si viene) llega a `num_ctx`, registra un aviso en el log con el modelo, `prompt_eval_count`, `eval_count` y `num_ctx` (también como campos del registro). Ollama recorta en silencio un prompt más largo que el contexto; este aviso es la única señal. No registra el contenido de la conversación |

Mapeo de opciones: `num_ctx`, `temperature`, `top_p` y `max_output_tokens` (como `num_predict`) van en `options`; `keep_alive`, `think` y `model` van aparte. Ningún nombre de modelo está en el código.


## `src/document_analysis/application/chunk_document.py`

| Función | Recibe | Devuelve | Notas |
|---|---|---|---|
| `build_paged_text(document)` | `ExtractedDocument` | `PagedText`: texto con una marca `[Página N \| origen]` por página y la posición donde empieza cada página | Las posiciones se calculan al armar el texto, no leyendo marcas del contenido: una marca falsa dentro de una página no altera las páginas citadas |
| `chunk_document(document, chunker)` | Documento y puerto `Chunker` | Lista de `DocumentChunk(index, text, first_page, last_page)` en orden | Cada trozo se ubica buscando hacia adelante desde el trozo anterior, así los trozos repetidos no se confunden |

## `src/document_analysis/application/verify_note_facts.py`

| Función | Recibe | Devuelve | Notas |
|---|---|---|---|
| `find_unverified_facts(note, chunk)` | Texto de la nota y texto del trozo | Tupla de hechos de la nota que **no** aparecen literalmente en el trozo, sin repetidos y en orden de aparición | Revisa dos clases de hecho: tokens con dígitos (códigos, cifras, fechas; 2 o más caracteres) y palabras en MAYÚSCULAS de 4 o más letras. Ignora espacios, puntuación, tildes y mayúsculas al comparar |

Límite conocido: si el documento dice "dos mil veintitrés" y el modelo escribe "2023", se marca como no verificado (falsa alarma). Es una alerta, no un bloqueo.

## `src/document_analysis/application/analyze_document.py`

| Función o clase | Recibe | Devuelve | Falla con |
|---|---|---|---|
| `AnalysisSetup(chunker, llm, store, notes_prompt, options)` | Puertos y configuración ya cargada | Paquete de dependencias | — |
| `analyze_document(document, setup, on_progress)` | Documento extraído, `AnalysisSetup` y una función opcional `(hechos, total)` (`ProgressCallback` de `application/progress.py`; por omisión `ignore_progress`) | `DocumentAnalysis(name, notes, generated_count, reused_count, failed_indexes)` | `LlmUnavailableError` si Ollama cae (las notas ya guardadas se conservan); `EmptyModelAnswerError` si **todos** los trozos fallan |
| `resolve_note(chunk, setup)` | Un trozo | Nota y su origen (`reused`, `generated`, `failed`) | — |
| `fingerprint_chunk(text, notes_prompt, options)` | Texto del trozo, prompt de notas y opciones | Huella SHA-256 | — |

Reglas:
- **Reanudación y reutilización:** cada nota se guarda apenas se genera, bajo la huella del trozo, el prompt de notas, el modelo, la temperatura, `top_p`, `max_output_tokens` y el modo de razonamiento (`think`). Una corrida interrumpida retoma donde quedó. Si cambian el prompt, el modelo, `think` o el texto del trozo, solo esos trozos se regeneran.
- **Reintento:** una respuesta con menos de 20 caracteres alfanuméricos (por ejemplo `-` o viñetas vacías) se reintenta una vez con la temperatura subida 0.3. Si sigue mal, la nota queda como "No se pudo generar la nota de este fragmento", **no se guarda** (se reintenta en la próxima corrida) y su número aparece en `failed_indexes`.
- Las notas no dependen de la solicitud del usuario; la solicitud se aplica al resumir.
- **Nota cortada:** si Ollama corta una nota por `max_output_tokens`, solo queda el aviso del cliente en el log; la nota se usa y se guarda igual que cualquier otra.

## `src/document_analysis/application/summarize_analysis.py`

| Función o clase | Recibe | Devuelve | Falla con |
|---|---|---|---|
| `SummarySetup(llm, summary_prompt, options, batch_chars)` | Dependencias y tamaño de lote en caracteres (`summary_batch_chars` del perfil de resumen) | Paquete de dependencias | — |
| `summarize_analysis(analysis, request, setup, on_progress)` | Análisis ya generado, solicitud del usuario y una función opcional `(hechos, total)` | `Generation(text, truncated)`: texto de la respuesta y si la **respuesta final** se cortó por `max_output_tokens` | `LlmUnavailableError`, `EmptyModelAnswerError` |

Cómo reduce: agrupa las notas en lotes que caben en `batch_chars` (mínimo 2 notas por lote, para garantizar que termine), resume cada lote conservando el rango de páginas y repite por niveles hasta que queda un solo lote; la última llamada es la respuesta. Solo el corte de esa última llamada llega a `truncated`; un resumen intermedio cortado deja el aviso del cliente en el log y se sigue usando. Tras cada llamada informa `(hechos, total)`, donde `total` es la cantidad de lotes de la ronda en curso; la llamada final informa `1/1`. No relee el PDF. Omite las notas "Sin contenido relevante" y los trozos fallidos. Si no queda nada, responde `No consta en el documento` sin llamar al modelo.

## `src/document_analysis/infrastructure/storage/json_notes_store.py`

| Función o clase | Recibe | Devuelve | Notas |
|---|---|---|---|
| `JsonNotesStore(root)` | Carpeta raíz (`storage.notes_dir`) | Adaptador del puerto `NotesStore` | Un archivo JSON por nota: `<raíz>/<2 primeros caracteres>/<huella>.json` |
| `load(fingerprint)` | Huella SHA-256 en hexadecimal | `ChunkNote` o `None` | Archivo ausente, dañado o con forma incorrecta cuenta como ausente |
| `save(fingerprint, note)` | Huella y nota | Nada | Escribe a un temporal y lo renombra (atómico). Falla con `InvalidFingerprintError` si la huella no es de 64 caracteres hexadecimales (evita salir de la carpeta) |

## `src/document_analysis/infrastructure/persistence/`

| Función | Recibe | Devuelve | Notas |
|---|---|---|---|
| `open_database(database_file)` | Ruta del archivo SQLite | Conexión `sqlite3` | Crea la carpeta si falta y activa `journal_mode = WAL` y `foreign_keys = ON` |
| `apply_migrations(connection, migrations_dir)` | Conexión y carpeta de migraciones | Tupla con las versiones aplicadas en esta corrida (vacía si no había pendientes) | Lee la versión de `PRAGMA user_version` y aplica solo las mayores, en orden |
| `discover_migrations(migrations_dir)` | Carpeta de migraciones | Migraciones ordenadas por número | Solo mira archivos `.sql`. Falla con `MigrationError` antes de aplicar nada si un nombre no cumple `NNNN_nombre.sql`, si un número se repite o si hay un hueco (la primera debe ser `0001`) |
| `apply_migration(connection, migration)` | Conexión y una migración | Nada | Ejecuta el archivo y sube `user_version` dentro de **una sola transacción**. Si falla, revierte todo y lanza `MigrationError` (`EXECUTION_FAILED`) con el error de SQLite como causa |

| `open_job_transaction(database_file)` | Ruta de la base | `JobTransaction` | Cada uso abre su propia conexión (las conexiones de `sqlite3` no se comparten entre hilos), empieza con `BEGIN IMMEDIATE` (toma el candado de escritura al inicio, así dos envíos simultáneos no se pisan), confirma al salir y revierte si algo falla |
| `SqliteJobRepository(connection)` | Una conexión ya dentro de la transacción | Adaptador del puerto `JobRepository` | Todo SQL va parametrizado. Resultados y errores se guardan como JSON con claves camelCase |

Métodos de `JobRepository`:

| Método | Qué hace |
|---|---|
| `find_version_id_by_sha(file_sha256)` | Identificador de la versión con ese contenido, o `None` |
| `add_document_version(version)` | Inserta el documento y su versión (las dos filas en la misma transacción) |
| `find_unfailed_job_by_key(idempotency_key)` | El trabajo no fallido con esa clave, o `None` |
| `add_job(job)` | Inserta un trabajo |
| `get_job(job_id)` | El trabajo con el nombre del documento y la ruta del PDF, o `None` |
| `find_oldest_queued_job()` | El trabajo `queued` más antiguo (por `created_at` y orden de alta), o `None` |
| `set_status(job_id, status, timestamp)` | Cambia el estado y borra el progreso |
| `set_progress(job_id, progress, timestamp)` | Guarda `{done, total}` |
| `complete_job(job_id, result, timestamp)` | Estado `completed` y `result_json` |
| `fail_job(job_id, error, timestamp)` | Estado `failed` y `error_json` |
| `requeue_jobs(statuses, timestamp)` | Pasa a `queued` los trabajos en esos estados, borra su progreso y devuelve cuántos cambió |

Tablas de `0001_create_documents_and_jobs.sql`: `documents` (nombre visible), `document_versions` (número de versión, nombre de archivo, `file_sha256` único y `file_path` relativo a `storage.uploads_dir`) y `jobs` (solicitud, `ocr`, clave de idempotencia, estado con `CHECK` sobre los valores de `JobStatus`, progreso, resultado y error en JSON, fechas ISO 8601 en UTC). Índice único parcial sobre `jobs(idempotency_key)` para los trabajos no fallidos e índice sobre `jobs(status, created_at)` para la cola.

Reglas de las migraciones: nombre `NNNN_nombre_en_minusculas.sql` en `backend/migrations/`; una migración ya aplicada **nunca se edita**, se crea otra; el archivo no abre ni cierra transacciones (`BEGIN`/`COMMIT`), de eso se encarga el ejecutor.

## Prompts de notas y resumen

`build_notes_messages(notes_prompt, chunk_text)` arma el mensaje `system` (archivo) y el `user` con `<fragmento>…</fragmento>`. `build_summary_messages(summary_prompt, request, notes_text)` arma `system` y `user` con `<solicitud>` y `<notas>`. En ambos, las marcas `documento`, `solicitud`, `fragmento` y `notas` que vengan en datos no confiables se reemplazan por `[etiqueta eliminada]`.

## `src/document_analysis/domain/ocr_layout.py` y `rapid_ocr_engine.py`

| Función o clase | Recibe | Devuelve | Notas |
|---|---|---|---|
| `OcrFragment(text, x_center, y_center, width, height)` | Un fragmento leído por el OCR: posición del centro como fracción de la página y tamaño en píxeles | — | Lo arma el adaptador `RapidOcrEngine` a partir de las cajas del OCR |
| `layout_ocr_text(fragments)` | Fragmentos de una página, en el orden del motor | Texto de la página | Sin encabezados de columna, devuelve los fragmentos tal cual, uno por línea (nada cambia). Con encabezados, devuelve `[Columnas: a \| b \| …]` y una línea por fila: `etiqueta -> columna; columna` |
| `find_headers(fragments)` | Fragmentos | Encabezados de columna ordenados de izquierda a derecha | Un encabezado seguro es texto rotado (alto mayor a 1.8 veces el ancho, 3 o más letras). Hacen falta al menos 3 en posiciones horizontales distintas; así un sello vertical en el margen no activa el modo tabla. Los encabezados cortos (`ENF`, `UCI`) se reconocen por tener el mismo ancho de línea y estar en la misma franja |
| `render_row(row, headers, tolerance)` | Fila y encabezados | Texto de la fila | Una celda de 2 o menos caracteres (la "X") se asocia a la columna más cercana si está a menos de la mitad de la separación típica entre columnas; si no, queda como texto |

Verificado con la página 60 de la RM 164 contra la imagen: las asociaciones hechas fueron correctas (Notas de Enfermería, Kárdex, Hoja de Control, Gráfica de Signos, Hojas de Balance, Reporte Operatorio, Hoja de Anestesia, Historia Perinatal, Obstetricia). Límites conocidos:
- Si el OCR no lee el encabezado de una columna (en esa página MC, CD, TM, BL, QF), las "X" bajo ella quedan como "X" sueltas, sin asociar.
- El OCR a veces acorta el encabezado (`M` por `MC`, `N` por `NU`).
- Una etiqueta de varias líneas se parte en varias filas; las "X" quedan en la última línea.

## `src/document_analysis/infrastructure/storage/file_upload_store.py`

| Función o clase | Recibe | Devuelve | Notas |
|---|---|---|---|
| `FileUploadStore(root)` | Carpeta (`storage.uploads_dir`) | Adaptador del puerto `UploadStore` | — |
| `save(content)` | Flujo binario del archivo subido | `StoredUpload(sha256, file_path, size_bytes)` con `file_path = <sha256>.pdf` | Lee por bloques de 1 MB calculando el SHA-256 mientras copia a un temporal en la misma carpeta y luego lo renombra (atómico). Si ya existía un archivo con ese contenido, descarta el temporal y no lo reescribe. Si la lectura falla, no deja archivos a medias. Falla con `EmptyUploadError` si no llegó ningún byte |
| `read(file_path)` | Ruta relativa devuelta por `save` | Bytes del PDF | — |

## Trabajos: casos de uso (`src/document_analysis/application/`)

| Función o clase | Recibe | Devuelve | Falla con |
|---|---|---|---|
| `normalize_request(request)` | Solicitud del usuario o `None` | La solicitud sin espacios en los extremos; si queda vacía, `Resume el documento` (`DEFAULT_JOB_REQUEST_TEXT`) | — |
| `job_idempotency_key(file_sha256, request, ocr, identity)` | SHA-256 del archivo, solicitud ya normalizada, `ocr` y `JobIdentity(notes_prompt, summary_prompt, notes_options, summary_options, summary_batch_chars)` | SHA-256 de la lista JSON `[file_sha256, request, ocr, notes_prompt, summary_prompt, campos de notes_options, campos de summary_options, summary_batch_chars]` | — |
| `submit_job(submission, setup)` | `JobSubmission(content, file_name, request, ocr)` y `SubmitSetup(open_jobs, uploads, identity, now, wake_worker)` | `SubmittedJob(job_id, status, created)` | `EmptyUploadError` |
| `get_job(job_id, open_jobs)` | Identificador | `Job` | `JobNotFoundError` |
| `recover_interrupted_jobs(open_jobs, now)` | Transacción y reloj | Cuántos trabajos volvieron a `queued` | — |
| `process_next_job(setup)` | `ProcessSetup(open_jobs, uploads, text_extractor, ocr_extractor, analysis, summary, now)` | `True` si procesó un trabajo (terminara bien o mal), `False` si la cola estaba vacía | No falla por el trabajo: el error queda guardado en él |

**`submit_job`**: guarda el PDF, normaliza la solicitud y calcula la clave; después, en **una sola transacción**, busca la versión por SHA-256 (si no existe, crea un documento nuevo con el nombre del archivo y su versión 1) y devuelve el trabajo no fallido con la misma clave si existe (`created = False`) o crea uno en `queued` (`created = True`). Solo al crear despierta al procesador.

**`process_next_job`**: toma el trabajo `queued` más antiguo y lo pasa a `extracting` en la misma transacción; extrae el texto del PDF guardado (con OCR solo si el trabajo lo pidió); pasa a `analyzing` y guarda el progreso tras cada trozo; pasa a `summarizing` (el cambio de estado borra el progreso del análisis) y resume con la solicitud del trabajo, guardando el progreso tras cada llamada de resumen; termina en `completed` con el resultado. Cada cambio de estado es una transacción corta: nada queda bloqueado mientras el modelo trabaja.
- Si falla con un `AppError` (PDF dañado, Ollama caído, respuesta vacía), el trabajo queda en `failed` con el error en el formato de la API (`statusCode`, `errorCode`, `message`, `timestamp`, `path = /jobs/{id}`) y se registra un aviso en el log.
- Si falla con cualquier otra excepción, se registra con la traza completa en el log y el trabajo guarda solo el error genérico `INTERNAL_ERROR` («Error interno del servidor.»), nunca el mensaje crudo.

`Job.visible_progress` devuelve el progreso solo si el estado es `analyzing` o `summarizing` (`PROGRESS_JOB_STATUSES`).

## API de trabajos (`src/document_analysis/api/`)

| Función | Ruta | Notas |
|---|---|---|
| `submit_job_endpoint(file, response, use_cases, request, ocr)` | `POST /jobs` | Arma un `JobSubmission` con el archivo, su nombre (o `documento.pdf` si no trae), la solicitud y `ocr`, y responde 202 o 200 según `created` |
| `read_job_endpoint(job_id, use_cases)` | `GET /jobs/{job_id}` | `job_id` se valida como UUID antes de consultar (si no, 400 `VALIDATION_ERROR` por el manejador global) |
| `to_job_response(job)` | — | Convierte un `Job` en `JobResponse` (camelCase) |
| `read_job_use_cases(request)` | — | Dependencia de FastAPI: lee `JobUseCases` de `app.state` |

DTO en `job_schemas.py`: `SubmitJobResponse`, `JobResponse` y `JobProgressResponse`. El resultado (`JobResult`, `JobNote`) vive en `src/shared/types/job_result.py` porque es a la vez lo que se guarda y lo que se responde. `JobResult.summary_truncated` (`summaryTruncated`) vale `false` por omisión: el `result_json` de los trabajos completados antes de que existiera el campo se lee sin error y lo devuelve en `false`.
