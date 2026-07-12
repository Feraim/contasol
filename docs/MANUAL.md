# Manual de usuario de ContaLibre

Guía práctica de todas las pantallas y funciones, pensada para quien usa el
programa día a día (no hace falta saber programación). Si buscas cómo está
construido por dentro, mira [`FUNCIONAMIENTO.md`](FUNCIONAMIENTO.md); si
quieres integrar la API REST desde otro programa, mira [`API.md`](API.md).

## Índice

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

## 1. Primeros pasos

### Instalar y arrancar

```bash
pip install -e .
contalibre
```

Abre **http://localhost:8000** en el navegador.

### Crear tu cuenta

La primera vez verás la pantalla de acceso. Pulsa la pestaña **Crear
cuenta** y rellena:

- **Tu nombre** (opcional, solo para identificarte).
- **Email** — será tu usuario para entrar.
- **Contraseña** — mínimo 8 caracteres.
- **Nombre de la empresa** — la empresa que se crea junto con tu cuenta; tú
  quedas como su administrador.

Al enviar el formulario entras directamente: no hace falta confirmar el
email (esta aplicación no envía correos, ver [§14](#14-tu-cuenta-contraseña-y-sesión)).

### Entrar en sesiones siguientes

Pestaña **Entrar**: email y contraseña. La sesión dura 30 días (o hasta que
pulses **Salir**, arriba a la derecha).

---

## 2. La ventana principal

La interfaz imita una aplicación de escritorio (estilo ContaSol/Office):

- **Barra de título** (naranja, arriba): nombre de la empresa activa,
  ejercicio (año) activo, selector de empresa, selector de ejercicio,
  enlace a la documentación de la API (`/docs`) y el botón **Salir**.
- **Cinta de opciones**: pestañas (Inicio, Asistente IA, Diario,
  Facturación, Inventario, Cierre, Bancos, Empresa, Impresión oficial) y,
  debajo, los botones de cada pestaña agrupados por función.
- **Área de trabajo**: aquí se abre cada pantalla.
- **Barra de estado** (abajo): recordatorio de la empresa/ejercicio activos
  y la versión del programa.

**Selector de empresa** (si perteneces a más de una): cambia qué empresa
ves en toda la aplicación. **Selector de ejercicio**: en la mayoría de
pantallas (diario, mayor, sumas y saldos, pérdidas y ganancias, balance)
solo precarga las fechas "Desde"/"Hasta" del filtro, que puedes cambiar a
mano sin volver a tocar el selector. En **Facturas emitidas/recibidas** es
la única forma de elegir el año: esa pantalla no tiene selector de fechas
propio, así que cambiar el ejercicio ahí sí determina qué facturas ves.

---

## 3. Plan General Contable

**Diario → P.G.C.**

Lista de todas las cuentas contables (código y título). Al crear una
empresa se precargan ~65 cuentas básicas del PGC PYMES; puedes:

- **Buscar** por código o por texto del título.
- **Nueva cuenta**: código numérico (hasta 10 dígitos) y título.
- **Extracto**: ver el libro mayor de la cuenta seleccionada.
- **Eliminar**: solo si la cuenta no tiene movimientos contabilizados.

No hay límite de subcuentas: puedes crear tantas como necesites (p. ej.
`6290001`, `6290002`...).

---

## 4. Diario

### Introducir asientos

**Diario → Introducir asientos** (o el botón homónimo en Inicio).

1. Fecha y concepto general del asiento.
2. Por cada línea: cuenta (con autocompletado), concepto de la línea
   (opcional; si lo dejas en blanco usa el concepto general), importe en
   **Debe** o en **Haber** (nunca los dos en la misma línea).
3. Se añade una línea nueva automáticamente al rellenar la cuenta de la
   última.
4. El pie de la ventana muestra el descuadre en vivo; en verde cuando
   cuadra. **Guardar asiento** solo funciona si Debe = Haber exactamente.

La numeración de los asientos es automática y correlativa dentro de cada
año natural.

### Consultar el diario

**Diario → Consulta de diario**: filtra por fecha y/o por cuenta (acepta
prefijos, p. ej. `43` muestra todos los clientes). Selecciona una fila para
**Ver asiento** completo o **Eliminar asiento** (no se puede si pertenece a
una factura, a una amortización, o si su ejercicio está cerrado — en esos
casos el mensaje de error te dice qué hacer en su lugar).

---

## 5. Clientes y proveedores

**Diario → Clientes / Proveedores** (o **Facturación → Clientes /
Proveedores**).

- **Nuevo**: tipo (cliente / proveedor / ambos), NIF, nombre, y
  opcionalmente teléfono/email/dirección.
- Al emitir o recibir la primera factura de un tercero, se le crea
  automáticamente una subcuenta contable: `430NNNN` si es cliente,
  `400NNNN` si es proveedor (columna "Subcuentas" de la tabla).
- **Eliminar**: solo si el tercero no tiene facturas registradas.

---

## 6. Facturación

**Facturación → Facturas emitidas** (ventas, IVA repercutido) o
**Facturas recibidas** (compras, IVA soportado). También accesibles desde
**Inicio**.

### Nueva factura

1. Número (libre, pero único por tipo — no puede repetirse entre dos
   facturas emitidas, por ejemplo), fecha, cliente/proveedor.
2. Cuenta de contrapartida: por defecto `700` (ventas) en emitidas o `600`
   (compras) en recibidas — cámbiala si corresponde (p. ej. `217` si la
   factura recibida es la compra de un equipo para inmovilizado).
3. Retención IRPF (%) si aplica (típico en facturas de profesionales).
4. Una o varias líneas: descripción, base imponible, tipo de IVA
   (21/10/4/0 %, o cualquier otro que necesites).
5. **Registrar y contabilizar** genera automáticamente el asiento completo:
   cliente/proveedor, IVA repercutido/soportado y retención si la hay.

### Cobrar o pagar

Selecciona la factura → botón **Cobrar** (emitidas) o **Pagar** (recibidas).
Indica la fecha y la cuenta de tesorería (por defecto `572`, bancos). Se
genera un segundo asiento y la factura pasa a estado "liquidada".

### Ver el asiento de una factura

Doble clic en la fila, o selecciónala y pulsa **Ver asiento**.

### Eliminar una factura

Borra también sus asientos vinculados (el de la factura y, si existe, el
del cobro/pago).

---

## 7. Inmovilizado

**Inventario → Fichas de activos**.

1. **Nueva ficha**: descripción, fecha de adquisición, valor de compra,
   valor residual (si lo hay), vida útil en años, y las tres cuentas
   contables (activo, amortización acumulada, gasto — con valores por
   defecto razonables).
   > La compra en sí se contabiliza aparte, normalmente como una factura
   > recibida con la cuenta del activo como contrapartida.
2. **Amortizar ejercicio**: pide el año a dotar y genera el asiento
   (gasto a amortización acumulada) de ese ejercicio. La amortización es
   lineal, con prorrateo por días en el año de compra y ajuste del
   redondeo en el último año del plan.
3. **Dotaciones**: consulta el histórico de amortizaciones de un activo,
   con enlace al asiento de cada una; puedes eliminar una dotación
   concreta (borra también su asiento).
4. **Eliminar** una ficha: solo si no tiene dotaciones registradas.

---

## 8. Informes

Todos en **Diario** (consultas) e **Impresión oficial** (formato de
presentación), con filtros de fecha:

- **Extracto de mayor**: todos los movimientos de una cuenta (o prefijo)
  con saldo acumulado línea a línea.
- **Sumas y saldos**: todas las cuentas con su debe, haber y saldo deudor
  o acreedor, con totales.
- **Pérdidas y ganancias**: ingresos y gastos del periodo y resultado.
- **Balance de situación**: activo y patrimonio neto + pasivo, clasificados
  con la estructura oficial del balance abreviado del PGC (Activo no
  corriente/corriente; Patrimonio neto; Pasivo no corriente/corriente, con
  sus apartados numerados I, II, III...).
- **Resumen de IVA** (estilo modelo 303): base y cuota repercutida/soportada
  de un trimestre concreto — es la versión rápida de consulta; para la
  versión con casillas oficiales usa los [modelos AEAT](#10-modelos-aeat).

---

## 9. Cierre y apertura de ejercicio

**Cierre → Cierre y apertura**.

La tabla muestra, por año: si está abierto, si está cerrado, fechas y
resultado (o resultado previsto, mientras el año sigue abierto).

- **Cerrar ejercicio**: genera dos asientos automáticos — uno que salda
  las cuentas de gastos e ingresos (grupos 6 y 7) contra la `129 Resultado
  del ejercicio`, y otro que salda a cero el resto de cuentas
  patrimoniales.
- **Abrir ejercicio** (el siguiente año): genera el asiento que reabre esos
  saldos, para poder seguir contabilizando.
- Solo puedes cerrar un año si el anterior ya está cerrado **y** abierto
  (secuencial: no hay atajos). Mientras un año está cerrado, no se pueden
  crear ni eliminar asientos con fecha de ese año.
- **Deshacer cierre** / **Deshacer apertura**: revierte la operación,
  siempre que no se haya avanzado ya al año siguiente (deshacer el cierre
  de 2024 exige que 2025 no esté abierto todavía).

---

## 10. Modelos AEAT

**Impresión oficial → Modelos AEAT**. Todos son **simplificaciones**:
sirven para consulta rápida y para exportar, pero no cubren todos los
regímenes especiales y no sustituyen la presentación real ante la Agencia
Tributaria (cada pantalla lo recuerda con un aviso).

- **Modelo 303** (trimestral): casillas de IVA devengado (27), deducible
  (28/29/44) y resultado de la liquidación (46/69), con si es "a ingresar",
  "a compensar" o "a devolver" (este último solo en el 4T).
- **Modelo 390** (anual): agrega los cuatro trimestres, con el desglose de
  IVA devengado/deducible del año completo y los cuatro resultados
  trimestrales.
- **Modelo 347**: terceros (clientes o proveedores) cuyas operaciones del
  año superan 3.005,06 €, con clave A (compras) o B (ventas) y desglose
  por trimestre.

---

## 11. Exportar a PDF y Excel

Todos los informes (mayor, sumas y saldos, pérdidas y ganancias, balance)
y los tres modelos AEAT tienen botones **PDF** y **Excel** en su barra de
herramientas: generan el documento con los mismos filtros que tengas
puestos en pantalla y lo descargan directamente.

---

## 12. Conciliación bancaria

**Bancos → Conciliación bancaria**.

1. **Importar**: indica la cuenta de tesorería (p. ej. `572`) y selecciona
   un fichero de extracto bancario en formato **cuaderno 43** de la AEB
   (el que exportan la mayoría de bancos españoles). Los movimientos ya
   importados no se duplican si repites la importación.
2. Cada movimiento intenta conciliarse **automáticamente** contra un
   apunte existente de igual fecha e importe en esa cuenta.
3. Lo que queda **pendiente**, selecciónalo y:
   - **Conciliar con apunte...**: si el movimiento ya está contabilizado
     pero con otra fecha (necesitas el ID del apunte, visible al abrir el
     asiento correspondiente en el Diario).
   - **Conciliar creando asiento**: para lo que aún no está contabilizado
     (comisiones, intereses...) — indicas la cuenta contrapartida y se
     genera el asiento al vuelo, ya conciliado.
4. **Desconciliar**: deshace el vínculo sin tocar el asiento contable.
5. **Eliminar**: solo movimientos pendientes (sin conciliar).

---

## 13. Empresas y usuarios

**Empresa → Usuarios**.

- Ves el listado de usuarios de la empresa activa y su rol.
- **Invitar usuario** (solo administradores): el email debe corresponder a
  alguien que **ya tenga una cuenta creada** (pestaña "Crear cuenta"); tú
  solo lo vinculas a tu empresa con rol **admin** o **editor**.
  - **Admin**: además de operar con normalidad, puede invitar/quitar
    usuarios y descargar la copia de seguridad.
  - **Editor**: puede operar (crear asientos, facturas, etc.) pero no
    gestionar usuarios.
- **Quitar** un usuario (solo admin; no puedes quitarte a ti mismo).
- **Crear nueva empresa**: te convierte automáticamente en administrador
  de una empresa nueva, completamente separada (su propia base de datos);
  cambia a ella con el selector de empresa de la barra de título.

---

## 14. Tu cuenta: contraseña y sesión

- **Cambiar mi contraseña** (pestaña Empresa → Usuarios): pide la
  contraseña actual y la nueva.
- **¿Olvidaste tu contraseña?** (pantalla de acceso): pide tu email y
  genera un token de un solo uso, válido 1 hora. Como esta aplicación es
  local y no envía correos, **el token aparece en la consola donde se
  ejecuta el servidor** (quien tiene acceso a esa máquina puede leerlo).
  Cópialo en el formulario "Restablecer contraseña" que aparece a
  continuación.
- Restablecer la contraseña cierra automáticamente todas tus sesiones
  activas (tendrás que volver a entrar donde estuvieras conectado).
- Las sesiones caducan a los 30 días, comprobado en el servidor (no basta
  con conservar la cookie del navegador).
- Tras varios intentos de login fallidos seguidos, la cuenta se bloquea
  temporalmente unos minutos (protección contra fuerza bruta).

---

## 15. Asistente de IA

**Asistente IA → Preguntar a la IA**.

Requiere [Ollama](https://ollama.com) instalado y en marcha en tu máquina
(la propia pantalla te indica los comandos si falta algo):

```bash
ollama pull qwen2.5
```

Escribe preguntas en lenguaje natural sobre tus propios datos, por
ejemplo:

- "¿Cuánto IVA tengo que pagar este trimestre?"
- "¿Qué clientes me deben dinero ahora mismo?"
- "¿Cuál fue mi resultado el año pasado?"
- "¿Cuánta tesorería tengo en el banco?"

El asistente consulta tus datos reales (nunca inventa cifras) y bajo cada
respuesta indica qué información consultó. Solo ve los datos de la
empresa activa: cambiar de empresa con el selector de la barra de título
también cambia lo que el asistente puede ver. **Nunca modifica nada**: solo
lee.

**Nueva conversación** borra el historial del chat (empieza de cero, sin
recordar preguntas anteriores).

---

## 16. Copias de seguridad

**Empresa → Usuarios → Descargar copia de seguridad** (solo
administradores): descarga un `.zip` con una instantánea completa y
consistente de los datos de la empresa activa. Guárdalo en un lugar seguro
periódicamente.

También puedes copiar directamente el directorio `contalibre_data/`
completo (contiene todas las empresas y usuarios) mientras el programa no
esté escribiendo en ese momento.

---

## 17. Solución de problemas

| Situación | Qué hacer |
|---|---|
| "El asiento no puede tener importe cero" / no cuadra | Revisa que Debe y Haber sumen exactamente lo mismo; el pie de la ventana de introducción de asientos te lo muestra en rojo mientras no cuadre. |
| "El ejercicio X está cerrado" al crear/eliminar un asiento | Ese año ya se cerró. Si necesitas corregir algo, deshaz primero el cierre desde **Cierre → Cierre y apertura** (solo si el año siguiente no está ya abierto). |
| No puedo eliminar una cuenta/tercero/activo | Tiene movimientos, facturas o dotaciones asociadas — elimina o reasigna esos elementos primero. |
| "Demasiados intentos fallidos" al entrar | Espera unos 15 minutos y vuelve a intentarlo, o usa "¿Olvidaste tu contraseña?" si no estás seguro de la contraseña. |
| El asistente de IA no responde | Comprueba que Ollama está instalado y en marcha (`ollama serve`) y que el modelo está descargado (`ollama pull qwen2.5`); la propia pantalla del asistente te dice cuál falta. |
| "No perteneces a esa empresa" | Estás usando el selector de empresa o una cabecera `X-Empresa-Id` que no corresponde a ninguna de tus membresías; vuelve a seleccionar una empresa válida en la barra de título. |
| Perdí mi contraseña y no tengo acceso a la consola del servidor | Pide a quien administra el servidor que consulte el log tras solicitar "¿Olvidaste tu contraseña?", o restaura la contraseña directamente en la base de datos con ayuda técnica. |

> ⚠️ ContaLibre es una herramienta de gestión; no constituye asesoramiento fiscal ni contable.
