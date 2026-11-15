"""
===============================================================================
SELECTORES DE DATOS DE SOUNDFLOW (musica/selectors.py)
===============================================================================
Consultas optimizadas para la biblioteca de usuario, listas, descargas
y suscripciones activas.
===============================================================================
"""
from typing import Dict, Any
from django.db.models import Prefetch
from musica.models import (
    Cancion, Album, Artista, Playlist, Favorito,
    Suscripcion, PlanSuscripcion, Descarga, ElementoPlaylist
)


def get_biblioteca_usuario(usuario) -> Dict[str, Any]:
    """Retorna las listas, favoritos y descargas del usuario autenticado."""
    if not usuario or not usuario.is_authenticated:
        return {'playlists': [], 'canciones_fav': [], 'albums_fav': [], 'artistas_fav': []}

    playlists = Playlist.objects.filter(usuario=usuario).order_by('-fecha_creacion')
    canciones_fav = (
        Cancion.objects.filter(favoritos__usuario=usuario, favoritos__tipo=Favorito.TIPO_CANCION)
        .select_related('artista', 'album')
        .order_by('-favoritos__fecha')
    )
    albums_fav = (
        Album.objects.filter(favoritos__usuario=usuario, favoritos__tipo=Favorito.TIPO_ALBUM)
        .select_related('artista')
        .order_by('-favoritos__fecha')
    )
    artistas_fav = (
        Artista.objects.filter(favoritos__usuario=usuario, favoritos__tipo=Favorito.TIPO_ARTISTA)
        .order_by('-favoritos__fecha')
    )

    return {
        'playlists': playlists,
        'canciones_fav': canciones_fav,
        'albums_fav': albums_fav,
        'artistas_fav': artistas_fav,
    }


def get_or_create_suscripcion_usuario(usuario) -> Suscripcion:
    """Obtiene o crea una suscripción en plan gratuito para el usuario."""
    plan_gratuito, _ = PlanSuscripcion.objects.get_or_create(
        codigo=PlanSuscripcion.CODIGO_GRATUITO,
        defaults={
            'nombre': 'SoundFlow Free',
            'precio_mensual': 0.00,
            'descripcion': 'Acceso al catálogo con publicidad simulada y calidad estándar.',
            'beneficios': 'Reproducción aleatoria\nCalidad estándar\nSoporte por tickets',
        }
    )
    suscripcion, _ = Suscripcion.objects.get_or_create(
        usuario=usuario,
        defaults={'plan': plan_gratuito, 'estado': Suscripcion.ESTADO_ACTIVA}
    )
    return suscripcion
