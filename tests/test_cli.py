"""La línea de comandos se prueba por sus dos puertas: ``main(argv)`` y el comando."""

import subprocess
import sys
from importlib.metadata import entry_points, version
from pathlib import Path

import pytest

from revisor.cli import main


def _config(tmp_path: Path, *urls: str) -> Path:
    ruta = tmp_path / "servicios.toml"
    ruta.write_text(
        "".join(
            f'[[servicios]]\nnombre = "s{i}"\nurl = "{u}"\ntimeout = 2\n\n'
            for i, u in enumerate(urls)
        ),
        encoding="utf-8",
    )
    return ruta


def test_todo_arriba_sale_con_0(
    tmp_path: Path, servidor: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--config", str(_config(tmp_path, f"{servidor}/ok"))]) == 0
    salida = capsys.readouterr()
    assert "1 servicio · 1 arriba" in salida.out
    assert salida.err == ""


def test_algo_caido_sale_con_1(
    tmp_path: Path, servidor: str, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path, f"{servidor}/ok", f"{servidor}/falla")
    assert main(["--config", str(config), "--formato", "json"]) == 1
    assert '"caido": 1' in capsys.readouterr().out


def test_una_configuracion_rota_sale_con_2_por_la_salida_de_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--config", str(tmp_path / "no-existe.toml")]) == 2
    salida = capsys.readouterr()
    assert salida.out == ""
    assert salida.err.startswith("error de configuración: no existe el archivo")


@pytest.mark.parametrize("argv", [["--formato", "xml"], ["--paralelo", "0"]])
def test_un_uso_invalido_sale_con_2(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        main(argv)
    assert salida.value.code == 2


def test_la_version_sale_de_lo_instalado(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out == f"revisor {version('revisor')}\n"


def test_el_comando_revisor_apunta_a_main() -> None:
    # [project.scripts] crea el comando al instalar: aquí se comprueba que el
    # paquete instalado lo declara y que lleva a esta misma función.
    (comando,) = entry_points(group="console_scripts", name="revisor")
    assert comando.value == "revisor.cli:main"
    assert comando.load() is main


def test_python_m_revisor(tmp_path: Path) -> None:
    # Un proceso aparte, como lo correría una persona. Se corre en tmp_path para
    # que la carpeta actual no le preste nada al import.
    proceso = subprocess.run(
        [sys.executable, "-m", "revisor", "--config", "no-existe.toml"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proceso.returncode == 2
    assert "no existe el archivo no-existe.toml" in proceso.stderr
