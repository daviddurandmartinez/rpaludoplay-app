import argparse
import asyncio
import logging
from fastapi import FastAPI
from routes.players import players_router
from routes.players.schemas import PlayerBulkAction, PlayerInsert, PlayerInsertRequest
from routes.players.service import PlayerSyncService
from settings import Setting
from utils.constants import LOGS_DIR
from utils.connection_bd import Async_session_local, fetch_sql_dataframe
from utils.clear_path import clear_path
from scrapers.scraper import Scraper,EstadoPagina, normalizar_ruc, parsear_estado_pagina
import pandas as pd
import uvicorn
from utils.sync_merger import construir_dataframes_sync
from datetime import datetime

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
'''Este bloque se encarga de inicializar y estructurar el sistema de registros (logging) para toda la aplicación. 
Permite rastrear qué está sucediendo en el código (eventos, advertencias o errores) en tiempo real.'''

def configurar_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8"),
            logging.StreamHandler(), #Muestra los mismos eventos en la consola/pantalla en tiempo real.
        ],
    )

configurar_logging()
logger = logging.getLogger(__name__) #Crea la instancia de log local asociada al nombre del archivo actual (__name__), lista para usar en el resto del script mediante logger.info("..."), logger.error("..."), etc.

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

'''Este bloque de código define y configura la aplicación web principal con FastAPI. En concreto, realiza tres acciones clave:
Instancia la API (app = FastAPI(...))
Registra las rutas principales (app.include_router(players_router))
Crea un endpoint de diagnóstico (@app.get("/health"))'''

app = FastAPI(
    title="Ludoplay Sync API",
    description="API para sincronizar registros de MINCETUR con la base de datos Ludoplay.",
    version="1.0.0",
)
app.include_router(players_router)
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Scraper helpers (Selenium)
# ---------------------------------------------------------------------------

def obtener_df_scraper(credenciales: Setting):
    ruc = normalizar_ruc(credenciales.MINCETUR_RUC)
    with Scraper(headless=credenciales.MINCETUR_HEADLESS) as scraper:
        try:
            scraper.navegar()
            scraper.clic_clave_sol()
            scraper.clic_formulario()
            scraper.llenar_formulario(
                ruc,
                credenciales.MINCETUR_USUARIO,
                credenciales.MINCETUR_CLAVE,
            )
            scraper.clic_registro_ludopatia()
            df_scraper = scraper.extraer_tabla_y_fotos_pdf()
            estado: EstadoPagina = parsear_estado_pagina(*scraper.capturar_estado())
        except Exception:
            logger.exception("Error durante la automatización MINCETUR")
            raise
    logger.info("Scraper OK — Título: %s | URL: %s", estado.titulo, estado.url)
    return df_scraper

# ---------------------------------------------------------------------------
# DataFrame → Pydantic conversion
# ---------------------------------------------------------------------------

def _df_insert_to_request(df) -> PlayerInsertRequest:
    players: list[PlayerInsert] = []
    for _, row in df.iterrows():
        players.append(PlayerInsert(
            code=int(row.get("code", 0)) if pd.notna(row.get("code")) else 0,
            first_name=str(row.get("first_name", "")).strip(),
            last_name=str(row.get("last_name", "")).strip(),
            card_type=int(row.get("card_type", 1)) if pd.notna(row.get("card_type")) else 1,
            id_card=str(row.get("id_card", "")).strip(),
            ubigeo=str(row.get("ubigeo", "")).strip(),
            published_at=datetime.strptime(str(row.get("published_at", "")).strip(), "%d/%m/%Y"),
            contact=str(row.get("contact", "")).strip(),
            photo=str(row.get("photo", "")).strip() or None
        ))
    return PlayerInsertRequest(players=players)

def _df_to_bulk_action(df, id_card_col: str = "id_card") -> PlayerBulkAction | None:
    if df is None or df.empty:
        return None
    id_cards = [str(v).strip() for v in df[id_card_col].tolist() if str(v).strip()]
    return PlayerBulkAction(id_cards=id_cards) if id_cards else None

# ---------------------------------------------------------------------------
# Full sync pipeline (CLI)
# ---------------------------------------------------------------------------

async def run_full_sync(credenciales: Setting) -> None:
    """Execute the full synchronization pipeline:
       Scraper MINCETUR → DB query → Merge → DB sync.
    """
    # Stage 1: Scraper MINCETUR
    logger.info("=== Etapa 1/5: Scraper MINCETUR ===")
    try:
        df_scraper = obtener_df_scraper(credenciales)
    except Exception as e:
        logger.error("Scraper falló: %s", e)
        return

    if df_scraper.empty:
        logger.warning("El scraper no devolvió registros. Nada que sincronizar.")
        return
    logger.info("Scraper devolvió %d registros", len(df_scraper))

    # Stage 2: Query ludoplay DB
    logger.info("=== Etapa 2/5: Consulta base de datos Ludoplay ===")
    df_desde_sql = await fetch_sql_dataframe()
    if df_desde_sql is None or df_desde_sql.empty:
        logger.error("No se pudo obtener datos desde la base de datos Ludoplay.")
        return
    logger.info("BD Ludoplay devolvió %d registros", len(df_desde_sql))

    # Stage 3: Merge
    logger.info("=== Etapa 3/5: Merge / Comparativo ===")
    resultado = construir_dataframes_sync(df_desde_sql, df_scraper)
    logger.info(
        "Resultado merge — INSERT: %d | UPDATE (desactivar): %d | RECURRENT (reactivar): %d",
        len(resultado.df_insert),
        len(resultado.df_update),
        len(resultado.df_update_recurrent),
    )

    # Stage 4: DB sync via service
    logger.info("=== Etapa 4/5: Sincronización directa a BD ===")
    async with Async_session_local() as session:
        svc = PlayerSyncService(session)
        insert_req = _df_insert_to_request(resultado.df_insert) if not resultado.df_insert.empty else None
        deactivate_req = _df_to_bulk_action(resultado.df_update, "id_card")
        reactivate_req = _df_to_bulk_action(resultado.df_update_recurrent, "id_card")
        result = await svc.sync_all(insert_req, deactivate_req, reactivate_req)

    logger.info("=== Sincronización completada ===")
    logger.info(
        "Resultado final — insertados: %d | desactivados: %d | reactivados: %d | fotos: %d",
        result.inserted, result.deactivated, result.reactivated, result.photos_moved,
    )
    if result.errors:
        logger.warning("Errores: %s", result.errors)

    logger.info("=== Etapa 5/5: Clear Path ===")
    clear_path()

# ---------------------------------------------------------------------------
# Interfaces de línea de comandos (CLI)
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Ludoplay Sync — Scraper MINCETUR + Sincronización a BD"
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Ejecuta el pipeline completo: scraper → merge → sync a BD",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Levanta el servidor FastAPI (uvicorn)",
    )
    args = parser.parse_args()

    if args.sync:
        credenciales = Setting()
        if not all([credenciales.MINCETUR_RUC, credenciales.MINCETUR_USUARIO, credenciales.MINCETUR_CLAVE]):
            raise SystemExit("Faltan credenciales MINCETUR en .env")
        asyncio.run(run_full_sync(credenciales))

    elif args.server:
        uvicorn.run("main:app", reload=True)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()