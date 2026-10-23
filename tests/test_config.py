"""La configuración se prueba con texto: ``servicios_desde`` no necesita archivos."""

from pathlib import Path

import pytest

from revisor.config import ErrorDeConfiguracion, leer_servicios, servicios_desde

BUENO = """
[[servicios]]
nombre = "a"
url = "https://a.example/salud"

[[servicios]]
nombre = "b"
url = "http://b.example:8080"
timeout = 0.5
"""


def test_lee_una_lista_valida() -> None:
    a, b = servicios_desde(BUENO)
    assert (a.nombre, a.url, a.timeout_s) == ("a", "https://a.example/salud", 2.0)
    assert (b.nombre, b.timeout_s) == ("b", 0.5)


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("nada = 1", "no declara ningún [[servicios]]"),
        ("[[servicios]]\nurl = 'https://a.example'", "servicio 1: falta 'nombre'"),
        ("[[servicios]]\nnombre = 'a'", "servicio 1 (a): falta 'url'"),
        (
            "[[servicios]]\nnombre = 'a'\nurl = 'ftp://a.example'",
            "tiene que empezar con http:// o https://",
        ),
        ("[[servicios]]\nnombre = 'a'\nurl = 'https://'", "le falta el servidor"),
        (
            "[[servicios]]\nnombre = 'a'\nurl = 'https://a.example'\ntiemout = 3",
            "campo desconocido 'tiemout'",
        ),
        (
            "[[servicios]]\nnombre = 'a'\nurl = 'https://a.example'\ntimeout = 0",
            "'timeout' tiene que ser",
        ),
        (
            "[[servicios]]\nnombre = 'a'\nurl = 'https://a.example'\ntimeout = true",
            "'timeout' tiene que ser",
        ),
        (
            "[[servicios]]\nnombre = 'a'\nurl = 'https://a.example'\n"
            "[[servicios]]\nnombre = 'a'\nurl = 'https://b.example'",
            "servicio 2: el nombre 'a' ya estaba en el 1",
        ),
        ("esto no es toml", "no es TOML válido"),
    ],
)
def test_rechaza_lo_que_no_sirve(texto: str, mensaje: str) -> None:
    with pytest.raises(ErrorDeConfiguracion) as error:
        servicios_desde(texto)
    assert mensaje in str(error.value)


def test_rechaza_credenciales_sin_repetirlas() -> None:
    texto = "[[servicios]]\nnombre = 'a'\nurl = 'https://yo:CLAVE_SECRETA@a.example'"
    with pytest.raises(ErrorDeConfiguracion) as error:
        servicios_desde(texto)
    assert "las credenciales no van en la URL" in str(error.value)
    assert "CLAVE_SECRETA" not in str(error.value)


def test_un_archivo_que_no_existe(tmp_path: Path) -> None:
    with pytest.raises(ErrorDeConfiguracion, match="no existe el archivo"):
        leer_servicios(tmp_path / "no-existe.toml")


def test_el_ejemplo_del_repo_es_valido() -> None:
    # El servicios.toml de la raíz es el que usa «Córrelo»: si alguien lo
    # rompe, se entera aquí y no el primer lector.
    ejemplo = Path(__file__).parent.parent / "servicios.toml"
    nombres = [s.nombre for s in leer_servicios(ejemplo)]
    assert nombres == ["python.org", "docs.python.org", "no-existe"]
