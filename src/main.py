import logging
from selenium.common.exceptions import WebDriverException
from config import LOGS_DIR, CredencialesSettings
from database.database_connector import fetch_sqlite_dataframe
from parser import EstadoPagina, normalizar_ruc, parsear_estado_pagina
from photo_manager import mover_fotos
from scraper import Scraper,Scraper_Ludoplay
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

def _procesar_registro_inhouse(tipo_operacion: str, registro: dict, scraper: Scraper_Ludoplay) -> None:
    logger.info("[%s] Iniciando scraping inhouse para: %s", tipo_operacion, registro)
    operaciones = {
        #"INSERT": scraper.clic_insert,
        "UPDATE": scraper.clic_update,
        #"UPDATE_RECURRENT": scraper.clic_update_recurrent,
    }
    metodo_accion = operaciones.get(tipo_operacion)
    if metodo_accion:
        try:
            metodo_accion(**registro)
        except WebDriverException as e:
            logger.error(
                "Error de Selenium al ejecutar %s: %s",
                tipo_operacion,
                e.msg,
                exc_info=True,
            )
            raise
    else:
        logger.warning("Tipo de operación no reconocido: %s", tipo_operacion)

def procesar_sincronizacion(resultado, credenciales: CredencialesSettings) -> None:
    """Abre una única sesión de Ludoplay y procesa las operaciones pendientes."""
    with Scraper_Ludoplay(headless=credenciales.ludopplay_headless) as scraper:
        try:
            scraper.navegar()
            scraper.llenar_formulario(
                credenciales.ludoplay_usuario,
                credenciales.ludoplay_clave,
            )
        except Exception:
            logger.exception("Error al autenticar en LUDOPLAY")
            raise

        # 1. Procesamiento de Nuevos Registros (INSERT)
        if not resultado.df_insert.empty:
            logger.info("Procesando %d registros para INSERT...", len(resultado.df_insert))
            resumen_fotos = mover_fotos(resultado.df_insert)
            logger.info("Fotos movidas exitosamente: %s", resumen_fotos)
            
            for registro in resultado.df_insert.to_dict(orient="records"):
                _procesar_registro_inhouse("INSERT", registro, scraper)
            logger.info("Tareas adicionales de INSERT finalizadas.")
        else:
            logger.info("No hay registros para insertar (df_insert vacío).")

        # 2. Procesamiento de Actualizaciones (UPDATE)
        if not resultado.df_update.empty:
            logger.info("Registros detectados en df_update (%d).", len(resultado.df_update))
            
            for registro in resultado.df_update.to_dict(orient="records"):
                _procesar_registro_inhouse("UPDATE", registro, scraper)
            logger.info("Tareas adicionales de UPDATE finalizadas.")
        else:
            logger.info("No hay registros para actualizar (df_update vacío).")

        # 3. Procesamiento de Actualizaciones Recurrentes (UPDATE RECURRENT)
        if not resultado.df_update_recurrent.empty:
            logger.info("Registros detectados en df_update_recurrent (%d).", len(resultado.df_update_recurrent))
            
            for registro in resultado.df_update_recurrent.to_dict(orient="records"):
                _procesar_registro_inhouse("UPDATE_RECURRENT", registro, scraper)
            logger.info("Tareas adicionales de UPDATE RECURRENT finalizadas.")
        else:
            logger.info("No hay registros recurrentes para actualizar (df_update_recurrent vacío).")

def main() -> None:
    configurar_logging()
    logger.info("Iniciando sincronización Ludoplay")
    credenciales = CredencialesSettings()

    if not all([credenciales.mincetur_ruc, credenciales.mincetur_usuario, credenciales.mincetur_clave]):
        raise SystemExit("Faltan credenciales en .env: define MINCETUR_RUC, MINCETUR_USUARIO y MINCETUR_CLAVE")

    # 1. Scraper Mincetur
    try:
        df_scraper = obtener_df_scraper(credenciales)
    except Exception as e:
        logger.error("Proceso abortado al obtener datos del scraper: %s", e)
        return
    if df_scraper.empty:
        logger.warning("El scraper no devolvió registros; no hay nada que sincronizar.")
        return

    # 2. Obtener datos de BD y fusionar
    df_desde_sqlite = fetch_sqlite_dataframe()
    if df_desde_sqlite is None or df_desde_sqlite.empty:
        logger.error("No se pudo obtener el dataframe desde la base de datos.")
        return
    resultado = construir_dataframes_sync(df_desde_sqlite, df_scraper)

    # 3. Ejecutar sincronización en Ludoplay
    try:
        procesar_sincronizacion(resultado, credenciales)
    except Exception as e:
        logger.error("Error durante la sincronización en Ludoplay: %s", e)
        return

    logger.info("Sincronización finalizada")

if __name__ == "__main__":
    main()