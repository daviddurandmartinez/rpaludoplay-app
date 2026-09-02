# Análisis Profundo: `src/entities` y `src/routes`

---

## CAPA ENTITIES (`src/entities/`)

Esta capa define **qué datos existen** y **cómo se accede a ellos**. Es la fundación del sistema.

---

### `entities/__init__.py` — La Base Genérica (29 líneas)

```python
class RepositoryBase(Generic[T]):
    def __init__(self, async_session: AsyncSession):
        self.async_session = session

    async def commit(self): ...
    async def flush(self): ...
    async def rollback(self): ...
```

**Qué hace:** Define una clase base reutilizable que **cualquier repositorio** puede heredar. No contiene lógica específica de negocio, solo operaciones transaccionales genéricas.

**Qué ofrece:**

| Método | Función | Cuándo se usa |
|--------|---------|---------------|
| `commit()` | Persiste todos los cambios en la DB | Después de INSERTs/UPDATEs exitosos |
| `flush()` | Envía cambios a la DB sin confirmar (pre-commit) | Para obtener IDs generados antes del commit final |
| `rollback()` | Revierte todos los cambios pendientes | Cuando algo falla y hay que deshacer |

**Qué más incluye:**

```python
class SerializerModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, ...)
```

Una clase base para los schemas Pydantic que permite convertir objetos ORM directamente a diccionarios (útil para las respuestas de la API).

**Analogía:** Es como un **formulario bancario en blanco**: tiene los campos comunes (commit, rollback) pero no sabe de qué cuenta se trata. Cada banco (repositorio) lo personaliza.

---

### `entities/player/__init__.py` — El Exportador (3 líneas)

```python
from .model import Player
__all__ = ["Player"]
```

**Qué hace:** Un simple **exportador de nombre**. Permite hacer `from entities.player import Player` en lugar de `from entities.player.model import Player`. Facilita los imports.

---

### `entities/player/model.py` — El Modelo de Datos (48 líneas)

```python
class Player(Model):
    __tablename__ = "players_player"

    id: Mapped[int]          # PK autoincremental
    code: Mapped[int]        # Código de registro MINCETUR
    first_name: Mapped[str]  # Nombre
    last_name: Mapped[str]   # Apellido
    card_type: Mapped[int]   # Tipo doc: 1=DNI, 2=CE, 3=PT, 4=PP
    id_card: Mapped[str]     # Número de documento (clave de negocio)
    ubigeo: Mapped[str]      # Código geográfico Peru
    published_at: Mapped[datetime]  # Fecha publicación
    contact: Mapped[str]     # Contacto
    photo: Mapped[str]       # Ruta foto (nullable)
    created_at: Mapped[datetime]    # Alta en sistema
    updated_at: Mapped[datetime]    # Última modificación
    is_active: Mapped[bool]  # Soft delete: False = desactivado
```

**Qué hace:** Define la **estructura exacta** de la tabla `players_player` en SQL Server. Cada atributo = una columna.

**Detalles clave:**

| Campo | Tipo | Nullable | Rol en el negocio |
|-------|------|----------|-------------------|
| `id` | int (PK) | No | Identificador interno del sistema |
| `id_card` | str | No | **Clave de negocio** — número de documento (DNI/CE/PT/PP). Es el campo que se usa para comparaciones en el merge |
| `card_type` | int | No | Codifica el tipo de documento (1=DNI, 2=CE, 3=PT, 4=PP) |
| `is_active` | bool | No | **Soft delete** — False = persona ya no está en MINCETUR |
| `photo` | str | **Sí** | Ruta al archivo de foto en disco |
| `created_at` / `updated_at` | datetime | No | Trazabilidad de cambios |

**Herencia:** `Model` (definido en `connection_bd.py`) combina `AsyncAttrs` (para eager loading async) + `DeclarativeBase` (base ORM moderna de SQLAlchemy 2.0).

**Analogía:** Es el **plano arquitectónico** de la tabla. Define qué columnas tiene, qué tipo de dato admite y qué restricciones apply.

---

### `entities/player/repository.py` — El Acceso a Datos (79 líneas)

```python
class PlayerRepository(RepositoryBase[Player]):
```

**Qué hace:** Hereda de `RepositoryBase` y añade **todas las consultas SQL** específicas de `Player`. Es la única clase que "habla" directamente con la base de datos.

**Cada método, explicado:**

| Método | SQL que ejecuta | Retorna | Cuándo se usa |
|--------|-----------------|---------|---------------|
| `create(player)` | `INSERT INTO players_player (...) VALUES (...)` | `Player` con ID generado | Insertar un solo jugador |
| `bulk_create(players)` | `INSERT INTO players_player (...) VALUES (...), (...), ...` | `list[Player]` | Insertar muchos de golpe (sincronización) |
| `get_all()` | `SELECT * FROM players_player` | `Sequence[Player]` | Obtener todos los registros |
| `get_by_id_cards(id_cards)` | `SELECT * WHERE id_card IN ('123', '456', ...)` | `Sequence[Player]` | Buscar jugadores específicos por DNI |
| `id_cards_exist(id_cards)` | `SELECT id_card WHERE id_card IN (...)` | `set[str]` | Verificar **cuáles ya existen** antes de insertar (evita duplicados) |
| `deactivate_by_id_cards(id_cards)` | `UPDATE SET is_active=0 WHERE id_card IN (...) AND is_active=1` | `int` (rowcount) | Desactivar registros que salieron de MINCETUR |
| `reactivate_by_id_cards(id_cards)` | `UPDATE SET is_active=1 WHERE id_card IN (...) AND is_active=0` | `int` (rowcount) | Reactivar registros que reaparecieron |
| `update_photo(id_card, photo_path)` | `UPDATE SET photo='...' WHERE id_card='...'` | `int` (rowcount) | Actualizar ruta de foto después de copiar |

**Patrón de diseño:** Cada método construye un `stmt` (statement), lo ejecuta con `session.execute()`, y retorna el resultado procesado. Nunca usa raw SQL — todo es SQLAlchemy ORM.

**Detalle importante en `deactivate_by_id_cards`:**

```python
.where(Player.id_card.in_(id_cards), Player.is_active == True)
```

Solo desactiva registros que **están activos**. Si un registro ya está inactivo, lo ignora. Esto evita contar como "desactivado" algo que ya estaba desactivado.

**Analogía:** Es el **administrador de archivos** de la empresa. Solo saca y mete papeles (datos) del archivador (DB). No decide qué hacer con ellos — solo ejecuta lo que le dicen.

---

## CAPA ROUTES (`src/routes/`)

Esta capa **recibe peticiones externas**, **aplica reglas de negocio** y **responde**.

---

### `routes/players/__init__.py` — El Exportador del Router (3 líneas)

```python
from .controller import router as players_router
__all__ = ["players_router"]
```

**Qué hace:** Exporta el router para que `main.py` pueda registrarlo en la app FastAPI.

---

### `routes/players/schemas.py` — Los Contratos de Datos (46 líneas)

Define los **schemas Pydantic** que actúan como contratos de entrada y salida de la API.

**Schemas de entrada (Request):**

```python
class PlayerInsert(BaseModel):
    code: int
    first_name: str
    last_name: str
    card_type: int
    id_card: str
    ubigeo: str
    published_at: datetime
    contact: str
    photo: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    is_active: bool = True
```

| Campo | Tipo | Requerido | Nota |
|-------|------|-----------|------|
| Todos los datos del jugador | sus tipos | Sí | Se reciben del scraper o del cliente |
| `photo` | str | No | Puede no venir |
| `created_at` / `updated_at` | datetime | No | Tiene `default_factory` — si no se envía, usa `datetime.now()` |
| `is_active` | bool | No | Default `True` — nuevo jugador siempre está activo |

```python
class PlayerInsertRequest(BaseModel):
    players: list[PlayerInsert]  # Wrapper para enviar muchos de golpe
```

```python
class PlayerBulkAction(BaseModel):
    id_cards: list[str] = Field(..., min_length=1)  # Mínimo 1 ID
```

**Schemas de salida (Response):**

```python
class SyncResult(BaseModel):
    inserted: int = 0
    deactivated: int = 0
    reactivated: int = 0
    photos_moved: int = 0
    errors: list[str] = []

class PhotoUploadResponse(BaseModel):
    id_card: str
    filename: str
    destination: str
```

**Analogía:** Son los **formularios de solicitud** que el cliente debe llenar. Si no los llena bien (validación Pydantic), la API rechaza la petición antes de llegar al service.

---

### `routes/players/controller.py` — La Ventanilla de Atención (113 líneas)

```python
router = APIRouter(prefix="/api/v1/players", tags=["players"])
```

**Qué hace:** Recibe las peticiones HTTP, **valida** los schemas, **delega** al service, y **responde** con el resultado o un error.

**Cada endpoint explicado:**

---

#### 1. POST `/api/v1/players` — Insertar nuevos jugadores

```python
@router.post("", response_model=SyncResult, status_code=201)
async def insert_players(request: PlayerInsertRequest, session: AsyncSessionDepends):
    svc = _get_service(session)
    try:
        return await svc.insert_players(request)
    except Exception as e:
        logger.exception("Error en POST /players")
        raise HTTPException(status_code=500, detail=str(e))
```

**Flujo:**
1. FastAPI recibe el JSON y lo valida contra `PlayerInsertRequest`
2. Si es válido, FastAPI inyecta una `AsyncSession` vía `AsyncSessionDepends`
3. Se crea un `PlayerSyncService` con esa sesión
4. Se llama a `svc.insert_players(request)`
5. Si todo va bien → retorna `SyncResult` con HTTP 201
6. Si falla → loguea el error y retorna HTTP 500

---

#### 2. PATCH `/api/v1/players/deactivate` — Desactivar

```python
@router.patch("/deactivate", response_model=SyncResult)
async def deactivate_players(request: PlayerBulkAction, session: AsyncSessionDepends):
    svc = _get_service(session)
    try:
        return await svc.deactivate_players(request)
    except Exception as e:
        logger.exception("Error en PATCH /players/deactivate")
        raise HTTPException(status_code=500, detail=str(e))
```

**Flujo:** Recibe una lista de `id_cards` → service actualiza `is_active=False` → retorna conteo.

---

#### 3. PATCH `/api/v1/players/reactivate` — Reactivar

Mismo patrón que deactivate pero con `is_active=True`.

---

#### 4. POST `/api/v1/players/sync` — Sincronización completa

```python
@router.post("/sync", response_model=SyncResult)
async def sync_players(
    session: AsyncSessionDepends,
    insert: PlayerInsertRequest | None = None,
    deactivate: PlayerBulkAction | None = None,
    reactivate: PlayerBulkAction | None = None,
):
```

**Nota:** Los parámetros `insert`, `deactivate`, `reactivate` son **opcionales** (pueden ser `None`). El endpoint acepta los tres lotes de datos en una sola petición.

---

#### 5. POST `/api/v1/players/{id_card}/photo` — Subir foto

```python
@router.post("/{id_card}/photo", response_model=PhotoUploadResponse)
async def upload_photo(id_card: str, session: AsyncSessionDepends, file: UploadFile = File(...)):
```

**Flujo:**
1. Valida que el archivo sea imagen (`content_type.startswith("image/")`)
2. Valida que no esté vacío
3. Lee el contenido en bytes
4. Llama a `svc.save_uploaded_photo(id_card, filename, content)`
5. Retorna la ruta donde se guardó

**Analogía:** El controller es el **recepcionista** que:
- Toma el formulario del cliente (request)
- Verifica que esté bien llenado (validación Pydantic automática)
- Lo pasa al especialista adecuado (service)
- Le devuelve la respuesta o le dice que hubo un error

---

### `routes/players/service.py` — La Lógica de Negocio (190 líneas)

```python
class PlayerSyncService:
    def __init__(self, session: AsyncSession):
        self.repo = PlayerRepository(session)
```

**Qué hace:** Contiene **toda la lógica de negocio**. No habla con HTTP, no habla con la DB directamente — usa el repository.

---

#### 1. `insert_players(request)` — El corazón del sistema

```python
async def insert_players(self, request: PlayerInsertRequest) -> SyncResult:
    result = SyncResult()

    # PASO 1: Extraer todos los IDs que llegan
    id_cards_incoming = [p.id_card for p in request.players]

    # PASO 2: Consultar cuáles ya existen en la DB
    existing = await self.repo.id_cards_exist(id_cards_incoming)

    # PASO 3: Filtrar duplicados y construir objetos Player
    for p in request.players:
        if p.id_card in existing:
            result.errors.append(f"id_card {p.id_card} ya existe, ignorado")
            continue
        player = Player(
            code=p.code,
            first_name=p.first_name,
            ...
            created_at=now,
            updated_at=now,
            is_active=True,
        )
        players_to_create.append(player)

    # PASO 4: Insertar en lote
    if players_to_create:
        await self.repo.bulk_create(players_to_create)
        result.inserted = len(players_to_create)

    # PASO 5: Confirmar cambios
    await self.repo.commit()

    # PASO 6: Copiar fotos
    if players_to_create:
        result.photos_moved = await self._copy_photos(players_to_create)

    return result
```

**Flujo visual:**

```
Request con 100 jugadores
        │
        ▼
┌─────────────────────────────────────┐
│ Buscar cuáles IDs ya existen en DB  │
│ (ej: 85 de los 100 ya existen)     │
└─────────────────────────┬───────────┘
                          ▼
┌─────────────────────────────────────┐
│ Filtrar: solo 15 son nuevos        │
│ Los 85 existentes → error list     │
└─────────────────────────┬───────────┘
                          ▼
┌─────────────────────────────────────┐
│ bulk_create(15 players)            │
│ commit()                           │
└─────────────────────────┬───────────┘
                          ▼
┌─────────────────────────────────────┐
│ Copiar 15 fotos de static/images/  │
│ hacia PATH_FOTOS_SALIDA            │
│ Actualizar rutas en DB             │
└─────────────────────────┬───────────┘
                          ▼
              SyncResult {inserted: 15, errors: [85 items]}
```

---

#### 2. `deactivate_players(request)` — Simple y directo

```python
async def deactivate_players(self, request: PlayerBulkAction) -> SyncResult:
    result.deactivated = await self.repo.deactivate_by_id_cards(request.id_cards)
    await self.repo.commit()
    return result
```

Una sola llamada al repository + commit. El repository se encarga de solo desactivar los que están activos.

---

#### 3. `reactivate_players(request)` — Espejo de deactivate

```python
async def reactivate_players(self, request: PlayerBulkAction) -> SyncResult:
    result.reactivated = await self.repo.reactivate_by_id_cards(request.id_cards)
    await self.repo.commit()
    return result
```

---

#### 4. `sync_all(...)` — El orquestador

```python
async def sync_all(self, insert_request, deactivate_request, reactivate_request) -> SyncResult:
    result = SyncResult()
    try:
        # Orden importa: primero desactivar, luego reactivar, luego insertar
        if deactivate_request and deactivate_request.id_cards:
            partial = await self.deactivate_players(deactivate_request)
            result.deactivated = partial.deactivated

        if reactivate_request and reactivate_request.id_cards:
            partial = await self.reactivate_players(reactivate_request)
            result.reactivated = partial.reactivated

        if insert_request and insert_request.players:
            partial = await self.insert_players(insert_request)
            result.inserted = partial.inserted
            result.photos_moved = partial.photos_moved

    except Exception as e:
        await self.repo.rollback()  # ← Si falla, deshace TODO
        result.errors.append(str(e))

    return result
```

**Orden de ejecución (importante):**
1. **Desactivar** primero — libera IDs que podrían ser reasignados
2. **Reactivar** segundo — restaura registros que reaparecieron
3. **Insertar** al final — agrega los nuevos

**Si falla en cualquier paso:** se ejecuta `rollback()` y se revierten **todos** los cambios de la transacción.

---

#### 5. `_copy_photos(players)` — Gestión de archivos

```python
async def _copy_photos(self, players: list[Player]) -> int:
    for player in players:
        foto_origen = STATIC_IMAGES_DIR / f"{id_card}.png"  # Busca por DNI
        if not foto_origen.exists():
            coincidencias = list(STATIC_IMAGES_DIR.glob(f"{id_card}.*"))  # Cualquier extensión
        shutil.copy2(str(foto_origen), str(dest_file))  # Copia con metadatos
        await self.repo.update_photo(id_card, str(dest_file))  # Actualiza DB
    await self.repo.commit()
```

**Flujo:**
1. Para cada jugador nuevo, busca su foto en `static/images/{dni}.png`
2. Si no la encuentra como `.png`, busca cualquier extensión (`{dni}.*`)
3. La copia al directorio de salida
4. Actualiza la ruta en la DB

---

#### 6. `save_uploaded_photo(id_card, filename, content)` — Subida directa

```python
def save_uploaded_photo(self, id_card: str, filename: str, content: bytes) -> Path:
    dest = STATIC_IMAGES_DIR / f"{id_card}{ext}"
    dest.write_bytes(content)
    return dest
```

Sincrónico (no async) porque es solo escritura de archivo. Guarda los bytes directamente en disco.

---

## DIAGRAMA DE INTERACCIÓN COMPLETA

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLIENTE    │────►│  CONTROLLER │────►│   SERVICE   │────►│ REPOSITORY  │
│  (HTTP/CLI) │     │  (FastAPI)  │     │  (Negocio)  │     │   (DB)      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │  1. Envía JSON    │                   │                   │
       │──────────────────►│                   │                   │
       │                   │  2. Valida con    │                   │
       │                   │     Pydantic      │                   │
       │                   │                   │                   │
       │                   │  3. Inyecta       │                   │
       │                   │     session       │                   │
       │                   │──────────────────►│                   │
       │                   │                   │                   │
       │                   │  4. Llama a       │  5. Ejecuta SQL   │
       │                   │     insert/       │──────────────────►│
       │                   │     deactivate/   │                   │
       │                   │     sync          │  6. Retorna       │
       │                   │                   │◄──────────────────│
       │                   │                   │                   │
       │                   │  7. Retorna       │                   │
       │                   │     SyncResult    │                   │
       │  8. HTTP 201/200  │◄──────────────────│                   │
       │◄──────────────────│                   │                   │
```

---

## RESUMEN DE RESPONSABILIDADES

| Archivo | Responsabilidad | Nivel |
|---------|-----------------|-------|
| `entities/__init__.py` | Base genérica de repositorio + serializer | Infraestructura |
| `entities/player/model.py` | Define la estructura de la tabla | Dominio |
| `entities/player/repository.py` | Ejecuta consultas SQL contra la tabla | Infraestructura |
| `routes/players/schemas.py` | Define contratos de entrada/salida (validación) | API |
| `routes/players/controller.py` | Recibe HTTP, valida, delega, responde | API |
| `routes/players/service.py` | Lógica de negocio: insertar, desactivar, sincronizar | Negocio |
| `dependencies/async_bd.py` | Entrega una sesión de DB por petición | Infraestructura |

**Flujo de datos:** `Request → Schema (validación) → Controller → Service → Repository → SQL Server`
