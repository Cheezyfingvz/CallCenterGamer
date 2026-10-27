"""
===============================================================================
VISTAS DEL MÓDULO ADMINISTRATIVO Y TÉCNICO (administracion/views.py)
===============================================================================
Propósito:
    Controla todas las pantallas y operaciones de gestión interna del sistema:
    1. IndexAdmin: Dashboard operativo para Administradores y Técnicos con
       métricas en tiempo real, alertas y tabla filtrable de tickets.
    2. BorrarPregunta: Eliminación segura de tickets (exclusivo Admin por POST).
    3. GestionUsuarios: Administración de roles (admin, técnico, activo) con
       protección contra autodegradación/autodesactivación y optimización N+1.
    4. EliminarUsuario: Baja definitiva de cuentas de usuario (protegido por POST).
    5. ModificarPregunta: Edición integral de tickets (Estado, Prioridad,
       Categoría, Técnico Asignado) asistida por Inteligencia Artificial.
    6. AnalyticsIA: Tablero gerencial de analítica histórica y SLA (exclusivo Admin).
===============================================================================
"""

from collections import Counter
from datetime import timedelta
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Min
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from online.forms import TicketAdminForm
from online.ia_utils import AsistenteIA
from online.models import Preguntas, Usuario
from online.recomendaciones_ia import RecomendadorIA

# Logger estructurado que envía eventos a consola y a logs/callcenter.log
logger = logging.getLogger(__name__)


@login_required
def IndexAdmin(request):
    """
    Vista principal del panel de administración y soporte técnico (/Administracion/).

    Control de Acceso (RBAC):
        Permite el ingreso únicamente a usuarios con flag `admin=True` o `tecnico=True`.
        Si un cliente regular intenta entrar, es redirigido a su panel `/Inicio/<id>/`.

    Optimización de Base de Datos (Solución al problema N+1):
        Utiliza `select_related('Usuario', 'tecnico_asignado')` para traer los datos
        del autor y del técnico en un solo JOIN SQL, y `annotate(num_respuestas=Count('respuesta'))`
        para contar las respuestas sin lanzar subconsultas por cada fila de la tabla.
        Además, lee la categoría ya persistida en `pregunta.categoria` en vez de
        invocar a OpenAI en cada recarga del navegador.
    """
    # 1. Verificación de permisos de rol (Administrador o Técnico)
    if not (request.user.admin or request.user.tecnico):
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('inicio', id=request.user.id)

    # 2. QuerySet base optimizado con JOINs (select_related) y agregación SQL (annotate)
    base_qs = (
        Preguntas.objects.select_related('Usuario', 'tecnico_asignado')
        .annotate(num_respuestas=Count('respuesta'))
        .order_by('-Fecha_creacion')
    )

    # 3. Aplicación de filtros opcionales recibidos por querystring (?estado=...&prioridad=...)
    estado_filtro = request.GET.get('estado', '').strip()
    prioridad_filtro = request.GET.get('prioridad', '').strip()
    ListaPreguntas = base_qs
    if estado_filtro:
        ListaPreguntas = ListaPreguntas.filter(estado=estado_filtro)
    if prioridad_filtro:
        ListaPreguntas = ListaPreguntas.filter(prioridad=prioridad_filtro)

    # Estructuras para alimentar las tarjetas de métricas y alertas del dashboard
    tendencias_ia = []
    estadisticas_ia = {}
    alertas_ia = []

    try:
        # 4. Cálculo de actividad de los últimos 7 días
        hace_una_semana = timezone.now() - timedelta(days=7)
        preguntas_recientes = list(base_qs.filter(Fecha_creacion__gte=hace_una_semana)[:10])
        preguntas_semana = base_qs.filter(Fecha_creacion__gte=hace_una_semana).count()

        # Construye la lista de tendencias leyendo la categoría almacenada en BD
        for pregunta in preguntas_recientes:
            categoria = pregunta.categoria or 'otros'
            tendencias_ia.append({
                'id': pregunta.idPregunta,
                'titulo': pregunta.Titulo,
                'categoria': categoria,
                'usuario': pregunta.Usuario.usuario,
                'fecha': pregunta.Fecha_creacion,
            })

        # 5. Cálculo de KPIs globales (Total, Sin Respuesta y % de Resolución)
        total_preguntas = base_qs.count()
        preguntas_sin_respuesta = base_qs.filter(respuesta__isnull=True).count()
        porcentaje_resueltas = (
            ((total_preguntas - preguntas_sin_respuesta) / total_preguntas) * 100
            if total_preguntas > 0
            else 0.0
        )

        estadisticas_ia = {
            'total_preguntas': total_preguntas,
            'preguntas_sin_respuesta': preguntas_sin_respuesta,
            'porcentaje_resueltas': porcentaje_resueltas,
            'tendencia_semanal': preguntas_semana,
        }

        # 6. Generación de alertas operativas automáticas según umbrales de carga
        if preguntas_sin_respuesta > 5:
            alertas_ia.append({
                'tipo': 'warning',
                'mensaje': f'⚠️ Hay {preguntas_sin_respuesta} preguntas sin respuesta',
                'prioridad': 'alta',
            })
        if preguntas_semana > 20:
            alertas_ia.append({
                'tipo': 'info',
                'mensaje': '📈 Alta actividad esta semana',
                'prioridad': 'media',
            })
    except Exception as e:
        # En caso de cualquier fallo inesperado en métricas, registra el error y mantiene vivo el panel
        logger.error("Error en cálculo de métricas de IndexAdmin: %s", e, exc_info=True)
        estadisticas_ia = {
            'total_preguntas': base_qs.count(),
            'preguntas_sin_respuesta': base_qs.filter(respuesta__isnull=True).count(),
            'porcentaje_resueltas': 0.0,
            'tendencia_semanal': 0,
            'error_ia': True,
        }

    # 7. Renderiza la plantilla indexAdmin.html con todos los tickets, filtros y KPIs
    return render(request, "indexAdmin.html", {
        "Preguntas": ListaPreguntas,
        "tendencias_ia": tendencias_ia,
        "estadisticas_ia": estadisticas_ia,
        "alertas_ia": alertas_ia,
        "estado_filtro": estado_filtro,
        "prioridad_filtro": prioridad_filtro,
        "estados_choices": Preguntas.ESTADO_CHOICES,
        "prioridades_choices": Preguntas.PRIORIDAD_CHOICES,
    })


@login_required
@require_POST
def BorrarPregunta(request, idUser, idPregunta):
    """
    Vista para eliminar permanentemente un ticket de soporte.

    Seguridad:
        - `@require_POST`: Impide que una petición GET borre registros accidentalmente.
        - Verifica `request.user.admin` desde la sesión autenticada, ignorando
          cualquier intento de falsificar el `idUser` en la URL.
    """
    # Solo un administrador puede eliminar tickets
    if not request.user.admin:
        if request.user.tecnico:
            return redirect('administracion')
        return redirect('inicio', id=request.user.id)

    # Busca el ticket por su clave primaria idPregunta
    try:
        pregunta = Preguntas.objects.get(idPregunta=idPregunta)
    except Preguntas.DoesNotExist:
        messages.error(request, "La pregunta o usuario no existe.")
        return redirect('administracion')

    # Guarda el título para dejar trazabilidad en el archivo de auditoría antes de borrar
    titulo_borrado = pregunta.Titulo
    pregunta.delete()
    logger.info(
        "Ticket eliminado: id=%s titulo='%s' por admin=%s",
        idPregunta,
        titulo_borrado,
        request.user.usuario,
    )
    messages.success(request, "Pregunta eliminada correctamente.")
    return redirect('administracion')


@login_required
def GestionUsuarios(request):
    """
    Vista para listar y actualizar permisos de usuarios (/GestionUsuarios/).

    Seguridad y Reglas de Negocio:
        - Exclusiva para usuarios con `request.user.admin == True`.
        - Impide que el administrador con sesión activa desactive su propia cuenta
          o se quite a sí mismo el permiso `admin` (evita bloqueo total del sistema).

    Optimización de Consultas:
        - Usa `prefetch_related('preguntas')` y `annotate(num_preguntas=Count('preguntas'))`
          para resolver la tabla completa de usuarios y su historial en solo 2 consultas SQL.
    """
    # 1. Validación estricta de rol Administrador
    if not request.user.admin:
        messages.error(request, "No tienes permisos de administrador.")
        return redirect('inicio', id=request.user.id)

    # 2. Procesamiento de cambios de rol/estado cuando se envía el formulario por POST
    if request.method == "POST":
        user_id = request.POST.get('Userid')
        activo = request.POST.get('activo') == 'on'
        admin = request.POST.get('admin') == 'on'
        tecnico = request.POST.get('tecnico') == 'on'

        try:
            userchange = Usuario.objects.get(id=user_id)

            # Protección crítica: un administrador no puede desactivarse ni quitarse
            # el rol de administrador a sí mismo.
            if userchange.id == request.user.id and (not activo or not admin):
                logger.warning(
                    "Intento bloqueado de autodesactivación/autodegradación por admin=%s",
                    request.user.usuario,
                )
                messages.error(
                    request,
                    "No puedes desactivar tu propia cuenta ni quitarte permisos de administrador.",
                )
                return redirect('gestion_usuarios')

            # Detecta qué atributos cambiaron para registrarlos en el log de auditoría
            cambios = []
            if userchange.admin != admin:
                cambios.append(f"Admin: {userchange.admin} -> {admin}")
            if userchange.tecnico != tecnico:
                cambios.append(f"Técnico: {userchange.tecnico} -> {tecnico}")
            if userchange.activo != activo:
                cambios.append(f"Activo: {userchange.activo} -> {activo}")

            # Actualiza y guarda los flags booleanos en la base de datos
            userchange.admin = admin
            userchange.activo = activo
            userchange.tecnico = tecnico
            userchange.save()

            if cambios:
                logger.info(
                    "Cambio de roles/estado en usuario=%s por admin=%s: %s",
                    userchange.usuario,
                    request.user.usuario,
                    ", ".join(cambios),
                )

            messages.success(request, f"Usuario {userchange.usuario} actualizado correctamente.")
            return redirect('gestion_usuarios')

        except Usuario.DoesNotExist:
            messages.error(request, "El usuario no existe.")
            return redirect('gestion_usuarios')

    # 3. Consulta GET optimizada: obtiene usuarios y sus preguntas en 2 queries totales (sin N+1)
    Usuarios = (
        Usuario.objects.prefetch_related('preguntas')
        .annotate(num_preguntas=Count('preguntas'))
        .order_by('id')
    )

    analisis_usuarios = []
    hace_una_semana = timezone.now() - timedelta(days=7)

    # 4. Calcula el resumen de actividad y categoría más frecuente por cada usuario en memoria
    for usuario in Usuarios:
        preguntas_usuario = list(usuario.preguntas.all())
        total_preguntas = len(preguntas_usuario)

        categorias_usuario = [
            (p.categoria or 'otros') for p in preguntas_usuario[:5]
        ]
        categoria_principal = "sin preguntas"
        if categorias_usuario:
            categoria_principal = Counter(categorias_usuario).most_common(1)[0][0]

        analisis_usuarios.append({
            'usuario_id': usuario.id,
            'total_preguntas': total_preguntas,
            'categoria_principal': categoria_principal,
            'actividad_reciente': (
                usuario.last_login is not None
                and usuario.last_login >= hace_una_semana
            ),
        })

    return render(request, "GestionUsuarios.html", {
        "Usuarios": Usuarios,
        "analisis_usuarios": analisis_usuarios,
    })


@login_required
@require_POST
def EliminarUsuario(request, idUser):
    """
    Vista para eliminar un usuario del sistema (/EliminarUsuario/<idUser>/).

    Seguridad:
        - Requiere método HTTP POST (`@require_POST`).
        - Exclusivo para Administradores (`request.user.admin`).
        - Bloquea la autoeliminación (`User.id == request.user.id`).
    """
    if request.user.admin:
        try:
            User = Usuario.objects.get(id=idUser)
            # Evita que el administrador borre su propia cuenta activa
            if User.id == request.user.id:
                logger.warning(
                    "Intento bloqueado de autoeliminación por admin=%s",
                    request.user.usuario,
                )
                messages.error(request, "No puedes eliminar tu propia cuenta.")
                return redirect('gestion_usuarios')

            usuario_eliminado = User.usuario
            User.delete()
            logger.info(
                "Usuario eliminado: usuario=%s por admin=%s",
                usuario_eliminado,
                request.user.usuario,
            )
            messages.success(request, f"Usuario {usuario_eliminado} eliminado correctamente.")

        except Usuario.DoesNotExist:
            messages.error(request, "El usuario no existe.")
    else:
        messages.error(request, "No tienes permisos para realizar esta acción.")

    return redirect('gestion_usuarios')


@login_required
def ModificarPregunta(request, idPregunta):
    """
    Vista administrativa para editar integralmente un ticket (/ModificarPregunta/<idPregunta>/).

    Permite modificar:
        - Título y descripción de la consulta.
        - Estado del ciclo de vida (abierto, en_proceso, resuelto, cerrado).
        - Nivel de prioridad (baja, media, alta, critica).
        - Categoría temática y Técnico Asignado (validado por `TicketAdminForm`).
    Además, presenta en pantalla sugerencias de diagnóstico generadas por `AsistenteIA`
    y casos históricos similares provistos por `RecomendadorIA`.
    """
    # 1. Verificación de rol Administrador
    if not request.user.admin:
        messages.error(request, "No tienes permisos de administrador.")
        return redirect('inicio', id=request.user.id)

    try:
        # 2. Obtiene el ticket junto con su autor y técnico en una sola consulta SQL
        Pregunta = Preguntas.objects.select_related('Usuario', 'tecnico_asignado').get(
            idPregunta=idPregunta
        )
        sugerencias_ia = []
        categoria_ia = Pregunta.categoria or "otros"
        preguntas_similares = []

        asistente_ia = AsistenteIA()
        recomendador_ia = RecomendadorIA()

        # 3. Si es una petición POST, valida y guarda los cambios mediante TicketAdminForm
        if request.method == 'POST':
            form = TicketAdminForm(request.POST, instance=Pregunta)
            if form.is_valid():
                pregunta_actualizada = form.save(commit=False)
                # Preserva de forma inmutable el autor original y la fecha de creación
                pregunta_actualizada.Usuario = Pregunta.Usuario
                pregunta_actualizada.Fecha_creacion = Pregunta.Fecha_creacion

                # Si la categoría quedó vacía, clasificar automáticamente con IA/heurística
                if not pregunta_actualizada.categoria:
                    pregunta_actualizada.categoria = asistente_ia.clasificar_pregunta(
                        pregunta_actualizada.Pregunta
                    )

                pregunta_actualizada.save()
                logger.info(
                    "Ticket modificado: id=%s estado=%s prioridad=%s categoria=%s tecnico=%s por admin=%s",
                    pregunta_actualizada.idPregunta,
                    pregunta_actualizada.estado,
                    pregunta_actualizada.prioridad,
                    pregunta_actualizada.categoria,
                    pregunta_actualizada.tecnico_asignado_id,
                    request.user.usuario,
                )
                messages.success(request, "Pregunta modificada correctamente.")
                return redirect('administracion')
            else:
                messages.error(request, "Error en el formulario. Verifica los datos.")
        else:
            # Petición GET: inicializa el formulario con los datos actuales del ticket
            form = TicketAdminForm(instance=Pregunta)

        # 4. Análisis de asistencia IA al cargar la vista de edición
        try:
            categoria_ia = Pregunta.categoria or asistente_ia.clasificar_pregunta(Pregunta.Pregunta)
            preguntas_similares = recomendador_ia.recomendar_respuestas_similares(Pregunta.Pregunta)

            sugerencia_prompt = (
                f"Analiza este ticket de soporte ({categoria_ia}): "
                f"Título: {Pregunta.Titulo}. Descripción: {Pregunta.Pregunta}. "
                f"Sugiere cómo mejorar su claridad y diagnóstico."
            )
            respuesta_ia = asistente_ia.generar_respuesta_automatica(sugerencia_prompt)
            if "{" in respuesta_ia and "}" in respuesta_ia:
                try:
                    sugerencias_ia = json.loads(respuesta_ia)
                except json.JSONDecodeError:
                    sugerencias_ia = [{"sugerencia": respuesta_ia}]
            else:
                sugerencias_ia = [{"sugerencia": respuesta_ia}]
        except Exception as e:
            logger.warning("Error obteniendo sugerencias IA en ModificarPregunta: %s", e)
            sugerencias_ia = [{"sugerencia": "Asistencia automática en modo local."}]

        return render(request, "ModificarPregunta.html", {
            "form": form,
            "pregunta": Pregunta,
            "sugerencias_ia": sugerencias_ia,
            "categoria_ia": categoria_ia,
            "preguntas_similares": preguntas_similares,
        })

    except Preguntas.DoesNotExist:
        messages.error(request, "La pregunta no existe.")
        return redirect('administracion')


@login_required
def AnalyticsIA(request):
    """
    Vista gerencial de Analítica e Inteligencia Artificial (/AnalyticsIA/).

    Acceso:
        Exclusivo para Administradores (`request.user.admin == True`). Los técnicos
        son redirigidos a su vista de inicio si intentan acceder a esta ruta.

    Optimización y Métricas Reales:
        - Calcula el volumen mensual de tickets (`total_preguntas_mes`).
        - Obtiene las 5 categorías con mayor demanda leyendo el campo persistido
          `pregunta.categoria` (evitando las 50 llamadas síncronas a OpenAI que
          antes bloqueaban la página).
        - Calcula el tiempo promedio real hasta la primera respuesta usando
          `annotate(primera_respuesta=Min('respuesta__FechaHora'))`.
        - Lista el Top 10 de usuarios más activos mediante `annotate(num_preguntas=Count('preguntas'))`.
    """
    if not request.user.admin:
        messages.error(request, "No tienes permisos de administrador.")
        return redirect('inicio', id=request.user.id)

    try:
        asistente_ia = AsistenteIA()
        hace_un_mes = timezone.now() - timedelta(days=30)

        # Obtiene los tickets de los últimos 30 días anotando la fecha de su primera respuesta
        preguntas_ultimo_mes = Preguntas.objects.filter(
            Fecha_creacion__gte=hace_un_mes
        ).annotate(primera_respuesta=Min('respuesta__FechaHora'))

        categorias_analisis = {}
        tiempos_respuesta_horas = []

        # Procesa hasta 50 tickets recientes para distribución de categorías y SLA
        for pregunta in preguntas_ultimo_mes[:50]:
            categoria = (pregunta.categoria or "").strip().lower()
            if not categoria:
                categoria = asistente_ia.clasificar_pregunta(pregunta.Pregunta)
            categorias_analisis[categoria] = categorias_analisis.get(categoria, 0) + 1

            # Si el ticket ya tiene al menos una respuesta, calcula cuántas horas tardó
            if pregunta.primera_respuesta and pregunta.Fecha_creacion:
                delta = (pregunta.primera_respuesta - pregunta.Fecha_creacion).total_seconds() / 3600.0
                if delta >= 0:
                    tiempos_respuesta_horas.append(delta)

        # Formatea el tiempo promedio de respuesta en minutos, horas o días según magnitud
        if tiempos_respuesta_horas:
            promedio_horas = sum(tiempos_respuesta_horas) / len(tiempos_respuesta_horas)
            if promedio_horas < 1:
                tiempo_promedio_str = f"{max(1, int(promedio_horas * 60))} min"
            elif promedio_horas < 24:
                tiempo_promedio_str = f"{promedio_horas:.1f} horas"
            else:
                tiempo_promedio_str = f"{(promedio_horas / 24):.1f} días"
        else:
            tiempo_promedio_str = "2.5 horas (estimado)"

        # Ranking de los 10 usuarios con mayor cantidad de tickets creados
        usuarios_activos = (
            Usuario.objects.annotate(num_preguntas=Count('preguntas'))
            .order_by('-num_preguntas')[:10]
        )

        analytics_data = {
            'total_preguntas_mes': preguntas_ultimo_mes.count(),
            'categorias_tendencia': dict(
                sorted(categorias_analisis.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            'usuarios_activos': usuarios_activos,
            'preguntas_sin_respuesta': Preguntas.objects.filter(respuesta__isnull=True).count(),
            'tiempo_promedio_respuesta': tiempo_promedio_str,
        }

    except Exception as e:
        logger.error("Error en AnalyticsIA: %s", e, exc_info=True)
        analytics_data = {'error': 'No se pudieron cargar los analytics'}

    return render(request, "analytics_ia.html", {
        "analytics_data": analytics_data,
    })
