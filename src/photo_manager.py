'''Este script busca y mueve las imágenes de perfil (.png) de las personas recién ingresadas (df_insert) desde la carpeta
 temporal de imágenes del proyecto hacia una carpeta de salida configurada.'''
import logging
import shutil
from pathlib import Path
import pandas as pd
from config import AppSettings, STATIC_IMAGES_DIR,EXTENSION_FOTO

logger = logging.getLogger(__name__)

def mover_fotos(df_insert: pd.DataFrame) -> dict:
    """
    Recorre df_insert e imprime cada registro; mueve la foto {documento}.png
    desde src/static/images hacia PATH_FOTOS_SALIDA. Retorna un resumen.
    """
    #Crea la carpeta de destino especificada en la configuración si aún no existe (evita errores de carpeta no encontrada).
    destino = Path(AppSettings().path_fotos_salida)
    destino.mkdir(parents=True, exist_ok=True)

    #Inicializa dos listas vacías (movidas y faltantes) y recorre fila por fila el DataFrame de registros nuevos (df_insert).
    movidas: list[str] = []
    faltantes: list[str] = []

    print(f"\n=== Moviendo fotos de df_insert hacia {destino} ===")
    for _, fila in df_insert.iterrows():
        documento = str(fila.get("documento", "")).strip() #Extrae el número de documento. Si el registro no tiene un documento válido, registra una advertencia (logger.warning) y salta al siguiente registro con continue.

        if not documento:
            logger.warning("Fila sin documento, no se puede ubicar su foto: %s", fila.to_dict())
            continue

        foto_origen = STATIC_IMAGES_DIR / f"{documento}{EXTENSION_FOTO}" #Construcción de la ruta origen: Arma la ruta buscando una imagen llamada {documento}.png en la carpeta STATIC_IMAGES_DIR.
        if foto_origen.exists():
            #Usa shutil.move() para transferir físicamente el archivo .png de origen a destino y guarda el número de documento en la lista movidas.
            shutil.move(str(foto_origen), str(destino / foto_origen.name))
            movidas.append(documento)
            logger.info("Foto movida: %s -> %s", foto_origen, destino / foto_origen.name)
        else:
            #Guarda el documento en la lista faltantes y genera un aviso en el registro (logger.warning).
            faltantes.append(documento)
            logger.warning("Foto no encontrada para documento %s: %s", documento, foto_origen)

    print(f"Fotos movidas: {len(movidas)} | Faltantes: {len(faltantes)}")
    return {"movidas": movidas, "faltantes": faltantes}