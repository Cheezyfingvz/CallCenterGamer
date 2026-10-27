"""
===============================================================================
MODELOS DE DATOS Y ESQUEMA ENTIDAD-RELACIÓN (online/models.py)
===============================================================================
Este archivo define la estructura de las 3 tablas principales de la base de
datos SQLite3 a través del ORM de Django:
1. `Usuario` (hereda de `AbstractBaseUser` + `UserManager`):
   - Modelo de autenticación personalizado con RUT chileno, correo único y
     control de acceso basado en roles mediante los campos booleanos `activo`,
     `admin` y `tecnico`.
2. `Preguntas` (Ticket de Soporte Técnico - Mejora 1 Evaluación N° 3):
   - Almacena la consulta creada por un cliente, junto con su ciclo de vida
     (`estado`), urgencia (`prioridad`), clasificación temática (`categoria`)
     y el especialista responsable (`tecnico_asignado`).
3. `Respuesta` (Mensaje de Conversación):
   - Representa cada mensaje enviado dentro del hilo de un ticket `Preguntas`,
     relacionando tanto el ticket como el `Usuario` emisor (Cliente, Técnico o Admin).
===============================================================================
"""
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone


# ==============================================================================
# 1. MANAGER PERSONALIZADO DE USUARIOS (`UserManager`)
# ==============================================================================
class UserManager(BaseUserManager):
    """
    Gestor encargado de la creación segura de usuarios estándar y superusuarios
    en la base de datos, asegurando la normalización del correo y el hash PBKDF2
    de la contraseña mediante `set_password()`.
    """

    def create_user(self, correo, usuario, password=None, **extra_fields):
        """
        Crea, cifra la contraseña y guarda un usuario estándar con el correo y
        nombre de usuario suministrados.
        """
        if not correo:
            raise ValueError('El usuario debe tener un correo electrónico')
        if not usuario:
            raise ValueError('El usuario debe tener un nombre de usuario')

        # Instancia el modelo Usuario normalizando el dominio del correo electrónico
        user = self.model(
            correo=self.normalize_email(correo),
            usuario=usuario,
            **extra_fields,
        )
        # Cifra la contraseña en texto plano usando el algoritmo seguro de Django (PBKDF2)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, correo, usuario, password=None, **extra_fields):
        """
        Crea y guarda un superusuario (Administrador) habilitando automáticamente
        los flags `admin=True`, `activo=True` y `tecnico=True`.
        """
        extra_fields.setdefault('admin', True)
        extra_fields.setdefault('activo', True)
        extra_fields.setdefault('tecnico', True)

        if extra_fields.get('admin') is not True:
            raise ValueError('Superuser debe tener admin=True.')

        return self.create_user(correo, usuario, password, **extra_fields)


# ==============================================================================
# 2. MODELO DE USUARIO PERSONALIZADO (`Usuario`)
# ==============================================================================
class Usuario(AbstractBaseUser):
    """
    Representa a cualquier persona registrada en la plataforma (Cliente, Técnico
    o Administrador).

    ¿Por qué hereda de `AbstractBaseUser`?
    Porque permite control total sobre los campos de identificación: usar `usuario`
    como identificador de login (`USERNAME_FIELD`), exigir `correo` único, incorporar
    el `rut` chileno y manejar los roles del sistema mediante los campos `admin`
    y `tecnico`, conservando toda la seguridad de sesiones y contraseñas de Django.
    """

    # Datos personales opcionales e identificadores únicos
    nombre = models.CharField(
        verbose_name='Nombre',
        max_length=30,
        blank=True,
        null=True,
    )
    apellido = models.CharField(
        verbose_name='Apellido',
        max_length=30,
        blank=True,
        null=True,
    )
    rut = models.CharField(
        verbose_name='RUT',
        max_length=12,
        unique=True,
        blank=True,
        null=True,
    )
    correo = models.EmailField(
        verbose_name='Correo electrónico',
        max_length=70,
        unique=True,
    )
    usuario = models.CharField(
        verbose_name='Usuario',
        max_length=50,
        unique=True,
    )
    fecha_nacimiento = models.DateField(
        verbose_name='Fecha de nacimiento',
        null=True,
        blank=True,
    )

    # --- Flags de Estado y Control de Acceso Basado en Roles (RBAC) ---
    # activo=True permite iniciar sesión; si es False, el login es rechazado.
    activo = models.BooleanField(default=True)
    # admin=True otorga control total (gestión de usuarios, borrado/edición y Analytics IA).
    admin = models.BooleanField(default=False)
    # tecnico=True permite acceder a /Administracion/ y responder cualquier ticket.
    tecnico = models.BooleanField(default=False)

    # Define que el login se realiza con el campo `usuario` y que `correo` es obligatorio
    USERNAME_FIELD = 'usuario'
    REQUIRED_FIELDS = ['correo']

    # Conecta el manager personalizado a `Usuario.objects`
    objects = UserManager()

    # --- Métodos auxiliares requeridos por el sistema de autenticación de Django ---
    def get_full_name(self):
        """Retorna el nombre y apellido concatenados del usuario."""
        return f"{self.nombre} {self.apellido}"

    def get_short_name(self):
        """Retorna el identificador corto (nombre de usuario)."""
        return self.usuario

    def has_perm(self, perm, obj=None):
        """Indica si el usuario posee un permiso específico (True para admins activos)."""
        return self.is_active and self.admin

    def has_module_perms(self, app_label):
        """Indica si el usuario tiene permisos sobre una app en el admin de Django."""
        return self.is_active and self.admin

    @property
    def is_active(self):
        """Propiedad leída por `authenticate()` para permitir o bloquear el acceso."""
        return self.activo

    @property
    def is_staff(self):
        """Determina quién puede entrar al panel nativo `/admin/` de Django."""
        return self.admin

    @property
    def is_admin(self):
        """Alias de conveniencia para consultar si el usuario es administrador."""
        return self.admin

    def __str__(self):
        """Representación legible en texto del objeto Usuario."""
        return self.usuario


# ==============================================================================
# 3. MODELO DE TICKET DE SOPORTE (`Preguntas` - MEJORA 1 EVALUACIÓN N° 3)
# ==============================================================================
class Preguntas(models.Model):
    """
    Representa un Ticket de Soporte Técnico creado por un usuario.
    Relación con `Usuario`: Muchos a Uno (N:1) mediante ForeignKey (`Usuario` autor
    y `tecnico_asignado` especialista).

    Mejora Estructural 1:
    Se extendió con `estado`, `prioridad`, `categoria` persistida en BD y
    `tecnico_asignado`, además de asignar `Fecha_creacion` automáticamente.
    """

    # --- Catálogo de Estados del Ciclo de Vida del Ticket ---
    ESTADO_ABIERTO = 'abierto'
    ESTADO_EN_PROCESO = 'en_proceso'
    ESTADO_RESUELTO = 'resuelto'
    ESTADO_CERRADO = 'cerrado'
    ESTADO_CHOICES = [
        (ESTADO_ABIERTO, 'Abierto'),
        (ESTADO_EN_PROCESO, 'En proceso'),
        (ESTADO_RESUELTO, 'Resuelto'),
        (ESTADO_CERRADO, 'Cerrado'),
    ]

    # --- Catálogo de Niveles de Prioridad ---
    PRIORIDAD_BAJA = 'baja'
    PRIORIDAD_MEDIA = 'media'
    PRIORIDAD_ALTA = 'alta'
    PRIORIDAD_CRITICA = 'critica'
    PRIORIDAD_CHOICES = [
        (PRIORIDAD_BAJA, 'Baja'),
        (PRIORIDAD_MEDIA, 'Media'),
        (PRIORIDAD_ALTA, 'Alta'),
        (PRIORIDAD_CRITICA, 'Crítica'),
    ]

    # Clave primaria autoincremental del ticket
    idPregunta = models.AutoField(primary_key=True)
    # Título descriptivo corto del problema (máx. 60 caracteres)
    Titulo = models.CharField(max_length=60)
    # Detalle extenso del problema técnico reportado
    Pregunta = models.TextField()
    # Fecha y hora exacta de creación (se asigna sola con timezone.now si no se indica)
    Fecha_creacion = models.DateTimeField(default=timezone.now)

    # Relación N:1 con el autor del ticket. Si se borra el usuario, se borran sus tickets (CASCADE).
    # `related_name='preguntas'` permite consultar `usuario.preguntas.all()` y `Count('preguntas')`.
    Usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='preguntas',
    )

    # --- Nuevos campos de gestión de tickets (Mejora 1) ---
    estado = models.CharField(
        max_length=15,
        choices=ESTADO_CHOICES,
        default=ESTADO_ABIERTO,
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default=PRIORIDAD_MEDIA,
    )
    # Categoría clasificada por IA (ej. hardware, software, conexion, rendimiento, etc.).
    # Se guarda en la BD al crear/modificar el ticket para no recalcularla en cada vista.
    categoria = models.CharField(max_length=30, default='otros', blank=True)

    # Técnico o Administrador asignado para resolver el ticket.
    # Usa `on_delete=models.SET_NULL` para que, si se elimina al técnico, el ticket no se pierda.
    tecnico_asignado = models.ForeignKey(
        'online.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets_asignados',
        limit_choices_to=Q(tecnico=True) | Q(admin=True),
    )

    def __str__(self):
        """Representación legible del ticket mostrando su ID y Título."""
        return f"{self.idPregunta} - {self.Titulo}"


# ==============================================================================
# 4. MODELO DE MENSAJE DE CONVERSACIÓN (`Respuesta`)
# ==============================================================================
class Respuesta(models.Model):
    """
    Representa cada mensaje o réplica enviada dentro del chat de un ticket.

    Relaciones entre `Usuario`, `Preguntas` y `Respuesta`:
    - `id_Pregunta`: ForeignKey (N:1) hacia `Preguntas`. Una pregunta puede tener
      muchas respuestas; al eliminarse la pregunta, sus respuestas se borran en cascada.
    - `Usuario`: ForeignKey (N:1) hacia `Usuario`. Indica qué usuario (el cliente
      dueño del ticket, un técnico o un administrador) escribió esa respuesta.
    """

    # Identificador único del mensaje
    idRespuesta = models.AutoField(primary_key=True)
    # Contenido textual de la respuesta
    Respuesta = models.TextField(verbose_name='Respuesta')
    # Ticket (Preguntas) al cual pertenece este mensaje
    id_Pregunta = models.ForeignKey(Preguntas, on_delete=models.CASCADE)
    # Autor que emitió el mensaje
    Usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    # Estampa de tiempo en que se envió el mensaje
    FechaHora = models.DateTimeField()

    def __str__(self):
        """Muestra el ID de la respuesta y un extracto de los primeros 20 caracteres."""
        return f"{self.idRespuesta} - {self.Respuesta[:20]}"
