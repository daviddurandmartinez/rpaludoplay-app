from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
import pandas as pd
import pdfplumber
import pymupdf as fitz
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utils.constants import (
    INPUT_CLAVE,
    INPUT_RUC,
    INPUT_USUARIO,
    PATH_DOWNLOADS,
    STATIC_IMAGES_DIR,
    TIEMPO_ESPERA,
    URL_EXTRANET,
    XPATH_BOTON_ENTRAR,
    XPATH_CLAVE_SOL,
    XPATH_FORMULARIO,
    XPATH_REGISTRO_LUDOPATIA,
    XPATH_REGISTRO_LUDOPATIA_ACEPTAR,
    XPATH_REGISTRO_LUDOPATIA_BUSCAR,
    XPATH_REGISTRO_LUDOPATIA_EXPORTAR,
)

'''Validar, limpiar y estructurar datos que provienen del scraping o de entradas del usuario.
Ofrece utilidades para garantizar un RUC válido y normalizar el contenido extraído de la web.'''

def normalize_ruc(ruc: str) -> str:
    ruc_limpio = ruc.strip()
    if not ruc_limpio.isdigit() or len(ruc_limpio) != 11:
        raise ValueError(f"El RUC debe tener 11 dígitos numéricos, se recibió: {ruc!r}")
    return ruc_limpio

@dataclass
class EstadoPagina:
    titulo: str
    url: str
    texto_visible: str

def parse_page_status(titulo: str, url: str, texto_visible: str) -> EstadoPagina:
    return EstadoPagina(
        titulo=titulo.strip(),
        url=url.strip(),
        texto_visible=texto_visible.strip(),
    )

def _build_options(headless: bool = False) -> Options:
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--kiosk-printing")  
    options.binary_location = "/snap/bin/chromium"    
    
    # Manejo con pathlib: asegura la creación del directorio como string para Selenium
    PATH_DOWNLOADS.mkdir(parents=True, exist_ok=True)
    download_dir_str = str(PATH_DOWNLOADS)
    
    app_state = {
        "recent_destinations": [{"id": "Save as PDF", "origin": "local", "account": ""}],
        "selected_destination_id": "Save as PDF",
        "version": 2
    }   
    prefs = {
        'download.default_directory': download_dir_str,
        'savefile.default_directory': download_dir_str,
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': True,
        'profile.default_content_settings.popups': 0,
        'plugins.always_open_pdf_externally': True,
        "printing.print_preview_sticky_settings.app_state": json.dumps(app_state)
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)  
    if headless:
        options.add_argument("--headless")
        
    return options

class Scraper:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = webdriver.Chrome(options=_build_options(headless))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()

    def browse(self) -> None:
        self.driver.get(URL_EXTRANET)

    def _wait_click(self, selector: tuple) -> None:
        boton = WebDriverWait(self.driver, TIEMPO_ESPERA).until(
            EC.element_to_be_clickable(selector)
        )
        boton.click()

    def click_key(self) -> None:
        self._wait_click((By.XPATH, XPATH_CLAVE_SOL))

    def click_form(self) -> None:
        self._wait_click((By.XPATH, XPATH_FORMULARIO))

    def fill_form(self, ruc: str, usuario: str, clave: str) -> None:
        WebDriverWait(self.driver, TIEMPO_ESPERA).until(
            EC.presence_of_element_located(INPUT_RUC)
        )
        self.driver.find_element(*INPUT_RUC).send_keys(ruc)
        self.driver.find_element(*INPUT_USUARIO).send_keys(usuario)
        self.driver.find_element(*INPUT_CLAVE).send_keys(clave)
        self._wait_click((By.XPATH, XPATH_BOTON_ENTRAR))
        print("Formulario CLAVE SOL rellenado con las credenciales del .env")

    def click_registration(self) -> None:
        self._wait_click((By.XPATH, XPATH_REGISTRO_LUDOPATIA))
        print("Ingresa a registro de ludopatia")
        
        ventanas = self.driver.window_handles
        self.driver.switch_to.window(ventanas[-1])
        
        self._wait_click((By.XPATH, XPATH_REGISTRO_LUDOPATIA_ACEPTAR))
        print("ACEPTAR registros de ludopatia")
        
        self._wait_click((By.XPATH, XPATH_REGISTRO_LUDOPATIA_BUSCAR))
        print("BUSCAR registros de ludopatia")
        
        time.sleep(80) 
        
        self._wait_click((By.XPATH, XPATH_REGISTRO_LUDOPATIA_EXPORTAR))
        print("EXPORTAR registros de ludopatia - Guardando PDF automáticamente...")

        time.sleep(20) 

        # Espera de archivo utilizando pathlib (sin os.listdir)
        tiempo_maximo = 60
        tiempo_transcurrido = 0
        archivo_descargado = False
        
        while tiempo_transcurrido < tiempo_maximo:
            archivos_nombres = [p.name for p in PATH_DOWNLOADS.iterdir() if p.is_file()]
            if any(f.endswith('.pdf') for f in archivos_nombres) and not any(f.endswith('.crdownload') for f in archivos_nombres):
                archivo_descargado = True
                break
            time.sleep(1)
            tiempo_transcurrido += 1

        if archivo_descargado:
            print(f"¡El PDF se ha descargado y guardado correctamente en {PATH_DOWNLOADS}!")
        else:
            print("Advertencia: El tiempo de descarga expiró o el archivo sigue procesándose.")

    def extract_table_photos_pdf(self) -> pd.DataFrame:
        # 1. Buscar automáticamente el PDF más reciente con pathlib
        archivos_pdf = [p for p in PATH_DOWNLOADS.glob("*.pdf") if p.is_file()]
        
        if not archivos_pdf:
            raise FileNotFoundError(f"No se encontró ningún archivo PDF en {PATH_DOWNLOADS}")
        
        # Selecciona el PDF más reciente basándose en mtime
        ruta_pdf = max(archivos_pdf, key=lambda p: p.stat().st_mtime)
        print(f"Procesando archivo PDF: {ruta_pdf}")
        
        # 3. Carpeta de destino del proyecto
        STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        tipos_doc = ["Dni", "Permiso Temporal De Permanencia", "Carnet Extranjeria", "Pasaporte"]
        patron_limpieza = re.compile(f"({'|'.join(tipos_doc)})", re.IGNORECASE)

        datos_completos = []
        doc_fitz = fitz.open(str(ruta_pdf))

        with pdfplumber.open(str(ruta_pdf)) as pdf:
            for num_pag, page in enumerate(pdf.pages):
                print(f"Procesando página {num_pag + 1} de {len(pdf.pages)}...")
                tabla = page.extract_table()
                if not tabla: 
                    continue

                pagina_fitz = doc_fitz[num_pag]
                imagenes_pagina = pagina_fitz.get_images(full=True)
                lista_imgs_coords = sorted([
                    {'xref': img[0], 'y0': rect.y0} 
                    for img in imagenes_pagina 
                    for rect in pagina_fitz.get_image_rects(img[0])
                ], key=lambda x: x['y0'])

                filas = tabla[1:] if any('Num' in str(c) for c in tabla[0]) else tabla

                for idx, fila in enumerate(filas):
                    if len(fila) < 7: 
                        continue

                    doc_sucio = str(fila[1]) if fila[1] else ''
                    coincidencia = patron_limpieza.search(doc_sucio)
                    tipo_doc_raw = coincidencia.group(0) if coincidencia else ''

                    doc_limpio = patron_limpieza.sub('', doc_sucio)
                    doc_limpio = re.sub(r'\D', '', doc_limpio)

                    ruta_foto_guardada = ''
                    if idx < len(lista_imgs_coords) and doc_limpio:
                        img_data = lista_imgs_coords[idx]
                        pix = fitz.Pixmap(doc_fitz, img_data['xref'])
                        if pix.n >= 5: 
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        
                        # Construcción del path de destino con pathlib
                        path_foto = STATIC_IMAGES_DIR / f"{doc_limpio}.png"
                        pix.save(str(path_foto))
                        ruta_foto_guardada = str(path_foto)
                        pix = None

                    datos_completos.append({
                        'code': fila[0],
                        'persona': fila[2],
                        'doc_raw': tipo_doc_raw,
                        'id_card': doc_limpio, 
                        'contact': fila[3],
                        'ubigeo': fila[4],
                        'photo': ruta_foto_guardada,
                        'published_at': fila[6],
                    })

        df_scraper = pd.DataFrame(datos_completos)

        if not df_scraper.empty:
            split_persona = df_scraper['persona'].astype(str).str.split(',', n=1, expand=True)
            df_scraper['last_name'] = split_persona[0].str.strip()
            df_scraper['first_name'] = split_persona[1].str.strip() if 1 in split_persona.columns else ''

            mapa_docs = {
                'dni': 'DNI',
                'carnet extranjeria': 'CE',
                'permiso temporal de permanencia': 'PT',
                'pasaporte': 'PP'
            }
            card_type_map = {
                'DNI': 1,
                'CE': 2,
                'PT': 3,
                'PP': 4
            }
            df_scraper['card_type'] = (
                df_scraper['doc_raw']
                .astype(str)
                .str.strip()
                .str.lower()
                .map(mapa_docs)
                .map(card_type_map)
                .fillna(1)
                .astype(int)
            )

            columnas_finales = [
                'code',
                'first_name',
                'last_name',
                'card_type',
                'id_card',
                'ubigeo',
                'published_at',
                'contact',
                'photo'
            ]
            
            df_scraper = df_scraper[columnas_finales]

        return df_scraper

    def capture_state(self) -> tuple[str, str, str]:
        return (
            self.driver.title,
            self.driver.current_url,
            self.driver.find_element(By.TAG_NAME, "body").text,
        )