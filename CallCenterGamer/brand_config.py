"""
===============================================================================
CONFIGURACIÓN CENTRALIZADA WHITE-LABEL / MULTI-EMPRESA (brand_config.py)
===============================================================================
Este módulo desacopla todos los elementos comerciales y visuales del negocio
(nombre de la marca, textos de bienvenida, íconos FontAwesome, paleta de colores
CSS, dirección física, prompt del rol de IA y catálogo de categorías de tickets)
para que la plataforma pueda adaptarse a cualquier otra empresa o rubro
simplemente cambiando variables de entorno en `.env` o en Render, sin tocar la
lógica de negocio ni las plantillas.
===============================================================================
"""
import os
from django.conf import settings


def load_brand_config_from_env():
    """
    Lee las variables de entorno `BRAND_*` y construye el diccionario maestro
    de identidad visual y comercial. Si una variable no está definida, utiliza
    los valores por defecto de CallCenterGamer.
    """
    # Lee la lista de categorías de tickets separadas por coma desde BRAND_CATEGORIES
    raw_categories = os.environ.get(
        'BRAND_CATEGORIES',
        'hardware,software,conexion,cuenta,pago,rendimiento,otros',
    )
    categories = [c.strip().lower() for c in raw_categories.split(',') if c.strip()]
    # Garantiza que siempre exista la categoría comodín 'otros' como respaldo
    if 'otros' not in categories:
        categories.append('otros')

    return {
        # Nombre corto de la marca mostrado en la barra de navegación y títulos
        'NAME': os.environ.get('BRAND_NAME', 'CallCenterGamer'),
        # Título principal del banner de bienvenida en la portada
        'WELCOME_TITLE': os.environ.get('BRAND_WELCOME_TITLE', 'Bienvenido a Call of Gamers!'),
        # Descripción o eslogan comercial de la empresa
        'SLOGAN': os.environ.get(
            'BRAND_SLOGAN',
            'Comunicate con el mejor call center gamer, nosotros te brindaremos la '
            'solución necesaria para tu problema, no dudes más!',
        ),
        # Título de la sección de disponibilidad de servicio
        'SERVICE_TITLE': os.environ.get('BRAND_SERVICE_TITLE', 'Atención 24/7'),
        # Textos de llamada a la acción (Call To Action) inferiores
        'CTA_TITLE': os.environ.get('BRAND_CTA_TITLE', 'Comunicate con nosotros'),
        'CTA_SUBTITLE': os.environ.get(
            'BRAND_CTA_SUBTITLE',
            'Escribenos y nuestros profesionales solucionaran tu problema en tan solo un momento!',
        ),
        # Clase de ícono FontAwesome mostrada junto al logo (ej. 'fas fa-gamepad' o 'fas fa-headset')
        'ICON_CLASS': os.environ.get('BRAND_ICON_CLASS', 'fas fa-gamepad'),
        # Ruta relativa dentro de static/ para el archivo de imagen de logo
        'LOGO_STATIC': os.environ.get('BRAND_LOGO_STATIC', 'img/LOGITO.png'),
        # Paleta de colores corporativos inyectada como variables CSS (:root)
        'PRIMARY_COLOR': os.environ.get('BRAND_PRIMARY_COLOR', '#4E31E1'),
        'SECONDARY_COLOR': os.environ.get('BRAND_SECONDARY_COLOR', '#673de6'),
        'ACCENT_COLOR': os.environ.get('BRAND_ACCENT_COLOR', '#25c2b5'),
        # Dirección mostrada en el pie de página (footer)
        'FOOTER_ADDRESS': os.environ.get(
            'BRAND_FOOTER_ADDRESS',
            'Av. Américo Vespucio 974, Maipú, Región Metropolitana',
        ),
        # Instrucción de sistema (System Prompt) enviada al asistente de IA
        'AI_ROLE_PROMPT': os.environ.get(
            'BRAND_AI_ROLE_PROMPT',
            'Eres un experto técnico en videojuegos y hardware gaming.',
        ),
        # Lista de categorías válidas para clasificar tickets en esta empresa
        'TICKET_CATEGORIES': categories,
    }


def get_brand_config():
    """
    Devuelve el diccionario de configuración de marca activo.
    Combina los valores por defecto del entorno con cualquier sobrescritura
    realizada en `settings.BRAND_CONFIG` (muy útil para pruebas automatizadas
    con `@override_settings`).
    """
    base = load_brand_config_from_env()
    configured = getattr(settings, 'BRAND_CONFIG', None)
    if isinstance(configured, dict):
        merged = {**base, **configured}
    else:
        merged = base

    # Si se modificó settings.TICKET_CATEGORIES directamente, mantiene sincronía
    if hasattr(settings, 'TICKET_CATEGORIES') and not (
        isinstance(configured, dict) and 'TICKET_CATEGORIES' in configured
    ):
        merged['TICKET_CATEGORIES'] = list(settings.TICKET_CATEGORIES)

    return merged


def get_ticket_categories():
    """
    Retorna la lista de categorías de tickets activas en la configuración actual
    de marca (`TICKET_CATEGORIES`), centralizando en un único punto el fallback
    estándar para formularios y clasificadores de IA.
    """
    brand = get_brand_config()
    return list(
        brand.get(
            'TICKET_CATEGORIES',
            ['hardware', 'software', 'conexion', 'cuenta', 'pago', 'rendimiento', 'otros'],
        )
    )

