"""
Route SafeBuck-80 (2-layer, 2 oz):
  1. power copper as F.Cu zones (each zone = union of rectangles, checked against foreign pads)
  2. hot-loop GND returns as F.Cu GND zones, full GND plane on B.Cu
  3. Freerouting (Specctra DSN/SES) for every remaining connection
  4. F.Cu GND fill, GND stitching vias, zone fill, DRC
Run with KiCad's python after build_pcb.py:   /usr/bin/python3 route.py [check|dsn|route]
"""
import os, sys, re, subprocess, collections
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

def import_ses(board, path):
    """add Freerouting's wires and vias from a Specctra session file (KiCad 7's python
    ImportSpecctraSES() only works inside the GUI). SES units: 1/res um, y axis up."""
    from make_schematic import parse, find
    root = parse(open(path).read())[0]
    routes = find(root, 'routes')[0]
    res = float(find(routes, 'resolution')[0][2])
    nm = 1000.0 / res
    ntr = nvia = 0
    for net in find(find(routes, 'network_out')[0], 'net'):
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

def setup_rules(board):
    ds = board.GetDesignSettings()
    ns = ds.m_NetSettings
    dflt = ns.m_DefaultNetClass
    dflt.SetClearance(mm(0.2)); dflt.SetTrackWidth(mm(0.25)); dflt.SetViaDiameter(mm(0.7)); dflt.SetViaDrill(mm(0.35))
    pw = pcbnew.NETCLASS('POWER')
    pw.SetClearance(mm(0.25)); pw.SetTrackWidth(mm(0.8)); pw.SetViaDiameter(mm(0.8)); pw.SetViaDrill(mm(0.4))
    ns.m_NetClasses['POWER'] = pw
    for n in ('VIN_RAW', 'VIN_F', 'CSRC', 'VIN_P', 'SW1', 'SWL', 'SW2', 'VOUT_C', 'OUTF', 'OUTP', 'OUTN', 'GND'):
        ns.m_NetClassPatternAssignments.push_back(pcbnew.NETCLASS_PATTERN_ASSIGNMENT(n, 'POWER')) if hasattr(pcbnew, 'NETCLASS_PATTERN_ASSIGNMENT') else None

def base_board():
    """placed board + power zones + bottom GND plane (no tracks)"""
    board = pcbnew.LoadBoard(PLACED)
    for net, (prio, rects) in ZONES.items():
        add_zone(board, net, pcbnew.F_Cu, poly_from_rects(rects), prio, name=f'{net}_top')
    add_zone(board, 'GND', pcbnew.B_Cu, poly_from_rects([(0.3, 0.3, W - 0.3, H - 0.3)]), 0, connection='tht', name='GND_bottom')
    return board

def finish(board):
    full = poly_from_rects([(0.3, 0.3, W - 0.3, H - 0.3)])
    add_zone(board, 'GND', pcbnew.F_Cu, full, 1, connection='tht', name='GND_top_fill')
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print('stitching vias:', stitch_gnd(board))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB); print('saved', PCB)
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
    if mode == 'ripup':                        # session + rip-up-and-reroute completion -> final board
        import ripup_router as rr
        board = base_board()
        pads = []
        for fp in board.GetFootprints():
            for p_ in fp.Pads():
                bb = p_.GetBoundingBox()
                lay = [L for L, l in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if p_.IsOnLayer(l)]
                pads.append((p_.GetNetname(), f'{fp.GetReference()}.{p_.GetNumber()}',
                             (bb.GetX() / 1e6, bb.GetY() / 1e6, (bb.GetX() + bb.GetWidth()) / 1e6, (bb.GetY() + bb.GetHeight()) / 1e6),
                             lay, (p_.GetPosition().x / 1e6, p_.GetPosition().y / 1e6), p_.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH))
        zones = {n: [(OX + a, OY + b, OX + c, OY + d) for (a, b, c, d) in r] for n, (p_, r) in ZONES.items()}
        T, V = rr.parse_ses(sys.argv[2])
        print('session tracks/vias:', len(T), len(V))
        T, V, failed = rr.route_all(pads, zones, (OX, OY, OX + W, OY + H), T, V)
        print('not routed:', sorted(failed))
        for net, L, ax, ay, bx, by, wd, _ in T:
            tr = pcbnew.PCB_TRACK(board); tr.SetStart(pcbnew.VECTOR2I(mm(ax), mm(ay))); tr.SetEnd(pcbnew.VECTOR2I(mm(bx), mm(by)))
            tr.SetWidth(mm(wd)); tr.SetLayer(pcbnew.F_Cu if L == 0 else pcbnew.B_Cu); tr.SetNet(board.FindNet(net)); board.Add(tr)
        for net, x, y, d, _ in V:
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(d)); v.SetDrill(mm(0.35))
            v.SetNet(board.FindNet(net)); v.SetViaType(pcbnew.VIATYPE_THROUGH); board.Add(v)
        finish(board); sys.exit(0)
    if mode == 'complete':                     # import a session, finish the open links, fill, DRC
        from complete_routes import complete
        board = base_board()
        print('imported tracks/vias:', import_ses(board, sys.argv[2]))
        for line in complete(board, [(n, r) for n, (p_, r) in ZONES.items()], OX, OY, W, H): print('  ', line)
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
