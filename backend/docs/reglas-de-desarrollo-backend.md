---
tags: [minsa-citas-whatsapp-bot, reglas, backend, reorganizacion-vault]
fecha: 2026-10-11
---

---
# Reglas de Desarrollo — Backend

  

> Consolidado y depurado de `Reglas-AntesDDESARROLLAR/Reglas - Backend (núcleo).md`, `Reglas - Backend (limpio).md`, `Anexo - Backend Node.md` y `Reglas o Errores que no cometer - BackEnd.md` — sin duplicados, con los incidentes reales que originaron cada regla cuando existen. Aplica al backend de este bot (Next.js API routes + `lib/`) y a `minsa-incidencias-backend` (Express 5), que comparten el mismo stack Node/TypeScript.

>

> **[O]** = obligatoria. **[G]** = objetivo progresivo (se aplica cuando el stack lo facilita).

>

> Las secciones 14 a 17 (feature flags, idioma de los nombres, nombres de archivos de documentación y complementos) se agregaron el 2026-10-14 a partir de la revisión de la bandera `INCIDENCIAS_ENABLED`.

  

## 1. Arquitectura

  

1. **[O] Controlador delgado.** Solo recibe la petición, valida lo básico y responde. La lógica no depende del framework web.

2. **[O] La lógica de negocio vive en servicios**, que no conocen `Request` ni `Response`.

3. **[O] Sin SQL ni acceso directo al ORM fuera de la capa de repositorios.** Cambiar de motor de datos no debe tocar los servicios.

4. **[O] Los DTO son la frontera entre HTTP y negocio.** El controlador extrae, valida y entrega un objeto plano — nunca pasa `Request`/`Response` al servicio.

5. **[G] Inyección de dependencias por constructor** (en Node, por parámetro o un contenedor como `awilix`). Facilita sustituir dependencias en tests.

   - *Estado al 2026-10-14 (backend):* los servicios reciben sus dependencias por constructor, con una excepción: `analizarMensaje` (`src/services/analisis-ia/analizar-mensaje.ts`) crea el cliente de IA por defecto dentro de la lógica (`opciones.cliente ?? crearClienteOllama()`). El valor por defecto debería vivir en el punto de composición. Se corrige al tocar ese archivo (regla 132).

6. **[G] Servicios externos (pagos, correo, almacenamiento) detrás de una interfaz y un adaptador en `providers/`.** El servicio principal no importa la librería del tercero directamente.

   - *Estado al 2026-10-14 (backend):* no existe la carpeta `providers/`. El adaptador del modelo de IA está en `src/services/analisis-ia/cliente-ollama.ts` (cumple el contrato `ClienteModelo` y usa timeout) y el de hash de claves en `src/utils/hasher-de-claves.ts` (`argon2`, un solo archivo). Hay una fuga de tipo de un tercero: `src/database/base-de-datos.ts` expone `QueryResultRow` de `pg` en su interfaz. Se ordena al tocar esos archivos (regla 132); no hay librerías de pagos, captcha, PDF ni Excel todavía.

  

## 2. Errores y códigos HTTP

  

7. **[O] Un tipo de error propio** (`AppError extends Error`), con código HTTP, mensaje para el cliente y `errorCode` interno. Prohibido lanzar errores genéricos.

8. **[O] Un manejador de errores global.** Los controladores lanzan; el manejador captura, formatea y responde. Prohibido repetir `try/catch` por controlador para armar respuestas.

9. **[O] Todo `errorCode` sale de un enum central.** El cliente decide el texto según el código, no según un mensaje fijo.

10. **[O] Nunca enviar al cliente trazas de pila ni errores crudos del ORM.** 500 con mensaje genérico; el error real va solo a logs.

11. **[O] Un solo formato de error para toda la API:** `{ success: false, statusCode, errorCode, message, timestamp, path, details? }` — `details` es `{ path, message }[]`, solo para errores de validación.

12. **[O] Evolucionar el formato de error sin romper clientes.** Campos nuevos son aditivos; un cambio incompatible exige una versión nueva (`/v2`). Un cliente ya desplegado no se actualiza al mismo tiempo que el servidor.

13. **[O] Códigos HTTP semánticos; nunca un 200 con error en el cuerpo.**

  

   | Código | Cuándo |

   |---|---|

   | 200 | Operación exitosa |

   | 201 | Recurso creado |

   | 204 | Éxito sin cuerpo |

   | 400 | Sintaxis o validación de entrada |

   | 401 | Sin token, vencido o credenciales inválidas (quién eres) |

   | 403 | Autenticado pero sin permiso (qué puedes hacer) |

   | 404 | El recurso no existe |

   | 409 | Duplicado o conflicto de estado |

   | 422 | Formato correcto pero la regla de negocio lo impide |

   | 500 | Fallo no controlado; nunca se lanza a propósito |

   | 501 | Endpoint definido, funcionalidad pendiente |

  

## 3. Validación y entrada

  

14. **[O] Validar body, params y query con un esquema (Zod, Joi, class-validator) antes de llegar al servicio.**

15. **[O] Validar identificadores (UUID, enteros) antes de consultar.** Evita errores de base de datos y respuestas ambiguas.

16. **[O] Paginación centralizada con tope máximo.** Un helper único parsea `page`, `limit`, `sort`.

17. **[O] Un helper central que arme filtros y descarte `undefined`/`null`/`""`** (`buildQueryParams`, espejo del de frontend).

  

## 4. Constantes y configuración

  

18. **[O] Estados, roles y tipos fijos en enums centralizados** (`enums/`). Prohibidos los "magic strings" (`if (estado === 'activo')`).

19. **[O] Sin números mágicos** (`if (diasRestantes < 15)`). Constantes con nombre (`MAX_TRIAL_DAYS`, `TOKEN_TTL_MINUTES`).

20. **[O] Valor repetido → archivo de constantes.** No se redefine por módulo.

21. **[O] Configuración en un módulo central y tipado.** Todo acceso a variables de entorno pasa por ahí, no disperso por el código.

22. **[O] La aplicación falla al arrancar si falta una variable obligatoria** — mejor un error al inicio que en producción.

23. **[O] `.env.example` siempre sincronizado con la configuración real**, sin valores secretos.

24. **[O] Sin credenciales, tokens, secretos ni cadenas de conexión en código, README o logs.** Un secreto publicado se rota, no se oculta después.

  

## 5. Datos

  

25. **[O] Varias escrituras relacionadas van en una transacción.** Si un paso falla, todo se revierte.

26. **[O] Evitar N+1.** Joins/`include`/agrupaciones; nunca una consulta dentro de un `for`/`map`.

27. **[O] Migraciones versionadas; nunca se edita una ya aplicada.** Se crea una nueva.

28. **[O] Toda consulta va parametrizada.** Prohibido concatenar entrada del usuario en SQL.

165. **[O] Los instantes se guardan en UTC (`TIMESTAMPTZ`) y las zonas horarias se nombran con el identificador IANA** (`America/Lima`), nunca con un desplazamiento fijo (`-05:00`), que no sabe de horario de verano. Si el sistema opera en una sola zona, basta una constante con nombre en el módulo de reloj. Detalle: *Reglas del Backend — Calidad de Código*, R82.

   - *Estado al 2026-10-15:* las columnas de fecha del bot son `Timestamptz(3)`. El literal `'America/Lima'` se repite en el bot (`lib/time/lima-clock.ts` lo define como constante, pero `lib/recepcion/repositorio.ts:60`, `lib/recepcion/consulta-dto.ts:24` y la migración `20261005070000_codigo_incidencia` lo escriben suelto) y en el backend `ZONA_DE_LIMA` se exporta desde `incidencia.repository.ts` en vez de vivir en un módulo de reloj. Los tipos de columna del backend no se verificaron: sus migraciones no están en su repositorio.

166. **[O] Los KPIs y los cortes por día se calculan en la zona operativa, nunca en UTC crudo.** Se convierte el instante a la zona IANA antes de truncar (`date_trunc('day', creado_en AT TIME ZONE zona)`); un evento a las 23:30 locales entra como 04:30 UTC del día siguiente. No se mantiene a mano una tabla de cambios de horario de verano. Una columna `fecha_operativa` precalculada es una desnormalización y la decide el responsable. Detalle: R83.

   - *Estado al 2026-10-15 (backend):* cumple. `indicadores.repository.ts` e `incidencia.repository.ts` convierten con `AT TIME ZONE` y la constante de zona antes de truncar el día y de filtrar por rango.

  

## 6. Seguridad

  

29. **[O] Lista blanca de rutas públicas con coincidencia exacta, nunca por prefijo.** *Incidente real (#488): un prefijo dejó públicas todas las rutas que empezaban con "f".*

30. **[O] Sesión en cookie `httpOnly`, nunca en `localStorage`.** Un XSS no puede leerla.

31. **[O] Token de vida corta con `exp`.** Al vencer, 401; la renovación usa un refresh token aparte y revocable.

167. **[O] Un token o un mensaje firmado se verifica con una lista blanca de algoritmos fijada en el servidor.** Nunca se confía en el campo `alg` de la cabecera: se rechaza `none`, no se entrega una clave pública a un verificador simétrico (confusión `RS256` a `HS256`) y se validan `iss`, `aud` y `exp`. Detalle: R87.

   - *Estado al 2026-10-15:* el backend no tiene librerías de firma de tokens ni verifica webhooks (`package.json`, sin `timingSafeEqual`): la regla es preventiva. El bot sí verifica la firma de Meta (ver regla 34).

32. **[O] Rol y estado del usuario se validan en el servidor en cada petición protegida** — el rol dentro del JWT no basta, queda desactualizado hasta que vence; el middleware consulta la base para el rol vigente.

33. **[O] El cliente nunca decide permisos.** Un endpoint de identidad (`me`) informa al frontend; cada endpoint protegido vuelve a comprobar el rol por su cuenta.

34. **[O] Webhooks verifican firma o secreto** (HMAC con comparación de tiempo constante, `timingSafeEqual`). *Incidente real (#132).*

   - *Estado al 2026-10-15 (bot), brecha abierta:* `app/webhook/whatsapp/route.ts` calcula la firma con `process.env.META_APP_SECRET ?? ""`. Si la variable falta, la clave es vacía y cualquiera puede firmar un cuerpo válido: falla abierta, contra la regla 22. Lo mismo, hacia afuera, en `lib/integrations/minsa/signature.ts` con `MINSA_INTEGRATION_SECRET ?? ""`. No se verificó si otro módulo valida las variables al arrancar. Registrado en SDD como G-01 (Engram #717).

35. **[O] Ningún secreto con prefijo público** (`VITE_`, `NEXT_PUBLIC_`) — termina en el JS del navegador. *Incidente real (#494).*

36. **[O] No registrar en logs tokens, contraseñas ni datos sensibles.** *Incidente real: un `auth.js` logueaba el token de reseteo de contraseña.*

37. **[O] Límite de tasa (rate limit) en autenticación y endpoints públicos.**

  

## 7. Fiabilidad

  

38. **[O] Toda excepción, síncrona o asíncrona, llega al manejador global.** En Express 4, un handler async sin envolver (`asyncHandler`) deja la petición colgada ante una promesa rechazada — Express 5 ya lo resuelve nativo.

39. **[O] Llamadas externas con timeout y reintentos acotados.** Sin timeout, un tercero lento bloquea el servicio.

168. **[O] Los reintentos son solo para fallos transitorios, con retroceso exponencial y azar (*full jitter*).** Se reintentan los errores de red transitorios y `408`, `429`, `502`, `503`, `504`; nunca `400`, `401`, `403`, `404`, `422`. Solo operaciones idempotentes o con clave de idempotencia (regla 163). Espera: `aleatorio(0, min(máxima, base × 2^intento))`, con las tres cifras como constantes con nombre. Detalle: R96.

   - *Estado al 2026-10-15 (backend), brecha abierta:* el bucle de `cliente-ollama.ts` reintenta sin esperar entre intentos y sin azar, reintenta todo `>= 500` y mezcla los fallos de red con los de formato de la salida del modelo (que son reintentos de contenido, no de red). El bot no tiene reintentos de red hacia el backend de MINSA y no se midieron sus timeouts. Registrado en SDD como G-04 y G-05.

169. **[G] Un cortacircuito protege de las caídas sostenidas de un proveedor.** Tras N fallos consecutivos dentro de una ventana, el adaptador rechaza de inmediato con un error de dominio durante un período de enfriamiento y deja pasar una sola llamada de prueba. Su estado está en memoria y no se comparte entre instancias. Detalle: R97.

   - *Estado al 2026-10-15:* ningún repositorio tiene cortacircuito.

40. **[O] Logs estructurados con nivel y contexto.** El error real se registra ahí, no en la respuesta.

41. **[G] Conexiones de larga duración (SSE, websockets) con heartbeat, limpieza al cerrar y tope de clientes.**

42. **[G] Comprobar que el entorno de despliegue admite el modelo del servicio** (proceso persistente vs. serverless) antes de desplegar.

  

## 8. Comentarios

  

43. **[O] Sin comentarios en código, tests ni configuración.** El código se explica solo.

44. **[O] Tampoco docstrings ni comentarios «solo donde hace falta»** (cambiada el 2026-10-12 tras la revisión de código del bot; antes se permitía uno breve). Si la lógica necesita explicación, va en el nombre, en una función con nombre o en el README. Ver regla 64.

45. **[O] No se documentan CRUD, getters, wrappers ni nombres claros.** Prueba: si al borrar el comentario alguien entiende igual el código, se borra.

46. **[O] Eliminar comentarios en inglés, autogenerados, o que repitan la línea siguiente.** Ningún `/** Shape of a validation error... */` en inglés sobrevive.

47. **[O] Los comentarios no citan otro repositorio ni un estado temporal.** Envejecen y mienten — incluido `README`/`AGENTS.md` desactualizado respecto al código real.

  

## 9. Calidad y mantenibilidad

  

48. **[O] Lógica pura (cálculo, formato de fechas, cifrado, transformación de texto) en `utils/`.** Se prueba sin infraestructura.

49. **[O] Imports con alias absolutos** (`@/modules/...`), nunca `../../../`.

50. **[O] Bloque repetido → diccionario o helper.** Mapa `{código: manejador}` en vez de cadena de `if`.

51. **[O] Eliminar código muerto.** Lo que nadie importa se borra o se integra.

52. **[O] Patrón Repositorio obligatorio para el acceso a datos** — un cambio de motor de base de datos no debe tocar los servicios.

53. **[O] Antes de tocar código sin cobertura, escribir tests de caracterización** que fijen el comportamiento actual antes de cambiarlo.

153. **[O] Cláusulas de guarda: las precondiciones salen primero y el camino feliz queda al final, sin anidar.** Cada condición que impide continuar se comprueba al inicio, lanza su error específico (regla 82) o retorna, y la función sigue. La lógica principal queda en el nivel base de la función, no dentro de uno o varios `if`.

154. **[O] Prohibido `else` después de `throw` o `return`.** Si la rama anterior ya terminó la función, el `else` sobra y solo agrega un nivel de sangría.

155. **[G] Máximo 2 niveles de anidamiento por función** (`if`, `for`, `try`, callbacks). Más de 2 se resuelve con cláusulas de guarda (153) o extrayendo un bloque a una función con nombre. Rige para código nuevo; no se reescribe lo existente solo por esto (regla 132).

156. **[G] Una cláusula de guarda por motivo de fallo, en el orden en que se explica al usuario:** primero lo que no depende de otra cosa (autenticado, activo), después lo que depende de lo anterior (rol, estado del caso). Una condición compuesta con `&&` que lanza un único error genérico esconde cuál falló; se separa en guardas con errores distintos.

   Ejemplo de lo que no se genera (anidado: el camino feliz queda enterrado tres niveles adentro):

   ```ts
   function derivarCaso(caso: Caso, usuario: Usuario) {
     if (caso.estado === EstadoCaso.ABIERTO) {
       if (usuario.activo) {
         if (usuario.roles.includes(RolCodigo.GESTOR)) {
           return derivar(caso);
         } else {
           throw new PermisoDenegadoError(usuario.id);
         }
       } else {
         throw new UsuarioInactivoError(usuario.id);
       }
     } else {
       throw new CasoCerradoError(caso.codigo);
     }
   }
   ```

   Ejemplo de lo que se implementa (guardas al inicio, camino feliz plano):

   ```ts
   function derivarCaso(caso: Caso, usuario: Usuario) {
     if (!usuario.activo) throw new UsuarioInactivoError(usuario.id);
     if (!usuario.roles.includes(RolCodigo.GESTOR)) throw new PermisoDenegadoError(usuario.id);
     if (caso.estado !== EstadoCaso.ABIERTO) throw new CasoCerradoError(caso.codigo);

     return derivar(caso);
   }
   ```

   Excepción: con una sola condición simple y dos ramas que ambas producen un valor (`return a` / `return b`), un `if/else` plano o un ternario es igual de legible; no se fuerza una guarda.

157. **[G] Un contrato que cruza archivos vive en `src/types/[modulo].types.ts`, no en el archivo ejecutable.** Los `.service.ts`, `.routes.ts` y `.repository.ts` no exportan `type` ni `interface` para que otros los importen; los consumen con `import type { ... } from "@/types/[modulo].types.js"`. Un tipo que usa una sola función de ese archivo se queda ahí sin `export`. El beneficio es práctico: se evitan ciclos de importación y servicios y rutas comparten un contrato sin importar código ejecutable. `verbatimModuleSyntax` ya obliga a `import type` cuando solo se importa un tipo, así que esa parte la hace cumplir el compilador.
   - *Estado al 2026-10-14:* 13 archivos del backend (sobre todo repositorios) exportan tipos; `incidencia.repository.ts` exporta 7 interfaces. Es **[G]** y rige para código nuevo: no se mueven los existentes salvo al tocarlos por otra razón (regla 132).

158. **[O] Toda promesa se espera o se descarta a propósito.** Prohibida la promesa suelta: se hace `await`, o se marca `void` cuando corre en segundo plano a propósito, y entonces la función atrapa sus propios errores (regla 38). Las lecturas independientes entre sí van juntas en `Promise.all`; el `await` en serie queda para cuando un paso depende del anterior o cuando el orden es parte del comportamiento.

159. **[O] `catch` con `unknown`, nunca `any`.** `useUnknownInCatchVariables` ya viene con `strict`. Se discrimina con `instanceof` contra las clases de `errors/` (regla 85) antes de leer una propiedad; lo que no es de nuestras clases se vuelve a lanzar o se pasa al manejador global.

160. **[O] Una función no muta el objeto que recibe.** Se trabaja sobre una copia o se devuelve un objeto nuevo (`{ ...slots, clave: valor }`). En la máquina de estados del bot la copia se hace una vez al entrar (`cloneSession`) y solo se escribe en esa copia de trabajo, llamada `next`; la sesión original no se toca, así una persistencia que falla no deja el estado en memoria a medias y una prueba puede comparar la entrada antes y después.
   - *Estado al 2026-10-14:* el bot tiene 76 asignaciones `next.slots[...] = ...`, todas sobre la copia: es el patrón aceptado. Lo prohibido es `session.slots.x = ...` sobre la sesión recibida o mutar un arreglo parámetro (`items.push`). Una función que escribe en su argumento lo declara con el nombre `next` y solo se llama con la copia (`offerList(next, ...)`). En el backend no encontré mutación de parámetros.

161. **[O] El tiempo entra como parámetro.** Toda función que decide por plazo, vencimiento o ventana recibe el instante (`ahora`) y no llama a `new Date()` ni a `Date.now()` en su cuerpo. Un valor por defecto (`ahora = new Date()`) solo se permite en el borde, el punto de entrada, no en el cálculo. El tipo es el que ya usa el módulo: `Date` en el backend (`calcularPlazo` recibe `ahora: Date`), milisegundos en el bot (`handle(session, event, now = Date.now())`). El día y la hora de Lima salen de un solo módulo (`lib/time/lima-clock.ts` en el bot), no de `getHours()` ni de `toLocaleString` repartidos.
   - *Estado al 2026-10-14:* ya se cumple en la lógica de plazos del backend y del bot. Los 7 usos directos en el backend son de infraestructura (marca de tiempo del error, duración de la llamada a Ollama, vigía SSE), no de reglas de negocio. Una excepción en el bot: `format-window-countdown.ts` lee `Date.now()` en su cuerpo.

162. **[G] Aleatoriedad e identificadores: `node:crypto`, nunca `Math.random`**, para todo código con efecto de seguridad o de unicidad (traceId, requestId, códigos). Quien los consume recibe el generador como parámetro cuando la prueba necesita fijarlo. *Estado:* hoy solo `crypto.randomUUID()` en `signature.ts` y `recepcion/servicio.ts` del bot, y `randomInt`/`randomUUID` en los auxiliares de prueba del backend; el OTP lo genera el servicio de MINSA, no este código.

163. **[O] Una entrada que se puede repetir se procesa una sola vez.** Meta reintenta un webhook si tarda en responder y una persona puede tocar dos veces un botón; las dos peticiones no pueden ejecutar la misma transición ni duplicar una cita o una incidencia. Dos mecanismos distintos, que se nombran por separado:
   - **Duplicado exacto:** reclamar el `messageId` antes de procesar (`inboundDedupe.claim(messageId)`, TTL de 24 h). Una petición que no consigue el reclamo termina sin efecto.
   - **Dos mensajes distintos de la misma conversación a la vez:** el candado por conversación (`turn-lock`, bloqueo consultivo de PostgreSQL por `waId`) serializa los turnos.
   - **Limitación conocida:** `inboundDedupe` guarda los reclamos en memoria, así que no se comparte entre instancias; con más de una instancia (o funciones serverless) el reintento puede caer en otra y pasar. El candado por conversación sí vive en la base y cubre ese caso, pero solo si el segundo turno vuelve a leer el estado ya guardado.
   - *Pendiente de verificar:* si el alta de una incidencia en el backend tiene una clave única (por ejemplo, el `traceId` del bot) que haga que reintentar la creación no cree un segundo caso. No la encontré en el repositorio; hasta confirmarla, la idempotencia de ese alta descansa solo en el bot.

164. **[G] Una ventana de tiempo se define por su inicio, y su inicio se prueba.** Para la ventana de 24 horas de WhatsApp: Meta la abre con el último mensaje entrante de la persona y cada mensaje nuevo la renueva, no se cuenta desde que se creó la conversación. *(Confirmar contra la documentación vigente de Meta antes de implementar la lógica: es el comportamiento que conozco, no lo verifiqué aquí.)* Consecuencias para el código: guardar el instante del último mensaje entrante, calcular el vencimiento con el instante recibido por parámetro (regla 161) y probar tres casos: mensaje en el último minuto de la ventana (la renueva), mensaje justo después del vencimiento (no la renueva, exige plantilla) y la misma ventana vista desde `America/Lima`. No confundir esta ventana con las otras del bot (`INBOUND_DEDUPE_TTL_MS`, ventana de coalescencia de 1,5 s, ventana del aviso de fallo): cada una tiene su constante con nombre (regla 148).

  

## 10. Git

  

54. **[O] `.gitignore` incluye `.vscode/`, `.idea/`, `.DS_Store`, `.env`, `.env.local`.**

55. **[O] Commits convencionales, en español, con el autor del usuario, sin atribución de IA.**

56. **[O] Ante correcciones sobre un PR abierto, no apilar commits** — `git commit --amend --no-edit` y `push --force-with-lease` (nunca `--force` a secas) solo en rama propia.

57. **[O] No crear ramas nuevas sin consultar.** Se actualiza la rama de trabajo existente.

58. **[O] Antes de un rebase, crear una rama de respaldo.** Ante un conflicto, se avisa — no se resuelve por cuenta propia. Procedimiento detallado: `Comandos para hacer Rebase.md`.

  

## 11. Lecciones de IA específicas de este proyecto (bot MINSA, verificadas)

  

> Estas 5 no son genéricas — salieron de bugs reales de este bot. Se mantienen con el incidente completo porque el "por qué" es la parte que evita repetirlo.

  

59. **Matching de texto libre contra un catálogo nunca es solo exacto o por prefijo.** Sumar tolerancia a errores de tipeo (Levenshtein u otra distancia) — si no, un typo real rompe el flujo en silencio. *"sam bolja" nunca resolvía contra "SAN BORJA"; el ciudadano caía al flujo manual después de ya haber pasado documento y OTP.*

60. **Si una función o prompt de IA espera varios campos de contexto, verificar que TODOS los call-sites los completen igual.** Un campo `undefined` en un solo lugar viola el diseño del prompt sin lanzar error — la IA sigue respondiendo, solo que peor, y nadie se entera hasta que un ciudadano real lo sufre.

61. **Un test que solo verifica "se disparó la consulta a la IA" no prueba nada real.** Hay que mockear la respuesta del modelo y verificar el estado final correcto después de recibirla — el bug de "sam bolja" pasó inadvertido bajo cobertura que solo comprobaba el disparo, nunca el resultado.

62. **Auditar qué puede responder cada clasificador de IA usado como red de seguridad, no solo qué reglas determinísticas existen antes de él.** Un clasificador con un enum/schema cerrado degrada en silencio hacia la categoría más parecida si el mensaje real no encaja en ninguna — nunca falla ruidosamente. *Ver [[project-emergencia-ia-ciego-caso]] (memoria): la IA del menú principal ya corría y recibía mensajes de una emergencia real, pero solo podía responder "cita"/"fuera de alcance"/"no está claro" — nunca "emergencia" — hasta la corrección del 2026-09-30.*

63. **Un flujo de recuperación manual nunca debe pedir más que el camino exitoso ni ser más pobre que él** — debe reusar la misma lógica de resolución (fuzzy, catálogo, IA), no un camino aparte más rígido. El usuario ya pagó el costo de que la automatización fallara; el rescate no debe cobrarle una segunda vez.

  

## 12. Checklist antes de abrir un PR

  

- [ ] El formato de error solo agrega campos; no quita ni renombra los existentes.

- [ ] Cero literales de estado, mensajes de error o números mágicos fuera de enums/constantes.

- [ ] Cero `try/catch` que respondan HTTP dentro de controladores.

- [ ] Cero secretos en código, README y logs; `.env.example` al día.

- [ ] Los errores devuelven el formato estándar y el código HTTP correcto.

- [ ] Sin comentarios triviales ni en inglés; sin código muerto.

- [ ] Si se tocó un matcher de texto libre o un prompt de IA: ¿tiene tolerancia a typos? ¿todos los call-sites pasan el mismo contexto? ¿el test verifica el resultado final, no solo que se disparó la consulta?

- [ ] Tests, análisis estático y build en verde.

- [ ] Ningún texto al usuario, botón, número de regla de negocio ni expresión regular dentro de un archivo de lógica (sección 13.1).

- [ ] Ningún `throw new Error(` genérico; ningún gesto repetido que ya tenga función utilitaria (secciones 13.3 y 13.4).

- [ ] Si se tocaron migraciones: probadas contra una base con la forma real del servidor y con datos, no solo contra una base vacía (sección 13.6).

- [ ] `npm run format:check` en verde.

- [ ] Rama al día con la rama destino, un solo commit, mensaje corto.

- [ ] Si se agregó una bandera: ¿se preguntó al responsable? ¿un solo lector, apagada por omisión, nombre `<ÁMBITO>_ENABLED`, probada encendida, apagada y sin definir, con todos los puntos de entrada enumerados (sección 14)?

- [ ] ¿Se corrieron las pruebas de convenciones del repo (regla 109) antes de abrir el PR?

- [ ] Las variables de entorno nuevas están en inglés (sección 15); los `.md` nuevos, en español y en kebab-case (sección 16).

  

---

  

## 13. Lecciones de la revisión de código del bot (octubre 2026)

  

> Salieron de la revisión de tres merge requests del bot en GitLab (`oidt/minsa-digital-bot`): el !11 (interfaz), el !13 (base de datos) y el !14 (flujo de incidencias y lógica), entre el 2026-10-11 y el 2026-10-12. Cada observación se aplicó a **todo** el proyecto, no solo al archivo señalado.

>

> **Estado al 2026-10-12:** las del MR !11 figuran resueltas. Las 10 del MR !14 están aplicadas en el código y subidas (commit `e2faf82`), pero **siguen abiertas en GitLab**: el revisor todavía no las dio por buenas. Si alguna se rechaza o se ajusta, se corrige aquí.

>

> Las reglas llevan el antes y el después reales del código, porque el «por qué» es lo que evita repetirlas.

  

### 13.1 Constantes: nada de valores escritos en medio de la lógica

  

64. **[O] Sin comentarios ni docstrings en ningún archivo**: código, pruebas, migraciones SQL, semillas, esquema de Prisma, configuración. La única excepción son las directivas que una herramienta necesita (`eslint-disable`). Se quitaron 350 comentarios SQL y 174 del código; se comprobó que el código impreso sin comentarios era idéntico antes y después.

   - *Observación:* sobre los comentarios de una migración. El responsable del proyecto la extendió a todo.

  

65. **[O] Un archivo de lógica no contiene textos.** Todo mensaje al usuario, título de botón, fila de lista o encabezado vive en `lib/constants/textos/`, un archivo por flujo (`incidencia.ts`, `consulta.ts`, `cita-reserva.ts`…). Vale también para los que **ya eran constantes** arriba del archivo del paso: estar declarado como constante no alcanza, tiene que estar en la carpeta.

   - *Observación:* «constante», y después «lo mismo» sobre un bloque que ya eran constantes de módulo.

   - *Antes:*

     ```ts

     if (!(hasEstablecimiento && codigo)) return "Gracias por tu reporte de incidencia, ya se registró.";

     ```

   - *Después:* el paso importa la constante; el texto está una sola vez, en `lib/constants/textos/incidencia.ts`.

  

66. **[O] Un texto que lleva un dato es una función en el mismo archivo de textos**, que recibe el dato y devuelve el mensaje. No se arma la plantilla dentro del paso.

   ```ts

   export const incidenciaRegistradaText = (codigo: string): string => …

   ```

  

67. **[O] Un mensaje existe una sola vez.** Antes de escribir un texto, buscar si ya existe. Se encontraron 17 mensajes repetidos tal cual entre archivos («Ingresa tu número de documento.» estaba 4 veces). Tres casos distintos, tres soluciones:

   - **Copia exacta** → una constante, todos la importan. No cambia nada para el usuario.

   - **Un texto que es otro con un agregado** → se arma a partir del común, solo si el resultado queda idéntico:

     ```ts

     export const VERIFIED_ASK_DISTRITO_TEXT = `¡Verificado! ${ASK_DISTRITO_TEXT}`;

     ```

   - **El mismo aviso redactado distinto** → unificarlo **cambia lo que lee el usuario**: es una decisión de contenido y la toma el responsable, no quien programa. Caso real: el aviso de cancelación de una incidencia existía con tres redacciones; se unificó en una sola por decisión explícita.

   - *Observación:* «este mismo texto está duplicado en `REGISTRO_CANCELADO_TEXT`». No era una copia exacta, por eso una búsqueda literal no lo encontraba: hay que buscar también los casi iguales.

  

68. **[O] Las palabras que escribe el usuario también son constantes.** `typed.toUpperCase() === "OMITIR"` pasa a comparar contra `OMITIR_KEYWORD`. Si la misma palabra ya está dentro de una expresión regular o de una lista de frases, no se duplica el conocimiento: se reporta.

  

69. **[O] Los números que expresan una regla van con nombre, en `lib/constants/limits/`**, un archivo por tema. Longitudes máximas, cantidad de intentos, ventanas de tiempo, umbrales. Refina la regla 19: no basta con nombrarlos, tienen que salir del archivo de lógica.

   - Se quedan donde están: índices de arreglos, aritmética con 0 y 1, conversiones de unidad evidentes, códigos HTTP.

   - **Un texto que menciona un límite se arma con la constante**, no con el número copiado. Caso real: un mensaje decía «hasta 1000 caracteres» mientras el límite vivía en otra constante; si alguien cambiaba el límite, el mensaje mentía.

  

70. **[O] Las expresiones regulares viven en `lib/constants/regex/`**, agrupadas por tema, cada una con un nombre que dice qué reconoce. Un patrón largo con varias alternativas se arma con partes con nombre. Las que se construyen con datos del propio módulo (nombres de meses, de días) se quedan en él, anotadas en una lista de excepciones.

  

71. **[O] Las instrucciones para un modelo de IA (prompts) van en `lib/constants/prompts/`**, una por tarea. Las que interpolan datos son funciones. Complementa la regla 60: tener el prompt en un solo lugar hace visible qué contexto espera.

  

72. **[O] Sin alias que solo renombran un valor.** `const CONSENT_SI = IncidenciaButtonId.CONSENT_SI;` no aporta nada: se usa el miembro del enum directo. Se borraron 45.

  

### 13.2 Estados y tipos

  

73. **[O] Ningún estado, motivo o discriminante se compara como texto suelto.** `result.status === "accepted"`, `result.reason === "daily_limit"`, `by: "codigo" | "nombre"` pasan a enums en `lib/enums/` (uno por archivo), con los **mismos valores** que tenían. Un error de tipeo en un texto suelto compila igual; en un enum no. Refuerza la regla 18.

   - *Observación:* «constante» sobre el tipo de resultado de `buscar.ts`.

  

74. **[O] Los tipos usan el enum directo, no una plantilla.** Para no tocar pruebas se había escrito `` status: `${EstablecimientoSearchStatus.FOUND}` ``; quedaban líneas de más de 200 caracteres y se perdía que el compilador avisara si faltaba tratar un caso. La forma correcta es `status: EstablecimientoSearchStatus.FOUND`, aunque obligue a actualizar las pruebas.

   - **Lección:** un atajo para no editar pruebas se paga en legibilidad y en seguridad de tipos. Las pruebas que arman un resultado con el texto literal pasan a usar el miembro del enum; el valor es el mismo, la afirmación no se debilita.

  

75. **[O] Un `switch` sobre un enum trata todos los casos, sin `default`.** Así el compilador falla si alguien agrega un valor y olvida tratarlo. Solo lleva `default` cuando ese caso es un error de programación, y entonces lanza un error propio (regla 82).

  

76. **[O] Los valores que se guardan no se renombran.** Estados de sesión, claves de datos de la conversación e identificadores de botones quedan persistidos y las pruebas los afirman literalmente: cambiar uno rompe conversaciones en curso. Un enum nuevo toma exactamente los textos que ya circulaban.

  

### 13.3 Funciones utilitarias

  

77. **[O] Un gesto que se repite es una función con nombre y con pruebas**, en `lib/utils/`. Antes de la revisión, `String(x ?? "")` aparecía 102 veces y `typeof x === "string"` 52.

   - *Observación:* «agregar una función utilitaria, `esString(variable)`».

   - *Antes:* `const codigo = typeof payload.codigo === "string" ? payload.codigo : "";`

   - *Después:* `const codigo = stringOr(payload.codigo);`

   - Las que existen hoy: `isString`, `isNonEmptyString`, `isFiniteNumber`, `isObject`, `isRecord`, `toText`, `stringOr`, `stringOrUndefined`, `stripAccents`, `arrayOr`, `parseJsonOr`, `readString`, `readNumber`.

  

78. **[O] Las que comprueban un tipo son predicados de tipo** (`value is string`), para que el compilador siga estrechando el tipo después de llamarlas. Se verifica con el chequeo de tipos que no se perdió ninguno.

  

79. **[O] Antes de reemplazar por una función que «ya existe», comprobar que hace exactamente lo mismo.** Dos casos reales en los que parecía obvio y no lo era:

   - `readReply(event)` devuelve el identificador del botón **o, si no hay, el texto escrito**. Usarla donde se leía solo el toque habría hecho que alguien que tipeara el identificador de un botón contara como si lo hubiera tocado. Se creó `readTappedId`, que solo acepta toques.

   - `normalizeText` quita acentos **y además** pasa a mayúsculas, recorta y junta espacios. Se creó `stripAccents`, que solo quita acentos.

   - **Dos expresiones parecidas no son intercambiables:** `String(x ?? "")` convierte números y booleanos en texto; `typeof x === "string" ? x : ""` no. `isNonEmptyString` recorta espacios; comparar contra `""` no.

  

80. **[O] Un lector tipado vive junto al tipo que lee, no en las utilitarias generales.** Leer un dato de la conversación como texto (`slotText(slots, clave)`) está junto a la sesión; leer el texto del mensaje entrante está junto a los demás lectores del evento. Una utilitaria general no conoce el dominio.

  

81. **[O] Solo se crean las utilitarias que el código usa.** Nada «por si acaso».

  

### 13.4 Errores

  

82. **[O] No se lanza `Error` genérico. Cada falla tiene su clase en `lib/errors/`**, una por archivo, con el nombre del archivo igual al de la clase. Concreta la regla 7 para los errores internos, los que no llegan al cliente.

   - *Observación:* «crear una clase Error específica para evitar duplicar. Ej.: `throw new UnknowStateError(session.state)`». (El nombre correcto es `UnknownStateError`.)

   - *Antes:* el mismo `throw new Error(...)` con el mensaje armado a mano, repetido en cuatro despachadores de estados.

   - *Después:*

     ```ts

     export class UnknownStateError extends Error {

       constructor(

         readonly handler: string,

         readonly state: string,

       ) {

         super(`${handler}: unknown state "${state}"`);

         this.name = "UnknownStateError";

       }

     }

     ```

  

83. **[O] La clase guarda los datos como campos y arma el mensaje adentro.** Quien atrapa el error lee `error.state`, no descompone un texto. Se agrupa por significado, no una clase por cada lugar donde se lanza.

  

84. **[O] Al cambiar un `Error` por una clase, el mensaje queda idéntico.** Las pruebas y los registros lo buscan por texto. Se afirma con una prueba que compara contra el texto anterior, letra por letra.

   - **Efecto a tener presente:** en los registros, el nombre del error pasa de `Error` al nombre de la clase. Si alguien filtra por ese campo, hay que avisarle.

  

85. **[O] Un error se reconoce por su clase (`instanceof`), nunca por el texto del mensaje.** Con un error de un tercero, por su código (`P2002`, `55P03`), no por una expresión regular sobre el mensaje.

  

86. **[O] Un resultado no es un error.** Una función que devuelve «encontrado / vacío / falló» sigue devolviéndolo; no se convierte en excepción ni al revés. Las excepciones son para fallas de programación o de infraestructura.

  

87. **[O] Un `catch` que no deja rastro esconde fallas.** Caso real encontrado y todavía sin corregir: al registrar una incidencia, si falla la lectura del código, el error se traga sin registro y el usuario recibe la confirmación sin código. Un `catch` vacío solo se acepta cuando es intencional y hay una prueba que lo dice (por ejemplo, el registrador de eventos nunca debe lanzar).

  

### 13.5 Datos que vienen de otro servicio

  

88. **[O] El cliente es transparente: usa lo que envía el backend, tal cual.** Si el servicio manda `{ status_reference, message, data }`, hacia adentro circula `{ statusReference, message, data }`. No se deduce el estado mirando si hay filas, no se vuelve a validar un estado que ya llegó, y no se filtran datos por reglas de negocio: eso es del servicio.

   - *Observación:* «Si el status ya es `found`, vuelves a agregar `status: "found"`; esto es doble validación… Busca que tu frontend sea transparente para el backend y el backend un estándar, así no haces combinaciones raras en el frontend y la mantenibilidad es más rápida».

  

89. **[O] La respuesta se lee en un solo punto, en la frontera.** Nadie más adivina su forma con cadenas como `body?.data ?? body?.referencias ?? body?.items`. Cada forma alternativa que se tolera sin evidencia es una mentira sobre el contrato.

  

90. **[O] Un campo no se llama `status` a secas.** Lleva un nombre específico (`statusReference`).

  

91. **[O] Sin datos simulados que se activen con un valor mágico** (un documento de prueba fijo). Confunden a quien revisa y quedan vivos en producción. Los simuladores generales, los que responden cuando la integración real está apagada, son otra cosa y se quedan.

  

92. **[O] Antes de quitar una deducción del cliente, confirmar que el servicio ya envía ese dato, y avisar.** Caso real: el bot dejó de deducir el estado de las referencias y de filtrar por estado. El servicio todavía devolvía un arreglo suelto, así que hasta que publique el contrato nuevo el bot no ofrece referencias (sigue con el flujo normal, sin romperse). Quedó anotado como requisito del despliegue. **No se cambia el contrato de otro equipo por suposición:** se le pregunta, con una lista concreta.

  

### 13.6 Base de datos, migraciones y despliegue

  

93. **[O] Editar una migración ya aplicada rompe en silencio las bases que ya existen.** Refuerza la regla 27 con el incidente real: nueve migraciones se habían reescrito conservando el nombre de carpeta. Al desplegar sobre una base creada con la versión anterior, `prisma migrate deploy` terminó con éxito, aplicó solo la migración nueva y **no avisó nada**. La base quedó sin 7 tablas y 98 columnas. La herramienta identifica las migraciones por el nombre de carpeta, no por su contenido.

  

94. **[O] Si ya pasó, se arregla con una migración «puente», no reescribiendo otra vez.** Una migración nueva e idempotente (`IF NOT EXISTS`, `CREATE OR REPLACE`, cambios de datos condicionados a la forma vieja) que:

   - completa una base creada con la versión anterior, sin perder filas;

   - no cambia nada en una base creada con la versión actual. Se comprueba que ninguna fila cambia de versión física.

   - Se ejecuta dos veces sin error.

  

95. **[O] Una migración se prueba contra una base con la forma real del servidor y con datos.** No alcanza con una base vacía. El procedimiento que funcionó:

   96. Crear una base desechable con las migraciones que tiene hoy la rama desplegada.

   97. Cargarle datos representativos, incluidos los casos límite.

   98. Aplicar las migraciones nuevas.

   99. Comparar contra una base creada desde cero: tablas, columnas, restricciones, índices, funciones, disparadores y descripciones. La diferencia tiene que ser cero.

   100. Comparar los conteos de filas antes y después.

   - **Mismo motor y versión que el servidor.** El servidor usa PostgreSQL 16 y el desarrollo PostgreSQL 18; `uuidv7()` solo existe en la 18.

   - **Confirmar cuál es la forma real.** Se habían hecho las pruebas contra una forma de nueve migraciones y la rama desplegada tenía ocho. Se confirma leyendo las migraciones de la rama que está desplegada, no de memoria.

  

96. **[O] Los datos que no cargan las migraciones son un requisito de despliegue, y se escribe.** El padrón de establecimientos (434 filas) se carga con un comando aparte. Sin él, 17 pruebas contra la base fallaban y el flujo respondía «No encontré ese establecimiento» a todo. Una migración que crea una tabla vacía de la que depende un flujo no está completa hasta que alguien carga los datos.

  

97. **[O] Las pruebas contra una base real se corren antes de subir, no solo las unitarias.** Las unitarias simulan la base; las de humo (contra PostgreSQL real) fueron las que encontraron el padrón vacío. Si el entorno local no tiene el cliente de base de datos, se corre dentro del contenedor.

  

98. **[O] Una migración que mueve datos decide en voz alta, y la decisión es del responsable.** Qué hacer con una columna que desaparece, con roles que ya no existen, con filas que no cumplen una regla nueva. Si un dato no se puede convertir, la migración **se detiene con un error claro**; no inventa un valor. Caso real: una incidencia resuelta sin texto de resolución detiene el puente.

  

99. **[O] Saber qué dispara un despliegue antes de fusionar.** La rama de integración despliega sola al entorno de desarrollo, y las de `release/*` al de calidad. Fusionar es desplegar: las migraciones corren contra la base del servidor en ese momento. Los requisitos (datos por cargar, contrato de otro servicio, variables de entorno) se cierran antes.

  

100. **[O] Una variable de entorno nueva se pide a infraestructura con su riesgo dicho.** Caso real: `SANDBOX_PAGE_ENABLED=true` muestra las páginas de prueba y además abre una bandeja **sin autenticación**, que lista conversaciones con su teléfono. En producción se deja sin definir. Para saber qué variables son nuevas se compara lo que lee el código entre las dos versiones, no se confía en la memoria.

  

101. **[O] Entregar por partes, y en el único orden que funciona.** Un cambio grande se dividió en tres merge requests: interfaz, base de datos, lógica. **La base va antes que el código que la usa:** el código nuevo necesita tablas que no existen, y el código actual sí funciona con la base nueva. Eso se **demuestra** antes de subir: la versión desplegada más solo la parte de base de datos tiene que compilar, pasar sus pruebas y pasar las de humo contra la base nueva.

  

### 13.7 Formato

  

102. **[O] El formato lo decide una herramienta, no cada persona.** Prettier con una configuración mínima que coincide con cómo ya estaba escrito el código, para que el cambio sea partir líneas y no reestilizar. Comandos `npm run format` y `npm run format:check`; un paso del CI falla si se sube código sin formatear.

   - *Observación:* «ordena el código, formatea los cambios que subas; el código debe ser fácil de entender».

  

103. **[O] Medir antes de elegir el ancho de línea.** Se probaron 100, 120 y 140 caracteres: cuántos archivos y líneas cambiaba cada uno y cuántas líneas largas dejaba. Se eligió 140 por ser el que menos tocaba. **Costo conocido:** a 140 la herramienta junta en una línea listas que estaban una por renglón; con 120 no, a cambio de unas 2.500 líneas más de diferencia.

  

104. **[O] No se formatea lo que no es de este cambio.** Formatear todo de una vez llenaba el merge request de archivos ya fusionados que solo cambiaban de forma. Se formateó la mitad que se estaba entregando y el resto se dejó excluido en la configuración, anotado como tarea aparte.

  

105. **[O] El formateador no reordena clases de estilos ni toca el contenido de los textos.** No se instalan complementos que lo hagan. Las líneas largas que quedan son contenido de cadenas (mensajes, instrucciones para la IA, SQL) y se aceptan.

  

106. **[G] Cuidar los finales de línea.** En Windows una herramienta de edición puede cambiar los finales de línea de un archivo entero: un cambio de dos líneas apareció como 346. Antes de cada commit se compara `git diff --shortstat` con `git diff --shortstat --ignore-cr-at-eol`; si los números difieren, hay un cambio espurio.

  

### 13.8 Cómo se trabaja una observación de revisión

  

107. **[O] Una observación se corrige en todo el proyecto, no solo en el archivo señalado.** Si no, el revisor marca lo mismo en el archivo siguiente. Se empieza por un **inventario**: cuántas veces aparece el patrón y dónde. Los números de esta revisión: 265 textos dentro de funciones, 102 conversiones a texto, 119 expresiones regulares en línea, 17 mensajes duplicados.

  

108. **[O] «No cambia el comportamiento» se demuestra, no se afirma.** Para cada movimiento mecánico hubo una comprobación mecánica:

   - Comentarios: el código impreso sin comentarios es idéntico antes y después.

   - Textos y expresiones regulares: el conjunto completo de valores distintos es el mismo antes y después; cada diferencia se explica una por una.

   - Clases de estilos: cada componente se dibuja a texto antes y después y se comparan las clases como conjunto.

   - Migraciones: comparación de catálogos entre dos bases reales.

   - Código sin pruebas: primero una prueba de caracterización (regla 53), después el cambio.

  

109. **[O] Cada regla nueva lleva una prueba que la hace cumplir.** Si no, se rompe en el siguiente cambio. Las que existen hoy leen el código con el analizador del lenguaje y fallan si aparece: un mensaje dentro de una función, una expresión regular fuera de su carpeta, un gesto repetido escrito a mano, un `new Error` fuera de `lib/errors`, un botón nativo fuera del componente base. Las excepciones van en una lista explícita, cada una con su motivo como dato.

  

110. **[O] Una prueba que lee el código como texto tiene que tolerar espacios.** Si el formateo rompe uno de sus patrones, se arregla la prueba; no se desformatea el código ni se afloja lo que prohíbe.

  

111. **[O] Los cambios que tocan los mismos archivos van uno después del otro, no en paralelo.** Cada tanda se verifica (tipos, análisis estático, pruebas, rendimiento, pruebas contra la base) antes de empezar la siguiente, para poder atribuir una falla a una sola.

  

112. **[O] Lo que se encuentra y no se pidió, se reporta; no se arregla de paso.** Errores de redacción, patrones dudosos, fallas escondidas. Mezclarlos con un cambio mecánico impide demostrar que el cambio no altera nada. Pendientes reales de esta revisión: «Disculpa» dos veces en un mismo mensaje, «espere 1 minutos», mezcla de «tú» y «usted».

  

113. **[O] Un trabajo delegado se verifica antes de darlo por hecho.** Se vuelven a correr las pruebas, se lee el resultado y se contrasta contra el repositorio. Un informe puede equivocarse con seguridad: hubo conteos inflados y una prueba que se ejecutó en la carpeta equivocada.

  

### 13.9 Entrega en un repositorio con revisión

  

114. **[O] Una rama y un merge request por entrega, con un solo commit.** Las correcciones reemplazan ese commit; no se apilan (regla 56). Con `--force-with-lease` **atado al commit que se espera encontrar**: si alguien subió otra cosa, se rechaza en vez de pisarla.

  

115. **[O] Antes de cada subida se trae la rama destino y, si avanzó, se hace rebase.** Avanzó tres veces en un día por cambios de otras personas. Con respaldo local del commit anterior (regla 58).

  

116. **[O] El mensaje de commit es corto:** un título y pocas viñetas puntuales. No describe pruebas ni verificación; eso va en el merge request.

  

117. **[O] Una rama montada sobre otra se revisa contra esa otra.** Si su merge request apunta a la rama de integración, la plataforma muestra las dos sumadas y parece que trae el triple de cambios. Se avisa antes de crearla, o se espera a que la primera esté fusionada.

  

118. **[O] Archivos de asistentes de IA (`CLAUDE.md`, `AGENTS.md`, `.claude/skills/`) no se suben al repositorio institucional (GitLab); en GitHub sí se versionan** (actualizada el 2026-10-14). El servidor de desarrollo regenera `AGENTS.md`: antes de preparar un commit o MR hacia GitLab se verifica con `git diff --name-only <destino>...HEAD` que ninguno está incluido. Las skills de revisión secuencial (`revision-backend`, `revision-be-01` a `10`) aplican estas reglas en orden.

  

119. **[O] Lo que se deja para después se escribe con los pasos.** No «pendiente: formatear el frontend», sino qué quitar, qué correr y qué verificar. Un pendiente sin pasos se pierde o se rehace desde cero.

  

## 14. Feature flags (banderas de funcionalidad)

  

120. **[O] Cuándo una función necesita bandera.** Antes de programar, preguntar al responsable si el requisito es de alguno de estos tipos:

   - Se despliega apagado y se enciende después (piloto, alcance por fases).

   - Depende de un dato, contrato o servicio de otro equipo que aún no está listo.

   - Se necesita poder apagarla en producción sin redesplegar.

   - Abre una superficie sin autenticación o de riesgo (regla 100).

   Quien programa pregunta «¿esta función lleva bandera? ¿con qué valor por defecto?»; no lo decide solo.

  

121. **[O] Un solo lector por bandera.** Un único módulo (`lib/config/features.ts` en el bot, `src/config/entorno.ts` en el backend) lee la variable y expone `isXEnabled()` o un campo booleano ya transformado. Ningún otro archivo toca `process.env.X`.

   - El literal `process.env.NOMBRE` se mantiene en ese lector: la prueba de `.env.example` detecta las variables por esa forma (`process.env.X`, `process.env["X"]`, `numberFromEnv("X")`, `env("X")`). Un lector genérico con el nombre en una variable no lo detecta.

  

122. **[O] Valor por defecto: apagado.** Se enciende solo con `true` explícito. Prohibido `!== "false"` (encendido por omisión), salvo decisión escrita del responsable. Una sola normalización para todas (`trim`, minúsculas, `=== "true"`).

   - *Estado al 2026-10-14:* `DATABASE_ENABLED` está encendida por omisión (`!== "false"`), con polaridad opuesta a las demás; el README tiene que explicar «vacía = con base». Es una trampa documentada, no un diseño.

  

123. **[O] Nombre `<ÁMBITO>_ENABLED`, en inglés y afirmativo.** Nunca `DISABLE_X` ni `NO_X`.

  

124. **[O] Documentar la bandera en el mismo cambio:** `.env.example`, tabla de variables del README, qué ve la persona con la bandera apagada y si se lee en cada petición o solo al arrancar. El bloque mínimo de despliegue la incluye solo si el servidor la necesita.

  

125. **[O] Con la bandera apagada, TODOS los puntos de entrada responden igual de claro.** Se enumeran antes de programar:

   - menú y lista,

   - texto escrito (número, palabra clave, código),

   - botón o fila pulsada de un mensaje viejo,

   - la IA que clasifica (no debe ofrecer lo apagado),

   - consultas del ejecutor,

   - la sesión que quedó a medias en ese flujo (se saca con una salida clara, sin perder la conversación; los estados terminales no se tocan),

   - páginas y API.

  

   Apagado = respuesta explícita («por ahora solo…»), nunca silencio ni un 500.

  

126. **[O] Estado persistido.** Antes de apagar, decidir qué pasa con lo ya guardado (sesiones en ese flujo, datos). Se prueba en las dos direcciones: apagar con una sesión a medias y volver a encender.

  

127. **[O] Pruebas.** Cada bandera lleva una prueba con la bandera encendida y otra apagada en cada punto de entrada de la regla 125, y una prueba del valor por defecto con la variable sin definir. Se alterna la variable en la prueba (`vi.stubEnv`), no se mockea el lector. Los archivos de apagado se nombran `*-disabled.test.ts`, uno por capa que consulta la bandera.

  

128. **[G] Varios servicios con el mismo gate → un registro** (`ServiceCatalog`), consultado por menú, routing, despacho y ejecutor.

   - Clase base con métodos sobrescribibles solo si los servicios difieren en dos o más comportamientos reales (respuesta de apagado, limpieza, validación). Si solo cambia el gate, basta un registro de objetos con un campo `enabled`.

   - El registro NO elimina la regla 125: cada punto de entrada de routing sigue consultando el gate. En el bot, `first-contact.ts` y `main-menu.ts` suman 12 comprobaciones `isEnabled()`; el valor de la clase está en que menú, despacho y ejecutor salen del catálogo, no en evitar esas guardias.

   - *Evaluación al 2026-10-14:* con `IncidenciaService` y `ConsultaService` solo se sobrescribe un método (`isEnabled`), idéntico en ambas; `disabledReply` nunca se sobrescribe. Hoy son 0 de 2 comportamientos que difieren; la herencia aún no se paga.

   - *Incidente real (PR #80 del bot, 2026-10-14):* el primer código del flag se subió con JSDoc y `//` (regla 64), un texto dentro de un archivo de lógica (65), una expresión regular en línea (70), un `throw new Error` genérico (82) y prefijos de estado escritos como texto (73). Se retiró de GitHub y se corrigió antes de revisión. **Prueba para que no se repita:** las pruebas de convenciones del repo (regla 109) tienen que correrse antes de abrir el PR.

  

## 15. Idioma de los nombres

  

129. **[O] Las variables de entorno van en inglés, MAYÚSCULAS con guion bajo.** Prefijo por ámbito (`META_`, `MINSA_`, `SANDBOX_`, `RATE_LIMIT_`), bandera `<ÁMBITO>_ENABLED`, booleanos solo `true`/`false`, unidad en el nombre (`_MINUTES`, `_SECONDS`, `_DAYS`). Prohibido mezclar idiomas en una variable.

   - *Pendientes de renombrar (decididos el 2026-10-14, NO se tocan todavía; renombrar exige avisar a infraestructura, regla 100):*

  

     | Actual | Repo | Propuesta |

     |---|---|---|

     | `CITA_ALLOWED_DEPARTAMENTOS` | bot | `APPOINTMENT_ALLOWED_DEPARTMENTS` (o ámbito acordado) |

     | `IA_POC_HABILITADA` | backend | `AI_POC_ENABLED` |

     | `PLAZO_ATENCION_DIAS` | backend | `ATTENTION_DEADLINE_DAYS` |

     | `VIGENCIA_RESOLUCION_DIAS` | backend | `RESOLUTION_VALIDITY_DAYS` |

     | `PLAZO_AVISO_HORAS` | backend | `NOTICE_DEADLINE_HOURS` |

  

130. **[O] El vocabulario del dominio MINSA va en español** (incidencia, establecimiento, plazo, reclamante, derivar, resolver) **y los términos técnicos en inglés** (service, repository, handler, catalog, build, is, enabled). En un nombre compuesto cada palabra conserva su idioma, sin partir una palabra de dominio: `isIncidenciasEnabled`, nunca `isIncidentsEnabled`.

  

131. **[O] En el backend (`minsa-incidencias-backend`) el código es todo en español**, incluidos los verbos (`listarPorVencer`), con sufijos técnicos de archivo en inglés (`.service`, `.routes`, `.enum`, `.types`). En el bot rige la regla 130. Los archivos nuevos siguen la convención de la carpeta en que viven.

  

132. **[O] No se renombra lo existente solo por consistencia.** Se corrige al tocar el archivo por otra razón (regla 104). La excepción son las variables de entorno: se acuerdan con infraestructura y se hacen aparte.

  

133. **[G] Los valores persistidos no se renombran** (regla 76), aunque el nombre del enum cambie de idioma.

  

## 16. Nombres de archivos de documentación

  

134. **[O] Los archivos de `docs/` se nombran en el mismo idioma que el README del proyecto** (hoy español), en kebab-case, minúsculas, sin acentos, espacios ni mayúsculas. Excepciones: `README.md`, `CLAUDE.md`, `AGENTS.md` y siglas de herramienta (`ci.md`).

  

135. **[O] Patrón `<tema>[-<detalle>].md`.** Los flujos del bot empiezan con `flujo-` (`flujo-cita.md`); las guías de pruebas van en `docs/qa/`; lo de despliegue, en `despliegue-<entorno>.md`.

  

136. **[O] El título (`#`) y el nombre del archivo dicen lo mismo.** Si el título cambia de idioma o de tema, el archivo se renombra y se actualizan los enlaces en el mismo commit.

  

137. **[O] Al renombrar un documento, buscar sus enlaces entrantes** (README, `AGENTS.md`, CI, otros documentos) y corregirlos en el mismo commit. Va en un commit aparte para no perder el historial por archivo.

  

138. **[G] Los documentos generados** (diccionario de datos) siguen la misma regla: se cambia el generador, no se renombra a mano el resultado.

   - *Estado al 2026-10-14 (bot), inventario:* `docs/despliegue-minsa.md`, `flujo-cita.md` y `flujo-incidencia.md` están en español; `observability.md`, `out-of-scope-channels.md`, `technical-gaps.md` y `qa/manual-test-playbook.md` están en inglés con contenido en español; `prisma/diccionario/generado/Diccionario de datos.md` tiene espacios y mayúscula. El backend no tiene `docs/` (solo tres `README.md`).

   - *Renombres ejecutados el 2026-10-14 (a la espera de commit/PR):*

  

     | Antes | Ahora |

     |---|---|

     | `docs/observability.md` | `docs/observabilidad.md` |

     | `docs/out-of-scope-channels.md` | `docs/canales-fuera-de-alcance.md` |

     | `docs/technical-gaps.md` | `docs/brechas-tecnicas.md` (solo brechas abiertas) |

     | `docs/qa/manual-test-playbook.md` | `docs/qa/guia-pruebas-manuales.md` |

     | `prisma/diccionario/generado/Diccionario de datos.md` | `prisma/diccionario/generado/diccionario-de-datos.md` (cambió `generar.mjs`) |

  

     Los renombres obligaron a cambiar la ruta en tres archivos que no son `.md`: `tests/lib/observability/events.test.ts`, `tests/lib/fsm/flows/out-of-scope/out-of-scope-channels.test.ts` y `prisma/diccionario/generar.mjs`. Antes de renombrar un documento se busca también quién lo lee por ruta en `tests/` y `scripts/`, no solo enlaces en `.md` (regla 137).

  

## 17. Complementos

  

139. **[O] Un inventario de lectores de entorno que se comprueba con una prueba** (completa la regla 21): `process.env.` solo puede aparecer en el módulo central. *Estado al 2026-10-14 en el bot:* 7 variables se leen fuera de un módulo central (`SANDBOX_ENABLED` dentro del handler, `SANDBOX_USE_REAL_MINSA` en dos archivos, `SANDBOX_USE_REAL_RENIEC`, `SANDBOX_USE_REAL_AI`, entre otras) con tres estilos de lectura y tres normalizaciones distintas.

  

140. **[O] Tabla de valores por defecto para toda variable nueva** en el README: variable, valor por defecto, qué pasa si falta.

  

141. **[O] El README y `.env.example` se actualizan en el mismo PR que cambia la variable** (completa la regla 47). El README del bot documenta la bandera nueva en cinco lugares; no se deja ninguno atrás.

  

## 18. Idioma de la documentación

  

142. **[O] Antes de crear un archivo `.md` nuevo, se pregunta al usuario si se redacta en español o en inglés.** Aplica a todos los `.md` salvo `README.md`, `CLAUDE.md`, `AGENTS.md` y siglas de herramienta (`ci.md`). Una sola pregunta, y se espera la respuesta; no se asume.

   - El ambiente solo sugiere el valor por defecto: en el bot y en `minsa-incidencias-backend`, español (regla 134). Otro proyecto u otro ambiente puede pedir inglés, y lo decide el usuario.

   - La respuesta fija el idioma del **nombre** del archivo y de su **contenido** (regla 136: título y nombre dicen lo mismo).

   - Agregada el 2026-10-14 tras unificar los nombres de `docs/` (regla 138), que mezclaban español e inglés.

   - Al renombrar un `.md`, se busca también quién lo lee por ruta en `tests/` y `scripts/` (regla 137).

  

## 19. Reutilización y diseño (análisis del 2026-10-14, solo anotado)

  

> **Estado: anotado, no aplicado al código.** Se midió el bot (`lib/` y `app/`: 364 archivos, 16.910 líneas) con un script de lectura (no cambia nada) y se contrastó a mano cada hallazgo. Las cifras son aproximadas (regex sobre texto, no el analizador del lenguaje); se repiten antes de aplicar. Todas las reglas de esta sección son **[G]**: se aplican al tocar el archivo (regla 132) o al arrancar un proyecto nuevo.

>

> **Calibración:** lo que ya reforzaron las reglas 65-75 funciona. Expresiones regulares en línea fuera de `lib/constants/regex/`: **0**. Bloques de 6 líneas repetidos entre archivos: **2 pares**. El problema que queda no es texto copiado: es **estructura secuencial**.

  

### 19.1 Hallazgos medidos

  

La tabla completa (H1 a H8, con archivo y cifra de cada uno) vive en [[Correcciones detectadas]]. Aquí solo quedan las reglas que salen de ellas.

  

### 19.2 Reglas

  

143. **[G] Despacho por tabla, no por `switch` de un caso por estado.** Un `Record<Estado, Manejador>` por flujo, tipado para que el compilador falle si falta un estado. El manejador declara el tipo de evento que recibe (entrante o resultado de consulta), de modo que desaparece el `as` en cada `case`. *(H1)*

  

144. **[G] Una secuencia de condiciones que decide qué hacer es una lista ordenada de reglas con nombre.** Cada regla es `{ nombre, coincide(evento), ejecuta }`; el recorrido toma la primera que coincide. El orden queda declarado en un solo sitio y cada regla se prueba sola. Aplica a `handleMainMenu`, a las guardas de `handleTurn` y a cualquier función de más de 60 líneas que sea una cadena de `if`. *(H2)*

  

145. **[G] Clases solo cuando hay estado o ciclo de vida compartido** (catálogo de servicios, buffer, candado). Para variar comportamiento se prefiere unión discriminada + mapa + función pura; es lo que en TypeScript cubre lo que en Python se resolvería con clases. Una subclase solo se justifica si difiere en **dos o más** comportamientos reales (regla 128). *(H4)*

  

146. **[G] El gesto que se repite junto con su condición previa se declara una vez.** Si cada regla de una lista necesita «¿su servicio está encendido?», la regla declara su servicio y la comprobación se hace en el recorrido, no en cada `if`. *(H3)*

  

147. **[G] Un objeto que se arma igual en varios sitios (una nota de turno, una respuesta) es una función constructora con nombre**, en el mismo módulo que su tipo (`confirmationUnknownNote(...)`). Los valores que llegan del cable de un tercero (`"text"`, `"image"` de Meta) tienen su propio enum, separado del enum interno (regla 76). *(H5)*

  

148. **[G] Duraciones y tamaños con unidades compartidas:** `MINUTE_MS`, `HOUR_MS`, `DAY_MS` y `MB` en `lib/constants/limits/`, y **una constante por concepto de negocio** (ventana de 24 horas de WhatsApp, tamaño máximo de imagen) que todos importan. Si dos capas necesitan valores distintos (5 MB en servidor, 3 MB en el navegador), es una decisión del responsable y se nombran por separado. *(H6)*

  

149. **[G] El entorno se lee en un solo módulo con un esquema** (`lib/config/env.ts` con zod): normaliza una vez (`trim`, minúsculas, `=== "true"`), valida al arrancar y expone campos ya tipados. Es la forma de cumplir las reglas 21, 22, 121 y 139. *(H7)*

  

150. **[G] Validación en toda frontera con esquema y un tipo reutilizable.** HTTP, payload del webhook y entorno usan zod. Dentro de `parsing/`, un `Validador<T> = (entrada: unknown) => Resultado<T, Motivo>` común, para componer validaciones en lugar de escribir otra función `is*`/`parse*` por campo. Las rutas que repiten una precondición (buscar la conversación, 404) la reciben de un envoltorio (`withConversation`). *(H8)*

  

151. **[G] Proyecto nuevo: las reglas existen desde el primer commit.** Esqueleto mínimo: `lib/{constants/{textos,regex,limits,prompts},enums,errors,utils,config}`, `apiError`, lector de entorno con esquema (149), despacho por tabla (143) y las pruebas de convenciones (regla 109) escritas antes que la primera función de negocio. Es más barato que remediar 364 archivos después (regla 107).

  

152. **[G] Repetir la medición antes de cada revisión grande y anotar los números aquí.** Esta sección es la bitácora: qué se midió, cuánto dio y qué se decidió, para comparar en el siguiente proyecto.

  

## 20. Instrucciones para la IA: no generes esto, implementa así

  

> Cada instrucción corresponde a una corrección de [[Correcciones detectadas]] y a una regla de la sección 19. Son **agnósticas del lenguaje**: los pasos valen para TypeScript, Python u otro; el ejemplo se adapta. La IA las aplica **al generar** código nuevo y al tocar código existente, para no repetir el patrón.

  

### Prompt maestro (se pega al inicio de cualquier sesión de generación)

  

```

Antes de escribir código, para cada función, manejador o archivo nuevo:

1. Busca primero lo que ya existe (utilidad, constante, enum, validador, componente) y reutilízalo.

   Si no existe, créalo en su carpeta de constantes, enums, errores o utilidades; no en el archivo de lógica.

2. Si vas a escribir tres o más ramas que eligen según un estado, un tipo o una palabra,

   no escribas una cadena de if ni un switch: declara una tabla o una lista ordenada de reglas.

3. Todo literal que se compara o se repite (texto, estado, valor de un tercero, número con significado,

   duración, tamaño) es un enum o una constante con nombre.

4. Toda entrada que cruza una frontera (HTTP, webhook, entorno, archivo) se valida con un esquema

   antes de usarse. No escribas validaciones a mano repetidas.

5. No crees clases para variar un solo comportamiento ni «por si acaso».

6. Una función de más de 60 líneas o con más de 8 ramas se parte antes de entregarla.

7. Si la decisión es de contenido o de negocio (redacción de mensajes, límites distintos por capa,

   banderas, valores por defecto), pregunta al responsable. No la tomes tú.

8. Escribe cláusulas de guarda: comprueba al inicio cada condición que impide continuar,

   lanza su error específico o retorna, y deja el camino feliz sin anidar al final.

   No uses else después de throw o return y no pases de 2 niveles de anidamiento.

9. Espera toda promesa (o márcala void a propósito), agrupa las lecturas independientes en Promise.all
   y deja el catch con unknown; nunca any.

10. No mutes lo que recibes: trabaja sobre una copia o devuelve un objeto nuevo. Toda decisión por plazo
    o vencimiento recibe el instante como parámetro; no llames a new Date() ni a Date.now() dentro del cálculo.

11. Lo que se puede repetir (webhook, botón) se procesa una sola vez: reclama el messageId y usa el candado
    por conversación antes de cambiar estado o crear un registro.

Antes de entregar, responde la Confirmación previa (sección 20.2). Si alguna respuesta es «No», corrige primero.

```

  

### 20.1 Instrucciones por corrección

  

**P1 · Despacho por estado** *(H1, regla 143)*

- **No generes:** un `switch` o una cadena de `if` con un `case` por estado donde cada rama convierte el evento (`as TipoEvento`).

- **Implementa:** 1) un enum con todos los estados; 2) una tabla `estado → manejador` tipada para que falte un estado y el compilador falle; 3) cada manejador declara el tipo de evento que recibe, sin conversión; 4) el despachador solo busca en la tabla.

- **Verifica:** agregar un estado nuevo sin manejador debe romper la compilación o una prueba.

  

**P2 · Cadena de condiciones** *(H2, regla 144)*

- **No generes:** una función larga con `if (A) return …; if (B) return …; if (C) return …` donde el orden importa pero no está declarado.

- **Implementa:** 1) una lista ordenada de reglas `{ nombre, coincide(evento), ejecuta }`; 2) el recorrido toma la primera que coincide; 3) cada regla se prueba sola; 4) el orden de la lista es la documentación de la prioridad.

- **Verifica:** una función de decisión no pasa de 60 líneas ni de 8 ramas.

  

**P3 · Precondición repetida** *(H3, regla 146)*

- **No generes:** la misma comprobación previa («¿el servicio está encendido?», «¿existe el recurso?») copiada dentro de cada rama.

- **Implementa:** que la regla declare su dependencia (`servicio`, `recurso`) y que el recorrido o un envoltorio haga la comprobación una sola vez.

- **Verifica:** buscar la comprobación; debe aparecer en un único sitio.

  

**P4 · Clases** *(H4, regla 145)*

- **No generes:** una clase base con subclases que solo sobrescriben un método, ni una clase para agrupar funciones sin estado.

- **Implementa:** funciones puras, unión discriminada y mapa. Una clase solo si hay estado o ciclo de vida compartido (catálogo, buffer, candado) o si las subclases difieren en dos o más comportamientos.

- **Verifica:** por cada subclase, listar qué sobrescribe; si es una sola cosa, se reemplaza por un registro de objetos con un campo.

  

**P5 · Literales, notas y valores de terceros** *(H5, regla 147)*

- **No generes:** el mismo texto de estado o tipo escrito en varios sitios, ni el mismo objeto de nota armado a mano en cada uso.

- **Implementa:** 1) un enum por conjunto de valores; 2) una función constructora con nombre para el objeto que se repite, junto a su tipo; 3) un enum aparte para los valores que llegan del cable de un tercero (el del tercero y el interno no se mezclan).

- **Verifica:** buscar `=== "…"` y `kind: "…"` con texto; no debe haber ninguno fuera del enum.

  

**P6 · Duraciones y tamaños** *(H6, regla 148)*

- **No generes:** `24 * 60 * 60 * 1000`, `5 * 1024 * 1024` ni otro número con unidad escrito en la lógica.

- **Implementa:** constantes de unidad (`MINUTE_MS`, `HOUR_MS`, `DAY_MS`, `MB`) y **una constante por concepto de negocio** (ventana de 24 horas, tamaño máximo de imagen) que todos importan.

- **Pregunta antes:** si dos capas parecen necesitar valores distintos (servidor 5 MB, navegador 3 MB), es decisión del responsable.

  

**P7 · Entorno** *(H7, regla 149)*

- **No generes:** `process.env.X` (o su equivalente) ni `=== "true"` fuera del módulo de configuración.

- **Implementa:** un módulo de configuración con esquema que normaliza una vez, valida al arrancar y expone campos tipados. Una variable nueva se agrega ahí, a `.env.example` y al README en el mismo cambio.

- **Pregunta antes:** si la función lleva bandera y con qué valor por defecto (regla 120).

  

**P8 · Validación** *(H8, regla 150)*

- **No generes:** una función `is*`/`parse*`/`validate*` nueva por cada campo, ni un bloque de precondición copiado entre rutas.

- **Implementa:** esquema (zod u otro) en toda frontera; un tipo `Validador<T>` que devuelve `Resultado<T, Motivo>` para componer validaciones; un envoltorio para las precondiciones comunes de las rutas.

- **Verifica:** antes de escribir un validador, buscar si ya existe uno que haga exactamente lo mismo (regla 79).

  

**P9 · Anidamiento y cláusulas de guarda** *(reglas 153-156)*

- **No generes:** `if` dentro de `if` con el camino feliz en el nivel más profundo, ni un `else` después de un `throw` o `return`.

- **Implementa:** 1) lista las condiciones que impiden continuar, en orden de dependencia; 2) escribe cada una al inicio como `if (!condición) throw new ErrorEspecifico(...)` o `return`; 3) deja la lógica principal al final, en el nivel base de la función; 4) si una guarda necesita varias líneas, extráela a una función con nombre.

- **Verifica:** ninguna función nueva supera 2 niveles de anidamiento y no queda ningún `else` tras `throw` o `return`; se revisa a mano en el cambio.

**P10 · Contratos y tipos fuera del código ejecutable** *(regla 157)*

- **No generes:** un `export interface` o `export type` dentro de un `.service.ts`, `.routes.ts` o `.repository.ts` que otros módulos tengan que importar, ni un import de tipos sin la palabra `type`.

- **Implementa:** 1) el contrato que cruza archivos va en `src/types/[modulo].types.ts`; 2) el archivo ejecutable lo consume con `import type { ... } from "@/types/[modulo].types.js"`; 3) un tipo auxiliar que solo usa una función de ese archivo queda ahí, sin `export`.

- **Verifica:** `grep -rE "^export (type|interface)" src --include=*.service.ts --include=*.routes.ts --include=*.repository.ts` no devuelve nada en archivos nuevos o tocados; `tsc` en verde (`verbatimModuleSyntax` ya obliga a `import type`).

  Ejemplo de lo que no se genera (el contrato vive en el archivo ejecutable):

  ```ts
  import { consultarCaso } from "@/repositories/incidencia.repository.js";

  export interface ResumenDeCaso {
    codigo: string;
    estado: EstadoCaso;
    diasParaVencer: number;
  }

  export async function resumirCaso(codigo: string): Promise<ResumenDeCaso> {
    const fila = await consultarCaso(codigo);
    return { codigo: fila.codigo, estado: fila.estado, diasParaVencer: fila.diasParaVencer };
  }
  ```

  Ejemplo de lo que se implementa:

  ```ts
  import type { EstadoCaso } from "@/enums/estado-caso.enum.js";

  export interface ResumenDeCaso {
    codigo: string;
    estado: EstadoCaso;
    diasParaVencer: number;
  }
  ```

  ```ts
  import { consultarCaso } from "@/repositories/incidencia.repository.js";
  import type { ResumenDeCaso } from "@/types/incidencia.types.js";

  type FilaAjustada = Awaited<ReturnType<typeof consultarCaso>>;

  export async function resumirCaso(codigo: string): Promise<ResumenDeCaso> {
    const fila: FilaAjustada = await consultarCaso(codigo);
    return { codigo: fila.codigo, estado: fila.estado, diasParaVencer: fila.diasParaVencer };
  }
  ```

  Estructura: `src/types/incidencia.types.ts` (contrato), `src/services/incidencia.service.ts` (lógica). `FilaAjustada` es el tipo auxiliar privado permitido: sin `export` y usado por una sola función.

  

**P11 · Asincronía y errores tipados** *(reglas 38, 39, 85, 158, 159)*

- **No generes:** una promesa sin `await` ni `void`, `await` en serie de lecturas que no dependen una de otra, ni `catch (e: any)`.

- **Implementa:** 1) agrupa las lecturas independientes en `Promise.all`; 2) en el `catch`, deja `unknown` y discrimina con `instanceof` contra las clases de `errors/` antes de leer una propiedad; 3) si el orden importa (enviar varios mensajes en secuencia), usa un bucle con `await` dentro de una sola función con nombre.

- **Verifica:** cero `catch (e: any)`; ninguna llamada a una función `async` queda sin `await` ni `void`; las lecturas independientes no se esperan en serie.

  

**P12 · Inmutabilidad y tiempo explícito** *(reglas 160-162)*

- **No generes:** `session.slots.x = 1` sobre la sesión recibida, `items.push(...)` sobre un arreglo parámetro, ni `new Date()` / `Date.now()` dentro de un cálculo de plazo o vencimiento.

- **Implementa:** 1) copia al entrar y escribe solo en la copia (`const next = cloneSession(session)`), o devuelve un objeto nuevo con `{ ...slots, clave: valor }`; 2) la función que decide por plazo recibe `ahora` como parámetro, con el tipo que ya usa su módulo, y el valor por defecto va solo en el punto de entrada; 3) el día y la hora de Lima salen del módulo único de reloj.

- **Verifica:** una prueba que pasa la entrada, ejecuta la función y comprueba que la entrada sigue igual (copia con `structuredClone` y `toEqual`); las pruebas de vencimiento pasan `ahora` explícito, no dependen del reloj de la máquina ni de `setTimeout`, y se ejecutan también con `TZ=America/Lima` y con `TZ=UTC`.

  

**P13 · Idempotencia en entradas repetibles** *(reglas 163-164)*

- **No generes:** un manejador de webhook o de botón que cambie estado o cree un registro sin comprobar si ese `messageId` ya se procesó, ni una ventana de tiempo contada desde un instante que no se guarda.

- **Implementa:** 1) reclama el `messageId` antes de ejecutar nada (`inboundDedupe.claim`); 2) ejecuta el turno dentro del candado por conversación; 3) toda creación de registro que el bot pueda reintentar lleva una clave de idempotencia (única en la base); 4) guarda el instante del último mensaje entrante y calcula la ventana a partir de él.

- **Verifica:** una prueba que entrega el mismo `messageId` dos veces y comprueba un solo efecto, y otra que lanza dos turnos a la vez para la misma conversación y comprueba que se ejecutan en serie.

**P14 · Firmas y confusión de algoritmo** *(reglas 31, 34, 167)*

- **No generes:** `jwt.verify(token, clave)` sin fijar `algorithms`, leer el algoritmo de la cabecera entrante, ni entregar una clave pública a un verificador que acepte `HS256`.

- **Implementa:** 1) el algoritmo permitido en una constante; 2) `{ algorithms, issuer, audience }` en toda verificación; 3) la carga verificada se valida con un esquema; 4) el verificador vive en un adaptador (regla 6).

- **Verifica:** una prueba con un token `alg: none` y otro firmado en `HS256` con la clave pública como secreto; ambos se rechazan.

  

**P15 · Reintentos con retroceso y azar** *(reglas 39, 168, 169)*

- **No generes:** reintentos inmediatos, esperas fijas (`sleep(2000)`), ni reintentos de un `4xx`.

- **Implementa:** 1) un predicado `esReintentable`; 2) la espera `aleatorio(0, min(máxima, base × 2^intento))` con el azar como parámetro; 3) el tope de intentos en `constants/limits/`; 4) relanzar el último error al agotarse.

- **Verifica:** ante un `400` o `401` falla en el primer intento sin esperar; ante un `503` las esperas crecen, varían y no superan el tope.

  

**P16 · KPIs y cortes por día con zona IANA** *(reglas 165, 166)*

- **No generes:** `DATE(creado_en)` en UTC crudo, tablas manuales de horario de verano, ni desplazamientos fijos.

- **Implementa:** 1) el instante en `TIMESTAMPTZ` y la zona como identificador IANA; 2) convertir a la zona antes de truncar el día.

- **Verifica:** un evento a las 23:30 locales cuenta en el día local, también en una fecha de horario de verano si la zona lo tiene.

  

### 20.2 Confirmación previa a entregar

  

La IA responde cada punto con **Sí**, **No** o **No aplica**. Un «No» se corrige antes de entregar; un «No aplica» se justifica en una línea.

  

- [ ] ¿Busqué lo que ya existía antes de crear una utilidad, constante, enum o validador?

- [ ] ¿Ninguna decisión por estado, tipo o palabra quedó como cadena de `if` o `switch` de un caso por valor? (P1, P2)

- [ ] ¿La comprobación previa repetida está declarada una sola vez? (P3)

- [ ] ¿Ninguna clase nueva varía un solo comportamiento? (P4)

- [ ] ¿Cero literales de estado, tipo o valor de tercero fuera de un enum? ¿Los objetos repetidos tienen función constructora? (P5)

- [ ] ¿Cero números con unidad escritos en la lógica y una sola constante por concepto? (P6)

- [ ] ¿Cero lecturas de entorno fuera del módulo de configuración? (P7)

- [ ] ¿Toda entrada de una frontera se valida con esquema y no con una función nueva a mano? (P8)

- [ ] ¿Ninguna función pasa de 60 líneas ni de 8 ramas?

- [ ] ¿Los tipos que cruzan archivos están en `src/types/` y no exportados desde un servicio, ruta o repositorio? (P10)

- [ ] ¿Ninguna promesa quedó sin `await` ni `void`, las lecturas independientes van en `Promise.all` y ningún `catch` usa `any`? (P11)

- [ ] ¿Ninguna función muta lo que recibe, y toda decisión por plazo recibe `ahora` en vez de leer el reloj? (P12)

- [ ] ¿Lo que se puede repetir (webhook, botón) se procesa una sola vez, con prueba del mismo `messageId` dos veces? (P13)

- [ ] ¿Toda verificación de firma fija el algoritmo en el servidor y rechaza `none`? (P14)

- [ ] ¿Los reintentos son solo de fallos transitorios, con retroceso exponencial y azar? (P15)

- [ ] ¿Los cortes por día convierten a la zona IANA antes de truncar? (P16)

- [ ] ¿Las precondiciones están como cláusulas de guarda al inicio, sin `else` tras `throw`/`return` y con máximo 2 niveles de anidamiento? (P9)

- [ ] ¿Las decisiones de contenido o de negocio las tomó el responsable, no yo?

- [ ] ¿Corrí las pruebas de convenciones del repositorio y pasan? (regla 109)