"""
===============================================================================
PUNTO DE ENTRADA ASGI (CallCenterGamer/asgi.py)
===============================================================================
ASGI (Asynchronous Server Gateway Interface) permite ejecutar Django sobre
servidores asíncronos (como Uvicorn o Daphne) si en el futuro se integran
WebSockets o Django Channels.
===============================================================================
"""

import os
from django.core.asgi import get_asgi_application

# Apunta al módulo de configuración principal del proyecto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CallCenterGamer.settings')

# Instancia de aplicación ASGI expuesta para el servidor
application = get_asgi_application()
