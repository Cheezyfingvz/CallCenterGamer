#!/usr/bin/env bash
# ==============================================================================
# SCRIPT DE CONSTRUCCIÓN Y APROVISIONAMIENTO PARA RENDER (build.sh)
# ==============================================================================
# Este script se configura como "Build Command" (`./build.sh`) en el servicio
# Web de Render. Automatiza los 4 pasos necesarios para dejar la aplicación
# lista antes de que arranque el servidor WSGI Gunicorn:
#   1. Instala las librerías de Python definidas en requirements.txt.
#   2. Empaqueta y comprime los archivos estáticos (CSS/JS/Img) en staticfiles/.
#   3. Crea o actualiza las tablas de la base de datos SQLite3 (db.sqlite3).
#   4. Ejecuta el comando idempotente seed_initial_data para asegurar que
#      existan los usuarios de prueba (Admin, Técnico, Cliente) y tickets base.
# ==============================================================================

# Detiene inmediatamente la ejecución si cualquier comando devuelve un error
set -o errexit

echo "==> 1. Instalando dependencias desde requirements.txt..."
pip install -r requirements.txt

echo "==> 2. Recolectando archivos estáticos con WhiteNoise..."
python manage.py collectstatic --noinput

echo "==> 3. Aplicando migraciones sobre SQLite3 (db.sqlite3)..."
python manage.py migrate --noinput

echo "==> 4. Precargando usuarios y tickets iniciales (idempotente)..."
python manage.py seed_initial_data

echo "==> Build finalizado exitosamente."
