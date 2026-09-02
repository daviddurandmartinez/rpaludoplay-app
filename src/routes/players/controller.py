import logging
from fastapi import APIRouter, File, HTTPException, UploadFile
from dependencies.async_bd import AsyncSessionDepends
from routes.players.schemas import (
    PlayerBulkAction,
    PlayerInsertRequest,
    PhotoUploadResponse,
    SyncResult,
)
from routes.players.service import PlayerSyncService

'''Qué hace: Recibe las peticiones HTTP, valida los schemas, delega al service, y responde con el resultado o un error.'''
'''Analogía: El controller es el recepcionista que:
- Toma el formulario del cliente (request)
- Verifica que esté bien llenado (validación Pydantic automática)
- Lo pasa al especialista adecuado (service)
- Le devuelve la respuesta o le dice que hubo un error
'''
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/players", tags=["players"])

def _get_service(session: AsyncSessionDepends) -> PlayerSyncService:
    return PlayerSyncService(session)

# -----------------------------------------------------------------------
# POST /api/v1/players — Insert new players (df_insert)
# -----------------------------------------------------------------------

@router.post("", response_model=SyncResult, status_code=201)
async def insert_players(
                            request: PlayerInsertRequest,
                            session: AsyncSessionDepends,
                        ):
    svc = _get_service(session)
    try:
        return await svc.insert_players(request)
    except Exception as e:
        logger.exception("Error en POST /players")
        raise HTTPException(status_code=500, detail=str(e))

'''
Flujo:
1. FastAPI recibe el JSON y lo valida contra PlayerInsertRequest
2. Si es válido, FastAPI inyecta una AsyncSession vía AsyncSessionDepends
3. Se crea un PlayerSyncService con esa sesión
4. Se llama a svc.insert_players(request)
5. Si todo va bien → retorna SyncResult con HTTP 201
6. Si falla → loguea el error y retorna HTTP 500
'''

# -----------------------------------------------------------------------
# PATCH /api/v1/players/deactivate — Set is_active=0 (df_update)
# -----------------------------------------------------------------------

@router.patch("/deactivate", response_model=SyncResult)
async def deactivate_players(
    request: PlayerBulkAction,
    session: AsyncSessionDepends,
):
    svc = _get_service(session)
    try:
        return await svc.deactivate_players(request)
    except Exception as e:
        logger.exception("Error en PATCH /players/deactivate")
        raise HTTPException(status_code=500, detail=str(e))

'''Flujo: Recibe una lista de id_cards → service actualiza is_active=False → retorna conteo.'''

# -----------------------------------------------------------------------
# PATCH /api/v1/players/reactivate — Set is_active=1 (df_update_recurrent)
# -----------------------------------------------------------------------

@router.patch("/reactivate", response_model=SyncResult)
async def reactivate_players(
    request: PlayerBulkAction,
    session: AsyncSessionDepends,
):
    svc = _get_service(session)
    try:
        return await svc.reactivate_players(request)
    except Exception as e:
        logger.exception("Error en PATCH /players/reactivate")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------
# POST /api/v1/players/sync — Full batch (insert + deactivate + reactivate)
# -----------------------------------------------------------------------

@router.post("/sync", response_model=SyncResult)
async def sync_players(
                session: AsyncSessionDepends,
                insert: PlayerInsertRequest | None = None,
                deactivate: PlayerBulkAction | None = None,
                reactivate: PlayerBulkAction | None = None,
            ):
    svc = _get_service(session)
    try:
        return await svc.sync_all(insert, deactivate, reactivate)
    except Exception as e:
        logger.exception("Error en POST /players/sync")
        raise HTTPException(status_code=500, detail=str(e))

'''Nota: Los parámetros insert, deactivate, reactivate son opcionales (pueden ser None). El endpoint acepta los tres lotes de datos en una sola petición.'''

# -----------------------------------------------------------------------
# POST /api/v1/players/{id_card}/photo — Upload a photo
# -----------------------------------------------------------------------

@router.post("/{id_card}/photo", response_model=PhotoUploadResponse)
async def upload_photo(
                            id_card: str,
                            session: AsyncSessionDepends,
                            file: UploadFile = File(...),
                        ):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    svc = _get_service(session)
    try:
        dest = svc.save_uploaded_photo(id_card, file.filename or "photo.png", content)
        return PhotoUploadResponse(
            id_card=id_card,
            filename=dest.name,
            destination=str(dest),
        )
    except Exception as e:
        logger.exception("Error subiendo foto para %s", id_card)
        raise HTTPException(status_code=500, detail=str(e))

'''
Flujo:
1. Valida que el archivo sea imagen (content_type.startswith("image/"))
2. Valida que no esté vacío
3. Lee el contenido en bytes
4. Llama a svc.save_uploaded_photo(id_card, filename, content)
5. Retorna la ruta donde se guardó
'''