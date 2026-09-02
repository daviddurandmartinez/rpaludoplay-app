from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from utils.connection_bd import Model

T = TypeVar("T", bound="Model")

class RepositoryBase(Generic[T]):
    """RepositoryBase.
    Use this class when you create a new Repository class to manage transactions"""

    def __init__(self, async_session: AsyncSession):
        self.async_session: AsyncSession = async_session

    async def commit(self):
        await self.async_session.commit()

    async def flush(self):
        await self.async_session.flush()

    async def rollback(self):
        await self.async_session.rollback()

class SerializerModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        from_attributes=True,
    )