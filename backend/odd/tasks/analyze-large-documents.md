# analyze-large-documents
Objetivo: analizar documentos grandes (RM 164, 142 págs.) con notas por trozo citadas por página, guardadas en disco, reanudables y verificadas.
Rama: ninguna (el directorio no es un repositorio git; no se crean repos ni ramas sin consultar). Estrategia de entrega: sin commits. Ejecutor de pruebas: `.venv/bin/python -m pytest`.

## Specs
- S1. Los prompts de notas y de resumen son archivos editables aparte (decisión del usuario: "archivo editable aparte"), referenciados desde `models.toml`; el directorio de almacenamiento sale de la configuración. Nada hardcodeado; falla al arrancar si falta o está vacío.
- S2. Dominio: `ChunkNote` (trozo, páginas, texto, hechos no verificados), `DocumentAnalysis`, puerto `NotesStore`.
- S3. El texto del documento lleva marcas de página y cada trozo conoce su rango de páginas exacto (orden estable, sin ambigüedad por trozos repetidos).
- S4. Verificación literal sin modelo: códigos, cifras, fechas y nombres en mayúsculas de una nota deben existir en su trozo; los que no, se marcan como no verificados (caso real: "REPRESENTANTE LEGAL: J. PEREZ" inventado por el 3B).
- S5. Almacén JSON en disco, escritura atómica; un archivo dañado cuenta como ausente.
- S6. `analyze_document`: notas por trozo en texto libre con viñetas fijas ("texto libre con viñetas fijas"); guarda cada nota al generarla, reanuda donde quedó, reutiliza notas de trozos sin cambios (huella de contenido + prompt + modelo), reporta progreso.
- S7. Resumen bajo demanda: reduce jerárquico sobre las notas, por lotes que caben en el contexto; nunca relee el PDF.
- S8. Validación real contra documentos reales, midiendo tiempos y calidad, incluida una interrupción y reanudación.
- S9. Mejora 1 (después del núcleo): reconstruir tablas del OCR con posiciones (asociar cada "X" a su columna).
- S10. Documentación en español actualizada en el mismo cambio; informe final de mejoras, retrocesos y problemas.
- Supuesto: el análisis no depende de la solicitud del usuario (las notas son reutilizables para resúmenes y preguntas); la solicitud se aplica en el resumen.
- Fuera de alcance de este documento: endpoints HTTP, procesos en segundo plano, Pipe de Open WebUI, Word/Excel, embeddings.

## Tasks
- [x] T1 (S1) Configuración de prompts y almacenamiento — inline — RED: error de colección por `load_prompt_file` inexistente; GREEN: 119 pruebas — sin commit (no es repo)
- [x] T2 (S2) Modelos y puerto — inline — cubierto por T3/T5/T6; 128 pruebas
- [x] T3 (S3) Texto con marcas y rangos de página — inline — RED: error de colección; GREEN: 128 pruebas (incluye marca de página falsa dentro del texto)
- [x] T4 (S4) Verificación literal — inline — GREEN 7 pruebas; RED no observado por separado (prueba y código juntos); mutación (no marcar nada) hizo fallar 3 pruebas
- [x] T5 (S5) Almacén JSON — inline — RED: módulo inexistente; la prueba de convenciones atrapó un `raise TypeError` y se rehízo con modelo pydantic estricto; 152 pruebas
- [x] T6 (S6) Caso de uso analyze_document — inline — RED: error de colección; GREEN 167 pruebas; 2 fallos iniciales eran errores de mis pruebas (aritmética de trozos y palabra en mayúsculas); mutaciones (ignorar almacén) hicieron fallar 3 pruebas
- [x] T7 (S7) Resumen jerárquico — inline — RED: error de colección; GREEN 175 pruebas. Añadido `summary_profile` (RED: 4 pruebas fallaban) por evidencia de T8: 3B resume mal, 7B bien
- [ ] T8 (S8) Validación real — inline
- [x] T9 (S9) Reconstrucción de tablas — inline — pruebas sintéticas + OCR real; validado contra la imagen de la pág. 60 de la RM 164; 203 pruebas
- [ ] T10 (S10) Documentación e informe — inline
Ruta: todas inline (sin razón de escritor delegado; trabajo secuencial con archivos compartidos).

## Log
- L1 (2026-10-16, usuario): "dale, implementa ordenemos el plan y armemos la mejorar a hacer los paso a paso para poder ir avanzando sin que te tenga que revisar y lo vallas pasando y cada pasada de implementaciona hagas un test y puedas analizalro y al final me des un analicis de mejora o si se retrocedio o si hubo algun problema"
- L2 (2026-10-16, usuario): "texto libre con viñetas fijas, y medimos dale analizalo"
- L3 (2026-10-16, usuario): "1,2 y 5 creo yo que serian las mejoras respectivas de gran impacto como lo ves ?" (acordado: 1 y 5 sí; 5 dividido en reanudar ahora e incremental después; 2 condicionada a medición con 7B)
- L4 medición previa (muestra de 6 trozos de 104, RM 164 OCR): formato rígido en 3B respondió "Ninguno" en 5/6; viñetas libres funcionan; el 3B inventó un nombre; el reduce del 3B es malo. Map ~28 s/trozo (3B) y ~58 s (7B).
- L5 hallazgos de T8 (ley 30024, 9 trozos, 3B): la cláusula de escape del prompt de notas ("Sin contenido relevante") hizo que el 3B descartara una ley entera (retroceso mío) -> cláusula eliminada. El 3B degeneró en 2 de 9 trozos (notas `-`) -> reintento con más temperatura + nota "no legible" no cacheada + `failed_indexes`. Resumen con 3B malo, con 7B bueno (366 s vs 145 s).
- L6 hallazgos de T9: el criterio de texto rotado por proporción descartaba encabezados cortos (ENF, UCI) -> reconocimiento por ancho de línea y franja; sellos verticales no activan el modo tabla.
