"""
===============================================================================
VISTAS DE SOUNDFLOW (musica/views.py)
===============================================================================
Controladores para toda la experiencia de usuario en SoundFlow:
- Inicio, Catálogo, Búsqueda híbrida.
- Fichas de detalle: Canción, Álbum, Artista, Playlist.
- Gestión de Biblioteca: Favoritos, Playlists propias.
- Suscripciones y descargas simuladas.
- Integración bidireccional con el sistema de tickets del Call Center.
===============================================================================
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from django.db import transaction

from musica.models import (
    Genero, Artista, Album, Cancion, Playlist, ElementoPlaylist,
    Favorito, PlanSuscripcion, Suscripcion, Descarga, Resena,
    HistorialEscucha, ContenidoMusical
)
from musica.forms import PlaylistForm, ResenaForm, TicketMusicaForm
from musica.services.catalog import CatalogService
from musica.selectors import get_biblioteca_usuario, get_or_create_suscripcion_usuario
from online.models import Preguntas

logger = logging.getLogger(__name__)


# =============================================================================
# 1. PORTADA E INICIO DE SOUNDFLOW
# =============================================================================

def inicio(request):
    """Página principal de SoundFlow con álbumes, playlists y recomendaciones."""
    catalog = CatalogService()

    albums_destacados = Album.objects.select_related('artista').all().order_by('-id')[:8]
    artistas_populares = Artista.objects.all().order_by('-id')[:6]
    playlists_destacadas = Playlist.objects.filter(publica=True).select_related('usuario')[:6]

    # Recomendaciones explicables
    recomendaciones = catalog.obtener_recomendaciones(request.user if request.user.is_authenticated else None, limit=6)

    # Historial reciente
    historial = []
    if request.user.is_authenticated:
        historial = HistorialEscucha.objects.filter(usuario=request.user).select_related('cancion__artista', 'cancion__album')[:6]

    return render(request, 'musica/inicio.html', {
        'albums_destacados': albums_destacados,
        'artistas_populares': artistas_populares,
        'playlists_destacadas': playlists_destacadas,
        'recomendaciones': recomendaciones,
        'historial': historial,
    })


# =============================================================================
# 2. CATÁLOGO Y BÚSQUEDA HÍBRIDA
# =============================================================================

def catalogo(request):
    """Catálogo general de música local paginado."""
    genero_slug = request.GET.get('genero', '').strip()
    qs_canciones = Cancion.objects.select_related('artista', 'album').all().order_by('titulo')

    if genero_slug:
        qs_canciones = qs_canciones.filter(album__generos__slug=genero_slug)

    paginator = Paginator(qs_canciones, 16)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    generos = Genero.objects.all()

    return render(request, 'musica/catalogo.html', {
        'page_obj': page_obj,
        'generos': generos,
        'genero_seleccionado': genero_slug,
    })


def buscar(request):
    """
    Búsqueda combinada: base de datos local SQLite y metadatos externos de MusicBrainz.
    Muestra los orígenes diferenciados con degradación controlada.
    """
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', 'todos')
    page = int(request.GET.get('page', 1))

    catalog = CatalogService()
    resultados = catalog.search(query=query, tipo=tipo, page=page, limit=12)

    return render(request, 'musica/buscar.html', {
        'resultados': resultados,
        'query': query,
        'tipo': tipo,
    })


# =============================================================================
# 3. DETALLE DE ENTIDADES (ARTISTA, ÁLBUM, CANCIÓN)
# =============================================================================

def artista_detail(request, pk):
    """Ficha de artista con sus canciones y álbumes locales."""
    artista = get_object_or_404(Artista, pk=pk)
    canciones = artista.canciones.select_related('album').all()[:15]
    albums = artista.albums.all()

    es_favorito = False
    if request.user.is_authenticated:
        es_favorito = Favorito.objects.filter(usuario=request.user, tipo=Favorito.TIPO_ARTISTA, artista=artista).exists()

    return render(request, 'musica/artista_detail.html', {
        'artista': artista,
        'canciones': canciones,
        'albums': albums,
        'es_favorito': es_favorito,
    })


def album_detail(request, pk):
    """Ficha del álbum con lista de temas y módulo de reseñas."""
    album = get_object_or_404(Album.objects.select_related('artista'), pk=pk)
    canciones = album.canciones.all().order_by('numero_pista', 'titulo')
    resenas = album.resenas.select_related('usuario').order_by('-fecha')

    es_favorito = False
    mi_resena = None
    form_resena = None

    if request.user.is_authenticated:
        es_favorito = Favorito.objects.filter(usuario=request.user, tipo=Favorito.TIPO_ALBUM, album=album).exists()
        mi_resena = album.resenas.filter(usuario=request.user).first()
        if not mi_resena:
            form_resena = ResenaForm()

    return render(request, 'musica/album_detail.html', {
        'album': album,
        'canciones': canciones,
        'resenas': resenas,
        'es_favorito': es_favorito,
        'mi_resena': mi_resena,
        'form_resena': form_resena,
    })


def cancion_detail(request, pk):
    """Ficha de detalle de una canción."""
    cancion = get_object_or_404(Cancion.objects.select_related('artista', 'album'), pk=pk)

    es_favorito = False
    mis_playlists = []
    if request.user.is_authenticated:
        es_favorito = Favorito.objects.filter(usuario=request.user, tipo=Favorito.TIPO_CANCION, cancion=cancion).exists()
        mis_playlists = Playlist.objects.filter(usuario=request.user)
        # Registrar escucha simulada en historial
        HistorialEscucha.objects.create(usuario=request.user, cancion=cancion)

    return render(request, 'musica/cancion_detail.html', {
        'cancion': cancion,
        'es_favorito': es_favorito,
        'mis_playlists': mis_playlists,
    })


def sincronizar_externo(request, tipo, mbid):
    """
    Controlador para persistir un elemento encontrado en MusicBrainz y abrir su ficha local.
    """
    catalog = CatalogService()
    if tipo == 'cancion':
        cancion = catalog.sincronizar_o_obtener_cancion(mbid)
        if cancion:
            messages.success(request, f"La canción '{cancion.titulo}' fue sincronizada con éxito.")
            return redirect('musica:cancion_detail', pk=cancion.pk)
    elif tipo == 'album':
        album = catalog.sincronizar_o_obtener_album(mbid)
        if album:
            messages.success(request, f"El álbum '{album.titulo}' fue sincronizado con éxito.")
            return redirect('musica:album_detail', pk=album.pk)
    elif tipo == 'artista':
        artista = catalog.sincronizar_o_obtener_artista(mbid)
        if artista:
            messages.success(request, f"El artista '{artista.nombre}' fue sincronizado con éxito.")
            return redirect('musica:artista_detail', pk=artista.pk)

    messages.error(request, "No se pudo sincronizar el recurso con MusicBrainz.")
    return redirect('musica:buscar')


# =============================================================================
# 4. GESTIÓN DE RESEÑAS
# =============================================================================

@login_required
@require_POST
def agregar_resena(request, tipo, pk):
    """Permite al usuario dejar una valoración (1 a 5 estrellas)."""
    form = ResenaForm(request.POST)
    if form.is_valid():
        resena = form.save(commit=False)
        resena.usuario = request.user
        if tipo == 'album':
            album = get_object_or_404(Album, pk=pk)
            # Evitar reseñas duplicadas del mismo usuario
            Resena.objects.filter(usuario=request.user, album=album).delete()
            resena.album = album
            resena.save()
            messages.success(request, "Tu reseña ha sido publicada.")
            return redirect('musica:album_detail', pk=pk)
        elif tipo == 'playlist':
            playlist = get_object_or_404(Playlist, pk=pk)
            Resena.objects.filter(usuario=request.user, playlist=playlist).delete()
            resena.playlist = playlist
            resena.save()
            messages.success(request, "Tu reseña ha sido publicada.")
            return redirect('musica:playlist_detail', pk=pk)

    messages.error(request, "Error al guardar la reseña. Verifica la puntuación.")
    if tipo == 'album':
        return redirect('musica:album_detail', pk=pk)
    return redirect('musica:playlist_detail', pk=pk)


@login_required
@require_POST
def eliminar_resena(request, pk):
    """Permite al usuario eliminar su propia reseña."""
    resena = get_object_or_404(Resena, pk=pk, usuario=request.user)
    album_id = resena.album_id
    playlist_id = resena.playlist_id
    resena.delete()
    messages.success(request, "Tu reseña ha sido eliminada.")
    if album_id:
        return redirect('musica:album_detail', pk=album_id)
    if playlist_id:
        return redirect('musica:playlist_detail', pk=playlist_id)
    return redirect('musica:inicio')


# =============================================================================
# 5. GESTIÓN DE PLAYLISTS
# =============================================================================

@login_required
def playlist_list(request):
    """Listado de playlists del usuario y públicas."""
    mis_playlists = Playlist.objects.filter(usuario=request.user).order_by('-fecha_creacion')
    playlists_comunidad = Playlist.objects.filter(publica=True).exclude(usuario=request.user)[:10]

    return render(request, 'musica/playlist_list.html', {
        'mis_playlists': mis_playlists,
        'playlists_comunidad': playlists_comunidad,
    })


def playlist_detail(request, pk):
    """Detalle de una playlist, canciones y opciones de reproducción."""
    playlist = get_object_or_404(Playlist.objects.select_related('usuario'), pk=pk)

    # Si es privada, solo el dueño o administradores pueden verla
    if not playlist.publica and request.user != playlist.usuario and not (request.user.is_authenticated and (request.user.admin or request.user.tecnico)):
        messages.error(request, "Esta playlist es privada.")
        return redirect('musica:playlist_list')

    elementos = playlist.elementos.select_related('cancion__artista', 'cancion__album').order_by('orden', 'agregado')
    resenas = playlist.resenas.select_related('usuario').all()

    es_favorito = False
    if request.user.is_authenticated:
        es_favorito = Favorito.objects.filter(usuario=request.user, tipo=Favorito.TIPO_PLAYLIST, playlist=playlist).exists()

    form_resena = ResenaForm() if request.user.is_authenticated else None

    return render(request, 'musica/playlist_detail.html', {
        'playlist': playlist,
        'elementos': elementos,
        'resenas': resenas,
        'es_favorito': es_favorito,
        'form_resena': form_resena,
        'es_duenio': request.user == playlist.usuario,
    })


@login_required
def playlist_create(request):
    """Crea una nueva playlist para el usuario autenticado."""
    if request.method == 'POST':
        form = PlaylistForm(request.POST)
        if form.is_valid():
            playlist = form.save(commit=False)
            playlist.usuario = request.user
            playlist.save()
            messages.success(request, f"Playlist '{playlist.nombre}' creada.")
            return redirect('musica:playlist_detail', pk=playlist.pk)
    else:
        form = PlaylistForm()

    return render(request, 'musica/playlist_form.html', {
        'form': form,
        'titulo': 'Crear nueva Playlist',
    })


@login_required
def playlist_edit(request, pk):
    """Edición de datos de una playlist existente (solo propietario)."""
    playlist = get_object_or_404(Playlist, pk=pk, usuario=request.user)
    if request.method == 'POST':
        form = PlaylistForm(request.POST, instance=playlist)
        if form.is_valid():
            form.save()
            messages.success(request, "Playlist actualizada correctamente.")
            return redirect('musica:playlist_detail', pk=playlist.pk)
    else:
        form = PlaylistForm(instance=playlist)

    return render(request, 'musica/playlist_form.html', {
        'form': form,
        'titulo': 'Editar Playlist',
        'playlist': playlist,
    })


@login_required
@require_POST
def playlist_delete(request, pk):
    """Elimina una playlist (solo propietario)."""
    playlist = get_object_or_404(Playlist, pk=pk, usuario=request.user)
    nombre = playlist.nombre
    playlist.delete()
    messages.success(request, f"Playlist '{nombre}' eliminada.")
    return redirect('musica:playlist_list')


@login_required
@require_POST
def playlist_add_cancion(request, pk):
    """Añade una canción a la playlist."""
    playlist = get_object_or_404(Playlist, pk=pk, usuario=request.user)
    cancion_id = request.POST.get('cancion_id')
    cancion = get_object_or_404(Cancion, pk=cancion_id)

    max_orden = playlist.elementos.count()
    ElementoPlaylist.objects.get_or_create(
        playlist=playlist,
        cancion=cancion,
        defaults={'orden': max_orden + 1}
    )
    messages.success(request, f"'{cancion.titulo}' agregada a {playlist.nombre}.")
    referer = request.META.get('HTTP_REFERER')
    return redirect(referer if referer else reverse('musica:playlist_detail', kwargs={'pk': pk}))


@login_required
@require_POST
def playlist_remove_cancion(request, pk, cancion_id):
    """Quita una canción de la playlist."""
    playlist = get_object_or_404(Playlist, pk=pk, usuario=request.user)
    ElementoPlaylist.objects.filter(playlist=playlist, cancion_id=cancion_id).delete()
    messages.success(request, "Canción quitada de la playlist.")
    return redirect('musica:playlist_detail', pk=pk)


# =============================================================================
# 6. FAVORITOS Y BIBLIOTECA PERSONAL
# =============================================================================

@login_required
@require_POST
def toggle_favorito(request, tipo, pk):
    """Marca o desmarca un elemento como favorito."""
    filtros = {'usuario': request.user, 'tipo': tipo}
    objeto = None

    if tipo == Favorito.TIPO_CANCION:
        objeto = get_object_or_404(Cancion, pk=pk)
        filtros['cancion'] = objeto
    elif tipo == Favorito.TIPO_ALBUM:
        objeto = get_object_or_404(Album, pk=pk)
        filtros['album'] = objeto
    elif tipo == Favorito.TIPO_ARTISTA:
        objeto = get_object_or_404(Artista, pk=pk)
        filtros['artista'] = objeto
    elif tipo == Favorito.TIPO_PLAYLIST:
        objeto = get_object_or_404(Playlist, pk=pk)
        filtros['playlist'] = objeto

    fav = Favorito.objects.filter(**filtros).first()
    if fav:
        fav.delete()
        messages.info(request, "Eliminado de tus favoritos.")
    else:
        Favorito.objects.create(**filtros)
        messages.success(request, "Agregado a tus favoritos.")

    referer = request.META.get('HTTP_REFERER')
    return redirect(referer if referer else reverse('musica:inicio'))


@login_required
def biblioteca(request):
    """Muestra todas las colecciones guardadas del usuario."""
    datos_biblio = get_biblioteca_usuario(request.user)
    descargas = Descarga.objects.filter(usuario=request.user).select_related('cancion__artista')[:10]

    return render(request, 'musica/biblioteca.html', {
        **datos_biblio,
        'descargas': descargas,
    })


# =============================================================================
# 7. SUSCRIPCIONES Y DESCARGAS SIMULADAS
# =============================================================================

@login_required
def suscripcion_view(request):
    """Muestra el plan actual del usuario y los planes disponibles para simular cambio."""
    mi_suscripcion = get_or_create_suscripcion_usuario(request.user)
    planes = PlanSuscripcion.objects.all().order_by('precio_mensual')

    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        nuevo_plan = get_object_or_404(PlanSuscripcion, pk=plan_id)
        mi_suscripcion.plan = nuevo_plan
        mi_suscripcion.estado = Suscripcion.ESTADO_ACTIVA
        mi_suscripcion.save()
        messages.success(request, f"¡Plan cambiado a {nuevo_plan.nombre} exitosamente (simulado)!")
        return redirect('musica:suscripcion')

    return render(request, 'musica/suscripcion.html', {
        'suscripcion': mi_suscripcion,
        'planes': planes,
    })


@login_required
@require_POST
def descarga_simulada(request, cancion_id):
    """Registra una descarga offline simulada en SQLite sin descargar archivos reales."""
    cancion = get_object_or_404(Cancion, pk=cancion_id)
    Descarga.objects.create(
        usuario=request.user,
        cancion=cancion,
        estado=Descarga.ESTADO_COMPLETADA,
        plataforma="SoundFlow Web App (Simulada)"
    )
    messages.success(request, f"Descarga de '{cancion.titulo}' guardada para escuchar sin conexión (simulada).")
    referer = request.META.get('HTTP_REFERER')
    return redirect(referer if referer else reverse('musica:cancion_detail', kwargs={'pk': cancion_id}))


# =============================================================================
# 8. INTEGRACIÓN CON CALL CENTER: CREACIÓN DE TICKETS DESDE CONTENIDO MUSICAL
# =============================================================================

@login_required
def ticket_desde_musica(request, tipo, objeto_id):
    """
    Flujo obligatorio:
    1. El usuario selecciona 'Contactar soporte' desde una ficha.
    2. El sistema recupera o crea el registro local `ContenidoMusical`.
    3. Precarga la referencia del contenido en la vista de ticket.
    4. Al enviar el formulario, crea el Ticket en `online.Preguntas` con la referencia musical.
    5. Redirige al chat del ticket (/Respuesta/<idPregunta>/).
    """
    contenido = None
    objeto_nombre = ""
    portada_url = ""
    url_interna = ""
    mbid_val = None

    # Resolver la entidad y construir o recuperar el ContenidoMusical
    if tipo == ContenidoMusical.TIPO_CANCION:
        cancion = get_object_or_404(Cancion.objects.select_related('artista', 'album'), pk=objeto_id)
        objeto_nombre = f"{cancion.titulo} - {cancion.artista.nombre}"
        portada_url = cancion.portada_o_default
        url_interna = reverse('musica:cancion_detail', kwargs={'pk': cancion.pk})
        mbid_val = cancion.mbid
        contenido, _ = ContenidoMusical.objects.get_or_create(
            tipo=tipo,
            cancion=cancion,
            defaults={
                'nombre': objeto_nombre,
                'mbid': mbid_val,
                'portada_url': portada_url,
                'url_interna': url_interna,
                'detalles_extra': f"Artista: {cancion.artista.nombre} | Álbum: {cancion.album.titulo if cancion.album else 'Sencillo'}"
            }
        )

    elif tipo == ContenidoMusical.TIPO_ALBUM:
        album = get_object_or_404(Album.objects.select_related('artista'), pk=objeto_id)
        objeto_nombre = f"{album.titulo} ({album.artista.nombre})"
        portada_url = album.portada_o_default
        url_interna = reverse('musica:album_detail', kwargs={'pk': album.pk})
        mbid_val = album.mbid
        contenido, _ = ContenidoMusical.objects.get_or_create(
            tipo=tipo,
            album=album,
            defaults={
                'nombre': objeto_nombre,
                'mbid': mbid_val,
                'portada_url': portada_url,
                'url_interna': url_interna,
                'detalles_extra': f"Año: {album.anio or 'Desconocido'} | Pistas: {album.canciones.count()}"
            }
        )

    elif tipo == ContenidoMusical.TIPO_ARTISTA:
        artista = get_object_or_404(Artista, pk=objeto_id)
        objeto_nombre = artista.nombre
        portada_url = artista.imagen_url or "/static/musica/img/cover_placeholder.svg"
        url_interna = reverse('musica:artista_detail', kwargs={'pk': artista.pk})
        mbid_val = artista.mbid
        contenido, _ = ContenidoMusical.objects.get_or_create(
            tipo=tipo,
            artista=artista,
            defaults={
                'nombre': objeto_nombre,
                'mbid': mbid_val,
                'portada_url': portada_url,
                'url_interna': url_interna,
                'detalles_extra': f"País: {artista.pais or 'N/A'}"
            }
        )

    elif tipo == ContenidoMusical.TIPO_PLAYLIST:
        playlist = get_object_or_404(Playlist, pk=objeto_id)
        objeto_nombre = f"Playlist: {playlist.nombre}"
        url_interna = reverse('musica:playlist_detail', kwargs={'pk': playlist.pk})
        contenido, _ = ContenidoMusical.objects.get_or_create(
            tipo=tipo,
            playlist=playlist,
            defaults={
                'nombre': objeto_nombre,
                'url_interna': url_interna,
                'detalles_extra': f"Canciones: {playlist.elementos.count()}"
            }
        )

    elif tipo == ContenidoMusical.TIPO_SUSCRIPCION:
        suscripcion = get_or_create_suscripcion_usuario(request.user)
        objeto_nombre = f"Suscripción: {suscripcion.plan.nombre}"
        url_interna = reverse('musica:suscripcion')
        contenido, _ = ContenidoMusical.objects.get_or_create(
            tipo=tipo,
            nombre=objeto_nombre,
            defaults={
                'url_interna': url_interna,
                'detalles_extra': f"Estado: {suscripcion.estado} | Precio: ${suscripcion.plan.precio_mensual}"
            }
        )

    elif tipo == ContenidoMusical.TIPO_DESCARGA:
        descarga = get_object_or_404(Descarga, pk=objeto_id, usuario=request.user)
        objeto_nombre = f"Descarga: {descarga.cancion.titulo}"
        url_interna = reverse('musica:cancion_detail', kwargs={'pk': descarga.cancion.pk})
        contenido, _ = ContenidoMusical.objects.get_or_create(
            tipo=tipo,
            cancion=descarga.cancion,
            nombre=objeto_nombre,
            defaults={
                'url_interna': url_interna,
                'detalles_extra': f"Fecha de descarga: {descarga.fecha} | Estado: {descarga.estado}"
            }
        )

    else:
        objeto_nombre = "Consulta general de SoundFlow"
        contenido, _ = ContenidoMusical.objects.get_or_create(
            tipo=ContenidoMusical.TIPO_OTRO,
            nombre=objeto_nombre,
            defaults={'url_interna': reverse('musica:inicio')}
        )

    # Procesar formulario de creación de ticket
    if request.method == 'POST':
        form = TicketMusicaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                pregunta = Preguntas.objects.create(
                    Titulo=form.cleaned_data['Titulo'],
                    Pregunta=form.cleaned_data['Pregunta'],
                    prioridad=form.cleaned_data['prioridad'],
                    categoria=form.cleaned_data['categoria'],
                    Usuario=request.user,
                    contenido_musical=contenido,
                    Fecha_creacion=timezone.now(),
                )
            logger.info(
                "Ticket de soporte musical creado: id=%s por usuario=%s con contenido=%s",
                pregunta.idPregunta, request.user.usuario, contenido.nombre
            )
            messages.success(request, "Ticket de soporte creado correctamente. Un especialista te atenderá pronto.")
            return redirect('respuestas', idPregunta=pregunta.idPregunta)
    else:
        initial_categoria = 'contenido_musical'
        if tipo == ContenidoMusical.TIPO_SUSCRIPCION:
            initial_categoria = 'suscripciones'
        elif tipo == ContenidoMusical.TIPO_DESCARGA:
            initial_categoria = 'descargas'
        elif tipo == ContenidoMusical.TIPO_PLAYLIST:
            initial_categoria = 'playlists'

        form = TicketMusicaForm(initial={
            'Titulo': f"Problema con {objeto_nombre[:40]}",
            'categoria': initial_categoria,
            'prioridad': Preguntas.PRIORIDAD_MEDIA,
        })

    return render(request, 'musica/ticket_musica.html', {
        'form': form,
        'contenido': contenido,
        'tipo': tipo,
        'objeto_nombre': objeto_nombre,
    })


@login_required
def mis_tickets(request):
    """Permite al cliente revisar sus tickets relacionados con SoundFlow."""
    tickets = (
        Preguntas.objects.filter(Usuario=request.user)
        .filter(contenido_musical__isnull=False)
        .select_related('contenido_musical', 'tecnico_asignado')
        .order_by('-Fecha_creacion')
    )

    return render(request, 'musica/mis_tickets.html', {
        'tickets': tickets,
    })
