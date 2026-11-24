"""Ayudas visuales para Claude.
look.py grid <imagen> <salida.png>            imagen con rejilla y coordenadas reales (cada 50 px, etiquetas cada 100)
look.py zoom <imagen> x0 y0 x1 y1 <salida.png> recorte ampliado con rejilla cada 10/50 px y coordenadas reales
look.py boxes <imagen> <spec.json> <salida.png> dibuja las cajas del spec con su número
look.py sheet <carpeta_salida> <salida.png>   hoja de capas sobre fondo magenta (para ver restos de fondo)
"""
import sys, json, os
from PIL import Image, ImageDraw, ImageFont
def font(sz):
    for f in ['/System/Library/Fonts/Supplemental/Arial.ttf','/System/Library/Fonts/Helvetica.ttc']:
        try: return ImageFont.truetype(f, sz)
        except Exception: pass
    return ImageFont.load_default()
def fit(im, maxside=1600):
    s = min(1.0, maxside/max(im.size)); 
    return (im.resize((int(im.width*s), int(im.height*s)), Image.LANCZOS) if s<1 else im), s
def grid(im, step, lab, off=(0,0), scale=1.0):
    im = im.convert('RGB'); dr = ImageDraw.Draw(im); F = font(max(11, int(13)))
    W,H = im.size; ox,oy = off
    import math
    start_x = math.ceil(ox/step)*step
    for gx in range(start_x, int(ox+W/scale)+1, step):
        x = (gx-ox)*scale; major = gx % lab == 0
        dr.line([(x,0),(x,H)], fill=(255,0,255) if major else (255,150,255), width=1)
        if major: dr.text((x+2,2), str(gx), fill=(255,255,0), font=F, stroke_width=2, stroke_fill=(0,0,0))
    start_y = math.ceil(oy/step)*step
    for gy in range(start_y, int(oy+H/scale)+1, step):
        y = (gy-oy)*scale; major = gy % lab == 0
        dr.line([(0,y),(W,y)], fill=(255,0,255) if major else (255,150,255), width=1)
        if major: dr.text((2,y+2), str(gy), fill=(255,255,0), font=F, stroke_width=2, stroke_fill=(0,0,0))
    return im
cmd = sys.argv[1]
if cmd == 'grid':
    im = Image.open(sys.argv[2]); W,H = im.size; sm, s = fit(im)
    step = 50 if max(W,H) <= 2000 else 100
    grid(sm, step, step*2, scale=s).save(sys.argv[3]); print(f'imagen {W}x{H}px; vista a escala {s:.3f}; etiquetas = píxeles reales')
elif cmd == 'zoom':
    im = Image.open(sys.argv[2]); x0,y0,x1,y1 = map(int, sys.argv[3:7])
    c = im.crop((x0,y0,x1,y1)); sc = min(8.0, 1000/max(c.size)); c = c.resize((int(c.width*sc), int(c.height*sc)), Image.LANCZOS)
    step = 10 if (x1-x0) <= 300 else 25
    grid(c, step, 50, off=(x0,y0), scale=sc).save(sys.argv[7]); print(f'zoom x{sc:.1f}; etiquetas = píxeles reales')
elif cmd == 'boxes':
    im = Image.open(sys.argv[2]).convert('RGB'); sp = json.load(open(sys.argv[3]))
    sm, s = fit(im); dr = ImageDraw.Draw(sm); F = font(14)
    cols = [(255,0,255),(0,255,255),(255,128,0),(0,255,0),(255,255,0),(255,0,0)]
    for i,e in enumerate(sp['elements']):
        x0,y0,x1,y1 = [v*s for v in e['box']]; c = cols[i%len(cols)]
        dr.rectangle([x0,y0,x1,y1], outline=c, width=2)
        dr.text((x0+2,y0+1), str(i), fill=c, font=F, stroke_width=2, stroke_fill=(0,0,0))
    sm.save(sys.argv[4]); print('cajas dibujadas; número = índice en elements')
elif cmd == 'sheet':
    out = sys.argv[2]; m = json.load(open(os.path.join(out,'manifest.json')))
    cell=230; cols=6; n=len(m['layers']); rows=max(1,(n+cols-1)//cols)
    sh=Image.new('RGB',(cols*cell,rows*(cell+18)),'white'); dr=ImageDraw.Draw(sh); F=font(11)
    for i,L in enumerate(m['layers']):
        p=Image.open(os.path.join(out,L['file'])).convert('RGBA'); p.thumbnail((cell-10,cell-10))
        cb=Image.new('RGB',p.size,(200,60,200)); cb.paste(p,(0,0),p)
        x=(i%cols)*cell; y=(i//cols)*(cell+18); sh.paste(cb,(x+5,y+5))
        dr.text((x+5,y+cell-2),f"{i} {L['name']}"[:38],fill='black',font=F)
    sh.save(sys.argv[3]); print(f'{n} capas en la hoja')
