from dataclasses import dataclass
from pydantic_settings import BaseSettings, SettingsConfigDict


class Credenciales(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mincetur_ruc: str = ""
    mincetur_usuario: str = ""
    mincetur_clave: str = ""
    mincetur_headless: bool = False

def normalizar_ruc(ruc: str) -> str:
    ruc_limpio = ruc.strip()
    if not ruc_limpio.isdigit() or len(ruc_limpio) != 11:
        raise ValueError(f"El RUC debe tener 11 dígitos numéricos, se recibió: {ruc!r}")
    return ruc_limpio

@dataclass
class EstadoPagina:
    titulo: str
    url: str
    texto_visible: str


def parsear_estado_pagina(titulo: str, url: str, texto_visible: str) -> EstadoPagina:
    return EstadoPagina(
        titulo=titulo.strip(),
        url=url.strip(),
        texto_visible=texto_visible.strip(),
    )