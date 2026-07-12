# Referencia de la API REST

Todos los endpoints cuelgan de `/api/v1`. La especificación interactiva
completa (con "probar" incluido) está siempre disponible en
**`/docs`** (Swagger UI) o **`/openapi.json`** mientras el servidor está
en marcha — este documento es un resumen navegable, no sustituye a esa
especificación autogenerada.

Convenciones generales:

- Los importes se leen y escriben en **euros** (número con decimales); por
  dentro se guardan en céntimos enteros.
- Las fechas son cadenas ISO `AAAA-MM-DD`.
- Los tipos de IVA/retención son porcentajes normales (`21`, no `0.21`).
- Los errores devuelven `{"detail": "mensaje"}` con el código HTTP que
  corresponda (`401`, `403`, `404`, `409`, `422`...).

## Autenticación

Casi todos los endpoints requieren sesión. La sesión es una cookie
(`contalibre_sesion`, httponly) que se obtiene al hacer login o registro;
los clientes HTTP normales (navegador, `httpx`, `requests` con `Session`)
la reenvían solos en peticiones siguientes.

Si tu usuario pertenece a más de una empresa, indica cuál quieres usar en
cada petición con la cabecera `X-Empresa-Id: <id>` (si la omites, se usa
la primera empresa a la que perteneces).

```bash
# Registro (crea usuario + empresa + sesión)
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/registro \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@email.com","password":"contraseña123","empresa_nombre":"Mi Empresa"}'

# Peticiones siguientes, reutilizando la cookie
curl -b cookies.txt http://localhost:8000/api/v1/cuentas
```

### `auth` — cuenta y sesión

| Método y ruta | Body | Descripción |
|---|---|---|
| `POST /auth/registro` | `{email, password, nombre?, empresa_nombre}` | Crea usuario + empresa (tú como admin) + sesión. `201`. |
| `POST /auth/login` | `{email, password}` | Inicia sesión. Bloquea temporalmente tras 5 fallos en 15 min (`429`). |
| `POST /auth/logout` | — | Cierra la sesión actual. `204`. |
| `GET /auth/me` | — | Perfil del usuario autenticado y sus empresas (`{id, email, nombre, empresas: [{id, nombre, rol}]}`). |
| `POST /auth/olvide-password` | `{email}` | Genera un token de restablecimiento (se registra en la consola del servidor). Siempre `202`, no revela si el email existe. |
| `POST /auth/restablecer-password` | `{token, password_nueva}` | Consume el token (caduca en 1h) e invalida todas las sesiones del usuario. `204`. |
| `PUT /auth/password` | `{password_actual, password_nueva}` | Cambia la contraseña estando autenticado. `204`. |

### `empresas` — empresas y usuarios

| Método y ruta | Body | Descripción |
|---|---|---|
| `GET /empresas` | — | Empresas del usuario autenticado y su rol en cada una. |
| `POST /empresas` | `{nombre, nif?}` | Crea una empresa nueva; el usuario queda como admin. `201`. |
| `GET /empresas/{id}/exportar` | — | (solo admin) Descarga un `.zip` con una copia consistente de la base de datos de esa empresa. |
| `GET /empresas/{id}/usuarios` | — | Lista los usuarios de la empresa y su rol (requiere pertenecer a ella). |
| `POST /empresas/{id}/usuarios` | `{email, rol}` | (solo admin) Vincula un usuario **ya registrado** a la empresa. `rol` es `admin` o `editor`. `201`. |
| `DELETE /empresas/{id}/usuarios/{usuario_id}` | — | (solo admin) Quita a un usuario de la empresa. No puedes quitarte a ti mismo. `204`. |

## `cuentas` — Plan General Contable

| Método y ruta | Query/Body | Descripción |
|---|---|---|
| `GET /cuentas` | `?q=` (opcional) | Lista cuentas; `q` busca por prefijo de código o texto del nombre. |
| `POST /cuentas` | `{codigo, nombre}` | Crea una cuenta. `409` si el código ya existe. `201`. |
| `PUT /cuentas/{codigo}` | `{codigo, nombre}` | Renombra (el `codigo` del body debe coincidir con el de la ruta). |
| `DELETE /cuentas/{codigo}` | — | `409` si la cuenta tiene apuntes contabilizados. `204`. |

## `asientos` — Diario

| Método y ruta | Query/Body | Descripción |
|---|---|---|
| `GET /asientos` | `?desde=&hasta=&cuenta=&limite=200` | Lista asientos (`cuenta` filtra por prefijo, vía sus apuntes). |
| `GET /asientos/{id}` | — | Detalle de un asiento con sus apuntes. |
| `POST /asientos` | `{fecha, concepto, apuntes:[{cuenta, concepto?, debe?, haber?}, ...]}` (mín. 2 líneas) | Crea un asiento. `422` si no cuadra, tiene importe cero, o mezcla debe+haber en una línea. `201`. |
| `DELETE /asientos/{id}` | — | `409` si pertenece a una factura, a una amortización, o su ejercicio está cerrado. `204`. |

## `terceros` — Clientes y proveedores

| Método y ruta | Query/Body | Descripción |
|---|---|---|
| `GET /terceros` | `?q=&tipo=` | `tipo` es `cliente` o `proveedor` (incluye los `ambos`). |
| `POST /terceros` | `{tipo, nif, nombre, direccion?, email?, telefono?}` | `409` si el NIF ya existe. `201`. |
| `PUT /terceros/{id}` | mismo cuerpo que `POST` | Actualiza los datos. |
| `DELETE /terceros/{id}` | — | `409` si tiene facturas registradas. `204`. |

## `facturas` — Facturación

| Método y ruta | Query/Body | Descripción |
|---|---|---|
| `GET /facturas` | `?tipo=&estado=&desde=&hasta=` | `tipo`: `emitida`/`recibida`. `estado`: `pendiente`/`pagada`. |
| `GET /facturas/{id}` | — | Detalle con líneas. |
| `POST /facturas` | `{tipo, numero, fecha, tercero_id, cuenta_contrapartida?, retencion_pct?, lineas:[{descripcion, base, tipo_iva}, ...]}` | Contabiliza automáticamente. `cuenta_contrapartida` por defecto `700` (emitida) o `600` (recibida). `409` si el número ya existe para ese tipo. `201`. |
| `POST /facturas/{id}/liquidar` | `{fecha, cuenta_tesoreria?}` (`cuenta_tesoreria` por defecto `572`) | Registra el cobro/pago. `409` si ya estaba pagada. |
| `DELETE /facturas/{id}` | — | Elimina la factura y sus asientos vinculados (el de la factura y, si existe, el del cobro/pago). `204`. |

## `activos` — Inmovilizado

| Método y ruta | Query/Body | Descripción |
|---|---|---|
| `GET /activos` | — | Lista con amortizado y valor neto. |
| `GET /activos/{id}` | — | Detalle con histórico de dotaciones. |
| `POST /activos` | `{nombre, fecha_adquisicion, valor, valor_residual?, vida_util_anios, cuenta_activo?, cuenta_amort_acum?, cuenta_gasto?}` | `422` si el valor residual ≥ valor. `201`. |
| `POST /activos/{id}/amortizar` | `{ejercicio}` | Genera la dotación de ese año (lineal, con prorrateo/ajuste). `409` si ya está dotado o totalmente amortizado; `422` si el ejercicio es anterior a la compra. |
| `DELETE /activos/{id}/amortizaciones/{ejercicio}` | — | Elimina una dotación y su asiento. `204`. |
| `DELETE /activos/{id}` | — | `409` si tiene dotaciones. `204`. |

## `informes` — Consultas contables

| Método y ruta | Query | Descripción |
|---|---|---|
| `GET /informes/panel` | — | Resumen general (resultado, tesorería, pendientes de cobro/pago, IVA del trimestre actual). |
| `GET /informes/mayor` | `?cuenta=&desde=&hasta=&formato=` | `cuenta` (obligatoria) acepta prefijo. `formato`: `json` (por defecto), `pdf` o `excel`. |
| `GET /informes/sumas-saldos` | `?desde=&hasta=&formato=` | |
| `GET /informes/pyg` | `?desde=&hasta=&formato=` | Pérdidas y ganancias. |
| `GET /informes/balance` | `?hasta=&formato=` | Balance de situación con la estructura oficial de epígrafes del PGC. |
| `GET /informes/iva` | `?ejercicio=&trimestre=` (ambos obligatorios) | Resumen de IVA repercutido/soportado del trimestre (estilo modelo 303, sin exportación). |

`formato=pdf|excel` en `mayor`, `sumas-saldos`, `pyg` y `balance` devuelve
el fichero descargable en vez de JSON.

## `ejercicios` — Cierre y apertura

| Método y ruta | Descripción |
|---|---|
| `GET /ejercicios` | Estado (abierto/cerrado, fechas, resultado) de cada año con movimientos. |
| `GET /ejercicios/{anio}` | Detalle de un año; incluye `resultado_previsto` si sigue abierto. |
| `POST /ejercicios/{anio}/cerrar` | Regulariza (6/7 contra 129) y salda el balance. `409` si ya está cerrado, o si falta cerrar/abrir un año anterior. |
| `POST /ejercicios/{anio}/abrir` | Reabre los saldos del cierre del año anterior. `409` si el año anterior no está cerrado. |
| `DELETE /ejercicios/{anio}/cierre` | Deshace el cierre (elimina sus asientos). `409` si el año siguiente ya está abierto. |
| `DELETE /ejercicios/{anio}/apertura` | Deshace la apertura. `409` si ese año ya está cerrado. |

## `aeat` — Modelos oficiales simplificados

| Método y ruta | Query | Descripción |
|---|---|---|
| `GET /aeat/303` | `?ejercicio=&trimestre=&formato=` | Liquidación trimestral de IVA por casillas. |
| `GET /aeat/390` | `?ejercicio=&formato=` | Resumen anual (agrega los 4 trimestres). |
| `GET /aeat/347` | `?ejercicio=&formato=` | Operaciones con terceros > 3.005,06 €/año. |

Los tres aceptan `formato=pdf|excel` igual que los informes.

## `bancos` — Conciliación bancaria

| Método y ruta | Body | Descripción |
|---|---|---|
| `POST /bancos/importar` | `{cuenta_tesoreria, contenido}` (`contenido` = texto completo del fichero norma 43) | Importa movimientos (deduplica los ya importados) e intenta conciliarlos automáticamente. `422` si la cuenta no existe o el fichero no tiene registros de movimiento. `201`. |
| `GET /bancos/movimientos` | `?cuenta=&conciliado=&desde=&hasta=` | Lista movimientos importados. |
| `POST /bancos/{id}/conciliar` | `{apunte_id}` | Concilia contra un apunte ya contabilizado. `422` si el importe o la cuenta no coinciden; `409` si el apunte ya estaba usado. |
| `POST /bancos/{id}/conciliar-nuevo` | `{cuenta_contrapartida, concepto?}` | Crea un asiento nuevo y lo concilia. |
| `DELETE /bancos/{id}/conciliacion` | — | Desconcilia (no borra el asiento). |
| `DELETE /bancos/{id}` | — | Elimina el movimiento importado. `409` si está conciliado (desconcilia primero). `204`. |

## `ia` — Asistente y contexto para LLM

| Método y ruta | Body | Descripción |
|---|---|---|
| `GET /ia/contexto` | — | Esquema de datos, convenciones y catálogo de endpoints — pensado como *system prompt* para un LLM. |
| `GET /ia/estado` | — | `{disponible, url, modelo, modelo_descargado, modelos_descargados}` — si Ollama responde y si el modelo configurado está descargado. |
| `POST /ia/preguntar` | `{pregunta, historial?}` | Resuelve una pregunta en lenguaje natural con *tool calling* contra los datos de la empresa activa. `historial` es la lista de mensajes previos (`{role, content}`) de la misma conversación. `503` si Ollama no está disponible. Devuelve `{respuesta, herramientas_usadas}`. |

---

Para el detalle exacto de cada campo (tipos, validaciones, ejemplos
generados) usa siempre `/docs` con el servidor en marcha: esta tabla es un
mapa de alto nivel, la especificación OpenAPI es la fuente de verdad.
