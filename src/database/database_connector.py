from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from typing import Optional
import urllib.parse
from config import SQL_SERVER_CONFIG,TARGET_TABLE  # Asegúrate de importar tu configuración validada
import pandas as pd
import sqlite3
import openpyxl
import os

#############################################
## CONEXION A SQL SERVER USANDO SQLALCHEMY ##
#############################################

def fetch_sqlite_dataframe():
    nombre_archivo = os.path.join("src", "static", "files","ludoplay.xlsx")
    df_excel = pd.read_excel(nombre_archivo)
    conn = sqlite3.connect(':memory:')
    df_excel.to_sql('ludoplay', conn, if_exists='replace', index=False)
    consulta_sql = "SELECT * FROM ludoplay"
    df_desde_sqlite = pd.read_sql(consulta_sql, conn)
    conn.close()
    return df_desde_sqlite

'''def create_sqlalchemy_engine():
    """
    Crea un motor de SQLAlchemy para SQL Server aplicando buenas prácticas
    de conexión, codificación de credenciales y manejo de errores.
    """
    if not SQL_SERVER_CONFIG:
        print("Error: No se encontró la configuración de SQL Server.")
        return None
    
    try:
        # Extraemos los valores de forma segura desde el diccionario de configuración
        driver_name = SQL_SERVER_CONFIG["DRIVER"].strip("{}")
        username = SQL_SERVER_CONFIG["USER"]
        server = SQL_SERVER_CONFIG["SERVER"]
        database = SQL_SERVER_CONFIG["DATABASE"]
        password = urllib.parse.quote_plus(SQL_SERVER_CONFIG["PASSWORD"])
        
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

# Ejemplo de uso:
# engine_gestion = create_sqlalchemy_engine(database="NOMBRE_DE_BD")

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