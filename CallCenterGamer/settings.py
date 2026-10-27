"""
===============================================================================
ARCHIVO DE CONFIGURACIÓN CENTRAL DE DJANGO (CallCenterGamer/settings.py)
===============================================================================
Este módulo define todos los parámetros globales del proyecto CallCenterGamer:
1. Rutas base del sistema de archivos (BASE_DIR).
2. Lectura segura de variables de entorno con `django-environ` (.env / Render).
3. Parámetros críticos de seguridad: SECRET_KEY, DEBUG, ALLOWED_HOSTS y CSRF.
4. Aplicaciones instaladas (INSTALLED_APPS) y capas intermedias (MIDDLEWARE).
5. Motor de plantillas HTML (TEMPLATES) y Context Processors globales.
6. Conexión exclusiva a base de datos relacional SQLite3 (db.sqlite3).
7. Servidores de archivos estáticos con WhiteNoise para producción en Render.
8. Modelo de usuario personalizado (AUTH_USER_MODEL = 'online.Usuario').
9. Configuración White-Label (Multi-Empresa) y Logging estructurado (Mejora 2).
===============================================================================
"""
import os
from pathlib import Path

import environ  # Librería django-environ (PPT 6) para leer variables de entorno tipadas
from django.core.exceptions import ImproperlyConfigured

# ==============================================================================
# 1. RUTAS BASE DEL PROYECTO
# ==============================================================================
# BASE_DIR apunta a la carpeta raíz donde se encuentra manage.py
BASE_DIR = Path(__file__).resolve().parent.parent
# Ruta opcional para plantillas globales a nivel de proyecto
TEMPLATES_DIRS = os.path.join(BASE_DIR, 'templates')

# ==============================================================================
# 2. LECTURA DE VARIABLES DE ENTORNO (.env local o Panel de Render)
# ==============================================================================
# Inicializa el lector de entorno. Si existe un archivo ".env" en la raíz del
# proyecto, carga sus variables automáticamente sin pisar las del sistema operativo.
env = environ.Env()
if (BASE_DIR / '.env').exists():
    environ.Env.read_env(str(BASE_DIR / '.env'))

# ==============================================================================
# 3. SEGURIDAD: DEBUG, SECRET_KEY, ALLOWED_HOSTS Y CSRF
# ==============================================================================
# DEBUG: Interruptor booleano que define si el proyecto corre en modo desarrollo
# (True: muestra trazas detalladas de error) o producción (False: oculta errores
# internos y activa políticas de seguridad estrictas).
DEBUG = env.bool('DJANGO_DEBUG', default=True)

# SECRET_KEY: Clave criptográfica usada por Django para firmar sesiones, cookies
# y tokens CSRF. En producción (DEBUG=False) es obligatorio definir una clave real.
_INSECURE_DEV_KEY = 'insecure-development-key-change-before-deploying'
SECRET_KEY = env.str('DJANGO_SECRET_KEY', default=_INSECURE_DEV_KEY)
if not DEBUG and SECRET_KEY == _INSECURE_DEV_KEY:
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY when DJANGO_DEBUG is disabled.')

# ALLOWED_HOSTS: Lista blanca de dominios/IPs autorizados para servir esta app.
# Protege contra ataques de falsificación de cabecera HTTP Host.
# Acepta tanto ALLOWED_HOSTS (estándar en Render) como DJANGO_ALLOWED_HOSTS.
ALLOWED_HOSTS = [
    host.strip()
    for host in env.str(
        'ALLOWED_HOSTS',
        default=env.str('DJANGO_ALLOWED_HOSTS', default='.onrender.com,localhost,127.0.0.1'),
    ).split(',')
    if host.strip()
]

# CSRF_TRUSTED_ORIGINS: Dominios HTTPS de confianza para peticiones POST (login,
# formularios, logout) cuando la app corre detrás del proxy inverso de Render.
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in env.str('CSRF_TRUSTED_ORIGINS', default='https://*.onrender.com').split(',')
    if origin.strip()
]

# ==============================================================================
# 4. APLICACIONES INSTALADAS (INSTALLED_APPS) Y MIDDLEWARE
# ==============================================================================
INSTALLED_APPS = [
    # --- Aplicaciones nativas de Django ---
    'django.contrib.admin',          # Panel administrativo nativo (/admin/)
    'django.contrib.auth',           # Sistema de autenticación y permisos
    'django.contrib.contenttypes',   # Registro de tipos de modelos
    'django.contrib.sessions',       # Gestión de sesiones de usuario en servidor
    'django.contrib.messages',       # Mensajes flash (éxito/error/alerta)
    'django.contrib.staticfiles',    # Gestión de archivos estáticos (CSS/JS/Img)
    # --- Extensiones externas (PPT 6) ---
    'crispy_forms',                  # Renderizado elegante de formularios Django
    'crispy_bootstrap5',             # Pack de estilos Bootstrap 5 para Crispy Forms
    # --- Aplicaciones propias del proyecto CallCenterGamer ---
    'administracion',                # App 2: Panel de soporte técnico, moderación y Analytics IA
    'online',                        # App 1: Portal de clientes, modelos de datos, auth y motor IA
]

# MIDDLEWARE: Capas de procesamiento secuencial por las que pasa cada petición
# HTTP entrante y cada respuesta HTTP saliente.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoiseMiddleware: Permite a Django servir sus propios archivos estáticos
    # comprimidos en producción (Render/Gunicorn) sin requerir Nginx externo.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # Bloquea peticiones POST sin token CSRF válido
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # Asocia request.user a la sesión
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Módulo principal de enrutamiento de URLs
ROOT_URLCONF = 'CallCenterGamer.urls'

# ==============================================================================
# 5. MOTOR DE PLANTILLAS (TEMPLATES) Y CONTEXT PROCESSORS
# ==============================================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIRS],  # Carpetas adicionales de templates
        'APP_DIRS': True,          # Busca automáticamente dentro de <app>/templates/
        'OPTIONS': {
            # Los context_processors inyectan variables globales en todos los templates
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Context processor propio (Fase 5): inyecta {{ brand }} en todas las vistas
                'online.context_processors.brand_context',
            ],
        },
    },
]

# Punto de entrada WSGI para servidores de producción como Gunicorn
WSGI_APPLICATION = 'CallCenterGamer.wsgi.application'

# ==============================================================================
# 6. BASE DE DATOS (SQLITE3 NATIVO EXCLUSIVO)
# ==============================================================================
# Se utiliza exclusivamente el motor SQLite3 nativo de Python/Django apuntando
# al archivo local `db.sqlite3`. No requiere servidor MySQL ni compilación C.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ==============================================================================
# 7. VALIDACIÓN DE CONTRASEÑAS E INTERNACIONALIZACIÓN
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'es-ES'  # Idioma predeterminado: Español
TIME_ZONE = 'UTC'        # Zona horaria base interna
USE_I18N = True          # Activa traducción de textos de Django
USE_TZ = True            # Usa fechas conscientes de zona horaria (timezone-aware)

# ==============================================================================
# 8. ARCHIVOS ESTÁTICOS (CSS, JAVASCRIPT, IMÁGENES) Y WHITENOISE
# ==============================================================================
# Prefijo URL público para archivos estáticos
STATIC_URL = '/static/'
# Carpeta donde `python manage.py collectstatic` reúne todos los estáticos para Render
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Crea la carpeta si no existe para evitar advertencias de WhiteNoise en desarrollo/tests
STATIC_ROOT.mkdir(exist_ok=True)

# Configuración moderna de almacenamiento (Django 4.2+ / 5.x / 6.x):
# Usa WhiteNoise con compresión automática Gzip/Brotli para servir estáticos rápido.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# Tipo de clave primaria automática por defecto para nuevos modelos
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# 9. AUTENTICACIÓN, MODELO DE USUARIO PERSONALIZADO Y SESIONES
# ==============================================================================
# AUTH_USER_MODEL reemplaza el modelo User por defecto de Django por nuestro
# modelo personalizado `Usuario` definido en `online/models.py` (con RUT, roles, etc.).
AUTH_USER_MODEL = 'online.Usuario'

# Rutas de redirección del flujo de autenticación
LOGIN_URL = 'Login'           # A dónde enviar usuarios no autenticados (@login_required)
LOGIN_REDIRECT_URL = '/'      # Ruta tras iniciar sesión si no hay parámetro ?next=
LOGOUT_REDIRECT_URL = 'Login' # Ruta tras cerrar sesión

# En producción (DEBUG=False), las cookies de sesión y CSRF solo viajan por HTTPS
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Indica a Django que confíe en el encabezado HTTPS enviado por el balanceador de Render
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Configuración de Crispy Forms con Bootstrap 5
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ==============================================================================
# 10. PARAMETRIZACIÓN WHITE-LABEL (MULTI-EMPRESA) E INTELIGENCIA ARTIFICIAL
# ==============================================================================
from CallCenterGamer.brand_config import load_brand_config_from_env

# Diccionario maestro con nombre de empresa, colores, ícono y categorías de tickets
BRAND_CONFIG = load_brand_config_from_env()
TICKET_CATEGORIES = BRAND_CONFIG['TICKET_CATEGORIES']

# API Key de OpenAI (opcional). Si está vacía, `AsistenteIA` usa el motor heurístico local.
OPENAI_API_KEY = env.str('OPENAI_API_KEY', default='')

# ==============================================================================
# 11. LOGGING ESTRUCTURADO DEL SISTEMA (MEJORA 2 - EVALUACIÓN N° 3)
# ==============================================================================
# Asegura que exista la carpeta `logs/` antes de inicializar el FileHandler
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Configuración del sistema de registro de eventos (reemplaza el uso de print())
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    # Formatos de texto para cada línea de log
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname}: {message}',
            'style': '{',
        },
    },
    # Destinos de salida: consola (para Render) y archivo rotativo en disco
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(LOGS_DIR / 'callcenter.log'),
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    # Loggers específicos por módulo/aplicación
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'online': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'administracion': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
