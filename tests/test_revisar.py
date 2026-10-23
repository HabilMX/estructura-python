"""La consulta se prueba con un doble (sin red) y contra un servidor local."""

import io
import threading
import time

from revisor.revisar import (
    SIN_TIEMPO,
    URL_INVALIDA,
    ConsultorHTTP,
    drenar,
    revisar_todos,
)
from revisor.servicio import Estado, Resultado, Servicio


class ConsultorFalso:
    """Cumple el protocolo Consultor sin declararlo y sin tocar la red."""

    def __init__(self, espera_s: float = 0.0) -> None:
        self.espera_s = espera_s
        self.a_la_vez = 0
        self.maximo = 0
        self._candado = threading.Lock()

    def consultar(self, servicio: Servicio) -> Resultado:
        with self._candado:
            self.a_la_vez += 1
            self.maximo = max(self.maximo, self.a_la_vez)
        time.sleep(self.espera_s)
        with self._candado:
            self.a_la_vez -= 1
        return Resultado(servicio, Estado.ARRIBA, 1, "200")


def _servicios(n: int) -> list[Servicio]:
    return [Servicio(f"s{i}", f"https://s{i}.example") for i in range(n)]


def test_revisar_todos_conserva_el_orden() -> None:
    resultados = revisar_todos(_servicios(7), ConsultorFalso(), paralelo=3)
    assert [r.servicio.nombre for r in resultados] == [f"s{i}" for i in range(7)]


def test_revisar_todos_respeta_el_paralelo() -> None:
    falso = ConsultorFalso(espera_s=0.05)
    revisar_todos(_servicios(8), falso, paralelo=2)
    assert falso.maximo == 2


def test_revisar_todos_sin_servicios() -> None:
    assert revisar_todos([], ConsultorFalso()) == []


def test_un_servicio_sano(servidor: str) -> None:
    r = ConsultorHTTP().consultar(Servicio("ok", f"{servidor}/ok"))
    assert (r.estado, r.detalle) == (Estado.ARRIBA, "200")
    assert r.tiempo_ms is not None


def test_un_503_es_caido_pero_si_contesto(servidor: str) -> None:
    r = ConsultorHTTP().consultar(Servicio("falla", f"{servidor}/falla"))
    assert (r.estado, r.detalle) == (Estado.CAIDO, "503")


def test_un_puerto_cerrado(puerto_cerrado: str) -> None:
    r = ConsultorHTTP().consultar(Servicio("cerrado", puerto_cerrado))
    assert (r.estado, r.detalle) == (Estado.CAIDO, "conexión rechazada")


# --- Tiempos límite: cada uno con su prueba -------------------------------------


def test_el_que_nunca_contesta_respeta_su_tiempo_limite(colgado: str) -> None:
    inicio = time.monotonic()
    r = ConsultorHTTP().consultar(Servicio("colgado", colgado, timeout_s=0.3))
    transcurrido = time.monotonic() - inicio
    assert (r.estado, r.detalle) == (Estado.CAIDO, SIN_TIEMPO)
    assert 0.25 <= transcurrido < 2.0  # margen para máquinas lentas


def test_el_cuerpo_a_goteo_respeta_su_tiempo_limite(servidor: str) -> None:
    # Cada byte llega antes del tiempo límite de lectura, así que solo el reloj
    # del cuerpo completo lo puede cortar. Sin él, tardaría 50 segundos.
    inicio = time.monotonic()
    r = ConsultorHTTP().consultar(Servicio("goteo", f"{servidor}/goteo", timeout_s=0.3))
    transcurrido = time.monotonic() - inicio
    assert (r.estado, r.detalle) == (Estado.CAIDO, SIN_TIEMPO)
    assert transcurrido < 3.0


def test_los_colgados_se_esperan_en_paralelo(colgado: str) -> None:
    servicios = [Servicio(f"c{i}", colgado, timeout_s=0.3) for i in range(8)]
    inicio = time.monotonic()
    resultados = revisar_todos(servicios, ConsultorHTTP(), paralelo=8)
    assert all(r.detalle == SIN_TIEMPO for r in resultados)
    assert time.monotonic() - inicio < 1.5  # en serie serían 2.4 s o más


# --- El drenado tiene tope ------------------------------------------------------


def test_el_drenado_tiene_tope() -> None:
    cuerpo = io.BytesIO(b"x" * 1_000_000)
    assert drenar(cuerpo, tope=64 * 1024, fin=time.monotonic() + 5) is True
    assert cuerpo.tell() == 64 * 1024  # leyó su tope y ni un byte más


def test_el_drenado_respeta_el_reloj() -> None:
    cuerpo = io.BytesIO(b"x" * 1000)
    assert drenar(cuerpo, tope=64 * 1024, fin=time.monotonic() - 1) is False
    assert cuerpo.tell() == 0


def test_un_cuerpo_enorme_no_nos_detiene(servidor: str) -> None:
    inicio = time.monotonic()
    r = ConsultorHTTP().consultar(Servicio("grande", f"{servidor}/grande", timeout_s=5))
    assert (r.estado, r.detalle) == (Estado.ARRIBA, "200")
    assert time.monotonic() - inicio < 5


# --- Ningún detalle repite la URL -----------------------------------------------


def test_una_redireccion_a_ftp_no_se_sigue_ni_filtra_la_url(servidor: str) -> None:
    r = ConsultorHTTP().consultar(Servicio("ftp", f"{servidor}/a-ftp"))
    assert r.estado is Estado.CAIDO
    assert r.detalle == "redirección a un esquema que no es http ni https"
    assert "SECRETO" not in r.detalle


def test_un_puerto_cerrado_no_repite_la_url(puerto_cerrado: str) -> None:
    r = ConsultorHTTP().consultar(
        Servicio("cerrado", puerto_cerrado + "?token=SECRETO")
    )
    assert (r.estado, r.detalle) == (Estado.CAIDO, "conexión rechazada")


def test_una_url_inservible_no_se_repite() -> None:
    # urllib contesta «unknown url type: 'sin-esquema/?token=SECRETO'»: repite
    # la URL entera. El detalle no puede usar ese texto.
    r = ConsultorHTTP().consultar(Servicio("rota", "sin-esquema/?token=SECRETO"))
    assert (r.estado, r.detalle) == (Estado.CAIDO, URL_INVALIDA)
