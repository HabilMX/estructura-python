"""El vocabulario del programa: qué es un servicio y en qué estado lo encontramos.

Es el módulo del que dependen todos y que no depende de ninguno del proyecto: no
abre conexiones, no lee archivos y no sabe de JSON. Por eso se prueba sin red y
sin disco, y por eso no puede formar parte de un ciclo de importaciones.
"""

from dataclasses import dataclass
from enum import StrEnum

UMBRAL_LENTO_MS = 1000
"""A partir de cuántos milisegundos una respuesta correcta se considera lenta."""

TIMEOUT_POR_OMISION_S = 2.0
"""Lo que se le espera a un servicio que no declara su propio tiempo límite."""


class Estado(StrEnum):
    """Cómo encontramos un servicio. Son tres, y ninguno más."""

    ARRIBA = "ARRIBA"
    LENTO = "LENTO"
    CAIDO = "CAIDO"


@dataclass(frozen=True, slots=True)
class Servicio:
    """Algo que sabemos consultar por HTTP."""

    nombre: str
    url: str
    timeout_s: float = TIMEOUT_POR_OMISION_S


@dataclass(frozen=True, slots=True)
class Resultado:
    """Una fotografía de un servicio en el momento en que se consultó."""

    servicio: Servicio
    estado: Estado
    tiempo_ms: int | None
    """Cuánto tardó la respuesta; ``None`` si nunca llegó."""
    detalle: str
    """El código HTTP (``"200"``) o, si no hubo respuesta, por qué."""


def clasificar(
    codigo: int | None, tiempo_ms: int | None, umbral_ms: int = UMBRAL_LENTO_MS
) -> Estado:
    """Decide el estado a partir del código HTTP y del tiempo de respuesta.

    Sin código, o con un código 400 o mayor, el servicio está caído. Con una
    respuesta correcta, está lento si tardó el umbral o más.
    """
    if codigo is None or codigo >= 400:
        return Estado.CAIDO
    if tiempo_ms is not None and tiempo_ms >= umbral_ms:
        return Estado.LENTO
    return Estado.ARRIBA
