from pathlib import Path
from selenium.webdriver.common.by import By
# ---------------------------------------------------------------------------------------
# SQL SERVER
# ---------------------------------------------------------------------------------------
TARGET_TABLE = "dbo.players_player"
KEY_COLUMN = "id_card"

# ---------------------------------------------------------------------------------------
# Rutas del proyecto basadas en la ubicación de este archivo (independientes del CWD)
# --------------------------------------------------------------------------------------- 
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent  # src/
STATIC_IMAGES_DIR = PROJECT_ROOT / "static" / "images"
LOGS_DIR = PROJECT_ROOT / "logs"
EXTENSION_FOTO = ".png"
PATH_FOTOS_SALIDA = Path("/home/ddurand/fotos")
PATH_DOWNLOADS = Path("/home/ddurand/Downloads/") #Ruta de descarga

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

# -------------------------------------------------------------------------
# MERGE: GENERACION DE df_insert, df_update, df_update_recurrent
# -------------------------------------------------------------------------
CODIGOS_EXCLUIDOS = [10010, 99999999, 88888888]