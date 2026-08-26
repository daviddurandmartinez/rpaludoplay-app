from dataclasses import dataclass

'''validar, limpiar y estructurar datos que provienen del scraping o de entradas del usuario. Ofrece dos utilidades principales: 
una función para garantizar que un RUC sea válido y una estructura para normalizar el contenido extraído de una página web.'''

def normalizar_ruc(ruc: str) -> str:
    ruc_limpio = ruc.strip()
    if not ruc_limpio.isdigit() or len(ruc_limpio) != 11:
        raise ValueError(f"El RUC debe tener 11 dígitos numéricos, se recibió: {ruc!r}")
    return ruc_limpio

@dataclass # El decorador @dataclass convierte esta clase en un contenedor de datos ligero.
class EstadoPagina:
    titulo: str
    url: str
    texto_visible: str

def parsear_estado_pagina(titulo: str, url: str, texto_visible: str) -> EstadoPagina:
    return EstadoPagina(
        titulo=titulo.strip(),
        url=url.strip(),
        texto_visible=texto_visible.strip(),
    )