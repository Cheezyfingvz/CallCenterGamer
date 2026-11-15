"""
===============================================================================
MODELOS DE DATOS DE SOUNDFLOW (musica/models.py)
===============================================================================
Define la estructura de datos para la aplicación musical SoundFlow:
1. Catálogo musical con caché local (Genero, Artista, Album, Cancion).
2. Biblioteca de usuarios y listas (Playlist, ElementoPlaylist, Favorito).
3. Planes y suscripciones simuladas (PlanSuscripcion, Suscripcion).
4. Descargas simuladas y reseñas (Descarga, Resena, HistorialEscucha).
5. Modelo de integración con el Call Center (ContenidoMusical).
===============================================================================
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import slugify


class Genero(models.Model):
    """Género o etiqueta musical."""
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        verbose_name = "Género"
        verbose_name_plural = "Géneros"
        ordering = ['nombre']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Artista(models.Model):
    """Artista o banda musical con soporte de identificador MBID de MusicBrainz."""
    mbid = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="MBID MusicBrainz"
    )
    nombre = models.CharField(max_length=200, verbose_name="Nombre del artista")
    pais = models.CharField(max_length=100, blank=True, default="", verbose_name="País")
    bio = models.TextField(blank=True, default="", verbose_name="Biografía")
    generos = models.ManyToManyField(Genero, blank=True, related_name="artistas")
    imagen_url = models.URLField(max_length=500, blank=True, default="", verbose_name="URL de Imagen")
    es_demo = models.BooleanField(default=False, verbose_name="Es dato demo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_sync = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Artista"
        verbose_name_plural = "Artistas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Album(models.Model):
    """Álbum o lanzamiento musical con soporte de MBID y Cover Art Archive."""
    mbid = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="MBID Lanzamiento"
    )
    titulo = models.CharField(max_length=200, verbose_name="Título del álbum")
    artista = models.ForeignKey(
        Artista,
        on_delete=models.CASCADE,
        related_name="albums",
        verbose_name="Artista"
    )
    anio = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Año")
    fecha_lanzamiento = models.CharField(max_length=30, blank=True, default="")
    portada_url = models.URLField(max_length=500, blank=True, default="", verbose_name="URL de Portada")
    generos = models.ManyToManyField(Genero, blank=True, related_name="albums")
    es_demo = models.BooleanField(default=False, verbose_name="Es dato demo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_sync = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Álbum"
        verbose_name_plural = "Álbumes"
        ordering = ['-anio', 'titulo']

    def __str__(self):
        return f"{self.titulo} - {self.artista.nombre}"

    @property
    def portada_o_default(self):
        if self.portada_url:
            return self.portada_url
        return "/static/musica/img/cover_placeholder.svg"


class Cancion(models.Model):
    """Canción o grabación musical."""
    mbid = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="MBID Grabación"
    )
    titulo = models.CharField(max_length=200, verbose_name="Título de la canción")
    artista = models.ForeignKey(
        Artista,
        on_delete=models.CASCADE,
        related_name="canciones",
        verbose_name="Artista"
    )
    album = models.ForeignKey(
        Album,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canciones",
        verbose_name="Álbum"
    )
    duracion_seg = models.PositiveIntegerField(null=True, blank=True, default=180, verbose_name="Duración (seg)")
    numero_pista = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Pista")
    es_demo = models.BooleanField(default=False, verbose_name="Es dato demo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_sync = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Canción"
        verbose_name_plural = "Canciones"
        ordering = ['titulo']

    def __str__(self):
        return f"{self.titulo} - {self.artista.nombre}"

    @property
    def duracion_formateada(self):
        if not self.duracion_seg:
            return "0:00"
        minutos = self.duracion_seg // 60
        segundos = self.duracion_seg % 60
        return f"{minutos}:{segundos:02d}"

    @property
    def portada_o_default(self):
        if self.album and self.album.portada_url:
            return self.album.portada_url
        return "/static/musica/img/cover_placeholder.svg"


class Playlist(models.Model):
    """Lista de reproducción creada por un usuario."""
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists",
        verbose_name="Propietario"
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Playlist")
    descripcion = models.TextField(blank=True, default="", verbose_name="Descripción")
    publica = models.BooleanField(default=False, verbose_name="Es pública")
    canciones = models.ManyToManyField(Cancion, through="ElementoPlaylist", blank=True, related_name="en_playlists")
    es_demo = models.BooleanField(default=False, verbose_name="Es playlist demo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Playlist"
        verbose_name_plural = "Playlists"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.nombre} (por {self.usuario})"

    @property
    def total_canciones(self):
        return self.canciones.count()


class ElementoPlaylist(models.Model):
    """Relación intermedia con orden de canciones dentro de una playlist."""
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="elementos")
    cancion = models.ForeignKey(Cancion, on_delete=models.CASCADE, related_name="elementos_playlist")
    orden = models.PositiveIntegerField(default=0)
    agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'agregado']
        unique_together = ('playlist', 'cancion')

    def __str__(self):
        return f"{self.playlist.nombre} - #{self.orden} {self.cancion.titulo}"


class Favorito(models.Model):
    """Elemento guardado en favoritos por el usuario."""
    TIPO_CANCION = 'cancion'
    TIPO_ALBUM = 'album'
    TIPO_ARTISTA = 'artista'
    TIPO_PLAYLIST = 'playlist'
    TIPO_CHOICES = [
        (TIPO_CANCION, 'Canción'),
        (TIPO_ALBUM, 'Álbum'),
        (TIPO_ARTISTA, 'Artista'),
        (TIPO_PLAYLIST, 'Playlist'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favoritos"
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cancion = models.ForeignKey(Cancion, on_delete=models.CASCADE, null=True, blank=True, related_name="favoritos")
    album = models.ForeignKey(Album, on_delete=models.CASCADE, null=True, blank=True, related_name="favoritos")
    artista = models.ForeignKey(Artista, on_delete=models.CASCADE, null=True, blank=True, related_name="favoritos")
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, null=True, blank=True, related_name="favoritos")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Favorito"
        verbose_name_plural = "Favoritos"
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'tipo', 'cancion'],
                name='unique_favorito_cancion',
                condition=models.Q(cancion__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['usuario', 'tipo', 'album'],
                name='unique_favorito_album',
                condition=models.Q(album__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['usuario', 'tipo', 'artista'],
                name='unique_favorito_artista',
                condition=models.Q(artista__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['usuario', 'tipo', 'playlist'],
                name='unique_favorito_playlist',
                condition=models.Q(playlist__isnull=False)
            ),
        ]

    def __str__(self):
        return f"{self.usuario} - {self.tipo}"


class PlanSuscripcion(models.Model):
    """Catálogo de planes de suscripción para SoundFlow."""
    CODIGO_GRATUITO = 'gratuito'
    CODIGO_INDIVIDUAL = 'individual'
    CODIGO_FAMILIAR = 'familiar'
    CODIGO_ESTUDIANTE = 'estudiante'
    CODIGOS_CHOICES = [
        (CODIGO_GRATUITO, 'Gratuito'),
        (CODIGO_INDIVIDUAL, 'Individual'),
        (CODIGO_FAMILIAR, 'Familiar'),
        (CODIGO_ESTUDIANTE, 'Estudiante'),
    ]

    codigo = models.CharField(max_length=20, choices=CODIGOS_CHOICES, unique=True)
    nombre = models.CharField(max_length=60)
    precio_mensual = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    descripcion = models.TextField(blank=True, default="")
    beneficios = models.TextField(blank=True, default="", help_text="Beneficios separados por salto de línea")
    destacado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Plan de Suscripción"
        verbose_name_plural = "Planes de Suscripción"
        ordering = ['precio_mensual']

    def __str__(self):
        return f"{self.nombre} (${self.precio_mensual}/mes)"

    def lista_beneficios(self):
        return [b.strip() for b in self.beneficios.split('\n') if b.strip()]


class Suscripcion(models.Model):
    """Suscripción activa de un usuario a un plan."""
    ESTADO_ACTIVA = 'activa'
    ESTADO_CANCELADA = 'cancelada'
    ESTADO_VENCIDA = 'vencida'
    ESTADO_CHOICES = [
        (ESTADO_ACTIVA, 'Activa'),
        (ESTADO_CANCELADA, 'Cancelada'),
        (ESTADO_VENCIDA, 'Vencida'),
    ]

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suscripcion_musical"
    )
    plan = models.ForeignKey(PlanSuscripcion, on_delete=models.PROTECT, related_name="suscripciones")
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default=ESTADO_ACTIVA)
    fecha_inicio = models.DateField(auto_now_add=True)
    fecha_renovacion = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"

    def __str__(self):
        return f"{self.usuario} - {self.plan.nombre} ({self.estado})"


class Descarga(models.Model):
    """Registro de descargas simuladas en SQLite."""
    ESTADO_COMPLETADA = 'completada'
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_ERROR = 'error'
    ESTADO_CHOICES = [
        (ESTADO_COMPLETADA, 'Completada'),
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_ERROR, 'Error'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="descargas_musicales"
    )
    cancion = models.ForeignKey(Cancion, on_delete=models.CASCADE, related_name="descargas")
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_COMPLETADA)
    plataforma = models.CharField(max_length=60, default="Navegador Web / SoundFlow Player")

    class Meta:
        verbose_name = "Descarga Simulada"
        verbose_name_plural = "Descargas Simuladas"
        ordering = ['-fecha']

    def __str__(self):
        return f"Descarga: {self.cancion.titulo} por {self.usuario}"


class Resena(models.Model):
    """Valoraciones y comentarios de usuarios sobre álbumes o playlists."""
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resenas_musicales"
    )
    album = models.ForeignKey(Album, on_delete=models.CASCADE, null=True, blank=True, related_name="resenas")
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, null=True, blank=True, related_name="resenas")
    puntuacion = models.PositiveSmallIntegerField(verbose_name="Puntuación (1-5)")
    comentario = models.TextField(blank=True, default="", verbose_name="Comentario")
    fecha = models.DateTimeField(auto_now_add=True)
    editado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reseña"
        verbose_name_plural = "Reseñas"
        ordering = ['-fecha']

    def clean(self):
        if self.puntuacion is None or not (1 <= self.puntuacion <= 5):
            raise ValidationError({'puntuacion': 'La puntuación debe ser un número entero entre 1 y 5.'})
        if not self.album and not self.playlist:
            raise ValidationError('La reseña debe asociarse a un álbum o a una playlist.')

    def __str__(self):
        destino = self.album.titulo if self.album else (self.playlist.nombre if self.playlist else "N/A")
        return f"{self.usuario} ({self.puntuacion}★) - {destino}"


class HistorialEscucha(models.Model):
    """Historial de reproducciones simuladas y navegación."""
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="historial_musical"
    )
    cancion = models.ForeignKey(Cancion, on_delete=models.CASCADE, related_name="reproducciones")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de Escucha"
        verbose_name_plural = "Historiales de Escucha"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.usuario} escuchó {self.cancion} el {self.fecha.strftime('%Y-%m-%d %H:%M')}"


class ContenidoMusical(models.Model):
    """
    Modelo unificador que almacena la referencia a cualquier entidad de SoundFlow
    para vincularla de manera limpia y resiliente con un Ticket de soporte (Preguntas).
    Permite que el ticket conserve la información completa aun si el objeto original
    se borra o si los servicios externos no están disponibles.
    """
    TIPO_CANCION = 'cancion'
    TIPO_ALBUM = 'album'
    TIPO_ARTISTA = 'artista'
    TIPO_PLAYLIST = 'playlist'
    TIPO_SUSCRIPCION = 'suscripcion'
    TIPO_DESCARGA = 'descarga'
    TIPO_RECOMENDACION = 'recomendacion'
    TIPO_OTRO = 'otro'

    TIPO_CHOICES = [
        (TIPO_CANCION, 'Canción'),
        (TIPO_ALBUM, 'Álbum'),
        (TIPO_ARTISTA, 'Artista'),
        (TIPO_PLAYLIST, 'Playlist'),
        (TIPO_SUSCRIPCION, 'Suscripción'),
        (TIPO_DESCARGA, 'Descarga simulada'),
        (TIPO_RECOMENDACION, 'Recomendación'),
        (TIPO_OTRO, 'Otro contenido musical'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_CANCION)
    nombre = models.CharField(max_length=255, verbose_name="Nombre visible")
    mbid = models.CharField(max_length=64, blank=True, null=True, verbose_name="MBID externo")
    portada_url = models.CharField(max_length=500, blank=True, default="", verbose_name="URL Portada")
    url_interna = models.CharField(max_length=255, blank=True, default="", verbose_name="Enlace SoundFlow")
    detalles_extra = models.TextField(blank=True, default="", verbose_name="Detalles técnicos o metadatos")

    # Relaciones directas opcionales (con SET_NULL para no perder el ticket si se borra el elemento)
    cancion = models.ForeignKey(Cancion, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_referenciados")
    album = models.ForeignKey(Album, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_referenciados")
    artista = models.ForeignKey(Artista, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_referenciados")
    playlist = models.ForeignKey(Playlist, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_referenciados")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contenido Musical de Soporte"
        verbose_name_plural = "Contenidos Musicales de Soporte"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.nombre}"

    @property
    def portada_o_default(self):
        if self.portada_url:
            return self.portada_url
        return "/static/musica/img/cover_placeholder.svg"
