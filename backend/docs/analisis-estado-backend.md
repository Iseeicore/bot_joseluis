---
fecha: 2026-10-20
alcance: backend de análisis de documentos (FastAPI + Ollama) y Pipe de Open WebUI
rama: Iseeicore/docs-project-analysis-readme (sin commits desde 8eb4e18)
---

# Análisis del estado del backend

Documento de gestión: qué está terminado, qué falló en la última iteración (fases F2 y ajustes del resumen) y qué falta, con prioridad, dependencias y criterio de aceptación por tarea.

## 1. Resumen

- F0 (base), F1 (API de trabajos) y F2 (Pipe de Open WebUI) están implementadas y probadas. Nada de eso está en un commit todavía.
- Analizar documentos grandes funciona de punta a punta. El documento de 142 páginas se analiza completo y la respuesta ya no sale cortada.
- **El problema abierto más grave es la calidad, no la velocidad.** El resumen jerárquico deforma datos: inventa números de directiva que no están en el PDF, reformula la pregunta y pierde normas que sí están en las notas. Hasta que se resuelva, una respuesta a una pregunta de tipo listado ("¿qué normativas…?") no es confiable.
- Un documento grande tarda alrededor de 1 h 30 min la primera vez (unos 40 min de notas más 47 min de resumen). Eso supera el tiempo máximo de espera de la Pipe (1 h).

## 2. Estado verificado al 2026-10-20

| Verificación | Resultado |
|---|---|
| Pruebas del backend (`pytest -q` en `backend/`) | 384 pasan |
| Pruebas de la Pipe (`pytest integrations/open_webui`) | 32 pasan |
| `ruff check` (backend e integraciones) | Sin observaciones |
| Contenedores locales | `bot-joseluis-backend-1` y `bot-joseluis-open-webui-1` en ejecución y sanos (`compose.local.yaml`, Ollama del equipo) |
| Trabajos en `data/app.db` | 2, ambos `completed`, sin errores |
| Control de versiones | Todo el trabajo de F0, F1 y F2 está sin commit en la rama `Iseeicore/docs-project-analysis-readme`; `.atl/` no está versionado |

Trabajos registrados:

| Trabajo | Creado (UTC) | Terminado (UTC) | Observación |
|---|---|---|---|
| `1aefbb36-0ae4-4739-8241-d87d2f4aaea8` | 2026-10-18 19:59:43 | 2026-10-18 21:49:31 | Lotes de resumen de 15 000 caracteres y salida de 1024 tokens: resumen en 29,3 min, respuesta cortada a 2377 caracteres. El total incluye el tiempo que el proceso estuvo detenido |
| `deb3b04b-1f94-4e0f-88e2-ad6cfdc13826` | 2026-10-18 22:04:34 | 2026-10-18 22:51:56 | Lotes de 13 000 y salida de 2048 tokens: notas reutilizadas, resumen en unos 47 min, respuesta completa de 3676 caracteres |

## 3. Qué está hecho

| Fase | Contenido |
|---|---|
| Núcleo de análisis | Extracción de texto con marcas de página, OCR con reconstrucción de tablas, troceado (6000 caracteres con solapamiento de 400), notas por trozo con `qwen3.5:4b`, almacén de notas JSON reanudable y reutilizable por huella, verificación literal de datos de las notas, resumen jerárquico con `qwen3.5:9b` |
| F0 | Perfiles de modelo en `models.toml`, carga de `.env` con prioridad, conexión SQLite (WAL, claves foráneas) y migraciones al arrancar, `GET /health`, Docker Compose |
| F1 | `POST /jobs` y `GET /jobs/{jobId}`, cola persistente en SQLite, worker en hilo, progreso, idempotencia (hash del archivo, solicitud, OCR, prompts, opciones de perfil y tamaño de lote del resumen), recuperación de trabajos interrumpidos al reiniciar |
| F2 | Pipe `integrations/open_webui/document_analysis_pipe.py` (versión 0.2.0): envío con reintentos, consulta tolerante a cortes, control de propiedad del archivo, estados en el chat, avisos de respuesta cortada, fragmentos fallidos y datos no verificados. Variante local `compose.local.yaml` |
| Ajustes del resumen (esta iteración) | `summary_batch_chars` por perfil, validado contra el contexto al arrancar; progreso por ronda del resumen ("Redactando el resumen: parte n/m"); detección de respuesta cortada por `done_reason = length` (`summaryTruncated` en el resultado); avisos en el log por desborde de contexto; `max_output_tokens = 2048` en `qwen9b` |

## 4. Qué falló en esta iteración

Cada falla indica síntoma, causa comprobada, evidencia y estado. Las de estado **abierta** tienen su tarea en la sección 5.

### F-01. El resumen parecía colgado en "Redactando el resumen…" — mitigada

- **Síntoma:** con el PDF de 142 páginas (4,6 MB, 109 trozos), Open WebUI quedó más de 40 min en "Redactando el resumen…" sin señales de avance, y el usuario detuvo el proceso.
- **Causa:** no estaba colgado. El resumen jerárquico usaba lotes del mismo tamaño que los trozos (6000 caracteres). Con 226 191 caracteres de notas, eso daba 45 llamadas en la primera ronda y entre 60 y 90 en total, a 60–90 s cada una con `qwen3.5:9b`. Tampoco se informaba progreso durante el resumen.
- **Evidencia:** log de Ollama (`%LOCALAPPDATA%\Ollama\server.log`) con llamadas sucesivas al modelo de resumen; medición en la sección 7.
- **Corrección:** tamaño de lote propio (`summary_batch_chars`), progreso por ronda y estados de la Pipe cada 10 %.
- **Lo que queda:** sigue siendo lento (unos 47 min solo el resumen). Ver F-06 y la tarea Q-02.

### F-02. Respuesta final cortada a mitad de frase — corregida

- **Síntoma:** con lotes de 15 000 caracteres el resumen bajó a 29,3 min, pero la respuesta terminó cortada a los 2377 caracteres.
- **Causa:** `max_output_tokens = 1024` en `qwen9b`. Ollama devolvió `done_reason = "length"` y el sistema no lo detectaba.
- **Corrección:** el puerto `LLMClient.generate` devuelve `Generation(text, truncated)`, el cliente de Ollama marca `truncated` y deja un aviso en el log, el resultado expone `summaryTruncated` y la Pipe lo avisa en el chat. Se subió la salida de `qwen9b` a 2048 tokens y el lote a 13 000 caracteres para que siga entrando en `num_ctx = 8192`.
- **Verificación:** trabajo `deb3b04b…` con `summaryTruncated = false` y 3676 caracteres. No hubo avisos de desborde de contexto.
- **Costo:** el resumen pasó de 21 a 27 llamadas y de 29 a unos 47 min.

### F-03. El resumen deforma e inventa datos — abierta, crítica

- **Síntoma:** a "Quiero que me digas las normativas", la respuesta:
  - reformuló la pregunta como "normativas que establecen el proceso de acreditación";
  - partió en varias "Directivas" lo que parecen secciones de una sola (consulta externa, emergencia, hospitalización);
  - citó números de directiva que no existen en el texto del PDF;
  - omitió normas que sí están en las notas.
- **Evidencia (búsqueda literal en el texto extraído del PDF):**

  | Número citado en la respuesta | ¿Aparece en el PDF? |
  |---|---|
  | N° 333, 343, 393 | Sí |
  | N° 3-13, 3-P, 313, 37, 395 | No |

  La Ley 26842 y el D. Leg. 1161 están en las notas y en la respuesta de la corrida anterior, y faltan en la última. "SINCE" aparece 91 veces en el PDF, así que no es un invento.
- **Causa:** el reduce jerárquico funciona como el teléfono descompuesto. Cada ronda (20 → 4 → 2 → 1) reescribe el texto de la anterior, y en 3 o 4 reescrituras los datos se deforman o se pierden. Además, la verificación literal (`verify_note_facts`) solo se aplica a las notas, no a la respuesta final, así que los números inventados llegan al usuario sin aviso.
- **Factor agravante:** la propia capa de texto del PDF trae números de directiva inconsistentes, de modo que parte del ruido viene del documento.
- **Tareas:** Q-01 (verificar la respuesta final) y Q-02 (seleccionar notas por relevancia, F3).

### F-04. Detener en Open WebUI no detiene el trabajo — abierta

- **Síntoma:** el botón de detener de Open WebUI corta la Pipe, pero el trabajo sigue ocupando el modelo en el backend hasta terminar.
- **Causa:** no existe un endpoint para cancelar ni un estado `cancelled` (la restricción `CHECK` de `jobs.status` en `migrations/0001_create_documents_and_jobs.sql` no lo contempla).
- **Tarea:** O-01.

### F-05. La Pipe espera menos de lo que tarda un documento grande — abierta

- **Síntoma probable:** la primera vez, un documento como la RM 164 tarda alrededor de 1 h 30 min (109 trozos a unos 22 s, más unos 47 min de resumen). `max_wait_seconds` es 3600 (1 h), así que la Pipe deja de esperar antes del final.
- **Mitigación actual:** reenviar el mismo archivo con la misma pregunta retoma el mismo trabajo, gracias a la idempotencia.
- **Tarea:** O-04.

### F-06. El hardware limita el modelo de resumen — limitación conocida

- **Hecho:** `qwen3.5:9b` (6,3 GB) no entra completo en la RTX 3050 de 6 GB. Corre 45 % en CPU y 55 % en GPU, a 60–90 s por llamada de resumen. La VM de Docker Desktop tiene 8 GB.
- **Consecuencia:** el tiempo total depende de cuántas llamadas haga el resumen. Reducir llamadas (Q-02) rinde más que ajustar parámetros.

### F-07. Actualizar la Pipe exige volver a pegarla — operativa

- **Hecho:** Open WebUI guarda el código de la Function en su propia base. Cada cambio de `document_analysis_pipe.py` requiere pegarlo de nuevo en Admin Panel → Functions.
- **Pendiente inmediato:** pegar la versión 0.2.0 para ver el progreso del resumen y el aviso de respuesta cortada.

## 5. Pendientes

Prioridades: **P0** bloquea la confianza en las respuestas, **P1** necesario para usar el sistema en serio, **P2** mejora o deuda, **P3** alcance futuro. Tamaño estimado: **S** menos de medio día, **M** uno o dos días, **L** más de dos días.

### 5.1 Calidad de las respuestas

| ID | Prioridad | Tamaño | Tarea | Depende de | Criterio de aceptación |
|---|---|---|---|---|---|
| Q-01 | P0 | S | Verificar literalmente la respuesta final contra el texto del documento, reutilizando `verify_note_facts`, y mostrar los datos no encontrados como "datos por verificar" | — | En el PDF de la RM 164, los números 3-13, 3-P, 313, 37 y 395 aparecen marcados; los que existen (333, 343, 393) no |
| Q-02 | P0 | L | Seleccionar las notas relevantes a la pregunta antes de resumir, en vez de reducir las 109 notas | F3 (V-01) | "¿Qué normativas…?" se responde con las notas que mencionan normas, en menos llamadas que el reduce completo, e incluye la Ley 26842 y el D. Leg. 1161 |
| Q-03 | P1 | S | Ajustar el prompt de resumen para que no reformule la pregunta ni fusione o parta elementos de una lista | — | En la RM 164 la respuesta conserva el alcance de la pregunta ("normativas", no "normativas de acreditación") |
| Q-04 | P1 | M | Conjunto de preguntas de referencia con respuestas esperadas sobre la RM 164 para medir la calidad antes y después de cada cambio | — | Script que reporta datos esperados presentes, faltantes e inventados por pregunta |
| Q-05 | P2 | S | Cerrar T8 (validación real) de `backend/odd/tasks/analyze-large-documents.md` con las mediciones de la sección 7 | — | Tarea marcada con tiempos y hallazgos de calidad |

### 5.2 F3 — Versiones y preguntas de seguimiento

| ID | Prioridad | Tamaño | Tarea | Depende de | Criterio de aceptación |
|---|---|---|---|---|---|
| V-01 | P1 | M | Migración y repositorio de `version_chunks` (trozos por versión con su huella y rango de páginas) | — | Nueva migración numerada, sin editar la 0001; pruebas del repositorio |
| V-02 | P1 | M | Preguntas de seguimiento sobre un documento ya analizado sin volver a extraer ni hacer OCR | V-01 | Una segunda pregunta sobre la RM 164 no ejecuta extracción ni notas; solo selección y resumen |
| V-03 | P1 | L | Reglas de identidad de versión, en orden: hash del archivo, hash del texto, indicación explícita, similitud mayor o igual al umbral (Jaccard de 5-shingles de palabras más Levenshtein del nombre) con confirmación en el chat; si no, documento nuevo | V-01 | Pruebas por regla, incluido el caso de plantillas casi iguales de personas distintas, que no deben unirse sin confirmar |
| V-04 | P1 | M | Confirmación en el chat desde la Pipe (`__event_call__`) cuando la similitud supera el umbral | V-03 | Sí une la versión; No crea un documento nuevo; sin respuesta se toma como No |
| V-05 | P2 | S | Fijar el umbral de similitud como constante configurable y documentarlo | V-03 | Documentado en `variables-de-entorno.md` |

### 5.3 F4 — Cambios entre versiones

| ID | Prioridad | Tamaño | Tarea | Depende de | Criterio de aceptación |
|---|---|---|---|---|---|
| C-01 | P2 | M | Migración y repositorios de `version_comparisons` y `version_changes` | V-01 | Nueva migración y pruebas |
| C-02 | P2 | M | Diferencias por línea o párrafo con `difflib` (no por trozo: un documento chico es un solo trozo) | C-01 | Pruebas con cambios de una línea, de un párrafo y de una tabla |
| C-03 | P2 | M | Explicación de los cambios con el modelo, enviando solo los fragmentos cambiados y verificándola con `verify_note_facts` | C-02 | La explicación no menciona datos ausentes en los fragmentos |

### 5.4 F5 — Estabilidad de los cortes

| ID | Prioridad | Tamaño | Tarea | Depende de | Criterio de aceptación |
|---|---|---|---|---|---|
| E-01 | P2 | M | Medir cuántas huellas de trozo se conservan entre dos versiones con cambios chicos, para saber cuántas notas se reutilizan | V-01 | Informe con el porcentaje reutilizado en al menos dos pares de versiones reales |

### 5.5 API, Pipe y operación

| ID | Prioridad | Tamaño | Tarea | Depende de | Criterio de aceptación |
|---|---|---|---|---|---|
| O-01 | P1 | M | Cancelar trabajos: endpoint, estado `cancelled` (nueva migración), corte cooperativo del worker entre llamadas al modelo y llamada desde la Pipe al detener | — | Detener en Open WebUI libera el modelo después de la llamada en curso |
| O-02 | P1 | S | Límite de tamaño del archivo subido, con error de validación propio | — | Un archivo mayor al límite responde con `errorCode` y no se guarda |
| O-03 | P1 | M | Autenticación entre Open WebUI y el backend (secreto compartido por variable de entorno, sin valor por defecto) | — | Sin el secreto, `POST /jobs` y `GET /jobs/{id}` responden 401 |
| O-04 | P1 | S | Subir `max_wait_seconds` de la Pipe o reanudar la espera automáticamente en el turno siguiente | — | La RM 164 analizada desde cero termina con la respuesta en el chat |
| O-05 | P2 | S | Listar trabajos (`GET /jobs`) con filtro por estado | — | Paginado y probado |
| O-06 | P2 | S | Validar en la Pipe la forma de `progress` antes de usarlo | — | Un `progress` inválido no rompe la Pipe; se muestra el estado sin números |
| O-07 | P3 | M | Notificar a Open WebUI al terminar (adaptador `JobNotifier`), en vez de consultar | O-03 | Pendiente de verificar que los eventos posteriores al turno se guardan en el chat |
| O-08 | P3 | M | HTTPS con Caddy para un despliegue fuera del equipo local | — | — |

### 5.6 Deuda técnica comprobada

| ID | Prioridad | Tamaño | Hallazgo | Ubicación | Corrección |
|---|---|---|---|---|---|
| D-01 | P2 | S | El experimento usa el tamaño de trozo del perfil como tamaño de lote del resumen | `backend/experiments/analyze.py:78` | Usar `summary_profile.summary_batch_chars`, como `job_composition.py` |
| D-02 | P2 | S | El armado de lotes no cuenta el separador entre notas, y el mínimo de 2 notas por lote permite pasar `batch_chars` con dos notas grandes | `summarize_analysis.py:34-48` | Sumar el largo de `ITEM_SEPARATOR` y probar el caso de dos notas grandes |
| D-03 | P2 | S | Un rango de una sola página se muestra como "págs. 1-1" | `shared/constants/prompts/analysis.py:21` | Mostrar "pág. N" cuando `first_page == last_page` |
| D-04 | P2 | S | La referencia documenta `load_system_prompt`, que ya no existe | `backend/docs/referencia-de-funciones.md:74` | Reemplazar por la función vigente (`load_prompt_file`) |
| D-05 | P2 | S | `pytest` está en las dependencias de producción | `backend/requirements.txt:12` | Pasarlo a un archivo de dependencias de desarrollo y sacarlo de la imagen |
| D-06 | P2 | S | Mensajes de log escritos en línea, en inglés, a diferencia de los textos centralizados en constantes | `ollama_llm_client.py` y otros | Decidir la convención y aplicarla de forma pareja |
| D-07 | P1 | S | Nada de F0, F1 y F2 está en un commit; `.atl/` no tiene decisión de versionado | Rama actual | Commits convencionales por fase, cuando el responsable lo indique |
| D-08 | P2 | S | T10 (documentación e informe) de la especificación sin cerrar | `backend/odd/tasks/analyze-large-documents.md` | Cerrar con este documento y el README actualizado |

### 5.7 Fuera del alcance actual

- Archivos Word y Excel.
- Embeddings sobre las notas (la selección de Q-02 se diseña primero sin embeddings).
- Proxy inverso o API gateway (no hace falta mientras todo corre en la misma red de Compose).

## 6. Orden recomendado

1. **Q-01**: es barato y deja de mostrar datos inventados sin aviso.
2. **D-07**: guardar en commits lo hecho antes de empezar F3.
3. **O-04 y Q-03**: cambios chicos que mejoran la experiencia y el alcance de la respuesta.
4. **Q-04**: medir la calidad antes de tocar el resumen a fondo.
5. **F3: V-01, V-02 y Q-02**: selección por relevancia y preguntas de seguimiento. Es el cambio que ataca la causa de F-03 y del tiempo de F-01.
6. **O-01, O-02 y O-03**: cancelar, limitar el tamaño y autenticar, antes de que otra persona use el sistema.
7. **V-03 a V-05**, después **F4 (C-01 a C-03)** y **F5 (E-01)**.
8. La deuda P2 se resuelve junto con el cambio que toque cada archivo.

## 7. Datos de referencia

Documento de prueba: RM N° 164-2024-MINSA, 142 páginas, 4,6 MB, 109 trozos, 226 191 caracteres de notas.

| Configuración del resumen | Llamadas por ronda | Duración del resumen | Resultado |
|---|---|---|---|
| Lotes de 6000 (tamaño de trozo), salida de 1024 | 45 en la primera ronda; 60 a 90 estimadas en total | 1 a 1,5 h estimadas | Detenido por el usuario a los 40 min aproximadamente |
| Lotes de 15 000, salida de 1024 | 17 + 3 + 1 = 21 | 29,3 min | Cortada a 2377 caracteres |
| Lotes de 13 000, salida de 2048 | 20 + 4 + 2 + 1 = 27 | Unos 47 min | Completa, 3676 caracteres, con datos inventados (F-03) |

| Recurso | Valor |
|---|---|
| Equipo | i5-12450HX, 15,7 GB de RAM, RTX 3050 de 6 GB |
| VM de Docker Desktop | 8 GB |
| Notas (`qwen3.5:4b`) | Unos 22 s por trozo |
| Resumen (`qwen3.5:9b`, 45 % CPU / 55 % GPU) | 60 a 90 s por llamada |
| Contexto y salida | `num_ctx = 8192`; salida de 1024 (`qwen4b`) y 2048 (`qwen9b`) |
