"""Lo que comparten las pruebas: el guardia de lo instalado y un servidor HTTP local.

**El guardia.** Al arrancar, pytest imprime de dónde viene el ``revisor`` que está
probando: de la carpeta del proyecto (instalación editable, ``pip install -e .``)
o del paquete instalado. Con ``REVISOR_EXIGIR_INSTALADO=1`` se niega a correr si
viene de la carpeta: así el guion de lo instalado no puede probar tu
``src/revisor`` creyendo que probó la rueda. Ojo: solo mira de dónde viene
``revisor``. Si otro módulo de tu carpeta se cuela en esas pruebas (por ejemplo,
porque alguien mete ``src`` en ``sys.path``), no lo ve; eso lo ataja
``herramientas/probar-frontera.sh``.

**El servidor.** Uno de verdad, en 127.0.0.1 y en un puerto libre que elige el
sistema. Las pruebas no salen a internet.
"""

import os
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import revisor


def _origen(config: pytest.Config) -> tuple[Path, bool]:
    """De dónde se importó ``revisor``, y si es la carpeta ``src/`` del proyecto."""
    ruta = Path(revisor.__file__).resolve().parent
    carpeta = (config.rootpath / "src").resolve()
    return ruta, ruta.is_relative_to(carpeta)


def _corta(ruta: Path, config: pytest.Config) -> str:
    """La ruta, sin la parte que cambia de una máquina a otra.

    ``ruta`` ya viene resuelta; la raíz se resuelve también, porque pytest la
    toma tal cual de la línea de comandos y puede llegar por un enlace simbólico.
    """
    raiz = config.rootpath.resolve()
    if ruta.is_relative_to(raiz):
        return str(ruta.relative_to(raiz))
    partes = ruta.parts
    if "site-packages" in partes:
        return "…/" + "/".join(partes[partes.index("site-packages") :])
    return str(ruta)


def pytest_report_header(config: pytest.Config) -> str:
    ruta, de_la_carpeta = _origen(config)
    if de_la_carpeta:
        return f"revisor bajo prueba: {_corta(ruta, config)} (la CARPETA del proyecto)"
    return f"revisor bajo prueba: {_corta(ruta, config)} (el paquete INSTALADO)"


def pytest_configure(config: pytest.Config) -> None:
    if os.environ.get("REVISOR_EXIGIR_INSTALADO") != "1":
        return
    ruta, de_la_carpeta = _origen(config)
    if de_la_carpeta:
        raise pytest.UsageError(
            "REVISOR_EXIGIR_INSTALADO=1, pero revisor viene de la carpeta "
            f"{_corta(ruta, config)}. "
            "Estas pruebas probarían tu carpeta, no lo que se instala. "
            "Usa: bash herramientas/probar-instalado.sh"
        )


class _Manejador(BaseHTTPRequestHandler):
    """Rutas de práctica: cada una se porta como un tipo de servicio."""

    def do_GET(self) -> None:
        try:
            self._responder()
        except (BrokenPipeError, ConnectionResetError):
            pass  # el cliente ya se fue: es lo que prueban /grande y /goteo

    def _responder(self) -> None:
        match self.path:
            case "/ok":
                self._enviar(200, b"ok")
            case "/falla":
                self._enviar(503, b"no disponible")
            case "/grande":
                # 10 MiB anunciados; el revisor solo debe leer su tope.
                self.send_response(200)
                self.send_header("Content-Length", str(10 * 1024 * 1024))
                self.end_headers()
                for _ in range(10 * 1024):
                    self.wfile.write(b"x" * 1024)
            case "/goteo":
                # Contesta 200 enseguida y manda el cuerpo de a un byte.
                self.send_response(200)
                self.send_header("Content-Length", "1000")
                self.end_headers()
                for _ in range(1000):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.05)
            case "/a-ftp":
                self.send_response(302)
                self.send_header("Location", "ftp://ejemplo.invalid/x?token=SECRETO")
                self.end_headers()
            case _:
                self._enviar(404, b"no existe")

    def _enviar(self, codigo: int, cuerpo: bytes) -> None:
        self.send_response(codigo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, format: str, *args: object) -> None:
        pass  # sin ruido en la salida de pytest


@pytest.fixture(scope="session")
def servidor() -> Iterator[str]:
    """La URL base de un servidor local con las rutas de ``_Manejador``."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Manejador)
    httpd.daemon_threads = True
    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def colgado() -> Iterator[str]:
    """Una URL que acepta la conexión y nunca contesta.

    El socket escucha pero nadie llama a accept(): el sistema completa la
    conexión y el cliente se queda esperando la respuesta.
    """
    with socket.socket() as escucha:
        escucha.bind(("127.0.0.1", 0))
        escucha.listen(64)  # cola amplia: varias pruebas conectan a la vez
        yield f"http://127.0.0.1:{escucha.getsockname()[1]}/"


@pytest.fixture
def puerto_cerrado() -> str:
    """Una URL a un puerto donde no escucha nadie."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    return f"http://127.0.0.1:{puerto}/"
