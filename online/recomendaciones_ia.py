"""
===============================================================================
MOTOR HEURÍSTICO LOCAL DE RECOMENDACIÓN (online/recomendaciones_ia.py)
===============================================================================
Este módulo implementa `RecomendadorIA`, un algoritmo local de procesamiento de
texto en español que busca en la base de datos SQLite3 tickets previamente
respondidos que sean similares a la consulta actual del usuario.

Ventajas arquitectónicas:
- Costo cero de tokens y latencia sub-milisegundo (no depende de Internet).
- Optimizado con `Prefetch` para traer preguntas y sus respuestas en 2 queries
  SQL totales, evitando el problema N+1.
===============================================================================
"""
import logging
import re
from django.db.models import Count, Prefetch
from online.models import Preguntas, Respuesta

logger = logging.getLogger(__name__)


class RecomendadorIA:
    """
    Buscador de similitud léxica ponderada sobre el historial de tickets resueltos.
    """

    def __init__(self):
        # Lista de palabras vacías (stopwords) en español que se descartan al tokenizar
        # porque no aportan significado técnico a la comparación.
        self.palabras_comunes = [
            'el', 'la', 'de', 'que', 'y', 'en', 'un', 'es', 'se', 'no',
            'te', 'lo', 'le', 'su', 'por', 'con', 'para', 'al', 'del',
            'los', 'las', 'una', 'uno', 'como', 'pero', 'mi', 'ya', 'muy',
        ]

    def recomendar_respuestas_similares(self, nueva_pregunta):
        """
        Recibe el texto de una consulta nueva y retorna hasta 3 tickets previos
        que ya tengan respuesta y superen el umbral de similitud (`> 0.15`),
        ordenados de mayor a menor coincidencia.
        """
        try:
            # Consulta optimizada: obtiene solo preguntas que tienen al menos una
            # respuesta (`respuesta__isnull=False`) y precarga sus respuestas en memoria.
            preguntas_resueltas = (
                Preguntas.objects.filter(respuesta__isnull=False)
                .prefetch_related(
                    Prefetch(
                        'respuesta_set',
                        queryset=Respuesta.objects.order_by('FechaHora'),
                    )
                )
                .distinct()
            )

            if not preguntas_resueltas:
                return []

            # Limpia signos de puntuación y extrae las palabras clave de la nueva consulta
            palabras_nueva = self._limpiar_y_tokenizar(nueva_pregunta)
            if not palabras_nueva:
                return []

            recomendaciones = []

            for pregunta in preguntas_resueltas:
                # Une título y descripción del ticket histórico para comparar vocabulario
                texto_pregunta = f"{pregunta.Titulo} {pregunta.Pregunta}"
                palabras_pregunta = self._limpiar_y_tokenizar(texto_pregunta)

                # Intersección de conjuntos: palabras significativas presentes en ambos textos
                palabras_comunes = set(palabras_nueva) & set(palabras_pregunta)
                palabras_comunes = [
                    p for p in palabras_comunes
                    if p not in self.palabras_comunes and len(p) > 3
                ]

                if palabras_comunes:
                    similitud = self._calcular_similitud(
                        palabras_nueva, palabras_pregunta, palabras_comunes
                    )

                    # Si supera el 15% de similitud ponderada, incluye la primera respuesta
                    if similitud > 0.15:
                        respuestas = list(pregunta.respuesta_set.all())
                        mejor_respuesta = respuestas[0] if respuestas else None
                        if mejor_respuesta:
                            texto_resp = mejor_respuesta.Respuesta
                            recomendaciones.append({
                                'pregunta_similar': pregunta.Titulo,
                                'respuesta': (
                                    texto_resp[:150] + "..."
                                    if len(texto_resp) > 150
                                    else texto_resp
                                ),
                                'similitud': round(similitud, 2),
                                'categoria': getattr(pregunta, 'categoria', 'otros') or 'otros',
                            })

            # Ordena de mayor a menor puntaje de similitud y devuelve el Top 3
            recomendaciones.sort(key=lambda x: x['similitud'], reverse=True)
            return recomendaciones[:3]

        except Exception as e:
            logger.error("Error en recomendaciones locales de IA: %s", e, exc_info=True)
            return []

    def _calcular_similitud(self, palabras1, palabras2, palabras_comunes):
        """
        Fórmula de similitud ponderada (normalizada en rango 0.0 a 1.0):
        - 70% del peso proviene de la cantidad de palabras clave en común.
        - 30% del peso proviene de la proporción de longitud entre ambas consultas.
        """
        if not palabras1 or not palabras2:
            return 0

        peso_palabras_comunes = len(palabras_comunes)
        peso_longitud = min(len(palabras1), len(palabras2)) / max(len(palabras1), len(palabras2))

        similitud = (peso_palabras_comunes * 0.7) + (peso_longitud * 0.3)
        return min(similitud / 5, 1.0)

    def _limpiar_y_tokenizar(self, texto):
        """
        Normaliza un texto convirtiéndolo a minúsculas, eliminando signos de
        puntuación (conservando tildes y eñes del español) y filtrando palabras
        de menos de 3 letras o incluidas en `self.palabras_comunes`.
        """
        if not texto:
            return []

        texto_limpio = re.sub(r'[^\w\sáéíóúñ]', '', texto.lower())
        palabras = [
            palabra for palabra in texto_limpio.split()
            if palabra not in self.palabras_comunes and len(palabra) > 2
        ]

        return palabras

    def obtener_preguntas_populares(self, limite=5):
        """
        Retorna los tickets con mayor número de respuestas utilizando agregación
        SQL `Count('respuesta')` a través del ORM de Django.
        """
        try:
            preguntas_populares = (
                Preguntas.objects.annotate(num_respuestas=Count('respuesta'))
                .filter(num_respuestas__gt=0)
                .order_by('-num_respuestas')[:limite]
            )

            return [
                {
                    'titulo': p.Titulo,
                    'respuestas': p.num_respuestas,
                    'categoria': getattr(p, 'categoria', 'otros') or 'otros',
                }
                for p in preguntas_populares
            ]
        except Exception as e:
            logger.error("Error obteniendo preguntas populares: %s", e, exc_info=True)
            return []
