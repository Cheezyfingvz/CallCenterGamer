"""
===============================================================================
PUNTO DE ENTRADA WSGI PARA PRODUCCIÓN (CallCenterGamer/wsgi.py)
===============================================================================
WSGI (Web Server Gateway Interface) es el estándar de Python para comunicar
servidores web de producción (como Gunicorn en Render) con aplicaciones Django.
El comando de arranque en Render invoca:
    gunicorn CallCenterGamer.wsgi:application
===============================================================================
"""

import os
from django.core.wsgi import get_wsgi_application

# Define qué archivo settings.py debe cargar Django al iniciar el proceso WSGI
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CallCenterGamer.settings')

# Objeto invocable (callable) que Gunicorn utiliza para procesar cada petición HTTP
application = get_wsgi_application()
