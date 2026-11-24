#!/bin/bash
# psdcapas.sh <imagen> <fichero_estado>
# Convierte una imagen en PSD por capas usando Claude Code en modo automático.
# Escribe el progreso en <fichero_estado> (una línea) y al final "FIN|OK|<psd>" o "FIN|REVISAR|<psd>|motivo" o "FIN|ERROR|<motivo>".
IMG="$1"; STATUS="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:$HOME/.claude/local:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
st() { echo "$1" > "$STATUS"; }

[ -f "$IMG" ] || { st "FIN|ERROR|No encuentro el archivo"; exit 1; }
command -v claude >/dev/null || { st "FIN|ERROR|No encuentro Claude Code en este Mac"; exit 1; }
if ! claude auth status 2>/dev/null | grep -q '"loggedIn": true'; then
  st "FIN|ERROR|LOGIN"; exit 1
fi

name="$(basename "$IMG")"; base="${name%.*}"; ext="${name##*.}"
dir="$(cd "$(dirname "$IMG")" && pwd)"
dest="$dir/${base}_capas.psd"; i=2
while [ -e "$dest" ]; do dest="$dir/${base}_capas-$i.psd"; i=$((i+1)); done

WORK="$HOME/Library/Caches/PSDporCapas/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$WORK"; cp "$IMG" "$WORK/input.$ext"; cd "$WORK"
LOG="$WORK/log.jsonl"

PROMPT="$(cat "$HERE/INSTRUCCIONES.md")

---
RUN = $HERE/run.sh
DESTINO = $dest
La imagen es: input.$ext"

st "Analizando la imagen…"
claude -p "$PROMPT" \
  --tools "Read,Write,Edit,Bash" \
  --allowedTools "Read" "Write" "Edit" "Bash($HERE/run.sh:*)" \
  --strict-mcp-config --output-format stream-json --verbose \
  2>"$WORK/stderr.log" | tee "$LOG" | "$HERE/../venv/bin/python" -I -u -c '
import sys, json
msgs = {"grid": "Analizando la imagen…", "zoom": "Midiendo los elementos…", "boxes": "Comprobando las cajas…",
        "extract": "Separando las capas…", "sheet": "Revisando las capas…", "build": "Montando el PSD…"}
status = sys.argv[1]; last = ""
for line in sys.stdin:
    try: ev = json.loads(line)
    except Exception: continue
    if ev.get("type") == "assistant":
        for c in ev.get("message", {}).get("content", []):
            if c.get("type") == "tool_use" and c.get("name") == "Bash":
                cmd = c.get("input", {}).get("command", "")
                for k, v in msgs.items():
                    if f"run.sh {k}" in cmd and v != last:
                        open(status, "w").write(v + "\n"); last = v
    if ev.get("type") == "result":
        open(sys.argv[2], "w").write(ev.get("result") or "")
' "$STATUS" "$WORK/result.txt"

res="$(grep -o 'RESULTADO:.*' "$WORK/result.txt" 2>/dev/null | tail -1)"
if [ -f "$dest" ]; then
  if echo "$res" | grep -q "REVISAR"; then
    "$HERE/run.sh" sheet "$WORK/out" "${dest%.psd}_revision.png" >/dev/null 2>&1
    st "FIN|REVISAR|$dest|${res#*REVISAR · }"
  else
    st "FIN|OK|$dest|${res#RESULTADO: OK · }"
  fi
else
  if grep -qi -E "usage limit|rate limit|limit reached" "$LOG" "$WORK/stderr.log" 2>/dev/null; then
    st "FIN|ERROR|Has llegado al límite de uso de Claude. Prueba más tarde."
  else
    st "FIN|ERROR|No se ha podido generar el PSD. Detalle en $WORK"
  fi
fi
# limpieza de trabajos de más de 7 días
find "$HOME/Library/Caches/PSDporCapas" -maxdepth 1 -mindepth 1 -mtime +7 -exec rm -rf {} + 2>/dev/null
exit 0
