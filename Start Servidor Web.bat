@echo off
chcp 65001 >nul
title Servidor Web CallCenterGamer
cd /d "%~dp0"

:: ==============================================================================
:: SCRIPT DE CONFIGURACION E INICIO AUTOMATICO — CALLCENTERGAMER
:: - Si db.sqlite3 YA EXISTE: salta directamente a iniciar el servidor (runserver).
:: - Si db.sqlite3 NO EXISTE: instala requirements.txt, ejecuta manage.py check,
::   crea db.sqlite3 (migrate), carga los 3 usuarios por defecto (seed_initial_data)
::   y finalmente levanta el servidor web.
:: ==============================================================================

set "PYTHON_CMD=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"

if exist "db.sqlite3" goto :ARCHIVO_EXISTE

echo ===================================================================
echo [PRIMERA EJECUCION] db.sqlite3 no encontrado. Configurando proyecto...
echo ===================================================================

echo.
echo [1/4] Instalando dependencias desde requirements.txt...
"%PYTHON_CMD%" -m pip install -r requirements.txt
if errorlevel 1 goto :ERROR_INSTALACION

echo.
echo [2/4] Verificando integridad del proyecto con manage.py check...
"%PYTHON_CMD%" manage.py check
if errorlevel 1 goto :ERROR_CHECK

echo.
echo [3/4] Creando base de datos SQLite3 y aplicando migraciones...
"%PYTHON_CMD%" manage.py migrate
if errorlevel 1 goto :ERROR_MIGRATE

echo.
echo [4/4] Creando los 3 usuarios por defecto: usuario, tecnico, admin...
"%PYTHON_CMD%" manage.py seed_initial_data
if errorlevel 1 goto :ERROR_SEED

echo.
echo ===================================================================
echo [LISTO] Base de datos db.sqlite3 creada y poblada con exito:
echo   - Usuario Normal:        usuario  / usuario@gmail.com  / usuario123
echo   - Usuario Tecnico:       tecnico  / tecnico@gmail.com  / tecnico123
echo   - Tecnico Administrador: admin    / admin@gmail.com    / admin123
echo ===================================================================
goto :INICIAR_SERVIDOR

:ARCHIVO_EXISTE
echo ===================================================================
echo [OK] Base de datos db.sqlite3 detectada.
echo Omitiendo instalacion y migraciones previas.
echo ===================================================================

:INICIAR_SERVIDOR
echo.
echo Iniciando servidor Django en http://127.0.0.1:8000 ...
echo Presiona Ctrl+C para detener el servidor.
echo.
"%PYTHON_CMD%" manage.py runserver 127.0.0.1:8000
pause
exit /b 0

:ERROR_INSTALACION
echo.
echo [ERROR] Fallo la instalacion de requirements.txt.
pause
exit /b 1

:ERROR_CHECK
echo.
echo [ERROR] manage.py check detecto problemas en el proyecto.
pause
exit /b 1

:ERROR_MIGRATE
echo.
echo [ERROR] Fallo la creacion de tablas en db.sqlite3.
pause
exit /b 1

:ERROR_SEED
echo.
echo [ERROR] Fallo la carga inicial de usuarios por defecto.
pause
exit /b 1

:ERROR_INSTALACION
echo.
echo [ERROR] Fallo la instalacion de requirements.txt.
pause
exit /b 1

:ERROR_CHECK
echo.
echo [ERROR] manage.py check detecto problemas en el proyecto.
pause
exit /b 1

:ERROR_MIGRATE
echo.
echo [ERROR] Fallo la creacion de tablas en db.sqlite3.
pause
exit /b 1

:ERROR_SEED
echo.
echo [ERROR] Fallo la carga inicial de usuarios por defecto.
pause
exit /b 1

