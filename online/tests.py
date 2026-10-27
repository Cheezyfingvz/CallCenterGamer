"""
===============================================================================
SUITE DE PRUEBAS AUTOMATIZADAS DE LA APP ONLINE (online/tests.py)
===============================================================================
Propósito:
    Verifica de forma automatizada la seguridad, integridad de datos, formularios,
    resiliencia de Inteligencia Artificial, sistema White-Label y semillas de datos:
    1. ConversationAccessTests: Control de acceso por propietario/rol (IDOR fix),
       protección contra manipulación de campos ocultos, login de inactivos y POST en logout.
    2. TicketModelTests: Valores por defecto de la Mejora 1 (estado, prioridad,
       categoría, técnico asignado) y comportamiento `SET_NULL` al borrar técnicos.
    3. TicketFormTests: Validación de `PreguntasForm`, `RespuestaForm` y `TicketAdminForm`.
    4. AIResilienceAndAssistantTests: Fallback sin `OPENAI_API_KEY` (Mejora 2) y
       buscador interactivo `buscar_ayuda` en `/Inicio/<id>/`.
    5. WhiteLabelAndSeedTests: Inyección de marca por Context Processor (Fase 5)
       e idempotencia del comando `seed_initial_data` (Fase 6).
===============================================================================
"""

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from online.forms import PreguntasForm, RespuestaForm, TicketAdminForm
from online.ia_utils import AsistenteIA
from online.models import Preguntas, Respuesta, Usuario


class ConversationAccessTests(TestCase):
    """
    Pruebas de seguridad y control de acceso en las conversaciones de soporte (`/Respuesta/<id>/`),
    cierre de sesión por POST y bloqueo de acceso a cuentas desactivadas.
    """

    def setUp(self):
        """
        Prepara dos usuarios clientes (`owner` y `other`) y un ticket perteneciente a `owner`.
        """
        self.owner = self.create_user('owner', 'owner@example.com')
        self.other = self.create_user('other', 'other@example.com')
        self.question = Preguntas.objects.create(
            Titulo='Consulta',
            Pregunta='No inicia el juego',
            Fecha_creacion=timezone.now(),
            Usuario=self.owner,
        )

    def create_user(self, username, email, **fields):
        """
        Helper auxiliar para crear usuarios de prueba con contraseña cifrada válida.
        """
        user = Usuario.objects.create(
            usuario=username,
            correo=email,
            **fields,
        )
        user.set_password('test-password-123')
        user.save()
        return user

    def test_user_cannot_view_another_users_conversation(self):
        """
        Verifica que un cliente (`other`) NO pueda espiar el hilo de otro usuario (`owner`)
        y sea redirigido de inmediato a su propio panel `/Inicio/<id>/`.
        """
        self.client.force_login(self.other)

        # La URL ya no lleva idUser: solo el id de la pregunta.
        response = self.client.get(
            reverse('respuestas', args=[self.question.idPregunta])
        )

        self.assertRedirects(response, reverse('inicio', args=[self.other.id]))

    def test_admin_and_technician_can_view_conversations(self):
        """
        Comprueba que tanto los Administradores como los Técnicos de soporte
        puedan abrir y atender cualquier hilo de conversación (HTTP 200).
        """
        for username, email, role in (
            ('admin', 'admin@example.com', {'admin': True}),
            ('tech', 'tech@example.com', {'tecnico': True}),
        ):
            with self.subTest(role=username):
                user = self.create_user(username, email, **role)
                self.client.force_login(user)
                response = self.client.get(
                    reverse('respuestas', args=[self.question.idPregunta])
                )
                self.assertEqual(response.status_code, 200)

    def test_reply_uses_url_question_not_tampered_hidden_question(self):
        """
        Garantiza que si un atacante envía campos ocultos manipulados (`id_Pregunta`,
        `Usuario`) en el POST de respuesta, el servidor los ignore y asocie la respuesta
        al ticket de la URL y al usuario de la sesión autenticada.
        """
        another_question = Preguntas.objects.create(
            Titulo='Otra consulta',
            Pregunta='No hay audio',
            Fecha_creacion=timezone.now(),
            Usuario=self.other,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('respuestas', args=[self.question.idPregunta]),
            {
                'Respuesta': 'Prueba reiniciar el juego.',
                # Campos manipulados: el formulario ya no los acepta y la vista
                # usa la pregunta de la URL y el usuario de la sesion.
                'id_Pregunta': another_question.idPregunta,
                'Usuario': self.other.id,
                'FechaHora': timezone.now().isoformat(),
            },
        )

        self.assertRedirects(
            response,
            f'/Respuesta/{self.question.idPregunta}/',
        )
        respuesta = Respuesta.objects.get()
        self.assertEqual(respuesta.id_Pregunta_id, self.question.idPregunta)
        self.assertEqual(respuesta.Usuario_id, self.owner.id)

    def test_response_url_no_longer_accepts_user_id_segment(self):
        """
        Verifica que la antigua ruta insegura `/Respuesta/<idUser>/<idPregunta>/`
        ya no exista y devuelva HTTP 404.
        """
        self.client.force_login(self.owner)

        response = self.client.get(
            f'/Respuesta/{self.owner.id}/{self.question.idPregunta}/'
        )

        self.assertEqual(response.status_code, 404)

    def test_logout_requires_post(self):
        """
        Verifica que la vista `Logout` rechace peticiones GET con HTTP 405
        (Method Not Allowed) para prevenir cierres de sesión forzados por CSRF.
        """
        self.client.force_login(self.owner)

        response = self.client.get(reverse('Logout'))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(self.client.session.get('_auth_user_id'))

    def test_inactive_users_cannot_log_in(self):
        """
        Comprueba que un usuario con `activo=False` no pueda iniciar sesión
        aunque ingrese su contraseña correcta.
        """
        self.owner.activo = False
        self.owner.save()

        response = self.client.post(
            reverse('Login'),
            {'Usuario': self.owner.usuario, 'password': 'test-password-123'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        self.assertTrue(response.context['form'].non_field_errors())


class TicketModelTests(TestCase):
    """
    Pruebas unitarias para la Mejora 1 (Evolución del modelo `Preguntas` a sistema
    de tickets con `estado`, `prioridad`, `categoria` y `tecnico_asignado`).
    """

    def setUp(self):
        """
        Crea un usuario cliente y un usuario técnico para probar las relaciones del ticket.
        """
        self.client_user = Usuario.objects.create(usuario='cliente', correo='c@example.com')
        self.tech = Usuario.objects.create(usuario='tecnico', correo='t@example.com', tecnico=True)

    def test_new_ticket_has_sensible_defaults(self):
        """
        Verifica que todo ticket recién creado reciba automáticamente:
        estado='abierto', prioridad='media', categoria='otros', tecnico_asignado=None
        y Fecha_creacion igual al timestamp actual.
        """
        before = timezone.now()
        ticket = Preguntas.objects.create(
            Titulo='Lag', Pregunta='Mucho lag', Usuario=self.client_user
        )

        self.assertEqual(ticket.estado, 'abierto')
        self.assertEqual(ticket.prioridad, 'media')
        self.assertEqual(ticket.categoria, 'otros')
        self.assertIsNone(ticket.tecnico_asignado)
        # Fecha_creacion se completa sola cuando no se envia.
        self.assertGreaterEqual(ticket.Fecha_creacion, before)

    def test_deleting_assigned_technician_keeps_the_ticket(self):
        """
        Verifica que si se elimina la cuenta del técnico asignado, el ticket NO se borre
        en cascada, sino que su campo `tecnico_asignado` pase a `NULL` (`on_delete=SET_NULL`).
        """
        ticket = Preguntas.objects.create(
            Titulo='Lag', Pregunta='Mucho lag', Usuario=self.client_user,
            tecnico_asignado=self.tech,
        )

        self.tech.delete()

        ticket.refresh_from_db()
        self.assertIsNone(ticket.tecnico_asignado)

    def test_user_reverse_relation_is_named_preguntas(self):
        """
        Comprueba que la relación inversa desde `Usuario` hacia `Preguntas`
        esté accesible mediante `usuario.preguntas`.
        """
        Preguntas.objects.create(Titulo='A', Pregunta='a', Usuario=self.client_user)

        self.assertEqual(self.client_user.preguntas.count(), 1)


class TicketFormTests(TestCase):
    """
    Pruebas de validación de formularios (`PreguntasForm`, `RespuestaForm` y `TicketAdminForm`).
    """

    def setUp(self):
        """
        Crea un cliente propietario, un administrador, otro cliente sin rol y un ticket base.
        """
        self.owner = Usuario.objects.create(usuario='owner', correo='o@example.com')
        self.admin = Usuario.objects.create(usuario='admin', correo='a@example.com', admin=True)
        self.client_only = Usuario.objects.create(usuario='plain', correo='p@example.com')
        self.ticket = Preguntas.objects.create(
            Titulo='Consulta', Pregunta='No inicia', Usuario=self.owner
        )

    def test_client_forms_do_not_expose_hidden_or_management_fields(self):
        """
        Verifica que los formularios de cliente expongan únicamente los campos seguros
        permitidos y ningún campo administrativo ni oculto.
        """
        self.assertEqual(
            list(PreguntasForm().fields), ['Titulo', 'Pregunta', 'prioridad']
        )
        self.assertEqual(list(RespuestaForm().fields), ['Respuesta'])

    def test_client_creates_ticket_without_hidden_fields(self):
        """
        Comprueba que al enviar un ticket desde `/Inicio/<id>/`, el servidor asigne
        automáticamente el autor, el estado inicial 'abierto' y clasifique la categoría.
        """
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('inicio', args=[self.owner.id]),
            {'Titulo': 'Sin sonido', 'Pregunta': 'No hay audio en auriculares', 'prioridad': 'alta'},
        )

        self.assertRedirects(
            response, reverse('inicio', args=[self.owner.id])
        )
        ticket = Preguntas.objects.get(Titulo='Sin sonido')
        self.assertEqual(ticket.Usuario_id, self.owner.id)
        self.assertEqual(ticket.prioridad, 'alta')
        self.assertEqual(ticket.estado, 'abierto')
        self.assertEqual(ticket.categoria, 'hardware')

    def test_client_cannot_set_state_or_assign_technician_via_post(self):
        """
        Verifica que si un cliente intenta inyectar `estado='cerrado'` o `tecnico_asignado`
        en el POST de creación, estos sean ignorados.
        """
        self.client.force_login(self.owner)

        self.client.post(
            reverse('inicio', args=[self.owner.id]),
            {
                'Titulo': 'Intento', 'Pregunta': 'x', 'prioridad': 'baja',
                'estado': 'cerrado', 'tecnico_asignado': self.admin.id,
            },
        )

        ticket = Preguntas.objects.get(Titulo='Intento')
        self.assertEqual(ticket.estado, 'abierto')
        self.assertIsNone(ticket.tecnico_asignado)

    def test_ticket_admin_form_only_offers_staff_as_assignees(self):
        """
        Comprueba que el desplegable `tecnico_asignado` de `TicketAdminForm` solo incluya
        usuarios con rol técnico o administrador activos, excluyendo clientes normales.
        """
        queryset = TicketAdminForm(instance=self.ticket).fields['tecnico_asignado'].queryset

        self.assertIn(self.admin, queryset)
        self.assertNotIn(self.client_only, queryset)

    def test_ticket_admin_form_rejects_unknown_category(self):
        """
        Verifica que `TicketAdminForm` rechace categorías no definidas en el catálogo oficial.
        """
        form = TicketAdminForm(
            {'Titulo': 'T', 'Pregunta': 'P', 'estado': 'abierto',
             'prioridad': 'media', 'categoria': 'inexistente'},
            instance=self.ticket,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('categoria', form.errors)

    def test_admin_updates_ticket_management_fields(self):
        """
        Comprueba que el administrador pueda actualizar estado, prioridad, categoría
        y técnico asignado desde `/ModificarPregunta/<id>/` sin alterar el autor original.
        """
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('modificar_pregunta', args=[self.ticket.idPregunta]),
            {
                'Titulo': 'Consulta', 'Pregunta': 'No inicia',
                'estado': 'en_proceso', 'prioridad': 'critica',
                'categoria': 'hardware', 'tecnico_asignado': self.admin.id,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, 'en_proceso')
        self.assertEqual(self.ticket.prioridad, 'critica')
        self.assertEqual(self.ticket.categoria, 'hardware')
        self.assertEqual(self.ticket.tecnico_asignado_id, self.admin.id)
        # El autor no cambia al editar.
        self.assertEqual(self.ticket.Usuario_id, self.owner.id)


class AIResilienceAndAssistantTests(TestCase):
    """
    Pruebas para la Mejora 2 (Resiliencia de `AsistenteIA` con fallback local cuando
    no hay `OPENAI_API_KEY`) y buscador de ayuda instantánea en `Inicio`.
    """

    def setUp(self):
        self.owner = Usuario.objects.create(usuario='gamer1', correo='g1@example.com')
        self.owner.set_password('test-password-123')
        self.owner.save()

    @override_settings(OPENAI_API_KEY='')
    def test_asistente_ia_fallback_without_api_key_never_exposes_errors(self):
        """
        Garantiza que cuando `OPENAI_API_KEY` está vacía, `AsistenteIA` clasifique
        y responda mediante el motor heurístico local sin exponer textos de error.
        """
        asistente = AsistenteIA()
        categoria = asistente.clasificar_pregunta('Tengo mucho ping y desconexiones de internet')
        respuesta = asistente.generar_respuesta_automatica('Mi tarjeta grafica calienta mucho')

        self.assertEqual(categoria, 'conexion')
        self.assertNotIn('Error:', respuesta)
        self.assertNotIn('OPENAI_API_KEY', respuesta)
        self.assertIn('Diagnóstico preliminar', respuesta)

    @override_settings(OPENAI_API_KEY='')
    def test_inicio_search_assistant_populates_sugerencias_ia(self):
        """
        Verifica que al consultar `?buscar_ayuda=...` en `/Inicio/<id>/`, la vista
        inyecte el diccionario `sugerencias_ia` con diagnóstico y recomendaciones.
        """
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse('inicio', args=[self.owner.id]),
            {'buscar_ayuda': 'problema con internet y lag'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['sugerencias_ia'])
        self.assertEqual(
            response.context['sugerencias_ia']['consulta_original'],
            'problema con internet y lag',
        )
        self.assertTrue(response.context['sugerencias_ia']['respuesta_automatica'])


class WhiteLabelAndSeedTests(TestCase):
    """
    Pruebas para la Fase 5 (Parametrización White-Label Multi-Empresa) y
    Fase 6 (Comando idempotente de carga inicial `seed_initial_data`).
    """

    @override_settings(
        BRAND_CONFIG={
            'NAME': 'ClinicaSoporteTI',
            'WELCOME_TITLE': 'Bienvenido a Clínica Soporte TI',
            'SLOGAN': 'Soporte médico informático 24/7',
            'ICON_CLASS': 'fas fa-laptop-medical',
            'PRIMARY_COLOR': '#0f766e',
            'SECONDARY_COLOR': '#115e59',
            'ACCENT_COLOR': '#14b8a6',
        }
    )
    def test_white_label_context_processor_injects_custom_brand(self):
        """
        Comprueba que al cambiar `BRAND_CONFIG` (por ejemplo, a una clínica médica),
        la portada y el header actualicen automáticamente el nombre, eslogan, ícono y
        variables CSS `:root` sin tocar el código HTML.
        """
        response = self.client.get(reverse('index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ClinicaSoporteTI')
        self.assertContains(response, 'Bienvenido a Clínica Soporte TI')
        self.assertContains(response, 'fas fa-laptop-medical')
        self.assertContains(response, '--brand-primary: #0f766e;')

    def test_seed_initial_data_is_idempotent_and_creates_roles_and_tickets(self):
        """
        Verifica que ejecutar `python manage.py seed_initial_data` múltiples veces
        seguidas cree exactamente los 3 usuarios base por defecto (admin, tecnico, usuario)
        con sus correos y contraseñas solicitadas y los 6 tickets de demostración
        sin duplicar registros ni lanzar errores de integridad.
        """
        call_command('seed_initial_data')
        call_command('seed_initial_data')

        admin_user = Usuario.objects.get(usuario='admin', correo='admin@gmail.com', admin=True, tecnico=True)
        tech_user = Usuario.objects.get(usuario='tecnico', correo='tecnico@gmail.com', tecnico=True, admin=False)
        normal_user = Usuario.objects.get(usuario='usuario', correo='usuario@gmail.com', admin=False, tecnico=False)

        self.assertTrue(admin_user.check_password('admin123'))
        self.assertTrue(tech_user.check_password('tecnico123'))
        self.assertTrue(normal_user.check_password('usuario123'))
        self.assertEqual(Preguntas.objects.count(), 6)

    def test_privacy_policy_view_and_footer_button(self):
        """
        Verifica que el botón de Políticas de Privacidad esté presente en el footer
        global de la aplicación y que la vista `/PoliticaPrivacidad/` responda HTTP 200.
        """
        index_response = self.client.get(reverse('index'))
        self.assertEqual(index_response.status_code, 200)
        self.assertContains(index_response, reverse('politica_privacidad'))
        self.assertContains(index_response, 'Políticas de Privacidad')

        privacy_response = self.client.get(reverse('politica_privacidad'))
        self.assertEqual(privacy_response.status_code, 200)
        self.assertContains(privacy_response, '1. Datos que recopilamos')
        self.assertContains(privacy_response, '2. Uso de la información e IA')
