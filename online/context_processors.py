"""
===============================================================================
CONTEXT PROCESSOR GLOBAL DE IDENTIDAD DE MARCA (online/context_processors.py)
===============================================================================
En Django, un Context Processor es una función que recibe el objeto `request`
y retorna un diccionario cuyas claves se agregan automáticamente al contexto de
TODAS las plantillas HTML del sitio.

Gracias a `brand_context`, cualquier template puede usar `{{ brand.NAME }}`,
`{{ brand.PRIMARY_COLOR }}`, `{{ brand.ICON_CLASS }}`, etc., sin que cada vista
tenga que pasar esos datos manualmente en `render()`.
===============================================================================
"""
from CallCenterGamer.brand_config import get_brand_config


def brand_context(request):
    """
    Inyecta la variable global `brand` con todos los parámetros White-Label
    activos en cada plantilla renderizada.
    """
    return {
        'brand': get_brand_config(),
    }
