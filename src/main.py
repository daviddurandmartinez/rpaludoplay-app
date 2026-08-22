import logging
from config import LOGS_DIR
from database.database_connector import fetch_sqlite_dataframe
from notifier import enviar_notificacion
from parser import Credenciales, EstadoPagina, normalizar_ruc, parsear_estado_pagina
from photo_manager import mover_fotos
from scraper import Scraper
from sync_merger import construir_dataframes_sync, recorrer_e_imprimir

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


def obtener_df_scraper(credenciales: Credenciales):
    """Ejecuta la automatización MINCETUR y retorna el dataframe con datos y fotos."""
    ruc = normalizar_ruc(credenciales.mincetur_ruc)

    with Scraper(headless=credenciales.mincetur_headless) as scraper:
        try:
            scraper.navegar()
            scraper.clic_clave_sol()
            scraper.clic_formulario()
            scraper.llenar_formulario(
                ruc,
                credenciales.mincetur_usuario,
                credenciales.mincetur_clave,
            )
            scraper.clic_registro_ludopatia()
            df_scraper = scraper.extraer_tabla_y_fotos_pdf()
            estado: EstadoPagina = parsear_estado_pagina(*scraper.capturar_estado())
        except Exception:
            logger.exception("Error durante la automatización MINCETUR")
            raise

    print(f"Título: {estado.titulo} | URL: {estado.url}")
    return df_scraper


def main() -> None:
    configurar_logging()
    logger.info("Iniciando sincronización Ludoplay")

    credenciales = Credenciales()
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
    
    #recorrer_e_imprimir("df_insert", resultado.df_insert)
    #recorrer_e_imprimir("df_update", resultado.df_update)
    #recorrer_e_imprimir("df_update_recurrent", resultado.df_update_recurrent)

    resumen_fotos = mover_fotos(resultado.df_insert)
    #enviar_notificacion(resultado, resumen_fotos)

    logger.info("Sincronización finalizada")


if __name__ == "__main__":
    main()
