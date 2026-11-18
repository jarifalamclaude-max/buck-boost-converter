"""
Build the SafeBuck-80 KiCad PCB from netlist.py (run with KiCad's python: /usr/bin/python3 build_pcb.py).

Steps: custom LT8390 footprint -> place every footprint -> assign nets -> outline ->
(export DSN for Freerouting) -> import routes -> copper zones -> fill -> DRC -> save.
"""
import os, sys, math, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
from netlist import PARTS, nets, sym_uuid

KDIR = os.path.join(HERE, 'kicad')
LIBDIR = os.path.join(KDIR, 'SafeBuck.pretty')
STD = '/usr/share/kicad/footprints'
os.makedirs(LIBDIR, exist_ok=True)

W, H = 65.0, 48.0          # board size (same as QS-1212CCBD: 65.1 x 47.7 mm)
OX, OY = 100.0, 100.0      # board origin in KiCad coordinates
def mm(v): return pcbnew.FromMM(v)
def lset(*layers):
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    return ls
def V(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))

# ------------------------------------------------------------------ custom LT8390 FE28 (EB) footprint
def make_lt8390_fp():
    """ADI FE28 (EB) land, pads narrowed to 0.40 x 1.05 @0.65 (0.25 mm gap for 2 oz copper), outer 6.60 / inner 4.50,
    exposed pad 4.75 (along length) x 2.74, with 2x5 thermal vias 0.3 mm."""
    base = pcbnew.FootprintLoad(STD + '/Package_SO.pretty', 'TSSOP-28-1EP_4.4x9.7mm_P0.65mm')
    fp = pcbnew.FOOTPRINT(None)
    name = 'LT8390_FE28_EB_TSSOP-28_EP4.75x2.74mm'
    fp.SetFPID(pcbnew.LIB_ID('SafeBuck', name))
    fp.SetDescription('ADI/Linear FE28 (EB) TSSOP-28 4.4 mm, exposed pad 4.75x2.74 mm (LT8390 datasheet p29)')
    for item in base.GraphicalItems():           # keep silk/fab/courtyard drawings
        fp.Add(item.Duplicate())
    fp.Reference().SetText('U**'); fp.Value().SetText('LT8390')
    xc = (4.50 / 2 + 1.05 / 2)                   # 2.775 mm pad centre
    for i in range(28):
        n = i + 1
        if n <= 14: x, y = -xc, -4.225 + 0.65 * i
        else:       x, y = xc, 4.225 - 0.65 * (n - 15)
        p = pcbnew.PAD(fp)
        p.SetNumber(str(n)); p.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT); p.SetRoundRectRadiusRatio(0.25)
        p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        p.SetLayerSet(lset(pcbnew.F_Cu, pcbnew.F_Paste, pcbnew.F_Mask))
        p.SetSize(pcbnew.VECTOR2I(mm(1.05), mm(0.40)))   # 0.40 (ADI land: 0.45) -> 0.25 mm gap for 2 oz etching
        p.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); p.SetPos0(pcbnew.VECTOR2I(mm(x), mm(y)))
        fp.Add(p)
    ep = pcbnew.PAD(fp)
    ep.SetNumber('29'); ep.SetShape(pcbnew.PAD_SHAPE_RECT); ep.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    ep.SetLayerSet(lset(pcbnew.F_Cu, pcbnew.F_Mask))
    ep.SetSize(pcbnew.VECTOR2I(mm(2.74), mm(4.75))); fp.Add(ep)
    for (px, py) in [(-0.6, -1.6), (0.6, -1.6), (-0.6, 1.6), (0.6, 1.6)]:   # paste windows ~50 %
        pp = pcbnew.PAD(fp); pp.SetNumber(''); pp.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pp.SetShape(pcbnew.PAD_SHAPE_RECT); pp.SetLayerSet(lset(pcbnew.F_Paste))
        pp.SetSize(pcbnew.VECTOR2I(mm(1.0), mm(1.3)))
        pp.SetPosition(pcbnew.VECTOR2I(mm(px), mm(py))); pp.SetPos0(pcbnew.VECTOR2I(mm(px), mm(py))); fp.Add(pp)
    for ix in (-0.7, 0.7):
        for iy in (-1.9, -0.95, 0, 0.95, 1.9):
            v = pcbnew.PAD(fp); v.SetNumber('29'); v.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
            v.SetShape(pcbnew.PAD_SHAPE_CIRCLE); v.SetLayerSet(pcbnew.LSET.AllCuMask())
            v.SetSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6))); v.SetDrillSize(pcbnew.VECTOR2I(mm(0.3), mm(0.3)))
            v.SetPosition(pcbnew.VECTOR2I(mm(ix), mm(iy))); v.SetPos0(pcbnew.VECTOR2I(mm(ix), mm(iy))); fp.Add(v)
    path = os.path.join(LIBDIR, name + '.kicad_mod')
    if os.path.exists(path): os.remove(path)
    pcbnew.FootprintSave(LIBDIR, fp)
    return name

def load_fp(fpid):
    lib, name = fpid.split(':')
    path = LIBDIR if lib == 'SafeBuck' else os.path.join(STD, lib + '.pretty')
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None: raise RuntimeError('footprint not found ' + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp

# ------------------------------------------------------------------ placement (x, y, rot) board-local mm
from placement import PLACE

def build(route=True):
    make_lt8390_fp()
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.15); ds.m_ViasMinSize = mm(0.6); ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.3); ds.m_HoleClearance = mm(0.25)
    ds.m_HoleToHoleMin = mm(0.3)
    ds.SetBoardThickness(mm(1.6))
    nc = ds.m_NetSettings.m_DefaultNetClass
    # 2 oz outer copper at JLCPCB: >= 0.2 mm (8 mil) track and gap -> use 0.25 mm tracks, 0.21 mm gaps
    nc.SetClearance(mm(0.21)); nc.SetTrackWidth(mm(0.25)); nc.SetViaDiameter(mm(0.7)); nc.SetViaDrill(mm(0.35))

    # nets
    netobj = {}
    for n in sorted(nets().keys()):
        ni = pcbnew.NETINFO_ITEM(board, n); board.Add(ni); netobj[n] = ni

    missing = []
    FIXED_FP = ('SON5x6', 'TDSON', 'L_Coilcraft', 'CP_Elec', 'TerminalBlock', 'Potentiometer', 'MountingHole',
                'R_2512', 'NANO2', 'D_SMB', 'LT8390', 'HVQFN', 'C_1210')
    def local_cy(fp):
        fp.SetPosition(pcbnew.VECTOR2I(0, 0)); fp.SetOrientationDegrees(0)
        fp.BuildCourtyardCaches()
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
        return (pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                pcbnew.ToMM(bb.GetX() + bb.GetWidth()), pcbnew.ToMM(bb.GetY() + bb.GetHeight()))
    def rect_at(lc, x, y, rot):
        x0, y0, x1, y1 = lc
        pts = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
        th = math.radians(rot)
        g = [(x + px * math.cos(th) + py * math.sin(th), y - px * math.sin(th) + py * math.cos(th)) for px, py in pts]
        return (min(p[0] for p in g), min(p[1] for p in g), max(p[0] for p in g), max(p[1] for p in g))
    def overlaps(r, rects, m=0.05):
        for o in rects:
            if r[0] < o[2] + m and r[2] > o[0] - m and r[1] < o[3] + m and r[3] > o[1] - m:
                return True
        return False
    def inside(r, e=0.3):
        return r[0] >= e and r[1] >= e and r[2] <= W - e and r[3] <= H - e
    loaded = []
    for p in PARTS:
        if p['ref'] not in PLACE: missing.append(p['ref']); continue
        fp = load_fp(p['fp'])
        fp.SetReference(p['ref']); fp.SetValue(p['value'])
        fp.SetPath(pcbnew.KIID_PATH('/' + sym_uuid(p['ref'])))      # link to the schematic symbol
        for k, v in (('Sheetfile', 'SafeBuck-80.kicad_sch'), ('Sheetname', ''), ('LCSC', p['lcsc']), ('MPN', p['mpn'])):
            if v or k == 'Sheetname': fp.SetProperty(k, v)
        board.Add(fp)
        loaded.append((p, fp, local_cy(fp)))
    placed_rects = []
    self_placed = {}
    order = sorted(loaded, key=lambda t: 0 if any(k in t[0]['fp'] for k in FIXED_FP) else 1)
    for p, fp, lc in order:
        x, y, rot = PLACE[p['ref']][:3]
        fixed = any(k in p['fp'] for k in FIXED_FP) or p['ref'].startswith('NT')
        if not fixed:
            best = None
            for r_try in (rot, (rot + 90) % 360):
                for rad in [i * 0.25 for i in range(0, 60)]:
                    steps = max(1, int(2 * math.pi * rad / 0.25)) if rad > 0 else 1
                    for k in range(steps):
                        a = 2 * math.pi * k / steps
                        cx, cy_ = x + rad * math.cos(a), y + rad * math.sin(a)
                        rr = rect_at(lc, cx, cy_, r_try)
                        if inside(rr) and not overlaps(rr, placed_rects):
                            best = (cx, cy_, r_try, rad); break
                    if best: break
                if best and best[3] < 1.5: break
            if best is None:
                print('NO ROOM for', p['ref']); best = (x, y, rot, 99)
            x, y, rot = best[0], best[1], best[2]
        fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
        if not p['ref'].startswith('NT'):
            placed_rects.append(rect_at(lc, x, y, rot))
        self_placed[p['ref']] = (round(x, 2), round(y, 2), rot)
        if p['dnp']:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num in p['pins']:
                pad.SetNet(netobj[p['pins'][num]])
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); fp.Reference().SetTextThickness(mm(0.12))
    json.dump(self_placed, open(os.path.join(KDIR, 'placement_result.json'), 'w'), indent=0)
    if missing: print('NOT PLACED:', missing)

    # Kelvin net-ties: put each tie at the inner edge of its shunt pad (pad2 of the tie overlaps the shunt pad)
    def place_tie(tie, shunt, pad_sign):
        fs = board.FindFootprintByReference(shunt); ft = board.FindFootprintByReference(tie)
        th = math.radians(fs.GetOrientationDegrees())
        lx = pad_sign * 1.845
        gx = lx * math.cos(th); gy = -lx * math.sin(th)
        c = fs.GetPosition()
        ft.SetPosition(pcbnew.VECTOR2I(c.x + mm(gx), c.y + mm(gy)))
        ft.SetOrientationDegrees(fs.GetOrientationDegrees() + (180 if pad_sign < 0 else 0))
    for tie, shunt, sgn in (('NT1', 'R15', -1), ('NT2', 'R15', +1), ('NT3', 'R31', -1), ('NT4', 'R31', +1)):
        place_tie(tie, shunt, sgn)

    # silkscreen help for first-time builders: polarity, pot names, LED meaning, the common-ground warning
    LABELS = [('+', 9.3, 27.6, 1.6, 0), ('-', 9.3, 22.5, 1.6, 0), ('VIN', 9.3, 25.05, 0.8, 0),
              ('+', 55.6, 39.2, 1.6, 0), ('-', 55.6, 44.3, 1.6, 0), ('OUT', 63.9, 31.0, 0.9, 90),
              ('OUT- switched: never tie to IN-', 35.3, 47.0, 0.6, 0),
              ('CV', 29.4, 41.95, 0.9, 0), ('CC', 41.2, 41.95, 0.9, 0), ('CW+', 35.3, 44.4, 0.7, 90),
              ('IN', 1.25, 35.6, 0.6, 90), ('ON', 31.8, 39.3, 0.6, 0), ('OUT', 53.2, 46.5, 0.6, 90),
              ('SafeBuck-80 v1.0 - DUBURI', 32.5, 0.95, 0.9, 0)]
    for txt, x, y, sz, rot in LABELS:
        st = pcbnew.PCB_TEXT(board); st.SetText(txt); st.SetLayer(pcbnew.F_SilkS)
        st.SetPosition(V(x, y)); st.SetTextAngleDegrees(rot)
        st.SetTextSize(pcbnew.VECTOR2I(mm(sz), mm(sz))); st.SetTextThickness(mm(max(0.12, sz * 0.15)))
        board.Add(st)
    # bottom side (all parts are on top, so the back is free): Duburi logo + designer credit, mirrored to read from below
    logo_path = os.path.join(LIBDIR, 'Logo_Duburi.kicad_mod')
    if os.path.exists(logo_path):
        lg = load_fp('SafeBuck:Logo_Duburi'); lg.SetReference('LOGO1'); lg.SetValue('Logo_Duburi')
        board.Add(lg); lg.SetPosition(V(18.0, 40.4)); lg.Flip(V(18.0, 40.4), True)
    for txt, x, y, sz in (('SafeBuck-80', 42.0, 38.4, 1.6), ('Designed by Jarif Alam', 42.0, 40.9, 1.25),
                          ('80 W protected buck-boost - 2026', 42.0, 43.0, 0.85)):
        st = pcbnew.PCB_TEXT(board); st.SetText(txt); st.SetLayer(pcbnew.B_SilkS); st.SetMirrored(True)
        st.SetPosition(V(x, y)); st.SetTextSize(pcbnew.VECTOR2I(mm(sz), mm(sz))); st.SetTextThickness(mm(max(0.15, sz * 0.15)))
        board.Add(st)

    # outline with 1 mm corner radius
    r = 1.0
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetWidth(mm(0.1)); board.Add(s)
    def arc(c, start, ang):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetCenter(V(*c)); s.SetStart(V(*start)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T)); s.SetWidth(mm(0.1)); board.Add(s)
    seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
    arc((r, r), (0, r), 90); arc((W - r, r), (W - r, 0), 90); arc((W - r, H - r), (W, H - r), 90); arc((r, H - r), (r, H), 90)
    return board, netobj

def courtyard_report(board):
    """list overlapping courtyards (F side)"""
    boxes = []
    for fp in board.GetFootprints():
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
        boxes.append((fp.GetReference(), bb))
    bad = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a.Intersects(b):
                ov = a.Intersect(b) if hasattr(a, 'Intersect') else None
                bad.append((boxes[i][0], boxes[j][0]))
    out = []
    for fp in board.GetFootprints():
        bb = fp.GetBoundingBox(False, False)
        x0, y0 = pcbnew.ToMM(bb.GetX()) - OX, pcbnew.ToMM(bb.GetY()) - OY
        x1, y1 = x0 + pcbnew.ToMM(bb.GetWidth()), y0 + pcbnew.ToMM(bb.GetHeight())
        if x0 < -0.01 or y0 < -0.01 or x1 > W + 0.01 or y1 > H + 0.01:
            out.append((fp.GetReference(), round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)))
    return bad, out

def drc(board, path):
    pcbnew.WriteDRCReport(board, path, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(path).read()
    import re, collections
    kinds = collections.Counter(re.findall(r'^\[(\w+)\]', txt, re.M))
    return kinds, txt

if __name__ == '__main__':
    board, _ = build()
    for fp in board.GetFootprints(): fp.BuildCourtyardCaches() if hasattr(fp, 'BuildCourtyardCaches') else None
    bad, out = courtyard_report(board)
    print('outside board:', out)
    path = os.path.join(KDIR, 'SafeBuck-80_placed.kicad_pcb')     # route.py turns this into SafeBuck-80.kicad_pcb
    board.Save(path); print('saved', path)
    b2 = pcbnew.LoadBoard(path)
    kinds, txt = drc(b2, os.path.join(KDIR, 'drc_placement.rpt'))
    print('DRC kinds:', dict(kinds))
    import re
    for m in re.finditer(r'\[courtyards_overlap\][^\n]*\n([^\n]*)\n([^\n]*)', txt):
        a = re.search(r'Footprint (\S+)', m.group(1)); b = re.search(r'Footprint (\S+)', m.group(2))
        print('  overlap', a.group(1) if a else m.group(1)[:40], b.group(1) if b else m.group(2)[:40])
