from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from utils.connection_bd import Model

T = TypeVar("T", bound="Model")

'''Define una clase base reutilizable que cualquier repositorio puede heredar. No contiene lógica específica de negocio, solo operaciones transaccionales genéricas.'''
class RepositoryBase(Generic[T]):

    def __init__(self, async_session: AsyncSession):
        self.async_session: AsyncSession = async_session

    async def commit(self):
        await self.async_session.commit()

    async def flush(self):
        await self.async_session.flush()

    async def rollback(self):
        await self.async_session.rollback()

'''Una clase base para los schemas Pydantic que permite convertir objetos ORM directamente a diccionarios (útil para las respuestas de la API).'''
class SerializerModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        from_attributes=True,
    )