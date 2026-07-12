# Manual de usuario de ContaLibre

Guía completa de todas las pantallas y funciones, pensada para quien usa el
programa día a día (no hace falta saber programación, y los conceptos
contables se explican sobre la marcha). Documentos relacionados:

- [`API.md`](API.md) — si quieres integrar la API REST desde otro programa.
- [`FUNCIONAMIENTO.md`](FUNCIONAMIENTO.md) — cómo está construido por dentro.

## Índice

- [Guía rápida: tu primer día](#guía-rápida-tu-primer-día)
- [Conceptos básicos (si no eres contable)](#conceptos-básicos-si-no-eres-contable)

Referencia por pantallas:

1. [Primeros pasos](#1-primeros-pasos)
2. [La ventana principal](#2-la-ventana-principal)
3. [Plan General Contable](#3-plan-general-contable)
4. [Diario](#4-diario)
5. [Clientes y proveedores](#5-clientes-y-proveedores)
6. [Facturación](#6-facturación)
7. [Inmovilizado](#7-inmovilizado)
8. [Informes](#8-informes)
9. [Cierre y apertura de ejercicio](#9-cierre-y-apertura-de-ejercicio)
10. [Modelos AEAT](#10-modelos-aeat)
11. [Exportar a PDF y Excel](#11-exportar-a-pdf-y-excel)
12. [Conciliación bancaria](#12-conciliación-bancaria)
13. [Empresas y usuarios](#13-empresas-y-usuarios)
14. [Tu cuenta: contraseña y sesión](#14-tu-cuenta-contraseña-y-sesión)
15. [Asistente de IA](#15-asistente-de-ia)
16. [Copias de seguridad](#16-copias-de-seguridad)
17. [Solución de problemas](#17-solución-de-problemas)

---

## Guía rápida: tu primer día

Un recorrido completo de 10 minutos: desde instalar hasta ver tu primer
informe. Cada paso remite a la sección del manual donde se explica a fondo.

**1. Instala y arranca** ([§1](#1-primeros-pasos)):

```bash
pip install -e .
contalibre
```

Abre http://localhost:8000 y crea tu cuenta con la pestaña **Crear cuenta**
(email, contraseña y el nombre de tu empresa). Entras directamente.

**2. Registra el capital inicial** ([§4](#4-diario)). Supón que empiezas
con 3.000 € en el banco. Ve a **Inicio → Introducir asientos** y crea este
asiento:

| Cuenta | Título | Debe | Haber |
|---|---|---:|---:|
| 572 | Bancos c/c | 3.000,00 | |
| 100 | Capital social | | 3.000,00 |

El pie de la ventana marca "Descuadre: 0,00 € ✓" en verde → **Guardar**.

**3. Da de alta tu primer cliente** ([§5](#5-clientes-y-proveedores)). En
**Diario → Clientes / Proveedores → Nuevo**: tipo *cliente*, su NIF y su
nombre. Nada más.

**4. Emite tu primera factura** ([§6](#6-facturación)). En **Facturación →
Facturas emitidas → Nueva factura**: número `F-2026-001`, el cliente que
acabas de crear, una línea "Servicios de consultoría" de 1.000 € al 21 %.
Al pulsar **Registrar y contabilizar**, ContaLibre genera solo el asiento:
cliente (1.210 €) contra ventas (1.000 €) e IVA repercutido (210 €). No has
tenido que escribir ni una cuenta.

**5. Cobra la factura**. Selecciónala en la lista → **Cobrar** → fecha de
hoy y cuenta `572`. Segundo asiento automático; la factura pasa a
"liquidada".

**6. Mira cómo va el negocio** ([§8](#8-informes)). En **Inicio → Resumen**
ya ves resultado, tesorería (4.210 €) e IVA del trimestre (210 € a
ingresar). En **Impresión oficial** tienes el balance, las pérdidas y
ganancias y el modelo 303 con sus casillas, todos exportables a PDF/Excel.

**7. (Opcional) Pregúntale a la IA** ([§15](#15-asistente-de-ia)): con
Ollama instalado, escribe en la pestaña **Asistente IA**: *"¿cuánto IVA
tengo que pagar este trimestre?"* y te responde con tus datos reales.

---

## Conceptos básicos (si no eres contable)

- **Partida doble**: todo movimiento se anota dos veces — de dónde sale el
  dinero/valor y a dónde va. Por eso cada asiento tiene al menos dos
  líneas, y la suma de la columna Debe siempre iguala a la del Haber.
  ContaLibre no deja guardar nada descuadrado, así que es imposible
  "romper" la contabilidad por un error de suma.
- **Debe / Haber**: no significan "debo dinero" / "me deben". Son las dos
  columnas del asiento: a grandes rasgos, el Debe recoge aumentos de
  activos y gastos; el Haber, aumentos de deudas, patrimonio e ingresos.
  Si dudas, deja que las facturas generen los asientos por ti.
- **Cuenta contable**: cada "cajón" donde se clasifica el dinero, con un
  código numérico estándar en España (el PGC): `572` bancos, `430`
  clientes, `700` ventas... ContaLibre precarga las habituales.
- **Ejercicio**: el año contable (aquí, el año natural). Al terminar, se
  "cierra" (se calcula el resultado y se archivan los saldos) y se "abre"
  el siguiente.
- **Tercero**: cualquier cliente o proveedor con el que trabajas.
- **Conciliación bancaria**: comprobar que lo que dice el extracto del
  banco coincide con lo que tienes contabilizado, movimiento a movimiento.

---

## 1. Primeros pasos

### Requisitos e instalación

Necesitas Python 3.10 o superior. Desde la carpeta del proyecto:

```bash
python -m venv .venv
source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -e .
contalibre                     # o: uvicorn contalibre.main:app
```

Abre **http://localhost:8000** en el navegador. Los datos se guardan en el
directorio `contalibre_data/` junto a donde ejecutes el programa (se puede
cambiar con la variable de entorno `CONTALIBRE_DATA`).

### Crear tu cuenta

La primera vez verás la pantalla de acceso. Pulsa **Crear cuenta**:

| Campo | Notas |
|---|---|
| Tu nombre | Opcional, solo para identificarte. |
| Email | Será tu usuario para entrar. No se envía ningún correo de confirmación. |
| Contraseña | Mínimo 8 caracteres. |
| Nombre de la empresa | Se crea junto con tu cuenta y quedas como su **administrador**. |

Al enviar el formulario entras directamente.

> **¿Vienes de una versión antigua de ContaLibre (un solo fichero
> `contalibre.db`)?** Al arrancar se detecta y se convierte en la "Empresa
> migrada". El primer usuario que se registre queda como su administrador
> automáticamente, además de crear su propia empresa.

### Entrar en sesiones siguientes

Pestaña **Entrar**: email y contraseña. La sesión dura 30 días o hasta que
pulses **Salir** (arriba a la derecha). Si olvidas la contraseña, mira
[§14](#14-tu-cuenta-contraseña-y-sesión).

---

## 2. La ventana principal

La interfaz imita una aplicación de escritorio con cinta de opciones
(estilo ContaSol/Office):

- **Barra de título** (naranja, arriba): empresa y ejercicio activos, el
  **selector de empresa**, el **selector de ejercicio**, un enlace a la
  documentación interactiva de la API (`API`) y el botón **Salir**.
- **Cinta de opciones**: nueve pestañas — *Inicio, Asistente IA, Diario,
  Facturación, Inventario, Cierre, Bancos, Empresa, Impresión oficial* —
  con sus botones agrupados por función. Muchas pantallas están accesibles
  desde varias pestañas (p. ej. las facturas, desde Inicio y desde
  Facturación).
- **Área de trabajo**: donde se abre cada pantalla.
- **Barra de estado** (abajo): empresa y ejercicio activos, y versión.

**Selector de empresa** (solo útil si perteneces a más de una): cambia qué
empresa ves en **toda** la aplicación, incluido el asistente de IA. Cada
empresa es un mundo aparte: su plan contable, sus asientos, sus facturas.

**Selector de ejercicio**: en la mayoría de pantallas (diario, mayor,
sumas y saldos, pérdidas y ganancias, balance) solo precarga las fechas
"Desde"/"Hasta" del filtro, que luego puedes cambiar a mano. En **Facturas
emitidas/recibidas** es la única forma de elegir el año: esa pantalla no
tiene filtro de fechas propio.

---

## 3. Plan General Contable

**Diario → P.G.C.**

El maestro de cuentas contables (código + título). Al crear una empresa se
precargan ~65 cuentas básicas del PGC PYMES, listas para trabajar.

| Acción | Cómo | Detalles |
|---|---|---|
| Buscar | Caja "Buscar" + Intro | Por prefijo de código (`57` → toda la tesorería) o por texto del título ("banco"). |
| Nueva cuenta | Botón **Nueva cuenta** | Código numérico de hasta 10 dígitos + título. Sin límite de subcuentas: `6290001`, `6290002`... |
| Ver movimientos | Selecciona una fila → **Extracto** | Abre el libro mayor de esa cuenta. |
| Eliminar | Selecciona → **Eliminar** | Solo si la cuenta no tiene ningún apunte contabilizado. |

Las subcuentas de clientes (`430NNNN`) y proveedores (`400NNNN`) no hace
falta crearlas a mano: se crean solas con la primera factura de cada
tercero.

---

## 4. Diario

### Introducir asientos

**Diario → Introducir asientos** (también en Inicio).

1. Arriba: **fecha** y **concepto general** del asiento.
2. En la rejilla, por cada línea: la **cuenta** (con autocompletado por
   código y nombre), un **concepto de línea** opcional (si lo dejas vacío
   hereda el general), y el importe en **Debe** *o* en **Haber** — nunca
   ambos en la misma línea.
3. Al rellenar la cuenta de la última línea se añade una nueva
   automáticamente; la tecla **Intro** salta al campo siguiente.
4. El pie muestra los totales y el **descuadre en vivo**: rojo mientras no
   cuadre, verde con "✓" cuando Debe = Haber exactamente (al céntimo).
5. **Guardar asiento** — solo funciona cuadrado. La numeración es
   automática y correlativa dentro de cada año natural.

Reglas que el programa hace cumplir (y por qué):

- *Debe = Haber al céntimo* — es la partida doble; sin ella los informes
  no cuadrarían.
- *Ningún importe negativo* — para corregir, haz el asiento inverso.
- *Nada con fecha de un ejercicio cerrado* — ver [§9](#9-cierre-y-apertura-de-ejercicio).

### Consultar el diario

**Diario → Consulta de diario**: filtro por rango de fechas y/o por cuenta
(acepta prefijos: `43` = todos los clientes). Selecciona una fila para:

- **Ver asiento**: el detalle completo, con el **Id** de cada apunte (lo
  necesitarás para la conciliación manual, [§12](#12-conciliación-bancaria)).
  También con doble clic.
- **Eliminar asiento**: no permitido si el asiento pertenece a una factura
  (elimina la factura en su lugar), a una dotación de amortización
  (elimínala desde la ficha del activo) o a un ejercicio cerrado — el
  mensaje de error siempre te dice cuál es el camino correcto.

---

## 5. Clientes y proveedores

**Diario → Clientes / Proveedores** (o desde Facturación).

- **Nuevo**: tipo (*cliente*, *proveedor* o *ambos*), NIF (único por
  empresa), nombre y, opcionalmente, teléfono/email/dirección.
- **Editar**: doble clic sobre la fila, o selecciónala y pulsa **Editar**.
- La columna **Subcuentas** muestra la cuenta contable de cada tercero
  (`430NNNN` clientes / `400NNNN` proveedores), que se crea sola con su
  primera factura. Un tercero de tipo "ambos" puede llegar a tener las dos.
- **Eliminar**: solo si el tercero no tiene facturas registradas.

---

## 6. Facturación

**Facturación → Facturas emitidas** (tus ventas: IVA repercutido) o
**Facturas recibidas** (tus compras: IVA soportado).

### Nueva factura

1. **Número**: libre, pero único dentro de su tipo (no puede haber dos
   emitidas con el mismo número; sí una emitida y una recibida).
2. **Fecha** y **cliente/proveedor** (debe existir ya como tercero).
3. **Cuenta de contrapartida**: dónde se imputa el ingreso o gasto. Por
   defecto `700` (ventas) en emitidas y `600` (compras) en recibidas.
   Ejemplos de cuándo cambiarla:
   - Factura recibida del alquiler → `621`.
   - Factura recibida de la compra de un ordenador → `217` (y luego crea
     su ficha de inmovilizado, [§7](#7-inmovilizado)).
   - Factura emitida por servicios → `705`.
4. **Retención IRPF (%)**: si aplica (típico entre profesionales, 15 %).
5. **Líneas** (una o varias): descripción, base imponible y tipo de IVA
   (21/10/4/0 % en el desplegable). Los totales se calculan en vivo.
6. **Registrar y contabilizar**: genera automáticamente el asiento
   completo. Ejemplo, factura emitida de 1.000 € + 21 % con 15 % de
   retención:

   | Cuenta | Debe | Haber |
   |---|---:|---:|
   | 430xxxx Cliente | 1.060,00 | |
   | 473 Retenciones a cuenta | 150,00 | |
   | 700 Ventas | | 1.000,00 |
   | 477 IVA repercutido | | 210,00 |

### Cobrar o pagar (liquidar)

Selecciona la factura → **Cobrar** (emitidas) / **Pagar** (recibidas) →
fecha y cuenta de tesorería (por defecto `572`). El importe es el total
menos la retención. Genera el segundo asiento y la factura pasa a
**liquidada**. El filtro "Estado" de la lista permite ver solo pendientes.

### Otras acciones

- **Ver asiento**: doble clic, o selección + botón.
- **Eliminar**: borra la factura **y** sus asientos vinculados (el de la
  factura y el del cobro/pago si existía). No se puede eliminar solo el
  asiento desde el Diario: siempre a través de la factura, para que ambos
  no se desincronicen.

---

## 7. Inmovilizado

**Inventario → Fichas de activos** — para los bienes duraderos (equipos,
mobiliario, vehículos...) que se amortizan a lo largo de varios años.

### Alta de un activo

**Nueva ficha**: descripción, fecha de adquisición, valor de compra, valor
residual (lo que valdrá al final de su vida útil, normalmente 0), vida
útil en años, y las tres cuentas contables — con valores por defecto
razonables: `213` activo (cámbiala a `217` para equipos informáticos,
`218` vehículos...), `281` amortización acumulada, `681` gasto.

> La compra en sí se contabiliza aparte, normalmente como una **factura
> recibida** con la cuenta del activo como contrapartida ([§6](#6-facturación)).
> La ficha solo gestiona el plan de amortización.

### Amortizar

**Amortizar ejercicio** pide el año y genera el asiento de dotación
(gasto `681` contra amortización acumulada `281`, con fecha 31/12). El
cálculo es **lineal** con dos matices automáticos:

- El año de compra se **prorratea por días** (un equipo comprado el 1 de
  diciembre solo dota ~1/12 del importe anual ese año).
- El **último año** del plan absorbe los céntimos de redondeo, de forma
  que el activo queda amortizado exactamente a su valor amortizable.

Ejemplo: 100 € a 3 años comprado el 01/01/2023 → dotaciones de 33,33 /
33,33 / **33,34**.

### Consultar y deshacer

**Dotaciones** muestra el histórico del activo seleccionado con enlace al
asiento de cada año; desde ahí puedes eliminar una dotación concreta (se
borra también su asiento). **Eliminar** la ficha requiere no tener
dotaciones.

---

## 8. Informes

En **Diario** (consulta) y en **Impresión oficial**, con filtros de fechas
precargadas al ejercicio activo:

| Informe | Qué muestra |
|---|---|
| **Extracto de mayor** | Todos los movimientos de una cuenta (o prefijo, p. ej. `57` = toda la tesorería) con saldo acumulado línea a línea. |
| **Sumas y saldos** | Todas las cuentas con debe, haber y saldo deudor/acreedor, con totales y comprobación de cuadre. |
| **Pérdidas y ganancias** | Ingresos (grupo 7) y gastos (grupo 6) del periodo, y el resultado. |
| **Balance de situación** | Activo y Patrimonio neto + Pasivo a una fecha, con la estructura oficial del balance abreviado del PGC (Activo no corriente/corriente, Patrimonio neto, Pasivo no corriente/corriente, con sus apartados I, II, III...). Mientras el ejercicio no está cerrado, el resultado aparece como "Resultado del periodo (sin regularizar)". |
| **Resumen de IVA** | Base y cuota repercutida/soportada de un trimestre, con el resultado (a ingresar o a compensar). Es la consulta rápida; la versión con casillas oficiales está en los [modelos AEAT](#10-modelos-aeat). |

Todos menos el resumen de IVA se exportan a PDF/Excel ([§11](#11-exportar-a-pdf-y-excel)).

---

## 9. Cierre y apertura de ejercicio

**Cierre → Cierre y apertura**. La tabla muestra cada año con movimientos:
si está abierto/cerrado, sus fechas y su resultado (o el **resultado
previsto** mientras siga abierto).

### Qué hace el cierre

Al **cerrar un ejercicio** se generan dos asientos automáticos a 31/12:

1. **Regularización**: salda todas las cuentas de gastos (grupo 6) e
   ingresos (grupo 7) contra la `129 Resultado del ejercicio`. Ahí queda
   "fotografiado" el beneficio o pérdida del año.
2. **Cierre**: salda a cero el resto de cuentas (grupos 1-5). Siempre
   cuadra: es una propiedad matemática de la partida doble.

Al **abrir el ejercicio siguiente** se genera el asiento de apertura
(espejo del de cierre, a 1/1), que reabre los saldos para seguir
trabajando.

### Reglas

- **Secuencial**: no puedes cerrar 2025 sin haber cerrado *y abierto* 2024
  antes. El primer año con movimientos no necesita apertura.
- Mientras un año está **cerrado**, no se pueden crear ni eliminar
  asientos con fecha de ese año (protege el resultado ya calculado).
- **Deshacer cierre / Deshacer apertura**: elimina los asientos generados
  y reabre el año — siempre que no hayas avanzado ya al siguiente
  (deshacer el cierre de 2024 exige que 2025 no esté abierto).

**Flujo típico en enero**: revisa que todo el año anterior está
contabilizado (facturas, amortizaciones, [conciliación](#12-conciliación-bancaria))
→ Cerrar 2025 → Abrir 2026 → seguir trabajando.

---

## 10. Modelos AEAT

**Impresión oficial → Modelos AEAT**. Los tres son **simplificaciones
declaradas**: útiles para consultar y para preparar la presentación, pero
no cubren regímenes especiales (intracomunitario, importaciones, bienes de
inversión, recargo de equivalencia...) y **no sustituyen la presentación
oficial** ante la Agencia Tributaria. Cada pantalla lo recuerda.

| Modelo | Periodicidad | Contenido |
|---|---|---|
| **303** | Trimestral | Liquidación de IVA por casillas: devengado (27), deducible (28/29/44) y resultado (46/69), con su sentido: *a ingresar*, *a compensar* o *a devolver* (esto último solo en el 4T). |
| **390** | Anual | Resumen informativo: desglose anual de IVA devengado/deducible por tipo, más los cuatro resultados trimestrales. |
| **347** | Anual | Terceros cuyas operaciones del año superan **3.005,06 €** (IVA incluido), con clave A (compras) o B (ventas) y desglose por trimestre. |

Los tres se calculan a partir de las facturas registradas y se exportan a
PDF/Excel.

---

## 11. Exportar a PDF y Excel

Los cuatro informes principales (mayor, sumas y saldos, pérdidas y
ganancias, balance) y los tres modelos AEAT tienen botones **PDF** y
**Excel** en su barra de herramientas. El documento se genera con los
mismos filtros que tengas en pantalla y se descarga al momento.

- **PDF**: formato de presentación, con importes en formato español
  (1.234,56).
- **Excel**: valores numéricos puros, listos para seguir calculando.

Desde la API: añade `?formato=pdf` o `?formato=excel` a la URL del informe
(ver [`API.md`](API.md)).

---

## 12. Conciliación bancaria

**Bancos → Conciliación bancaria** — para cuadrar el extracto del banco
con tu contabilidad.

### Importar el extracto

1. Descarga de tu banca electrónica el extracto en formato **cuaderno 43**
   (también llamado *norma 43* o *AEB43*; casi todos los bancos españoles
   lo ofrecen, a veces como "formato contable").
2. Indica la **cuenta de tesorería** a la que corresponde (p. ej. `572`),
   selecciona el fichero y pulsa **Importar**.
3. Repetir una importación no duplica movimientos: los ya conocidos se
   ignoran.

### Conciliar

Al importar, cada movimiento intenta **conciliarse automáticamente** con
un apunte existente de esa cuenta con la misma fecha e importe. Lo que
queda **pendiente** se resuelve a mano:

| Botón | Cuándo usarlo | Cómo |
|---|---|---|
| **Conciliar con apunte…** | El movimiento ya está contabilizado, pero con otra fecha (p. ej. el banco lo aplicó dos días después). | Abre el asiento en el Diario, apunta el **Id** de la línea de tesorería y escríbelo en el formulario. El importe debe coincidir exactamente. |
| **Conciliar creando asiento** | Aún no está contabilizado: comisiones, intereses, recibos domiciliados... | Indica la cuenta de contrapartida (p. ej. `626` comisiones) y el concepto; el asiento se crea y se concilia en un solo paso. |

- **Desconciliar**: deshace el vínculo sin tocar el asiento contable.
- **Eliminar**: borra un movimiento importado (solo pendientes; desconcilia
  primero si hace falta).

Objetivo sano al cerrar cada mes: **0 pendientes**.

---

## 13. Empresas y usuarios

**Empresa → Usuarios**.

### Roles

| | Operar (asientos, facturas...) | Invitar/quitar usuarios | Copia de seguridad |
|---|:---:|:---:|:---:|
| **Admin** | ✓ | ✓ | ✓ |
| **Editor** | ✓ | — | — |

### Gestionar usuarios

- **Invitar usuario** (solo admin): escribe el email de alguien que **ya
  tenga cuenta creada** en este servidor (pestaña "Crear cuenta" de la
  pantalla de acceso) y elige su rol. No se envía ningún correo: el
  usuario simplemente verá tu empresa en su selector la próxima vez que
  consulte su perfil o entre.
- **Quitar** (solo admin): deja de dar acceso; no puedes quitarte a ti
  mismo.

### Varias empresas

**Crear nueva empresa** te hace administrador de una empresa nueva y
completamente separada — literalmente otra base de datos: ni un informe,
ni una búsqueda, ni el asistente de IA pueden mezclar datos de dos
empresas. Cambia entre ellas con el selector de la barra de título. Un
mismo usuario puede ser admin de una y editor de otra.

---

## 14. Tu cuenta: contraseña y sesión

- **Cambiar mi contraseña** (Empresa → Usuarios): contraseña actual + la
  nueva (mínimo 8 caracteres).
- **¿Olvidaste tu contraseña?** (pantalla de acceso): introduce tu email.
  Se genera un token de un solo uso, válido **1 hora** — y como esta
  aplicación es local y no envía correos, el token aparece **en la consola
  donde se ejecuta el servidor** (solo quien tiene acceso a esa máquina
  puede leerlo). Cópialo en el formulario "Restablecer contraseña" que
  aparece a continuación, junto con tu contraseña nueva.
- Restablecer la contraseña **cierra todas tus sesiones** abiertas, en
  todos los navegadores.
- Las sesiones caducan a los **30 días**, comprobado en el servidor (no
  basta con conservar la cookie).
- Tras **5 intentos de login fallidos** seguidos, ese email queda bloqueado
  unos 15 minutos (protección contra fuerza bruta).

---

## 15. Asistente de IA

**Asistente IA → Preguntar a la IA** — un chat que responde preguntas
sobre **tus** datos contables usando un modelo de lenguaje que corre **en
tu propia máquina** (nada sale a internet).

### Preparación (una sola vez)

1. Instala [Ollama](https://ollama.com/download) (Windows/Mac/Linux).
2. Descarga un modelo con soporte de herramientas:
   ```bash
   ollama pull qwen2.5
   ```

La propia pantalla del asistente comprueba la conexión y te indica el
comando exacto que falte. Para usar otro modelo u otro servidor Ollama,
arranca ContaLibre con las variables `OLLAMA_MODEL` / `OLLAMA_URL`.

### Uso

Escribe preguntas en lenguaje natural:

- *"¿Cuánto IVA tengo que pagar este trimestre?"*
- *"¿Qué clientes me deben dinero ahora mismo?"*
- *"¿Cuál fue mi resultado en 2025?"*
- *"¿Qué facturas recibidas tengo pendientes de pagar?"*
- *"¿Hay movimientos bancarios sin conciliar?"*

El asistente **consulta tus datos reales** mediante herramientas de solo
lectura (facturas, asientos, informes, modelos AEAT, bancos...) y bajo
cada respuesta indica qué consultó (🔎). Garantías:

- **Solo lee**: no puede crear, modificar ni borrar nada.
- **Solo tu empresa activa**: cambiar de empresa en el selector cambia lo
  que la IA puede ver; jamás mezcla empresas.
- **No inventa cifras**: si no puede obtener un dato, lo dice.

**Nueva conversación** borra el historial (las preguntas siguientes no
recuerdan las anteriores). Si el modelo corre en CPU, las respuestas
pueden tardar bastantes segundos: es normal.

---

## 16. Copias de seguridad

Dos formas complementarias:

1. **Desde la interfaz** (solo admin): **Empresa → Usuarios → Descargar
   copia de seguridad** — un `.zip` con una instantánea completa y
   consistente de la empresa activa (segura aunque haya alguien trabajando
   en ese momento). Hazlo periódicamente y guarda el fichero fuera del
   equipo.
2. **A nivel de sistema**: copiar el directorio `contalibre_data/` entero
   (todas las empresas + usuarios). Mejor con el servidor parado.

Para **restaurar** una copia de empresa: descomprime el `.zip` y sustituye
el fichero correspondiente en `contalibre_data/empresas/` con el servidor
parado.

---

## 17. Solución de problemas

| Situación | Qué hacer |
|---|---|
| "Asiento descuadrado" o "no puede tener importe cero" | Debe y Haber tienen que sumar exactamente lo mismo; el pie de la pantalla de asientos te muestra el descuadre en rojo hasta que cuadre. |
| "El ejercicio X está cerrado; no admite nuevos asientos" | Ese año se cerró. Para corregir algo, primero **Deshacer cierre** en Cierre → Cierre y apertura (solo posible si el año siguiente no está abierto aún). |
| "El asiento pertenece a la factura…" al eliminar | Los asientos de facturas se gestionan desde la factura: elimínala o modifícala allí y sus asientos la siguen. |
| No puedo eliminar una cuenta / tercero / activo | Tiene movimientos, facturas o dotaciones asociadas. Elimina primero esos elementos (o simplemente no la elimines: no ocupa nada). |
| "Ya existe la factura emitida nº X" | El número de factura debe ser único dentro de su tipo. Usa el siguiente número libre. |
| "Demasiados intentos fallidos" al entrar | Espera ~15 minutos, o usa "¿Olvidaste tu contraseña?" si no estás seguro de ella. |
| El asistente de IA dice que Ollama no está disponible | Instala Ollama, comprueba que corre (`ollama serve`, normalmente automático) y que el modelo está descargado (`ollama pull qwen2.5`). La pantalla te dice exactamente qué falta. |
| El asistente responde muy lento | Es normal en CPU. Un modelo más pequeño (`qwen2.5:3b`) responde más rápido a costa de menos precisión; configúralo con `OLLAMA_MODEL`. |
| "No perteneces a esa empresa" | El selector de empresa (o la cabecera `X-Empresa-Id` si usas la API) apunta a una empresa que no es tuya. Reselecciona una válida en la barra de título. |
| El movimiento bancario no se auto-concilia | La conciliación automática exige fecha **e** importe idénticos. Si el banco aplicó el movimiento otro día, usa "Conciliar con apunte…" con el Id del apunte (visible al abrir el asiento en el Diario). |
| Perdí la contraseña y no tengo acceso a la consola del servidor | Quien administre esa máquina puede leer el token en el log tras pedir "¿Olvidaste tu contraseña?". Sin acceso a la máquina no hay puerta trasera — es deliberado. |

> ⚠️ ContaLibre es una herramienta de gestión; no constituye asesoramiento
> fiscal ni contable. Ante dudas fiscales, consulta a un profesional.
