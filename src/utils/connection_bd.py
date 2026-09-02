from typing import Optional
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy_utils import create_database, database_exists
from settings import setting
from utils.constants import TARGET_TABLE

uri: URL = URL.create(
    "mssql+aioodbc",
    username=setting.BD_USERNAME,
    password=setting.BD_PASSWORD.get_secret_value(),
    host=setting.BD_HOST,
    database=setting.BD_NAME,
    query={
        "driver": "ODBC Driver 18 for SQL Server",
        "MARS_Connection": "yes",
        "Encrypt": "no",
        "TrustServerCertificate": "yes",
        "Trusted_Connection": "no"
    },
)

async_engine: AsyncEngine = create_async_engine(uri, pool_pre_ping=True)
Async_session_local: async_sessionmaker[AsyncSession] = async_sessionmaker(
    autoflush=False, bind=async_engine, expire_on_commit=False, class_=AsyncSession
)

class Model(AsyncAttrs, DeclarativeBase): ...

async def fetch_sql_dataframe(table_name: str = TARGET_TABLE) -> Optional[pd.DataFrame]:
    async with Async_session_local() as session:
        result = await session.execute(text(f"SELECT * FROM {table_name}"))
        rows = result.fetchall()
        columns = result.keys()
        return pd.DataFrame(rows, columns=columns)