"""
===============================================================================
FORMULARIOS ADMINISTRATIVOS DE USUARIO (administracion/forms.py)
===============================================================================
Propósito:
    Provee los formularios especializados para la creación y edición de cuentas
    del modelo personalizado `online.models.Usuario` desde interfaces de
    administración (como el Django Admin o paneles internos de gestión).
===============================================================================
"""

from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from online.models import Usuario


class UserAdminCreationForm(forms.ModelForm):
    """
    Formulario administrativo para crear un nuevo `Usuario` verificando
    que ambas contraseñas coincidan y aplicando hash criptográfico (`set_password`).
    """

    # Primer campo de contraseña (renderizado como <input type="password">)
    password = forms.CharField(widget=forms.PasswordInput)
    # Segundo campo para confirmar que no hubo errores de tipeo en la contraseña
    password_2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)

    class Meta:
        model = Usuario
        fields = ['usuario', 'correo']

    def clean(self):
        """
        Valida a nivel de formulario completo que `password` y `password_2` sean idénticos.
        """
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_2 = cleaned_data.get("password_2")
        if password is not None and password != password_2:
            self.add_error("password_2", "Your passwords must match")
        return cleaned_data

    def save(self, commit=True):
        """
        Guarda la instancia de `Usuario` cifrando previamente la contraseña en texto
        plano con el algoritmo PBKDF2 de Django (`set_password`).
        """
        Usuario = super().save(commit=False)
        Usuario.set_password(self.cleaned_data["password"])
        if commit:
            Usuario.save()
        return Usuario


class UserAdminChangeForm(forms.ModelForm):
    """
    Formulario administrativo para editar un `Usuario` existente.
    Muestra el hash de la contraseña en modo solo lectura (`ReadOnlyPasswordHashField`)
    para evitar que se sobrescriba accidentalmente el hash con texto plano.
    """

    password = ReadOnlyPasswordHashField()

    class Meta:
        model = Usuario
        fields = ['usuario', 'correo', 'password', 'activo', 'admin', 'tecnico']

    def clean_password(self):
        """
        Retorna siempre el hash de contraseña original almacenado en la base de datos.
        """
        return self.initial["password"]
