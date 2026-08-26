from pathlib import Path
from selenium.webdriver.common.by import By
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

# -------------------------------------------------------------------------------------------------------------------
# PYDANTIC: clases de configuración para gestionar credenciales y parámetros de entorno de forma segura e inteligible
# -------------------------------------------------------------------------------------------------------------------

class CredencialesSettings(BaseSettings):
    mincetur_ruc: str = ""
    mincetur_usuario: str = ""
    mincetur_clave: str = ""
    mincetur_headless: bool = False
    ludoplay_usuario: str = ""
    ludoplay_clave: str = ""
    ludopplay_headless: bool = False
    # Configuración para apuntar al archivo .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

class SQLServerSettings(BaseSettings):
    """
    Modelo de configuración para SQL Server usando Pydantic.
    Lee y valida automáticamente las variables desde el archivo .env.
    """
    driver: str = Field(..., alias="DRIVER") # El uso de ... marca que el campo es obligatorio. Si no existe en el archivo .env, Pydantic lanzará un error de validación.
    server: str = Field(..., alias="SERVER") # Mapea la variable de entorno DRIVER a la propiedad de Python driver
    user: str = Field(..., alias="USER")
    database: str = Field(..., alias="DATABASE")
    password: SecretStr = Field(..., alias="PASSWORD")  # SecretStr protege las credenciales de impresión accidental
    # Configuración para apuntar al archivo .env
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignora otras variables del .env que no estén definidas aquí
    )

class AppSettings(BaseSettings):
    """
    Configuración general de la aplicación (rutas de salida).
    """
    path_fotos_salida: str = "/home/ddurand/fotos" # Define una ruta por defecto en el sistema operativo donde la aplicación guardará imágenes extraídas o procesadas
    # Configuración para apuntar al archivo .env
    model_config = SettingsConfigDict(
        env_file=".env", # Lee los valores automáticamente desde el archivo .env.
        env_file_encoding="utf-8", # Define la codificación de lectura del archivo.
        extra="ignore", # Si en el archivo .env hay más variables que no coinciden con esta clase, las ignora sin lanzar un error.
    )

# ---------------------------------------------------------------------------------------
# SQL SERVER
# ---------------------------------------------------------------------------------------
TARGET_TABLE = "dbo.players_player"
KEY_COLUMN = "id_card"

# ---------------------------------------------------------------------------------------
# Rutas del proyecto basadas en la ubicación de este archivo (independientes del CWD)
# --------------------------------------------------------------------------------------- 
SRC_DIR = Path(__file__).resolve().parent
STATIC_IMAGES_DIR = SRC_DIR / "static" / "images"
STATIC_FILES_DIR = SRC_DIR / "static" / "files"
LOGS_DIR = SRC_DIR.parent / "logs"
EXTENSION_FOTO = ".png"

# ---------------------------------------------------------------------------------------
# SCRAPER A MINCETUR
# ---------------------------------------------------------------------------------------
URL_EXTRANET = "https://extranet.mincetur.gob.pe/extranet2/Home/Inicio"
TIEMPO_ESPERA = 20
XPATH_CLAVE_SOL = "/html/body/div[2]/div[2]/div/div/div[1]" #Clic en CLAVE SOL
XPATH_FORMULARIO = "/html/body/div[4]/div/div[4]/div[1]" #Ingresar a formulario y digitar ruc, usuario, clave de la empresa
INPUT_RUC = (By.ID, "txtRuc")
INPUT_USUARIO = (By.ID, "txtUsuario")
INPUT_CLAVE = (By.ID, "txtContrasena")
XPATH_BOTON_ENTRAR = "/html/body/div[2]/div/div/div/div/div/form/div[11]/button"
XPATH_REGISTRO_LUDOPATIA = "/html/body/div[2]/div/div/div[2]/div/div[2]/div[4]/table/tbody/tr/td[2]/a/button" #Registro de ludopatia, abre otra ventana
XPATH_REGISTRO_LUDOPATIA_ACEPTAR = "/html/body/div[8]/div[2]/fieldset/table/tbody/tr[2]/td/img"
XPATH_REGISTRO_LUDOPATIA_BUSCAR = "/html/body/div[1]/div[2]/div/div/div[1]/fieldset/table/tbody/tr[3]/td[2]/input[1]"
XPATH_REGISTRO_LUDOPATIA_EXPORTAR = "/html/body/div[1]/div[2]/div/div/div[1]/fieldset/table/tbody/tr[3]/td[1]/input"
PATH_DOWNLOADS = "/home/ddurand/Downloads/" #Ruta de descarga

# -------------------------------------------------------------------------
# MERGE: GENERACION DE df_insert, df_update, df_update_recurrent
# -------------------------------------------------------------------------
CODIGOS_EXCLUIDOS = [10010, 99999999, 88888888]

# ---------------------------------------------------------------------------------------
# SCRAPER A SISTEMA LUDOPLAY
# ---------------------------------------------------------------------------------------
URL_LUDOPLAY="http://ludoplay.gruposam.com.pe/accounts/login/"
INPUT_USUARIO_LUDOPLAY = (By.NAME, "username")
INPUT_CLAVE_LUDOPLAY = (By.NAME, "password")
XPATH_BOTON_ENTRAR_LUDOPLAY = "/html/body/section/div/div[1]/form/div[2]/button"
XPATH_MENU_PERSONAS_LUDOPLAY = "/html/body/aside/section[1]/ul/li[1]/ul/li[3]/a"
XPATH_MENU_PERSONAS_LISTA_LUDOPLAY = "/html/body/section/div[1]/a[1]"
XPATH_MENU_PERSONAS_NUEVO_LUDOPLAY = "/html/body/section/div[1]/a[2]"
XPATH_MENU_PERSONAS_NUEVO_REGISTRO = (By.ID, "id_code")
INPUT_MENU_PERSONAS_NUEVO_UBIGEO = (By.ID, "id_ubigeo")
INPUT_MENU_PERSONAS_NUEVO_NOMBRE = (By.ID, "id_first_name")
INPUT_MENU_PERSONAS_NUEVO_APELLIDO = (By.ID, "id_last_name")
INPUT_MENU_PERSONAS_NUEVO_TIPO = (By.ID, "id_card_type")
INPUT_MENU_PERSONAS_NUEVO_DOCUMENTO = (By.ID, "id_id_card")
INPUT_MENU_PERSONAS_NUEVO_CONTACTO = (By.ID, "id_contact")
INPUT_MENU_PERSONAS_NUEVO_PUBLICADO = (By.ID, "id_published_at")
INPUT_MENU_PERSONAS_NUEVO_FOTO = (By.ID, "id_photo")
XPATH_MENU_PERSONAS_NUEVO_BOTON = "/html/body/section/div[2]/form/div[2]/div/button"