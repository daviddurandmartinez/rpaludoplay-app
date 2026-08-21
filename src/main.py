from parser import Credenciales, EstadoPagina, normalizar_ruc, parsear_estado_pagina
from scraper import Scraper
from database.database_connector import fetch_sql_dataframe
import time

#Resumen de la sinergia
#El parser.py alimenta de datos limpios y seguros al sistema.
#El scraper.py ejecuta las acciones físicas virtuales en la página web del MINCETUR.
#El main.py sincroniza el inicio, vigila que no haya errores durante el proceso y asegura que todo fluya de principio a fin de manera ordenada.

def main() -> None:
    credenciales = Credenciales()

    if not all(
        [credenciales.mincetur_ruc, credenciales.mincetur_usuario, credenciales.mincetur_clave]
    ):
        raise SystemExit(
            "Faltan credenciales en .env: define MINCETUR_RUC, MINCETUR_USUARIO y MINCETUR_CLAVE"
        )

    ruc = normalizar_ruc(credenciales.mincetur_ruc)

    with Scraper(headless=credenciales.mincetur_headless) as scraper:
        try:
            #scraper.navegar()
            #scraper.clic_clave_sol()
            #scraper.clic_formulario()
            #scraper.llenar_formulario(
            #    ruc,
            #    credenciales.mincetur_usuario,
            #    credenciales.mincetur_clave,
            #)
            #scraper.clic_registro_ludopatia()
            #scraper.extraer_tabla_y_fotos_pdf()
            #scraper.limpiar_carpetas()
            estado: EstadoPagina = parsear_estado_pagina(*scraper.capturar_estado())
        except Exception as e:
            print(f"Ocurrió un error durante la automatización: {e}")
            return

    print(f"Título: {estado.titulo}")
    print(f"URL: {estado.url}")

if __name__ == "__main__":
    # La función devuelve dos valores: el DataFrame y el mensaje de estado
    df, mensaje = fetch_sql_dataframe()
    if df is not None:
        print(df)
    #main()