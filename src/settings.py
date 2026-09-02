from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

# Determina la raíz del proyecto (sube 1 nivel desde src/settings.py)
BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------------------------------------------------------------
# PYDANTIC: clases de configuración para gestionar credenciales y parámetros de entorno de forma segura e inteligible
# -------------------------------------------------------------------------------------------------------------------
class Setting(BaseSettings):
    MINCETUR_RUC: str = ""
    MINCETUR_USUARIO: str = ""
    MINCETUR_CLAVE: str = ""
    MINCETUR_HEADLESS: bool = False
    LUDOPLAY_USUARIO: str = ""
    LUDOPLAY_CLAVE: str = ""
    LUDOPLAY_HEADLESS: bool = False

    # Credenciales SQL Server
    BD_HOST: str
    BD_USERNAME: str
    BD_NAME: str
    BD_PASSWORD: SecretStr

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

setting: Setting = Setting()  # type: ignore