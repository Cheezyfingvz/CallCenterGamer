"""
===============================================================================
ENRUTADOR PRINCIPAL DE URLS (CallCenterGamer/urls.py)
===============================================================================
Este archivo mapea cada dirección URL solicitada por el navegador hacia su
correspondiente Vista (función o clase) en las aplicaciones `online` y
`administracion`.
===============================================================================
"""

from django.contrib import admin
from django.urls import path

# Importación de vistas del portal del cliente y autenticación (App `online`)
from online.views import (
    Index,
    PoliticaPrivacidad,
    Inicio,
    RegisterView,
    LoginView,
    ViewRespuestas,
    logout_view,
)

# Importación de vistas del panel de soporte y administración (App `administracion`)
from administracion.views import (
    IndexAdmin,
    BorrarPregunta,
    GestionUsuarios,
    EliminarUsuario,
    ModificarPregunta,
    AnalyticsIA,
)

urlpatterns = [
    # 1. Panel administrativo nativo de Django (restringido a usuarios con is_staff/admin=True)
    path('admin/', admin.site.urls),

    # 2. Portada pública (Landing Page) y Políticas de Privacidad de la plataforma
    path('', Index, name='index'),
    path('PoliticaPrivacidad/', PoliticaPrivacidad, name='politica_privacidad'),

    # 3. Rutas del Panel de Administración y Soporte Técnico
    path('Administracion/', IndexAdmin, name='administracion'),
    path('AnalyticsIA/', AnalyticsIA, name='analytics_ia'),
    path('GestionUsuarios/', GestionUsuarios, name='gestion_usuarios'),
    path('EliminarUsuario/<int:idUser>/', EliminarUsuario, name='eliminar_usuario'),
    path('ModificarPregunta/<int:idPregunta>/', ModificarPregunta, name='modificar_pregunta'),
    path('BorrarPregunta/<int:idUser>/<int:idPregunta>/', BorrarPregunta, name='borrar_pregunta'),

    # 4. Rutas de Autenticación de Usuarios (Login, Registro y Cierre de Sesión por POST)
    path('Login/', LoginView.as_view(), name='Login'),
    path('Register/', RegisterView.as_view(), name='Register'),
    path('Logout/', logout_view, name='Logout'),

    # 5. Rutas operativas del Cliente y Chat de Soporte
    # Panel personal del cliente (muestra su historial de tickets y buscador IA)
    path('Inicio/<int:id>/', Inicio, name='inicio'),
    # Hilo de conversación de un ticket específico (sin el parámetro decorativo idUser)
    path('Respuesta/<int:idPregunta>/', ViewRespuestas, name='respuestas'),
]
