#!/bin/bash
# Instalador de «PSD por capas». Doble clic (la primera vez: clic derecho → Abrir).
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/Library/Application Support/PSDporCapas"
APP="$HOME/Applications/PSD por capas.app"
export PATH="$HOME/.local/bin:$HOME/.claude/local:/opt/homebrew/bin:/usr/local/bin:$PATH"

clear
echo "=============================================="
echo "  Instalando PSD por capas v0.2 (tarda ~5-10 min)"
echo "=============================================="
echo

echo "1/5 · Comprobando Claude Code…"
if ! command -v claude >/dev/null; then
  echo
  echo "  ✗ No encuentro Claude Code en este Mac."
  echo "    Instálalo desde https://claude.com/claude-code y vuelve a abrir este instalador."
  read -p "  Pulsa Intro para salir." _; exit 1
fi
echo "  ✓ $(claude --version)"

echo "2/5 · Copiando el motor…"
mkdir -p "$DEST" "$DEST/models"
rm -rf "$DEST/engine"; cp -R "$SRC/engine" "$DEST/engine"
chmod +x "$DEST/engine/"*.sh

echo "3/5 · Preparando Python y librerías (lo más largo)…"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
  export PATH="$HOME/.local/bin:$PATH"
fi
[ -x "$DEST/venv/bin/python" ] || uv venv --quiet --python 3.12 "$DEST/venv"
uv pip install --quiet --python "$DEST/venv/bin/python" numpy pillow opencv-python-headless psd-tools rembg onnxruntime
echo "  ✓ librerías listas"

echo "4/5 · Descargando los modelos de recorte y relleno (~430 MB)…"
U2NET_HOME="$DEST/models" "$DEST/venv/bin/python" -c "from rembg import new_session; new_session('birefnet-general-lite')" >/dev/null 2>&1
[ -s "$DEST/models/lama_fp32.onnx" ] || curl -sL -o "$DEST/models/lama_fp32.onnx" https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx
[ -s "$DEST/models/lama_fp32.onnx" ] && echo "  ✓ modelos listos" || echo "  ⚠ no se pudo bajar el modelo de relleno (funcionará con relleno simple)"

echo "5/5 · Creando la app…"
mkdir -p "$HOME/Applications"
rm -rf "$APP"
osacompile -o "$APP" "$SRC/app/PSD por capas.applescript"
[ -f "$SRC/app/icono.icns" ] && cp "$SRC/app/icono.icns" "$APP/Contents/Resources/droplet.icns"
xattr -dr com.apple.quarantine "$APP" "$DEST" 2>/dev/null || true
touch "$APP"
echo "  ✓ $APP"

echo
if claude auth status 2>/dev/null | grep -q '"loggedIn": true'; then
  echo "  ✓ Claude Code tiene la sesión iniciada."
else
  echo "  Falta iniciar sesión en Claude Code con TU cuenta. Se abre ahora:"
  claude auth login || true
fi
echo
echo "=============================================="
echo "  ¡Listo! Arrastra «PSD por capas» al Dock"
echo "  y suelta encima las imágenes (JPG o PNG)."
echo "=============================================="
open -R "$APP"
read -p "Pulsa Intro para cerrar." _
