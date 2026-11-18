"""
Route SafeBuck-80 (2-layer, 2 oz):
  1. power copper as F.Cu zones (each zone = union of rectangles, checked against foreign pads)
  2. hot-loop GND returns as F.Cu GND zones, full GND plane on B.Cu
  3. Freerouting (Specctra DSN/SES) for every remaining connection
  4. F.Cu GND fill, GND stitching vias, zone fill, DRC
Run with KiCad's python after build_pcb.py:
  /usr/bin/python3 route.py route                      # Freerouting from scratch
  /usr/bin/python3 route.py complete kicad/SafeBuck-80.ses   # finish open links with complete_routes.py, fill, DRC
"""
import os, sys, math, re, subprocess, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew

KDIR = os.path.join(HERE, 'kicad')
PLACED = os.path.join(KDIR, 'SafeBuck-80_placed.kicad_pcb')   # from build_pcb.py
PCB = os.path.join(KDIR, 'SafeBuck-80.kicad_pcb')             # final routed board
FR = os.environ.get('FREEROUTING_JAR', os.path.join(HERE, 'tools', 'freerouting.jar'))
W, H = 65.0, 48.0
OX, OY = 100.0, 100.0
CLR = 0.25                       # zone-to-foreign-copper clearance (mm)
def mm(v): return pcbnew.FromMM(v)

# ------------------------------------------------------------------ power zones, board-local mm
# (x0, y0, x1, y1) rectangles; the union of a net's rectangles is its zone outline.
# Layout intent (docs/layout-rules.md): hot loop 1 = VIN_P -> Q3 -> SW1 -> Q4 -> GND -> C7/C8,
# hot loop 2 = SW2 -> Q6 -> VOUT_C -> C12..C14 -> GND -> Q5, both closed on F.Cu with no vias.
ZONES = {
    'VIN_RAW': (6, [(4.5, 26.1, 7.5, 29.4), (2.45, 29.0, 7.5, 31.3), (2.45, 31.0, 4.75, 35.2)]),
    'VIN_F':   (6, [(7.35, 31.6, 9.9, 37.9), (9.65, 36.95, 15.2, 40.05), (14.95, 35.95, 19.85, 40.95)]),
    'CSRC':    (6, [(15.0, 32.45, 18.5, 33.8), (16.3, 33.8, 19.8, 35.15)]),
    'VIN_P':   (6, [(7.7, 4.15, 12.2, 7.05), (7.7, 7.05, 10.9, 18.65), (10.9, 14.5, 13.15, 18.65),
                    (13.15, 13.4, 18.0, 18.65), (15.9, 18.65, 17.8, 26.6), (14.95, 26.6, 19.85, 31.65)]),
    'SW1':     (7, [(14.5, 10.6, 24.4, 12.3), (24.3, 10.6, 28.1, 11.55), (18.85, 12.2, 23.7, 16.25)]),
    'SWL':     (7, [(24.3, 17.05, 28.2, 18.2), (27.6, 17.0, 29.6, 19.2), (29.0, 18.2, 31.0, 20.6), (30.9, 20.0, 34.5, 34.2)]),
    'SW2':     (7, [(47.2, 8.9, 57.7, 10.0), (54.2, 10.0, 57.7, 11.35), (47.0, 10.0, 51.85, 15.0),
                    (44.35, 12.5, 47.15, 20.8), (41.5, 18.9, 47.15, 20.8), (41.5, 20.55, 45.1, 34.2)]),
    'VOUT_C':  (6, [(53.1, 12.4, 60.6, 17.4), (60.6, 14.9, 63.3, 17.4), (59.6, 7.4, 60.7, 12.4),   # + D15 clamp, C36
                    (53.1, 17.4, 55.3, 27.1), (55.3, 17.4, 61.6, 21.65), (55.55, 21.65, 56.95, 32.1)]),
    'OUTF':    (6, [(62.2, 28.5, 63.4, 32.4), (60.85, 32.3, 63.4, 36.05)]),
    'OUTP':    (6, [(55.95, 32.45, 58.35, 36.8), (55.95, 36.4, 60.5, 40.7)]),
    'OUTN':    (6, [(48.75, 39.95, 53.75, 44.85), (53.0, 42.75, 60.5, 45.8)]),
    # hot-loop GND returns (kept free of traces so the loops close on the top layer)
    'GND':     (5, [(18.85, 16.6, 22.7, 18.35), (19.1, 18.35, 20.8, 25.1),        # Q4 source -> C7/C8
                    (47.45, 15.75, 51.0, 17.35), (50.1, 17.35, 51.75, 27.1)]),    # Q5 source -> C12..C14
}

def poly_from_rects(rects):
    ps = pcbnew.SHAPE_POLY_SET()
    for (x0, y0, x1, y1) in rects:
        r = pcbnew.SHAPE_POLY_SET(); r.NewOutline()
        for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            r.Append(mm(OX + x), mm(OY + y))
        ps.BooleanAdd(r, pcbnew.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
    ps.Simplify(pcbnew.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
    return ps

def add_zone(board, net, layer, outline, prio, connection='full', clearance=CLR, min_w=0.25, name=''):
    """one KiCad zone per outline of the polygon set (a zone keeps only one main outline)"""
    zones = []
    for i in range(outline.OutlineCount()):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer); z.SetNet(board.FindNet(net))
        z.SetAssignedPriority(prio) if hasattr(z, 'SetAssignedPriority') else z.SetPriority(prio)
        z.SetLocalClearance(mm(clearance)); z.SetMinThickness(mm(min_w))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        if name: z.SetZoneName(name if outline.OutlineCount() == 1 else f'{name}{i + 1}')
        if connection == 'full':
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        elif connection == 'tht':        # solid to SMD pads, thermal spokes on through-hole pads
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
            z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.6))
        else:
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.5))
        o = z.Outline()                  # copy points (SetOutline() would hand over ownership)
        o.RemoveAllContours(); o.NewOutline()
        ol = outline.COutline(i)
        for k in range(ol.PointCount()):
            p = ol.CPoint(k); o.Append(p.x, p.y)
        board.Add(z); zones.append(z)
    return zones

def check_zones(board):
    """foreign pads within CLR of a power zone, and overlaps between zones of different nets"""
    bad = []
    outlines = {n: poly_from_rects(r) for n, (_, r) in ZONES.items()}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if not p.IsOnLayer(pcbnew.F_Cu) or p.GetNumber() == '': continue
            for net, ol in outlines.items():
                if p.GetNetname() == net: continue
                sh = pcbnew.SHAPE_POLY_SET()
                p.TransformShapeToPolygon(sh, pcbnew.F_Cu, mm(CLR - 0.01), mm(0.005))
                sh.BooleanIntersection(ol, pcbnew.SHAPE_POLY_SET.PM_FAST)
                if sh.OutlineCount() and sh.Area() > 0:
                    bad.append(f'{fp.GetReference()}.{p.GetNumber()} ({p.GetNetname()}) too close to zone {net}')
    nets = list(outlines)
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            a = pcbnew.SHAPE_POLY_SET(outlines[nets[i]]); b = pcbnew.SHAPE_POLY_SET(outlines[nets[j]])
            b.Inflate(mm(CLR - 0.01), 8)
            a.BooleanIntersection(b, pcbnew.SHAPE_POLY_SET.PM_FAST)
            if a.OutlineCount() and a.Area() > 0:
                bad.append(f'zones {nets[i]} and {nets[j]} closer than {CLR} mm')
    return bad

def dsn_poly(ol_set, layer, inset):
    """outlines of a polygon set, shrunk by `inset` mm, as Specctra polygons (um, y up)"""
    s = pcbnew.SHAPE_POLY_SET(ol_set)
    if inset: s.Inflate(-mm(inset), 8)
    out = []
    for i in range(s.OutlineCount()):
        ol = s.COutline(i)
        pts = ' '.join(f'{ol.CPoint(k).x / 1000:.1f} {-ol.CPoint(k).y / 1000:.1f}' for k in range(ol.PointCount()))
        if ol.PointCount() >= 3:
            out.append(f'    (keepout "" (polygon {layer} 0 {pts}))')
    return out

def tune_dsn(board, path):
    """Freerouting lets other nets run straight through a plane, so each power-zone rectangle is
    also written as a fixed ("fix") wire of its own net: other nets must keep clear of it, the
    same net can connect anywhere on it. Net-tie copper becomes a small keepout, and the routing
    boundary is pulled 0.15 mm inside the board edge."""
    t = open(path).read()
    U = lambda v: f'{v * 1000:.0f}'                       # mm -> um
    wires = []
    for net, (prio, rects) in ZONES.items():
        for (x0, y0, x1, y1) in rects:
            w, h = x1 - x0, y1 - y0
            if w >= h: a, b, wd = (x0 + h / 2, (y0 + y1) / 2), (max(x1 - h / 2, x0 + h / 2), (y0 + y1) / 2), h
            else:      a, b, wd = ((x0 + x1) / 2, y0 + w / 2), ((x0 + x1) / 2, max(y1 - w / 2, y0 + w / 2)), w
            wires.append(f'    (wire (path F.Cu {U(wd)} {U(OX + a[0])} {U(-(OY + a[1]))} {U(OX + b[0])} {U(-(OY + b[1]))})'
                         f' (net {net}) (type fix))')
    ko = []
    for fp in board.GetFootprints():
        if not fp.GetReference().startswith('NT'): continue
        c = fp.GetPosition(); x, y = c.x / 1e6, c.y / 1e6
        ko.append(f'    (keepout "" (rect F.Cu {U(x - 0.3)} {U(-(y - 0.3))} {U(x + 0.3)} {U(-(y + 0.3))}))')
    e, cc = 0.15, 1.0
    X0, Y0, X1, Y1 = OX, OY, OX + W, OY + H
    pts = [(X0 + cc, Y0 + e), (X1 - cc, Y0 + e), (X1 - e, Y0 + cc), (X1 - e, Y1 - cc), (X1 - cc, Y1 - e),
           (X0 + cc, Y1 - e), (X0 + e, Y1 - cc), (X0 + e, Y0 + cc), (X0 + cc, Y0 + e)]
    bnd = '    (boundary\n      (path pcb 0 ' + ' '.join(f'{U(px)} {U(-py)}' for px, py in pts) + ')\n    )'
    s = t.index('    (boundary'); e_ = t.index('    )', t.index('(path pcb', s)) + 5
    t = t[:s] + bnd + '\n' + '\n'.join(ko) + t[e_:]
    w0 = t.rindex('(wiring')
    t = t[:w0] + '(wiring\n' + '\n'.join(wires) + t[w0 + len('(wiring'):]
    open(path, 'w').write(t)
    return len(ko), len(wires)

def run_freerouting(dsn, ses, passes=100):
    # Freerouting 1.9 needs an X display even in batch mode -> run it inside a virtual X server
    cmd = ['xvfb-run', '-a', 'java', '-jar', FR, '-de', dsn, '-do', ses, '-mp', str(passes), '-mt', '1']
    print('running', ' '.join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3000)
    tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
    print('\n'.join(tail))
    return os.path.exists(ses)

def stitch_gnd(board, spacing=2.6):
    """GND vias on a grid wherever both layers are GND copper (keeps the two GND layers one node)"""
    n = 0
    gnd = board.FindNet('GND')
    zf = [z for z in board.Zones() if z.GetNetname() == 'GND']
    fz = [z for z in zf if z.GetLayer() == pcbnew.F_Cu]
    bz = [z for z in zf if z.GetLayer() == pcbnew.B_Cu]
    def filled_at(zs, layer, x, y, r):
        for z in zs:
            fp = z.GetFilledPolysList(layer)
            c = pcbnew.SHAPE_POLY_SET(); c.NewOutline()
            for k in range(12):
                import math
                a = 2 * math.pi * k / 12
                c.Append(int(x + r * math.cos(a)), int(y + r * math.sin(a)))
            c.BooleanSubtract(fp, pcbnew.SHAPE_POLY_SET.PM_FAST)
            if c.OutlineCount() == 0 or c.Area() < 1: return True
        return False
    holes = [v.GetPosition() for v in board.GetTracks() if v.GetClass() == 'PCB_VIA']
    holes += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
    def far(X, Y):
        return all((X - h.x) ** 2 + (Y - h.y) ** 2 > mm(1.2) ** 2 for h in holes)
    y = 1.5
    while y < H - 1.0:
        x = 1.5
        while x < W - 1.0:
            X, Y = mm(OX + x), mm(OY + y)
            if far(X, Y) and filled_at(fz, pcbnew.F_Cu, X, Y, mm(0.75)) and filled_at(bz, pcbnew.B_Cu, X, Y, mm(0.75)):
                v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(X, Y))
                v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                board.Add(v); n += 1; holes.append(pcbnew.VECTOR2I(X, Y))
            x += spacing
        y += spacing
    return n

def import_ses(board, path, skip=()):
    """add Freerouting's wires and vias from a Specctra session file (KiCad 7's python
    ImportSpecctraSES() only works inside the GUI). SES units: 1/res um, y axis up."""
    from make_schematic import parse, find
    root = parse(open(path).read())[0]
    routes = find(root, 'routes')[0]
    res = float(find(routes, 'resolution')[0][2])
    nm = 1000.0 / res
    ntr = nvia = 0
    for net in find(find(routes, 'network_out')[0], 'net'):
        if str(net[1]) in skip: continue
        ni = board.FindNet(str(net[1]))
        for w in find(net, 'wire'):
            for pth in find(w, 'path'):
                layer = pcbnew.F_Cu if str(pth[1]) == 'F.Cu' else pcbnew.B_Cu
                width = int(float(pth[2]) * nm)
                if width > mm(0.6): continue          # our fixed power-zone wires, not real tracks
                c = [float(v) for v in pth[3:]]
                pts = [pcbnew.VECTOR2I(int(c[i] * nm), int(-c[i + 1] * nm)) for i in range(0, len(c) - 1, 2)]
                for a, b in zip(pts, pts[1:]):
                    tr = pcbnew.PCB_TRACK(board); tr.SetStart(a); tr.SetEnd(b); tr.SetWidth(width)
                    tr.SetLayer(layer); tr.SetNet(ni); board.Add(tr); ntr += 1
        for v in find(net, 'via'):
            m = re.search(r'_(\d+):(\d+)_um', str(v[1]))
            dia, drill = (int(m.group(1)) * 1000, int(m.group(2)) * 1000) if m else (mm(0.6), mm(0.3))
            via = pcbnew.PCB_VIA(board); via.SetPosition(pcbnew.VECTOR2I(int(float(v[2]) * nm), int(-float(v[3]) * nm)))
            via.SetWidth(dia); via.SetDrill(drill); via.SetNet(ni); via.SetViaType(pcbnew.VIATYPE_THROUGH)
            board.Add(via); nvia += 1
    return ntr, nvia

def drc_summary(board, path):
    pcbnew.WriteDRCReport(board, path, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(path).read()
    kinds = collections.Counter(re.findall(r'^\[(\w+)\]', txt, re.M))
    m = re.search(r'\*\* Found (\d+) unconnected pads \*\*', txt)
    return dict(kinds), (m.group(1) if m else '?')

def base_board():
    """placed board + power zones + bottom GND plane (no tracks)"""
    board = pcbnew.LoadBoard(PLACED)
    for net, (prio, rects) in ZONES.items():
        add_zone(board, net, pcbnew.F_Cu, poly_from_rects(rects), prio, name=f'{net}_top')
    add_zone(board, 'GND', pcbnew.B_Cu, poly_from_rects([(0.3, 0.3, W - 0.3, H - 0.3)]), 0, connection='tht', name='GND_bottom')
    return board

def island_vias(board, r_test=0.33, hole_gap=0.9):
    """top-layer GND islands with no via or through-hole GND pad inside get a via to the bottom plane
    (spot: a 0.33 mm disk inside the island and inside the bottom GND fill, 0.9 mm from other holes)"""
    import math
    gnd = board.FindNet('GND')
    holes = [v.GetPosition() for v in board.GetTracks() if v.GetClass() == 'PCB_VIA']
    holes += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
    anchors = [v.GetPosition() for v in board.GetTracks() if v.GetClass() == 'PCB_VIA' and v.GetNetname() == 'GND']
    anchors += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0 and p.GetNetname() == 'GND']
    bfill = [z.GetFilledPolysList(pcbnew.B_Cu) for z in board.Zones() if z.GetNetname() == 'GND' and z.IsOnLayer(pcbnew.B_Cu)]
    def disk(x, y, r):
        c = pcbnew.SHAPE_POLY_SET(); c.NewOutline()
        for k in range(16):
            a = 2 * math.pi * k / 16; c.Append(int(x + r * math.cos(a)), int(y + r * math.sin(a)))
        return c
    def inside(poly, x, y, r):
        c = disk(x, y, r); c.BooleanSubtract(poly, pcbnew.SHAPE_POLY_SET.PM_FAST)
        return c.OutlineCount() == 0 or c.Area() < 1
    added, stuck = 0, []
    for z in [z for z in board.Zones() if z.GetNetname() == 'GND' and z.IsOnLayer(pcbnew.F_Cu)]:
        fl = z.GetFilledPolysList(pcbnew.F_Cu)
        for k in range(fl.OutlineCount()):
            isl = pcbnew.SHAPE_POLY_SET(); isl.AddOutline(fl.COutline(k))
            for h in range(fl.HoleCount(k)): isl.AddHole(fl.CHole(k, h))
            if any(isl.Contains(a) for a in anchors): continue
            bb = isl.BBox(); spot = None
            y = bb.GetY() + mm(r_test)
            while y < bb.GetBottom() - mm(r_test) and not spot:
                x = bb.GetX() + mm(r_test)
                while x < bb.GetRight() - mm(r_test):
                    if all((x - h.x) ** 2 + (y - h.y) ** 2 > mm(hole_gap) ** 2 for h in holes) and inside(isl, x, y, mm(r_test)) \
                       and any(inside(bf, x, y, mm(r_test)) for bf in bfill):
                        spot = (x, y); break
                    x += mm(0.1)
                y += mm(0.1)
            if not spot:
                stuck.append((round(pcbnew.ToMM(bb.GetX()) - OX, 1), round(pcbnew.ToMM(bb.GetY()) - OY, 1), round(isl.Area() / 1e12, 2)))
                continue
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(int(spot[0]), int(spot[1])))
            v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            board.Add(v); added += 1; holes.append(v.GetPosition()); anchors.append(v.GetPosition())
    return added, stuck

# Hand-placed escape stubs for the two tightest spots. The completion router routes nets one at a time and
# would take the shortest way out of U2's left pin row, closing in the neighbouring pins; these stubs fan the
# row out first (CSRC straight out to a via, GND below it to its own via into the bottom plane), and tie U1's
# GND pin 10 to its exposed pad. Other nets' tracks that clash with a stub are ripped up and re-routed.
FANOUT = [   # net, [(x, y) board mm, ...], via at the last point
    ('CSRC', [(22.4625, 30.75), (20.15, 30.75)], True),                      # U2.15
    ('GND',  [(22.4625, 31.25), (21.10, 31.25), (20.85, 31.50)], True),      # U2.16
    ('GND',  [(34.90, 8.625), (36.30, 8.625)], False),                       # U1.10 -> U1 exposed pad
]

def apply_fanout(board):
    from complete_routes import add_track, add_via, TW, CL, VIA_D
    segs = []                                          # (net, layers, ax, ay, bx, by, half width)
    for net, pts, via in FANOUT:
        P = [(OX + x, OY + y) for x, y in pts]
        segs += [(net, (pcbnew.F_Cu,), a[0], a[1], b[0], b[1], TW / 2) for a, b in zip(P, P[1:])]
        if via: segs.append((net, (pcbnew.F_Cu, pcbnew.B_Cu), P[-1][0], P[-1][1], P[-1][0], P[-1][1], VIA_D / 2))
    def dseg(a, b):                                    # distance between two segments (sampled, mm)
        best = 1e9
        for k in range(21):
            px, py = a[0] + (a[2] - a[0]) * k / 20, a[1] + (a[3] - a[1]) * k / 20
            dx, dy = b[2] - b[0], b[3] - b[1]; ll = dx * dx + dy * dy
            s = 0 if ll == 0 else max(0, min(1, ((px - b[0]) * dx + (py - b[1]) * dy) / ll))
            best = min(best, math.hypot(b[0] + s * dx - px, b[1] + s * dy - py))
        return best
    kill = set()
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            q = t.GetPosition(); geo = (q.x / 1e6, q.y / 1e6, q.x / 1e6, q.y / 1e6); lay = (pcbnew.F_Cu, pcbnew.B_Cu)
        else:
            s, e = t.GetStart(), t.GetEnd(); geo = (s.x / 1e6, s.y / 1e6, e.x / 1e6, e.y / 1e6); lay = (t.GetLayer(),)
        hw = t.GetWidth() / 1e6 / 2
        for net, L, ax, ay, bx, by, r in segs:
            if t.GetNetname() == net or not set(L) & set(lay): continue
            if dseg((ax, ay, bx, by), geo) < r + hw + CL + 0.01 or dseg(geo, (ax, ay, bx, by)) < r + hw + CL + 0.01:
                kill.add(t); break
    ripped = sorted({t.GetNetname() for t in kill})
    for t in kill: board.Remove(t)
    for net, pts, via in FANOUT:
        ni = board.FindNet(net); P = [(OX + x, OY + y) for x, y in pts]
        for a, b in zip(P, P[1:]): add_track(board, ni, 0, a[0], a[1], b[0], b[1])
        if via: add_via(board, ni, *P[-1])
    return ripped

def gnd_merge(board, r_test=0.26, hole_gap=0.75, step=0.1):
    """GND copper that is not connected to the main GND: union-find over the filled islands of every GND zone,
    GND vias, pads and tracks; then, while another component exists, drop a via where one of its islands
    overlaps an island of a different component on the other layer (disk of r_test inside both fills,
    hole_gap from other holes). The pours keep 0.25 mm from other nets, so a 0.6 mm via whose centre disk
    of 0.26 mm lies inside both fills still keeps 0.21 mm (> 0.205) from foreign copper.
    Returns (vias added, components left over)."""
    import math
    gnd = board.FindNet('GND'); added = 0
    holes = [v.GetPosition() for v in board.GetTracks() if v.GetClass() == 'PCB_VIA']
    holes += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
    def disk_inside(poly, x, y, r):
        c = pcbnew.SHAPE_POLY_SET(); c.NewOutline()
        for k in range(16):
            a = 2 * math.pi * k / 16; c.Append(int(x + r * math.cos(a)), int(y + r * math.sin(a)))
        c.BooleanSubtract(poly, pcbnew.SHAPE_POLY_SET.PM_FAST)
        return c.OutlineCount() == 0 or c.Area() < 1
    for it in range(40):
        isl = []                                       # (layer, polyset, area)
        for z in board.Zones():
            if z.GetNetname() != 'GND' or z.GetIsRuleArea(): continue
            for L in (pcbnew.F_Cu, pcbnew.B_Cu):
                if not z.IsOnLayer(L): continue
                fl = z.GetFilledPolysList(L)
                for k in range(fl.OutlineCount()):
                    sp = pcbnew.SHAPE_POLY_SET(); sp.AddOutline(fl.COutline(k))
                    for h in range(fl.HoleCount(k)): sp.AddHole(fl.CHole(k, h))
                    isl.append((L, sp, sp.Area()))
        items = []                                     # (layers, anchor points, object)
        for t in board.GetTracks():
            if t.GetNetname() != 'GND': continue
            if t.GetClass() == 'PCB_VIA': items.append(((pcbnew.F_Cu, pcbnew.B_Cu), [t.GetPosition()], t))
            else: items.append(((t.GetLayer(),), [t.GetStart(), t.GetEnd()], t))
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() == 'GND':
                    items.append((tuple(L for L in (pcbnew.F_Cu, pcbnew.B_Cu) if p.IsOnLayer(L)), [p.GetPosition()], p))
        n = len(isl) + len(items); par = list(range(n))
        def f(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        def u(a, b): par[f(a)] = f(b)
        for j, (lays, pts, obj) in enumerate(items):
            for i, (L, sp, _) in enumerate(isl):
                if L in lays and any(sp.Contains(q) for q in pts): u(len(isl) + j, i)
        bbs = []
        for lays, pts, obj in items:
            bb = obj.GetBoundingBox(); bbs.append((bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()))
        for j, (lays, pts, obj) in enumerate(items):            # item-item contacts (track ends on pads/vias/tracks)
            A = bbs[j]
            for k2 in range(j + 1, len(items)):
                l2, p2, o2 = items[k2]; B = bbs[k2]
                if A[0] > B[2] or B[0] > A[2] or A[1] > B[3] or B[1] > A[3]: continue
                if not set(lays) & set(l2): continue
                if any(o2.HitTest(q, 0) for q in pts) or any(obj.HitTest(q, 0) for q in p2): u(len(isl) + j, len(isl) + k2)
        comp = {}
        for i in range(len(isl)): comp.setdefault(f(i), []).append(i)
        for j in range(len(items)): comp.setdefault(f(len(isl) + j), [])
        if not isl: return added, 0
        main = f(max(range(len(isl)), key=lambda i: isl[i][2] if isl[i][0] == pcbnew.B_Cu else 0))
        others = [c for c in comp if c != main and comp[c]]
        lone = [c for c in comp if c != main and not comp[c]]
        if not others: return added, len(lone)
        done = False
        for c in sorted(others, key=lambda c: -sum(isl[i][2] for i in comp[c])):
            for i in comp[c]:
                L, sp, _ = isl[i]
                cands = [k for k in range(len(isl)) if isl[k][0] != L and f(k) != c]
                cands.sort(key=lambda k: (f(k) != main, -isl[k][2]))     # straight to the main GND first
                for k in cands:
                    a, b = sp.BBox(), isl[k][1].BBox()
                    x0, y0 = max(a.GetX(), b.GetX()), max(a.GetY(), b.GetY())
                    x1, y1 = min(a.GetRight(), b.GetRight()), min(a.GetBottom(), b.GetBottom())
                    if x1 - x0 < 2 * mm(r_test) or y1 - y0 < 2 * mm(r_test): continue
                    y = y0 + mm(r_test)
                    while y <= y1 - mm(r_test) and not done:
                        x = x0 + mm(r_test)
                        while x <= x1 - mm(r_test):
                            q = pcbnew.VECTOR2I(int(x), int(y))
                            if sp.Contains(q) and isl[k][1].Contains(q) and \
                               all((x - h.x) ** 2 + (y - h.y) ** 2 > mm(hole_gap) ** 2 for h in holes) and \
                               disk_inside(sp, x, y, mm(r_test)) and disk_inside(isl[k][1], x, y, mm(r_test)):
                                v = pcbnew.PCB_VIA(board); v.SetPosition(q); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
                                v.SetNet(gnd); v.SetViaType(pcbnew.VIATYPE_THROUGH); board.Add(v)
                                holes.append(q); added += 1; done = True; break
                            x += mm(step)
                        y += mm(step)
                    if done: break
                if done: break
            if done: break
        if not done: return added, len(others) + len(lone)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return added, -1

def gnd_hookup(board, step=0.02, reach=4.0, hole_gap=0.65, rule=0.205):
    """Last resort for GND copper the grid router cannot reach (its 0.04 mm grid margin is too coarse for some
    pockets): with exact KiCad hit tests, look for a via that touches the main GND on one layer and either sits
    in the stray copper's own pour or is reached from one of its vias/pads by one straight 0.2 mm track.
    Returns the number of hookups made."""
    from complete_routes import clusters, add_track, add_via
    gnd = board.FindNet('GND'); gc = gnd.GetNetCode(); made = 0
    def P(x, y): return pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6)))
    for attempt in range(6):
        op = clusters(board)
        if gc not in op: return made
        groups = sorted(op[gc], key=len, reverse=True)
        tracks = list(board.GetTracks()); pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
        zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
        holes = [t.GetPosition() for t in tracks if t.GetClass() == 'PCB_VIA'] + [p.GetPosition() for p in pads if p.GetDrillSize().x > 0]
        def clear(x, y, r, layer):
            q = P(x, y); acc = int((r + rule + 0.003) * 1e6)
            for t in tracks:
                if t.GetNetCode() != gc and (t.GetClass() == 'PCB_VIA' or t.GetLayer() == layer) and t.HitTest(q, acc): return False
            for p in pads:
                if p.GetNetCode() != gc and p.IsOnLayer(layer) and p.HitTest(q, acc): return False
            for z in zones:
                if z.GetNetCode() != gc and z.IsOnLayer(layer) and z.HitTestFilledArea(layer, q, acc): return False
            return True
        def seg_clear(a, c, layer):
            n = int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.01) + 1
            return all(clear(a[0] + (c[0] - a[0]) * k / n, a[1] + (c[1] - a[1]) * k / n, 0.1, layer) for k in range(n + 1))
        main = groups[0]
        main_objs = [it[4] for it in main if it[0] in ('via', 'trk')]
        main_pads = [p for p in pads if p.GetNetCode() == gc and any(it[0] == 'pad' and it[4] == f'{p.GetParent().GetReference()}.{p.GetNumber()}' for it in main)]
        main_isl = []
        for z in zones:                                 # pour islands that hold a main GND item
            if z.GetNetCode() != gc: continue
            for L in (pcbnew.F_Cu, pcbnew.B_Cu):
                if not z.IsOnLayer(L): continue
                fl = z.GetFilledPolysList(L)
                for k in range(fl.OutlineCount()):
                    sp = pcbnew.SHAPE_POLY_SET(); sp.AddOutline(fl.COutline(k))
                    for h in range(fl.HoleCount(k)): sp.AddHole(fl.CHole(k, h))
                    if any(sp.Contains(p.GetPosition()) for p in main_pads if p.IsOnLayer(L)) or \
                       any(sp.Contains(o.GetPosition()) for o in main_objs if o.GetClass() == 'PCB_VIA'):
                        main_isl.append((L, sp))
        def touches_main(x, y, L):
            q = P(x, y)
            return any(LL == L and sp.Contains(q) for LL, sp in main_isl) or \
                   any(p.IsOnLayer(L) and p.HitTest(q, int(0.3e6)) for p in main_pads) or \
                   any(o.GetClass() == 'PCB_VIA' and o.HitTest(q, int(0.3e6)) for o in main_objs)
        done = False
        for grp in groups[1:]:
            anchors = []                                # (x, y, layers) of the stray copper
            for it in grp:
                if it[0] == 'via': anchors.append((it[1][0] / 1e6, it[1][1] / 1e6, (pcbnew.F_Cu, pcbnew.B_Cu)))
                elif it[0] == 'pad': anchors.append((it[3][0] / 1e6, it[3][1] / 1e6, tuple(L for L in (pcbnew.F_Cu, pcbnew.B_Cu) if L in [(pcbnew.F_Cu, pcbnew.B_Cu)[k] for k in it[2]])))
            best = None
            for ax, ay, alay in anchors:
                n = int(reach / step)
                for di in range(-n, n + 1, 2):
                    for dj in range(-n, n + 1, 2):
                        x, y = ax + di * step, ay + dj * step; d = math.hypot(x - ax, y - ay)
                        if d > reach or (best and d >= best[0]): continue
                        for L1 in (pcbnew.F_Cu, pcbnew.B_Cu):          # via touches the main GND on L1
                            L2 = pcbnew.B_Cu if L1 == pcbnew.F_Cu else pcbnew.F_Cu
                            if L2 not in alay or not touches_main(x, y, L1): continue
                            if min(math.hypot(h.x / 1e6 - x, h.y / 1e6 - y) for h in holes) < hole_gap: continue
                            if not (clear(x, y, 0.3, pcbnew.F_Cu) and clear(x, y, 0.3, pcbnew.B_Cu)): continue
                            if not seg_clear((ax, ay), (x, y), L2): continue
                            best = (d, x, y, ax, ay, L2)
            if best:
                d, x, y, ax, ay, L2 = best
                add_track(board, gnd, 0 if L2 == pcbnew.F_Cu else 1, ax, ay, x, y); add_via(board, gnd, x, y)
                print(f'   GND hookup: {"F" if L2 == pcbnew.F_Cu else "B"}.Cu track ({ax - OX:.2f},{ay - OY:.2f}) -> via ({x - OX:.2f},{y - OY:.2f}), {d:.2f} mm')
                made += 1; done = True
                pcbnew.ZONE_FILLER(board).Fill(board.Zones())
                break
        if not done: return made
    return made

def sync_project():
    """KiCad keeps net classes and design rules in the .kicad_pro file; the python Save() of a board
    that was loaded from another file does not rewrite it. Copy them from the placed board's project."""
    import json
    src = json.load(open(PLACED.replace('.kicad_pcb', '.kicad_pro')))
    dst_path = PCB.replace('.kicad_pcb', '.kicad_pro')
    dst = json.load(open(dst_path)) if os.path.exists(dst_path) else dict(src)
    dst['net_settings'] = src['net_settings']
    dst.setdefault('board', {})['design_settings'] = src['board']['design_settings']
    dst.setdefault('meta', {})['filename'] = os.path.basename(dst_path)
    json.dump(dst, open(dst_path, 'w'), indent=2); open(dst_path, 'a').write('\n')

def add_top_pour(board):
    if not any(z.GetZoneName() == 'GND_top_fill' for z in board.Zones()):
        add_zone(board, 'GND', pcbnew.F_Cu, poly_from_rects([(0.3, 0.3, W - 0.3, H - 0.3)]), 1, connection='tht', name='GND_top_fill')

def finish(board):
    from complete_routes import prune_stubs
    add_top_pour(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print('stitching vias:', stitch_gnd(board))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print('GND merge vias (added, components left):', gnd_merge(board))
    from complete_routes import complete, clusters
    # GND copper the pours and merge vias did not reach is routed now (with rip-up; ripped nets re-route or roll
    # back). A refill can move a pour edge away from a new track end, so repeat until a refill changes nothing.
    for it in range(4):
        for line in complete(board, [(n, r) for n, (p_, r) in ZONES.items()], OX, OY, W, H, skip=(), rippable=(), rounds=10):
            print('  ', line)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        print('GND merge vias (added, components left):', gnd_merge(board))
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        n = prune_stubs(board)
        print('dead ends (removed, trimmed):', n)
        if any(n): pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        left = clusters(board)
        if list(left) == [board.FindNet('GND').GetNetCode()] and it >= 1:
            print('GND hookups (exact):', gnd_hookup(board))
            pcbnew.ZONE_FILLER(board).Fill(board.Zones()); left = clusters(board)
        print(f'pass {it}: open nets {[board.GetNetInfo().GetNetItem(k).GetNetname() for k in left]}')
        if not left: break
    board.Save(PCB); sync_project(); print('saved', PCB)
    print('DRC:', drc_summary(board, os.path.join(KDIR, 'drc_routed.rpt')))

def reroute(prev_ses, passes=100):
    """second pass: start from a previous session's routes, let Freerouting finish the open connections"""
    board = base_board()
    print('previous routes:', import_ses(board, prev_ses))
    dsn = os.path.join(KDIR, 'SafeBuck-80.dsn'); ses = os.path.join(KDIR, 'SafeBuck-80.ses')
    pcbnew.ExportSpecctraDSN(board, dsn); print('DSN keepouts:', tune_dsn(board, dsn))
    if os.path.exists(ses): os.remove(ses)
    print('freerouting ok:', run_freerouting(dsn, ses, passes))
    board = base_board()
    print('imported tracks/vias:', import_ses(board, ses))
    finish(board)

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'route'      # check | dsn | route | import | reroute
    if mode == 'reroute':
        reroute(sys.argv[2]); sys.exit(0)
    if mode == 'complete':                     # import a session, finish the open links, fill, DRC
        from complete_routes import complete
        board = base_board()
        rip = sys.argv[3].split(',') if len(sys.argv) > 3 else []
        print('imported tracks/vias:', import_ses(board, sys.argv[2], set(rip)), 'ripped:', rip)
        print('fan-out stubs added, ripped nets:', apply_fanout(board))
        add_top_pour(board)                    # GND pads count as connected when the top pour reaches them
        for line in complete(board, [(n, r) for n, (p_, r) in ZONES.items()], OX, OY, W, H, skip=('GND',), rippable=('GND',), order=rip + ['LSP', 'LSN', 'CSRC', 'ISP_K', 'ISN_K']):
            print('  ', line)
        finish(board); sys.exit(0)
    board = pcbnew.LoadBoard(PLACED)
    bad = check_zones(board)
    print('zone conflicts:', len(bad)); [print('   ', b) for b in bad]
    if mode == 'check': sys.exit(1 if bad else 0)
    for net, (prio, rects) in ZONES.items():
        add_zone(board, net, pcbnew.F_Cu, poly_from_rects(rects), prio, name=f'{net}_top')
    full = poly_from_rects([(0.3, 0.3, W - 0.3, H - 0.3)])
    add_zone(board, 'GND', pcbnew.B_Cu, full, 0, connection='tht', name='GND_bottom')
    dsn = os.path.join(KDIR, 'SafeBuck-80.dsn'); ses = os.path.join(KDIR, 'SafeBuck-80.ses')
    if mode in ('dsn', 'route'):
        pcbnew.ExportSpecctraDSN(board, dsn)
        print('DSN keepouts:', tune_dsn(board, dsn))
    if mode == 'dsn':
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        board.Save(PLACED.replace('_placed', '_zones')); sys.exit(0)
    if mode == 'route':
        if os.path.exists(ses): os.remove(ses)
        print('freerouting ok:', run_freerouting(dsn, ses))
    print('imported tracks/vias:', import_ses(board, ses))
    add_zone(board, 'GND', pcbnew.F_Cu, full, 1, connection='tht', name='GND_top_fill')
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print('stitching vias:', stitch_gnd(board))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB); print('saved', PCB)
    print('DRC:', drc_summary(board, os.path.join(KDIR, 'drc_routed.rpt')))
