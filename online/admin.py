"""
===============================================================================
CONFIGURACIÓN DEL PANEL NATIVO DE DJANGO ADMIN (online/admin.py)
===============================================================================
Registra los modelos `Usuario`, `Preguntas` y `Respuesta` en la interfaz
administrativa nativa `/admin/` de Django, conectando los formularios seguros
`UserAdminCreationForm` y `UserAdminChangeForm` y configurando columnas visibles,
filtros laterales, buscador y precarga de claves foráneas (`list_select_related`)
para evitar consultas N+1.
===============================================================================
"""
from django.contrib import admin
from administracion.forms import UserAdminCreationForm, UserAdminChangeForm
from online.models import Usuario, Preguntas, Respuesta


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    """
    Configuración de gestión de cuentas de `Usuario` en `/admin/`, utilizando
    los formularios de creación y edición con contraseña cifrada de `administracion/forms.py`.
    """
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    list_display = ('id', 'usuario', 'correo', 'rut', 'activo', 'admin', 'tecnico', 'last_login')
    list_filter = ('activo', 'admin', 'tecnico')
    search_fields = ('usuario', 'correo', 'rut')

    def get_form(self, request, obj=None, **kwargs):
        """
        Utiliza `UserAdminCreationForm` al crear un usuario nuevo y
        `UserAdminChangeForm` al editar uno existente.
        """
        defaults = {}
        if obj is None:
            defaults['form'] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)


@admin.register(Preguntas)
class PreguntasAdmin(admin.ModelAdmin):
    """Configuración de visualización y filtrado de Tickets en `/admin/`."""
    # Columnas mostradas en la tabla principal de tickets
    list_display = (
        'idPregunta',
        'Titulo',
        'Usuario',
        'estado',
        'prioridad',
        'categoria',
        'tecnico_asignado',
        'Fecha_creacion',
    )
    # Filtros rápidos en la barra lateral derecha
    list_filter = ('estado', 'prioridad', 'categoria')
    # Campos habilitados en la barra de búsqueda superior
    search_fields = ('Titulo', 'Pregunta', 'Usuario__usuario')
    # Realiza JOIN SQL con Usuario y tecnico_asignado en una sola consulta
    list_select_related = ('Usuario', 'tecnico_asignado')


@admin.register(Respuesta)
class RespuestaAdmin(admin.ModelAdmin):
    """Configuración de visualización de Mensajes/Respuestas en `/admin/`."""
    list_display = ('idRespuesta', 'id_Pregunta', 'Usuario', 'FechaHora')
    list_select_related = ('id_Pregunta', 'Usuario')
