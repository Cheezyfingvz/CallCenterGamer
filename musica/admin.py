"""
===============================================================================
ADMINISTRACIÓN DJANGO DE SOUNDFLOW (musica/admin.py)
===============================================================================
"""
from django.contrib import admin
from musica.models import (
    Genero, Artista, Album, Cancion, Playlist, ElementoPlaylist,
    Favorito, PlanSuscripcion, Suscripcion, Descarga, Resena,
    HistorialEscucha, ContenidoMusical
)


@admin.register(Genero)
class GeneroAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}
    search_fields = ('nombre',)


@admin.register(Artista)
class ArtistaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'pais', 'mbid', 'es_demo', 'fecha_sync')
    search_fields = ('nombre', 'mbid', 'pais')
    list_filter = ('es_demo', 'generos')


class CancionInline(admin.TabularInline):
    model = Cancion
    extra = 1
    fields = ('numero_pista', 'titulo', 'duracion_seg', 'mbid')


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'artista', 'anio', 'mbid', 'es_demo')
    search_fields = ('titulo', 'artista__nombre', 'mbid')
    list_filter = ('es_demo', 'anio')
    inlines = [CancionInline]


@admin.register(Cancion)
class CancionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'artista', 'album', 'duracion_formateada', 'mbid', 'es_demo')
    search_fields = ('titulo', 'artista__nombre', 'album__titulo', 'mbid')
    list_filter = ('es_demo',)


class ElementoPlaylistInline(admin.TabularInline):
    model = ElementoPlaylist
    extra = 1


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'publica', 'es_demo', 'fecha_creacion')
    search_fields = ('nombre', 'usuario__usuario')
    list_filter = ('publica', 'es_demo')
    inlines = [ElementoPlaylistInline]


@admin.register(PlanSuscripcion)
class PlanSuscripcionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'precio_mensual', 'destacado')
    list_filter = ('destacado',)


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plan', 'estado', 'fecha_inicio')
    list_filter = ('estado', 'plan')


@admin.register(Descarga)
class DescargaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'cancion', 'fecha', 'estado', 'plataforma')
    list_filter = ('estado',)


@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'puntuacion', 'album', 'playlist', 'fecha')
    list_filter = ('puntuacion', 'fecha')


@admin.register(ContenidoMusical)
class ContenidoMusicalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'mbid', 'fecha_creacion')
    list_filter = ('tipo', 'fecha_creacion')
    search_fields = ('nombre', 'mbid')
