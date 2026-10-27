"""
===============================================================================
SUITE DE PRUEBAS AUTOMATIZADAS DE LA APP ADMINISTRACION (administracion/tests.py)
===============================================================================
Propósito:
    Valida los controles de seguridad RBAC, protección contra falsificación de
    parámetros en URLs administrativas, exigencia de método POST en acciones
    destructivas, renderizado real de `indexAdmin.html` sin bucle infinito y
    protección contra autodesactivación/autoeliminación del administrador.
===============================================================================
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from online.models import Preguntas, Usuario


class AdministrationAccessTests(TestCase):
    """
    Pruebas de integración y seguridad para las vistas del módulo `administracion`.
    """

    def setUp(self):
        """
        Crea un usuario Administrador (`self.admin`), un cliente propietario (`self.owner`)
        y un ticket de soporte inicial (`self.question`).
        """
        self.admin = self.create_user('admin', 'admin@example.com', admin=True)
        self.owner = self.create_user('owner', 'owner@example.com')
        self.question = Preguntas.objects.create(
            Titulo='Consulta',
            Pregunta='No inicia el juego',
            Fecha_creacion=timezone.now(),
            Usuario=self.owner,
        )

    def create_user(self, username, email, **fields):
        """
        Helper auxiliar para instanciar usuarios con contraseña cifrada válida.
        """
        user = Usuario.objects.create(
            usuario=username,
            correo=email,
            **fields,
        )
        user.set_password('test-password-123')
        user.save()
        return user

    def test_non_admin_cannot_delete_question_by_spoofing_admin_id(self):
        """
        Verifica que un usuario sin permisos de administrador (`owner`) NO pueda
        borrar un ticket aunque ponga el ID del administrador en la URL de `borrar_pregunta`.
        """
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('borrar_pregunta', args=[self.admin.id, self.question.idPregunta])
        )

        self.assertRedirects(response, reverse('inicio', args=[self.owner.id]))
        self.assertTrue(Preguntas.objects.filter(pk=self.question.pk).exists())

    def test_admin_can_delete_question_only_with_post(self):
        """
        Comprueba que la eliminación de un ticket falle con HTTP 405 si se invoca
        por GET, y tenga éxito únicamente cuando el Administrador envía una petición POST.
        """
        self.client.force_login(self.admin)

        get_response = self.client.get(
            reverse('borrar_pregunta', args=[self.owner.id, self.question.idPregunta])
        )
        self.assertEqual(get_response.status_code, 405)
        self.assertTrue(Preguntas.objects.filter(pk=self.question.pk).exists())

        post_response = self.client.post(
            reverse('borrar_pregunta', args=[self.owner.id, self.question.idPregunta])
        )
        self.assertRedirects(post_response, reverse('administracion'))
        self.assertFalse(Preguntas.objects.filter(pk=self.question.pk).exists())

    def test_user_deletion_requires_post_and_prevents_self_deletion(self):
        """
        Verifica que `eliminar_usuario` rechace peticiones GET (HTTP 405) y que
        impida que el administrador con sesión activa elimine su propia cuenta.
        """
        self.client.force_login(self.admin)

        get_response = self.client.get(
            reverse('eliminar_usuario', args=[self.owner.id])
        )
        self.assertEqual(get_response.status_code, 405)
        self.assertTrue(Usuario.objects.filter(pk=self.owner.pk).exists())

        post_response = self.client.post(
            reverse('eliminar_usuario', args=[self.admin.id])
        )
        self.assertRedirects(post_response, reverse('gestion_usuarios'))
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())

    def test_admin_can_delete_another_user_with_post(self):
        """
        Comprueba que un Administrador pueda eliminar la cuenta de otro usuario
        mediante una petición POST válida.
        """
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('eliminar_usuario', args=[self.owner.id])
        )

        self.assertRedirects(response, reverse('gestion_usuarios'))
        self.assertFalse(Usuario.objects.filter(pk=self.owner.pk).exists())

    def test_analytics_route_is_available_to_admin(self):
        """
        Verifica que la ruta `/AnalyticsIA/` responda HTTP 200 y cargue `analytics_data`
        sin errores cuando accede un Administrador.
        """
        self.client.force_login(self.admin)

        response = self.client.get(reverse('analytics_ia'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('error', response.context['analytics_data'])

    def test_technician_cannot_access_analytics(self):
        """
        Verifica que un usuario con rol exclusivamente Técnico (`tecnico=True, admin=False`)
        no pueda entrar a `/AnalyticsIA/` y sea redirigido a `/Inicio/<id>/`.
        """
        technician = self.create_user(
            'tech',
            'tech@example.com',
            tecnico=True,
        )
        self.client.force_login(technician)

        response = self.client.get(reverse('analytics_ia'))

        self.assertRedirects(response, reverse('inicio', args=[technician.id]))

    def test_index_admin_renders_real_dashboard_without_redirect_loop(self):
        """
        Garantiza que `/Administracion/` renderice el panel real con la tabla de tickets
        y que ya NO contenga el script `window.location.href = '/Administracion/'`
        que provocaba el bucle infinito diagnosticado en la PPT 5.
        """
        self.client.force_login(self.admin)

        response = self.client.get(reverse('administracion'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "window.location.href = '/Administracion/'")
        self.assertContains(response, self.question.Titulo)
        self.assertContains(response, 'Panel de Administración y Soporte')

    def test_admin_cannot_deactivate_or_demote_themselves(self):
        """
        Verifica que desde `/GestionUsuarios/`, un Administrador no pueda desmarcar
        su propio check `activo` ni su propio check `admin`.
        """
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion_usuarios'),
            {'Userid': self.admin.id, 'tecnico': 'on'},
        )

        self.assertRedirects(response, reverse('gestion_usuarios'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.activo)
        self.assertTrue(self.admin.admin)
