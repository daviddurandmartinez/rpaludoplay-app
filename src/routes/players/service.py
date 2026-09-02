import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from entities.player.model import Player
from entities.player.repository import PlayerRepository
from routes.players.schemas import PlayerInsertRequest, PlayerBulkAction, SyncResult
from utils.constants import STATIC_IMAGES_DIR, EXTENSION_FOTO, PATH_FOTOS_SALIDA

logger = logging.getLogger(__name__)

class PlayerSyncService:

    def __init__(self, session: AsyncSession):
        self.repo = PlayerRepository(session)

    # -------------------------------------------------------------------
    # INSERT
    # -------------------------------------------------------------------

    async def insert_players(self, request: PlayerInsertRequest) -> SyncResult:
        result = SyncResult()

        if not request.players:
            return result

        id_cards_incoming = [p.id_card for p in request.players]
        existing = await self.repo.id_cards_exist(id_cards_incoming)

        now = datetime.now(timezone.utc)
        players_to_create: list[Player] = []

        for p in request.players:
            if p.id_card in existing:
                result.errors.append(f"id_card {p.id_card} ya existe, ignorado")
                continue

            player = Player(
                code=p.code,
                first_name=p.first_name,
                last_name=p.last_name,
                card_type=p.card_type,
                id_card=p.id_card,
                ubigeo=p.ubigeo,
                published_at=p.published_at,
                contact=p.contact,
                photo=p.photo,
                created_at=now,
                updated_at=now,
                is_active=True,
            )
            players_to_create.append(player)

        if players_to_create:
            await self.repo.bulk_create(players_to_create)
            result.inserted = len(players_to_create)

        await self.repo.commit()
        logger.info("INSERT completado: %d registros", result.inserted)

        if players_to_create:
            result.photos_moved = await self._copy_photos(players_to_create)

        return result

    # -------------------------------------------------------------------
    # DEACTIVATE (is_active = False)
    # -------------------------------------------------------------------
    
    async def deactivate_players(self, request: PlayerBulkAction) -> SyncResult:
        result = SyncResult()
        if not request.id_cards:
            return result

        result.deactivated = await self.repo.deactivate_by_id_cards(request.id_cards)
        await self.repo.commit()
        logger.info("DEACTIVATE completado: %d registros", result.deactivated)
        return result

    # -------------------------------------------------------------------
    # REACTIVATE (is_active = True)
    # -------------------------------------------------------------------

    async def reactivate_players(self, request: PlayerBulkAction) -> SyncResult:
        result = SyncResult()
        if not request.id_cards:
            return result

        result.reactivated = await self.repo.reactivate_by_id_cards(request.id_cards)
        await self.repo.commit()
        logger.info("REACTIVATE completado: %d registros", result.reactivated)
        return result

    # -------------------------------------------------------------------
    # FULL BATCH SYNC
    # -------------------------------------------------------------------

    async def sync_all(
                        self,
                        insert_request: PlayerInsertRequest | None,
                        deactivate_request: PlayerBulkAction | None,
                        reactivate_request: PlayerBulkAction | None,
                    ) -> SyncResult:
        result = SyncResult()

        try:
            if deactivate_request and deactivate_request.id_cards:
                partial = await self.deactivate_players(deactivate_request)
                result.deactivated = partial.deactivated
                result.errors.extend(partial.errors)

            if reactivate_request and reactivate_request.id_cards:
                partial = await self.reactivate_players(reactivate_request)
                result.reactivated = partial.reactivated
                result.errors.extend(partial.errors)

            if insert_request and insert_request.players:
                partial = await self.insert_players(insert_request)
                result.inserted = partial.inserted
                result.photos_moved = partial.photos_moved
                result.errors.extend(partial.errors)

        except Exception as e:
            logger.exception("Error durante sync_all")
            await self.repo.rollback()
            result.errors.append(str(e))

        return result

    # -------------------------------------------------------------------
    # PHOTO HANDLING
    # -------------------------------------------------------------------

    async def _copy_photos(self, players: list[Player]) -> int:
        """Copia fotos desde STATIC_IMAGES_DIR hacia PATH_FOTOS_SALIDA y actualiza la BD."""
        destino = Path(PATH_FOTOS_SALIDA)
        try:
            destino.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error("No se pudo crear directorio de fotos %s: %s", destino, e)
            return 0

        copied = 0
        for player in players:
            id_card = player.id_card
            foto_origen = STATIC_IMAGES_DIR / f"{id_card}.png"

            if not foto_origen.exists():
                coincidencias = list(STATIC_IMAGES_DIR.glob(f"{id_card}.*"))
                if coincidencias:
                    foto_origen = coincidencias[0]
                else:
                    logger.warning("Foto no encontrada en %s para documento %s", STATIC_IMAGES_DIR, id_card)
                    continue

            try:
                dest_file = destino / foto_origen.name
                if foto_origen.resolve() != dest_file.resolve():
                    shutil.copy2(str(foto_origen), str(dest_file))
                    logger.info("Foto copiada: %s -> %s", foto_origen, dest_file)
                else:
                    logger.info("La foto ya se encuentra en el destino: %s", foto_origen)

                await self.repo.update_photo(id_card, str(dest_file))
                copied += 1
            except (OSError, shutil.Error) as e:
                logger.error("Error copiando foto %s: %s", foto_origen, e)

        if copied > 0:
            await self.repo.commit()
            logger.info("Fotos copiadas y rutas actualizadas en BD: %d", copied)

        return copied

    def save_uploaded_photo(self, id_card: str, filename: str, content: bytes) -> Path:
        """Guarda un archivo subido en static/images/{id_card}.{ext}."""
        STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        ext = Path(filename).suffix or EXTENSION_FOTO
        dest = STATIC_IMAGES_DIR / f"{id_card}{ext}"

        try:
            dest.write_bytes(content)
            logger.info("Foto guardada: %s", dest)
        except OSError as e:
            logger.error("Error guardando foto %s: %s", dest, e)
            raise

        return dest