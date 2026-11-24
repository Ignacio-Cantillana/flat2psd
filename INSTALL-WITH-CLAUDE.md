# Install and test with your own Claude Code

Open Claude Code in the folder that **contains** `flat2psd/` and paste the block below.
(It is in Spanish because the app is; Claude will answer in your language if you ask.)

```text
Instala y comprueba la app «PSD por capas», que está en `flat2psd/`. Convierte una imagen en un PSD por capas
llamando a Claude Code en modo automático. Lee antes `flat2psd/LEEME.txt`.

Reglas:
- NO modifiques nada de `engine/`, `app/` ni el instalador. Si algo falla, averigua por qué y apúntalo;
  solo puedes arreglar cosas del entorno de este Mac (permisos, cuarentena, descargas cortadas, herramientas
  que falten) y siempre diciéndome antes qué vas a hacer.
- No inicies sesión en nada por mí: si hace falta, dímelo y lo hago yo.

Pasos:
1. Ejecuta el instalador sin interacción: `bash "flat2psd/Instalar PSD por capas.command" </dev/null`
   Comprueba que existen `~/Applications/PSD por capas.app`, `~/Library/Application Support/PSDporCapas/venv`
   y en `.../PSDporCapas/models` el modelo `birefnet-general-lite` y `lama_fp32.onnx`.
2. Prueba el motor con la imagen de ejemplo, midiendo tiempo y memoria:
   `cp flat2psd/examples/demo_flyer.png /tmp/demo_flyer.png`
   `/usr/bin/time -l "$HOME/Library/Application Support/PSDporCapas/engine/psdcapas.sh" /tmp/demo_flyer.png /tmp/estado.txt`
   y luego `cat /tmp/estado.txt`. (Tarda varios minutos; no lo cortes salvo que pase de 25 min.)
3. Si ha salido `/tmp/demo_flyer_capas.psd`, lista sus capas y grupos con el Python de la app:
   `"$HOME/Library/Application Support/PSDporCapas/venv/bin/python" -c "from psd_tools import PSDImage; p=PSDImage.open('/tmp/demo_flyer_capas.psd'); [print(l.name, [c.name for c in l] if l.is_group() else '') for l in p]"`
   y abre la hoja de capas y `out/bg_clean.png` de la carpeta de trabajo más reciente en `~/Library/Caches/PSDporCapas/`.
4. Pídeme que arrastre `flat2psd/examples/demo_flyer.png` encima de la app y que abra el PSD en Photoshop,
   y espera a que te diga cómo ha ido.
5. Resúmeme: si la instalación fue bien, tiempo y pico de memoria del paso 2, capas que salieron y cualquier error
   con su mensaje exacto.
```
