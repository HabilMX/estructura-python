#!/usr/bin/env bash
# Corre las pruebas contra el paquete INSTALADO, no contra tu carpeta.
#
# Qué hace, en una carpeta temporal:
#   1. crea un entorno virtual nuevo y vacío;
#   2. instala el proyecto SIN -e: pip construye la rueda (el .whl) y la instala,
#      igual que lo haría cualquiera que use tu paquete;
#   3. corre pytest con REVISOR_EXIGIR_INSTALADO=1: si por cualquier razón el
#      revisor viniera de tu carpeta, tests/conftest.py se niega a correr.
#
# Por qué: con «pip install -e .» Python lee tu carpeta src/ completa. Un
# archivo que existe ahí pero que no viaja en la rueda pasa tus pruebas y le
# truena a quien instala. Este guion ve lo mismo que esa persona.
#
# Uso:  bash herramientas/probar-instalado.sh   → sale 0 si todo pasó
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=herramientas/_comun.sh
source "$raiz/herramientas/_comun.sh"

tmp="$(mktemp -d)"
# Al salir se borra la carpeta temporal, y el código de salida se conserva. Con
# el bash 3.2 que trae macOS, si el guion se corta por una variable sin definir
# (set -u), la trampa recibe un 0 en «$?»: sin la bandera «terminado», un
# guion cortado a la mitad saldría 0, un falso verde (medido). Por eso, si no
# llegó al final, sale 1 aunque «$?» diga 0.
salir() {
  local codigo=$?
  rm -rf "$tmp"
  if [ "$codigo" -eq 0 ] && [ "${terminado:-}" != 1 ]; then
    echo "❌ el guion se cortó antes de terminar" >&2
    codigo=1
  fi
  exit "$codigo"
}
trap salir EXIT

echo "entorno nuevo con $("$PY" --version)"
crear_entorno "$tmp/entorno" "$raiz"
"$tmp/entorno/bin/python" -m pip install -q --disable-pip-version-check "$raiz"

rc=0
correr_pruebas "$tmp/entorno" "$raiz" "$tmp/informe.xml" REVISOR_EXIGIR_INSTALADO=1 || rc=$?
origen_bajo_prueba "$tmp/informe.xml"

read -r total pasaron fallaron errores saltadas < <(contar "$tmp/informe.xml" | head -n 1)
echo "pruebas: $total · pasaron $pasaron · fallaron $fallaron · con error $errores · saltadas $saltadas"

if [ "$rc" -ne 0 ] || [ "$total" -eq 0 ] || [ "$pasaron" -ne "$total" ]; then
  contar "$tmp/informe.xml" | tail -n +2 | sed 's/^/   ✗ /'
  echo "--- final de la salida de pytest ---"
  tail -n 15 "$tmp/informe.xml.log"
  echo "❌ lo instalado NO pasa sus pruebas (pytest salió con $rc)"
  exit 1
fi
echo "✅ lo instalado pasa sus pruebas"
terminado=1
