from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from utils.connection_bd import Model

'''Qué hace: Define la estructura exacta de la tabla players_player en SQL Server. Cada atributo = una columna.'''
'''Analogía: Es el plano arquitectónico de la tabla. Define qué columnas tiene, qué tipo de dato admite y qué restricciones apply.'''
class Player(Model):
    __tablename__ = "players_player"

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    code: Mapped[int] = mapped_column(
        Integer, name="code", nullable=False
    )
    first_name: Mapped[str] = mapped_column(
        String, name="first_name", nullable=False
    )
    last_name: Mapped[str] = mapped_column(
        String, name="last_name", nullable=False
    )
    card_type: Mapped[int] = mapped_column(
        Integer, name="card_type", nullable=False
    )
    id_card: Mapped[str] = mapped_column(
        String, name="id_card", nullable=False
    )
    ubigeo: Mapped[str] = mapped_column(
        String, name="ubigeo", nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime, name="published_at", nullable=False
    )
    contact: Mapped[str] = mapped_column(
        String, name="contact", nullable=False
    )
    photo: Mapped[str] = mapped_column(
        String, name="photo", nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, name="created_at", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, name="updated_at", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, name="is_active", nullable=False
    )