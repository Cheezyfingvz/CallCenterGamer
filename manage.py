#!/usr/bin/env python
"""
===============================================================================
UTILIDAD DE LÍNEA DE COMANDOS DE DJANGO (manage.py)
===============================================================================
Permite ejecutar tareas administrativas del proyecto como:
- `python manage.py runserver` (servidor de desarrollo)
- `python manage.py makemigrations` / `migrate` (gestión de base de datos)
- `python manage.py test` (ejecución de pruebas automatizadas)
- `python manage.py seed_initial_data` (precarga de usuarios y tickets base)
===============================================================================
"""
import os
import sys


def main():
    """Función principal que inicializa el entorno de Django y procesa los argumentos CLI."""
    # Vincula por defecto el archivo CallCenterGamer/settings.py
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CallCenterGamer.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # Ejecuta el subcomando recibido por consola (ej. migrate, runserver, test)
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
