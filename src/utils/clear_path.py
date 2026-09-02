import os
import glob
from utils.constants import (
    PATH_DOWNLOADS,
    PATH_FOTOS_SALIDA,
    STATIC_IMAGES_DIR,
)

def clear_path() -> None:
    carpetas_a_limpiar = [
        STATIC_IMAGES_DIR,
        PATH_FOTOS_SALIDA,
        PATH_DOWNLOADS,
    ]

    for carpeta in carpetas_a_limpiar:
        if not carpeta.exists():
            print(f"La carpeta no existe: {carpeta}")
            continue

        # Iterar sobre todos los elementos dentro de la carpeta
        for elemento in carpeta.iterdir():
            if elemento.is_file():
                try:
                    elemento.unlink()  # Elimina el archivo
                except Exception as e:
                    print(f"No se pudo eliminar {elemento}: {e}")