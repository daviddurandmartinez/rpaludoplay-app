# Análisis General del Proyecto Ludoplay Sync App

## 1. Propósito Principal

**Ludoplay Sync App** resuelve un problema operativo crítico: la **sincronización automática de registros de jugadores desde el portal oficial de MINCETUR** (Ministerio de Comercio Exterior y Turismo del Perú) hacia la base de datos interna del sistema Ludoplay.

**A nivel funcional:**

- Accede al portal de la "Clave SOL" de MINCETUR mediante automatización web (Selenium)
- Descarga un PDF que contiene el registro oficial de personas vinculadas a la actividad de juego
- Extrae los datos del PDF (nombres, DNI, código de registro, ubigeo, fecha de publicación, foto)
- Compara contra la base de datos existente e identifica: nuevos registros, bajas y reactivaciones
- Ejecuta las operaciones masivas en la base de datos SQL Server
- Gestiona la migración de fotos del directorio temporal al directorio final

**En resumen ejecutivo:** Es un sistema que mantiene la base de datos de Ludoplay sincronizada con el registro oficial de MINCETUR, garantizando cumplimiento normativo y operatividad sin intervención manual.

---

## 2. Mapa de la Estructura

```
rpaludoplay-app/
│
├── src/
│   ├── main.py                    ← Punto de entrada (CLI + API)
│   ├── settings.py                ← Configuración desde .env
│   │
│   ├── scrapers/
│   │   └── scraper.py             ← Automatización Selenium (MINCETUR)
│   │
│   ├── entities/
│   │   ├── __init__.py            ← Base genérica de repositorio
│   │   └── player/
│   │       ├── model.py           ← Modelo ORM (tabla players_player)
│   │       └── repository.py      ← Acceso a datos (CRUD async)
│   │
│   ├── routes/
│   │   └── players/
│   │       ├── controller.py      ← Endpoints REST (FastAPI)
│   │       ├── service.py         ← Lógica de negocio
│   │       └── schemas.py         ← Schemas Pydantic (request/response)
│   │
│   ├── dependencies/
│   │   └── async_bd.py            ← Inyección de sesión DB
│   │
│   ├── utils/
│   │   ├── constants.py           ← URLs, XPaths, rutas, selectores
│   │   ├── connection_bd.py       ← Engine + session SQLAlchemy
│   │   ├── sync_merger.py         ← Lógica de comparación (merge)
│   │   └── clear_path.py          ← Limpieza de archivos temporales
│   │
│   ├── static/images/             ← Fotos de jugadores
│   └── logs/app.log               ← Log de la aplicación
│
├── .env                           ← Variables de entorno (credenciales)
├── requirements.txt               ← Dependencias Python
└── readme.md                      ← Documentación técnica
```

### Rol de cada capa

| Capa             | Archivos                                             | Qué hace                                                               | Analogía                                                            |
| ---------------- | ---------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Scraper**      | `scraper.py`                                         | Ingresa al portal de MINCETUR, descarga el PDF y extrae los datos      | El "recolector" que va al sitio oficial y trae la información cruda |
| **Entidades**    | `model.py`, `repository.py`                          | Define QUÉ datos se guardan y CÓMO se acceden                          | El "catálogo maestro" y el "archivista"                             |
| **Rutas**        | `controller.py`, `service.py`, `schemas.py`          | Recibe peticiones externas, aplica reglas de negocio, responde         | La "ventanilla de atención"                                         |
| **Utilidades**   | `sync_merger.py`, `connection_bd.py`, `constants.py` | Compara datos nuevos vs existentes, conecta a la DB, define parámetros | El "motor de decisiones" y la "conexión telefónica"                 |
| **Dependencias** | `async_bd.py`                                        | Entrega una sesión de base de datos por cada petición                  | El "acta de acceso" que se entrega por uso                          |

---

## 3. Flujo de Ejecución End-to-End

Tiene **dos formas de funcionar**:

- **CLI** (`python main.py --sync`): ejecuta el pipeline completo automatizado (scraper → merge → sync)
- **API** (`python main.py --server`): levanta una REST API en FastAPI para gestionar jugadores manualmente

```
┌─────────────────────────────────────────────────────────────┐
│  PASO 1: INICIALIZACIÓN                                     │
│  main.py carga settings.py → lee .env → obtiene credenciales│
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PASO 2: SCRAPING MINCETUR                                  │
│  scraper.py abre Chromium → ingresa a la extranet →         │
│  descarga PDF → extrae tabla con pdfplumber + fotos con     │
│  PyMuPDF → devuelve DataFrame de pandas                     │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PASO 3: CONSULTA A BASE DE DATOS                           │
│  connection_bd.py ejecuta SELECT * FROM players_player →    │
│  devuelve DataFrame con registros existentes                │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PASO 4: MERGE (Comparación)                                │
│  sync_merger.py compara los dos DataFrames usando           │
│  operaciones de conjunto sobre la columna id_card:          │
│                                                             │
│  • df_insert → IDs en scraper pero NO en DB (nuevos)        │
│  • df_deactivate → IDs en DB activos pero NO en scraper     │
│    (bajas)                                                  │
│  • df_reactivate → IDs en DB inactivos pero SÍ en scraper   │
│    (reactivaciones)                                         │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PASO 5: SINCRONIZACIÓN EN BASE DE DATOS                    │
│  main.py invoca PlayerSyncService.sync_all():               │
│                                                             │
│  5a. deactivate → UPDATE SET is_active=False WHERE id_card  │
│  5b. reactivate → UPDATE SET is_active=True WHERE id_card   │
│  5c. insert → INSERT de registros nuevos + copia de fotos   │
│                                                             │
│  Todo dentro de una transacción: si falla, se hace rollback │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PASO 6: LIMPIEZA                                           │
│  clear_path.py elimina archivos temporales de las rutas:    │
│  static/images/, directorio de fotos de salida, downloads   │
└─────────────────────────────────────────────────────────────┘
```

### Escenario B: API REST (`python main.py --server`)

```
  Cliente externo                  FastAPI                     SQL Server
       │                             │                            │
       │  POST /api/v1/players       │                            │
       │  {players: [...]}           │                            │
       │────────────────────────────►│                            │
       │                             │  PlayerSyncService         │
       │                             │  .insert_players()         │
       │                             │───────────────────────────►│
       │                             │          Bulk INSERT       │
       │                             │◄───────────────────────────│
       │  201 {inserted: N}          │                            │
       │◄────────────────────────────│                            │
```

### Endpoints disponibles

| Método  | Ruta                         | Descripción               |
| ------- | ---------------------------- | ------------------------- |
| `POST`  | `/api/v1/players`            | Insertar nuevos jugadores |
| `PATCH` | `/api/v1/players/deactivate` | Desactivar por IDs        |
| `PATCH` | `/api/v1/players/reactivate` | Reactivar por IDs         |
| `POST`  | `/api/v1/players/sync`       | Sincronización completa   |
| `POST`  | `/api/v1/players/{id}/photo` | Subir foto                |
| `GET`   | `/health`                    | Verificar salud del API   |

---

##

---

## 4. Stack Tecnológico

| Componente        | Tecnología                              | Versión         |
| ----------------- | --------------------------------------- | --------------- |
| Framework web     | FastAPI                                 | ≥ 0.115         |
| ORM               | SQLAlchemy 2.0 (async)                  | ≥ 2.0.45        |
| Base de datos     | SQL Server (vía aioodbc/ODBC Driver 18) | —               |
| Scraping          | Selenium + Chromium                     | ≥ 4.25          |
| Extracción de PDF | pdfplumber + PyMuPDF                    | ≥ 0.11 / ≥ 1.24 |
| Datos tabulares   | pandas                                  | ≥ 2.2           |
| Configuración     | pydantic-settings + python-dotenv       | ≥ 2.10          |
| Servidor ASGI     | uvicorn                                 | ≥ 0.30          |

-
