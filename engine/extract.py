"""Separa una creatividad plana (JPG/PNG) en capas a partir de un spec JSON.

uso: extract.py <imagen> <spec.json> <carpeta_salida>

spec = {
  "name": "...",
  "background": "smooth" | "photo",   # smooth: fondo liso/degradado/textura suave (se reconstruye limpio)
                                      # photo: fondo fotográfico (se queda el original; solo se rellena bajo 'rect' y 'cutout' con fill_under)
  "synth_regions": [[x0,y0,x1,y1], ...],   # (smooth) zonas grandes tapadas por objetos: fondo por ajuste polinómico
  "elements": [  # el PRIMERO es el de ARRIBA del todo
     {"name": "...", "group": "...", "box": [x0,y0,x1,y1], "mode": "flat|photo|rect|panel|cutout", ...}
  ]
}
modos:
  flat   texto/forma de UN color sobre el fondo -> capa de color plano con alfa exacto ("color": "#RRGGBB" opcional)
  photo  objeto multicolor (producto, foto, botón, logo). "fill": false para textos multicolor/objetos con huecos
  rect   bloque rectangular opaco (póster, QR con su caja, foto encuadrada)
  panel  caja/forma con fondo propio y lo de dentro encima: "poly": [[x,y],...]
  cutout persona/objeto sobre FOTO: recorte con BiRefNet ligero, UNA caja por persona (delante primero).
         "fill_under": true rellena el fondo de debajo con LaMa (por defecto en cutout)
"""
import sys, json, os
import cv2, numpy as np
from PIL import Image

src, specf, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
spec = json.load(open(specf))
img8 = np.array(Image.open(src).convert('RGB'))
img = img8.astype(np.float32)
H, W, _ = img.shape
BGMODE = spec.get('background', 'smooth')
ELS = spec['elements']
for e in ELS:
    x0, y0, x1, y1 = [int(round(v)) for v in e['box']]
    e['box'] = [max(0, min(x0, x1)), max(0, min(y0, y1)), min(W, max(x0, x1)), min(H, max(y0, y1))]

def normconv(im, m, sig):
    num = cv2.GaussianBlur(im * m[..., None], (0, 0), sig)
    den = cv2.GaussianBlur(m, (0, 0), sig)
    return num / np.maximum(den, 1e-5)[..., None], den

def cascade(im, m, sigmas, thr=0.15):
    res = None; cov = None
    for s in sigmas:
        b, den = normconv(im, m, s)
        if res is None: res, cov = b, den
        else:
            need = cov < thr; res[need] = b[need]; cov = np.maximum(cov, den)
    return res

_rembg = None
CUT_MODEL = os.environ.get('PSDCAPAS_CUT_MODEL', 'birefnet-general-lite')
def rembg_mask(crop):
    """Recorte de la persona/objeto principal de la caja. BiRefNet ligero (bordes finos, se queda con lo de
    delante); si no está, el modelo antiguo."""
    global _rembg, CUT_MODEL
    from rembg import remove, new_session
    if _rembg is None:
        try: _rembg = new_session(CUT_MODEL)
        except Exception as ex:
            print('AVISO: no carga', CUT_MODEL, '->', ex); CUT_MODEL = 'isnet-general-use'; _rembg = new_session(CUT_MODEL)
    m = remove(Image.fromarray(crop), session=_rembg, only_mask=True)
    return np.array(m.convert('L')).astype(np.float32) / 255

f = 4
sm = cv2.resize(img, (max(1, W // f), max(1, H // f)), interpolation=cv2.INTER_AREA)

def smooth_bg(free_full):
    fs = cv2.resize(free_full, (sm.shape[1], sm.shape[0]), interpolation=cv2.INTER_AREA)
    fs = (fs > 0.99).astype(np.float32)
    if fs.sum() < 50: fs = np.ones_like(fs)
    b = cascade(sm, fs, [3, 8, 20, 60, 150])
    return cv2.resize(b, (W, H), interpolation=cv2.INTER_CUBIC)

def run(bg, d, save):
    owned = np.zeros((H, W), np.float32)
    layers = []
    for idx, e in enumerate(ELS):
        x0, y0, x1, y1 = e['box']
        if x1 - x0 < 2 or y1 - y0 < 2: continue
        mode = e.get('mode', 'photo')
        I = img[y0:y1, x0:x1]; B = bg[y0:y1, x0:x1]; D = d[y0:y1, x0:x1]
        clip_owned = True
        if mode == 'rect':
            a = np.ones(D.shape, np.float32); col = I.copy()
        elif mode == 'cutout':
            if '_mask' not in e: e['_mask'] = rembg_mask(img8[y0:y1, x0:x1])
            m = e['_mask']; lo, hi = e.get('lo', 0.10), e.get('hi', 0.50)
            a = np.clip((m - lo) / (hi - lo), 0, 1)
            n, lab, st, _ = cv2.connectedComponentsWithStats((a > 0.05).astype(np.uint8))
            for i in range(1, n):
                if st[i, 4] < e.get('speck', 300): a[lab == i] = 0
            col = I.copy()
        elif mode == 'panel':
            pm = np.zeros((H, W), np.uint8)
            cv2.fillPoly(pm, [np.array(e['poly'], np.int32)], 1)
            pm = cv2.dilate(pm, np.ones((5, 5)))[y0:y1, x0:x1].astype(np.float32)
            own = owned[y0:y1, x0:x1]
            keep = ((own < 0.02) & (pm > 0)).astype(np.float32)
            keep = cv2.erode(keep, np.ones((5, 5)))
            lumI = I.mean(2)
            if keep.sum() > 0:
                keep = keep * (lumI < np.percentile(lumI[keep > 0], 90) + 4)
            keep = cv2.erode(keep.astype(np.float32), np.ones((3, 3)))
            fillc = cascade(I, keep, [4, 12, 40], 0.1) if keep.sum() > 0 else I.copy()
            fillc = fillc + np.random.default_rng(2).normal(0, 1.5, fillc.shape)
            col = np.where((own < 0.02)[..., None], I, fillc)
            a = pm; clip_owned = False
        elif mode == 'flat':
            t = e.get('t', 40)
            sel = D > t * 1.6
            fg = np.median(I[sel], axis=0) if sel.sum() > 10 else I.reshape(-1, 3).mean(0)
            if e.get('color'): fg = np.array([int(e['color'][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
            v = fg[None, None, :] - B
            a = np.clip(((I - B) * v).sum(2) / np.maximum((v * v).sum(2), 1), 0, 1)
            a[D < t * 0.35] = 0
            col = np.broadcast_to(fg, I.shape).copy()
            e['hex'] = '#%02X%02X%02X' % tuple(int(c) for c in fg)
        else:  # photo
            t0, t1 = e.get('t0', 14), e.get('t1', 34)
            a = np.clip((D - t0) / (t1 - t0), 0, 1)
            core = (D > t1).astype(np.uint8)
            fill = e.get('fill', True)
            if fill:
                k = e.get('close', 9)
                core = cv2.morphologyEx(core, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
                n, lab, st, _ = cv2.connectedComponentsWithStats(core)
                keep = np.zeros_like(core)
                if n > 1:
                    minA = e.get('minarea', 0.02) * st[1:, 4].max()
                    for i in range(1, n):
                        if st[i, 4] >= minA: keep[lab == i] = 1
                hh, ww = keep.shape
                pad = np.zeros((hh + 2, ww + 2), np.uint8); pad[1:-1, 1:-1] = keep
                fl = (1 - pad).astype(np.uint8); msk = np.zeros((hh + 4, ww + 4), np.uint8)
                cv2.floodFill(fl, msk, (0, 0), 2)
                holes = (fl[1:-1, 1:-1] == 1)
                solid = np.maximum(keep, holes.astype(np.uint8)).astype(np.float32)
                ring = cv2.dilate(solid, np.ones((3, 3)))
                a = np.maximum(solid, a * ring)
                a = cv2.GaussianBlur(a, (0, 0), 0.6)
                a = np.where(solid > 0, 1.0, a)
            else:
                a[a < 0.12] = 0
                n, lab, st, _ = cv2.connectedComponentsWithStats((a > 0).astype(np.uint8), connectivity=8)
                for i in range(1, n):
                    if st[i, 4] < e.get('speck', 14): a[lab == i] = 0
            aa = np.maximum(a, 1e-3)[..., None]
            col = np.clip(B + (I - B) / aa, 0, 255)
            col = np.where(a[..., None] > 0.98, I, col)
        if clip_owned:
            a = a * (1 - owned[y0:y1, x0:x1])
        owned[y0:y1, x0:x1] = np.maximum(owned[y0:y1, x0:x1], a)
        ys, xs = np.where(a > 0.004)
        if len(ys) == 0:
            if save: print('AVISO: capa vacía ->', e['name'])
            continue
        ty0, ty1, tx0, tx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        fn = f"L{len(layers):02d}.png"
        if save:
            rgba = np.dstack([col, a * 255]).clip(0, 255).astype(np.uint8)
            Image.fromarray(rgba[ty0:ty1, tx0:tx1]).save(os.path.join(out, fn))
        layers.append(dict(name=e['name'], group=e.get('group', ''), file=fn, left=int(x0 + tx0), top=int(y0 + ty0),
                           hidden=bool(e.get('hidden', False)), mode=mode, box=e['box']))
    return layers, owned

def inpaint_telea(src8, mask, scale=2):
    s = cv2.resize(src8, (W // scale, H // scale), interpolation=cv2.INTER_AREA)
    ms = cv2.resize(mask, (W // scale, H // scale), interpolation=cv2.INTER_NEAREST)
    r = cv2.inpaint(s, ms, 12, cv2.INPAINT_TELEA)
    r = cv2.resize(r, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    r += np.random.default_rng(0).normal(0, 3, r.shape)
    fm = cv2.GaussianBlur((mask > 0).astype(np.float32), (0, 0), 2)[..., None]
    return src8 * (1 - fm) + r * fm

LAMA = os.path.join(os.environ.get('U2NET_HOME', ''), 'lama_fp32.onnx')
def inpaint(src8, mask):
    """Rellena los huecos: LaMa (modelo de relleno de fotos) por zonas; si no está, Telea (borroso)."""
    if not os.path.exists(LAMA):
        print('AVISO: sin LaMa, relleno simple'); return inpaint_telea(src8, mask)
    import onnxruntime as ort
    so = ort.SessionOptions(); so.enable_cpu_mem_arena = False; so.intra_op_num_threads = 4
    sess = ort.InferenceSession(LAMA, so, providers=['CPUExecutionProvider'])
    out = src8.astype(np.float32).copy()
    n, lab, st, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8))
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        side = int(max(w, h) * 1.35) + 32
        cx, cy = x + w // 2, y + h // 2
        x0 = max(0, min(W - side, cx - side // 2)) if side < W else 0
        y0 = max(0, min(H - side, cy - side // 2)) if side < H else 0
        x1, y1 = min(W, x0 + side), min(H, y0 + side)
        c = out[y0:y1, x0:x1].astype(np.uint8); m = (lab[y0:y1, x0:x1] == i).astype(np.uint8)
        ci = cv2.resize(c, (512, 512), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        mi = (cv2.resize(m, (512, 512), interpolation=cv2.INTER_NEAREST) > 0).astype(np.float32)
        ci = ci * (1 - mi[..., None])
        o = sess.run(None, {'image': ci.transpose(2, 0, 1)[None], 'mask': mi[None, None]})[0][0].transpose(1, 2, 0)
        if o.max() <= 1.5: o = o * 255
        o = cv2.resize(np.clip(o, 0, 255).astype(np.float32), (x1 - x0, y1 - y0), interpolation=cv2.INTER_CUBIC)
        o += np.random.default_rng(i).normal(0, 2, o.shape)
        f = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 3)[..., None]
        out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - f) + o * f
    return out

if BGMODE == 'photo':
    bg = img.copy(); d = np.zeros((H, W), np.float32)
    layers, owned = run(bg, d, True)
    hole = np.zeros((H, W), np.uint8)
    for e in ELS:
        x0, y0, x1, y1 = e['box']
        if e.get('mode') == 'rect': hole[max(0, y0 - 3):y1 + 3, max(0, x0 - 3):x1 + 3] = 255
    for e in ELS:
        if e.get('mode') == 'cutout' and e.get('fill_under', True) and '_mask' in e:
            x0, y0, x1, y1 = e['box']
            mk = (e['_mask'] > 0.1).astype(np.uint8) * 255
            hole[y0:y1, x0:x1] = np.maximum(hole[y0:y1, x0:x1], cv2.dilate(mk, np.ones((17, 17))))
    clean = inpaint(img8, hole) if hole.any() else img.copy()
else:
    excl = np.zeros((H, W), np.float32)
    for e in ELS:
        x0, y0, x1, y1 = e['box']; excl[y0:y1, x0:x1] = 1
    bg = smooth_bg(1 - excl)
    d = np.linalg.norm(img - bg, axis=2)
    _, owned = run(bg, d, False)
    free = (cv2.dilate(owned, np.ones((7, 7))) < 0.01).astype(np.float32)
    bg = smooth_bg(free)
    d = np.linalg.norm(img - bg, axis=2)
    layers, owned = run(bg, d, True)
    free = (cv2.dilate(owned, np.ones((7, 7))) < 0.01).astype(np.float32)
    A = cv2.dilate(owned, np.ones((5, 5)))
    A = np.clip(cv2.GaussianBlur(A, (0, 0), 1.5) * 1.5, 0, 1)
    plate = bg.copy()
    if spec.get('synth_regions'):
        R = np.zeros((H, W), np.float32)
        for x0, y0, x1, y1 in spec['synth_regions']: R[max(0, y0):y1, max(0, x0):x1] = 1
        fr = free.copy(); fr[R > 0] = 0
        mg = spec.get('synth_margin', 260)
        E = np.zeros((H, W), np.float32)
        for x0, y0, x1, y1 in spec['synth_regions']: E[max(0, y0 - mg):y1 + mg, max(0, x0 - mg):x1 + mg] = 1
        ys, xs = np.where((fr > 0) & (E > 0))
        if len(ys) > 200:
            sel = np.random.default_rng(0).choice(len(ys), min(60000, len(ys)), replace=False)
            ys, xs = ys[sel], xs[sel]
            def feats(x, y):
                x = x / W; y = y / H
                return np.stack([(x ** i) * (y ** j) for i in range(5) for j in range(5 - i)], -1)
            coef = np.linalg.lstsq(feats(xs.astype(np.float32), ys.astype(np.float32)), img[ys, xs], rcond=None)[0]
            gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
            syn = (feats(gx, gy) @ coef).astype(np.float32)
            Rf = np.clip(cv2.GaussianBlur(R, (0, 0), 25) * 2, 0, 1)
            plate = bg * (1 - Rf[..., None]) + syn * Rf[..., None]
            A = np.maximum(A, Rf)
            lum = lambda x: x @ np.array([0.299, 0.587, 0.114], np.float32)
            sa = np.clip(1 - lum(img) / np.maximum(lum(syn), 1), 0, 1) * Rf * (1 - np.clip(owned, 0, 1))
            sa[sa < 0.04] = 0
            if (sa > 0).any():
                ys2, xs2 = np.where(sa > 0)
                ty0, ty1, tx0, tx1 = ys2.min(), ys2.max() + 1, xs2.min(), xs2.max() + 1
                rgba = np.dstack([np.zeros((H, W, 3)), sa * 255]).astype(np.uint8)
                Image.fromarray(rgba[ty0:ty1, tx0:tx1]).save(os.path.join(out, 'shadow.png'))
                layers.append(dict(name='Sombras', group=spec.get('shadow_group', layers[-1]['group'] if layers else ''),
                                   file='shadow.png', left=int(tx0), top=int(ty0), hidden=False, mode='shadow'))
    ok = (owned == 0) & (free > 0)
    sd = float(np.std((img - bg)[ok])) if ok.any() else 3
    grain = np.random.default_rng(1).normal(0, min(sd, spec.get('grain_max', 6)), (H, W))[..., None]
    clean = img * (1 - A[..., None]) + (plate + grain) * A[..., None]

Image.fromarray(np.clip(clean, 0, 255).astype(np.uint8)).save(os.path.join(out, 'bg_clean.png'))
Image.fromarray(img8).save(os.path.join(out, 'original.png'))

comp = np.clip(clean, 0, 255).astype(np.float32)
for L in reversed(layers):
    p = np.array(Image.open(os.path.join(out, L['file']))).astype(np.float32)
    h, w = p.shape[:2]; y, x = L['top'], L['left']
    al = p[..., 3:4] / 255
    comp[y:y + h, x:x + w] = p[..., :3] * al + comp[y:y + h, x:x + w] * (1 - al)
diff = float(np.abs(comp - img).mean())
Image.fromarray(comp.clip(0, 255).astype(np.uint8)).save(os.path.join(out, 'composite.png'))
dm = np.abs(comp - img).mean(2)
Image.fromarray(np.clip(dm * 8, 0, 255).astype(np.uint8)).save(os.path.join(out, 'diff.png'))
json.dump(dict(width=W, height=H, layers=layers, name=spec.get('name', ''), bgname=spec.get('bgname'),
               diff=round(diff, 3)), open(os.path.join(out, 'manifest.json'), 'w'), ensure_ascii=False, indent=1)
print(f'capas: {len(layers)} · diferencia media con el original: {diff:.2f}/255 (bien si < 2)')
for L in layers: print(f"  [{L['group']}] {L['name']}  @({L['left']},{L['top']})")
