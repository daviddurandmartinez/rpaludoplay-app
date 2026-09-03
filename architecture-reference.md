# Plantilla Arquitectónica — Backend FastAPI (Clean / Hexagonal / Modular Monolith)

> **Fuente**: Proyecto `gestion-accesos-backend`.
> **Objetivo**: Guía técnica prescriptiva para reestructurar el Proyecto B.
> **Stack de referencia**: Python 3.12, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, pydantic-settings, SQL Server (pyodbc), PyJWT, ldap3.

---

## 1. Visión General de la Arquitectura de Referencia

### Patrón extraído

**Monolito Modular con Arquitectura Hexagonal (Puertos y Adaptadores)**.

Cada dominio funcional es un módulo independiente con sus propias capas. La dependencia siempre apunta hacia adentro (hacia el dominio). Los puertos definen contratos; los adaptadores los implementan.

### Estructura de directorios estándar

```
proyecto/
├── main.py                              # App factory + registro de routers
├── pyproject.toml                       # Ruff, Pytest, mypy config
├── requirements.txt                     # Dependencias pinned
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── permissions.md
│   └── adr/
│
└── src/
    ├── __init__.py
    ├── settings.py                      # pydantic-settings BaseSettings
    │
    ├── shared/                          # Infraestructura transversal
    │   ├── __init__.py
    │   ├── exceptions.py                # Jerarquía de errores de dominio
    │   ├── health.py                    # /health/live, /health/ready
    │   └── database/
    │       ├── __init__.py              # Re-exports: Base, SessionLocal, get_session
    │       ├── session.py               # Engine, sessionmaker, get_session()
    │       └── models.py                # Modelos ORM (legacy o nuevos)
    │
    └── modules/
        ├── __init__.py
        │
        └── <modulo>/                    # Un módulo por dominio funcional
            ├── __init__.py
            ├── domain/                  # Entidades, value objects, enums, puertos
            │   ├── __init__.py
            │   ├── entities.py          # Dataclasses de dominio (sin dependencias de framework)
            │   └── ports.py             # Protocol (puertos) de salida
            │
            ├── application/             # Casos de uso y puertos de entrada
            │   ├── __init__.py
            │   ├── ports.py             # Protocol (puertos) de entrada
            │   ├── service.py           # Servicio de aplicación / caso de uso
            │   └── queries.py           # (Opcional) Consultas de solo lectura
            │
            ├── infrastructure/          # Adaptadores concretos
            │   ├── __init__.py          # Re-exports de factories DI
            │   ├── dependencies.py      # @lru_cache factories para Depends()
            │   ├── repositories.py      # Implementaciones SQLAlchemy de ports
            │   └── external.py          # (Opcional) Adaptadores externos
            │
            └── presentation/            # Capa de presentación (API)
                ├── __init__.py
                ├── router.py            # APIRouter con endpoints
                └── schemas.py           # Pydantic request/response schemas
```

### Regla cardinal

```
presentation → application → domain ← infrastructure
      │              │                        │
      │              └── Define puertos ──────┘
      └── Usa Depends() para inyectar adaptadores
```

---

## 2. Contratos y Responsabilidades por Capa

### 2.1 `domain/` — Capa de Dominio

| Elemento | Responsabilidad | Reglas |
|----------|-----------------|--------|
| `entities.py` | Modelos de negocio puros (dataclasses) | **Cero imports de frameworks externos** (sin FastAPI, sin SQLAlchemy, sin Pydantic). Solo stdlib. |
| `ports.py` | Protocol (puertos) que la capa externa debe implementar | Define la interfaz del adaptador. El dominio **nunca** importa la implementación concreta. |
| `status.py` / enums | Value objects y enumeraciones | `StrEnum` para strings persistentes. Lógica de validación inyectada en `parse()` o `__post_init__`. |
| `permissions.py` | Catálogo de permisos + grafo de dependencias | Enum `StrEnum` con diccionario de dependencias y función `resolve_permissions()` (cierre transitivo). |

**Ejemplo — Entidad de dominio inmutable** (`authentication/domain/entities.py`):

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    collaborator_id: int
    document: str
    display_name: str
    email: str
    permissions: tuple[str, ...] = field(default_factory=tuple)
```

**Ejemplo — Entidad con invariantes de negocio** (`collaborators/domain/entities.py`):

```python
from dataclasses import dataclass
from datetime import date
from src.modules.collaborators.domain.status import CollaboratorStatus
from src.shared.exceptions import ValidationError

@dataclass
class CollaboratorState:
    id: int
    document: str
    status: CollaboratorStatus
    cease_date: date | None

    def change_status(self, target: CollaboratorStatus) -> bool:
        if self.status == CollaboratorStatus.INACTIVE and target != self.status:
            raise ValidationError("No se puede reactivar un colaborador inactivo")
        if target == CollaboratorStatus.ACTIVE and self.cease_date is not None:
            raise ValidationError("No se puede activar un colaborador con fecha de cese")
        changed = self.status != target
        self.status = target
        return changed
```

**Ejemplo — Puerto (Protocol)** (`external_provisioning/domain/ports.py`):

```python
from typing import Any, Protocol

class ExternalAccountGateway(Protocol):
    system_name: str
    @property
    def is_configured(self) -> bool: ...
    def get_catalog(self) -> Any: ...
    def get_account(self, collaborator_id: int) -> Any: ...
    def sync_profile(self, collaborator_id: int) -> Any: ...
    def replace_sites(self, collaborator_id: int, site_ids: list[int]) -> None: ...
    def grant_access(self, collaborator_id: int, group_ids: list[int], site_ids: list[int]) -> None: ...
    def revoke_access(self, collaborator_id: int) -> None: ...
    def set_active(self, collaborator_id: int, is_active: bool) -> bool: ...
    def deactivate_by_document(self, document: str) -> bool: ...
```

### 2.2 `application/` — Capa de Aplicación

| Elemento | Responsabilidad | Reglas |
|----------|-----------------|--------|
| `ports.py` | Protocol de entrada (puertos de entrada) | Define lo que la infraestructura debe proveer al caso de uso. |
| `service.py` | Caso de uso o fachada de servicio | Orquesta operaciones, llama a repositorios vía puertos, aplica reglas de negocio. **Nunca** importa SQLAlchemy directamente. |
| `queries.py` | Consultas de solo lectura | Separadas del caso de uso. Clase `*Queries` que delega a un `*Reader` (Protocol). |
| `common.py` | Base genérica para CRUD | `CrudRepository` Protocol + `CrudService` base con métodos `get_all`, `get_by_id`, `create`, `update`, `delete`, `get_deletion_impact`. |

**Ejemplo — Servicio de aplicación con inyección de puertos** (`authentication/application/service.py`):

```python
from src.modules.authentication.application.ports import IdentityProvider, UserAccessRepository

class AuthenticationService:
    def __init__(self, identity_provider: IdentityProvider, user_repository: UserAccessRepository):
        self._identity_provider = identity_provider
        self._user_repository = user_repository

    def authenticate(self, username: str, password: str):
        document, email = self._identity_provider.authenticate(username, password)
        return self._user_repository.get_active_by_document(document, email)
```

**Ejemplo — Caso de uso con Command/Result** (`collaborators/application/update_status.py`):

```python
from dataclasses import dataclass

@dataclass
class UpdateCollaboratorStatusCommand:
    collaborator_id: int
    status: str

@dataclass
class UpdateCollaboratorStatusResult:
    id: int
    status: str
    deactivated_external_systems: list[str]

class UpdateCollaboratorStatus:
    def __init__(self, unit_of_work_factory, external_accounts):
        self._unit_of_work_factory = unit_of_work_factory
        self._external_accounts = external_accounts

    def execute(self, command: UpdateCollaboratorStatusCommand) -> UpdateCollaboratorStatusResult:
        target = CollaboratorStatus.parse(command.status)
        with self._unit_of_work_factory() as unit_of_work:
            collaborator = unit_of_work.collaborators.get(command.collaborator_id)
            changed = collaborator.change_status(target)
            deactivated = []
            if target == CollaboratorStatus.INACTIVE:
                deactivated = self._external_accounts.deactivate_all(collaborator.document)
            if changed:
                unit_of_work.commit()
        return UpdateCollaboratorStatusResult(
            id=collaborator.id, status=collaborator.status.value,
            deactivated_external_systems=deactivated,
        )
```

### 2.3 `infrastructure/` — Capa de Infraestructura

| Elemento | Responsabilidad | Reglas |
|----------|-----------------|--------|
| `dependencies.py` | Fábricas de dependencias (`@lru_cache`) | Crea instancias de servicios/repositorios. Punto de composición del módulo. |
| `repositories.py` | Implementación concreta de repositorios | Implementa Protocol de la capa application. Usa `SessionLocal` y SQLAlchemy. |
| `unit_of_work.py` | (Opcional) Unit of Work | Maneja ciclo de vida de sesión + commit/rollback. Usado solo para transacciones multi-agregado. |

**Ejemplo — Fábrica DI con `@lru_cache`** (`collaborators/infrastructure/dependencies.py`):

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_update_collaborator_status() -> UpdateCollaboratorStatus:
    return UpdateCollaboratorStatus(
        unit_of_work_factory=lambda: SqlAlchemyCollaboratorUnitOfWork(SessionLocal),
        external_accounts=get_external_provisioning_service(),
    )

@lru_cache(maxsize=1)
def get_collaborator_queries() -> CollaboratorQueries:
    return CollaboratorQueries(SqlAlchemyCollaboratorReader(SessionLocal))
```

### 2.4 `presentation/` — Capa de Presentación (API)

| Elemento | Responsabilidad | Reglas |
|----------|-----------------|--------|
| `router.py` | APIRouter con endpoints | Recibe servicios vía `Depends()`. Define permisos por ruta. Sin lógica de negocio inline. |
| `schemas.py` | Modelos Pydantic v2 para request/response | Separados de los modelos ORM. `BaseModel` puro, `Field()` para constraints. |

### Reglas de dependencia

```
✅ presentation  →  application  (casos de uso / servicios)
✅ presentation  →  infrastructure  (solo factories DI vía Depends)
✅ application   →  domain  (entidades, puertos)
✅ infrastructure  →  application  (implementa Protocol de application/ports)
✅ infrastructure  →  shared/database  (sesiones, engine)

❌ domain  →  ANY  (domain es la capa más interna, sin dependencias externas)
❌ presentation  →  infrastructure repositories  (directamente, sin pasar por DI)
❌ application  →  shared/database  (directamente, solo vía puertos)
```

---

## 3. Patrones de Código Reutilizables

### 3.1 Configuración base con `pydantic-settings`

```python
# src/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- Base de datos principal ---
    BD_HOST: str
    BD_PORT: str
    BD_NAME: str
    BD_USERNAME: str
    BD_PASSWORD: str

    # --- Base de datos externa (opcional) ---
    SABPLAY_BD_HOST: str | None = None
    SABPLAY_BD_PORT: str = "1433"
    SABPLAY_BD_NAME: str | None = None
    SABPLAY_BD_USERNAME: str | None = None
    SABPLAY_BD_PASSWORD: str | None = None

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- Autenticación ---
    AUTH_PROVIDER: str = "LDAP"
    AUTH_JWT_SECRET: str = "change-this-secret"
    AUTH_JWT_ALGORITHM: str = "HS256"
    AUTH_ACCESS_TOKEN_MINUTES: int = 15
    AUTH_REFRESH_TOKEN_DAYS: int = 7

    # --- Propiedades derivadas ---
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def external_database(self, system_name: str) -> dict[str, str | None]:
        prefix = system_name.strip().upper()
        return {k: getattr(self, f"{prefix}_{k}") for k in ("BD_HOST", "BD_PORT", "BD_NAME", "BD_USERNAME", "BD_PASSWORD")}

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**Reglas:**
- Instanciar `Settings()` como singleton a nivel de módulo.
- Preferir `properties` para valores derivados.
- `external_database()` para configuraciones dinámicas por sistema externo.
- Nunca importar `settings` en capa de dominio.

### 3.2 Inyección de Dependencias (`Depends`)

**Patrón base — Fábrica con `@lru_cache`:**

```python
# src/modules/<modulo>/infrastructure/dependencies.py
from functools import lru_cache
from src.shared.database import SessionLocal

@lru_cache(maxsize=1)
def get_<service>() -> <ServiceType>:
    return <ServiceType>(<ConcreteRepository>(SessionLocal))
```

**Patrón — Inyección en router:**

```python
@router.get("", response_model=ResponseModel, dependencies=[Depends(require_permission(PermissionCode.XXX))])
def get_all(service: ServiceType = Depends(get_service)):
    return service.get_all()
```

**Patrón — CurrentUser con `Annotated`:**

```python
from typing import Annotated
from fastapi import Depends, Cookie, HTTPException

CurrentUser = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]
```

**Patrón — require_permission (factory de dependencias):**

```python
def require_permission(permission: PermissionCode):
    def dependency(user: CurrentUser) -> AuthenticatedUser:
        granted = set(user.permissions)
        if PermissionCode.AUTHORIZATION_ADMIN not in granted and permission not in granted:
            raise HTTPException(status_code=403, detail=f"Permiso requerido: {permission.value}")
        return user
    return dependency
```

**Reglas de DI:**
- `@lru_cache(maxsize=1)` para singletons (servicios que no mantienen estado por request).
- Sin `lru_cache` para dependencias que requieren sesión per-request (`get_session`, `require_authenticated_user`).
- Las factories siempre residen en `infrastructure/dependencies.py`.
- El `__init__.py` del módulo re-exporta las factories para que `presentation/` importe desde `infrastructure`.

### 3.3 Manejo centralizado de errores

**Jerarquía de excepciones de dominio** (`shared/exceptions.py`):

```python
class DomainError(Exception): ...
class ResourceNotFoundError(DomainError): ...
class ValidationError(DomainError): ...
class ConflictError(DomainError): ...
class ExternalSystemUnavailableError(DomainError): ...
class ExternalCoordinationError(DomainError): ...
```

**Handler global en `main.py`:**

```python
async def handle_domain_error(_request: Request, error: DomainError):
    status_map = {
        ResourceNotFoundError: 404,
        ConflictError: 409,
        ExternalCoordinationError: 502,
        ExternalSystemUnavailableError: 503,
        ValidationError: 400,
    }
    status_code = status_map.get(type(error), 400)
    return JSONResponse(status_code=status_code, content={"detail": str(error)})

app.add_exception_handler(DomainError, handle_domain_error)
```

**Reglas:**
- Las capas domain y application **solo** lanzan excepciones de dominio.
- La infraestructura traduce errores técnicos (IntegrityError, DBAPIError) a excepciones de dominio.
- Nunca lanzar `HTTPException` desde application/domain; solo desde presentation (router).
- El handler global convierte `DomainError` a HTTP status + JSON.

### 3.4 Separación Schema (Pydantic) vs Modelo (ORM)

```python
# --- Modelo ORM (shared/database/models.py) ---
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

class Collaborator(Base):
    __tablename__ = "colaborador"          # Nombre legacy
    id: Mapped[int] = mapped_column(primary_key=True)
    document: Mapped[str] = mapped_column(name="documento", type_=String(250))
    name: Mapped[str] = mapped_column(name="nombre")
    status: Mapped[str] = mapped_column(name="estado")
    email: Mapped[str | None] = mapped_column(name="correo")

# --- Schema Pydantic (presentation/schemas.py) ---
from pydantic import BaseModel, Field

class CollaboratorSummaryResponse(BaseModel):
    id: int
    document: str
    name: str
    email: str | None = None
    status: str

class CollaboratorDetailResponse(CollaboratorSummaryResponse):
    cease_date: date | None = None
    access: list[CollaboratorAccessResponse] = Field(default_factory=list)

class CollaboratorListResponse(BaseModel):
    collaborators: list[CollaboratorSummaryResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int
```

**Reglas:**
- Los schemas **nunca** heredan de modelos ORM.
- Los schemas definen `response_model=` en los decoradores de ruta.
- Los schemas usan `Field(default_factory=list)` para colecciones, `str | None = None` para opcionales.
- `model_dump()` se llama en el router para serializar la respuesta.
- Los modelos ORM usan `name=` para mapear columnas a nombres legacy.
- Nunca ejecutar `create_all()` si la BD es preexistente.

### 3.5 Concurrencia (`async` vs `def`)

**Regla del proyecto de referencia: todo es sincrónico.**

```python
# ✅ Routers — synchronous def (FastAPI ejecuta en thread pool)
@router.get("")
def get_all(service: Service = Depends(get_service)):
    return service.get_all()

# ✅ Services — synchronous
class Service:
    def get_all(self):
        return self._repository.get_all()

# ✅ Repositories — synchronous with sessionmaker
class SqlAlchemyRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def get_all(self):
        with self._session_factory() as session:
            return session.execute(select(...)).scalars().all()

# ✅ Database engine — synchronous
engine = create_engine(uri, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

**Cuándo usar async:**
- Solo si el driver de BD soporta async (ej: `aiosqlite`, `asyncpg`) Y hay concurrencia real de I/O.
- Si el driver es síncrono (pyodbc, psycopg2), usar `def` normal. FastAPI maneja la ejecución en thread pool automáticamente.
- Nunca mezclar `async def` con operaciones síncronas de BD bloqueantes dentro del mismo handler.

### 3.6 App Factory (`main.py`)

```python
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.settings import settings

def create_app() -> FastAPI:
    application = FastAPI(title="Mi API", version="1.0.0")
    application.add_exception_handler(DomainError, handle_domain_error)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Routers públicos (sin auth)
    application.include_router(health_router)
    application.include_router(auth_router)
    # Routers protegidos (requieren JWT válido)
    for router in (resource_router,):
        application.include_router(router, dependencies=[Depends(require_authenticated_user)])
    return application

app = create_app()
```

### 3.7 Base de datos y sesión

```python
# shared/database/session.py
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from src.settings import settings

uri = URL.create(
    "mssql+pyodbc",
    username=settings.BD_USERNAME,
    password=settings.BD_PASSWORD,
    host=settings.BD_HOST,
    port=int(settings.BD_PORT),
    database=settings.BD_NAME,
    query={"driver": f"ODBC Driver {settings.BD_DRIVER_NUMBER} for SQL Server"},
)

engine: Engine = create_engine(uri, pool_pre_ping=True)
SessionLocal: sessionmaker[Session] = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

class Base(DeclarativeBase): ...

def get_session():
    with SessionLocal() as session:
        yield session
```

**Reglas:**
- `expire_on_commit=False` para evitar detached instance errors en response serialization.
- `pool_pre_ping=True` para detectar conexiones muertas.
- `get_session()` es un generator FastAPI dependency (per-request session).
- `SessionLocal` es un sessionmaker reutilizable (para repositorios que crean su propia sesión).

### 3.8 Unit of Work (cuando aplica)

```python
# collaborators/infrastructure/unit_of_work.py
class SqlAlchemyCollaboratorUnitOfWork:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def __enter__(self):
        self._session = self._session_factory()
        self.collaborators = SqlAlchemyCollaboratorRepository(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._session.rollback()
        else:
            self._session.commit()
        self._session.close()

    def commit(self):
        self._session.commit()
```

**Cuándo usar UoW:**
- Transacciones multi-agregado (ej: cambiar estado + desactivar cuentas externas).
- Cuando necesitas rollback automático ante excepciones.
- **No** usar para operaciones CRUD simples; basta con `session_factory.begin()`.

### 3.9 Repositorio genérico CRUD

```python
# application/common.py
from typing import Any, Protocol

class CrudRepository(Protocol):
    def get_all(self) -> list[dict[str, Any]]: ...
    def get_by_id(self, resource_id: int) -> dict[str, Any]: ...
    def create(self, data: dict[str, Any]) -> dict[str, Any]: ...
    def update(self, resource_id: int, data: dict[str, Any]) -> dict[str, Any]: ...
    def delete(self, resource_id: int) -> None: ...
    def get_deletion_impact(self, resource_id: int) -> dict[str, int]: ...

class CrudService:
    def __init__(self, repository: CrudRepository):
        self._repository = repository

    def get_all(self): return self._repository.get_all()
    def get_by_id(self, resource_id): return self._repository.get_by_id(resource_id)
    def create(self, data): return self._repository.create(data)
    def update(self, resource_id, data): return self._repository.update(resource_id, data)
    def delete(self, resource_id): self._repository.delete(resource_id)
    def get_deletion_impact(self, resource_id): return self._repository.get_deletion_impact(resource_id)
```

---

## 4. Checklist de Adecuación para el Proyecto B

### Fase 1 — Estructura de carpetas
- [ ] Crear `src/`, `src/shared/`, `src/modules/`, `tests/`, `docs/`
- [ ] Crear `src/settings.py` con `pydantic-settings`
- [ ] Crear `src/shared/exceptions.py` con jerarquía `DomainError`
- [ ] Crear `src/shared/database/` con `session.py`, `models.py`, `__init__.py`
- [ ] Crear al menos un módulo con estructura completa: `domain/`, `application/`, `infrastructure/`, `presentation/`
- [ ] Crear `main.py` con app factory y registro de routers
- [ ] Crear `.env.example` con todas las variables de entorno documentadas

### Fase 2 — Configuración
- [ ] Configurar `pyproject.toml` con `[tool.ruff]` y `[tool.pytest.ini_options]`
- [ ] Verificar que `Settings` carga desde `.env`
- [ ] Configurar CORS con `settings.cors_origins`
- [ ] Configurar `create_engine` con driver correcto + `pool_pre_ping=True`
- [ ] Configurar `sessionmaker` con `expire_on_commit=False`
- [ ] Crear `Dockerfile` y `docker-compose.yml`

### Fase 3 — Capa de datos
- [ ] Definir modelos ORM con `Mapped[]` / `mapped_column()` (SQLAlchemy 2.0 style)
- [ ] Mapear columnas legacy con `name=` si aplica
- [ ] Crear `Base(DeclarativeBase)` vacía
- [ ] Implementar repositorios que implementen Protocol de application
- [ ] Crear `get_session()` como dependency de FastAPI
- [ ] Crear `@lru_cache` factories en `infrastructure/dependencies.py`
- [ ] Re-exportar factories desde `infrastructure/__init__.py`

### Fase 4 — Lógica de negocio
- [ ] Definir entidades de dominio como dataclasses (sin dependencias de framework)
- [ ] Definir puertos (Protocol) en `domain/ports.py` o `application/ports.py`
- [ ] Implementar casos de uso en `application/service.py`
- [ ] Separar consultas de solo lectura en `application/queries.py`
- [ ] Implementar invariantes de negocio en entidades de dominio
- [ ] Crear excepciones de dominio específicas bajo `DomainError`

### Fase 5 — Endpoints (presentación)
- [ ] Crear `router.py` con `APIRouter(prefix=..., tags=[...])`
- [ ] Crear `schemas.py` con Pydantic v2 (`BaseModel`, `Field`, `list[T]`, `X | None`)
- [ ] Aplicar `response_model=` en decoradores de ruta
- [ ] Inyectar servicios vía `Depends(get_factory)`
- [ ] Proteger rutas con `dependencies=[Depends(require_permission(PermissionCode.XXX))]`
- [ ] Aplicar guard global de auth: `dependencies=[Depends(require_authenticated_user)]` en `create_app`
- [ ] Registrar handler global de `DomainError` → HTTP status mapping
- [ ] Implementar `/health/live` y `/health/ready`

### Fase 6 — Autenticación y autorización
- [ ] Implementar `require_authenticated_user` (lee cookie JWT, verifica activo en BD)
- [ ] Implementar `require_permission(code)` (closure que verifica permisos del JWT)
- [ ] Crear `CurrentUser = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]`
- [ ] Definir `PermissionCode` como `StrEnum` con catálogo y dependencias
- [ ] Implementar `resolve_permissions()` (cierre transitivo del grafo de dependencias)

### Fase 7 — Verificación
- [ ] Ejecutar `ruff check src tests` — 0 errores
- [ ] Ejecutar `pytest -q` — todos los tests pasan
- [ ] Verificar que domain/ tiene 0 imports de framework
- [ ] Verificar que todos los endpoints están protegidos con permiso
- [ ] Verificar que no existe `create_all()` en ningún archivo
- [ ] Revisar `git status` — no hay cambios no intencionados

---

## 5. Criterios de Aceptación y Calidad

### 5.1 Configuración de linter/formateador (Ruff)

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["E501", "B008"]  # B008: permite Depends() en defaults de FastAPI

[tool.ruff.lint.isort]
known-first-party = ["src"]
```

### 5.2 Configuración de mypy (opcional pero recomendado)

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
disallow_untyped_defs = true
disallow_any_generics = true
warn_return_any = true
warn_unused_configs = true
```

### 5.3 Configuración de Pytest

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

**Estructura de tests:**

```
tests/
├── __init__.py
└── unit/
    ├── __init__.py
    ├── test_<modulo>_service.py
    ├── test_<modulo>_repository.py
    └── test_openapi_contract.py
```

**Patrón de test con `TestClient`:**

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_all():
    response = client.get("/resource")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)
```

**Patrón de test unitario con mocks:**

```python
from unittest.mock import MagicMock

def test_service_delegates_to_repository():
    repo = MagicMock()
    service = MyService(repo)
    service.get_all()
    repo.get_all.assert_called_once()
```

### 5.4 Criterios de calidad obligatorios

| Criterio | Verificación |
|----------|-------------|
| Domain layer sin dependencias externas | `grep -r "from fastapi\|from sqlalchemy\|from pydantic" src/modules/*/domain/` retorna vacío |
| Todos los endpoints protegidos | `grep -r "require_permission" src/modules/*/presentation/` cubre todos los `@router.` |
| Sin `create_all()` | `grep -r "create_all" src/` retorna vacío |
| Ruff pasa | `ruff check src tests` sin errores |
| Tests pasan | `pytest -q` sin fallos |
| Response models declarados | `grep -r "response_model=" src/modules/*/presentation/` cubre todos los GET/POST |
| Schemas separados de ORM | `grep -r "BaseModel" src/modules/*/presentation/schemas.py` existe; `src/shared/database/models.py` no hereda BaseModel |

### 5.5 Comandos de verificación

```bash
# Linting
docker compose run --rm api ruff check src tests

# Tests
docker compose run --rm api pytest -q

# Type checking (si mypy está configurado)
docker compose run --rm api mypy src

# Verificar que domain está limpio
grep -r "from fastapi\|from sqlalchemy\|from pydantic" src/modules/*/domain/

# Verificar endpoints protegidos
grep -c "require_permission" src/modules/*/presentation/*.py
```
