from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

# ---------------------------------------------------------------------------
# REQUEST — INSERT
# ---------------------------------------------------------------------------
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
    
    # --- Hacer opcionales los campos para la solicitud de entrada ---
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    is_active: bool = True

class PlayerInsertRequest(BaseModel):
    players: list[PlayerInsert]

# ---------------------------------------------------------------------------
# REQUEST — DEACTIVATE / REACTIVATE
# ---------------------------------------------------------------------------
class PlayerBulkAction(BaseModel):
    id_cards: list[str] = Field(..., min_length=1)

# ---------------------------------------------------------------------------
# RESPONSE
# ---------------------------------------------------------------------------
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