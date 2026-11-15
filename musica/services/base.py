"""
===============================================================================
CAPA DE PROVEEDORES MUSICALES (musica/services/base.py)
===============================================================================
Define la interfaz conceptual BaseMusicProvider. Toda implementación de
proveedor de metadatos externo (como MusicBrainz) o mock para pruebas
debe adherirse a esta especificación.
===============================================================================
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseMusicProvider(ABC):
    """
    Contrato abstracto para proveedores de metadatos musicales externos.
    Desacopla el resto de la aplicación del proveedor concreto.
    """

    @abstractmethod
    def search_tracks(self, query: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """Busca canciones o grabaciones según el término de búsqueda."""
        pass

    @abstractmethod
    def search_artists(self, query: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """Busca artistas o bandas musicales."""
        pass

    @abstractmethod
    def search_albums(self, query: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """Busca álbumes o lanzamientos."""
        pass

    @abstractmethod
    def get_track(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el detalle normalizado de una canción mediante su identificador externo."""
        pass

    @abstractmethod
    def get_artist(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el detalle normalizado de un artista mediante su identificador externo."""
        pass

    @abstractmethod
    def get_album(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el detalle normalizado de un álbum mediante su identificador externo."""
        pass
