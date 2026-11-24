# build_psd.py <outdir> <dest.psd>  — Python-only layered PSD writer (psd-tools)
import sys, os, json
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer, Group
out, dest = sys.argv[1:3]
m = json.load(open(os.path.join(out, 'manifest.json')))
W, H = m['width'], m['height']
psd = PSDImage.new('RGBA', (W, H))
def px(parent, name, fn, left, top, hidden=False):
    im = Image.open(os.path.join(out, fn)).convert('RGBA')
    L = PixelLayer.frompil(im, parent, name=name, top=top, left=left)
    if hidden: L.visible = False
    return L
# bottom first
px(psd, m.get('bgname') or 'Fondo limpio (sin elementos)', 'bg_clean.png', 0, 0)
order = []; groups = {}
for L in m['layers']:
    g = L.get('group') or 'Varios'
    if g not in groups: groups[g] = []; order.append(g)
    groups[g].append(L)
for g in reversed(order):
    grp = Group.new(psd, name=g, open_folder=True)
    for L in reversed(groups[g]):
        px(grp, L['name'], L['file'], L['left'], L['top'], L.get('hidden', False))
px(psd, 'REFERENCIA · creatividad original (oculta)', 'original.png', 0, 0, hidden=True)
psd.save(dest)
print('ok', dest, os.path.getsize(dest))
