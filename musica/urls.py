"""
===============================================================================
ENRUTADOR DE SOUNDFLOW (musica/urls.py)
===============================================================================
Mapea todas las rutas web para la aplicación musical SoundFlow:
- Catálogo y búsqueda.
- Vistas de detalle de entidades musicales.
- Playlists y favoritos.
- Suscripción y descargas.
- Creación de tickets vinculados al Call Center.
===============================================================================
"""
from django.urls import path
from musica import views

app_name = 'musica'

urlpatterns = [
    # Portada y Catálogo
    path('', views.inicio, name='inicio'),
    path('catalogo/', views.catalogo, name='catalogo'),
    path('buscar/', views.buscar, name='buscar'),

    # Fichas de detalle
    path('artista/<int:pk>/', views.artista_detail, name='artista_detail'),
    path('album/<int:pk>/', views.album_detail, name='album_detail'),
    path('cancion/<int:pk>/', views.cancion_detail, name='cancion_detail'),
    path('sincronizar/<str:tipo>/<str:mbid>/', views.sincronizar_externo, name='sincronizar_externo'),

    # Reseñas
    path('resena/agregar/<str:tipo>/<int:pk>/', views.agregar_resena, name='agregar_resena'),
    path('resena/eliminar/<int:pk>/', views.eliminar_resena, name='eliminar_resena'),

    # Playlists
    path('playlists/', views.playlist_list, name='playlist_list'),
    path('playlist/<int:pk>/', views.playlist_detail, name='playlist_detail'),
    path('playlist/nueva/', views.playlist_create, name='playlist_create'),
    path('playlist/<int:pk>/editar/', views.playlist_edit, name='playlist_edit'),
    path('playlist/<int:pk>/eliminar/', views.playlist_delete, name='playlist_delete'),
    path('playlist/<int:pk>/agregar-cancion/', views.playlist_add_cancion, name='playlist_add_cancion'),
    path('playlist/<int:pk>/quitar-cancion/<int:cancion_id>/', views.playlist_remove_cancion, name='playlist_remove_cancion'),

    # Biblioteca y Favoritos
    path('biblioteca/', views.biblioteca, name='biblioteca'),
    path('favorito/toggle/<str:tipo>/<int:pk>/', views.toggle_favorito, name='toggle_favorito'),

    # Suscripciones y Descargas
    path('suscripcion/', views.suscripcion_view, name='suscripcion'),
    path('descarga/<int:cancion_id>/', views.descarga_simulada, name='descarga_simulada'),

    # Integración con Tickets de Soporte
    path('ticket/<str:tipo>/<int:objeto_id>/', views.ticket_desde_musica, name='ticket_desde_musica'),
    path('mis-tickets/', views.mis_tickets, name='mis_tickets'),
]
