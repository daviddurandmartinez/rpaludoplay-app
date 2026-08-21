from selenium.webdriver.common.by import By
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from typing import Optional

class SQLServerSettings(BaseSettings):
    """
    Modelo de configuración para SQL Server usando Pydantic.
    Lee y valida automáticamente las variables desde el archivo .env.
    """
    driver: str = Field(..., alias="DRIVER")
    server: str = Field(..., alias="SERVER")
    user: str = Field(..., alias="USER")
    database: str = Field(..., alias="DATABASE")
    password: SecretStr = Field(..., alias="PASSWORD")  # SecretStr protege las credenciales de impresión accidental

    # Configuración para apuntar al archivo .env
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignora otras variables del .env que no estén definidas aquí
    )

def get_sql_server_configs() -> Optional[dict]:
    """
    Carga y valida las configuraciones de SQL Server usando Pydantic.
    Retorna un diccionario listo para la conexión o None si falla la validación.
    """
    try:
        settings = SQLServerSettings()
        
        # Retornamos en formato diccionario (usamos .get_secret_value() para extraer la contraseña al conectar)
        return {
            "DRIVER": settings.driver,
            "SERVER": settings.server,
            "USER": settings.user,
            "DATABASE": settings.database,
            "PASSWORD": settings.password.get_secret_value(),
        }
    except Exception as e:
        print(f"Error al cargar las credenciales de configuración: {e}")
        return None

# Cargar la configuración principal validada
SQL_SERVER_CONFIG = get_sql_server_configs()

# Validar y extraer configuraciones individuales de forma segura
if SQL_SERVER_CONFIG and all(SQL_SERVER_CONFIG.values()):
    TARGET_TABLE = "dbo.players_player" 
    KEY_COLUMN = "id_card" 
else:
    TARGET_TABLE = "ERROR_TABLE_CHECK_CONFIG"
    KEY_COLUMN = "ERROR_ID_CHECK_CONFIG"

URL_EXTRANET = "https://extranet.mincetur.gob.pe/extranet2/Home/Inicio"
TIEMPO_ESPERA = 20

#Clic en CLAVE SOL
XPATH_CLAVE_SOL = "/html/body/div[2]/div[2]/div/div/div[1]"

#Ingresar a formulario y digitar ruc, usuario, clave de la empresa
XPATH_FORMULARIO = "/html/body/div[4]/div/div[4]/div[1]"
INPUT_RUC = (By.ID, "txtRuc")
INPUT_USUARIO = (By.ID, "txtUsuario")
INPUT_CLAVE = (By.ID, "txtContrasena")
XPATH_BOTON_ENTRAR = "/html/body/div[2]/div/div/div/div/div/form/div[11]/button"

#Registro de ludopatia, abre otra ventana
XPATH_REGISTRO_LUDOPATIA = "/html/body/div[2]/div/div/div[2]/div/div[2]/div[4]/table/tbody/tr/td[2]/a/button"
XPATH_REGISTRO_LUDOPATIA_ACEPTAR = "/html/body/div[8]/div[2]/fieldset/table/tbody/tr[2]/td/img"
XPATH_REGISTRO_LUDOPATIA_BUSCAR = "/html/body/div[1]/div[2]/div/div/div[1]/fieldset/table/tbody/tr[3]/td[2]/input[1]"
XPATH_REGISTRO_LUDOPATIA_EXPORTAR = "/html/body/div[1]/div[2]/div/div/div[1]/fieldset/table/tbody/tr[3]/td[1]/input"

#Ruta de descarga
PATH_DOWNLOADS = "/home/ddurand/Downloads/"