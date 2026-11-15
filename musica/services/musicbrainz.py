"""
===============================================================================
SERVICIO DE INTEGRACIÓN CON MUSICBRAINZ (musica/services/musicbrainz.py)
===============================================================================
Implementa el cliente HTTP para el Web Service v2 de MusicBrainz respetando:
- User-Agent institucional requerido por la API.
- Respuestas estrictamente en formato JSON.
- Timeout configurable (5-10s).
- Manejo de excepciones (Timeout, ConnectionError, 429, 4xx, 5xx).
- Almacenamiento en caché de Django para evitar peticiones redundantes.
- Normalización de metadatos antes de enviarlos a las capas superiores.
===============================================================================
"""
import logging
import requests
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.core.cache import cache
from urllib.parse import urlencode

from musica.services.base import BaseMusicProvider

logger = logging.getLogger(__name__)


class MusicBrainzService(BaseMusicProvider):
    """
    Cliente desacoplado para consultar metadatos musicales desde MusicBrainz WS/2.
    """

    def __init__(self):
        self.base_url = getattr(
            settings,
            'MUSICBRAINZ_BASE_URL',
            'https://musicbrainz.org/ws/2'
        ).rstrip('/')
        self.user_agent = getattr(
            settings,
            'MUSICBRAINZ_USER_AGENT',
            'SoundFlow/1.0 ( contacto@example.com )'
        )
        self.timeout = getattr(settings, 'MUSICBRAINZ_TIMEOUT', 8)
        self.cache_ttl = getattr(settings, 'MUSICBRAINZ_CACHE_SECONDS', 86400)

    def _headers(self) -> Dict[str, str]:
        return {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
        }

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Ejecuta una petición GET a MusicBrainz con caché, timeouts y manejo de errores.
        """
        params = params or {}
        params['fmt'] = 'json'

        # Construir clave de caché determinista
        query_string = urlencode(sorted(params.items()))
        cache_key = f"mbz_{endpoint}_{query_string}".replace(" ", "_")[:200]

        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.debug("MusicBrainz HIT en caché para clave: %s", cache_key)
            return cached_response

        url = f"{self.base_url}/{endpoint}"
        try:
            logger.info("Consultando MusicBrainz: %s?%s", url, query_string)
            response = requests.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    cache.set(cache_key, data, self.cache_ttl)
                    return data
                except Exception as json_err:
                    logger.error("Error decodificando JSON de MusicBrainz: %s", json_err)
                    return None

            elif response.status_code == 429:
                logger.warning("Límite de tasa excedido en MusicBrainz (HTTP 429). Activando fallback.")
                return None

            elif response.status_code == 404:
                logger.info("Recurso no encontrado en MusicBrainz (HTTP 404): %s", url)
                return None

            elif 400 <= response.status_code < 500:
                logger.warning("Error de cliente MusicBrainz (HTTP %s): %s", response.status_code, response.text[:200])
                return None

            elif response.status_code >= 500:
                logger.error("Error de servidor MusicBrainz (HTTP %s)", response.status_code)
                return None

        except requests.exceptions.Timeout:
            logger.warning("Timeout al conectar con MusicBrainz (%ss): %s", self.timeout, url)
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("Fallo de conexión de red hacia MusicBrainz: %s", url)
            return None
        except Exception as exc:
            logger.error("Excepción inesperada consultando MusicBrainz: %s", exc, exc_info=True)
            return None

        return None

    def search_tracks(self, query: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Busca grabaciones (recordings) en MusicBrainz.
        """
        if not query or not query.strip():
            return []

        offset = max(0, (page - 1) * limit)
        params = {
            'query': query.strip(),
            'limit': limit,
            'offset': offset,
        }
        data = self._request('recording', params)
        if not data or 'recordings' not in data:
            return []

        resultados = []
        for rec in data.get('recordings', []):
            mbid = rec.get('id')
            titulo = rec.get('title', 'Sin título')

            # Extraer artista principal
            artist_credit = rec.get('artist-credit', [])
            artista_nombre = "Artista Desconocido"
            artista_mbid = None
            if artist_credit and isinstance(artist_credit[0], dict):
                art_dict = artist_credit[0].get('artist', {})
                artista_nombre = art_dict.get('name') or artist_credit[0].get('name', artista_nombre)
                artista_mbid = art_dict.get('id')

            # Extraer álbum (release)
            releases = rec.get('releases', [])
            album_nombre = ""
            album_mbid = None
            fecha = ""
            if releases and isinstance(releases[0], dict):
                first_rel = releases[0]
                album_nombre = first_rel.get('title', '')
                album_mbid = first_rel.get('id')
                fecha = first_rel.get('date', '')

            # Duración en segundos (MusicBrainz da milisegundos en 'length')
            length_ms = rec.get('length')
            duracion_seg = int(length_ms / 1000) if length_ms else 180

            # Tags/géneros
            tags = [t.get('name') for t in rec.get('tags', []) if t.get('name')]

            resultados.append({
                'mbid': mbid,
                'titulo': titulo,
                'artista': artista_nombre,
                'artista_mbid': artista_mbid,
                'album': album_nombre,
                'album_mbid': album_mbid,
                'duracion_seg': duracion_seg,
                'fecha': fecha,
                'generos': tags[:3],
                'proveedor': 'MusicBrainz',
            })
        return resultados

    def search_artists(self, query: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Busca artistas en MusicBrainz.
        """
        if not query or not query.strip():
            return []

        offset = max(0, (page - 1) * limit)
        params = {
            'query': query.strip(),
            'limit': limit,
            'offset': offset,
        }
        data = self._request('artist', params)
        if not data or 'artists' not in data:
            return []

        artistas = []
        for art in data.get('artists', []):
            tags = [t.get('name') for t in art.get('tags', []) if t.get('name')]
            area = art.get('area', {})
            pais = area.get('name', '') if isinstance(area, dict) else ''
            artistas.append({
                'mbid': art.get('id'),
                'nombre': art.get('name', 'Artista'),
                'pais': pais,
                'tipo': art.get('type', 'Grupo/Persona'),
                'bio': art.get('disambiguation', ''),
                'generos': tags[:3],
                'proveedor': 'MusicBrainz',
            })
        return artistas

    def search_albums(self, query: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Busca lanzamientos (releases / release-groups) en MusicBrainz.
        """
        if not query or not query.strip():
            return []

        offset = max(0, (page - 1) * limit)
        params = {
            'query': query.strip(),
            'limit': limit,
            'offset': offset,
        }
        data = self._request('release-group', params)
        if not data or 'release-groups' not in data:
            # Fallback a 'release' si release-group no devuelve resultados
            data = self._request('release', params)
            if not data or 'releases' not in data:
                return []
            items = data.get('releases', [])
        else:
            items = data.get('release-groups', [])

        albums = []
        for item in items:
            mbid = item.get('id')
            titulo = item.get('title', 'Sin título')

            artist_credit = item.get('artist-credit', [])
            artista_nombre = "Varios Artistas"
            artista_mbid = None
            if artist_credit and isinstance(artist_credit[0], dict):
                art_dict = artist_credit[0].get('artist', {})
                artista_nombre = art_dict.get('name') or artist_credit[0].get('name', artista_nombre)
                artista_mbid = art_dict.get('id')

            fecha = item.get('first-release-date') or item.get('date', '')
            anio = None
            if fecha and len(fecha) >= 4 and fecha[:4].isdigit():
                anio = int(fecha[:4])

            tags = [t.get('name') for t in item.get('tags', []) if t.get('name')]

            albums.append({
                'mbid': mbid,
                'titulo': titulo,
                'artista': artista_nombre,
                'artista_mbid': artista_mbid,
                'anio': anio,
                'fecha': fecha,
                'generos': tags[:3],
                'proveedor': 'MusicBrainz',
            })
        return albums

    def get_track(self, external_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el detalle de una grabación por MBID.
        """
        if not external_id:
            return None
        data = self._request(f"recording/{external_id}", {'inc': 'artists+releases'})
        if not data:
            return None

        artist_credit = data.get('artist-credit', [])
        artista_nombre = "Artista Desconocido"
        artista_mbid = None
        if artist_credit and isinstance(artist_credit[0], dict):
            art_dict = artist_credit[0].get('artist', {})
            artista_nombre = art_dict.get('name') or artist_credit[0].get('name', artista_nombre)
            artista_mbid = art_dict.get('id')

        releases = data.get('releases', [])
        album_nombre = ""
        album_mbid = None
        fecha = ""
        if releases and isinstance(releases[0], dict):
            first_rel = releases[0]
            album_nombre = first_rel.get('title', '')
            album_mbid = first_rel.get('id')
            fecha = first_rel.get('date', '')

        length_ms = data.get('length')
        duracion_seg = int(length_ms / 1000) if length_ms else 180

        return {
            'mbid': data.get('id'),
            'titulo': data.get('title', 'Sin título'),
            'artista': artista_nombre,
            'artista_mbid': artista_mbid,
            'album': album_nombre,
            'album_mbid': album_mbid,
            'duracion_seg': duracion_seg,
            'fecha': fecha,
            'generos': [],
            'proveedor': 'MusicBrainz',
        }

    def get_artist(self, external_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el detalle de un artista por MBID.
        """
        if not external_id:
            return None
        data = self._request(f"artist/{external_id}", {'inc': 'release-groups+tags'})
        if not data:
            return None

        tags = [t.get('name') for t in data.get('tags', []) if t.get('name')]
        area = data.get('area', {})
        pais = area.get('name', '') if isinstance(area, dict) else ''

        albums = []
        for rg in data.get('release-groups', [])[:10]:
            albums.append({
                'mbid': rg.get('id'),
                'titulo': rg.get('title', ''),
                'fecha': rg.get('first-release-date', ''),
            })

        return {
            'mbid': data.get('id'),
            'nombre': data.get('name', 'Artista'),
            'pais': pais,
            'tipo': data.get('type', 'Grupo/Persona'),
            'bio': data.get('disambiguation', ''),
            'generos': tags[:4],
            'albums': albums,
            'proveedor': 'MusicBrainz',
        }

    def get_album(self, external_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el detalle de un álbum o release-group por MBID.
        """
        if not external_id:
            return None
        data = self._request(f"release-group/{external_id}", {'inc': 'artists+releases'})
        if not data:
            # Reintentar como release si era un release mbid
            data = self._request(f"release/{external_id}", {'inc': 'artists+recordings'})
            if not data:
                return None

        artist_credit = data.get('artist-credit', [])
        artista_nombre = "Artista"
        artista_mbid = None
        if artist_credit and isinstance(artist_credit[0], dict):
            art_dict = artist_credit[0].get('artist', {})
            artista_nombre = art_dict.get('name') or artist_credit[0].get('name', artista_nombre)
            artista_mbid = art_dict.get('id')

        fecha = data.get('first-release-date') or data.get('date', '')
        anio = None
        if fecha and len(fecha) >= 4 and fecha[:4].isdigit():
            anio = int(fecha[:4])

        pistas = []
        media = data.get('media', [])
        if media and isinstance(media[0], dict):
            for track in media[0].get('tracks', []):
                pistas.append({
                    'mbid': track.get('id'),
                    'titulo': track.get('title', ''),
                    'duracion_seg': int(track.get('length', 180000) / 1000) if track.get('length') else 180,
                    'numero': track.get('position', 1),
                })

        return {
            'mbid': data.get('id'),
            'titulo': data.get('title', 'Álbum'),
            'artista': artista_nombre,
            'artista_mbid': artista_mbid,
            'anio': anio,
            'fecha': fecha,
            'pistas': pistas,
            'proveedor': 'MusicBrainz',
        }
