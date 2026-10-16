# Referencia de funciones

Cada función se documenta aquí y no dentro del código (reglas 43, 44 y 64). Se actualiza en el mismo cambio que la función.

## `src/shared/config/settings.py`

| Función o clase | Recibe | Devuelve | Variables que consume | Falla con |
|---|---|---|---|---|
| `load_settings(config_file)` | Ruta del TOML (por defecto `config/models.toml`) | `Settings` ya validado | `APP_ACTIVE_PROFILE` y el archivo | `InvalidConfigurationError` |
| `settings_class_for(config_file)` | Ruta del TOML | Clase de configuración atada a ese archivo | — | — |
| `Settings.active` | — | `ModelProfile` del perfil activo | — | — |
| `ModelProfile` | Claves de un perfil | Perfil validado | — | `InvalidChunkOverlapError` si el solapamiento no es menor que el trozo |

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
| `create_app(settings, system_prompt, now)` | Configuración, prompt del sistema y reloj | Aplicación FastAPI con manejadores, `app.state.settings` y `app.state.system_prompt` |
| `build_default_app()` | — | Aplicación con la configuración real y el reloj UTC. Falla al arrancar si la configuración es inválida |

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
| `to_generation_options(profile)` | `ModelProfile` de la configuración | `GenerationOptions` del dominio. Copia `model`, `num_ctx`, `temperature`, `top_p`, `keep_alive` y `max_output_tokens`; deja fuera los campos de trozos, que son del `Chunker` |

## Puertos (`src/document_analysis/domain/ports.py`)

| Puerto | Método | Quién lo implementa |
|---|---|---|
| `TextExtractor` | `extract(content, filename) -> ExtractedDocument` | `PdfTextExtractor` (Word y Excel, para otra versión) |
| `OcrEngine` | `read(image_png) -> str` | `RapidOcrEngine` |
| `LLMClient` | `generate(messages, options) -> str` | Adaptador de Ollama (pendiente) |
| `Chunker` | `split(text) -> list[str]` | Adaptador de trozos (pendiente) |

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
| `DocumentWithoutTextError` | `filename` | HTTP 422, `DOCUMENT_WITHOUT_TEXT`: PDF sin texto extraíble |
| `CorruptDocumentError` | `filename` | HTTP 422, `CORRUPT_DOCUMENT`: archivo dañado o no válido |
| `EncryptedDocumentError` | `filename` | HTTP 422, `ENCRYPTED_DOCUMENT`: PDF con contraseña |

## `src/document_analysis/infrastructure/chunking/recursive_text_chunker.py`

| Función o clase | Recibe | Devuelve | Notas |
|---|---|---|---|
| `RecursiveTextChunker(chunk_size_chars, chunk_overlap_chars)` | Tamaño de trozo y solapamiento, tomados del perfil activo | Adaptador del puerto `Chunker` | Usa `RecursiveCharacterTextSplitter`: corta primero por párrafo, luego por línea, luego por espacio |
| `split(text)` | Texto completo | Lista de trozos de a lo más `chunk_size_chars` caracteres | Texto vacío devuelve lista vacía. Trozos contiguos comparten hasta `chunk_overlap_chars` caracteres |

## `src/document_analysis/infrastructure/llm/ollama_llm_client.py`

| Función o clase | Recibe | Devuelve | Falla con |
|---|---|---|---|
| `OllamaLlmClient(client)` | Un cliente con método `chat` (en producción `ollama.Client(host, timeout)`, armado con `ollama.base_url` y `ollama.timeout_seconds`) | Adaptador del puerto `LLMClient` | — |
| `generate(messages, options)` | Mensajes y `GenerationOptions` del perfil activo | Texto de la respuesta (vacío si el modelo no devuelve contenido) | `LlmUnavailableError` (503, `LLM_UNAVAILABLE`) si Ollama no responde, se agota el tiempo o devuelve error HTTP |

Mapeo de opciones: `num_ctx`, `temperature`, `top_p` y `max_output_tokens` (como `num_predict`) van en `options`; `keep_alive` y `model` van aparte. Ningún nombre de modelo está en el código.


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
| `analyze_document(document, setup, on_progress)` | Documento extraído, `AnalysisSetup` y una función opcional `(hechos, total)` | `DocumentAnalysis(name, notes, generated_count, reused_count, failed_indexes)` | `LlmUnavailableError` si Ollama cae (las notas ya guardadas se conservan); `EmptyModelAnswerError` si **todos** los trozos fallan |
| `resolve_note(chunk, setup)` | Un trozo | Nota y su origen (`reused`, `generated`, `failed`) | — |
| `fingerprint_chunk(text, notes_prompt, options)` | Texto del trozo, prompt de notas y opciones | Huella SHA-256 | — |

Reglas:
- **Reanudación y reutilización:** cada nota se guarda apenas se genera, bajo la huella del trozo, el prompt de notas, el modelo, la temperatura, `top_p` y `max_output_tokens`. Una corrida interrumpida retoma donde quedó. Si cambian el prompt, el modelo o el texto del trozo, solo esos trozos se regeneran.
- **Reintento:** una respuesta con menos de 20 caracteres alfanuméricos (por ejemplo `-` o viñetas vacías) se reintenta una vez con la temperatura subida 0.3. Si sigue mal, la nota queda como "No se pudo generar la nota de este fragmento", **no se guarda** (se reintenta en la próxima corrida) y su número aparece en `failed_indexes`.
- Las notas no dependen de la solicitud del usuario; la solicitud se aplica al resumir.

## `src/document_analysis/application/summarize_analysis.py`

| Función o clase | Recibe | Devuelve | Falla con |
|---|---|---|---|
| `SummarySetup(llm, summary_prompt, options, batch_chars)` | Dependencias y tamaño de lote en caracteres (`chunk_size_chars` del perfil) | Paquete de dependencias | — |
| `summarize_analysis(analysis, request, setup)` | Análisis ya generado y solicitud del usuario | Texto de la respuesta | `LlmUnavailableError`, `EmptyModelAnswerError` |

Cómo reduce: agrupa las notas en lotes que caben en `batch_chars` (mínimo 2 notas por lote, para garantizar que termine), resume cada lote conservando el rango de páginas y repite por niveles hasta que queda un solo lote; la última llamada es la respuesta. No relee el PDF. Omite las notas "Sin contenido relevante" y los trozos fallidos. Si no queda nada, responde `No consta en el documento` sin llamar al modelo.

## `src/document_analysis/infrastructure/storage/json_notes_store.py`

| Función o clase | Recibe | Devuelve | Notas |
|---|---|---|---|
| `JsonNotesStore(root)` | Carpeta raíz (`storage.notes_dir`) | Adaptador del puerto `NotesStore` | Un archivo JSON por nota: `<raíz>/<2 primeros caracteres>/<huella>.json` |
| `load(fingerprint)` | Huella SHA-256 en hexadecimal | `ChunkNote` o `None` | Archivo ausente, dañado o con forma incorrecta cuenta como ausente |
| `save(fingerprint, note)` | Huella y nota | Nada | Escribe a un temporal y lo renombra (atómico). Falla con `InvalidFingerprintError` si la huella no es de 64 caracteres hexadecimales (evita salir de la carpeta) |

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
