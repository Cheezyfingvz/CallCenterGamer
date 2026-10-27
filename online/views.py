"""
===============================================================================
VISTAS DEL PORTAL DEL CLIENTE Y AUTENTICACIÓN (online/views.py)
===============================================================================
Contiene los controladores (Views) de la aplicación principal `online`:
1. `Index`: Renderiza la portada pública (Landing Page).
2. `logout_view`: Cierra la sesión activa exigiendo petición HTTP POST (`@require_POST`).
3. `Inicio`: Panel personal del cliente autenticado. Permite buscar ayuda con el
   Asistente Virtual IA (GET `buscar_ayuda`), crear nuevos tickets clasificándolos
   automáticamente (POST) y listar el historial personal de consultas.
4. `ViewRespuestas`: Sala de chat de un ticket específico. Verifica que solo el
   autor del ticket, un técnico o un administrador puedan ver o responder el hilo.
5. `RegisterView` y `LoginView`: Vistas basadas en clases (CBV) para registro e
   inicio de sesión con redirección inteligente según el rol del usuario.
===============================================================================
"""
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView
from online.forms import RegisterForm, LoginForm, PreguntasForm, RespuestaForm
from online.ia_utils import AsistenteIA
from online.models import Preguntas, Usuario, Respuesta
from online.recomendaciones_ia import RecomendadorIA

# Logger estructurado para registrar eventos de negocio y seguridad en consola y archivo
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. VISTA DE PORTADA PÚBLICA (`Index`)
# ==============================================================================
def Index(request):
    """
    Renderiza la página de bienvenida (`index.html`).
    Recibe automáticamente la identidad visual `{{ brand }}` vía Context Processor.
    """
    return render(request, "index.html")


def PoliticaPrivacidad(request):
    """
    Renderiza la página informativa con las Políticas de Privacidad (`politica_privacidad.html`).
    Está disponible para todos los usuarios (Cliente, Técnico, Administrador y visitantes)
    desde el botón situado en el footer global de la plataforma.
    """
    return render(request, "politica_privacidad.html")


# ==============================================================================
# 2. VISTA DE CIERRE DE SESIÓN SEGURO (`logout_view`)
# ==============================================================================
@require_POST
def logout_view(request):
    """
    Cierra la sesión del usuario actual y redirige al formulario de Login.
    El decorador `@require_POST` bloquea peticiones GET (devolviendo HTTP 405)
    para evitar cierres de sesión accidentales o ataques CSRF por enlaces.
    """
    usuario_nombre = getattr(request.user, 'usuario', 'anonimo')
    logout(request)
    logger.info("Sesión cerrada correctamente para usuario=%s", usuario_nombre)
    return redirect('Login')


# ==============================================================================
# 3. VISTA DEL PANEL DEL CLIENTE (`Inicio`)
# ==============================================================================
@login_required
def Inicio(request, id):
    """
    Panel principal del cliente (`/Inicio/<id>/`).
    - Seguridad RBAC: Si un cliente intenta abrir el `/Inicio/<id>/` de otro
      usuario cambiando el número en la URL, es redirigido a su propio panel.
    - En GET con `?buscar_ayuda=...`: Consulta el motor híbrido (`AsistenteIA` +
      `RecomendadorIA`) y devuelve respuestas automáticas y tickets similares.
    - En POST: Valida `PreguntasForm`, asigna el usuario autenticado como autor,
      clasifica la categoría con IA y guarda el ticket en SQLite3.
    """
    try:
        User = Usuario.objects.get(id=id)
        # Bloquea acceso horizontal entre clientes distintos
        if request.user.id != User.id:
            return redirect('inicio', id=request.user.id)

        # Obtiene los tickets del usuario precargando el técnico asignado en una sola consulta
        preguntas = (
            Preguntas.objects.filter(Usuario=User)
            .select_related('tecnico_asignado')
            .order_by('-Fecha_creacion')
        )
        form = PreguntasForm()
        sugerencias_ia = None

        # --- Procesamiento del Buscador del Asistente Virtual IA (GET) ---
        buscar_ayuda = request.GET.get('buscar_ayuda', '').strip()
        if buscar_ayuda:
            try:
                asistente = AsistenteIA()
                recomendador = RecomendadorIA()
                # Genera diagnóstico automático (OpenAI o fallback local si no hay API Key)
                respuesta_auto = asistente.generar_respuesta_automatica(buscar_ayuda)
                # Busca hasta 3 tickets previos resueltos con similitud léxica
                recomendaciones = recomendador.recomendar_respuestas_similares(buscar_ayuda)
                sugerencias_ia = {
                    'consulta_original': buscar_ayuda,
                    'respuesta_automatica': respuesta_auto,
                    'recomendaciones': recomendaciones,
                }
            except Exception as e:
                logger.error("Error procesando buscar_ayuda en Inicio: %s", e, exc_info=True)
                sugerencias_ia = {
                    'consulta_original': buscar_ayuda,
                    'respuesta_automatica': (
                        "En este momento no pudimos procesar la sugerencia automática, "
                        "pero puedes crear tu pregunta en el formulario para que un técnico te asista."
                    ),
                    'recomendaciones': [],
                }

        # --- Procesamiento de Creación de Nuevo Ticket (POST) ---
        if request.method == "POST":
            form = PreguntasForm(request.POST)
            if form.is_valid():
                pregunta = form.save(commit=False)
                # Fija el autor desde la sesión activa (inmune a manipulaciones del cliente)
                pregunta.Usuario = User
                # Clasifica la categoría una sola vez al crear el ticket y la persiste en BD
                try:
                    asistente = AsistenteIA()
                    pregunta.categoria = asistente.clasificar_pregunta(
                        f"{pregunta.Titulo} {pregunta.Pregunta}"
                    )
                except Exception as e:
                    logger.warning("Fallback a categoría 'otros' al crear ticket: %s", e)
                    pregunta.categoria = 'otros'

                pregunta.save()
                logger.info(
                    "Ticket creado: id=%s autor=%s prioridad=%s categoria=%s",
                    pregunta.idPregunta,
                    User.usuario,
                    pregunta.prioridad,
                    pregunta.categoria,
                )
                return redirect('inicio', id=id)

        return render(request, "inicio.html", {
            "Preguntas": preguntas,
            "form": form,
            "id": id,
            "sugerencias_ia": sugerencias_ia,
        })
    except Usuario.DoesNotExist:
        return redirect('index')


# ==============================================================================
# 4. VISTA DE CONVERSACIÓN Y RESPUESTAS DE UN TICKET (`ViewRespuestas`)
# ==============================================================================
@login_required
def ViewRespuestas(request, idPregunta):
    """
    Muestra el detalle de un ticket y su hilo de mensajes (`/Respuesta/<idPregunta>/`).
    - Regla de autorización: Solo pueden acceder el cliente dueño del ticket
      (`request.user.id == pregunta.Usuario_id`), los técnicos (`request.user.tecnico`)
      o los administradores (`request.user.admin`). Cualquier otro usuario es
      redirigido a su propio panel `/Inicio/<id>/`.
    - En POST: Crea un nuevo mensaje `Respuesta` vinculando forzosamente la
      pregunta de la URL y el `request.user` autenticado.
    """
    try:
        pregunta = Preguntas.objects.select_related('Usuario', 'tecnico_asignado').get(
            idPregunta=idPregunta
        )
        # Verificación estricta de permisos en backend
        if not (
            request.user.id == pregunta.Usuario_id
            or request.user.admin
            or request.user.tecnico
        ):
            logger.warning(
                "Acceso denegado a ticket id=%s para usuario=%s",
                idPregunta,
                request.user.usuario,
            )
            return redirect('inicio', id=request.user.id)

        now = timezone.now()
        # Obtiene todas las respuestas del ticket junto con sus autores en una sola consulta SQL
        MostrarRespuestas = (
            Respuesta.objects.filter(id_Pregunta=pregunta)
            .select_related('Usuario')
            .order_by('FechaHora')
        )

        form = RespuestaForm()

        if request.method == "POST":
            form = RespuestaForm(request.POST)
            if form.is_valid():
                respuesta = form.save(commit=False)
                # Asigna la pregunta de la URL y el usuario de la sesión (previene ID Spoofing)
                respuesta.id_Pregunta = pregunta
                respuesta.Usuario = request.user
                respuesta.FechaHora = now
                respuesta.save()
                logger.info(
                    "Nueva respuesta registrada en ticket id=%s por usuario=%s",
                    idPregunta,
                    request.user.usuario,
                )
                return redirect('respuestas', idPregunta=idPregunta)

        # Si quien visualiza el ticket es Técnico o Administrador, genera sugerencia
        # de respuesta asistida por IA para agilizar la atención.
        sugerencia_ia = None
        if request.user.admin or request.user.tecnico:
            try:
                asistente = AsistenteIA()
                sugerencia_ia = asistente.generar_respuesta_automatica(
                    f"{pregunta.Titulo}: {pregunta.Pregunta}"
                )
            except Exception as e:
                logger.warning("No se pudo generar sugerencia IA en ViewRespuestas: %s", e)

        return render(request, "Respuestas.html", {
            "Pregunta": pregunta,
            "form": form,
            "Respuestas": MostrarRespuestas,
            "sugerencia_ia": sugerencia_ia,
        })
    except Preguntas.DoesNotExist:
        return redirect('index')


# ==============================================================================
# 5. VISTAS BASADAS EN CLASES PARA REGISTRO E INICIO DE SESIÓN
# ==============================================================================
class RegisterView(CreateView):
    """
    Vista basada en clase (`CreateView`) para el registro de nuevos usuarios en `/Register/`.
    Si el formulario es válido, crea el usuario, inicia su sesión automáticamente
    y lo redirige a `/Administracion/` (si es staff) o a `/Inicio/<id>/` (si es cliente).
    """
    form_class = RegisterForm
    template_name = 'register.html'
    success_url = '/'

    def form_valid(self, form):
        request = self.request
        user = form.save()
        login(request, user)
        logger.info("Nuevo usuario registrado y autenticado: usuario=%s", user.usuario)
        if user.admin or user.tecnico:
            return redirect('administracion')
        return redirect('inicio', id=user.id)


class LoginView(FormView):
    """
    Vista basada en clase (`FormView`) para autenticar usuarios en `/Login/`.
    - Verifica credenciales con `authenticate()` (que además comprueba `user.is_active`).
    - Si `remember_me` está desmarcado, configura la sesión para expirar al cerrar
      el navegador (`set_expiry(0)`).
    - Redirige a `/Administracion/` para administradores y técnicos, o a `/Inicio/<id>/`
      para clientes estándar.
    """
    form_class = LoginForm
    template_name = 'login.html'
    success_url = '/'

    def form_valid(self, form):
        request = self.request
        usuario = form.cleaned_data.get("Usuario")
        password = form.cleaned_data.get("password")
        remember_me = form.cleaned_data['remember_me']

        user = authenticate(request, username=usuario, password=password)
        if user is not None:
            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            logger.info("Inicio de sesión exitoso: usuario=%s", user.usuario)
            if user.admin or user.tecnico:
                return redirect('administracion')
            return redirect('inicio', id=user.id)

        logger.warning("Intento de inicio de sesión fallido para usuario=%s", usuario)
        form.add_error(None, "Usuario o contraseña incorrectos.")
        return super().form_invalid(form)
