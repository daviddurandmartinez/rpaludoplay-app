import logging
from dataclasses import dataclass
from utils.constants import CODIGOS_EXCLUIDOS
import pandas as pd

logger = logging.getLogger(__name__)

LLAVE_DB = "id_card"
LLAVE_SCRAPER = "id_card"

@dataclass
class ResultadoSync:
    """Contenedores del resultado del merge entre df_scraper y df_desde_sqlite."""
    df_insert: pd.DataFrame
    df_update: pd.DataFrame
    df_update_recurrent: pd.DataFrame

def _clear_text(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina saltos de línea y espacios extras en todas las columnas de tipo string."""
    df_clean = df.copy()
    col_texto = df_clean.select_dtypes(include=["object", "string"]).columns
    
    for col in col_texto:
        df_clean[col] = (
            df_clean[col]
            .astype(str)
            .str.replace(r"[\r\n]+", " ", regex=True) # Reemplaza saltos de línea por un espacio
            .str.strip()
        )
    return df_clean

def _normalize_key(valores: pd.Series) -> pd.Series:
    return valores.astype(str).str.strip()


def build_dataframes_sync(
                        df_desde_sqlite: pd.DataFrame,
                        df_scraper: pd.DataFrame,
                        ) -> ResultadoSync:
    """
    Genera los 3 dataframes de sincronización usando la llave id_card <-> id_card:
      - df_insert: en scraper y NO en base (nuevos en MINCETUR)
      - df_update: en base con is_active=1 y NO en scraper (salieron del registro oficial)
      - df_update_recurrent: en ambos y is_active=0 en base (reaparecieron)
    """
    # 1. Limpieza de saltos de línea y espacios en blanco en todo el DataFrame
    db = _clear_text(df_desde_sqlite)
    sc = _clear_text(df_scraper)

    db["_key"] = _normalize_key(db[LLAVE_DB])
    sc["_key"] = _normalize_key(sc[LLAVE_SCRAPER])

    #Esa instrucción elimina todas las filas que tengan una llave vacía ("") tanto en el DataFrame de la base de datos (db) como en el del scraper (sc).
    db = db[db["_key"].ne("")]
    sc = sc[sc["_key"].ne("")]

    #Comprueba si la tabla de la base de datos incluye una columna de fecha/hora de actualización.
    if "updated_at" in db.columns:
        db = db.sort_values("updated_at", ascending=False)
    #Busca registros que compartan el mismo id_card/ID (_key).
    #Gracias al keep="first", se queda con la primera fila que encuentra (que es la más reciente por el ordenamiento previo) y elimina las versiones antiguas de ese mismo id_card.    
    db = db.drop_duplicates(subset="_key", keep="first")
    #Si el scraper por error extrajo varias veces a la misma persona con el mismo id_card, se queda solo con el primer registro hallado y descarta las repeticiones.
    sc = sc.drop_duplicates(subset="_key", keep="first")

    #Extrae los id_card/IDs de cada DataFrame y los convierte en conjuntos (set) de Python.¿Por qué un set? En Python, buscar un elemento en un set 
    #toma tiempo constante $O(1)$, mientras que en una lista o Series toma $O(n)$. Esto optimiza la velocidad de filtrado cuando hay miles de filas.
    claves_sc = set(sc["_key"])
    claves_db = set(db["_key"])

    # -------------------------------------------------------------------------
    # df_insert (Registros a insertar)
    # -------------------------------------------------------------------------
    df_insert = (
        #Compara cada registro del scraper contra las llaves de la base de datos. Devuelve True si el id_card ya existe en la base de datos y False si es nuevo.
        sc[~sc["_key"].isin(claves_db)] # "~" Transforma los False (los que no están en la DB) en True. Esto selecciona únicamente a las personas que el scraper encontró pero que la base de datos nunca ha visto.
        .drop(columns=["_key"]) #Elimina la columna auxiliar _key que se creó al inicio para normalizar los textos, devolviendo el DataFrame con su estructura original.
        .reset_index(drop=True) #Reorganiza los índices del nuevo DataFrame de 0 a N-1 para eliminar los saltos de índice que quedaron tras el filtrado.
    )

    # -------------------------------------------------------------------------
    # df_update (Registros a desactivar)
    # -------------------------------------------------------------------------
    # Condición: NO está en scraper AND is_active == 1 AND code NOT IN excluidos
    mascara_update = (
        (~db["_key"].isin(claves_sc)) 
        & (db["is_active"] == 1) 
        & (~db["code"].isin(CODIGOS_EXCLUIDOS))
    )
    #Extrae esas filas, elimina la columna auxiliar _key y limpia los índices.
    df_update = (
        db[mascara_update]
        .drop(columns=["_key"])
        .reset_index(drop=True)
    )

    # -------------------------------------------------------------------------
    # df_update_recurrent (Registros a reactivar)
    # -------------------------------------------------------------------------
    # Mapeamos tanto el estado (is_active) como el código (code) desde la DB
    estado_db = db.set_index("_key")["is_active"] #Crea una serie de consulta rápida donde el índice es el número de id_card y el valor es su estado actual (0 o 1).
    codigo_db = db.set_index("_key")["code"]
    en_ambos = sc[sc["_key"].isin(claves_db)].copy() #Filtra las filas del scraper que SÍ existen en la base de datos.
    en_ambos["_is_active"] = en_ambos["_key"].map(estado_db) #Utiliza el .map() para "traer" el estado que tenía esa persona en la DB y colocarlo al lado del registro del scraper.
    en_ambos["_code"] = en_ambos["_key"].map(codigo_db)
    df_update_recurrent = (
        en_ambos[
            (en_ambos["_is_active"] == 0) & 
            (~en_ambos["_code"].isin(CODIGOS_EXCLUIDOS))
        ]
        .drop(columns=["_key", "_is_active"]) #Remueve las columnas temporales _key y _is_active.
        .reset_index(drop=True) #Estos registros deben actualizarse en la DB a is_active = 1 (volvieron a figurar en MINCETUR/Scraper).
    )

    #Muestra un mensaje informativo en la consola o archivo de registro de tu aplicación.
    logger.info(
        "Merge completado: insert=%d | update=%d | recurrent=%d",
        len(df_insert),
        len(df_update),
        len(df_update_recurrent),
    )

    #Instancia y retorna la dataclass que se definió al inicio del script.
    #Asigna cada DataFrame procesado a su respectivo atributo (df_insert, df_update, df_update_recurrent).
    return ResultadoSync(
        df_insert=df_insert,
        df_update=df_update,
        df_update_recurrent=df_update_recurrent,
    )