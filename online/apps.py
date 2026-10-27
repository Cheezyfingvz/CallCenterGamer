"""
===============================================================================
CONFIGURACIÓN DE LA APLICACIÓN `online` (online/apps.py)
===============================================================================
Define los metadatos de la aplicación principal `online` (portal del cliente,
modelos de datos, autenticación e Inteligencia Artificial).
===============================================================================
"""
from django.apps import AppConfig


class OnlineConfig(AppConfig):
    # Tipo de campo autoincremental por defecto para claves primarias (64 bits)
    default_auto_field = 'django.db.models.BigAutoField'
    # Nombre interno del paquete de la aplicación registrado en INSTALLED_APPS
    name = 'online'
