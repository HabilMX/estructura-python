"""Lee la lista de servicios de un archivo TOML y la valida.

No toca la red. ``leer_servicios`` recibe una ruta; ``servicios_desde`` recibe el
texto ya leído, así que las pruebas no necesitan archivos.

El archivo tiene esta forma::

    [[servicios]]
    nombre = "python.org"
    url = "https://www.python.org"
    timeout = 3        # segundos; opcional
"""

import math
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from revisor.servicio import TIMEOUT_POR_OMISION_S, Servicio

CAMPOS = frozenset({"nombre", "url", "timeout"})
TIMEOUT_MAXIMO_S = 60.0


class ErrorDeConfiguracion(Exception):
    """El archivo de servicios no existe, no se puede leer o no tiene sentido."""


def leer_servicios(ruta: Path) -> list[Servicio]:
    """Lee y valida el archivo de servicios."""
    try:
        texto = ruta.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ErrorDeConfiguracion(f"no existe el archivo {ruta}") from None
    except (OSError, UnicodeDecodeError) as error:
        raise ErrorDeConfiguracion(
            f"no se pudo leer {ruta}: {type(error).__name__}"
        ) from None
    return servicios_desde(texto)


def servicios_desde(texto: str) -> list[Servicio]:
    """Convierte el texto TOML en una lista de servicios validada.

    El primer problema que encuentra dice en qué servicio está, contando desde 1.
    """
    try:
        datos = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as error:
        raise ErrorDeConfiguracion(f"el archivo no es TOML válido: {error}") from None

    crudos = datos.get("servicios")
    if not isinstance(crudos, list) or not crudos:
        raise ErrorDeConfiguracion("el archivo no declara ningún [[servicios]]")

    servicios: list[Servicio] = []
    vistos: dict[str, int] = {}
    for posicion, crudo in enumerate(crudos, start=1):
        servicio = _servicio(posicion, crudo)
        if servicio.nombre in vistos:
            raise ErrorDeConfiguracion(
                f"servicio {posicion}: el nombre {servicio.nombre!r} "
                f"ya estaba en el {vistos[servicio.nombre]}"
            )
        vistos[servicio.nombre] = posicion
        servicios.append(servicio)
    return servicios


def _servicio(posicion: int, crudo: Any) -> Servicio:
    if not isinstance(crudo, dict):
        raise ErrorDeConfiguracion(f"servicio {posicion}: no es una tabla")
    sobran = sorted(set(crudo) - CAMPOS)
    if sobran:
        # Un campo mal escrito («tiemout») es un error, no un silencio.
        raise ErrorDeConfiguracion(
            f"servicio {posicion}: campo desconocido {sobran[0]!r}"
        )

    nombre = crudo.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip():
        raise ErrorDeConfiguracion(f"servicio {posicion}: falta 'nombre'")

    url = crudo.get("url")
    if not isinstance(url, str):
        raise ErrorDeConfiguracion(f"servicio {posicion} ({nombre}): falta 'url'")
    _validar_url(posicion, nombre, url)

    timeout = crudo.get("timeout", TIMEOUT_POR_OMISION_S)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, int | float)
        or not math.isfinite(timeout)
        or not 0 < timeout <= TIMEOUT_MAXIMO_S
    ):
        raise ErrorDeConfiguracion(
            f"servicio {posicion} ({nombre}): 'timeout' tiene que ser un número "
            f"de segundos mayor que 0 y no mayor que {TIMEOUT_MAXIMO_S:g}"
        )
    return Servicio(nombre=nombre, url=url, timeout_s=float(timeout))


def _validar_url(posicion: int, nombre: str, url: str) -> None:
    """Exige http o https y rechaza usuario y contraseña dentro de la URL.

    🔒 Una URL como ``https://usuario:clave@host`` lleva un secreto escrito en el
    archivo, y una URL termina en bitácoras y reportes. Si un servicio pide
    credenciales, van en otro lado, nunca en la URL. Por eso ningún mensaje de
    aquí repite la URL: solo dice qué está mal.
    """
    prefijo = f"servicio {posicion} ({nombre})"
    try:
        partes = urlsplit(url)
        _ = partes.port  # un puerto que no es número revienta aquí
    except ValueError:
        raise ErrorDeConfiguracion(f"{prefijo}: la URL no se puede leer") from None
    if partes.scheme not in ("http", "https"):
        raise ErrorDeConfiguracion(
            f"{prefijo}: la URL tiene que empezar con http:// o https://"
        )
    if not partes.hostname:
        raise ErrorDeConfiguracion(f"{prefijo}: a la URL le falta el servidor")
    if partes.username is not None or partes.password is not None:
        raise ErrorDeConfiguracion(
            f"{prefijo}: la URL trae usuario o contraseña (usuario:clave@...); "
            "las credenciales no van en la URL"
        )
