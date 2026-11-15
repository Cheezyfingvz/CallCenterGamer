"""
===============================================================================
FORMULARIOS DE SOUNDFLOW (musica/forms.py)
===============================================================================
Formularios para creación de playlists, registro de reseñas y creación
de tickets vinculados a contenido musical.
===============================================================================
"""
from django import forms
from CallCenterGamer.brand_config import get_ticket_categories
from musica.models import Playlist, Resena
from online.models import Preguntas


class PlaylistForm(forms.ModelForm):
    """Formulario para crear o editar playlists."""
    class Meta:
        model = Playlist
        fields = ['nombre', 'descripcion', 'publica']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'sf-input',
                'placeholder': 'Mi Lista Favorita',
                'required': True,
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'sf-textarea',
                'placeholder': 'Añade una descripción opcional...',
                'rows': 3,
            }),
            'publica': forms.CheckboxInput(attrs={
                'class': 'sf-checkbox',
            }),
        }


class ResenaForm(forms.ModelForm):
    """Formulario para valorar un álbum o una playlist (1 a 5 estrellas)."""
    puntuacion = forms.ChoiceField(
        choices=[(i, f"{i} Estrella{'s' if i > 1 else ''}") for i in range(5, 0, -1)],
        widget=forms.Select(attrs={'class': 'sf-select'})
    )

    class Meta:
        model = Resena
        fields = ['puntuacion', 'comentario']
        widgets = {
            'comentario': forms.Textarea(attrs={
                'class': 'sf-textarea',
                'placeholder': '¿Qué te pareció este lanzamiento? Deja tu opinión...',
                'rows': 3,
            }),
        }


class TicketMusicaForm(forms.Form):
    """
    Formulario especializado para crear un ticket de soporte directamente
    desde una ficha musical en SoundFlow.
    """
    Titulo = forms.CharField(
        max_length=60,
        label="Título del problema",
        widget=forms.TextInput(attrs={
            'class': 'sf-input',
            'placeholder': 'Ej. Error en los metadatos de la canción',
            'required': True,
        })
    )
    Pregunta = forms.CharField(
        label="Descripción detallada",
        widget=forms.Textarea(attrs={
            'class': 'sf-textarea',
            'placeholder': 'Describe el problema que encontraste con este contenido...',
            'rows': 4,
            'required': True,
        })
    )
    prioridad = forms.ChoiceField(
        choices=Preguntas.PRIORIDAD_CHOICES,
        initial=Preguntas.PRIORIDAD_MEDIA,
        widget=forms.Select(attrs={'class': 'sf-select'})
    )
    categoria = forms.ChoiceField(
        label="Categoría temática",
        widget=forms.Select(attrs={'class': 'sf-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categorias = get_ticket_categories()
        # Dar prioridad a categorías musicales
        prioritarias = [
            'contenido_musical', 'reproductor', 'playlists', 'biblioteca',
            'descargas', 'suscripciones', 'recomendaciones', 'problemas_tecnicos', 'otros'
        ]
        opciones = []
        for cat in prioritarias:
            if cat in categorias:
                opciones.append((cat, cat.replace('_', ' ').capitalize()))
        for cat in categorias:
            if cat not in prioritarias:
                opciones.append((cat, cat.replace('_', ' ').capitalize()))
        self.fields['categoria'].choices = opciones
