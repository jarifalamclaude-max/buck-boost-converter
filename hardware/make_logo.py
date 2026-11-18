"""
Turn a logo image into a KiCad silkscreen footprint (kicad/SafeBuck.pretty/Logo_Duburi.kicad_mod).

  python3 make_logo.py [logo.png] [width_mm]

* With an image: dark pixels (or opaque pixels of a transparent PNG) become silkscreen.
  Put your logo at docs/img/duburi_logo.png and run without arguments.
* Without an image: a bold "DUBURI" text logo is drawn as a placeholder.
build_pcb.py places the footprint on the BOTTOM silkscreen (it is mirrored there automatically).
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'kicad', 'SafeBuck.pretty', 'Logo_Duburi.kicad_mod')
DEFAULT_IMG = os.path.join(ROOT, 'docs', 'img', 'duburi_logo.png')
PX_MM = 0.08                      # silkscreen pixel size (JLCPCB prints >= 0.15 mm lines reliably)

def load(path):
    im = Image.open(path)
    if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
        a = im.convert('RGBA').split()[-1]
        return a.point(lambda v: 255 if v > 128 else 0)
    g = ImageOps.grayscale(im)
    return g.point(lambda v: 255 if v < 128 else 0)          # dark = ink

def text_logo(text='DUBURI'):
    font = None
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.exists(f): font = ImageFont.truetype(f, 120); break
    font = font or ImageFont.load_default()
    w, h = 900, 180
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, w - 5, h - 5), radius=40, outline=255, width=14)     # badge frame
    bb = d.textbbox((0, 0), text, font=font)
    d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], (h - (bb[3] - bb[1])) / 2 - bb[1]), text, fill=255, font=font)
    return im

def to_footprint(mask, width_mm):
    W = int(round(width_mm / PX_MM))
    H = int(round(mask.height * W / mask.width))
    m = mask.resize((W, H), Image.LANCZOS).point(lambda v: 255 if v > 127 else 0)
    px = m.load()
    rects, open_runs = [], {}
    for y in range(H + 1):
        runs = []
        if y < H:
            x = 0
            while x < W:
                if px[x, y]:
                    x0 = x
                    while x < W and px[x, y]: x += 1
                    runs.append((x0, x))
                else:
                    x += 1
        nxt = {}
        for r in runs:                                   # merge identical runs of consecutive rows
            nxt[r] = open_runs.pop(r, y)
        for (x0, x1), y0 in open_runs.items():
            rects.append((x0, y0, x1, y))
        open_runs = nxt
    ox, oy = W * PX_MM / 2, H * PX_MM / 2
    lines = ['(footprint "Logo_Duburi" (version 20221018) (generator make_logo) (layer "F.Cu")',
             '  (descr "Duburi logo, silkscreen") (attr board_only exclude_from_pos_files exclude_from_bom)',
             '  (fp_text reference "LOGO1" (at 0 0) (layer "F.SilkS") hide (effects (font (size 1 1) (thickness 0.15))))',
             '  (fp_text value "Logo_Duburi" (at 0 0) (layer "F.Fab") hide (effects (font (size 1 1) (thickness 0.15))))']
    for (x0, y0, x1, y1) in rects:
        X0, Y0, X1, Y1 = x0 * PX_MM - ox, y0 * PX_MM - oy, x1 * PX_MM - ox, y1 * PX_MM - oy
        lines.append(f'  (fp_poly (pts (xy {X0:.3f} {Y0:.3f}) (xy {X1:.3f} {Y0:.3f}) (xy {X1:.3f} {Y1:.3f}) (xy {X0:.3f} {Y1:.3f}))'
                     ' (stroke (width 0) (type solid)) (fill solid) (layer "F.SilkS"))')
    lines.append(')')
    open(OUT, 'w').write('\n'.join(lines) + '\n')
    return len(rects), W * PX_MM, H * PX_MM

if __name__ == '__main__':
    img = sys.argv[1] if len(sys.argv) > 1 else (DEFAULT_IMG if os.path.exists(DEFAULT_IMG) else None)
    width = float(sys.argv[2]) if len(sys.argv) > 2 else 22.0
    mask = load(img) if img else text_logo()
    n, w, h = to_footprint(mask, width)
    print(f'{OUT}: {n} rectangles, {w:.1f} x {h:.1f} mm, from {img or "text placeholder"}')
