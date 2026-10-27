"""
===============================================================================
CONFIGURACIÓN DE LA APLICACIÓN ADMINISTRACION (administracion/apps.py)
===============================================================================
Propósito:
    Define los metadatos de registro de la app `administracion` dentro de
    `INSTALLED_APPS` en `CallCenterGamer/settings.py`.
===============================================================================
"""

from django.apps import AppConfig


class AdministracionConfig(AppConfig):
    """
    Clase de configuración de Django para el módulo de paneles administrativos y técnicos.
    """

    # Tipo de clave primaria automática por defecto (entero de 64 bits)
    default_auto_field = 'django.db.models.BigAutoField'
    # Nombre interno del paquete Python de la aplicación
    name = 'administracion'
