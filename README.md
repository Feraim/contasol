# 📒 ContaLibre

**Contabilidad de código abierto para pymes y autónomos (España)**, inspirada en ContaSol. Todo funciona **en local**: servidor FastAPI + base de datos SQLite + interfaz web, sin nube. Soporta varias empresas y varios usuarios, cada uno con su sesión y su rol, pero todos los datos se quedan en tu máquina. La API REST está pensada para que, en el futuro, un modelo de IA local consulte los datos contables.

## Características

- **Plan General Contable**: cuentas del PGC PYMES precargadas, subcuentas ilimitadas, búsqueda.
- **Diario**: asientos con validación estricta de partida doble (importes en céntimos enteros: los cuadres son exactos), numeración automática por ejercicio.
- **Terceros**: clientes y proveedores con creación automática de subcuentas `430xxxx` / `400xxxx`.
- **Facturación**: facturas emitidas y recibidas con varias líneas y tipos de IVA (21/10/4/0 %), retenciones IRPF, asiento automático, cobro/pago con un clic.
- **Inmovilizado**: fichas de activos con amortización lineal (prorrateo por días el primer año, ajuste de redondeo en el último) y asientos de dotación automáticos.
- **Informes**: libro mayor, balance de sumas y saldos, pérdidas y ganancias, balance de situación y resumen de IVA trimestral estilo modelo 303.
- **Cierre y apertura de ejercicio**: regularización automática de las cuentas de gastos e ingresos (grupos 6/7) contra la 129, asiento de cierre que salda el resto de cuentas patrimoniales y asiento de apertura que reabre esos saldos en el ejercicio siguiente. Cierre secuencial obligatorio (no se puede cerrar un año sin haber cerrado y abierto los anteriores) y deshacer disponible mientras no se haya abierto/cerrado el ejercicio contiguo. Bloquea la creación o eliminación de asientos en ejercicios ya cerrados.
- **Modelos AEAT simplificados**: 303 (liquidación trimestral de IVA por casillas), 390 (resumen anual agregando los cuatro trimestres) y 347 (operaciones con terceros que superan 3.005,06 € anuales, con desglose trimestral). No cubren todos los regímenes/claves del formulario oficial (ver aviso en cada informe) y no sustituyen la presentación real ante la AEAT.
- **Exportación a PDF y Excel**: todos los informes (mayor, sumas y saldos, pérdidas y ganancias, balance) y los tres modelos AEAT se pueden descargar en PDF o Excel (`?formato=pdf|excel` en la API, botones en la interfaz).
- **Conciliación bancaria**: importación de extractos en formato cuaderno 43 de la AEB, conciliación automática por fecha e importe contra los apuntes existentes de la cuenta de tesorería, y conciliación manual (contra un apunte ya contabilizado o creando un asiento nuevo) para lo que no casa solo.
- **Multiempresa y usuarios**: cada empresa tiene su propia base de datos SQLite, completamente aislada de las demás (ni una consulta puede filtrar mal y mezclar datos: son ficheros distintos). Login por email/contraseña, sesión mediante cookie; un usuario puede pertenecer a varias empresas y cambiar entre ellas. Roles por empresa: **admin** (puede invitar/quitar usuarios) y **editor** (puede operar pero no gestionar usuarios).
- **API REST** completa y documentada (OpenAPI en `/docs`).

## Instalación y arranque

Requiere Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
contalibre            # o: uvicorn contalibre.main:app
```

Abre **http://localhost:8000** — la interfaz web — o **http://localhost:8000/docs** — la API. La primera vez, crea tu cuenta y tu empresa desde la pestaña "Crear cuenta" de la pantalla de acceso.

Los datos se guardan en el directorio `contalibre_data/` (variable de entorno `CONTALIBRE_DATA` para cambiar la ruta): `control.db` con los usuarios y empresas, y `empresas/{id}.db` con la contabilidad de cada empresa. Copia de seguridad = copiar ese directorio completo.

Si vienes de una versión anterior a multiempresa (un único `contalibre.db`), al arrancar se detecta y se adopta automáticamente como "Empresa migrada". El primer usuario que se registre después de la migración queda vinculado como administrador de esa empresa (y de cualquier otra que aún no tenga usuarios), además de crear la suya propia.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Integración con IA (hoja de ruta)

El diseño anticipa un asistente de IA **local** que responda preguntas sobre tus datos ("¿cuánto IVA tengo que pagar este trimestre?", "¿qué clientes me deben dinero?"):

1. `GET /api/v1/ia/contexto` devuelve el esquema de datos, las convenciones contables y el catálogo de endpoints de consulta: es el *system prompt* que necesita el modelo.
2. El modelo (Ollama, llama.cpp, o la API de Claude/otros) usa *tool calling* contra los endpoints REST (`/informes/*`, `/facturas`, `/asientos`…) para obtener los datos y responder.
3. Todo el tráfico queda en `localhost`: los datos contables nunca salen de tu máquina si el modelo es local.
4. Como la API exige sesión, el asistente ve exactamente los datos de la empresa activa del usuario que lo invoca: nunca mezcla información entre empresas.

## Estructura del proyecto

```
contalibre/
├── models.py          # Modelos contables SQLAlchemy (importes en céntimos): una base por empresa
├── models_control.py  # Modelos de control: Empresa, Usuario, Membresia, Sesion (base compartida)
├── auth.py            # Hash de contraseñas y tokens de sesión (sin dependencias externas)
├── deps.py            # Resuelve el usuario y la empresa activa a partir de la sesión
├── pgc.py             # Cuentas de arranque del PGC PYMES
├── services/          # Lógica contable (asientos, facturas, amortización, informes, cierre, aeat, conciliación)
├── routers/           # API REST /api/v1 (incluye auth.py, empresas.py e ia.py: contexto para LLM)
├── main.py            # Aplicación FastAPI + servidor de la interfaz
└── static/            # Interfaz web (vanilla JS, sin dependencias)
```

## Limitaciones actuales (roadmap)

- El balance de situación usa una clasificación orientativa por prefijos de cuenta; no sustituye a los formatos oficiales.

> ⚠️ ContaLibre es una herramienta de gestión; no constituye asesoramiento fiscal ni contable.

## Licencia

[MIT](LICENSE). Las contribuciones son bienvenidas.
