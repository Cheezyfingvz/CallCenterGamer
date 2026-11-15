"""
===============================================================================
COMANDO DE PRECARGA IDEMPOTENTE DE SOUNDFLOW (seed_musica.py)
===============================================================================
Puebla la base de datos SQLite con datos académicos de demostración para SoundFlow:
- 4 Géneros musicales.
- 8 Artistas ficticios (es_demo=True).
- 12 Álbumes ficticios con portadas de respaldo (es_demo=True).
- 30 Canciones ficticias con duraciones realistas.
- 8 Playlists de demostración.
- 4 Planes de suscripción oficiales (Gratuito, Individual, Familiar, Estudiante).
- Tickets demostrativos relacionados con música en el Call Center.

Uso:
    python manage.py seed_musica
===============================================================================
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from musica.models import (
    Genero, Artista, Album, Cancion, Playlist, ElementoPlaylist,
    PlanSuscripcion, Suscripcion, ContenidoMusical
)
from online.models import Usuario, Preguntas, Respuesta


class Command(BaseCommand):
    help = "Carga de datos de demostración académicos e idempotentes para SoundFlow."

    def handle(self, *args, **options):
        self.stdout.write("Iniciando precarga de datos de SoundFlow...")

        # ---------------------------------------------------------------------
        # 1. GÉNEROS MUSICALES
        # ---------------------------------------------------------------------
        generos_data = [
            ("Synthwave / Retro", "synthwave"),
            ("Rock Progresivo", "rock-progresivo"),
            ("Lo-Fi Beats", "lo-fi-beats"),
            ("Electrónica & Cyberpunk", "electronica-cyberpunk"),
            ("Metal Sinfónico", "metal-sinfonico"),
        ]
        generos_objs = {}
        for nom, slug in generos_data:
            gen, _ = Genero.objects.get_or_create(nombre=nom, defaults={'slug': slug})
            generos_objs[slug] = gen

        # ---------------------------------------------------------------------
        # 2. PLANES DE SUSCRIPCIÓN
        # ---------------------------------------------------------------------
        planes_data = [
            {
                'codigo': PlanSuscripcion.CODIGO_GRATUITO,
                'nombre': 'SoundFlow Free',
                'precio_mensual': 0.00,
                'descripcion': 'Música con anuncios simulados y reproducción aleatoria.',
                'beneficios': 'Catálogo completo\nReproducción estándar\nSoporte comunitario',
                'destacado': False,
            },
            {
                'codigo': PlanSuscripcion.CODIGO_INDIVIDUAL,
                'nombre': 'SoundFlow Premium',
                'precio_mensual': 5.99,
                'descripcion': 'Música sin interrupciones y descargas offline simuladas.',
                'beneficios': 'Sin anuncios\nAudio de alta fidelidad\nModo offline simulado\nSoporte prioritario',
                'destacado': True,
            },
            {
                'codigo': PlanSuscripcion.CODIGO_FAMILIAR,
                'nombre': 'SoundFlow Familiar',
                'precio_mensual': 9.99,
                'descripcion': 'Hasta 6 cuentas independientes para los miembros de tu hogar.',
                'beneficios': '6 cuentas premium\nControl de contenidos\nPlaylists familiares compartidas',
                'destacado': False,
            },
            {
                'codigo': PlanSuscripcion.CODIGO_ESTUDIANTE,
                'nombre': 'SoundFlow Estudiantes',
                'precio_mensual': 2.99,
                'descripcion': 'Descuento especial verificado para estudiantes universitarios.',
                'beneficios': 'Todos los beneficios de Premium\nTarifa reducida renovable anualmente',
                'destacado': False,
            },
        ]
        for p in planes_data:
            PlanSuscripcion.objects.get_or_create(
                codigo=p['codigo'],
                defaults=p
            )

        # ---------------------------------------------------------------------
        # 3. ARTISTAS FICTICIOS (8 artistas)
        # ---------------------------------------------------------------------
        artistas_data = [
            ("CyberPulse", "Chile", "Banda pionera en sintetizadores vintage y ritmos retrofuturistas.", "synthwave"),
            ("Neon Horizon", "Argentina", "Dúo electrónico especializado en paisajes sonoros urbanos y cyberpunk.", "electronica-cyberpunk"),
            ("Echoes of Silence", "México", "Quinteto de rock progresivo con guitarras melódicas y compases complejos.", "rock-progresivo"),
            ("Coffee & Rain", "Colombia", "Productor independiente de Lo-Fi hip hop relajante para estudiar.", "lo-fi-beats"),
            ("Solar Drift", "España", "Trío de dream pop y sintetizadores espaciales.", "synthwave"),
            ("Valkyrie Protocol", "Suecia", "Grupo de metal sinfónico con orquestaciones épicas para gaming.", "metal-sinfonico"),
            ("Pixel Dreams", "Japón", "Compositor de chiptune moderno y melodías inspiradas en consolas de 16-bits.", "electronica-cyberpunk"),
            ("Midnight Jazz Club", "Estados Unidos", "Ensamble nocturno que fusiona jazz clásico con texturas electrónicas modernas.", "lo-fi-beats"),
        ]
        artistas_objs = []
        for nombre, pais, bio, gen_slug in artistas_data:
            art, _ = Artista.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'pais': pais,
                    'bio': bio,
                    'es_demo': True,
                    'imagen_url': '/static/musica/img/cover_placeholder.svg',
                }
            )
            if gen_slug in generos_objs:
                art.generos.add(generos_objs[gen_slug])
            artistas_objs.append(art)

        # ---------------------------------------------------------------------
        # 4. ÁLBUMES FICTICIOS (12 álbumes)
        # ---------------------------------------------------------------------
        albumes_data = [
            ("Neon Boulevard", artistas_objs[0], 2024, "synthwave"),
            ("Grid Runner", artistas_objs[0], 2025, "synthwave"),
            ("Digital Rain", artistas_objs[1], 2023, "electronica-cyberpunk"),
            ("Subway Memories", artistas_objs[1], 2025, "electronica-cyberpunk"),
            ("The Infinite Loop", artistas_objs[2], 2022, "rock-progresivo"),
            ("Midnight Coding", artistas_objs[3], 2024, "lo-fi-beats"),
            ("Study Session Vol. 1", artistas_objs[3], 2025, "lo-fi-beats"),
            ("Constellation", artistas_objs[4], 2023, "synthwave"),
            ("Ragnarok Symphony", artistas_objs[5], 2024, "metal-sinfonico"),
            ("Boss Fight Overture", artistas_objs[5], 2025, "metal-sinfonico"),
            ("Arcade Nostalgia", artistas_objs[6], 2024, "electronica-cyberpunk"),
            ("Late Night Velvet", artistas_objs[7], 2023, "lo-fi-beats"),
        ]
        albumes_objs = []
        for titulo, artista, anio, gen_slug in albumes_data:
            alb, _ = Album.objects.get_or_create(
                titulo=titulo,
                artista=artista,
                defaults={
                    'anio': anio,
                    'fecha_lanzamiento': f"{anio}-05-12",
                    'es_demo': True,
                    'portada_url': '/static/musica/img/cover_placeholder.svg',
                }
            )
            if gen_slug in generos_objs:
                alb.generos.add(generos_objs[gen_slug])
            albumes_objs.append(alb)

        # ---------------------------------------------------------------------
        # 5. CANCIONES FICTICIAS (30+ canciones)
        # ---------------------------------------------------------------------
        canciones_data = [
            # Neon Boulevard (CyberPulse)
            ("Midnight Cruise", artistas_objs[0], albumes_objs[0], 215, 1),
            ("Overdrive Sunset", artistas_objs[0], albumes_objs[0], 198, 2),
            ("Highway 84", artistas_objs[0], albumes_objs[0], 240, 3),
            # Grid Runner (CyberPulse)
            ("Fast Forward", artistas_objs[0], albumes_objs[1], 185, 1),
            ("Neon Lights in the Dark", artistas_objs[0], albumes_objs[1], 210, 2),
            # Digital Rain (Neon Horizon)
            ("Circuit Breaker", artistas_objs[1], albumes_objs[2], 230, 1),
            ("Augmented Reality", artistas_objs[1], albumes_objs[2], 205, 2),
            ("Ghost in the Cable", artistas_objs[1], albumes_objs[2], 255, 3),
            # Subway Memories (Neon Horizon)
            ("Underground Flow", artistas_objs[1], albumes_objs[3], 195, 1),
            ("Next Stop: Future", artistas_objs[1], albumes_objs[3], 220, 2),
            # The Infinite Loop (Echoes of Silence)
            ("Fractal Reflection", artistas_objs[2], albumes_objs[4], 320, 1),
            ("Echoes in the Void", artistas_objs[2], albumes_objs[4], 290, 2),
            ("Time Paradigm", artistas_objs[2], albumes_objs[4], 345, 3),
            # Midnight Coding (Coffee & Rain)
            ("Terminal Chill", artistas_objs[3], albumes_objs[5], 160, 1),
            ("Warm Coffee Cup", artistas_objs[3], albumes_objs[5], 175, 2),
            ("Debugging at 3AM", artistas_objs[3], albumes_objs[5], 180, 3),
            # Study Session Vol. 1 (Coffee & Rain)
            ("Windowpane Droplets", artistas_objs[3], albumes_objs[6], 165, 1),
            ("Library Silence", artistas_objs[3], albumes_objs[6], 190, 2),
            # Constellation (Solar Drift)
            ("Star Chaser", artistas_objs[4], albumes_objs[7], 240, 1),
            ("Cosmic Dust", artistas_objs[4], albumes_objs[7], 225, 2),
            ("Gravity Well", artistas_objs[4], albumes_objs[7], 260, 3),
            # Ragnarok Symphony (Valkyrie Protocol)
            ("Gates of Valhalla", artistas_objs[5], albumes_objs[8], 310, 1),
            ("Shield Wall Hymn", artistas_objs[5], albumes_objs[8], 285, 2),
            ("Nordic Fire", artistas_objs[5], albumes_objs[8], 300, 3),
            # Boss Fight Overture (Valkyrie Protocol)
            ("Phase Two Awakens", artistas_objs[5], albumes_objs[9], 270, 1),
            ("Critical Strike", artistas_objs[5], albumes_objs[9], 260, 2),
            # Arcade Nostalgia (Pixel Dreams)
            ("16-Bit Hero", artistas_objs[6], albumes_objs[10], 190, 1),
            ("Insert Coin", artistas_objs[6], albumes_objs[10], 180, 2),
            ("Level Complete", artistas_objs[6], albumes_objs[10], 170, 3),
            # Late Night Velvet (Midnight Jazz Club)
            ("Blue Saxophone", artistas_objs[7], albumes_objs[11], 250, 1),
            ("Rainy Boulevard Jazz", artistas_objs[7], albumes_objs[11], 275, 2),
        ]
        canciones_objs = []
        for titulo, artista, album, duracion, pista in canciones_data:
            c, _ = Cancion.objects.get_or_create(
                titulo=titulo,
                artista=artista,
                album=album,
                defaults={
                    'duracion_seg': duracion,
                    'numero_pista': pista,
                    'es_demo': True,
                }
            )
            canciones_objs.append(c)

        # ---------------------------------------------------------------------
        # 6. PLAYLISTS DE DEMOSTRACIÓN (8 playlists)
        # ---------------------------------------------------------------------
        usuario_demo = Usuario.objects.filter(usuario='usuario').first()
        if not usuario_demo:
            usuario_demo = Usuario.objects.first()

        if usuario_demo:
            playlists_nombres = [
                ("Gaming Mode ON", "Pistas enérgicas para partidas competitivas.", True),
                ("Coding & Lo-Fi Focus", "Melodías suaves para programar y concentrarse.", True),
                ("Synthwave Nights", "Viaje sonoro retrofuturista por carreteras de neón.", True),
                ("Chillout Afternoon", "Música relajada para desconectar tras el trabajo.", True),
                ("Boss Battle Energy", "Metal y orquesta para momentos de máxima tensión.", True),
                ("Late Night Beats", "Selección nocturna para estudiar sin distracciones.", True),
                ("Retro Arcade Vibes", "Chiptunes y melodías electrónicas nostálgicas.", True),
                ("Mi Lista Personal", "Mis temas favoritos recopilados en un solo lugar.", False),
            ]
            for idx, (p_nom, p_desc, p_pub) in enumerate(playlists_nombres):
                pl, created = Playlist.objects.get_or_create(
                    usuario=usuario_demo,
                    nombre=p_nom,
                    defaults={
                        'descripcion': p_desc,
                        'publica': p_pub,
                        'es_demo': True,
                    }
                )
                if created:
                    # Añadir 3 canciones a cada playlist
                    inicio_idx = (idx * 3) % len(canciones_objs)
                    for orden, c_idx in enumerate(range(inicio_idx, inicio_idx + 3), start=1):
                        ElementoPlaylist.objects.get_or_create(
                            playlist=pl,
                            cancion=canciones_objs[c_idx % len(canciones_objs)],
                            defaults={'orden': orden}
                        )

            # Suscripción para el usuario demo
            plan_premium = PlanSuscripcion.objects.filter(codigo=PlanSuscripcion.CODIGO_INDIVIDUAL).first()
            if plan_premium:
                Suscripcion.objects.get_or_create(
                    usuario=usuario_demo,
                    defaults={'plan': plan_premium, 'estado': Suscripcion.ESTADO_ACTIVA}
                )

        # ---------------------------------------------------------------------
        # 7. TICKETS DE DEMOSTRACIÓN VINCULADOS A SOUNDFLOW (Call Center)
        # ---------------------------------------------------------------------
        if usuario_demo and canciones_objs:
            tech_user = Usuario.objects.filter(tecnico=True).first()

            # Ticket 1: Error en canción demo
            c1 = canciones_objs[0]
            ref_cancion, _ = ContenidoMusical.objects.get_or_create(
                tipo=ContenidoMusical.TIPO_CANCION,
                cancion=c1,
                defaults={
                    'nombre': f"{c1.titulo} - {c1.artista.nombre}",
                    'url_interna': f"/musica/cancion/{c1.pk}/",
                    'portada_url': c1.portada_o_default,
                    'detalles_extra': f"Artista: {c1.artista.nombre} | Álbum: {c1.album.titulo if c1.album else 'Sencillo'}"
                }
            )

            ticket1, created1 = Preguntas.objects.get_or_create(
                Titulo="Metadatos incorrectos en canción Midnight Cruise",
                Usuario=usuario_demo,
                defaults={
                    'Pregunta': "La duración mostrada difiere de la ficha oficial y el título del álbum tiene un carácter extraño.",
                    'estado': Preguntas.ESTADO_EN_PROCESO,
                    'prioridad': Preguntas.PRIORIDAD_MEDIA,
                    'categoria': 'contenido_musical',
                    'tecnico_asignado': tech_user,
                    'contenido_musical': ref_cancion,
                    'Fecha_creacion': timezone.now(),
                }
            )
            if created1 and tech_user:
                Respuesta.objects.create(
                    id_Pregunta=ticket1,
                    Usuario=tech_user,
                    Respuesta="Hola Matías, hemos revisado la ficha de la canción en SoundFlow y corregido la sincronización con el proveedor.",
                    FechaHora=timezone.now(),
                )

            # Ticket 2: Consulta sobre suscripción
            ref_sub, _ = ContenidoMusical.objects.get_or_create(
                tipo=ContenidoMusical.TIPO_SUSCRIPCION,
                nombre="Suscripción: SoundFlow Premium",
                defaults={
                    'url_interna': "/musica/suscripcion/",
                    'detalles_extra': "Plan Individual $5.99/mes"
                }
            )
            Preguntas.objects.get_or_create(
                Titulo="Duda sobre renovación de plan Premium estudiantil",
                Usuario=usuario_demo,
                defaults={
                    'Pregunta': "Quiero saber cómo acreditar mi certificado de alumno regular para cambiarme al plan Estudiantes.",
                    'estado': Preguntas.ESTADO_ABIERTO,
                    'prioridad': Preguntas.PRIORIDAD_BAJA,
                    'categoria': 'suscripciones',
                    'contenido_musical': ref_sub,
                    'Fecha_creacion': timezone.now(),
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"SoundFlow Seed completado exitosamente: {len(artistas_objs)} artistas, "
                f"{len(albumes_objs)} álbumes, {len(canciones_objs)} canciones y planes listos."
            )
        )
