from typing import Sequence
from sqlalchemy import select, update
from entities import RepositoryBase
from .model import Player

'''Qué hace: Hereda de RepositoryBase y añade todas las consultas SQL específicas de Player. Es la única clase que "habla" directamente con la base de datos.'''
'''Analogía: Es el administrador de archivos de la empresa. Solo saca y mete papeles (datos) del archivador (DB). No decide qué hacer con ellos — solo ejecuta lo que le dicen.'''
class PlayerRepository(RepositoryBase[Player]):

    # -------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------

    async def create(self, player: Player) -> Player:
        self.async_session.add(player)
        await self.async_session.flush()
        return player

    async def bulk_create(self, players: list[Player]) -> list[Player]:
        self.async_session.add_all(players)
        await self.async_session.flush()
        return players

    # -------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------

    async def get_all(self) -> Sequence[Player]:
        stmt = select(Player)
        result = await self.async_session.execute(stmt)
        return result.scalars().all()

    async def get_by_id_cards(self, id_cards: list[str]) -> Sequence[Player]:
        stmt = select(Player).where(Player.id_card.in_(id_cards))
        result = await self.async_session.execute(stmt)
        return result.scalars().all()

    async def id_cards_exist(self, id_cards: list[str]) -> set[str]:
        """Retorna el subconjunto de id_cards que ya existen en la tabla."""
        stmt = select(Player.id_card).where(Player.id_card.in_(id_cards))
        result = await self.async_session.execute(stmt)
        return {row[0] for row in result.all()}

    # -------------------------------------------------------------------
    # UPDATE — DEACTIVATE (is_active = False)
    # -------------------------------------------------------------------

    async def deactivate_by_id_cards(self, id_cards: list[str]) -> int:
        stmt = (
            update(Player)
            .where(Player.id_card.in_(id_cards), Player.is_active == True)
            .values(is_active=False)
        )
        result = await self.async_session.execute(stmt)
        return result.rowcount

    # -------------------------------------------------------------------
    # UPDATE — REACTIVATE (is_active = True)
    # -------------------------------------------------------------------

    async def reactivate_by_id_cards(self, id_cards: list[str]) -> int:
        stmt = (
            update(Player)
            .where(Player.id_card.in_(id_cards), Player.is_active == False)
            .values(is_active=True)
        )
        result = await self.async_session.execute(stmt)
        return result.rowcount

    # -------------------------------------------------------------------
    # UPDATE — PHOTO PATH
    # -------------------------------------------------------------------
    
    async def update_photo(self, id_card: str, photo_path: str) -> int:
        stmt = (
            update(Player)
            .where(Player.id_card == id_card)
            .values(photo=photo_path)
        )
        result = await self.async_session.execute(stmt)
        return result.rowcount