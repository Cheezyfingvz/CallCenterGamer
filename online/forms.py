"""
===============================================================================
FORMULARIOS Y VALIDACIONES DE ENTRADA (online/forms.py)
===============================================================================
Define los formularios de Django encargados de renderizar los campos HTML,
sanear los datos enviados por el usuario y aplicar reglas de negocio antes de
guardar en la base de datos:
1. `RegisterForm`: Registro de nuevos clientes con validación de correo único,
   longitud de contraseña y hash seguro.
2. `LoginForm`: Autenticación con opción `remember_me` (recordar sesión).
3. `PreguntasForm`: Creación de tickets por parte del cliente (sin campos
   ocultos manipulables).
4. `TicketAdminForm`: Edición avanzada de tickets para administradores (incluye
   estado, prioridad, categoría dinámica White-Label y técnico asignado).
5. `RespuestaForm`: Envío de mensajes en el hilo de conversación de un ticket.
===============================================================================
"""
from django import forms
from CallCenterGamer.brand_config import get_ticket_categories
from online.models import Usuario, Preguntas, Respuesta


# ==============================================================================
# 1. FORMULARIO DE REGISTRO DE USUARIOS (`RegisterForm`)
# ==============================================================================
class RegisterForm(forms.ModelForm):
    """
    Formulario basado en el modelo `Usuario` para dar de alta nuevas cuentas
    de clientes. Solicita contraseña y confirmación por separado para evitar
    errores de tipeo.
    """
    password = forms.CharField(
        label='',
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña'}),
    )
    password_2 = forms.CharField(
        label='',
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirmar contraseña'}),
    )

    class Meta:
        model = Usuario
        # Solo expone datos básicos; los flags admin/tecnico quedan en False por defecto
        fields = ['usuario', 'correo', 'rut']
        widgets = {
            'correo': forms.EmailInput(attrs={'placeholder': 'Ingrese su correo'}),
            'usuario': forms.TextInput(attrs={'placeholder': 'Ingrese su usuario'}),
            'rut': forms.TextInput(attrs={'placeholder': 'Ingrese su rut'}),
        }

    def clean_correo(self):
        """Verifica que el correo electrónico no esté registrado previamente."""
        correo = self.cleaned_data.get('correo')
        if Usuario.objects.filter(correo=correo).exists():
            raise forms.ValidationError("El correo ya está en uso")
        return correo

    def clean(self):
        """
        Ejecuta validaciones cruzadas sobre el nombre de usuario y las contraseñas:
        - Usuario obligatorio y de máximo 20 caracteres.
        - Contraseña de al menos 8 caracteres.
        - Coincidencia exacta entre `password` y `password_2`.
        """
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_2 = cleaned_data.get("password_2")
        usuario = cleaned_data.get("usuario")

        if usuario and len(usuario) > 20:
            self.add_error("usuario", "El nombre de usuario es demasiado largo!")
        if not usuario:
            self.add_error("usuario", "Debe ingresar un nombre de usuario!")
        if password and len(password) < 8:
            self.add_error("password", "La contraseña debe ser mayor a 8 dígitos")
        if password and password_2 and password != password_2:
            self.add_error("password_2", "Las contraseñas no coinciden")
        return cleaned_data

    def save(self, commit=True):
        """
        Sobrescribe el guardado para aplicar hash seguro (`set_password`) a la
        contraseña antes de persistir el registro en SQLite3.
        """
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password"])
        if commit:
            usuario.save()
        return usuario


# ==============================================================================
# 2. FORMULARIO DE INICIO DE SESIÓN (`LoginForm`)
# ==============================================================================
class LoginForm(forms.Form):
    """
    Formulario independiente para capturar credenciales de acceso (`Usuario` y
    `password`) y la casilla opcional `remember_me` para persistencia de sesión.
    """
    Usuario = forms.CharField(
        label='',
        max_length=63,
        widget=forms.TextInput(attrs={'placeholder': 'Ingrese su usuario'}),
    )
    password = forms.CharField(
        label='',
        max_length=63,
        widget=forms.PasswordInput(attrs={'placeholder': 'Ingrese su contraseña'}),
    )
    remember_me = forms.BooleanField(
        label='Recordar contraseña',
        required=False,
    )


# ==============================================================================
# 3. FORMULARIO DE CREACIÓN DE TICKETS PARA CLIENTES (`PreguntasForm`)
# ==============================================================================
class PreguntasForm(forms.ModelForm):
    """
    Formulario utilizado por el cliente en `/Inicio/<id>/` para abrir un ticket.

    Seguridad y Deuda Técnica Resuelta:
    Se excluyeron los campos ocultos `Usuario` y `Fecha_creacion`. El autor se
    toma directamente de `request.user` en la vista y la fecha se asigna de
    forma automática en el modelo, impidiendo suplantaciones de identidad.
    """
    class Meta:
        model = Preguntas
        fields = ['Titulo', 'Pregunta', 'prioridad']
        widgets = {
            'Titulo': forms.TextInput(attrs={'placeholder': 'Título de la pregunta'}),
            'Pregunta': forms.Textarea(attrs={'placeholder': 'Escriba su pregunta aquí...'}),
        }


# ==============================================================================
# 4. FORMULARIO DE GESTIÓN ADMINISTRATIVA DE TICKETS (`TicketAdminForm`)
# ==============================================================================
class TicketAdminForm(forms.ModelForm):
    """
    Formulario completo para que el Administrador modifique un ticket en
    `/ModificarPregunta/<idPregunta>/`. Permite actualizar título, descripción,
    estado, prioridad, categoría y técnico asignado.
    """
    # Campo de selección cuyas opciones se cargan dinámicamente desde settings.TICKET_CATEGORIES
    categoria = forms.ChoiceField(label='Categoría', choices=[])

    class Meta:
        model = Preguntas
        fields = ['Titulo', 'Pregunta', 'estado', 'prioridad', 'categoria', 'tecnico_asignado']
        widgets = {
            'Titulo': forms.TextInput(attrs={'placeholder': 'Título de la pregunta'}),
            'Pregunta': forms.Textarea(attrs={'placeholder': 'Escriba su pregunta aquí...'}),
        }

    def __init__(self, *args, **kwargs):
        """
        Inicializa el selector de categorías leyendo el catálogo White-Label activo
        en `settings.TICKET_CATEGORIES` y configura la etiqueta vacía del técnico.
        """
        super().__init__(*args, **kwargs)
        categorias = get_ticket_categories()
        # Si el ticket ya tenía una categoría histórica distinta, la preserva en la lista
        actual = self.instance.categoria if self.instance and self.instance.pk else None
        if actual and actual not in categorias:
            categorias.append(actual)
        self.fields['categoria'].choices = [
            (c, c.replace('_', ' ').capitalize()) for c in categorias
        ]
        self.fields['tecnico_asignado'].required = False
        self.fields['tecnico_asignado'].empty_label = 'Sin asignar'


# ==============================================================================
# 5. FORMULARIO DE MENSAJE DE CONVERSACIÓN (`RespuestaForm`)
# ==============================================================================
class RespuestaForm(forms.ModelForm):
    """
    Formulario para enviar un mensaje dentro del chat de un ticket (`/Respuesta/<idPregunta>/`).
    Solo expone el campo `Respuesta` (limitado a 200 caracteres en el widget);
    la pregunta destino, el usuario emisor y la fecha/hora los fija la vista en backend.
    """
    class Meta:
        model = Respuesta
        fields = ['Respuesta']
        widgets = {
            'Respuesta': forms.Textarea(
                attrs={'placeholder': 'Enviar mensaje...', 'maxlength': '200', 'rows': 3}
            ),
        }
