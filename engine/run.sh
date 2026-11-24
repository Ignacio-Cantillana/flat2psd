#!/bin/bash
# Única puerta de entrada que Claude puede usar. Subcomandos:
#   run.sh grid  <imagen> <salida.png>
#   run.sh zoom  <imagen> x0 y0 x1 y1 <salida.png>
#   run.sh boxes <imagen> <spec.json> <salida.png>
#   run.sh extract <imagen> <spec.json> <carpeta>
#   run.sh sheet <carpeta> <salida.png>
#   run.sh build <carpeta> <destino.psd>
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PSDCAPAS_PY:-$HERE/../venv/bin/python}"
export U2NET_HOME="${U2NET_HOME:-$HERE/../models}"
cmd="$1"; shift
case "$cmd" in
  grid|zoom|boxes|sheet) exec "$PY" -I "$HERE/look.py" "$cmd" "$@";;
  extract)
    # Protección de memoria (para que el Mac no se quede sin memoria ni se reinicie). Corta si:
    #  - este proceso pasa del 40 % de la RAM del Mac (o de PSDCAPAS_MEM_MB si se fija a mano), o
    #  - la memoria libre del Mac entero baja del 10 % (PSDCAPAS_MIN_FREE), use quien use la memoria.
    RAM_MB=$(( $(sysctl -n hw.memsize) / 1048576 ))
    LIM="${PSDCAPAS_MEM_MB:-$(( RAM_MB * 40 / 100 ))}"
    MINFREE="${PSDCAPAS_MIN_FREE:-10}"
    "$PY" -I "$HERE/extract.py" "$@" & PID=$!
    while kill -0 $PID 2>/dev/null; do
      R=$(ps -o rss= -p $PID 2>/dev/null | awk '{print int($1/1024)}'); R=${R:-0}
      FREE=$(sysctl -n kern.memorystatus_level 2>/dev/null); FREE=${FREE:-100}
      if [ "$R" -gt "$LIM" ]; then kill -9 $PID; echo "ERROR: memoria agotada (el proceso usaba ${R} MB, límite ${LIM} MB). Usa menos cutout o cajas más ajustadas."; exit 3; fi
      if [ "$FREE" -lt "$MINFREE" ]; then kill -9 $PID; echo "ERROR: el Mac se estaba quedando sin memoria (${FREE}% libre). Cierra programas pesados (Photoshop, Chrome) y vuelve a probar."; exit 3; fi
      sleep 1
    done
    wait $PID;;
  build) exec "$PY" -I "$HERE/build_psd.py" "$@";;
  *) echo "subcomando desconocido: $cmd"; exit 2;;
esac
