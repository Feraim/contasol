# Cómo funciona ContaLibre

Documento técnico de referencia: arquitectura, modelo de datos y cómo encaja
cada módulo. El README explica *qué* hace el software y cómo arrancarlo; este
documento explica *cómo* está construido por dentro.

## 1. Visión general

ContaLibre es una aplicación monolítica de un solo proceso:

```
Navegador (HTML/CSS/JS sin dependencias)
        │  fetch() a /api/v1/*
        ▼
FastAPI (contalibre/main.py)
        │
        ├── Routers (contalibre/routers/*.py)      → validan la petición HTTP
        ├── Servicios (contalibre/services/*.py)    → lógica de negocio pura
        └── Modelos SQLAlchemy (contalibre/models.py, models_control.py)
        │
        ▼
SQLite (un fichero por empresa + un fichero de control)
```

No hay build step, no hay framework de frontend: `static/index.html` +
`static/app.js` + `static/styles.css` hablan directamente con la API REST vía
`fetch`. El backend es FastAPI + SQLAlchemy 2.0 + Pydantic, sirviendo tanto la
API (`/api/v1/*`) como los ficheros estáticos (`/`).

### Capas del backend

Cada funcionalidad sigue el mismo patrón de tres capas:

1. **Router** (`routers/*.py`): define las rutas HTTP, valida entrada con
   Pydantic (`schemas.py`), inyecta la sesión de base de datos vía
   `Depends(get_db)`, y traduce la salida de los servicios a JSON o a un
   fichero descargable (PDF/Excel).
2. **Servicio** (`services/*.py`): toda la lógica de negocio — validaciones
   contables, cálculos, creación de asientos — vive aquí, no en los routers.
   Los servicios reciben una `Session` de SQLAlchemy ya lista para usar y no
   saben nada de HTTP (usan `HTTPException` de FastAPI para señalar errores
   de negocio, pero no leen ni escriben cabeceras/cookies).
3. **Modelo** (`models.py`): tablas SQLAlchemy. Todos los importes se
   guardan como enteros en **céntimos** (nunca `float`) para que las sumas de
   partida doble cuadren exactamente; los tipos de IVA/retención se guardan
   en centésimas de punto porcentual (`2100` = 21,00 %).

## 2. Multiempresa: aislamiento físico, no por columna

Esta es la decisión de diseño más importante del proyecto. En vez de añadir
una columna `empresa_id` a cada tabla y confiar en que **todas** las
consultas la filtren correctamente, cada empresa tiene **su propio fichero
SQLite**, con el mismo esquema (`models.py`) que ya existía antes de
multiempresa:

```
contalibre_data/
├── control.db            # Empresa, Usuario, Membresia, Sesion (compartida)
└── empresas/
    ├── 1.db               # contabilidad completa de la empresa 1
    ├── 2.db               # contabilidad completa de la empresa 2
    └── ...
```

**Por qué**: con `empresa_id` por columna, un solo `WHERE` olvidado en
cualquiera de los ~40 endpoints filtraría mal y filtraría datos de una
empresa a otra — el fallo más grave posible en una app multiempresa. Con
ficheros separados, esa clase de bug es estructuralmente imposible: si no
tienes el fichero abierto, no puedes ver sus datos, sin importar qué
consulta escribas.

**Cómo se conecta**: `contalibre/database.py` mantiene un `sessionmaker` por
`empresa_id` en un diccionario en memoria (`_sessionmakers`), creado la
primera vez que se accede a esa empresa (y precargando el Plan General
Contable si el fichero es nuevo). El resto del backend (routers, servicios)
**no sabe que existe multiempresa**: reciben una `Session` de SQLAlchemy
exactamente como antes.

### La pieza que conecta todo: `deps.py`

```python
def usuario_actual(...) -> Usuario          # de la cookie de sesión
def membresias_actual(...) -> list[Membresia]  # empresas a las que pertenece
def empresa_actual_id(...) -> int           # cabecera X-Empresa-Id, o la primera
def get_db(empresa_id = Depends(empresa_actual_id)):
    db = sesion_empresa(empresa_id)         # Session de ESA empresa
    yield db
```

Como todos los routers ya hacían `db: Session = Depends(get_db)` desde antes
de multiempresa, añadir usuarios/empresas **no tocó ni una línea** de
`asientos.py`, `facturas.py`, `informes.py`, etc. — solo se redirigió de
dónde importan `get_db` (`database.py` → `deps.py`). Es la razón por la que
esta funcionalidad, siendo la más grande del proyecto, tuvo el diff más
pequeño en proporción a su alcance.

### Autenticación

- `contalibre/auth.py`: hash de contraseñas con PBKDF2-HMAC-SHA256 (260.000
  iteraciones, sal aleatoria de 16 bytes) y tokens de sesión aleatorios de
  32 bytes — todo con `hashlib`/`secrets` de la librería estándar, sin
  dependencias externas.
- Sesión = cookie `contalibre_sesion` (`httponly`, `samesite=lax`, 30 días).
  El token se guarda en la tabla `sesiones` de `control.db`, y
  `deps.py::usuario_actual` comprueba `sesion.creada` contra
  `auth.DURACION_SESION` **en el servidor** en cada petición — no basta con
  que la cookie caduque en el navegador, una sesión vieja se borra y se
  rechaza aunque alguien reenvíe el token a mano.
- `contalibre/ratelimit.py`: bloqueo temporal (5 intentos / 15 minutos, en
  memoria) por email tras logins fallidos consecutivos; se limpia en un
  login correcto.
- Recuperación de contraseña (`routers/auth.py`): como la app es local y no
  tiene servidor de correo, `POST /auth/olvide-password` genera un token de
  un solo uso (tabla `restablecimientos_password`, caduca en 1 hora) y lo
  escribe en el **log del servidor** en vez de enviarlo por email — solo
  quien tiene acceso a la máquina donde corre `contalibre` puede leerlo.
  `POST /auth/restablecer-password` consume el token y cierra todas las
  sesiones activas del usuario (`_invalidar_sesiones`). Estando ya
  autenticado, `PUT /auth/password` cambia la contraseña sin pasar por un
  token.
- Un usuario puede pertenecer a varias empresas (tabla `membresias`, con rol
  `admin` o `editor`); el frontend cambia de empresa activa enviando la
  cabecera `X-Empresa-Id` en cada petición.

### Copia de seguridad bajo demanda

`GET /api/v1/empresas/{id}/exportar` (solo admin) usa la API de backup de
`sqlite3` (`services/backup.py`) para copiar la base de datos de una
empresa a un fichero temporal de forma consistente — no es una copia de
fichero en caliente, que podría corromperse si hay una escritura en curso —
y la devuelve comprimida en un `.zip`.

### Migración desde una instalación de un solo fichero

Si `database.py` encuentra el fichero de una instalación anterior a
multiempresa (variable `CONTALIBRE_DB`, por defecto `contalibre.db`) y no
hay ninguna empresa registrada todavía, lo copia a
`contalibre_data/empresas/1.db` y crea una fila `Empresa` sin usuarios
("huérfana"). El primer usuario que se registra después reclama
automáticamente esa empresa (y cualquier otra huérfana) como administrador,
además de crear la suya propia (`routers/auth.py::_reclamar_empresas_huerfanas`).

## 3. El corazón contable: partida doble

Todo gira en torno a tres tablas (`models.py`):

- **`Cuenta`**: el plan contable (`codigo`, `nombre`). Se precarga con
  `pgc.py` (subconjunto del PGC PYMES) al crear la empresa; el usuario puede
  añadir subcuentas libremente.
- **`Asiento`**: cabecera de un movimiento del diario (`numero` — secuencial
  dentro del año natural —, `fecha`, `concepto`).
- **`Apunte`**: cada línea de un asiento (`cuenta_codigo`, `debe`, `haber`).

La regla de oro vive en `services/asientos.py::crear_asiento_directo`:
suma(debe) tiene que ser exactamente igual a suma(haber) (en céntimos, sin
redondeos), ningún apunte puede tener debe y haber a la vez, y ningún importe
puede ser negativo. **Todo lo demás del sistema** — facturas, amortizaciones,
cierre de ejercicio, conciliación bancaria — termina llamando a esta misma
función para generar sus asientos, así que la integridad contable solo hay
que garantizarla en un sitio.

## 4. Módulos funcionales

### 4.1 Terceros y facturación (`services/facturas.py`)

Un `Tercero` (cliente/proveedor) obtiene automáticamente una subcuenta
`430NNNN` (cliente) o `400NNNN` (proveedor) la primera vez que se le emite o
recibe una factura (`subcuenta_tercero`). Al crear una `Factura`:

1. Se calculan base, cuota de IVA por línea y retención IRPF.
2. Se genera un asiento automático (cliente/proveedor a ingreso/gasto + IVA
   repercutido/soportado + retención si aplica).
3. `liquidar_factura` registra el cobro/pago con un segundo asiento contra
   la cuenta de tesorería indicada.

### 4.2 Inmovilizado (`services/amortizacion.py`)

Amortización lineal con prorrateo por días en el ejercicio de adquisición y
absorción del redondeo en el último ejercicio del plan
(`dotacion_del_ejercicio`). Cada dotación anual genera su propio asiento
(gasto a amortización acumulada) vinculado al activo.

### 4.3 Informes (`services/informes.py`)

Todos parten de `_saldos()`, que suma debe/haber por cuenta en un rango de
fechas. A partir de ahí: libro mayor, sumas y saldos, pérdidas y ganancias
(grupos 6/7) y resumen de IVA por trimestre.

El **balance de situación** clasifica cada cuenta en el epígrafe oficial del
balance abreviado del PGC (`_SECCIONES_ACTIVO`/`_SECCIONES_PASIVO` en
`informes.py`): A) Activo no corriente / B) Activo corriente con sus
apartados I-VII, y A) Patrimonio neto / B) Pasivo no corriente / C) Pasivo
corriente con los suyos. La clasificación sigue siendo por prefijo de
código de cuenta (coincidencia más larga gana, igual que antes), pero ahora
cubre la estructura oficial completa en vez de una agrupación simplificada;
una cuenta que no encaje en ningún epígrafe cae en un cajón "sin
clasificar" del lado que le corresponda por signo de su saldo.

### 4.4 Cierre y apertura de ejercicio (`services/cierre.py`)

Tres asientos generados automáticamente por año:

1. **Regularización**: salda las cuentas de gestión (grupos 6 y 7) contra la
   `129 Resultado del ejercicio`.
2. **Cierre**: salda a cero el resto de cuentas patrimoniales (grupos 1-5,
   incluida la 129 ya regularizada) — matemáticamente siempre cuadra, porque
   la suma de saldos de todo el plan contable es cero por construcción de la
   partida doble.
3. **Apertura** (del ejercicio siguiente): asiento espejo del de cierre
   (mismos importes, debe/haber invertidos), que reabre esos saldos.

El cierre/apertura es **secuencial obligatorio**: no se puede cerrar 2025
sin haber cerrado y abierto 2024 antes. Mientras un ejercicio está cerrado,
`services/asientos.py::validar_ejercicio_abierto` bloquea crear o eliminar
asientos en él. Todo es reversible (`deshacer_cierre`/`deshacer_apertura`)
mientras no se haya tocado el ejercicio contiguo.

### 4.5 Modelos AEAT (`services/aeat.py`)

Construidos sobre el resumen de IVA de `informes.py`:

- **303** (trimestral): casillas 27 (devengado), 28/29/44 (deducible), 46/69
  (resultado), con el sentido ("a ingresar"/"a compensar"/"a devolver").
- **390** (anual): agrega los cuatro trimestres.
- **347**: agrupa facturas por tercero y trimestre; declara los que superan
  3.005,06 €/año, con clave `A` (compras) o `B` (ventas).

Todos llevan un aviso explícito de qué NO cubren (intracomunitario,
importaciones, bienes de inversión, recargo de equivalencia) — son
simplificaciones útiles para consulta, no sustituyen la presentación oficial.

### 4.6 Exportación (`services/exportacion.py`)

Dos funciones genéricas, `a_pdf` (reportlab) y `a_excel` (openpyxl), que
reciben `(título, columnas, filas)` y devuelven bytes. Cualquier router que
quiera ofrecer descarga solo necesita construir esa tabla y llamar a
`exportacion.respuesta(formato, ...)`. Así se añadió exportación a los 4
informes y a los 3 modelos AEAT sin duplicar layout siete veces.

### 4.7 Conciliación bancaria (`services/norma43.py` + `conciliacion.py`)

`norma43.py` interpreta el formato de ancho fijo del cuaderno 43 de la AEB
(registros `22` de movimiento y `23` de concepto ampliado) y produce una
lista de movimientos con importe con signo (positivo = abono, negativo =
cargo). `conciliacion.py`:

- Al importar, descarta duplicados exactos (misma cuenta/fecha/importe/
  documento/referencia) e intenta conciliar automáticamente cada movimiento
  contra un apunte libre de igual importe y fecha en la cuenta de tesorería.
- Lo que no casa solo se concilia a mano: contra un apunte ya existente
  (`conciliar_manual`, valida que el importe coincida) o creando un asiento
  nuevo al vuelo (`conciliar_creando_asiento`, típico para comisiones o
  intereses bancarios).

## 5. Frontend (`static/app.js`)

Un único archivo JS sin dependencias ni build step. Estructura:

- `api(path, opts)`: wrapper de `fetch` que añade `Content-Type`, la cabecera
  `X-Empresa-Id` si hay una empresa activa, y convierte errores HTTP en
  excepciones JS con el mensaje de `detail` que envía FastAPI.
- `RIBBON`: array de datos que describe las pestañas y botones de la cinta
  de opciones (estilo ContaSol/Office). Añadir un botón nuevo es añadir una
  entrada aquí, no tocar HTML.
- `vistas.*`: un objeto con una función por pantalla (`vistas.inicio`,
  `vistas.diario`, `vistas.balance`, `vistas.bancos`, `vistas.usuarios`...).
  Cada una reemplaza `#area.innerHTML` con su propio HTML y conecta sus
  propios manejadores de eventos. No hay router de cliente ni framework:
  `abrirVista(id)` simplemente llama a `vistas[id]()`.
- Estado global mínimo: `ejercicio` (año activo), `empresaActual` (id),
  `miPerfil` (usuario + empresas), `cuentas` (mapa código→nombre para
  autocompletar). Todo lo demás se recarga desde la API cada vez que se
  abre una vista.

## 6. Tests (`tests/`)

`pytest` + `TestClient` de FastAPI. `conftest.py` define el fixture `client`,
que antes de cada test:

1. Apunta `database` a un directorio temporal nuevo
   (`database.reset_para_pruebas`), para que ningún test vea datos de otro.
2. Registra un usuario y una empresa de prueba (`demo@contalibre.local`),
   dejando la cookie de sesión ya puesta en el `TestClient`.

Así, los tests de negocio (asientos, facturas, cierre, AEAT, bancos...) no
necesitan preocuparse de autenticación: simplemente usan `client` y todas
las peticiones ya van autenticadas contra la empresa de prueba. Los tests de
`test_multiempresa.py` sí instancian `TestClient` adicionales para simular
más de un usuario/empresa a la vez (cada `TestClient` tiene su propio jarrón
de cookies, igual que dos navegadores distintos).

## 7. Variables de entorno

| Variable | Por defecto | Uso |
|---|---|---|
| `CONTALIBRE_DATA` | `contalibre_data` | Directorio con `control.db` y `empresas/*.db` |
| `CONTALIBRE_DB` | `contalibre.db` | Solo se lee para la migración de instalaciones antiguas (ver §2) |
| `OLLAMA_URL` | `http://localhost:11434` | Dónde buscar el servidor Ollama del asistente de IA |
| `OLLAMA_MODEL` | `qwen2.5` | Modelo a usar (debe soportar tool calling) |

## 8. Asistente de IA (`ollama_client.py`, `services/ia_tools.py`, `services/asistente.py`)

El asistente es un bucle de *tool calling* clásico, sin ningún framework de
agentes: la orquestación cabe en unas 50 líneas (`services/asistente.py`).

```
Usuario escribe una pregunta
        │
        ▼
services/asistente.py::responder(db, pregunta, historial)
        │  construye [system, ...historial, user] y llama a Ollama con
        │  la lista de herramientas (TOOL_SCHEMAS)
        ▼
ollama_client.chat(mensajes, tools)  ── POST /api/chat a Ollama
        │
        ├─ el modelo responde con tool_calls  ──► ia_tools.ejecutar_tool(db, nombre, args)
        │        (se añade el resultado como mensaje role="tool" y se       │
        │         vuelve a llamar a Ollama)                    ◄────────────┘
        │
        └─ el modelo responde sin tool_calls  ──► esa es la respuesta final
```

- **`services/ia_tools.py`** define 16 herramientas de solo lectura
  (`listar_facturas`, `informe_balance_situacion`, `modelo_aeat_303`...),
  cada una un envoltorio fino sobre una consulta ya existente (las mismas
  que usan los routers, o directamente las funciones de `services/`). Cada
  herramienta declara su propio JSON Schema (`TOOL_SCHEMAS`) y se ejecuta a
  través de `ejecutar_tool`, que **nunca lanza**: cualquier error se
  convierte en `{"error": "..."}` para que el modelo pueda leerlo y
  reformular la llamada en vez de romper la conversación.
- La `db` que reciben las herramientas es la misma sesión, ya ligada a la
  empresa activa, que usa el resto de la aplicación (`Depends(get_db)` en
  `routers/ia.py::POST /preguntar`) — el asistente **no puede** escapar del
  aislamiento multiempresa, ni aunque el modelo "alucine" una llamada rara:
  como mucho consulta datos de otra cuenta dentro de la misma empresa.
- `MAX_ITERACIONES = 6` en `asistente.py` evita que un modelo que se quede
  pidiendo herramientas en bucle cuelgue la petición para siempre.
- **`ollama_client.py`** es un cliente HTTP mínimo (no un SDK): solo cubre
  `/api/chat` (con tools) y `/api/tags` (para `GET /ia/estado`, que informa
  a la interfaz si Ollama está en marcha y si el modelo configurado está
  descargado). ContaLibre nunca instala ni arranca Ollama por su cuenta.

### Por qué no se testea con un modelo real

Los tests (`tests/test_asistente.py`) sustituyen `ollama_client.chat` por
una función de prueba (`monkeypatch`) que simula las respuestas de un
modelo — así se verifica el bucle de tool calling y que las herramientas
devuelven datos reales de la empresa activa, sin depender de tener Ollama
instalado ni de la latencia/variabilidad de un LLM real. `GET /ia/estado` y
`POST /ia/preguntar` sin Ollama en marcha también están cubiertos (deben
degradar con un mensaje claro, no reventar).
