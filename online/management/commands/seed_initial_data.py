"""
===============================================================================
COMANDO DE PRECARGA IDEMPOTENTE DE DATOS (seed_initial_data.py)
===============================================================================
Este módulo define el comando personalizado:
    python manage.py seed_initial_data

Propósito:
Poblar automáticamente la base de datos SQLite3 (`db.sqlite3`) tanto en el
entorno local (`Start Servidor Web.bat`) como durante cada despliegue en
Render (`build.sh`), creando:
1. Los 3 perfiles de usuario obligatorios por defecto:
   - `admin`   (`admin@gmail.com`   / `admin123`)   -> Estado Técnico y Administrador (`admin=True, tecnico=True`).
   - `tecnico` (`tecnico@gmail.com` / `tecnico123`) -> Estado Técnico (`admin=False, tecnico=True`).
   - `usuario` (`usuario@gmail.com` / `usuario123`) -> Usuario Normal / Cliente (`admin=False, tecnico=False`).
2. Un conjunto de 6 tickets de soporte realistas distribuidos en distintos
   estados (`abierto`, `en_proceso`, `resuelto`), prioridades (`media`, `alta`,
   `critica`) y categorías (`hardware`, `conexion`, `software`, `rendimiento`,
   `cuenta`, `pago`), junto con sus respectivas respuestas de conversación.

Idempotencia:
Utiliza `get_or_create()` para que, si el comando se ejecuta múltiples veces
seguidas, NO duplique usuarios ni tickets existentes.
===============================================================================
"""
import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from online.models import Preguntas, Respuesta, Usuario


class Command(BaseCommand):
    help = (
        "Crea de forma idempotente los 3 usuarios por defecto (admin, tecnico, "
        "usuario) y 6 tickets iniciales con respuestas."
    )

    def handle(self, *args, **options):
        """Punto de entrada que ejecuta Django al invocar `manage.py seed_initial_data`."""
        # Contraseñas por defecto solicitadas (personalizables por variables de entorno)
        admin_pass = os.environ.get('SEED_ADMIN_PASSWORD', 'admin123')
        tech_pass = os.environ.get('SEED_TECH_PASSWORD', 'tecnico123')
        client_pass = os.environ.get('SEED_CLIENT_PASSWORD', 'usuario123')

        # ------------------------------------------------------------------
        # 1. Creación / Verificación del Administrador y Técnico (`admin`)
        # ------------------------------------------------------------------
        admin_user, admin_created = Usuario.objects.get_or_create(
            usuario='admin',
            defaults={
                'correo': 'admin@gmail.com',
                'nombre': 'Carlos',
                'apellido': 'Astorga',
                'rut': '15.234.567-8',
                'activo': True,
                'admin': True,
                'tecnico': True,
            },
        )
        if admin_created or not admin_user.check_password(admin_pass) or admin_user.correo != 'admin@gmail.com':
            admin_user.correo = 'admin@gmail.com'
            admin_user.activo = True
            admin_user.admin = True
            admin_user.tecnico = True
            admin_user.set_password(admin_pass)
            admin_user.save()

        # ------------------------------------------------------------------
        # 2. Creación / Verificación del Técnico de Soporte (`tecnico`)
        # ------------------------------------------------------------------
        tech_user, tech_created = Usuario.objects.get_or_create(
            usuario='tecnico',
            defaults={
                'correo': 'tecnico@gmail.com',
                'nombre': 'Valentina',
                'apellido': 'Rojas',
                'rut': '18.765.432-1',
                'activo': True,
                'admin': False,
                'tecnico': True,
            },
        )
        if tech_created or not tech_user.check_password(tech_pass) or tech_user.correo != 'tecnico@gmail.com':
            tech_user.correo = 'tecnico@gmail.com'
            tech_user.activo = True
            tech_user.admin = False
            tech_user.tecnico = True
            tech_user.set_password(tech_pass)
            tech_user.save()

        # ------------------------------------------------------------------
        # 3. Creación / Verificación del Usuario Normal / Cliente (`usuario`)
        # ------------------------------------------------------------------
        client_user, client_created = Usuario.objects.get_or_create(
            usuario='usuario',
            defaults={
                'correo': 'usuario@gmail.com',
                'nombre': 'Matías',
                'apellido': 'Soto',
                'rut': '20.111.222-3',
                'activo': True,
                'admin': False,
                'tecnico': False,
            },
        )
        if client_created or not client_user.check_password(client_pass) or client_user.correo != 'usuario@gmail.com':
            client_user.correo = 'usuario@gmail.com'
            client_user.activo = True
            client_user.admin = False
            client_user.tecnico = False
            client_user.set_password(client_pass)
            client_user.save()

        # ------------------------------------------------------------------
        # 4. Catálogo de 6 Tickets de Demostración y sus Respuestas
        # ------------------------------------------------------------------
        now = timezone.now()
        tickets_seed = [
            {
                'Titulo': 'Sobrecalentamiento de GPU RTX al jugar en Ultra',
                'Pregunta': (
                    'Mi tarjeta gráfica sube a 88°C después de 15 minutos de partida '
                    'y los ventiladores suenan al máximo. ¿Debo cambiar pasta térmica?'
                ),
                'estado': Preguntas.ESTADO_EN_PROCESO,
                'prioridad': Preguntas.PRIORIDAD_ALTA,
                'categoria': 'hardware',
                'tecnico_asignado': tech_user,
                'dias_atras': 4,
                'respuestas': [
                    (
                        tech_user,
                        'Hola Matías, 88°C está cerca del límite térmico. Te sugerimos limpiar '
                        'los filtros de polvo del gabinete y configurar una curva de ventilación '
                        'en MSI Afterburner antes de abrir la tarjeta.',
                    ),
                    (
                        client_user,
                        'Gracias Valentina, limpié el filtro frontal y bajó a 79°C, probaré la curva.',
                    ),
                ],
            },
            {
                'Titulo': 'Ping alto y pérdida de paquetes en servidores de Brasil',
                'Pregunta': (
                    'Desde ayer tengo 180ms de latencia y desconexiones por Wi-Fi en partidas '
                    'competitivas, aunque mi velocidad de descarga es normal.'
                ),
                'estado': Preguntas.ESTADO_RESUELTO,
                'prioridad': Preguntas.PRIORIDAD_MEDIA,
                'categoria': 'conexion',
                'tecnico_asignado': tech_user,
                'dias_atras': 6,
                'respuestas': [
                    (
                        tech_user,
                        'Para juego competitivo te recomendamos conectar por cable Ethernet Cat6 '
                        'y configurar DNS 1.1.1.1 / 8.8.8.8 en tu adaptador de red.',
                    ),
                ],
            },
            {
                'Titulo': 'Error de DirectX 12 al iniciar el juego tras actualizar Windows',
                'Pregunta': (
                    'El juego se cierra en la pantalla de carga con un mensaje de error fatal '
                    'de DirectX 12 después de la última actualización del sistema.'
                ),
                'estado': Preguntas.ESTADO_ABIERTO,
                'prioridad': Preguntas.PRIORIDAD_CRITICA,
                'categoria': 'software',
                'tecnico_asignado': None,
                'dias_atras': 1,
                'respuestas': [],
            },
            {
                'Titulo': 'Caídas bruscas de FPS y stuttering en mapas abiertos',
                'Pregunta': (
                    'Tengo 16GB de RAM pero el juego presenta tirones constantes cada vez que '
                    'giro la cámara rápido en zonas con muchos jugadores.'
                ),
                'estado': Preguntas.ESTADO_EN_PROCESO,
                'prioridad': Preguntas.PRIORIDAD_MEDIA,
                'categoria': 'rendimiento',
                'tecnico_asignado': admin_user,
                'dias_atras': 3,
                'respuestas': [
                    (
                        admin_user,
                        'Verifica que el perfil XMP/DOCP de tu memoria RAM esté activo en la BIOS '
                        'y que el juego esté instalado en una unidad SSD NVMe.',
                    ),
                ],
            },
            {
                'Titulo': 'No llega el código de verificación 2FA al correo electrónico',
                'Pregunta': (
                    'Intenté iniciar sesión desde mi nuevo PC pero no recibo el correo con el '
                    'código de seguridad de dos factores.'
                ),
                'estado': Preguntas.ESTADO_RESUELTO,
                'prioridad': Preguntas.PRIORIDAD_ALTA,
                'categoria': 'cuenta',
                'tecnico_asignado': tech_user,
                'dias_atras': 5,
                'respuestas': [
                    (
                        tech_user,
                        'Hemos sincronizado el servicio de correo y desbloqueado el envío para '
                        'tu dominio. Revisa la carpeta de Spam o Promociones.',
                    ),
                ],
            },
            {
                'Titulo': 'Cobro duplicado en compra de pase de temporada',
                'Pregunta': (
                    'Realicé el pago con tarjeta de débito y me aparecen dos cargos idénticos '
                    'en la cartola bancaria.'
                ),
                'estado': Preguntas.ESTADO_ABIERTO,
                'prioridad': Preguntas.PRIORIDAD_ALTA,
                'categoria': 'pago',
                'tecnico_asignado': None,
                'dias_atras': 2,
                'respuestas': [],
            },
        ]

        tickets_creados = 0
        for item in tickets_seed:
            fecha_ticket = now - timedelta(days=item['dias_atras'])
            pregunta, created = Preguntas.objects.get_or_create(
                Titulo=item['Titulo'],
                Usuario=client_user,
                defaults={
                    'Pregunta': item['Pregunta'],
                    'Fecha_creacion': fecha_ticket,
                    'estado': item['estado'],
                    'prioridad': item['prioridad'],
                    'categoria': item['categoria'],
                    'tecnico_asignado': item['tecnico_asignado'],
                },
            )
            if created:
                tickets_creados += 1
                # Si el ticket acaba de crearse, inserta sus mensajes de conversación asociados
                for idx, (autor_resp, texto_resp) in enumerate(item['respuestas'], start=1):
                    Respuesta.objects.create(
                        id_Pregunta=pregunta,
                        Usuario=autor_resp,
                        Respuesta=texto_resp,
                        FechaHora=fecha_ticket + timedelta(hours=idx * 2),
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed completado: usuarios base verificados (admin, tecnico, "
                f"usuario) y {tickets_creados} tickets nuevos creados "
                f"(total en BD: {Preguntas.objects.count()})."
            )
        )
