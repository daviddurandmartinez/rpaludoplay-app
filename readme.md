## scraper.py

##

El script está diseñado usando buenas prácticas de programación (como el patrón de diseño Context Manager con **enter** y **exit**) para interactuar con la extranet del MINCETUR, específicamente para navegar, hacer clic en la opción de Clave SOL y rellenar un formulario de acceso.

1. Importación de librerías y constantes globales
   Librerías de Selenium: Se importan los módulos necesarios para controlar el navegador (webdriver), configurar opciones (Options), buscar elementos (By), y gestionar esperas inteligentes (WebDriverWait y expected_conditions como EC).

Constantes:

URL_EXTRANET: La dirección web de destino ([https://extranet.mincetur.gob.pe/extranet2/Home/Inicio](https://extranet.mincetur.gob.pe/extranet2/Home/Inicio)).

TIEMPO_ESPERA = 20: El tiempo máximo en segundos que Selenium esperará a que aparezcan los elementos en la página.

XPATH*\* y INPUT*\*: Localizadores estáticos (por XPATH, ID y NAME) que definen la ruta exacta de los botones y campos de texto dentro del HTML de la página.

2. Configuración de Opciones del Navegador (\_build_options)
   Esta función privada prepara la configuración con la que se abrirá Chromium:

--no-sandbox, --disable-dev-shm-usage, --disable-gpu: Argumentos técnicos indispensables para evitar que el navegador falle al ejecutarse en entornos Linux, servidores o contenedores.

--remote-debugging-port=9222: Facilita la depuración mediante DevTools.

binary_location = "/snap/bin/chromium": Le indica explícitamente a Selenium la ruta exacta donde está instalado Chromium en tu sistema (típicamente usado en distribuciones Linux que usan paquetes Snap).

headless: Si se activa (True), permite ejecutar el navegador en segundo plano sin mostrar una ventana gráfica.

3. Definición de la Clase Scraper
   Método de Inicialización y Gestión de Contexto (**init**, **enter**, **exit**)
   **init**: Recibe el parámetro headless y arranca la instancia del navegador ejecutando webdriver.Chrome() con las opciones previamente configuradas.

**enter** y **exit**: Convierten a la clase en un context manager (para usarse con la sentencia with). El método **exit** asegura que, al terminar la ejecución o ocurrir un error, el navegador se cierre automáticamente (self.driver.quit()) para no dejar procesos huérfanos en la memoria.

Método navegar
Toma la URL definida en URL_EXTRANET y le ordena al navegador (self.driver.get) que abra dicha página web.

Método auxiliar \_esperar_y_clic
Es una función interna de apoyo que utiliza esperas explícitas (WebDriverWait).

Espera hasta un máximo de 20 segundos a que el elemento indicado por selector esté interactuable (EC.element_to_be_clickable). Una vez que aparece y se puede presionar, ejecuta un .click() automáticamente.

Métodos de Interacción específicos
clic_clave_sol: Llama al método auxiliar pasando la ruta XPath (XPATH_CLAVE_SOL) del botón de Clave SOL y muestra un mensaje en consola al completarse.

clic_formulario: Hace clic en otra sección o botón auxiliar del formulario basándose en su XPath (XPATH_FORMULARIO).

llenar_formulario(ruc, usuario, clave):

Espera explícitamente a que el campo del RUC (INPUT_RUC) esté presente en el DOM (EC.presence_of_element_located).

Utiliza .send_keys() para escribir de forma simulada los valores de ruc, usuario y clave en sus respectivos campos de entrada.

Imprime una confirmación en la consola.

Método capturar_estado
Extrae y retorna una tupla con información clave de la página actual para verificar su estado:

El título de la pestaña (self.driver.title).

La URL actual en la que se encuentra el navegador (self.driver.current_url).

Todo el texto plano contenido dentro del cuerpo principal de la página (body), útil para auditorías o extraer datos.

## parser.py

A continuación, te explico detalladamente el funcionamiento de este segundo script, el cual está diseñado para gestionar la configuración de credenciales mediante variables de entorno, validar datos estrictos (como el RUC peruano) y estructurar los datos del estado de una página web utilizando clases y tipado avanzado en Python.

1. Importación de módulos principales
   from dataclasses import dataclass: Importa el decorador @dataclass, que sirve para crear clases especializadas principalmente en almacenar datos de forma limpia y automática (generando métodos como **init** y **repr** sin escribirlos manualmente).

from pydantic_settings import BaseSettings, SettingsConfigDict: Importa las herramientas de Pydantic Settings, una librería robusta utilizada para gestionar la configuración de aplicaciones mediante variables de entorno o archivos .env.

2. Gestión de Credenciales (class Credenciales)
   Esta clase hereda de BaseSettings y se encarga de leer, validar y cargar automáticamente los datos de acceso desde un archivo de entorno (.env).

model_config = SettingsConfigDict(...): Define la configuración interna que Pydantic utilizará:

env_file=".env": Indica que los valores deben buscarse en un archivo local llamado .env.

env_file_encoding="utf-8": Asegura que el archivo se lea con la codificación de caracteres UTF-8 (ideal para soportar tildes o caracteres especiales).

extra="ignore": Le indica a Pydantic que si el archivo .env contiene variables adicionales que no están declaradas en la clase, simplemente las ignore en lugar de arrojar un error.

Atributos de configuración:

mincetur_ruc: str = ""

mincetur_usuario: str = ""

mincetur_clave: str = ""

mincetur_headless: bool = False

Funcionamiento: Al instanciar esta clase (ej. creds = Credenciales()), Pydantic buscará automáticamente en el archivo .env variables que coincidan con estos nombres (o de forma insensible a mayúsculas/minúsculas según la configuración predeterminada), les asignará los tipos de datos correctos y dejará valores por defecto vacíos o falsos si no se encuentran.

3. Validación del RUC (normalizar_ruc)
   Esta función toma una cadena de texto que representa un RUC y valida que cumpla estrictamente con el formato requerido en Perú (11 dígitos numéricos).

ruc_limpio = ruc.strip(): Elimina cualquier espacio en blanco al inicio o al final que el usuario o el archivo de texto haya podido incluir por error.

Validación condicional (if not ruc_limpio.isdigit() or len(ruc_limpio) != 11):

ruc_limpio.isdigit(): Comprueba que todos los caracteres sean estrictamente números (del 0 al 9). Si contiene letras o símbolos, da falso.

len(ruc_limpio) != 11: Comprueba que la longitud total de la cadena sea exactamente de 11 caracteres (longitud oficial del RUC de la SUNAT en Perú).

Manejo de errores (raise ValueError(...)): Si alguna de las dos condiciones falla, la función interrumpe la ejecución lanzando un error descriptivo (ValueError), mostrando el valor exacto recibido (ruc!r) para facilitar la depuración.

return ruc_limpio: Si pasa todas las validaciones exitosamente, devuelve la cadena de texto limpia y lista para ser utilizada en el automatizador de Selenium.

4. Estructuración del Estado de la Página (@dataclass class EstadoPagina)
   Este bloque define una estructura de datos ligera y limpia mediante el decorador @dataclass.

Atributos:

titulo: str: Almacena el título de la pestaña del navegador.

url: str: Almacena la URL actual en la que se encuentra el navegador.

texto_visible: str: Almacena todo el texto visible extraído del cuerpo (body) de la página web.

Su único propósito es servir como un "contenedor ordenado" (un objeto tipo DTO - Data Transfer Object) para empaquetar la información devuelta por métodos de Selenium (como el método capturar_estado que viste en el script anterior).

5. Función de Parseo (parsear_estado_pagina)
   Esta función actúa como un transformador y limpiador de los datos crudos obtenidos del navegador antes de guardarlos.

Recibe tres cadenas de texto independientes (titulo, url, texto_visible).

return EstadoPagina(...): Crea y retorna una nueva instancia de la clase EstadoPagina aplicando .strip() a cada uno de los parámetros recibidos. Esto garantiza que cualquier salto de línea innecesario, espacio al principio o al final que venga del HTML del navegador sea limpiado de manera uniforme antes de ser procesado o guardado.

## main.py

A continuación, te explico detalladamente el funcionamiento de este script principal (main), el cual actúa como el orquestador que une las piezas de los scripts anteriores (el gestor de credenciales/parsers y el automatizador con Selenium).

1. Importaciones iniciales
   from parser import ...: Importa las clases y funciones de validación y estructuración de datos que vimos previamente (Credenciales, EstadoPagina, normalizar_ruc, parsear_estado_pagina).

from scraper import Scraper: Importa la clase principal de automatización con Selenium que controla el navegador Chromium.

2. Función Principal (def main() -> None)
   Paso A: Carga y Validación de Credenciales
   Python
   credenciales = Credenciales()

if not all([credenciales.mincetur_ruc, credenciales.mincetur_usuario, credenciales.mincetur_clave]):
raise SystemExit("Faltan credenciales en .env...")
Crea una instancia de Credenciales(), lo que lee automáticamente el archivo .env.

Verifica mediante all([...]) que el RUC, el usuario y la clave no estén vacíos. Si falta alguno de los tres, detiene la ejecución inmediatamente utilizando raise SystemExit y muestra un mensaje claro en la consola indicando qué falta.

Paso B: Normalización del RUC
Python
ruc = normalizar_ruc(credenciales.mincetur_ruc)
Pasa el RUC obtenido de las credenciales a la función normalizar_ruc. Esto asegura que tenga exactamente 11 dígitos numéricos y esté libre de espacios antes de proceder con la automatización.

Paso C: Ejecución del Scraper mediante Context Manager (with)
Python
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
estado: EstadoPagina = parsear_estado_pagina(\*scraper.capturar_estado())
except Exception as e:
print(f"Ocurrió un error durante la automatización: {e}")
return
Gracias al uso de la sentencia with, se garantiza que el navegador se abra al entrar y se cierre de forma segura (gracias al método **exit**) al terminar o si ocurre un fallo. Dentro del bloque se ejecuta la secuencia paso a paso:

scraper.navegar(): Abre la URL de la extranet del MINCETUR.

scraper.clic_clave_sol(): Hace clic en la opción de Clave SOL.

scraper.clic_formulario(): Selecciona o despliega el contenedor del formulario de acceso.

scraper.llenar_formulario(...): Introduce de forma automatizada las credenciales validadas (ruc, usuario y clave).

scraper.capturar_estado(): Extrae el título, la URL actual y el texto visible del navegador. El operador \* desempaqueta estos tres valores para pasarlos a la función parsear_estado_pagina, la cual retorna un objeto ordenado de tipo EstadoPagina.

except Exception as e: Si cualquier paso del proceso falla (por ejemplo, si un botón no carga o cambia el diseño de la web), captura el error, lo imprime en pantalla y finaliza el flujo ordenadamente sin dejar procesos colgados.

Paso D: Resultados Finales
Python
print(f"Título: {estado.titulo}")
print(f"URL: {estado.url}")
Una vez completada con éxito la automatización y el llenado del formulario, el script imprime en la consola el título de la página resultante y la URL en la que se encuentra el navegador como comprobación final del estado actual.

3. Punto de Entrada del Script
   Python
   if **name** == "**main**":
   main()
   Esta condición clásica de Python asegura que la función main() solo se ejecute cuando corras este archivo directamente desde la terminal (ej. python main.py), y no si es importado como módulo desde otro archivo de código.

## Diagrama Mental del Flujo Global

📁 .env (Credenciales)
│
▼

1.  📄 PARSER ──────► Lee, valida y normaliza datos (RUC, variables)
    │
    ▼
2.  🤖 SCRAPER ─────► Abre Selenium, navega e interactúa con la Web (MINCETUR)
    │
    ▼
3.  🚀 MAIN ────────► Orquesta todo el flujo secuencial y maneja el ciclo de vida

¿Cómo interactúan los 3 scripts paso a paso?

1. El Preparador (parser.py) — La Base de Datos y las Reglas
   Qué hace globalmente: Es el encargado de definir qué reglas deben cumplir los datos y de dónde se obtienen.

Su rol conjunto: Lee el archivo .env mediante Pydantic para extraer credenciales limpias. Además, incluye la función normalizar_ruc para asegurar que el RUC tenga obligatoriamente 11 dígitos antes de ser usado, evitando errores de tipeo o formato en la automatización. También provee las estructuras de datos (EstadoPagina) para empaquetar lo que devuelva el navegador.

2. El Operador de Navegación (scraper.py) — Las Manos y los Ojos
   Qué hace globalmente: Contiene toda la lógica técnica de Selenium. Sabe exactamente cómo abrir el navegador Chromium con opciones seguras (modo headless, sin sandbox, etc.), cómo esperar a que carguen los elementos web y cómo hacer clics o escribir texto.

Su rol conjunto: Funciona como un componente reutilizable y seguro gracias a un Context Manager (**enter** y **exit**), lo que garantiza que el navegador siempre se cerrará al terminar la tarea (o si ocurre un fallo), liberando memoria del sistema.

3. El Orquestador (main.py) — El Cerebro o Director de Orquesta
   Qué hace globalmente: Es el script principal que conecta y ejecuta secuencialmente a los otros dos. No hace web scraping por sí mismo ni lee archivos directamente; en su lugar, manda a llamar a parser y a scraper en el orden correcto.

Su rol conjunto en el flujo:

Fase de validación: Le pide al parser que cargue las credenciales y valide que el RUC sea correcto. Si falta algo, detiene el programa de inmediato.

Fase de ejecución: Inicia el Scraper utilizando las opciones configuradas.

Fase de automatización paso a paso: Le ordena navegar a la URL del MINCETUR, hacer clic en "Clave SOL", desplegar el formulario e introducir de forma automatizada las credenciales.

Fase de cierre y reporte: Captura el estado final de la página web, lo empaqueta de forma limpia y muestra los resultados en la consola.

Resumen de la sinergia
El parser.py alimenta de datos limpios y seguros al sistema.

El scraper.py ejecuta las acciones físicas virtuales en la página web del MINCETUR.

El main.py sincroniza el inicio, vigila que no haya errores durante el proceso y asegura que todo fluya de principio a fin de manera ordenada.

## archivo config

¿Por qué esta estructura es una buena práctica?
Validación estricta: Si falta alguna variable obligatoria en el archivo .env, Pydantic lanzará un error claro al iniciar la aplicación en lugar de fallar silenciosamente o a mitad de la ejecución.

Uso de SecretStr: La contraseña se maneja como un campo secreto, lo que evita que se imprima por error en los registros (logs) si alguien ejecuta un print(settings).

Tipado y Mantenibilidad: El uso de Field(..., alias="...") te permite mantener los nombres de variables en minúsculas/estándar dentro de tu clase de Python mientras se mapean correctamente con los nombres en mayúsculas tradicionales de tu archivo .env.

## archivo database_connector.py

Paso de parámetros limpio: Se añadió el parámetro database directamente a la función para que sea reutilizable si necesitas conectarte a distintas bases de datos usando las mismas credenciales de servidor.

Corrección de variables: Se reemplazó el uso de la variable errónea config_db por la importada y validada SQL_SERVER_CONFIG.

Manejo seguro de caracteres especiales: Se mantiene urllib.parse.quote_plus() para asegurar que las contraseñas que contengan símbolos especiales (@, #, /, etc.) no rompan la cadena de conexión URL de SQLAlchemy.

Resiliencia en el Pool: Se mantienen los parámetros de pool_pre_ping=True y pool_recycle, fundamentales en entornos corporativos o de automatización (RPA) para evitar desconexiones inesperadas por inactividad.
