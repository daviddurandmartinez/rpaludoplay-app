import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import pymupdf as fitz
import pdfplumber
import time
import re
import glob
from config import (
    URL_EXTRANET, 
    TIEMPO_ESPERA, 
    XPATH_CLAVE_SOL, 
    XPATH_FORMULARIO,
    XPATH_BOTON_ENTRAR, 
    XPATH_REGISTRO_LUDOPATIA, 
    XPATH_REGISTRO_LUDOPATIA_ACEPTAR,
    XPATH_REGISTRO_LUDOPATIA_BUSCAR, 
    XPATH_REGISTRO_LUDOPATIA_EXPORTAR,
    INPUT_RUC, 
    INPUT_CLAVE, 
    INPUT_USUARIO,
    PATH_DOWNLOADS
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
    
    # NUEVO: Argumento clave para que Chromium imprima/guarde automáticamente sin mostrar la ventana de diálogo
    options.add_argument("--kiosk-printing")
    
    options.binary_location = "/snap/bin/chromium"   
    
    download_dir = PATH_DOWNLOADS
    os.makedirs(download_dir, exist_ok=True)
    
    import json
    app_state = {
        "recent_destinations": [{"id": "Save as PDF", "origin": "local", "account": ""}],
        "selected_destination_id": "Save as PDF",
        "version": 2
    }  
    
    prefs = {
        'download.default_directory': download_dir,
        'savefile.default_directory': download_dir, # Forzar carpeta de guardado de impresión
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

    def navegar(self) -> None:
        self.driver.get(URL_EXTRANET)

    def _esperar_y_clic(self, selector: tuple) -> None:
        boton = WebDriverWait(self.driver, TIEMPO_ESPERA).until(
            EC.element_to_be_clickable(selector)
        )
        boton.click()

    def clic_clave_sol(self) -> None:
        self._esperar_y_clic((By.XPATH, XPATH_CLAVE_SOL))
        print("¡Clic realizado con éxito en CLAVE SOL!")

    def clic_formulario(self) -> None:
        self._esperar_y_clic((By.XPATH, XPATH_FORMULARIO))

    def llenar_formulario(self, ruc: str, usuario: str, clave: str) -> None:
        WebDriverWait(self.driver, TIEMPO_ESPERA).until(
            EC.presence_of_element_located(INPUT_RUC)
        )
        self.driver.find_element(*INPUT_RUC).send_keys(ruc)
        self.driver.find_element(*INPUT_USUARIO).send_keys(usuario)
        self.driver.find_element(*INPUT_CLAVE).send_keys(clave)
        self._esperar_y_clic((By.XPATH, XPATH_BOTON_ENTRAR))
        print("Formulario CLAVE SOL rellenado con las credenciales del .env")

    def clic_registro_ludopatia(self) -> None:
        self._esperar_y_clic((By.XPATH, XPATH_REGISTRO_LUDOPATIA))
        print("Ingresa a registro de ludopatia")
        
        ventanas = self.driver.window_handles
        self.driver.switch_to.window(ventanas[-1])
        
        self._esperar_y_clic((By.XPATH, XPATH_REGISTRO_LUDOPATIA_ACEPTAR))
        print("ACEPTAR registros de ludopatia")
        
        self._esperar_y_clic((By.XPATH, XPATH_REGISTRO_LUDOPATIA_BUSCAR))
        print("BUSCAR registros de ludopatia")
        
        time.sleep(100) 
        
        self._esperar_y_clic((By.XPATH, XPATH_REGISTRO_LUDOPATIA_EXPORTAR))
        print("EXPORTAR registros de ludopatia - Guardando PDF automáticamente...")

        time.sleep(20) 

        # Gracias a --kiosk-printing, al hacer clic en exportar se guardará directo en la carpeta sin abrir el diálogo visual
        tiempo_maximo = 60
        tiempo_transcurrido = 0
        archivo_descargado = False
        
        while tiempo_transcurrido < tiempo_maximo:
            archivos = os.listdir(PATH_DOWNLOADS)
            if any(f.endswith('.pdf') for f in archivos) and not any(f.endswith('.crdownload') for f in archivos):
                archivo_descargado = True
                break
            time.sleep(1)
            tiempo_transcurrido += 1

        if archivo_descargado:
            print("¡El PDF se ha descargado y guardado correctamente en /home/ddurand/Downloads!")
        else:
            print("Advertencia: El tiempo de descarga expiró o el archivo sigue procesándose.")

    def extraer_tabla_y_fotos_pdf(self):  

        # 1. Buscar automáticamente el PDF más reciente en la carpeta de descargas
        dir_downloads = PATH_DOWNLOADS
        archivos_pdf = [os.path.join(dir_downloads, f) for f in os.listdir(dir_downloads) if f.lower().endswith('.pdf')]
        
        if not archivos_pdf:
            raise FileNotFoundError(f"No se encontró ningún archivo PDF en {dir_downloads}")
        
        # Selecciona el archivo PDF más reciente basándose en la fecha de modificación
        ruta_pdf = max(archivos_pdf, key=os.path.getmtime)
        print(f"Procesando archivo PDF: {ruta_pdf}")
        
        # 3. Carpeta de destino del proyecto
        carpeta_fotos = os.path.join("src", "static", "images")
        os.makedirs(carpeta_fotos, exist_ok=True)

        # Lista para limpiar documentos
        tipos_doc = ["Dni", "Permiso Temporal De Permanencia", "Carnet Extranjeria", "Pasaporte"]
        # Creamos un patrón regex: "(Dni|Pasaporte|...)" ignorando mayúsculas/minúsculas
        patron_limpieza = re.compile(f"({'|'.join(tipos_doc)})", re.IGNORECASE)

        datos_completos = []
        doc_fitz = fitz.open(ruta_pdf)

        with pdfplumber.open(ruta_pdf) as pdf:
            for num_pag, page in enumerate(pdf.pages):
                print(f"Procesando página {num_pag + 1} de {len(pdf.pages)}...")
                tabla = page.extract_table()
                if not tabla: continue

                pagina_fitz = doc_fitz[num_pag]
                imagenes_pagina = pagina_fitz.get_images(full=True)
                lista_imgs_coords = sorted([
                    {'xref': img[0], 'y0': rect.y0} 
                    for img in imagenes_pagina 
                    for rect in pagina_fitz.get_image_rects(img[0])
                ], key=lambda x: x['y0'])

                filas = tabla[1:] if any('Num' in str(c) for c in tabla[0]) else tabla

                for idx, fila in enumerate(filas):
                    if len(fila) < 7: continue

                    # 1. Limpieza del documento (fila[2]) -> pdf muestra como fila[1]
                    # 1. Limpieza agresiva:
                    doc_sucio = str(fila[1]) if fila[1] else ''
                    # Eliminamos tipos de documentos
                    doc_limpio = patron_limpieza.sub('', doc_sucio)
                    # FUERZA: Solo conservar números (quitamos cualquier espacio, salto de línea o letra que haya quedado)
                    doc_limpio = re.sub(r'\D', '', doc_limpio)

                    # 2. Guardar foto usando el doc_limpio como nombre
                    ruta_foto_guardada = ''
                    if idx < len(lista_imgs_coords) and doc_limpio:
                        img_data = lista_imgs_coords[idx]
                        pix = fitz.Pixmap(doc_fitz, img_data['xref'])
                        if pix.n >= 5: 
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        
                        nombre_archivo = f"{doc_limpio}.png"
                        ruta_foto_guardada = os.path.join(carpeta_fotos, nombre_archivo)
                        pix.save(ruta_foto_guardada)
                        # Liberar memoria explícitamente
                        pix = None

                    datos_completos.append({
                        'num_reg': fila[0],
                        'persona': fila[2],
                        'documento': doc_limpio, # Guardamos el limpio en el DF
                        'contacto': fila[3],
                        'ubigeo': fila[4],
                        'ruta_foto': ruta_foto_guardada,
                        'fec_publicacion': fila[6],
                    })

        df_scraper = pd.DataFrame(datos_completos)  
        return df_scraper

    def limpiar_carpetas(self) -> None:
        carpetas_a_limpiar = [
            "/home/ddurand/Downloads/",
            "src/static/images/"
        ]
        
        for carpeta in carpetas_a_limpiar:
            if os.path.exists(carpeta):
                # Obtiene todos los archivos dentro de la carpeta
                archivos = glob.glob(os.path.join(carpeta, "*"))
                
                for archivo in archivos:
                    if os.path.isfile(archivo):
                        try:
                            os.remove(archivo)
                            print(f"Eliminado: {archivo}")
                        except Exception as e:
                            print(f"No se pudo eliminar {archivo}: {e}")
            else:
                print(f"La carpeta no existe: {carpeta}")

    def capturar_estado(self) -> tuple[str, str, str]:
        return (
            self.driver.title,
            self.driver.current_url,
            self.driver.find_element(By.TAG_NAME, "body").text,
        )