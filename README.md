# flat2psd

**Drop a finished ad (JPG/PNG) on a Mac app, get back a layered, named, grouped Photoshop file.**

Designers often receive only the flattened export of a creative and need to edit it: change a price, move a product,
adapt it to another format. Rebuilding it by hand takes an hour. flat2psd does it in a few minutes by turning
[Claude Code](https://claude.com/claude-code) into a headless agent with exactly one job.

<!-- TODO: demo GIF — drag examples/demo_flyer.png onto the app → progress bar → PSD opens in Photoshop -->

## What you get

- Every element on its own layer: headlines, prices, logo, products, buttons, QR, decoration, people.
- Human-readable names (`Headline · SUMMER`, `Price · 2,99€`, `Character · woman in red dress`) and 3-8 groups.
- A **clean background** underneath: smooth backgrounds are rebuilt, photographic ones are inpainted where
  objects or people were removed, so layers can actually be moved.
- The original image as a hidden reference layer on top, for comparison.

## How it works

```
 ┌──────────────┐  drop   ┌──────────────┐  claude -p (headless)   ┌──────────────────────────────┐
 │  Mac droplet │ ──────► │  psdcapas.sh │ ──────────────────────► │  Claude Code agent           │
 │ (AppleScript)│ ◄────── │  progress +  │ ◄── stream-json ─────── │  tools: Read/Write +         │
 └──────────────┘ status  │  result      │                         │  Bash(run.sh *) ONLY         │
                          └──────────────┘                         └──────────────┬───────────────┘
                                                                                  │
                    run.sh grid / zoom  → the agent looks at the image with pixel-accurate rulers
                    spec.json           → it writes one box + mode per element
                    run.sh boxes        → it checks its own boxes
                    run.sh extract      → the engine separates the layers (with a memory guard)
                    run.sh sheet        → it inspects every layer on magenta and fixes (≤ 3 rounds)
                    run.sh build        → psd-tools writes the PSD next to the original image
```

**The agent decides, the engine computes.** Claude reads the image, lists every element, measures each box with
zoomed crops and chooses how to separate it. A deterministic Python engine (`engine/extract.py`) does the pixel work:

| mode     | for                                   | how                                                            |
|----------|---------------------------------------|----------------------------------------------------------------|
| `flat`   | single-colour text and shapes         | alpha by colour projection against a modelled background       |
| `photo`  | multi-colour objects (products, logos)| distance-ramp alpha + un-premultiply, hole filling             |
| `rect`   | posters, framed photos, QR boxes      | opaque block, background filled underneath                     |
| `panel`  | boxes with their own background       | polygon layer, filled only where other layers sit on top       |
| `cutout` | people/objects over a photo           | [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) (lite) matting + [LaMa](https://github.com/advimman/lama) inpainting under the figure |

Smooth backgrounds are rebuilt with cascaded normalised convolution (two passes, excluding element boxes), with a
2D polynomial fit for large covered areas and a separate shadow layer computed from the luminance ratio.

**Guardrails**

- The agent can only run one script (`engine/run.sh`) and only touch its working folder
  (`--tools` + `--allowedTools "Bash(<engine>/run.sh:*)"` + `--strict-mcp-config`).
- A memory watchdog kills extraction if it passes 40 % of system RAM or the Mac drops below 10 % free memory,
  and the agent is instructed not to retry in that case. (Learned the hard way on an 8 GB Mac.)
- It ends with `RESULTADO: OK` or `REVISAR` (needs review); in the second case a contact sheet of all layers is saved
  next to the PSD.

## Requirements

- macOS on Apple Silicon, ~1 GB free disk, 16 GB RAM recommended for images with people.
- [Claude Code](https://claude.com/claude-code) installed and logged in with **your own** account
  (it uses your plan; nothing is sent anywhere else).

## Install

Double-click `Instalar PSD por capas.command` (first time: right-click → Open). It:

1. checks Claude Code,
2. copies the engine to `~/Library/Application Support/PSDporCapas`,
3. creates a Python 3.12 venv with [uv](https://github.com/astral-sh/uv) (numpy, opencv, pillow, psd-tools, rembg, onnxruntime),
4. downloads the models (~430 MB): `birefnet-general-lite` via rembg and `lama_fp32.onnx` from
   [Carve/LaMa-ONNX](https://huggingface.co/Carve/LaMa-ONNX),
5. compiles the droplet to `~/Applications/PSD por capas.app`.

Or let your own Claude Code install and test it: see [`INSTALL-WITH-CLAUDE.md`](INSTALL-WITH-CLAUDE.md).

## Use

Drag one or more images onto the app icon. The PSD appears next to each image as `<name>_capas.psd`.
Roughly 2-6 minutes per image, plus 30-60 s per person cut out.

Try it with [`examples/demo_flyer.png`](examples/demo_flyer.png) (a fictional brand made for this repo).

## Limitations

- Text comes out as pixels, not editable text layers (layer names carry the literal text).
- Inpainted backgrounds under people and posters are plausible, not perfect.
- Hair, feathers and semi-transparent fabric can lose detail.
- The UI and the agent prompt are in Spanish (it was built for a Spanish-speaking designer).

## Project layout

```
app/        AppleScript droplet (progress bar, notifications, login prompt)
engine/     INSTRUCCIONES.md (agent prompt) · psdcapas.sh (orchestrator) · run.sh (the only tool the agent gets)
            extract.py (layer engine) · look.py (grid/zoom/boxes/sheet) · build_psd.py (PSD writer)
examples/   demo image
```

## Licence

MIT. Models are downloaded at install time and keep their own licences (BiRefNet: MIT, LaMa: Apache-2.0).
