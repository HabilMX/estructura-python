"""Consulta muchos servicios a la vez.

Aquí vive ``Consultor``, el protocolo que ``revisar_todos`` necesita: alguien que
consulte UN servicio. Se declara del lado que lo usa, no del que lo implementa.
``ConsultorHTTP`` lo cumple sin heredar de él, y en las pruebas lo cumple un doble
que no toca la red.
"""

import socket
import time
import urllib.request
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException, HTTPResponse
from typing import IO, Protocol
from urllib.error import HTTPError, URLError

from revisor.servicio import Estado, Resultado, Servicio, clasificar

TOPE_DRENADO = 64 * 1024
"""Lo más que se lee del cuerpo de una respuesta, en bytes, para tirarlo."""

TROZO = 8 * 1024

SIN_TIEMPO = "se acabó el tiempo de espera"
REDIRECCION_PROHIBIDA = "redirección a un esquema que no es http ni https"
URL_INVALIDA = "la URL no se puede usar"


class Consultor(Protocol):
    """Lo único que ``revisar_todos`` necesita: alguien que consulte un servicio."""

    def consultar(self, servicio: Servicio) -> Resultado: ...


def revisar_todos(
    servicios: Sequence[Servicio], consultor: Consultor, paralelo: int = 5
) -> list[Resultado]:
    """Consulta todos los servicios, hasta ``paralelo`` a la vez.

    Devuelve los resultados en el mismo orden que los servicios. Cada consulta
    tiene su propio tiempo límite, así que un servicio colgado no detiene a los
    demás más allá del suyo.
    """
    if paralelo < 1:
        raise ValueError("paralelo tiene que ser al menos 1")
    if not servicios:
        return []
    with ThreadPoolExecutor(max_workers=min(paralelo, len(servicios))) as hilos:
        return list(hilos.map(consultor.consultar, servicios))


class _SoloHTTP(urllib.request.HTTPRedirectHandler):
    """Sigue redirecciones solo hacia http o https.

    urllib, por su cuenta, también seguiría una redirección hacia ftp://.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.lower().startswith(("http://", "https://")):
            # Sin la URL en el mensaje: podría traer un token.
            raise URLError(REDIRECCION_PROHIBIDA)
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


class ConsultorHTTP:
    """Consulta un servicio con un GET y mira qué contesta.

    Cuida tres cosas que una plantilla no debe enseñar mal:

    - **Tiempo límite siempre.** Cada servicio trae el suyo; se aplica a la
      conexión, a cada lectura y al cuerpo completo. Sin él, un servicio que
      acepta la conexión y nunca contesta colgaría la revisión.
    - **El cuerpo se drena con tope.** Se leen como mucho ``tope_bytes``, y no
      se empieza una lectura nueva pasado el tiempo límite: un servicio que
      contesta 200 con un cuerpo enorme, o que lo manda gota a gota, no nos
      tiene leyendo sin fin.
    - **Ningún detalle repite la URL.** Los errores de urllib suelen traer la
      URL completa, con su query string; aquí se traducen a frases fijas.

    Límites conocidos:

    - El reloj se revisa antes de cada lectura, y una lectura puede esperar
      hasta un tiempo límite más. En el peor caso, el cuerpo se deja de leer
      cerca del doble del tiempo límite (medido: 0.6 s con 0.3).
    - El tiempo se aplica a cada lectura de los encabezados, no a todos juntos.
      Un servidor que mande los encabezados byte por byte, justo antes de cada
      tiempo límite, puede alargar la consulta.
    - La resolución del nombre del servidor (DNS) no la acota el tiempo límite
      de urllib: un DNS lento alarga la consulta lo que él tarde.
    """

    def __init__(self, tope_bytes: int = TOPE_DRENADO) -> None:
        self._tope = tope_bytes
        self._abridor = urllib.request.build_opener(_SoloHTTP)

    def consultar(self, servicio: Servicio) -> Resultado:
        inicio = time.monotonic()
        fin = inicio + servicio.timeout_s
        try:
            peticion = urllib.request.Request(servicio.url, method="GET")
            with self._abridor.open(peticion, timeout=servicio.timeout_s) as respuesta:
                codigo = int(respuesta.status)
                if not drenar(respuesta, self._tope, fin):
                    return Resultado(servicio, Estado.CAIDO, None, SIN_TIEMPO)
        except HTTPError as error:
            # 4xx o 5xx: el servicio SÍ contestó. No se lee el cuerpo.
            codigo = error.code
            error.close()
        except TimeoutError:
            return Resultado(servicio, Estado.CAIDO, None, SIN_TIEMPO)
        except URLError as error:
            return Resultado(servicio, Estado.CAIDO, None, _motivo(error.reason))
        except ValueError:
            # urllib repite la URL completa en este error: no se usa su texto.
            return Resultado(servicio, Estado.CAIDO, None, URL_INVALIDA)
        except (HTTPException, OSError) as error:
            return Resultado(
                servicio, Estado.CAIDO, None, f"error de red ({type(error).__name__})"
            )
        tiempo_ms = round((time.monotonic() - inicio) * 1000)
        return Resultado(
            servicio, clasificar(codigo, tiempo_ms), tiempo_ms, str(codigo)
        )


def drenar(respuesta: HTTPResponse | IO[bytes], tope: int, fin: float) -> bool:
    """Lee y tira el cuerpo, hasta ``tope`` bytes y hasta el instante ``fin``.

    Devuelve ``False`` si se acabó el tiempo antes de terminar; ``True`` si el
    cuerpo terminó o si se alcanzó el tope (pasado el tope ya no interesa).
    """
    leidos = 0
    while leidos < tope:
        if time.monotonic() >= fin:
            return False
        trozo = respuesta.read1(min(TROZO, tope - leidos))  # type: ignore[union-attr]
        if not trozo:
            return True
        leidos += len(trozo)
    return True


def _motivo(razon: object) -> str:
    """Traduce el motivo de un URLError a una frase corta y sin la URL."""
    if isinstance(razon, TimeoutError):
        return SIN_TIEMPO
    if isinstance(razon, socket.gaierror):
        return "no se encontró el servidor"
    if isinstance(razon, ConnectionRefusedError):
        return "conexión rechazada"
    if razon == REDIRECCION_PROHIBIDA:
        return REDIRECCION_PROHIBIDA
    return f"no responde ({type(razon).__name__})"
