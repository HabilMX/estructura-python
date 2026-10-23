#!/usr/bin/env bash
# La frontera que sabe fallar: comprueba que lo que no está en el paquete NO
# llega a quien lo instala, y que las pruebas instaladas lo notan.
#
# Qué hace, en una COPIA temporal del proyecto (tu carpeta no se toca):
#
#   Siembra src/suelto.py, un módulo que vive en src/ pero FUERA del paquete
#   revisor, y tests/test_suelto.py, una prueba que lo importa. Luego corre la
#   suite completa dos veces, en dos entornos nuevos con el mismo Python, la
#   misma copia y la misma versión de pytest. Entre las dos solo cambia UNA
#   bandera de pip: -e.
#
#   1. CONTROL. «pip install -e»: Python lee la carpeta src/, así que suelto.py
#      se encuentra y TODAS las pruebas tienen que pasar, test_suelto incluida.
#      Si no pasan, el experimento está mal montado (la prueba sembrada tiene un
#      error, pytest no la recogió, el entorno no sirve) y el paso 2 no probaría
#      nada: se para en rojo.
#   2. VIOLACIÓN. «pip install» sin -e: se instala la rueda, que solo lleva
#      src/revisor. Tiene que fallar exactamente UNA prueba, test_suelto, y por
#      la razón exacta: «ModuleNotFoundError: No module named 'suelto'». Las
#      demás tienen que pasar. Si todo pasa, o si falla otra cosa, sale en rojo.
#
# Uso:  bash herramientas/probar-frontera.sh   → sale 0 si la frontera se sostiene
#
# Por qué así: un experimento que solo espera un rojo se pone «verde» también
# cuando falla por la razón equivocada. Lo impiden tres cosas: el control
# demuestra que la prueba sembrada pasa cuando el archivo está a la vista; la
# violación exige el mensaje exacto y que sea la única prueba que falle; y los
# números se leen del informe de pytest, no de su código de salida.
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

copia="$tmp/copia"
copiar_proyecto "$raiz" "$copia"

cat >"$copia/src/suelto.py" <<'EOF'
def saludo() -> str:
    return "hola desde fuera del paquete"
EOF
cat >"$copia/tests/test_suelto.py" <<'EOF'
def test_suelto_viaja_con_el_paquete() -> None:
    import suelto

    assert suelto.saludo() == "hola desde fuera del paquete"
EOF

mensaje="ModuleNotFoundError: No module named 'suelto'"

echo "1/2 control: pip install -e (la carpeta) · src/suelto.py está fuera del paquete"
crear_entorno "$tmp/control" "$copia"
"$tmp/control/bin/python" -m pip install -q --disable-pip-version-check -e "$copia"
correr_pruebas "$tmp/control" "$copia" "$tmp/control.xml" || true
echo "   $(origen_bajo_prueba "$tmp/control.xml")"
read -r total_c pasaron_c _ _ _ < <(contar "$tmp/control.xml" | head -n 1)
if [ "$total_c" -lt 2 ] || [ "$pasaron_c" -ne "$total_c" ] ||
  ! grep -q 'name="test_suelto_viaja_con_el_paquete"' "$tmp/control.xml"; then
  echo "❌ el control NO pasó ($pasaron_c de $total_c); el experimento está mal montado:"
  contar "$tmp/control.xml" | tail -n +2 | sed 's/^/     ✗ /'
  sed 's/^/     /' "$tmp/control.xml.log" | tail -n 25
  exit 1
fi
echo "   ✅ $pasaron_c de $total_c pasaron: desde la carpeta, suelto.py se ve"

echo "2/2 violación: pip install (la rueda) · el mismo archivo, la misma prueba"
crear_entorno "$tmp/violacion" "$copia"
"$tmp/violacion/bin/python" -m pip install -q --disable-pip-version-check "$copia"
correr_pruebas "$tmp/violacion" "$copia" "$tmp/violacion.xml" REVISOR_EXIGIR_INSTALADO=1 || true
echo "   $(origen_bajo_prueba "$tmp/violacion.xml")"
read -r total_v pasaron_v fallaron_v errores_v saltadas_v < <(contar "$tmp/violacion.xml" | head -n 1)
malas="$(contar "$tmp/violacion.xml" | tail -n +2)"

if [ "$total_v" -eq "$total_c" ] && [ "$pasaron_v" -eq "$total_v" ]; then
  echo "❌ PASÓ: lo instalado vio src/suelto.py, que no está en el paquete. La frontera no existe."
  exit 1
fi
if [ "$total_v" -ne "$total_c" ] || [ "$fallaron_v" -ne 1 ] || [ "$errores_v" -ne 0 ] ||
  [ "$saltadas_v" -ne 0 ] || [ "$pasaron_v" -ne $((total_c - 1)) ] ||
  [ "${malas%%: *}" != "test_suelto_viaja_con_el_paquete" ] ||
  ! printf '%s\n' "$malas" | grep -F -q "$mensaje"; then
  echo "❌ falló, pero NO solo por el archivo que falta. Esto no demuestra la frontera:"
  echo "     pruebas $total_v (control: $total_c) · pasaron $pasaron_v · fallaron $fallaron_v · con error $errores_v · saltadas $saltadas_v"
  [ -n "$malas" ] && printf '%s\n' "$malas" | sed 's/^/     ✗ /'
  sed 's/^/     /' "$tmp/violacion.xml.log" | tail -n 25
  exit 1
fi
printf '%s\n' "$malas" | sed 's/^/     ✗ /'
echo "   ✅ $pasaron_v de $total_v pasaron; falló solo la que usa suelto.py, por la razón exacta"
echo "✅ frontera: se sostiene"
terminado=1
