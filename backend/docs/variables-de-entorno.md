# Variables de entorno

Toda variable se lee en un solo lugar: `src/shared/config/settings.py`. El resto del código nunca llama a `os.environ` (lo verifica la prueba de convenciones).

| Variable | Valor por defecto | Si falta | Para qué sirve |
|---|---|---|---|
| `APP_ACTIVE_PROFILE` | El valor de `active_profile` en `config/models.toml` | Se usa el del archivo | Elige qué perfil de modelo se usa sin editar el archivo. Debe existir en `[profiles.*]`; si no, la aplicación **no arranca** |
| `APP_SUMMARY_PROFILE` | El valor de `summary_profile` en `config/models.toml`; si tampoco está, el perfil activo | Se usa el del archivo | Perfil de modelo para el paso de **resumen** (ver abajo). Debe existir en `[profiles.*]`; si no, la aplicación **no arranca** |

## Cómo se combinan las fuentes

1. Variable de entorno (`APP_*`), que gana sobre todo lo demás.
2. Archivo `config/models.toml`.

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
| `profiles.<nombre>.model` | texto | — | Modelo de Ollama (por ejemplo `qwen2.5:3b`) |
| `profiles.<nombre>.num_ctx` | entero | Mayor que 0 | Tokens de contexto por petición |
| `profiles.<nombre>.temperature` | decimal | Entre 0 y 2 | Creatividad: menor es más fiel |
| `profiles.<nombre>.top_p` | decimal | Mayor que 0 y hasta 1 | Muestreo de tokens |
| `profiles.<nombre>.keep_alive` | texto | — | Tiempo que el modelo queda cargado (por ejemplo `30m`) |
| `profiles.<nombre>.chunk_size_chars` | entero | Mayor que 0 | Tamaño de cada trozo del documento |
| `profiles.<nombre>.chunk_overlap_chars` | entero | 0 o más, **menor** que `chunk_size_chars` | Solapamiento entre trozos |
| `profiles.<nombre>.max_output_tokens` | entero | Mayor que 0 | Máximo de tokens que genera el modelo |

El archivo no admite comentarios (regla 64). Esta tabla es su documentación.

## Qué pasa ante una configuración inválida

La aplicación falla al arrancar con `InvalidConfigurationError` y el motivo. Casos cubiertos: archivo inexistente, valor fuera de rango, solapamiento mayor o igual al tamaño del trozo, perfil activo inexistente y archivo de prompt inexistente o vacío.

## Prompts

Hay tres archivos en `config/prompts/`: `analyst_system.md` (analista general), `notes_system.md` (notas por trozo) y `summary_system.md` (resumen sobre las notas). Los tres se editan sin tocar código y se leen al arrancar.

## Prompt del sistema

Vive en `config/prompts/analyst_system.md` y se edita sin tocar código. Se lee **al arrancar**: un cambio exige reiniciar el servicio. Define el alcance del analista, las reglas obligatorias y el formato de la respuesta. La solicitud del usuario y el documento **nunca** se concatenan a este archivo: viajan en un mensaje aparte.

## Por qué el resumen puede usar otro perfil

Medición del 2026-10-16 sobre la Ley 30024 (9 trozos, notas generadas con el 3B): el resumen con `qwen2.5:3b` no respondió la pregunta, repitió fragmentos y mezcló normas; con `qwen2.5:7b` respondió con viñetas y citó páginas, pero tardó 366 s contra 145 s. Por eso `config/models.toml` fija `summary_profile = "qwen7b"` y `active_profile = "qwen3b"` (notas). Ollama descarga un modelo y carga el otro (con `OLLAMA_MAX_LOADED_MODELS=1`), unos 9 s la primera vez. Es una decisión de **archivo o variable de entorno**, no de la petición.
