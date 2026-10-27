"""
===============================================================================
MOTOR DE INTELIGENCIA ARTIFICIAL GENERATIVA Y RESILIENCIA (online/ia_utils.py)
===============================================================================
Este módulo implementa la clase `AsistenteIA`, encargada de:
1. Generar respuestas automáticas de diagnóstico técnico (`generar_respuesta_automatica`).
2. Clasificar tickets entrantes dentro del catálogo de categorías de la empresa
   (`clasificar_pregunta`).

Arquitectura Resiliente (Mejora 2 - Evaluación N° 3):
- Si la variable de entorno `OPENAI_API_KEY` está configurada, utiliza el SDK
  oficial de OpenAI (`gpt-3.5-turbo`).
- Si `OPENAI_API_KEY` está vacía o se produce cualquier error externo (timeout,
  límite de cuota, caída de red), el sistema NUNCA colapsa ni muestra el error
  técnico al usuario: conmuta de forma transparente a su motor heurístico local
  (`_clasificar_localmente` y `_generar_respuesta_local`) y registra el evento
  mediante el módulo `logging`.
===============================================================================
"""
import logging
from django.conf import settings
from openai import OpenAI
from CallCenterGamer.brand_config import get_brand_config, get_ticket_categories

# Logger del módulo para registrar llamadas y fallbacks en logs/callcenter.log
logger = logging.getLogger(__name__)


class AsistenteIA:
    """
    Servicio híbrido de asistencia y clasificación de tickets de soporte.
    """

    # Diccionario de palabras clave en español por categoría para el clasificador
    # local cuando no se dispone de conexión con OpenAI.
    KEYWORDS_CATEGORIAS = {
        'hardware': [
            'gpu', 'placa', 'tarjeta', 'ram', 'memoria', 'procesador', 'cpu',
            'temperatura', 'calienta', 'pantalla', 'monitor', 'teclado', 'mouse',
            'auriculares', 'audio', 'sonido', 'disco', 'ssd', 'fuente', 'enciende',
        ],
        'software': [
            'driver', 'drivers', 'windows', 'actualizacion', 'actualizar', 'instalar',
            'instalacion', 'crash', 'cierra', 'error', 'dll', 'directx', 'inicia',
            'pantalla azul', 'bsod', 'sistema', 'juego no abre',
        ],
        'conexion': [
            'internet', 'ping', 'latencia', 'lag', 'red', 'wifi', 'ethernet',
            'servidor', 'desconecta', 'conexion', 'conectividad', 'paquetes', 'dns',
        ],
        'cuenta': [
            'cuenta', 'password', 'contraseña', 'login', 'acceso', 'baneo', 'ban',
            'correo', 'verificacion', '2fa', 'hackearon', 'bloqueada', 'perfil',
        ],
        'pago': [
            'pago', 'tarjeta de credito', 'cobro', 'factura', 'reembolso', 'compra',
            'tienda', 'suscripcion', 'transaccion', 'boleta', 'precio',
        ],
        'rendimiento': [
            'fps', 'lento', 'tirones', 'stuttering', 'bajos fps', 'optimizar',
            'rendimiento', 'graficos', 'congela', 'fluidez', 'carga lenta',
        ],
    }

    def __init__(self):
        """Inicializa el asistente leyendo la clave de API desde `django.conf.settings`."""
        self.api_key = getattr(settings, 'OPENAI_API_KEY', '')

    def _client(self):
        """
        Construye y retorna el cliente oficial de OpenAI.
        Si no hay API Key configurada, lanza `RuntimeError` controlado para activar el fallback.
        """
        if not self.api_key:
            raise RuntimeError("La variable de entorno OPENAI_API_KEY no está configurada.")
        return OpenAI(api_key=self.api_key)

    def _clasificar_localmente(self, pregunta, categorias_validas):
        """
        Evalúa cuántas palabras clave de cada categoría aparecen en el texto de la
        pregunta y devuelve la categoría con mayor coincidencia (o `'otros'` por defecto).
        """
        if not pregunta:
            return 'otros' if 'otros' in categorias_validas else categorias_validas[-1]

        texto = pregunta.lower()
        mejor_categoria = 'otros' if 'otros' in categorias_validas else categorias_validas[-1]
        max_coincidencias = 0

        for categoria, palabras in self.KEYWORDS_CATEGORIAS.items():
            if categoria not in categorias_validas:
                continue
            coincidencias = sum(1 for palabra in palabras if palabra in texto)
            if coincidencias > max_coincidencias:
                max_coincidencias = coincidencias
                mejor_categoria = categoria

        return mejor_categoria

    def _generar_respuesta_local(self, pregunta):
        """
        Construye una respuesta de diagnóstico preliminar 100% local combinando:
        1. La guía técnica base correspondiente a la categoría detectada.
        2. La mejor respuesta histórica encontrada en SQLite3 por `RecomendadorIA`.
        """
        from online.recomendaciones_ia import RecomendadorIA

        categorias_validas = get_ticket_categories()
        categoria = self._clasificar_localmente(pregunta, categorias_validas)

        # Recomendaciones técnicas estáticas de primera línea según el tipo de problema
        guias_por_categoria = {
            'hardware': (
                "Te recomendamos verificar la temperatura de tus componentes (CPU/GPU), "
                "comprobar que los cables de alimentación y video estén bien conectados "
                "y probar el periférico o componente en otro puerto."
            ),
            'software': (
                "Te sugerimos verificar la integridad de los archivos del juego, "
                "actualizar los controladores (drivers) de video a la última versión "
                "y ejecutar la aplicación como administrador."
            ),
            'conexion': (
                "Te aconsejamos reiniciar tu router, priorizar una conexión por cable "
                "Ethernet sobre Wi-Fi, y verificar que el firewall no bloquee los "
                "puertos del servidor del juego."
            ),
            'cuenta': (
                "Por seguridad, verifica tu bandeja de correo electrónico asociada, "
                "utiliza la opción de recuperación de credenciales y nunca compartas "
                "tu contraseña con terceros."
            ),
            'pago': (
                "Revisa el estado del movimiento en tu medio de pago y conserva el "
                "comprobante de transacción. Un especialista validará tu caso."
            ),
            'rendimiento': (
                "Prueba reducir la calidad de sombras y antialiasing en los ajustes "
                "gráficos, cerrar aplicaciones en segundo plano y activar el modo de "
                "alto rendimiento de energía."
            ),
        }

        guia_base = guias_por_categoria.get(
            categoria,
            "Hemos analizado tu consulta. Te recomendamos detallar el modelo de tu "
            "equipo y los pasos previos al incidente para que un técnico especializado "
            "te brinde una solución precisa.",
        )

        # Intenta enriquecer la respuesta con casos reales resueltos en la base de datos
        try:
            recomendador = RecomendadorIA()
            similares = recomendador.recomendar_respuestas_similares(pregunta)
            if similares:
                mejor = similares[0]
                return (
                    f"Diagnóstico preliminar ({categoria.capitalize()}): {guia_base}\n\n"
                    f"Además, encontramos una solución previa relacionada a "
                    f"«{mejor['pregunta_similar']}»: {mejor['respuesta']}"
                )
        except Exception as exc:
            logger.warning("No se pudieron adjuntar recomendaciones locales: %s", exc)

        return f"Diagnóstico preliminar ({categoria.capitalize()}): {guia_base}"

    def generar_respuesta_automatica(self, pregunta, historial_contexto=""):
        """
        Genera una respuesta técnica para el usuario.
        - Si hay `OPENAI_API_KEY`: Consulta `gpt-3.5-turbo` usando el prompt de rol
          configurado en White-Label (`BRAND_AI_ROLE_PROMPT`).
        - Si no hay clave o falla la llamada: Retorna `_generar_respuesta_local(pregunta)`.
        """
        if not self.api_key:
            logger.info(
                "OPENAI_API_KEY no configurada; generando respuesta con motor heurístico local."
            )
            return self._generar_respuesta_local(pregunta)

        try:
            brand = get_brand_config()
            role_prompt = brand.get(
                'AI_ROLE_PROMPT',
                'Eres un experto técnico en videojuegos y hardware gaming.',
            )
            prompt = f"""
            {role_prompt}

            Contexto del historial: {historial_contexto}

            Pregunta del usuario: {pregunta}

            Por favor, proporciona una respuesta útil, técnica pero comprensible.
            Si necesitas más información, pídela amablemente.
            Mantén un tono profesional pero cercano.

            Respuesta:
            """

            response = self._client().chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": role_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=500,
                temperature=0.7,
            )

            contenido = (response.choices[0].message.content or "").strip()
            if contenido:
                return contenido
            return self._generar_respuesta_local(pregunta)

        except Exception as e:
            logger.warning(
                "Fallo en llamada a OpenAI (generar_respuesta_automatica); "
                "activando fallback local. Detalle técnico: %s",
                e,
                exc_info=True,
            )
            return self._generar_respuesta_local(pregunta)

    def clasificar_pregunta(self, pregunta):
        """
        Clasifica el texto de un ticket en una de las categorías activas de la empresa.
        - Si hay `OPENAI_API_KEY`: Usa `gpt-3.5-turbo` con temperatura baja (`0.3`).
        - Si no hay clave o falla la API: Usa `_clasificar_localmente()`.
        """
        categorias = get_ticket_categories()

        if not self.api_key:
            categoria_local = self._clasificar_localmente(pregunta, categorias)
            logger.debug(
                "Pregunta clasificada localmente sin API Key como '%s'.", categoria_local
            )
            return categoria_local

        try:
            prompt = f"""
            Clasifica la siguiente pregunta del usuario en una de estas categorías: {', '.join(categorias)}

            Pregunta: {pregunta}

            Responde solo con la categoría más apropiada.
            """

            response = self._client().chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.3,
            )

            categoria = (response.choices[0].message.content or "").strip().lower()
            if categoria in categorias:
                return categoria
            return self._clasificar_localmente(pregunta, categorias)

        except Exception as e:
            logger.warning(
                "Fallo en llamada a OpenAI (clasificar_pregunta); "
                "usando clasificador local. Detalle técnico: %s",
                e,
                exc_info=True,
            )
            return self._clasificar_localmente(pregunta, categorias)
