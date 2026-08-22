import logging
import shutil
from pathlib import Path
import pandas as pd
from config import APP_SETTINGS, STATIC_IMAGES_DIR

logger = logging.getLogger(__name__)

EXTENSION_FOTO = ".png"

def mover_fotos(df_insert: pd.DataFrame) -> dict:
    """
    Recorre df_insert e imprime cada registro; mueve la foto {documento}.png
    desde src/static/images hacia PATH_FOTOS_SALIDA. Retorna un resumen.
    """
    destino = Path(APP_SETTINGS.path_fotos_salida)
    destino.mkdir(parents=True, exist_ok=True)

    movidas: list[str] = []
    faltantes: list[str] = []

    print(f"\n=== Moviendo fotos de df_insert hacia {destino} ===")
    for _, fila in df_insert.iterrows():
        documento = str(fila.get("documento", "")).strip()
        persona = fila.get("persona", "")
        print(f"  [INSERT] doc={documento} | persona={persona}")

        if not documento:
            logger.warning("Fila sin documento, no se puede ubicar su foto: %s", fila.to_dict())
            continue

        foto_origen = STATIC_IMAGES_DIR / f"{documento}{EXTENSION_FOTO}"
        if foto_origen.exists():
            shutil.move(str(foto_origen), str(destino / foto_origen.name))
            movidas.append(documento)
            logger.info("Foto movida: %s -> %s", foto_origen, destino / foto_origen.name)
        else:
            faltantes.append(documento)
            logger.warning("Foto no encontrada para documento %s: %s", documento, foto_origen)

    print(f"Fotos movidas: {len(movidas)} | Faltantes: {len(faltantes)}")
    return {"movidas": movidas, "faltantes": faltantes}
