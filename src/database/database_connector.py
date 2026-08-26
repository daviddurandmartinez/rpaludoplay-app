from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from typing import Optional
import urllib.parse
from config import SQLServerSettings,TARGET_TABLE
import pandas as pd
import os

#############################################
## CONEXION A SQL SERVER USANDO SQLALCHEMY ##
#############################################

def get_sql_server_configs() -> Optional[dict]:
    """
    Carga y valida las configuraciones de SQL Server usando Pydantic.
    Retorna un diccionario listo para la conexión o None si falla la validación.
    """
    try:
        settings = SQLServerSettings
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
    
def fetch_sqlite_dataframe() -> pd.DataFrame:
    nombre_archivo = os.path.join("src", "static", "files", "ludoplay.xlsx")
    df_excel = pd.read_excel(
        nombre_archivo,
        dtype={"id_card": str}  # Reemplaza 'id_card' por el nombre exacto del header en Excel
    )
    return df_excel

'''def create_sqlalchemy_engine():
    """
    Crea un motor de SQLAlchemy para SQL Server aplicando buenas prácticas
    de conexión, codificación de credenciales y manejo de errores.
    """
    if not SQLServerSettings:
        print("Error: No se encontró la configuración de SQL Server.")
        return None
    
    try:
        # Extraemos los valores de forma segura desde el diccionario de configuración
        driver_name = get_sql_server_configs["DRIVER"].strip("{}")
        username = get_sql_server_configs["USER"]
        server = get_sql_server_configs["SERVER"]
        database = get_sql_server_configs["DATABASE"]
        password = urllib.parse.quote_plus(get_sql_server_configs["PASSWORD"])
        
        # Construcción de la cadena de conexión optimizada para pyodbc
        conn_str = (
            f"mssql+pyodbc://{username}:{password}@{server}/{database}?"
            f"driver={driver_name}&Encrypt=no&TrustServerCertificate=yes"
        )
        
        # Creación del motor con parámetros de resiliencia (Pooling)
        engine = create_engine(
            conn_str, 
            pool_recycle=600,       # Recicla conexiones cada 10 minutos para evitar Timeouts
            pool_pre_ping=True,     # Verifica si la conexión sigue viva antes de usarla
            pool_size=5,            # Número de conexiones permanentes en el pool
            max_overflow=10         # Conexiones adicionales permitidas bajo alta demanda000
        )
        
        return engine
        
    except Exception as e:
        print(f"Error creando el motor de SQLAlchemy para la base de datos '{database}': {e}")
        return None
    
def fetch_sql_dataframe(table_name=TARGET_TABLE):
    """
    Descarga todos los datos de la tabla de destino a un DataFrame.
    Crea y desecha el motor de SQLAlchemy en la llamada.
    """
    engine = create_sqlalchemy_engine()
    if engine is None:
        return None, "Error al crear el motor de base de datos."

    try:
        # El bloque 'with' asegura que connection.close() se llame al salir.
        with engine.connect() as connection:
            query = f"SELECT * FROM {table_name}"      
            # FIX: Usar la conexión (connection) en lugar del motor (engine) en pd.read_sql
            df = pd.read_sql(query, connection) 
            return df, "Datos descargados correctamente."
        
    except Exception as e:
        return None, f"Error al descargar datos: {e}"
    finally:
        # Aseguramos que el motor se deseche al finalizar la operación de descarga.
        if engine:
            engine.dispose()'''