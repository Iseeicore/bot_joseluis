# Variables de entorno

Toda variable se lee en un solo lugar: `src/shared/config/settings.py`. El resto del código nunca llama a `os.environ` (lo verifica la prueba de convenciones).

| Variable | Valor por defecto | Si falta | Para qué sirve |
|---|---|---|---|
| `APP_ACTIVE_PROFILE` | El valor de `active_profile` en `config/models.toml` | Se usa el del archivo | Elige qué perfil de modelo se usa sin editar el archivo. Debe existir en `[profiles.*]`; si no, la aplicación **no arranca** |
| `APP_SUMMARY_PROFILE` | El valor de `summary_profile` en `config/models.toml`; si tampoco está, el perfil activo | Se usa el del archivo | Perfil de modelo para el paso de **resumen** (ver abajo). Debe existir en `[profiles.*]`; si no, la aplicación **no arranca** |
| `APP_OLLAMA__BASE_URL` | `http://127.0.0.1:11434` (`ollama.base_url`) | Se usa el del archivo | Dirección del servidor Ollama. En Docker Compose se fija a `http://ollama:11434` |
| `APP_STORAGE__DATABASE_FILE` | `data/app.db` (`storage.database_file`) | Se usa el del archivo | Archivo SQLite, relativo a `backend/` (una ruta absoluta se respeta). Se crea al arrancar junto con su carpeta |

Cualquier clave del TOML se puede sobrescribir igual: prefijo `APP_`, la ruta en mayúsculas y `__` entre niveles. Por ejemplo `APP_OLLAMA__TIMEOUT_SECONDS=900`, `APP_STORAGE__UPLOADS_DIR=/datos/pdf` o `APP_PROFILES__QWEN4B__THINK=true`. `backend/.env.example` lista las de la tabla, que son las que cambian entre una máquina local y Docker.

## Cómo se combinan las fuentes

1. Variable de entorno (`APP_*`), que gana sobre todo lo demás.
2. Archivo `backend/.env` (opcional; si no existe, se ignora). Se crea copiando `backend/.env.example`.
3. Archivo `config/models.toml`.

Una variable sobrescribe solo su campo: con `APP_OLLAMA__BASE_URL` definida, `ollama.timeout_seconds` sigue saliendo del TOML.

`backend/.env` solo admite variables `APP_*` que existan: una variable desconocida en el primer nivel (por ejemplo `APP_ACTIVE_PROFIL` o `WEBUI_SECRET_KEY`) hace que la aplicación **no arranque**. Una clave anidada desconocida (`APP_OLLAMA__NOPE`) se ignora sin aviso.

En Docker Compose el contenedor no lee `backend/.env` como archivo: Compose lo inyecta como variables de entorno (`env_file`, opcional) y `APP_OLLAMA__BASE_URL` del bloque `environment` gana sobre el valor del archivo.

## Variables de la raíz del repositorio (Docker Compose)

| Variable | Valor por defecto | Si falta | Para qué sirve |
|---|---|---|---|
| `WEBUI_SECRET_KEY` | Ninguno | `docker compose` **no arranca** (ni siquiera `docker compose config`) | Clave con la que Open WebUI firma las sesiones. Va en `.env` de la raíz (copia de `.env.example`), nunca en el repositorio |

## Archivo `config/models.toml`

| Clave | Tipo | Regla | Qué controla |
|---|---|---|---|
| `active_profile` | texto | Debe existir en `profiles` | Perfil de modelo activo |
| `summary_profile` | texto, opcional | Debe existir en `profiles` si se define | Perfil del modelo que resume las notas. Si falta, se usa `active_profile` |
| `ollama.base_url` | texto | — | Dirección del servidor Ollama |
| `ollama.timeout_seconds` | entero | Mayor que 0 | Tiempo máximo de espera a Ollama |
| `prompts.system_file` | ruta | Debe existir y no estar vacío; relativa a `backend/` | Archivo con las reglas del analista (prompt del sistema) |
| `prompts.notes_file` | ruta | Debe existir y no estar vacío; relativa a `backend/` | Reglas para generar las notas de cada trozo del documento |
| `prompts.summary_file` | ruta | Debe existir y no estar vacío; relativa a `backend/` | Reglas para resumir las notas según la solicitud del usuario |
| `storage.notes_dir` | ruta | Relativa a `backend/` | Carpeta donde se guardan las notas por trozo (`data/notes`, ignorada por git) |
| `storage.database_file` | ruta | Relativa a `backend/` | Base SQLite (`data/app.db`, ignorada por git). Las migraciones de `backend/migrations/` se aplican al arrancar |
| `storage.uploads_dir` | ruta | Relativa a `backend/` (una ruta absoluta se respeta) | Carpeta donde se guardan los PDF recibidos por `POST /jobs`, uno por contenido: `<sha256>.pdf` (`data/uploads`, ignorada por git). Se crea con el primer envío. La base guarda la ruta relativa a esta carpeta, así que se puede mover la carpeta junto con sus archivos sin romper los trabajos |
| `profiles.<nombre>.model` | texto | — | Modelo de Ollama (por ejemplo `qwen3.5:4b`) |
| `profiles.<nombre>.num_ctx` | entero | Mayor que 0 | Tokens de contexto por petición |
| `profiles.<nombre>.temperature` | decimal | Entre 0 y 2 | Creatividad: menor es más fiel |
| `profiles.<nombre>.top_p` | decimal | Mayor que 0 y hasta 1 | Muestreo de tokens |
| `profiles.<nombre>.keep_alive` | texto | — | Tiempo que el modelo queda cargado (por ejemplo `30m`) |
| `profiles.<nombre>.chunk_size_chars` | entero | Mayor que 0 | Tamaño de cada trozo del documento |
| `profiles.<nombre>.chunk_overlap_chars` | entero | 0 o más, **menor** que `chunk_size_chars` | Solapamiento entre trozos |
| `profiles.<nombre>.summary_batch_chars` | entero | Mayor que 0 y como máximo `(num_ctx - max_output_tokens) × 3` (3 caracteres por token, estimación conservadora para texto legal en español) | Caracteres de notas que entran en cada llamada de resumen. Solo se usa el del perfil de resumen. `qwen9b` (perfil de resumen) usa 13000 con `num_ctx = 8192` y `max_output_tokens = 2048`: 13000 / 3 ≈ 4334 tokens de notas + unos 570 del prompt y la solicitud + 2048 de salida ≈ 6952, dentro de 8192; incluso a 2,5 caracteres por token da ≈ 7818. `qwen4b` conserva 15000 con `max_output_tokens = 1024`. Más grande, menos llamadas; si no cabe en el contexto, Ollama recorta el prompt en silencio (queda un aviso en el log). Cambiarlo cambia la clave de idempotencia de los trabajos nuevos, pero no invalida las notas guardadas |
| `profiles.<nombre>.max_output_tokens` | entero | Mayor que 0 | Máximo de tokens que genera el modelo (`num_predict` de Ollama). Al llegar al límite, Ollama corta la respuesta sin error (`done_reason = "length"`): queda un aviso en el log y, si era la respuesta final del resumen, el resultado del trabajo trae `summaryTruncated = true`. `qwen4b` usa 1024 y `qwen9b` 2048. Forma parte de la huella de las notas: cambiarlo en el perfil activo invalida las notas guardadas; en el perfil de resumen solo cambia la clave de idempotencia de los trabajos nuevos |
| `profiles.<nombre>.think` | booleano | Obligatorio | Modo de razonamiento de Ollama (`think`). Los perfiles lo dejan en `false`: `qwen3.5` lo trae encendido por defecto y gasta tokens de salida pensando antes de responder. Cambiarlo invalida las notas guardadas |

El archivo no admite comentarios (regla 64). Esta tabla es su documentación.

## Qué pasa ante una configuración inválida

La aplicación falla al arrancar con `InvalidConfigurationError` y el motivo. Casos cubiertos: archivo inexistente, valor fuera de rango, clave obligatoria ausente (por ejemplo `think`), solapamiento mayor o igual al tamaño del trozo, `summary_batch_chars` que no cabe en el contexto del perfil, perfil activo inexistente, variable desconocida en `backend/.env` y archivo de prompt inexistente o vacío. Una migración inválida o que falla detiene el arranque con `MigrationError`.

## Prompts

Hay tres archivos en `config/prompts/`: `analyst_system.md` (analista general), `notes_system.md` (notas por trozo) y `summary_system.md` (resumen sobre las notas). Los tres se editan sin tocar código y se leen al arrancar.

## Prompt del sistema

Vive en `config/prompts/analyst_system.md` y se edita sin tocar código. Se lee **al arrancar**: un cambio exige reiniciar el servicio. Define el alcance del analista, las reglas obligatorias y el formato de la respuesta. La solicitud del usuario y el documento **nunca** se concatenan a este archivo: viajan en un mensaje aparte.

## Por qué el resumen puede usar otro perfil

Medición del 2026-10-16 sobre la Ley 30024 (9 trozos, notas generadas con el 3B): el resumen con `qwen2.5:3b` no respondió la pregunta, repitió fragmentos y mezcló normas; con `qwen2.5:7b` respondió con viñetas y citó páginas, pero tardó 366 s contra 145 s. Por eso el resumen usa el modelo más grande. Hoy `config/models.toml` fija `active_profile = "qwen4b"` (`qwen3.5:4b`, notas) y `summary_profile = "qwen9b"` (`qwen3.5:9b`, resumen), con `think = false`; la medición con `qwen3.5` todavía no se repitió. Ollama descarga un modelo y carga el otro (con `OLLAMA_MAX_LOADED_MODELS=1`), unos 9 s la primera vez. Es una decisión de **archivo o variable de entorno**, no de la petición.
