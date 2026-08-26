import logging
from config import LOGS_DIR, CredencialesSettings
from database.database_connector import fetch_sqlite_dataframe
from parser import EstadoPagina, normalizar_ruc, parsear_estado_pagina
from photo_manager import mover_fotos
from scraper import Scraper
from sync_merger import construir_dataframes_sync

logger = logging.getLogger(__name__)

def configurar_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

def obtener_df_scraper(credenciales: CredencialesSettings):
    """Ejecuta la automatización MINCETUR y retorna el dataframe con datos y fotos."""
    ruc = normalizar_ruc(credenciales.mincetur_ruc)

    with Scraper(headless=credenciales.mincetur_headless) as scraper:
        try:
            scraper.navegar()
            '''scraper.clic_clave_sol()
            scraper.clic_formulario()
            scraper.llenar_formulario(
                ruc,
                credenciales.mincetur_usuario,
                credenciales.mincetur_clave,
            )
            scraper.clic_registro_ludopatia()'''
            df_scraper = scraper.extraer_tabla_y_fotos_pdf()
            estado: EstadoPagina = parsear_estado_pagina(*scraper.capturar_estado())
        except Exception:
            logger.exception("Error durante la automatización MINCETUR")
            raise

    print(f"Título: {estado.titulo} | URL: {estado.url}")
    return df_scraper

def _procesar_registro_inhouse(tipo_operacion: str, registro: dict) -> None:
    """Función para ejecutar el scraping e ingresar/actualizar el registro en el sistema web inhouse."""
    logger.info("[%s] Iniciando scraping inhouse para: %s", tipo_operacion, registro)
    # Ejemplo de extracción de datos del diccionario:
    # documento = registro.get("documento")
    # nombre = registro.get("persona")
    # ... comandos de Selenium/Playwright para llenar el formulario inhouse ...

def procesar_sincronizacion(resultado) -> None:
    """Aplica la lógica de negocio según el contenido de los DataFrames de sincronización."""

    # 1. Procesamiento de Nuevos Registros (INSERT)
    if not resultado.df_insert.empty:
        logger.info("Procesando %d registros para INSERT...", len(resultado.df_insert))

        # Mueve las fotos de los registros a insertar
        resumen_fotos = mover_fotos(resultado.df_insert)
        logger.info("Fotos movidas exitosamente: %s", resumen_fotos)

        # Iteración fila por fila para scraping inhouse
        for registro in resultado.df_insert.to_dict(orient="records"):
            _procesar_registro_inhouse("INSERT", registro)

        logger.info("Tareas adicionales de scraping en sistema inhouse finalizadas.")
    else:
        logger.info("No hay registros para insertar (df_insert vacío).")

    # 2. Procesamiento de Actualizaciones (UPDATE)
    if not resultado.df_update.empty:
        logger.info(
            "Registros detectados en df_update (%d). Pendiente scraping a sistema inhouse.",
            len(resultado.df_update),
        )

        # Iteración fila por fila para scraping inhouse
        for registro in resultado.df_update.to_dict(orient="records"):
            _procesar_registro_inhouse("UPDATE", registro)

        logger.info("Tareas adicionales de scraping en sistema inhouse finalizadas.")
    else:
        logger.info("No hay registros para actualizar (df_update vacío).")

    # 3. Procesamiento de Actualizaciones Recurrentes (UPDATE RECURRENT)
    if not resultado.df_update_recurrent.empty:
        logger.info(
            "Registros detectados en df_update_recurrent (%d). Pendiente scraping a sistema inhouse.",
            len(resultado.df_update_recurrent),
        )

        # Iteración fila por fila para scraping inhouse
        for registro in resultado.df_update_recurrent.to_dict(orient="records"):
            _procesar_registro_inhouse("UPDATE_RECURRENT", registro)

        logger.info("Tareas adicionales de scraping en sistema inhouse finalizadas.")
    else:
        logger.info("No hay registros recurrentes para actualizar (df_update_recurrent vacío).")

def main() -> None:
    configurar_logging()
    logger.info("Iniciando sincronización Ludoplay")
    credenciales = CredencialesSettings()
    if not all(
        [credenciales.mincetur_ruc, credenciales.mincetur_usuario, credenciales.mincetur_clave]
        ):
        raise SystemExit(
            "Faltan credenciales en .env: define MINCETUR_RUC, MINCETUR_USUARIO y MINCETUR_CLAVE"
        )

    try:
        df_scraper = obtener_df_scraper(credenciales)
    except Exception as e:
        logger.error("Proceso abortado al obtener datos del scraper: %s", e)
        return

    if df_scraper.empty:
        logger.warning("El scraper no devolvió registros; no hay nada que sincronizar.")
        return

    df_desde_sqlite = fetch_sqlite_dataframe()
    if df_desde_sqlite is None or df_desde_sqlite.empty:
        logger.error("No se pudo obtener el dataframe desde la base de datos.")
        return
 
    resultado = construir_dataframes_sync(df_desde_sqlite, df_scraper)
    # Evaluación condicional de DataFrames
    procesar_sincronizacion(resultado)

    logger.info("Sincronización finalizada")

if __name__ == "__main__":
    main()