# Análisis del Proyecto: Task Queue API

> Documento generado a partir del análisis del código fuente del proyecto `task-queue-api`.

---

## 1. Resumen Ejecutivo

Este proyecto es un **"motor de automatización" (API) para el área de Recursos Humanos de Newport Capital Group**, una empresa peruana de entretenimiento. Su propósito principal es **procesar automáticamente los descansos médicos de los colaboradores**: descarga los documentos, extrae los datos con Inteligencia Artificial, los valida contra plataformas oficiales del gobierno peruano (EsSalud, CMP, SUNAT, MINCETUR) y detecta irregularidades o falsificaciones. Va dirigido al **equipo interno de Bienestar Social / RR.HH.**, que hoy en día haría ese trabajo manualmente y ahora recibe todo automatizado y auditable.

---

## 2. Arquitectura o Estructura General

Es una aplicación de Python (FastAPI) organizada en **capas bien definidas**. El flujo de llamadas es: **API → Servicio → Tarea en Celery (background) → adaptadores/entidades**.

```
main.py (FastAPI)
  └─ src/routes (endpoints HTTP)
       └─ src/routes/tasks/service.py (lógica de encolado)
            └─ src/background_tasks/image_tasks.py (13 tareas Celery)
                 ├─ src/core_services/       (lógica de negocio IA)
                 ├─ src/adapters/            (integración con servicios externos)
                 ├─ src/scrapers/            (automatización de navegador)
                 └─ src/entities/            (acceso a base de datos)
```

Los **componentes clave** son:

| Capa | Qué es | Ejemplos |
|---|---|---|
| **Routes** | Endpoints HTTP que reciben las peticiones | `/tasks`, `/crons` |
| **Background Tasks** | Trabajos pesados que corren en segundo plano con Celery | extracción IA, validaciones |
| **Core Services** | Lógica de negocio "inteligente" | extracción médica, validación, reputación de médicos, RAG de sanciones |
| **Adapters** | Puentes hacia sistemas externos | Microsoft Graph (OneDrive), Google Gemini, Serper, SMTP |
| **Scrapers** | Robots que navegan webs oficiales | EsSalud, CMP, COP, SUNAT, MINCETUR |
| **Entities** | Modelos de datos + repositorios (26 tablas) | descanso médico, médico, amonestación, RIT |
| **Utils** | Configuración y utilidades | conexiones BD, Redis, Celery |

Usa **dos bases de datos**: SQL Server (datos de negocio) y PostgreSQL (embeddings para búsqueda semántica).

---

## 3. Funcionamiento Paso a Paso

El proyecto tiene **varios flujos paralelos**, pero el central es el **ciclo de vida de un descanso médico**:

1. **Inicio — Sincronización:** Un colaborador llena un formulario Excel en OneDrive con sus descansos médicos y adjunta sus documentos (certificados, boletas, recetas). Una tarea de agenda (`sync_medical_leaves_from_onedrive`) baja ese Excel y los archivos desde SharePoint y registra cada fila en la tabla `descansos_medicos` con estado **PENDING** (pendiente).

2. **Procesamiento — Extracción con IA:** Un "scheduler" (`process_pending_medical_leaves_batch`) encola una tarea por cada descanso pendiente. La tarea `extract_medical_documents_with_ai` lee los PDFs y, usando **Gemini (IA de Google)**, extrae datos estructurados: nombre del paciente, diagnóstico, fechas, tipo de sustento (EsSalud o particular), etc. Guarda el resultado y cambia el estado a **TO_VALIDATE** (por validar).

3. **Procesamiento — Validación oficial:** Según el tipo, se valida en plataformas reales:
   - **EsSalud**: verifica el CITT (certificado de incapacidad temporal) en el portal del seguro.
   - **Particular**: verifica al médico en CMP/COP (colegios profesionales), la boleta en SUNAT y recetas.
   - Al mismo tiempo, un robot busca en internet noticias del médico (Serper) y Gemini genera un "audit" de **reputación** buscando señales de alerta (demandas, sanciones, clínicas cuestionadas).

4. **Resultado — Decisión:** El sistema marca el descanso como **APROBADO**, **RECHAZADO** (con motivo) o lo deja en estado de error para reintento. Todo queda registrado en tablas de auditoría (historial de estados, logs, motivos de rechazo), por lo que cualquier decisión es rastreable.

5. **Flujos secundarios:** Además gestiona **amonestaciones** (si un colaborador incumple el reglamento, la IA propone una sanción usando el Reglamento Interno de Trabajo — RIT — mediante búsqueda semántica) y los **retiros temporales en MINCETUR** (registro automático en el portal del Ministerio de Turismo con las credenciales de la empresa).

**Resultado final:** un descanso médico 100% digitalizado, validado contra fuentes oficiales y aprobado/rechazado por el sistema, con todo el proceso documentado.

---

## 4. Tecnologías, Herramientas o Recursos

**Lenguaje y frameworks:**
- **Python 3.12** + **FastAPI** (web API) + **Celery** (tareas en segundo plano) + **SQLAlchemy 2.0** (ORM asíncrono)

**Infraestructura:**
- **SQL Server** — base de datos principal de negocio
- **PostgreSQL + pgvector** — almacenamiento de embeddings
- **Redis** — cola de mensajes / broker de Celery
- **Docker + Gunicorn** — despliegue en contenedores
- **uv** — gestor de paquetes (similar a pip pero moderno y rápido)

**Servicios externos (requieren cuentas/credenciales):**
- **Google Gemini / Vertex AI** — IA para extraer datos y generar análisis
- **Google Serper** — buscador para reputación de médicos
- **Microsoft Graph API** — acceso a OneDrive/SharePoint (OAuth2 con Azure AD)
- **Servidor SMTP** — envío de correos
- **SAP (DM-OAM)** — datos de colaboradores

**Automatización de navegador:**
- **Playwright + Chromium** — para navegar los portales gubernamentales (EsSalud, CMP/COP, MINCETUR)

**Recursos humanos:** un desarrollador backend senior con Python y nociones de IA (prompts), y el **equipo de RR.HH./Bienestar Social** que opera el resultado. Las credenciales de las plataformas oficiales (CMP, MINCETUR, SUNAT) son indispensables.

---

## 5. Puntos Críticos o de Mayor Riesgo

1. **Dependencia de portales externos que cambian** — Los scrapers (EsSalud, CMP, MINCETUR) dependen del HTML de webs gubernamentales. Si esos sitios cambian su diseño, todo el flujo de validación se rompe. Hay _health checks_ y alertas por correo, pero es fragilidad estructural.

2. **Una sola tarea monstruosa** — `image_tasks.py` tiene **2.324 líneas y 13 tareas en un único archivo**. Es difícil de mantener y de testear.

3. **Credenciales y seguridad** — El sistema maneja credenciales reales de plataformas gubernamentales (clave SOL de SUNAT, CMP, correos). Están cifradas en BD pero cualquier fuga compromete la operación. También hay secretos (Azure AD, Gemini, Serper) en el `.env`.

4. **Scraping frágil por naturaleza** — Navegar portales oficiales con Playwright requiere manejar sesiones, captchas, timeouts y sesiones expiradas. Los errores no son técnicos sino "humanos" (que el portal empiece a pedir doble autenticación, por ejemplo).

5. **Costos de IA impredecibles** — La extracción con Gemini procesa miles de documentos; el costo de API crece con el volumen. No se ve control de presupuesto.

6. **Sesiones de BD duplicadas por diseño** — Cada tarea Celery crea **su propio motor de BD** (por razones técnicas válidas de Celery), pero eso duplica la lógica de conexión en decenas de lugares y es fuente de errores.

7. **Falta de pruebas automatizadas** — No se ve una carpeta de tests. Para un sistema que valida documentos oficiales, la ausencia de tests unitarios/integración es un riesgo importante.

---

## 6. Glosario Rápido

- **Celery** — Sistema de "cola de tareas". Una petición HTTP se responde al instante, y el trabajo pesado (leer PDFs, navegar webs) se encola para que un *worker* (trabajador) en segundo plano lo haga. Es como dar un pedido a cocina y que te avisen cuando esté listo, en vez de esperar parado.

- **ORM (SQLAlchemy)** — Mapero objeto-relacional. Te permite manejar las tablas de la base de datos como si fueran objetos de Python: en vez de escribir `SELECT * FROM descansos_medicos WHERE estado='PENDIENTE'`, escribes `select(MedicalLeave).where(status == ...)`. El código de `src/entities/medical_leave/model.py:28` convierte la clase `MedicalLeave` en la tabla `descansos_medicos`.

- **Endpoint** — Una "puerta de entrada" de la API: una combinación de dirección web + método HTTP (POST/GET). Por ejemplo, `POST /tasks/document-validations` dispara la validación de documentos.

- **Scheduler** — Una tarea "coordinadora" que no hace el trabajo directamente, sino que reparte el trabajo a otras tareas. El scheduler `process_pending_medical_leaves_batch` obtiene todos los pendientes y encola una tarea individual por cada uno.

- **Embedding** — Forma de "traducir" texto en una lista de números que una IA puede comparar por similitud. Si guardas las sanciones del RIT como embeddings en PostgreSQL, luego puedes buscar "falta grave por reincidencia" y encontrar el artículo del reglamento más parecido aunque no use las mismas palabras.

---

## 7. Conexión a Base de Datos y FastAPI (deep-dive)

### 7.1 Mapa general del flujo

```
HTTP request → Endpoint (routes) → Controller → [inyecta sesión] → Service → Repository → SQL Server/PostgreSQL
                                                     │                │
                                                     │                └─ (si no inyecta) abre su propia sesión
                                                     └─ AsyncSessionDepends
```

### 7.2 Los 4 archivos clave

| Archivo | Rol |
|---|---|
| `src/settings.py` | Lee el `.env` y expone todas las credenciales en el objeto `setting` (usuario, host, puerto, contraseña de BD) |
| `src/utils/conexion_bd.py` | Crea la conexión **a SQL Server** y la "fábrica de sesiones" |
| `src/utils/conexion_pg.py` | Crea la conexión **a PostgreSQL** (para la IA de sanciones/embeddings) |
| `src/dependencies/async_bd.py` | El "adaptador" que le da una sesión a FastAPI por cada petición |

### 7.3 Qué hace cada pieza, en detalle

#### a) La conexión en sí — `conexion_bd.py:14-30`

Se construye la "dirección" de la BD con `URL.create("mssql+aioodbc", ...)`, usando las variables que leyó `settings.py`. Con esa dirección se crea el **motor** (`create_async_engine`), que es la capa encargada de mantener un **pool de conexiones** reales a SQL Server.

```python
async_engine = create_async_engine(uri, pool_pre_ping=True)      # motor + pool
Async_session_local = async_sessionmaker(bind=async_engine, ...)  # fábrica de sesiones
```

- `pool_pre_ping=True`: antes de usar una conexión, verifica que siga viva (evita errores por conexiones "podridas").
- `Async_session_local` NO es una sesión: es una **fábrica** que crea sesiones a pedido. Es la pieza clave para entender el resto.

En `conexion_bd.py:33` también se define `Model`, la clase base de la que heredan **todas las entidades** (tablas) del proyecto.

#### b) La inyección de sesión en FastAPI — `dependencies/async_bd.py:9-14`

Este es el "puente" entre FastAPI y la base de datos. Es un **generador** (por el `yield`):

```python
async def get_async_session():
    async with Async_session_local() as s:   # abre sesión
        yield s                              # la entrega al endpoint

AsyncSessionDepends = Annotated[AsyncSession, Depends(get_async_session)]
```

Cuando un método de un controller declara el parámetro `async_session: AsyncSessionDepends`, FastAPI:
1. **Abre una sesión** antes de ejecutar el endpoint,
2. **la inyecta** para que el código la use,
3. y al terminar la petición, el `async with` la **cierra automáticamente**.

Este patrón se llama **"sesión por petición"**: cada request tiene su propia sesión aislada, sin compartir estado entre pedidos.

#### c) Cómo consume las tablas — el patrón Entidad + Repositorio

**Paso 1 — El modelo** (`entities/medical_leave/model.py:28-76`): una clase Python que **mapea a una tabla real que YA existe** en SQL Server:

```python
class MedicalLeave(Model):
    __tablename__ = "descansos_medicos"        # tabla real en BD
    status: Mapped[MedicalLeaveStatusEnum] = mapped_column(  # columna "estado"
        Enum(...), name="estado", ...)
    start_date: Mapped[date] = mapped_column(Date, name="fecha_inicio", ...)
```

Fíjate: `status` en Python → `estado` en BD, `start_date` → `fecha_inicio`. Este proyecto **no crea tablas**: mapea a un esquema ya existente (las tablas están en español, del sistema principal de Newport).

**Paso 2 — El repositorio** (`entities/medical_leave/repository.py`): recibe la sesión inyectada y ejecuta consultas específicas:

```python
class MedicalLeaveRepository(RepositoryBase[MedicalLeave]):
    def __init__(self, async_session):        # hereda de RepositoryBase (entities/__init__.py:15)
        self.async_session = async_session

    async def get_medical_leaves_pending(self):   # lee la tabla "descansos_medicos"
        query = select(MedicalLeave).where(
            MedicalLeave.status == MedicalLeaveStatusEnum.PENDING)
        return list((await self.async_session.execute(query)).scalars().all())
```

El `RepositoryBase` (`entities/__init__.py:11-25`) ya trae `commit()`, `flush()` y `rollback()` para gestionar transacciones.

#### d) El flujo completo en un ejemplo real

Tomemos el endpoint `POST /tasks/reputational-validations`:

1. **Route** (`routes/tasks/__init__.py:42-49`) declara que la URL responde con el método del controller.
2. **Controller** (`controller.py:118`) llama al servicio. Ten en cuenta que este método **no** usa la sesión inyectada; el servicio abre la suya.
3. **Service** (`service.py:162-176`): aquí está el consumo real de BD:

```python
async with Async_session_local() as session:            # abre sesión MANUALMENTE
    doctor_repository = DoctorRepository(session)        # crea repositorio
    expired_doctors = await doctor_repository.get_with_expired_cache(...)  # consulta
```

O sea, en este proyecto conviven **dos patrones**:

| Patrón | Dónde | Mecanismo |
|---|---|---|
| **Inyección por FastAPI** | Controller `trigger_extraction_image_task` (usa `AsyncSessionDepends`) | FastAPI abre/cierra la sesión |
| **Sesión manual** | Los `Service` (extracción, validación, reputación) | Usan `async with Async_session_local() as session:` directamente |

En la práctica, **la mayoría de consultas reales usan el patrón manual dentro de los servicios**, en vez de la inyección; la dependencia `AsyncSessionDepends` está declarada pero apenas se usa. Es una inconsistencia de diseño a tener en cuenta.

#### e) ¿Y PostgreSQL? — `conexion_pg.py`

Exactamente el mismo patrón, pero con `postgresql+asyncpg` y exponiendo `AsyncPgSession`. Solo se usa en las tareas de IA del RIT (ingesta de reglamentos y búsqueda semántica de sanciones), que abren sesión de PostgreSQL además de la de SQL Server.

### 7.4 Caso especial: Celery (las tareas de fondo)

Aquí está la diferencia importante. Las tareas Celery **no reciben sesiones de FastAPI** (no hay petición HTTP). Por eso cada tarea crea su **propio motor de BD, independiente y con `NullPool`** (`background_tasks/image_tasks.py:166-193`):

```python
def _create_celery_engine():
    return create_async_engine(uri, poolclass=NullPool, pool_pre_ping=True)
```

¿Por qué? Celery clona el proceso del worker y, si se comparten conexiones de un pool entre procesos clonados, se corrompen. Con `NullPool` **cada tarea abre su conexión cuando empieza y la cierra al terminar**, sin reutilizar. Es más lento pero a prueba de esa corrupción.

Además hay una **tercera base de datos** (`conexion_horacio.py`): la BD de otro servicio (Horacio Backend), de la que se sacan las credenciales MINCETUR cifradas. Tiene su propio motor con `NullPool` solo para tareas Celery.

### 7.5 Particularidades y riesgos de esta arquitectura de BD

1. **Tres puntos de conexión duplicados** — El mismo patrón de conexión a SQL Server se repite: en `conexion_bd.py`, dentro de cada tarea Celery (`_create_celery_engine`) y en `conexion_horacio.py`. Cualquier cambio de credenciales/driver exige tocar varios lugares.

2. **`pool_pre_ping` + `NullPool` combinados** — En SQL Server se usa pool típico; en Celery, `NullPool`. Entender cuál se aplica en cada contexto es clave para diagnosticar "conexiones que se cuelgan".

3. **Dos formas de abrir sesión** — La inyección de FastAPI y la sesión manual coexisten. Si no se respeta el patrón, se puede abrir una sesión y no cerrarla (fugas de conexiones).

4. **`expire_on_commit=False`** — En `conexion_bd.py:29`. Significa que tras un commit los objetos siguen usables (no se "invalidan"). Cómodo, pero hay que cuidar datos viejos: si dos procesos leen y escriben a la vez, podrías guardar datos obsoletos.

5. **Autocompletar: las tablas son un esquema existente** — No hay migraciones ni creación de tablas aquí. Si otra app cambia una columna, este proyecto se rompe silenciosamente (consulta a una columna que ya no existe).

---

## 8. Trazado detallado de transacciones (lectura/escritura en BD)

### 8.1 CASO 1 — `extract_medical_documents_with_ai` (extracción con IA)

Esta es la tarea que más claramente muestra el **patrón completo**: lee, escribe, y hace **dos commits separados**.

#### Fase 0 — Apertura de BD (`image_tasks.py:399-416`)

- Crea su propio motor con `_create_celery_engine()` → pool `NullPool` (cada tarea abre conexión nueva).
- Crea el sessionmaker y abre **UNA sola sesión** (`async with async_session_maker() as session`).
- Instancia **7 repositorios** (medical_leave, attachment, certificate, receipt, prescription, log, status_history) **todos sobre la misma sesión**. Este es el detalle clave: comparten la misma transacción.

#### Paso 1 — Lecturas iniciales

| Línea | Qué lee | Tabla |
|---|---|---|
| 421 | `get_by_id(medical_leave_id)` | `descansos_medicos` |
| 431 | `get_by_medical_leave_id()` | adjuntos |

#### Paso 2 — Procesamiento con IA y escrituras

El servicio `MedicalDocumentExtractionService` (líneas 438-444) lee el PDF del adjunto, llama a Gemini y **inserta** los resultados usando los repositorios que recibe de la misma sesión → inserciones en `medical_certificate_extraction`, `receipt_extraction` y/o `prescription_extraction`.

Si hubo extracciones:

| Línea | Operación | Tabla afectada |
|---|---|---|
| 456-457 | Actualiza `status` a `REGISTERED` | `descansos_medicos` |
| 460-468 | Inserta historial (`previous_status` → `new_status`) | `medical_leave_status_history` |
| 471-481 | Inserta log de extracción | `medical_leave_log` |
| 484-507 | Actualiza banderas del log (citt/receta/boleta) | `medical_leave_log` |

#### Paso 3 — PRIMER commit (`image_tasks.py:512`)

```python
await session.commit()
```

Todo lo anterior (cambio de estado + historial + log) se graba **en un único commit atómico**. Si algo falla antes, no se escribe nada de eso.

#### Paso 4 — SEGUNDO commit: lanzar validación automática

Después del commit, sigue el flujo "cambiar a POR_VALIDAR y encolar validación" (`image_tasks.py:517-639`):

| Línea | Operación |
|---|---|
| 532-533 | Cambia `status` a `TO_VALIDATE` (ES SALUD) / 624-625 (PARTICULAR) |
| 536-543 / 628-635 | Inserta **otro** registro en `medical_leave_status_history` |
| 544 / 636 | **Segundo commit** |
| 547 / 639 | Encola la tarea de validación (`validate_essalud_medical_certificate.delay()` o `validate_particular_...`) |

**Detalle que explica todo:** `expire_on_commit=False` (`conexion_bd.py:29`) permite que tras el primer commit los objetos sigan "vivos" en la sesión. Por eso en la línea 519-521 pueden seguir usando el mismo `session` para releer el certificado y modificar el mismo `medical_leave` en memoria. Si estuviera `expire_on_commit=True`, esos objetos se invalidarían al hacer commit y el código explotaría.

#### Si NO se extrajo nada

- Solo escribe el log de fallo (`append_to_log` línea 678-686) y hace commit (línea 688), dejando el descanso en su estado anterior.

#### Manejo de errores: `try/except/finally` (`695-702`)

- Si algo falla: registra el error y hace `raise` (no hay `rollback()` explícito).
- Al cerrarse el bloque `async with ... as session`, la sesión se cierra **sin hacer commit** → en la práctica eso es un "rollback implícito" (lo que no se commiteó se descarta).
- `engine.dispose()` en `finally` (línea 702): cierra la conexión pase lo que pase.

### 8.2 CASO 2 — `sync_medical_leaves_from_onedrive` (sincronización con savepoints)

Esta usa una estrategia de transacciones **distinta y más elaborada**: **un solo commit al final + savepoints (sub-transacciones) por fila**.

#### Cómo empieza (`image_tasks.py:1129-1147` + `cron_services/service.py`)

- Una sesión única para todo el proceso.
- El servicio `CronJobsService.sync_medical_leaves_from_onedrive` procesa **fila por fila del Excel**.

#### Savepoint individual por fila (`cron_services/service.py:228`)

```python
async with medical_leave_repository.async_session.begin_nested():
    ...
```

Dentro de ese bloque: consulta duplicados, consulta colaborador en SAP, crea/actualiza el `MedicalLeave`, descarga adjuntos de SharePoint y crea registros `Attachment`.

**¿Qué es un savepoint?** Un "punto de restauración" dentro de la transacción grande. Si una fila falla, solo se revierte **esa fila** (al savepoint), sin dañar las demás, y el proceso continúa con la siguiente. Es el patrón correcto aquí, porque una fila con datos inválidos no debe tumbar la sincronización de las otras 100.

#### Al final: commit único o rollback total (`cron_services/service.py:196-205`)

- `await medical_leave_repository.commit()` (línea 196): **una sola confirmación** graba todas las filas exitosas + las marcadas como ERROR.
- Si una excepción global ocurre: `await medical_leave_repository.rollback()` (línea 204) → no se graba nada.
- Después del commit, dispara el pipeline de extracción IA (`process_pending_medical_leaves_batch.delay()`).

### 8.3 Comparación de los 3 patrones de transacción que usa el proyecto

| Patrón | Dónde | Comportamiento |
|---|---|---|
| **Un commit al final** | Validaciones EsSalud/Particular/reputación | Todo lo del servicio se confirma junto (`image_tasks.py:826`) |
| **Dos commits intermedios** | Extracción con IA | Estado REGISTERED se graba antes de cambiar a POR_VALIDAR |
| **Savepoints + commit único** | Sincronización OneDrive | Cada fila es aislada; al final commit masivo o rollback total |

### 8.4 Riesgos concretos en estas transacciones

1. **No-idempotencia + reintentos de Celery** — Las tareas tienen `autoretry_for=(Exception,)` con 3 reintentos. En la extracción, el **primer commit ya ocurrió** antes de que pudiera fallar el segundo (validación). Si el fallo llega después del commit, al reintentar se **re-ejecuta la extracción completa**: Gemini vuelve a procesar y se podrían **duplicar** filas en `certificate/receipt/prescription_extraction`. El scheduler filtra por estado PENDING, pero la tarea individual directamente da por hecho que la extracción debe correrse.

2. **Rollback implícito que depende del cierre** — En la extracción no hay `rollback()` explícito; depende de que al cerrar la sesión se descarte lo no commiteado. Funciona con SQLAlchemy async, pero es frágil: si algún día se reutiliza la sesión (patrón de pool en vez de NullPool), quedarían datos sucios.

3. **Dos commits "a mitad de camino"** — Entre el commit de `REGISTERED` (línea 512) y el de `TO_VALIDATE` (línea 544/636) hay una ventana donde el descanso queda en `REGISTERED` sin tarea de validación. Si el proceso muere justo ahí (crash, timeout de 6 minutos), el registro queda **huérfano** (registrado pero nunca validado). Hay un "parche" para esto: la tarea `revalidate_stuck_particular_certificates`, que detecta los estancados en `TO_VALIDATE`... pero no rescata los que se quedaron en `REGISTERED`.

4. **`NullPool` en Celery = sin reutilización** — Cada tarea crea conexión propia, pero a cambio no hay "limpieza de conexiones muertas". Si el Worker se cae (timeout, `soft_time_limit`), la conexión queda abierta hasta que el SO la limpie.

5. **No hay bloqueos/locks** — Dos tareas (extracción + re-validación, o dos sincronizaciones simultáneas) pueden leer y escribir el mismo `medical_leave` sin `SELECT ... FOR UPDATE`. En la práctica la sincronización y la extracción corren en momentos distintos, pero no está protegido por diseño.

---

*Fin del documento.*