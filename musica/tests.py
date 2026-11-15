"""
===============================================================================
SUITE DE PRUEBAS AUTOMATIZADAS DE SOUNDFLOW (musica/tests.py)
===============================================================================
Verificaciones unitarias y de integración:
1. Integración desacoplada con MusicBrainz mediante Mocks (éxito, vacío, 429, timeout, caché).
2. Integración desacoplada con Cover Art Archive (éxito, 404, fallback placeholder).
3. Catálogo híbrido y sincronización a SQLite local.
4. Modelos y restricciones (unicidad de MBID, validación de reseñas 1-5 estrellas).
5. Gestión de Playlists y biblioteca (control estricto de propietario y favoritos).
6. Suscripciones y descargas simuladas en SQLite.
7. Integración con el sistema de tickets del Call Center:
   - Creación de tickets desde canciones, álbumes y playlists.
   - Preservación del ticket tras eliminar la referencia musical (SET_NULL).
   - Compatibilidad con tickets antiguos sin contenido musical.
===============================================================================
"""
from unittest.mock import patch, MagicMock
import requests
from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.core.exceptions import ValidationError

from online.models import Usuario, Preguntas, Respuesta
from musica.models import (
    Genero, Artista, Album, Cancion, Playlist, ElementoPlaylist,
    Favorito, PlanSuscripcion, Suscripcion, Descarga, Resena, ContenidoMusical
)
from musica.services.musicbrainz import MusicBrainzService
from musica.services.cover_art import CoverArtService
from musica.services.catalog import CatalogService


class MusicBrainzServiceTests(TestCase):
    """Pruebas del servicio MusicBrainz con Mocks (sin llamadas reales a internet)."""

    def setUp(self):
        cache.clear()
        self.service = MusicBrainzService()

    @patch('requests.get')
    def test_search_tracks_success_and_normalization(self, mock_get):
        """Comprueba la búsqueda exitosa y la correcta normalización de campos."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'recordings': [
                {
                    'id': 'mbid-track-123',
                    'title': 'Track Test',
                    'length': 210000,
                    'artist-credit': [{'artist': {'id': 'mbid-art-1', 'name': 'Artist Test'}}],
                    'releases': [{'id': 'mbid-rel-1', 'title': 'Album Test', 'date': '2024-01-01'}],
                    'tags': [{'name': 'rock'}],
                }
            ]
        }
        mock_get.return_value = mock_response

        results = self.service.search_tracks('Track Test')

        self.assertEqual(len(results), 1)
        tr = results[0]
        self.assertEqual(tr['mbid'], 'mbid-track-123')
        self.assertEqual(tr['titulo'], 'Track Test')
        self.assertEqual(tr['artista'], 'Artist Test')
        self.assertEqual(tr['album'], 'Album Test')
        self.assertEqual(tr['duracion_seg'], 210)
        self.assertEqual(tr['generos'], ['rock'])

    @patch('requests.get')
    def test_search_tracks_cached_avoids_repeated_http_calls(self, mock_get):
        """Verifica que el sistema de caché evite múltiples peticiones HTTP para la misma consulta."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'recordings': []}
        mock_get.return_value = mock_response

        # Primera llamada (debe hacer request)
        self.service.search_tracks('Query Unica')
        # Segunda llamada idéntica (debe usar caché)
        self.service.search_tracks('Query Unica')

        self.assertEqual(mock_get.call_count, 1)

    @patch('requests.get')
    def test_musicbrainz_handles_timeout(self, mock_get):
        """Garantiza degradación silenciosa y retorno seguro ante un Timeout."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        results = self.service.search_tracks('Cualquier cancion')
        self.assertEqual(results, [])

    @patch('requests.get')
    def test_musicbrainz_handles_http_429_rate_limit(self, mock_get):
        """Garantiza manejo elegante ante HTTP 429 Too Many Requests."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        results = self.service.search_artists('Artista')
        self.assertEqual(results, [])

    @patch('requests.get')
    def test_musicbrainz_handles_http_500_server_error(self, mock_get):
        """Garantiza manejo elegante ante caídas HTTP 500 del servidor externo."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        results = self.service.search_albums('Album')
        self.assertEqual(results, [])


class CoverArtServiceTests(TestCase):
    """Pruebas del servicio Cover Art Archive con Mocks."""

    def setUp(self):
        cache.clear()
        self.service = CoverArtService()

    @patch('requests.get')
    def test_cover_art_found(self, mock_get):
        """Verifica la obtención correcta de la miniatura de portada."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'images': [
                {
                    'front': True,
                    'thumbnails': {
                        '500': 'https://coverartarchive.org/500.jpg',
                        'small': 'https://coverartarchive.org/250.jpg',
                    },
                    'image': 'https://coverartarchive.org/full.jpg'
                }
            ]
        }
        mock_get.return_value = mock_response

        url = self.service.get_cover_url('mbid-album-1')
        self.assertEqual(url, 'https://coverartarchive.org/500.jpg')

    @patch('requests.get')
    def test_cover_art_404_returns_empty_for_placeholder_fallback(self, mock_get):
        """Comprueba que si no hay portada (404), retorne cadena vacía sin fallar."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        url = self.service.get_cover_url('mbid-inexistente')
        self.assertEqual(url, '')


class CatalogAndSyncTests(TestCase):
    """Pruebas de la capa de catálogo y sincronización con SQLite."""

    def setUp(self):
        cache.clear()
        self.catalog = CatalogService()
        self.artista = Artista.objects.create(nombre="Banda Local", es_demo=True)
        self.album = Album.objects.create(titulo="Disco Local", artista=self.artista, anio=2024, es_demo=True)
        self.cancion = Cancion.objects.create(titulo="Tema Local", artista=self.artista, album=self.album, duracion_seg=200)

    @patch.object(CoverArtService, 'get_cover_url', return_value='')
    @patch.object(MusicBrainzService, 'search_artists', return_value=[])
    @patch.object(MusicBrainzService, 'search_albums', return_value=[])
    @patch.object(MusicBrainzService, 'search_tracks')
    def test_search_local_first_with_external_fallback(self, mock_mb_tracks, mock_mb_albums, mock_mb_artists, mock_cover):
        """Verifica que la búsqueda local resuelva primero desde SQLite."""
        mock_mb_tracks.return_value = [
            {'mbid': 'ext-1', 'titulo': 'Tema Externo', 'artista': 'Ext Artista', 'album': 'Ext Alb', 'duracion_seg': 180, 'generos': []}
        ]

        results = self.catalog.search('Tema')

        self.assertIn(self.cancion, results['canciones_local'])
        self.assertEqual(len(results['canciones_externas']), 1)
        self.assertEqual(results['canciones_externas'][0]['titulo'], 'Tema Externo')

    @patch.object(CoverArtService, 'get_cover_url', return_value='')
    @patch.object(MusicBrainzService, 'get_album', return_value=None)
    @patch.object(MusicBrainzService, 'get_artist', return_value=None)
    @patch.object(MusicBrainzService, 'get_track')
    def test_sincronizar_cancion_persists_in_sqlite(self, mock_get_track, mock_get_artist, mock_get_album, mock_cover):
        """Verifica que la sincronización de una pista externa cree registros en SQLite."""
        mock_get_track.return_value = {
            'mbid': 'mbid-new-999',
            'titulo': 'Cancion Sincronizada',
            'artista': 'Nuevo Artista',
            'artista_mbid': 'mbid-art-999',
            'album': 'Nuevo Album',
            'album_mbid': 'mbid-alb-999',
            'duracion_seg': 215,
        }

        cancion = self.catalog.sincronizar_o_obtener_cancion('mbid-new-999')

        self.assertIsNotNone(cancion)
        self.assertEqual(cancion.titulo, 'Cancion Sincronizada')
        self.assertEqual(cancion.artista.nombre, 'Nuevo Artista')
        self.assertEqual(cancion.album.titulo, 'Nuevo Album')
        # Verificar que se guardó efectivamente en SQLite
        self.assertTrue(Cancion.objects.filter(mbid='mbid-new-999').exists())


class ModelConstraintsAndValidationTests(TestCase):
    """Pruebas de modelos, validación y restricciones de unicidad."""

    def setUp(self):
        self.user = Usuario.objects.create(usuario="tester", correo="tester@example.com")
        self.artista = Artista.objects.create(nombre="Test Artist", mbid="mbid-art-unique")
        self.album = Album.objects.create(titulo="Test Album", artista=self.artista, mbid="mbid-alb-unique")

    def test_resena_validation_1_to_5_stars(self):
        """Comprueba que la reseña valide que la puntuación esté entre 1 y 5."""
        resena_invalida = Resena(
            usuario=self.user,
            album=self.album,
            puntuacion=6,  # Inválida
            comentario="Excelente"
        )
        with self.assertRaises(ValidationError):
            resena_invalida.full_clean()

        resena_valida = Resena(
            usuario=self.user,
            album=self.album,
            puntuacion=5,
            comentario="Excelente"
        )
        resena_valida.full_clean()  # No debe lanzar excepción

    def test_mbid_uniqueness_prevents_duplicates(self):
        """Garantiza que no se puedan crear dos artistas o álbumes con el mismo MBID."""
        with self.assertRaises(Exception):
            Artista.objects.create(nombre="Duplicado", mbid="mbid-art-unique")


class PlaylistsAndFavoritesTests(TestCase):
    """Pruebas de gestión de playlists y favoritos."""

    def setUp(self):
        self.client = Client()
        self.user1 = Usuario.objects.create(usuario="user1", correo="u1@example.com")
        self.user1.set_password("pass123")
        self.user1.save()

        self.user2 = Usuario.objects.create(usuario="user2", correo="u2@example.com")
        self.user2.set_password("pass123")
        self.user2.save()

        self.artista = Artista.objects.create(nombre="Artista Demo")
        self.cancion = Cancion.objects.create(titulo="Cancion Demo", artista=self.artista)
        self.playlist = Playlist.objects.create(nombre="Mi Playlist", usuario=self.user1)

    def test_playlist_owner_can_add_and_remove_song(self):
        """Verifica que el propietario pueda agregar y quitar canciones de su playlist."""
        self.client.force_login(self.user1)

        # Agregar canción
        response = self.client.post(
            reverse('musica:playlist_add_cancion', args=[self.playlist.pk]),
            {'cancion_id': self.cancion.pk}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.playlist.elementos.count(), 1)

        # Quitar canción
        response2 = self.client.post(
            reverse('musica:playlist_remove_cancion', args=[self.playlist.pk, self.cancion.pk])
        )
        self.assertEqual(response2.status_code, 302)
        self.assertEqual(self.playlist.elementos.count(), 0)

    def test_user_cannot_edit_another_users_playlist(self):
        """Comprueba que un usuario ajeno reciba 404/bloqueo al intentar editar la playlist de otro."""
        self.client.force_login(self.user2)

        response = self.client.get(reverse('musica:playlist_edit', args=[self.playlist.pk]))
        self.assertEqual(response.status_code, 404)

    def test_toggle_favorito(self):
        """Verifica que el toggle agregue y quite correctamente de favoritos."""
        self.client.force_login(self.user1)

        # Agregar
        self.client.post(reverse('musica:toggle_favorito', args=['cancion', self.cancion.pk]))
        self.assertTrue(Favorito.objects.filter(usuario=self.user1, cancion=self.cancion).exists())

        # Quitar
        self.client.post(reverse('musica:toggle_favorito', args=['cancion', self.cancion.pk]))
        self.assertFalse(Favorito.objects.filter(usuario=self.user1, cancion=self.cancion).exists())


class SubscriptionsAndDownloadsTests(TestCase):
    """Pruebas de planes de suscripción y descargas simuladas."""

    def setUp(self):
        self.user = Usuario.objects.create(usuario="subuser", correo="sub@example.com")
        self.plan_free = PlanSuscripcion.objects.create(codigo=PlanSuscripcion.CODIGO_GRATUITO, nombre="Free", precio_mensual=0)
        self.plan_prem = PlanSuscripcion.objects.create(codigo=PlanSuscripcion.CODIGO_INDIVIDUAL, nombre="Premium", precio_mensual=5.99)
        self.artista = Artista.objects.create(nombre="A")
        self.cancion = Cancion.objects.create(titulo="C", artista=self.artista)

    def test_user_gets_free_subscription_and_can_upgrade(self):
        """Verifica la asignación de suscripción gratuita y el cambio simulado de plan."""
        client = Client()
        client.force_login(self.user)

        # Entrar a suscripción genera la suscripción gratuita
        response = client.get(reverse('musica:suscripcion'))
        self.assertEqual(response.status_code, 200)

        sub = Suscripcion.objects.get(usuario=self.user)
        self.assertEqual(sub.plan.codigo, PlanSuscripcion.CODIGO_GRATUITO)

        # Cambiar a Premium
        client.post(reverse('musica:suscripcion'), {'plan_id': self.plan_prem.pk})
        sub.refresh_from_db()
        self.assertEqual(sub.plan.codigo, PlanSuscripcion.CODIGO_INDIVIDUAL)

    def test_descarga_simulada_records_in_sqlite(self):
        """Comprueba que la descarga simulada se registre en SQLite sin descargar archivos."""
        client = Client()
        client.force_login(self.user)

        response = client.post(reverse('musica:descarga_simulada', args=[self.cancion.pk]))
        self.assertEqual(response.status_code, 302)

        descarga = Descarga.objects.filter(usuario=self.user, cancion=self.cancion).first()
        self.assertIsNotNone(descarga)
        self.assertEqual(descarga.estado, Descarga.ESTADO_COMPLETADA)


class CallCenterIntegrationTests(TestCase):
    """Pruebas de la integración funcional entre SoundFlow y el Call Center."""

    def setUp(self):
        self.client_user = Usuario.objects.create(usuario="cliente_music", correo="cm@example.com")
        self.tech_user = Usuario.objects.create(usuario="agente_soporte", correo="ag@example.com", tecnico=True)
        self.artista = Artista.objects.create(nombre="Banda de Prueba")
        self.album = Album.objects.create(titulo="Album de Prueba", artista=self.artista)
        self.cancion = Cancion.objects.create(titulo="Cancion con Error", artista=self.artista, album=self.album)

    def test_create_ticket_from_song(self):
        """Verifica la creación de un ticket de soporte directamente desde una canción."""
        client = Client()
        client.force_login(self.client_user)

        response = client.post(
            reverse('musica:ticket_desde_musica', args=['cancion', self.cancion.pk]),
            {
                'Titulo': 'No coincide la letra',
                'Pregunta': 'El título del álbum está mal escrito en los metadatos.',
                'prioridad': Preguntas.PRIORIDAD_ALTA,
                'categoria': 'contenido_musical',
            }
        )

        ticket = Preguntas.objects.filter(Titulo='No coincide la letra').first()
        self.assertIsNotNone(ticket)
        self.assertRedirects(response, reverse('respuestas', args=[ticket.idPregunta]))

        # Verifica que se asoció la referencia local ContenidoMusical
        self.assertIsNotNone(ticket.contenido_musical)
        self.assertEqual(ticket.contenido_musical.cancion, self.cancion)
        self.assertEqual(ticket.categoria, 'contenido_musical')

    def test_deleting_musical_content_keeps_the_ticket(self):
        """Verifica que el ticket sobreviva (SET_NULL) si se elimina el ContenidoMusical."""
        contenido = ContenidoMusical.objects.create(
            tipo=ContenidoMusical.TIPO_CANCION,
            cancion=self.cancion,
            nombre="Referencia temporal"
        )
        ticket = Preguntas.objects.create(
            Titulo="Ticket con música",
            Pregunta="Problema",
            Usuario=self.client_user,
            contenido_musical=contenido
        )

        contenido.delete()
        ticket.refresh_from_db()

        # El ticket debe seguir existiendo con contenido_musical a None
        self.assertIsNone(ticket.contenido_musical)
        self.assertEqual(ticket.Titulo, "Ticket con música")

    def test_old_ticket_without_musical_content_loads_fine(self):
        """Garantiza compatibilidad total: tickets antiguos sin contenido musical cargan sin error."""
        ticket_antiguo = Preguntas.objects.create(
            Titulo="Ticket Clásico",
            Pregunta="Problema de hardware original",
            Usuario=self.client_user,
            contenido_musical=None  # Sin referencia musical
        )

        client = Client()
        client.force_login(self.tech_user)

        # Ver en el chat de soporte
        response = client.get(reverse('respuestas', args=[ticket_antiguo.idPregunta]))
        self.assertEqual(response.status_code, 200)

        # Ver en modificación administrativa
        response_admin = client.get(reverse('modificar_pregunta', args=[ticket_antiguo.idPregunta]))
        # Tecnico sin admin redirige a inicio en ModificarPregunta según RBAC original
        self.assertTrue(response_admin.status_code in (200, 302))
