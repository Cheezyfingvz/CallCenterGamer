"""
===============================================================================
SERVICIO DE INTEGRACIÓN CON COVER ART ARCHIVE (musica/services/cover_art.py)
===============================================================================
Obtiene portadas asociadas a lanzamientos de MusicBrainz desde Cover Art Archive.
Incluye:
- Manejo de Timeouts y errores de conexión.
- Caché con Django cache framework (evita llamadas repetitivas).
- Portada genérica local de respaldo cuando no existe o falla el servicio.
- Preferencia de miniaturas (thumbnails de 250px o 500px) para rendimiento óptimo.
===============================================================================
"""
import logging
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CoverArtService:
    """
    Cliente desacoplado para consultar portadas en Cover Art Archive (CAA).
    """

    BASE_URL = "https://coverartarchive.org"
    PLACEHOLDER_URL = "/static/musica/img/cover_placeholder.svg"

    def __init__(self):
        self.timeout = getattr(settings, 'COVER_ART_TIMEOUT', 6)
        self.cache_ttl = getattr(settings, 'MUSICBRAINZ_CACHE_SECONDS', 86400)
        self.user_agent = getattr(
            settings,
            'MUSICBRAINZ_USER_AGENT',
            'SoundFlow/1.0 ( contacto@example.com )'
        )

    def _headers(self):
        return {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
        }

    def get_cover_url(self, release_mbid: str, release_group: bool = False) -> str:
        """
        Retorna la URL de la portada frontal (miniatura preferida) para el MBID dado.
        Si falla o no existe, retorna una cadena vacía (la plantilla o modelo usará el placeholder).
        """
        if not release_mbid:
            return ""

        cache_key = f"caa_{'rg' if release_group else 'rel'}_{release_mbid}".replace("-", "_")
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        tipo_endpoint = "release-group" if release_group else "release"
        url = f"{self.BASE_URL}/{tipo_endpoint}/{release_mbid}"

        try:
            logger.info("Consultando Cover Art Archive para %s: %s", tipo_endpoint, release_mbid)
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                images = data.get('images', [])
                front_image = None

                # Buscar la imagen frontal
                for img in images:
                    if img.get('front') is True:
                        front_image = img
                        break

                if not front_image and images:
                    front_image = images[0]

                if front_image:
                    thumbnails = front_image.get('thumbnails', {})
                    # Priorizar tamaño mediano (500) o pequeño (250) para no sobrecargar ancho de banda
                    cover_url = (
                        thumbnails.get('500')
                        or thumbnails.get('small')
                        or thumbnails.get('large')
                        or front_image.get('image', '')
                    )
                    if cover_url:
                        cache.set(cache_key, cover_url, self.cache_ttl)
                        return cover_url

            elif response.status_code == 404:
                logger.debug("Sin portada en Cover Art Archive (404) para %s", release_mbid)
                # Caché negativo para no repetir llamadas
                cache.set(cache_key, "", 3600)
                return ""

            elif response.status_code == 429:
                logger.warning("Límite de tasa en Cover Art Archive (HTTP 429).")
                return ""

        except requests.exceptions.Timeout:
            logger.warning("Timeout al consultar Cover Art Archive (%ss) para %s", self.timeout, release_mbid)
        except requests.exceptions.ConnectionError:
            logger.warning("Fallo de conexión al consultar Cover Art Archive para %s", release_mbid)
        except Exception as exc:
            logger.error("Error inesperado en CoverArtService: %s", exc)

        # Fallback a string vacío con TTL corto de reintento
        cache.set(cache_key, "", 600)
        return ""
