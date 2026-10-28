# CallCenterGamer

Sistema de soporte técnico y gestión de tickets para gaming, desarrollado con Django. El proyecto combina un portal para clientes, un panel administrativo para técnicos y administradores, soporte multimarcas/white-label, y un asistente IA con fallback local cuando no hay clave de OpenAI configurada.

## Descripción general

CallCenterGamer es una plataforma web de helpdesk orientada al rubro gaming y tecnología, pero preparada para adaptarse a otras empresas mediante variables de entorno del tipo `BRAND_*`.

Incluye:

- Portal de clientes para crear tickets de soporte
- Panel administrativo para atender, asignar y supervisar tickets
- Gestión de usuarios con roles diferenciados
- Soporte white-label con personalización visual y textos
- Motor IA híbrido con OpenAI y fallback local
- Base de datos SQLite3 lista para despliegue simple
- Preparación para Render con `gunicorn` y `whitenoise`

## Stack tecnológico

- Python 3.12+
- Django 5.2+
- SQLite3
- Bootstrap / crispy-forms
- OpenAI Python SDK (opcional)
- Gunicorn
- WhiteNoise
- django-environ

## Estructura del proyecto

```text
CallCenterGamer/
├── CallCenterGamer/              # Proyecto principal Django
│   ├── __init__.py
│   ├── settings.py               # Configuración general
│   ├── urls.py                  # Enrutamiento global
│   ├── brand_config.py          # Configuración white-label
│   ├── asgi.py
│   └── wsgi.py
├── online/                      # App del cliente y IA
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── ia_utils.py
│   ├── recomendaciones_ia.py
│   ├── templates/
│   ├── static/
│   └── management/
├── administracion/              # Panel administrativo
│   ├── views.py
│   ├── forms.py
│   ├── templates/
│   └── static/
├── logs/                        # Archivos de auditoría
├── db.sqlite3                    # Base de datos local
├── manage.py                    # Punto de entrada Django
├── requirements.txt             # Dependencias del proyecto
├── .env.example                 # Variables de entorno de ejemplo
├── build.sh                     # Script de despliegue
├── render.yaml                  # Configuración para Render
├── Start Servidor Web.bat       # Arranque rápido en Windows
├── PROJECT_DOSSIER_AI.md        # Documento técnico del proyecto
├── agent.md                     # Configuración del workflow del agente
└── README.md                    # Documentación del repositorio
```

## Características principales

### 1. Portal de clientes

- Registro e inicio de sesión
- Creación y seguimiento de tickets
- Visualización del historial de conversaciones
- Filtros por estado, prioridad y categoría
- Búsqueda de ayuda con soporte IA

### 2. Panel administrativo

- Gestión de usuarios
- Atención de tickets
- Cambio de estados y prioridades
- Asignación de técnicos
- Analytics y análisis IA
- Seguridad basada en permisos

### 3. White-label

El sistema puede cambiar branding mediante variables de entorno como:

- `BRAND_NAME`
- `BRAND_WELCOME_TITLE`
- `BRAND_SLOGAN`
- `BRAND_PRIMARY_COLOR`
- `BRAND_SECONDARY_COLOR`
- `BRAND_ACCENT_COLOR`
- `BRAND_AI_ROLE_PROMPT`
- `BRAND_CATEGORIES`

### 4. IA híbrida

- Si existe `OPENAI_API_KEY`, usa OpenAI para análisis y respuesta
- Si no existe la clave o falla la petición, usa un fallback local heurístico
- Reduce dependencia de servicios externos para mantener continuidad operativa

## Requisitos

- Python 3.12+
- pip
- Entorno virtual recomendado

## Configuración

1. Clona el repositorio:

```bash
git clone https://github.com/Cheezyfingvz/CallCenterGamer.git
cd CallCenterGamer
```

2. Crea un entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instala dependencias:

```bash
pip install -r requirements.txt
```

4. Configura variables de entorno:

Copia el archivo de ejemplo:

```bash
cp .env.example .env
```

Luego ajusta los valores de acuerdo a tu entorno. Los parámetros más importantes incluyen:

```env
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=tu-secret-key
OPENAI_API_KEY=
BRAND_NAME=CallCenterGamer
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Ejecución local

Realiza migraciones y levanta el proyecto:

```bash
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Si deseas cargar usuarios y tickets iniciales de demostración:

```bash
python manage.py seed_initial_data
```

## Usuarios de prueba

El proyecto incluye usuarios de ejemplo para pruebas rápidas:

| Rol | Usuario | Email | Contraseña |
| --- | --- | --- | --- |
| Administrador | `admin` | `admin@gmail.com` | `admin123` |
| Técnico | `tecnico` | `tecnico@gmail.com` | `tecnico123` |
| Cliente | `usuario` | `usuario@gmail.com` | `usuario123` |

## Pruebas

Ejecuta la suite de pruebas del proyecto:

```bash
python manage.py test
```

## Despliegue

Este proyecto está preparado para desplegarse en Render usando `gunicorn` y `whitenoise`.

Comandos de producción utilizados:

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py seed_initial_data
```

Start command recomendado:

```bash
gunicorn CallCenterGamer.wsgi:application
```

## Notas importantes

- La base de datos por defecto es SQLite3.
- El proyecto usa un modelo de usuario customizado para roles y permisos.
- El comportamiento del branding y del asistente puede adaptarse dinámicamente por variables de entorno.
- Si no configuras `OPENAI_API_KEY`, el sistema seguirá funcionando con lógica local para clasificación y recomendaciones.

## Licencia

No se ha especificado una licencia en este repositorio. Si necesitas usarlo en producción o redistribuirlo, revisa primero el titular de derechos del proyecto.

## Contacto / mantenimiento

Repositorio: https://github.com/Cheezyfingvz/CallCenterGamer

Proyecto desplegado: https://callcentergamer.onrender.com/

---

Este README fue generado para documentar la estructura, instalación y operación del proyecto CallCenterGamer.
