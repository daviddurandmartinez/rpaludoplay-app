from .controller import router as players_router

'''CAPA ROUTES (src/routes/) Esta capa recibe peticiones externas, aplica reglas de negocio y responde.'''
'''Qué hace: Exporta el router para que main.py pueda registrarlo en la app FastAPI.'''

__all__ = ["players_router"]