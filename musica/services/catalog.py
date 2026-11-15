"""
===============================================================================
SERVICIO DE CATÁLOGO Y SINCRONIZACIÓN LOCAL (musica/services/catalog.py)
===============================================================================
Capa intermedia que une:
- Base de datos local SQLite (artistas, álbumes, canciones, playlists).
- Proveedor externo (MusicBrainz).
- Proveedor de portadas (Cover Art Archive).
- Lógica de degradación controlada (offline-first).
- Generación de recomendaciones explicables sin IA externa.
===============================================================================
"""
import logging
from typing import Dict, Any, List, Optional
from django.db.models import Q, Count
from django.db import transaction

from musica.models import Genero, Artista, Album, Cancion, Playlist, Favorito, HistorialEscucha
from musica.services.musicbrainz import MusicBrainzService
from musica.services.cover_art import CoverArtService

logger = logging.getLogger(__name__)


class CatalogService:
    """
    Servicio de catálogo musical para SoundFlow.
    Las vistas solo se comunican con este servicio, manteniendo el desacoplamiento.
    """

    def __init__(self, provider=None, cover_service=None):
        self.provider = provider or MusicBrainzService()
        self.cover_service = cover_service or CoverArtService()

    # =========================================================================
    # BÚSQUEDA HÍBRIDA (LOCAL + EXTERNA)
    # =========================================================================

    def search(self, query: str, tipo: str = 'todos', page: int = 1, limit: int = 15) -> Dict[str, Any]:
        """
        Búsqueda con estrategia de degradación controlada:
        1. Busca primero en la base de datos local SQLite.
        2. Si la consulta lo amerita, consulta externamente a MusicBrainz.
        3. Integra y marca claramente el origen (local vs externo).
        """
        query = (query or "").strip()
        if not query:
            return {
                'canciones': [],
                'albums': [],
                'artistas': [],
                'playlists': [],
                'total_local': 0,
                'total_externo': 0,
            }

        # 1. Búsqueda local en SQLite
        canciones_local = list(
            Cancion.objects.filter(
                Q(titulo__icontains=query) |
                Q(artista__nombre__icontains=query) |
                Q(album__titulo__icontains=query)
            ).select_related('artista', 'album')[:limit]
        )

        albums_local = list(
            Album.objects.filter(
                Q(titulo__icontains=query) |
                Q(artista__nombre__icontains=query)
            ).select_related('artista')[:limit]
        )

        artistas_local = list(
            Artista.objects.filter(
                Q(nombre__icontains=query) |
                Q(bio__icontains=query)
            )[:limit]
        )

        playlists_local = list(
            Playlist.objects.filter(
                Q(nombre__icontains=query) |
                Q(descripcion__icontains=query)
            ).select_related('usuario')[:limit]
        )

        total_local = len(canciones_local) + len(albums_local) + len(artistas_local)

        # 2. Búsqueda externa en MusicBrainz (si no es exclusivamente playlist)
        canciones_externas = []
        albums_externos = []
        artistas_externos = []

        try:
            if tipo in ('todos', 'cancion'):
                mb_tracks = self.provider.search_tracks(query, page=page, limit=limit)
                for tr in mb_tracks:
                    # Si ya existe localmente por MBID, no duplicar en lista externa
                    if tr.get('mbid') and Cancion.objects.filter(mbid=tr['mbid']).exists():
                        continue
                    canciones_externas.append(tr)

            if tipo in ('todos', 'album'):
                mb_albums = self.provider.search_albums(query, page=page, limit=limit)
                for alb in mb_albums:
                    if alb.get('mbid') and Album.objects.filter(mbid=alb['mbid']).exists():
                        continue
                    # Buscar portada en segundo plano o bajo demanda
                    alb['portada_url'] = self.cover_service.get_cover_url(alb.get('mbid', ''))
                    albums_externos.append(alb)

            if tipo in ('todos', 'artista'):
                mb_artistas = self.provider.search_artists(query, page=page, limit=limit)
                for art in mb_artistas:
                    if art.get('mbid') and Artista.objects.filter(mbid=art['mbid']).exists():
                        continue
                    artistas_externos.append(art)

        except Exception as exc:
            logger.warning("Fallo al consultar proveedor externo en search(): %s. Usando solo local.", exc)

        total_externo = len(canciones_externas) + len(albums_externos) + len(artistas_externos)

        return {
            'canciones_local': canciones_local,
            'canciones_externas': canciones_externas,
            'albums_local': albums_local,
            'albums_externos': albums_externos,
            'artistas_local': artistas_local,
            'artistas_externos': artistas_externos,
            'playlists_local': playlists_local,
            'total_local': total_local,
            'total_externo': total_externo,
            'query': query,
        }

    # =========================================================================
    # PERSISTENCIA Y SINCRONIZACIÓN LOCAL DE ELEMENTOS EXTERNOS
    # =========================================================================

    @transaction.atomic
    def sincronizar_o_obtener_artista(self, mbid: str, fallback_data: Optional[Dict[str, Any]] = None) -> Optional[Artista]:
        """
        Busca un artista por MBID en la BD local. Si no existe, lo consulta en MusicBrainz
        y lo guarda en SQLite.
        """
        if not mbid:
            return None

        artista = Artista.objects.filter(mbid=mbid).first()
        if artista:
            return artista

        data = self.provider.get_artist(mbid) or fallback_data
        if not data:
            return None

        artista = Artista.objects.create(
            mbid=mbid,
            nombre=data.get('nombre') or data.get('name', 'Artista MusicBrainz'),
            pais=data.get('pais', ''),
            bio=data.get('bio', ''),
            es_demo=False
        )

        for gen_nombre in data.get('generos', []):
            genero, _ = Genero.objects.get_or_create(nombre=gen_nombre.title())
            artista.generos.add(genero)

        logger.info("Artista sincronizado en local: %s (MBID: %s)", artista.nombre, mbid)
        return artista

    @transaction.atomic
    def sincronizar_o_obtener_album(self, mbid: str, fallback_data: Optional[Dict[str, Any]] = None) -> Optional[Album]:
        """
        Busca un álbum por MBID localmente. Si no existe, lo consulta en MusicBrainz,
        obtiene su portada en Cover Art Archive y lo persiste en SQLite.
        """
        if not mbid:
            return None

        album = Album.objects.filter(mbid=mbid).select_related('artista').first()
        if album:
            return album

        data = self.provider.get_album(mbid) or fallback_data
        if not data:
            return None

        # Asegurar artista local
        artista_mbid = data.get('artista_mbid')
        artista = None
        if artista_mbid:
            artista = self.sincronizar_o_obtener_artista(artista_mbid, {'nombre': data.get('artista', 'Varios Artistas')})
        if not artista:
            artista_nombre = data.get('artista', 'Varios Artistas')
            artista, _ = Artista.objects.get_or_create(nombre=artista_nombre, defaults={'es_demo': False})

        # Obtener portada desde Cover Art Archive
        portada_url = self.cover_service.get_cover_url(mbid, release_group=True)
        if not portada_url:
            portada_url = self.cover_service.get_cover_url(mbid, release_group=False)

        anio = data.get('anio')
        if not anio and data.get('fecha') and len(data['fecha']) >= 4 and data['fecha'][:4].isdigit():
            anio = int(data['fecha'][:4])

        album = Album.objects.create(
            mbid=mbid,
            titulo=data.get('titulo', 'Álbum MusicBrainz'),
            artista=artista,
            anio=anio,
            fecha_lanzamiento=data.get('fecha', ''),
            portada_url=portada_url or '',
            es_demo=False
        )

        # Si el detalle trajo pistas, guardarlas
        pistas = data.get('pistas', [])
        for p in pistas:
            Cancion.objects.get_or_create(
                mbid=p.get('mbid'),
                defaults={
                    'titulo': p.get('titulo', 'Pista'),
                    'artista': artista,
                    'album': album,
                    'duracion_seg': p.get('duracion_seg', 180),
                    'numero_pista': p.get('numero', 1),
                    'es_demo': False,
                }
            )

        logger.info("Álbum sincronizado en local con portada: %s (MBID: %s)", album.titulo, mbid)
        return album

    @transaction.atomic
    def sincronizar_o_obtener_cancion(self, mbid: str, fallback_data: Optional[Dict[str, Any]] = None) -> Optional[Cancion]:
        """
        Busca o sincroniza una canción desde MusicBrainz a SQLite local.
        """
        if not mbid:
            return None

        cancion = Cancion.objects.filter(mbid=mbid).select_related('artista', 'album').first()
        if cancion:
            return cancion

        data = self.provider.get_track(mbid) or fallback_data
        if not data:
            return None

        # Sincronizar artista
        artista_mbid = data.get('artista_mbid')
        artista = None
        if artista_mbid:
            artista = self.sincronizar_o_obtener_artista(artista_mbid, {'nombre': data.get('artista', 'Artista')})
        if not artista:
            artista, _ = Artista.objects.get_or_create(
                nombre=data.get('artista', 'Artista'),
                defaults={'es_demo': False}
            )

        # Sincronizar álbum si viene informado
        album = None
        album_mbid = data.get('album_mbid')
        if album_mbid:
            album = self.sincronizar_o_obtener_album(album_mbid, {
                'titulo': data.get('album', 'Sencillo'),
                'artista': artista.nombre,
                'artista_mbid': artista.mbid
            })

        cancion = Cancion.objects.create(
            mbid=mbid,
            titulo=data.get('titulo', 'Canción'),
            artista=artista,
            album=album,
            duracion_seg=data.get('duracion_seg', 180),
            es_demo=False
        )

        logger.info("Canción sincronizada en local: %s (MBID: %s)", cancion.titulo, mbid)
        return cancion

    # =========================================================================
    # RECOMENDACIONES EXPLICABLES
    # =========================================================================

    def obtener_recomendaciones(self, usuario, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Genera recomendaciones basadas en reglas locales explicables:
        1. Artistas favoritos del usuario.
        2. Géneros de canciones/álbumes escuchados recientemente.
        3. Canciones populares más añadidas a playlists o favoritos.
        """
        recomendaciones = []
        ids_excluidos = set()

        if usuario and usuario.is_authenticated:
            # Regla 1: Basado en favoritos
            fav_canciones = Cancion.objects.filter(favoritos__usuario=usuario)
            artistas_fav = Artista.objects.filter(favoritos__usuario=usuario)

            # Canciones de sus artistas favoritos que no ha marcado en favoritos
            canciones_artistas_fav = Cancion.objects.filter(
                artista__in=artistas_fav
            ).exclude(
                id__in=fav_canciones.values_list('id', flat=True)
            ).select_related('artista', 'album')[:4]

            for c in canciones_artistas_fav:
                if c.id not in ids_excluidos:
                    recomendaciones.append({
                        'cancion': c,
                        'motivo': f"Porque te gusta el artista {c.artista.nombre}"
                    })
                    ids_excluidos.add(c.id)

            # Regla 2: Basado en historial reciente
            historial = HistorialEscucha.objects.filter(usuario=usuario).select_related('cancion__artista')[:10]
            if historial.exists():
                artistas_historial = [h.cancion.artista for h in historial if h.cancion]
                sugerencias_historial = Cancion.objects.filter(
                    artista__in=artistas_historial
                ).exclude(id__in=ids_excluidos).select_related('artista', 'album')[:4]

                for c in sugerencias_historial:
                    if c.id not in ids_excluidos:
                        recomendaciones.append({
                            'cancion': c,
                            'motivo': f"Basado en tus reproducciones recientes de {c.artista.nombre}"
                        })
                        ids_excluidos.add(c.id)

        # Regla 3: Si faltan recomendaciones, completar con canciones más populares localmente
        if len(recomendaciones) < limit:
            populares = (
                Cancion.objects.exclude(id__in=ids_excluidos)
                .annotate(num_favs=Count('favoritos'))
                .order_by('-num_favs', '-id')
                .select_related('artista', 'album')[:limit - len(recomendaciones)]
            )
            for c in populares:
                recomendaciones.append({
                    'cancion': c,
                    'motivo': "Destacado en la comunidad SoundFlow"
                })
                ids_excluidos.add(c.id)

        return recomendaciones[:limit]
