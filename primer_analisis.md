# Análisis del Proyecto: Ludoplay Sync API

---

## 1. ¿Qué es este proyecto?

**Ludoplay Sync API** es una aplicación que **sincroniza registros de jugadores** desde el portal del MINCETUR (Ministerio de Turismo del Perú) hacia una base de datos SQL Server.

El flujo central es:

```
MINCETUR (web) → Scraper Selenium → PDF → Parseo de datos → Merge con BD → Sincronización
```

Tiene **dos formas de funcionar**:
- **CLI** (`python main.py --sync`): ejecuta el pipeline completo automatizado (scraper → merge → sync)
- **API** (`python main.py --server`): levanta una REST API en FastAPI para gestionar jugadores manualmente

---

## 2. Estructura actual del proyecto

```
src/
├── main.py                    ← Punto de entrada (CLI + FastAPI)
├── settings.py                ← Lee credenciales del .env
├── scrapers/
│   └── scraper.py             ← Selenium: navega MINCETUR, descarga PDF, extrae datos
├── entities/
│   ├── __init__.py            ← RepositoryBase (commit/rollback genérico)
│   └── player/
│       ├── model.py           ← Modelo SQLAlchemy (tabla players_player)
│       └── repository.py      ← Consultas SQL (CRUD de jugadores)
├── routes/
│   └── players/
│       ├── controller.py      ← Endpoints HTTP (POST, PATCH)
│       ├── service.py         ← Lógica de negocio (insertar, desactivar, fotos)
│       └── schemas.py         ← Schemas Pydantic (request/response)
├── dependencies/
│   └── async_bd.py            ← Inyección de sesión SQL en FastAPI
└── utils/
    ├── constants.py           ← Paths, URLs, XPaths del scraper
    ├── connection_bd.py       ← Motor SQLAlchemy + fábrica de sesiones
    ├── sync_merger.py         ← Lógica de merge (compara scraper vs BD)
    └── clear_path.py          ← Limpia archivos temporales
```

---

## 3. ¿Cumple con Arquitectura Hexagonal?

**Respuesta corta: NO la aplica. Tiene bases, pero le faltan piezas clave.**

### Lo que SÍ tiene (la base)

| Concepto Hexagonal | Componente en tu proyecto | Estado |
|---|---|---|
| **Entidad de Dominio** | `entities/player/model.py` (Player) | Existe, pero es un modelo SQLAlchemy puro |
| **Puerto de salida** | `entities/player/repository.py` | Parcial: es concreto, no abstracto |
| **Adaptador de entrada (HTTP)** | `routes/players/controller.py` | Existe |
| **Adaptador de infraestructura** | `connection_bd.py`, `async_bd.py` | Existe |
| **Lógica de negocio** | `routes/players/service.py` | Existe, pero acoplada a implementaciones |

### Lo que FALTA (por qué no es Hexagonal)

La Arquitectura Hexagonal tiene **3 reglas de oro**:

1. **El dominio (entities) NUNCA depende de nada externo** (ni SQLAlchemy, ni FastAPI, ni archivos)
2. **Los puertos son interfaces abstractas** (contratos), no implementaciones concretas
3. **La inversión de dependencia**: el dominio define QUÉ necesita (puertos), y la infraestructura CÓMO se hace (adaptadores)

Tu proyecto falla en las 3:

```
Player (entity) ──usa──► SQLAlchemy       ← VIOLACIÓN: dominio acoplado a ORM
Repository (entity) ──usa──► SQLAlchemy   ← VIOLACIÓN: no hay interfaz abstracta
Service (routes) ──usa──► shutil          ← VIOLACIÓN: lógica de negocio con lógica de archivos
sync_merger (utils) ──usa──► pandas       ← Mezcla dominio con infraestructura
```

### Diagrama: cómo está vs cómo debería ser

**ACTUAL (sin Hexagonal):**
```
┌─────────────────────────────────────────────┐
│  main.py (orchestration + CLI + FastAPI)    │  ← Todo mezclado
├─────────────────────────────────────────────┤
│  controller.py ──► service.py ──► repo.py   │  ← Cadena rígida
├─────────────────────────────────────────────┤
│  model.py (SQLAlchemy)                      │  ← Dominio = ORM
├─────────────────────────────────────────────┤
│  connection_bd.py │ scraper.py              │  ← Infraestructura
└─────────────────────────────────────────────┘
```

**IDEAL (Hexagonal):**
```
         ┌──────────────────────────┐
         │    DOMINIO (centro)      │
         │  Player (entidad pura)   │
         │  PuertoSalida (interfaz) │
         │  PuertoEntrada (interfaz)│
         │  Lógica de sync/merge    │
         └──────┬───────────┬───────┘
                │           │
    ┌───────────▼──┐   ┌───▼──────────────┐
    │ ADAPTADOR    │   │ ADAPTADOR        │
    │ Entrada:     │   │ Salida:          │
    │ FastAPI/CLI  │   │ SQL Server       │
    │ Selenium     │   │ FileSystem       │
    └──────────────┘   └──────────────────┘
```

---

## 4. Plan de refactorización paso a paso

### Paso 1: Crear el dominio puro (sin dependencias)

Crear `src/domain/player.py` con una clase `Player` **pura** (dataclass o Pydantic), sin SQLAlchemy:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PlayerDomain:
    id: int | None
    code: int
    first_name: str
    last_name: str
    card_type: int
    id_card: str
    ubigeo: str
    published_at: datetime
    contact: str
    photo: str | None
    is_active: bool
```

Crear `src/domain/ports.py` con las interfaces:

```python
from abc import ABC, abstractmethod
from .player import PlayerDomain

class PlayerRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id_cards(self, id_cards: list[str]) -> list[PlayerDomain]: ...
    @abstractmethod
    async def bulk_create(self, players: list[PlayerDomain]) -> None: ...
    @abstractmethod
    async def deactivate_by_id_cards(self, id_cards: list[str]) -> int: ...
    @abstractmethod
    async def reactivate_by_id_cards(self, id_cards: list[str]) -> int: ...

class PhotoStoragePort(ABC):
    @abstractmethod
    def copy_photo(self, source: str, id_card: str) -> str: ...
    @abstractmethod
    def save_photo(self, id_card: str, content: bytes) -> str: ...
```

### Paso 2: Adaptador de infraestructura (SQLAlchemy)

Mover `model.py` y `repository.py` a `src/adapters/sql/`:

```
src/adapters/
└── sql/
    ├── player_model.py      ← SQLAlchemy model (lo que hoy es model.py)
    ├── player_repository.py ← Implementa PlayerRepositoryPort
    └── connection.py        ← Engine + session (lo que hoy es connection_bd.py)
```

### Paso 3: Adaptador de scraping

Mover `scraper.py` a `src/adapters/scraping/mincetur_scraper.py`, y definir un **puerto de entrada**:

```python
class MinceturPort(ABC):
    @abstractmethod
    def fetch_players(self, credentials) -> list[PlayerDomain]: ...
```

### Paso 4: Service layer en el dominio

Mover la lógica de sync y merge **fuera** de `routes/` hacia `src/domain/sync_service.py`:

```python
class PlayerSyncUseCase:
    def __init__(self, repo: PlayerRepositoryPort, scraper: MinceturPort, photos: PhotoStoragePort):
        self.repo = repo
        self.scraper = scraper
        self.photos = photos

    async def run_full_sync(self, credentials) -> SyncResult:
        # Lógica de negocio pura
        ...
```

### Paso 5: Adaptador CLI y API

- `src/adapters/api/controller.py` → FastAPI (como hoy, pero inyectando dependencias)
- `src/adapters/cli/main.py` → CLI con argparse (como hoy)

### Paso 6: Inyección de dependencias

En `src/main.py` o un archivo de composición:

```python
# Composición de dependencias
repo = PlayerRepositorySQL(session)
scraper = MinceturScraperAdapter()
photos = FileSystemPhotoAdapter()
use_case = PlayerSyncUseCase(repo, scraper, photos)
```

---

## 5. Resumen ejecutivo (5 puntos clave)

1. **¿Qué hace?** Sincroniza automáticamente los registros de jugadores de MINCETUR (gobierno peruano) hacia una base de datos SQL Server, detectando altas, bajas y reactivaciones.

2. **¿Cómo funciona?** Usa Selenium para navegar el portal del MINCETUR, descarga un PDF, extrae los datos con PyMuPDF/pdfplumber, compara con la BD existente (merge), y ejecuta INSERT/UPDATE en lote. También expone una API REST para operaciones manuales.

3. **Estado de arquitectura:** Tiene una estructura por capas (entities → service → controller), pero **no es Hexagonal** porque el dominio depende directamente de SQLAlchemy, los puertos no son interfaces abstractas, y la lógica de negocio está dispersa entre utils y routes.

4. **Ventaja principal del proyecto:** El pipeline de sync es robusto: maneja inserts, desactivaciones, reactivaciones, y copia de fotos de forma atómica. El merge en `sync_merger.py` es la pieza central de lógica de negocio.

5. **Para presentar:** Es una **herramienta de automatización RPA** (no una app web tradicional). Su valor es eliminar el trabajo manual de revisar el registro de ludopatía del MINCETUR y mantener la base de datos actualizada. La API REST es secundaria — el verdadero motor es el pipeline CLI de sincronización.
