from .model import Player

'''Qué hace: Un simple exportador de nombre. Permite hacer from entities.player import Player en lugar de from entities.player.model import Player. Facilita los imports.'''
__all__ = ["Player"]