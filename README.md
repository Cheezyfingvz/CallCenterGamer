# CallCenterGamer & SoundFlow

Sistema integral que combina una plataforma de soporte técnico y gestión de tickets para gaming (**CallCenterGamer**) con una segunda aplicación web de catálogo y biblioteca musical (**SoundFlow**), inspirada visualmente en plataformas de streaming modernas, con integración desacoplada a **MusicBrainz** y **Cover Art Archive**, y sincronización bidireccional con el sistema de soporte.

Deploy en Render: https://callcentergamer-5c2t.onrender.com

---

## 🎵 SoundFlow (Aplicación Musical Integrada)

**SoundFlow** es un módulo Django independiente (`musica/`) que agrega un ecosistema musical completo a la solución:

- **Catálogo musical**: Canciones, artistas, álbumes y playlists con metadatos reales o demostrativos.
- **Búsqueda híbrida**: Búsqueda prioritaria en base de datos local SQLite con consulta complementaria a MusicBrainz Web Service v2 (`/recording`, `/release-group`, `/artist`).
- **Portadas vía Cover Art Archive**: Obtención automatizada de miniaturas y portadas de lanzamientos mediante MBID, con imagen de respaldo local SVG para evitar enlaces rotos.
- **Degradación controlada (Offline-First)**: La plataforma opera de forma autónoma sin depender de conexión a internet o ante caídas (HTTP 429 / 5xx / Timeouts) de los servicios externos.
- **Reproductor visual interactivo**: Simulación completa (play/pause, barra de progreso, avance/retroceso, volumen) sin reproducción de audio real ni contenidos protegidos.
- **Biblioteca personal y Playlists**: Marcado de favoritos (canciones, álbumes, artistas, playlists), creación y edición de playlists con control de propietario.
- **Suscripciones y descargas simuladas**: Planes Free, Individual, Familiar y Estudiantes con simulación de upgrades y descargas offline registradas en SQLite.
- **Reseñas**: Sistema de valoraciones de 1 a 5 estrellas con comentarios para álbumes y playlists.
- **Recomendaciones explicables**: Motor local basado en favoritos, historial de escuchas y popularidad en la comunidad, sin requerir IA externa.
- **Integración funcional con Call Center**: Botón "Contactar soporte" en canciones, álbumes, artistas, playlists, suscripciones y descargas que precarga el formulario del Call Center asociando la entidad al ticket.

---

## 🎧 Arquitectura de la Integración

```text
CallCenterGamer/
├── CallCenterGamer/              # Configuración global del proyecto
│   ├── settings.py               # SQLite3, WhiteNoise, Crispy, LocMemCache, MusicBrainz
│   ├── urls.py                   # Enrutador principal (Call Center + /musica/)
│   └── brand_config.py           # Motor White-Label y catálogo de categorías
├── online/                       # App 1: Portal del Cliente y Helpdesk
│   ├── models.py                 # Usuario, Preguntas (+ contenido_musical FK), Respuesta
│   ├── views.py                  # Vistas del Call Center
│   └── forms.py                  # Formularios del cliente y de administración
├── administracion/               # App 2: Panel de Administración y Técnicos
│   ├── views.py                  # Dashboard, gestión de tickets y usuarios
│   └── templates/                # Plantillas con ficha musical para el agente
├── musica/                       # App 3: SoundFlow (Módulo Musical)
│   ├── models.py                 # Genero, Artista, Album, Cancion, Playlist,
│   │                             # ElementoPlaylist, Favorito, PlanSuscripcion,
│   │                             # Suscripcion, Descarga, Resena, ContenidoMusical
│   ├── services/
│   │   ├── base.py               # Interfaz abstracta BaseMusicProvider
│   │   ├── musicbrainz.py        # Cliente HTTP MusicBrainz con timeouts y caché
│   │   ├── cover_art.py          # Cliente Cover Art Archive con miniaturas
│   │   └── catalog.py            # Orquestador de catálogo híbrido y persistencia
│   ├── selectors.py              # Consultas optimizadas de biblioteca y planes
│   ├── forms.py                  # PlaylistForm, ResenaForm, TicketMusicaForm
│   ├── views.py                  # Controladores de SoundFlow
│   ├── urls.py                   # Rutas bajo el namespace 'musica'
│   ├── tests.py                  # 19 pruebas unitarias y de integración con mocks
│   ├── management/commands/
│   │   └── seed_musica.py        # Poblado inicial con datos ficticios demostrativos
│   ├── static/musica/
│   │   ├── css/soundflow.css     # Estética oscura moderna (carbón, verde acento)
│   │   ├── js/player.js          # Lógica interactiva del reproductor visual
│   │   └── img/cover_placeholder.svg # Portada genérica local de respaldo
│   └── templates/musica/         # 14 plantillas responsivas de SoundFlow
├── logs/                         # Archivo rotativo de auditoría
├── db.sqlite3                    # Base de datos relacional SQLite3 exclusiva
├── requirements.txt              # Dependencias (Django, requests, whitenoise, etc.)
└── README.md
```

---

## 🛠️ Stack Tecnológico

- **Python**: 3.12+
- **Framework Web**: Django 5.2+ / 6.x
- **Base de Datos**: SQLite3 nativo
- **Proveedor de Metadatos**: MusicBrainz Web Service v2 (backend)
- **Proveedor de Portadas**: Cover Art Archive
- **Estilos & UI**: CSS3 responsivo oscuro con acento verde (`#1DB954`) + Bootstrap 5 / Crispy Forms
- **Caché**: Django Cache Framework (`LocMemCache`)
- **Producción**: Gunicorn + WhiteNoise en Render

---

## 🌐 Configuración de MusicBrainz y Cover Art Archive

La integración opera **exclusivamente desde el backend de Django** (nunca llamadas cliente desde el navegador). Envía encabezados descriptivos, limita timeouts y utiliza el sistema de caché de Django (`LocMemCache` o Redis) para no saturar las APIs públicas.

Variables configurables en `.env`:

```env
# URL base de MusicBrainz WS/2
MUSICBRAINZ_BASE_URL=https://musicbrainz.org/ws/2

# User-Agent institucional (requerido por las políticas de MusicBrainz)
MUSICBRAINZ_USER_AGENT=SoundFlow/1.0 ( contacto@example.com )

# Timeout de peticiones HTTP en segundos (5 - 10s recomendado)
MUSICBRAINZ_TIMEOUT=8

# Tiempo de vida de la caché en segundos (86400s = 24 horas)
MUSICBRAINZ_CACHE_SECONDS=86400

# Timeout para consulta de portadas en Cover Art Archive
COVER_ART_TIMEOUT=6
```

### Funcionamiento sin conexión externa (Degradación Controlada)
1. Si MusicBrainz no responde, produce Timeout o devuelve error HTTP 429/5xx, el sistema no se cae: busca y entrega los resultados almacenados localmente en SQLite.
2. Si un release no tiene portada en Cover Art Archive, se muestra automáticamente el vector SVG local `cover_placeholder.svg`.
3. Todos los datos de demostración incluidos se marcan con el flag `es_demo=True`.

---

## 🎫 Integración de Tickets SoundFlow <-> Call Center

Desde cualquier vista de SoundFlow, los usuarios pueden reportar problemas con un solo clic:
1. El usuario hace clic en **"Contactar soporte"** en una canción, álbum, artista, playlist, suscripción o descarga.
2. SoundFlow genera o recupera una entidad `ContenidoMusical` local que guarda nombre, MBID, miniatura y enlace interno.
3. Se precarga el formulario con la categoría adecuada (`contenido_musical`, `reproductor`, `suscripciones`, `descargas`, etc.).
4. El ticket se almacena en la tabla original `online_preguntas` con su FK opcional `contenido_musical`.
5. El agente técnico visualiza en su panel la tarjeta del contenido musical con miniatura y el botón **"Abrir en SoundFlow"** para auditar el recurso.
6. Si la referencia musical se elimina en el futuro, el ticket se conserva íntegramente gracias a `on_delete=models.SET_NULL`.

---

## 🚀 Instalación y Puesta en Marcha

1. Clonar el repositorio y entrar a la carpeta:
```bash
git clone https://github.com/Cheezyfingvz/CallCenterGamer.git
cd CallCenterGamer
```

2. Crear y activar entorno virtual:
```bash
python -m venv .venv
# En Windows:
.\.venv\Scripts\Activate.ps1
# En Linux/macOS:
source .venv/bin/activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
```bash
cp .env.example .env
```

5. Aplicar migraciones:
```bash
python manage.py migrate
```

6. Cargar datos de demostración:
```bash
# Usuarios y tickets base del Call Center:
python manage.py seed_initial_data

# Catálogo musical completo de SoundFlow:
python manage.py seed_musica
```

7. Iniciar el servidor de desarrollo:
```bash
python manage.py runserver 127.0.0.1:8000
```

Rutas de acceso:
- **SoundFlow**: `http://127.0.0.1:8000/musica/`
- **Call Center Clientes**: `http://127.0.0.1:8000/Inicio/<id>/`
- **Panel Técnico / Admin**: `http://127.0.0.1:8000/Administracion/`
- **Admin Nativo Django**: `http://127.0.0.1:8000/admin/`

---

## 👥 Usuarios de Prueba

| Rol | Usuario | Email | Contraseña | Acceso |
| --- | --- | --- | --- | --- |
| Administrador | `admin` | `admin@gmail.com` | `admin123` | Call Center Admin + SoundFlow |
| Técnico | `tecnico` | `tecnico@gmail.com` | `tecnico123` | Call Center Helpdesk + SoundFlow |
| Cliente | `usuario` | `usuario@gmail.com` | `usuario123` | Portal Cliente + SoundFlow |

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con **47 tests unitarios y de integración** (28 del Call Center original + 19 de SoundFlow) ejecutables sin conexión externa mediante Mocks:

```bash
python manage.py test
```

Verificaciones ejecutadas:
- Control de acceso RBAC y prevención de IDOR.
- Fallback heurístico local de IA cuando no hay API Key de OpenAI.
- Consulta desacoplada a MusicBrainz (éxito, vacío, HTTP 429, 500, timeouts).
- Caché de resultados en memoria.
- Portadas en Cover Art Archive y placeholder de respaldo.
- CRUD de Playlists y control estricto de propiedad.
- Restricciones de unicidad de MBID y validación de reseñas 1-5 estrellas.
- Creación de tickets desde canciones/álbumes y preservación `SET_NULL`.
- Compatibilidad retroactiva de tickets clásicos sin referencia musical.

---

## ⚠️ Limitaciones Conocidas y Alcance Académico

- **Sin streaming real**: No se transmiten archivos MP3/AAC con derechos de autor; el reproductor es una simulación visual completa.
- **Sin videos musicales**: La plataforma se limita al catálogo y fichas de audio/álbum.
- **Sin pasarelas de pago reales**: Las suscripciones y renovaciones son demostraciones de base de datos SQLite.
- **Caché en memoria**: Por defecto utiliza `LocMemCache`. Para entornos distribuidos en clúster se sugiere Redis.

## 🚀 Despliegue en Render

Este proyecto debe desplegarse como **Web Service**, no como Static Site, porque
Django procesa autenticación, sesiones, formularios, tickets y el panel
administrativo en el servidor.

El archivo `render.yaml` ya configura el servicio Python. Para una demo:

1. En Render selecciona **New > Blueprint Instance**.
2. Conecta el repositorio y selecciona la rama `feat/soundflow-rebranding`.
3. Render ejecutará `bash build.sh`, que instala dependencias, recolecta
   estáticos, aplica migraciones y carga los seeds del Call Center y SoundFlow.
4. Define una clave segura en `DJANGO_SECRET_KEY` si no usas el valor generado
   automáticamente por el Blueprint.

La demo usa SQLite. Render tiene un filesystem efímero por defecto, por lo que
usuarios, tickets y cambios pueden perderse después de reinicios o nuevos
deploys. Para uso persistente se debe migrar la configuración a PostgreSQL.
