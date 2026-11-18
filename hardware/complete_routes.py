"""
Finish the connections Freerouting leaves open (route.py calls complete(board) after importing the session).

1. connectivity: union-find over pads, tracks, vias and filled zone islands of every net -> open clusters
2. for each open link: two-layer grid A* (0.1 mm grid, vias allowed) that keeps the JLC 2 oz rules
   (0.20 mm track, 0.205 mm gap) against every other net; GND clusters may also end on a via into
   the bottom GND plane
3. a link that cannot be routed is searched again with other nets' tracks passable at a cost; the
   tracks it crosses are ripped up and re-routed in the next round (nets routed that way are then
   protected, so two nets cannot keep ripping each other)
4. leftovers of ripped nets (floating pieces, dead-end stubs) are deleted

Runs inside KiCad's python (pcbnew). Pure python + heapq, no extra packages.
"""
import math, heapq
import pcbnew

G = 0.05                        # grid pitch, mm (0.5 mm pitch pads sit on 0.05 mm offsets)
TW, CL = 0.20, 0.205             # new track width, clearance (mm)
VIA_D, VIA_DR = 0.6, 0.3
NM = 1e6

def mm(v): return int(round(v * NM))

class Grid:
    def __init__(self, x0, y0, w, h):
        self.x0, self.y0 = x0, y0
        self.nx, self.ny = int(w / G) + 1, int(h / G) + 1
        self.c = [bytearray(self.nx * self.ny), bytearray(self.nx * self.ny)]   # per layer: 0 free, 255 blocked
        self.owner = [dict(), dict()]                                         # cell -> net code (single owner)

    def idx(self, i, j): return j * self.nx + i
    def cell(self, x, y): return int(round((x - self.x0) / G)), int(round((y - self.y0) / G))

    def mark_seg(self, L, net, ax, ay, bx, by, r):
        """block cells within r of segment a-b for every net except `net` (net=None: block for all)"""
        i0, j0 = self.cell(min(ax, bx) - r, min(ay, by) - r)
        i1, j1 = self.cell(max(ax, bx) + r, max(ay, by) + r)
        dx, dy = bx - ax, by - ay; ll = dx * dx + dy * dy
        c, own = self.c[L], self.owner[L]
        for j in range(max(0, j0), min(self.ny, j1 + 1)):
            y = self.y0 + j * G
            for i in range(max(0, i0), min(self.nx, i1 + 1)):
                x = self.x0 + i * G
                t = 0.0 if ll == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ll))
                px, py = ax + t * dx - x, ay + t * dy - y
                if px * px + py * py <= r * r:
                    k = j * self.nx + i
                    if net is None or c[k] == 255:
                        c[k] = 255; own.pop(k, None)
                    elif c[k] == 0:
                        c[k] = 1; own[k] = net
                    elif own.get(k) != net:
                        c[k] = 255; own.pop(k, None)

    def mark_rect(self, L, net, x0, y0, x1, y1, r):
        i0, j0 = self.cell(x0 - r, y0 - r); i1, j1 = self.cell(x1 + r, y1 + r)
        c, own = self.c[L], self.owner[L]
        for j in range(max(0, j0), min(self.ny, j1 + 1)):
            for i in range(max(0, i0), min(self.nx, i1 + 1)):
                k = j * self.nx + i
                if net is None or c[k] == 255:
                    c[k] = 255; own.pop(k, None)
                elif c[k] == 0:
                    c[k] = 1; own[k] = net
                elif own.get(k) != net:
                    c[k] = 255; own.pop(k, None)

    def block_rect_except(self, L, x0, y0, x1, y1, r, ex):
        """block (for every net) cells within r of the rect, except cells inside rect ex"""
        i0, j0 = self.cell(x0 - r, y0 - r); i1, j1 = self.cell(x1 + r, y1 + r)
        c, own = self.c[L], self.owner[L]
        for j in range(max(0, j0), min(self.ny, j1 + 1)):
            y = self.y0 + j * G
            for i in range(max(0, i0), min(self.nx, i1 + 1)):
                x = self.x0 + i * G
                if ex[0] - 1e-6 <= x <= ex[2] + 1e-6 and ex[1] - 1e-6 <= y <= ex[3] + 1e-6: continue
                k = j * self.nx + i; c[k] = 255; own.pop(k, None)

    def free(self, L, net, i, j):
        if not (0 <= i < self.nx and 0 <= j < self.ny): return False
        k = j * self.nx + i; v = self.c[L][k]
        return v == 0 or (v == 1 and self.owner[L].get(k) == net)

MARGIN = 0.04                   # covers the grid discretisation (half a cell diagonal = 0.035 mm)
TIE_DST = {}                    # 'NT1.1' -> rect (mm) where a Kelvin track may end inside the net-tie pad

def tie_geometry(fp):
    """Net-tie footprint: a copper bar runs from the centre of pad 2 to the centre of pad 1. KiCad's DRC only
    lets a track touch that bar inside the pad, so a Kelvin track must enter pad 1 from its far side.
    Returns (bar rect, end rect inside pad 1, corridor rect leading away from the bar), all in mm."""
    p1 = [p for p in fp.Pads() if p.GetNumber() == '1'][0]
    cx, cy = p1.GetPosition().x / NM, p1.GetPosition().y / NM
    bb = p1.GetBoundingBox(); hx, hy = bb.GetWidth() / NM / 2, bb.GetHeight() / NM / 2
    bars = [it.GetBoundingBox() for it in fp.GraphicalItems() if it.GetLayer() == pcbnew.F_Cu]
    bx0 = min(b.GetX() for b in bars) / NM; by0 = min(b.GetY() for b in bars) / NM
    bx1 = max(b.GetX() + b.GetWidth() for b in bars) / NM; by1 = max(b.GetY() + b.GetHeight() for b in bars) / NM
    m = TW / 2                                         # track copper must not reach the bar
    if abs(cx - (bx0 + bx1) / 2) >= abs(cy - (by0 + by1) / 2):
        s = 1 if cx > (bx0 + bx1) / 2 else -1
        a0, a1 = sorted((cx + s * m, cx + s * (hx - m)))
        end = (a0, cy - (hy - m), a1, cy + (hy - m))
        cor = (min(a0, a1 + s * 1.2), end[1], max(a1, a0 + s * 1.2), end[3])
    else:
        s = 1 if cy > (by0 + by1) / 2 else -1
        a0, a1 = sorted((cy + s * m, cy + s * (hy - m)))
        end = (cx - (hx - m), a0, cx + (hx - m), a1)
        cor = (end[0], min(a0, a1 + s * 1.2), end[2], max(a1, a0 + s * 1.2))
    return (bx0, by0, bx1, by1), end, cor

FINE = ('U1', 'U2')              # fine-pitch ICs: keep vias back from their pin rows so neighbours can escape
VIA_KEEP, VIA_PEN = 0.85, 1000.0 # mm from a pin, extra cost of a via there (a last resort only)

def via_penalty_map(board, g):
    pen = bytearray(g.nx * g.ny)
    for fp in board.GetFootprints():
        if fp.GetReference() not in FINE: continue
        for p in fp.Pads():
            if not p.GetNumber() or p.GetNumber() in ('29', '25'): continue      # exposed pads are not pin rows
            bb = p.GetBoundingBox()
            x0, y0 = bb.GetX() / NM, bb.GetY() / NM; x1, y1 = x0 + bb.GetWidth() / NM, y0 + bb.GetHeight() / NM
            i0, j0 = g.cell(x0 - VIA_KEEP, y0 - VIA_KEEP); i1, j1 = g.cell(x1 + VIA_KEEP, y1 + VIA_KEEP)
            for j in range(max(0, j0), min(g.ny, j1 + 1)):
                y = g.y0 + j * G; dy = max(y0 - y, 0, y - y1)
                for i in range(max(0, i0), min(g.nx, i1 + 1)):
                    x = g.x0 + i * G; dx = max(x0 - x, 0, x - x1)
                    if dx * dx + dy * dy <= VIA_KEEP * VIA_KEEP: pen[j * g.nx + i] = 1
    return pen

def build_grid(board, zones, ox, oy, W, H, tracks=True, hard_nets=()):
    g = Grid(ox, oy, W, H)
    r_tr = CL + TW / 2 + MARGIN
    edge = 0.3 + TW / 2
    for L in (0, 1):                                   # board edge
        g.mark_rect(L, None, ox - 1, oy - 1, ox + W + 1, oy + edge, 0)
        g.mark_rect(L, None, ox - 1, oy + H - edge, ox + W + 1, oy + H + 1, 0)
        g.mark_rect(L, None, ox - 1, oy - 1, ox + edge, oy + H + 1, 0)
        g.mark_rect(L, None, ox + W - edge, oy - 1, ox + W + 1, oy + H + 1, 0)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            x0, y0 = bb.GetX() / NM, bb.GetY() / NM
            x1, y1 = x0 + bb.GetWidth() / NM, y0 + bb.GetHeight() / NM
            net = p.GetNetCode() or None
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                for L in (0, 1): g.mark_rect(L, None, x0, y0, x1, y1, 0.3 + TW / 2)
                continue
            for L, lay in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
                if p.IsOnLayer(lay): g.mark_rect(L, net, x0, y0, x1, y1, r_tr)
    for fp in board.GetFootprints():                   # net-tie bars: keep-out for every net, except the corridor
        if fp.GetReference().startswith('NT'):          # into the far side of the Kelvin pad
            bar, end, cor = tie_geometry(fp)
            TIE_DST[fp.GetReference() + '.1'] = end
            g.block_rect_except(0, *bar, r_tr, cor)
    for t in board.GetTracks():
        net = t.GetNetCode() or None
        if not tracks and t.GetNetname() not in hard_nets: continue
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition(); r = t.GetWidth() / NM / 2 + r_tr
            for L in (0, 1): g.mark_seg(L, net, p.x / NM, p.y / NM, p.x / NM, p.y / NM, r)
        else:
            L = 0 if t.GetLayer() == pcbnew.F_Cu else 1
            s, e = t.GetStart(), t.GetEnd()
            g.mark_seg(L, net, s.x / NM, s.y / NM, e.x / NM, e.y / NM, t.GetWidth() / NM / 2 + r_tr)
    for netname, rects in zones:                       # fixed power copper on the top layer
        net = board.FindNet(netname).GetNetCode()
        for (x0, y0, x1, y1) in rects:
            g.mark_rect(0, net, ox + x0, oy + y0, ox + x1, oy + y1, r_tr)
    return g

# ---------------------------------------------------------------- connectivity (union-find)
def clusters(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    items = {}                                       # net -> list of (kind, data)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if not p.GetNetCode(): continue
            bb = p.GetBoundingBox()
            lay = [L for L, l in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if p.IsOnLayer(l)]
            items.setdefault(p.GetNetCode(), []).append(('pad', (bb.GetX(), bb.GetY(), bb.GetX() + bb.GetWidth(), bb.GetY() + bb.GetHeight()), lay,
                                                         (p.GetPosition().x, p.GetPosition().y), f'{fp.GetReference()}.{p.GetNumber()}'))
    for t in board.GetTracks():
        if not t.GetNetCode(): continue
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition()
            items.setdefault(t.GetNetCode(), []).append(('via', (p.x, p.y), [0, 1], t.GetWidth() // 2, t))
        else:
            L = 0 if t.GetLayer() == pcbnew.F_Cu else 1
            items.setdefault(t.GetNetCode(), []).append(('trk', (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y), [L], t.GetWidth() // 2, t))
    fills = {}
    for z in board.Zones():
        for L, lay in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
            if z.IsOnLayer(lay) and z.GetNetCode():
                fl = z.GetFilledPolysList(lay)
                for k in range(fl.OutlineCount()):              # every island is its own node
                    isl = pcbnew.SHAPE_POLY_SET(); isl.AddOutline(fl.COutline(k))
                    for h in range(fl.HoleCount(k)): isl.AddHole(fl.CHole(k, h))
                    fills.setdefault(z.GetNetCode(), []).append((L, isl))
    out = {}
    for net, its in items.items():
        n = len(its); par = list(range(n + len(fills.get(net, []))))
        def f(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        def u(a, b): par[f(a)] = f(b)
        def pts(it):
            k = it[0]
            if k == 'pad':
                x0, y0, x1, y1 = it[1]; cx, cy = it[3]
                return [(cx, cy), ((x0 + x1) // 2, y0 - 150000), ((x0 + x1) // 2, y1 + 150000), (x0 - 150000, (y0 + y1) // 2), (x1 + 150000, (y0 + y1) // 2)]
            if k == 'via': return [it[1]]
            return [(it[1][0], it[1][1]), (it[1][2], it[1][3])]
        def touch(a, b):
            if not set(a[2]) & set(b[2]): return False
            for (x, y) in pts(a)[:1] + (pts(a)[1:] if a[0] == 'trk' else []):
                if near(b, x, y): return True
            for (x, y) in pts(b)[:1] + (pts(b)[1:] if b[0] == 'trk' else []):
                if near(a, x, y): return True
            if a[0] == 'pad' and b[0] == 'pad':
                A, B = a[1], b[1]
                return A[0] <= B[2] and B[0] <= A[2] and A[1] <= B[3] and B[1] <= A[3]
            return False
        def near(it, x, y):
            k = it[0]
            if k == 'pad':
                x0, y0, x1, y1 = it[1]; return x0 - 20000 <= x <= x1 + 20000 and y0 - 20000 <= y <= y1 + 20000
            if k == 'via':
                return (x - it[1][0]) ** 2 + (y - it[1][1]) ** 2 <= (it[3] + 20000) ** 2
            ax, ay, bx, by = it[1]; dx, dy = bx - ax, by - ay; ll = dx * dx + dy * dy
            t = 0 if ll == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / ll))
            return (ax + t * dx - x) ** 2 + (ay + t * dy - y) ** 2 <= (it[3] + 20000) ** 2
        for a in range(n):
            for b in range(a + 1, n):
                if touch(its[a], its[b]): u(a, b)
        for zi, (L, poly) in enumerate(fills.get(net, [])):
            for a in range(n):
                if L in its[a][2] and any(poly.Contains(pcbnew.VECTOR2I(int(x), int(y))) for (x, y) in pts(its[a])):
                    u(a, n + zi)
        groups = {}
        for a in range(n): groups.setdefault(f(a), []).append(its[a])
        if len(groups) > 1: out[net] = list(groups.values())
    return out

# ---------------------------------------------------------------- routing
def simplify(path):
    if len(path) < 3: return path
    out = [path[0]]
    for k in range(1, len(path) - 1):
        a, b, c = out[-1], path[k], path[k + 1]
        if (b[0] - a[0]) * (c[1] - b[1]) != (b[1] - a[1]) * (c[0] - b[0]): out.append(b)
    out.append(path[-1]); return out

def add_track(board, net, L, ax, ay, bx, by):
    t = pcbnew.PCB_TRACK(board); t.SetStart(pcbnew.VECTOR2I(mm(ax), mm(ay))); t.SetEnd(pcbnew.VECTOR2I(mm(bx), mm(by)))
    t.SetWidth(mm(TW)); t.SetLayer(pcbnew.F_Cu if L == 0 else pcbnew.B_Cu); t.SetNet(net); board.Add(t)
    return t.m_Uuid.AsString()

def add_via(board, net, x, y):
    v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DR))
    v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH); board.Add(v)
    return v.m_Uuid.AsString()

def snapshot(t):
    """enough of a track/via to put it back after a rollback"""
    if t.GetClass() == 'PCB_VIA':
        return ('via', t.GetNetCode(), t.GetPosition().x, t.GetPosition().y, t.GetWidth(), t.GetDrillValue())
    return ('trk', t.GetNetCode(), t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth())

def restore(board, saved):
    for s in saved:
        ni = board.GetNetInfo().GetNetItem(s[1])
        if s[0] == 'via':
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(s[2], s[3])); v.SetWidth(s[4]); v.SetDrill(s[5])
            v.SetNet(ni); v.SetViaType(pcbnew.VIATYPE_THROUGH); board.Add(v)
        else:
            t = pcbnew.PCB_TRACK(board); t.SetLayer(s[2]); t.SetStart(pcbnew.VECTOR2I(s[3], s[4])); t.SetEnd(pcbnew.VECTOR2I(s[5], s[6]))
            t.SetWidth(s[7]); t.SetNet(ni); board.Add(t)

def remove_ids(board, ids):
    ids = set(ids)
    for t in [t for t in board.GetTracks() if t.m_Uuid.AsString() in ids]: board.Remove(t)

def item_cells(g, it, zones_by_net=None):
    """grid cells (layer, i, j) covered by a cluster item"""
    k, out = it[0], []
    if k == 'pad' and it[4] in TIE_DST:
        x0, y0, x1, y1 = TIE_DST[it[4]]
        I = range(int(math.ceil((x0 - g.x0) / G - 1e-6)), int(math.floor((x1 - g.x0) / G + 1e-6)) + 1)
        J = range(int(math.ceil((y0 - g.y0) / G - 1e-6)), int(math.floor((y1 - g.y0) / G + 1e-6)) + 1)
        if not len(I): I = [g.cell((x0 + x1) / 2, 0)[0]]
        if not len(J): J = [g.cell(0, (y0 + y1) / 2)[1]]
        return [(0, i, j) for i in I for j in J]
    if k == 'pad':
        x0, y0, x1, y1 = (v / NM for v in it[1])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x0, x1 = min(cx, x0 + 0.12), max(cx, x1 - 0.12); y0, y1 = min(cy, y0 + 0.12), max(cy, y1 - 0.12)
        i0, j0 = g.cell(x0, y0); i1, j1 = g.cell(x1, y1)
        i0, j0 = int(math.ceil((x0 - g.x0) / G)), int(math.ceil((y0 - g.y0) / G))
        i1, j1 = int(math.floor((x1 - g.x0) / G)), int(math.floor((y1 - g.y0) / G))
        if i1 < i0: i0 = i1 = g.cell(cx, cy)[0]
        if j1 < j0: j0 = j1 = g.cell(cx, cy)[1]
        for L in it[2]:
            out += [(L, i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]
    elif k == 'via':
        i, j = g.cell(it[1][0] / NM, it[1][1] / NM); out += [(0, i, j), (1, i, j)]
    else:
        ax, ay, bx, by = (v / NM for v in it[1]); n = int(max(abs(bx - ax), abs(by - ay)) / G) + 1
        out += [(it[2][0],) + g.cell(ax + (bx - ax) * s / n, ay + (by - ay) * s / n) for s in range(n + 1)]
    return out

def astar2(g, net, src, dst, via_cost=20.0, limit=6000000, vpen=None, max_cost=None):
    """two-layer grid search; src/dst = sets of (layer, i, j). Returns [(layer, i, j), ...]"""
    if not src or not dst: return None
    I = [c[1] for c in dst]; J = [c[2] for c in dst]
    bi0, bi1, bj0, bj1 = min(I), max(I), min(J), max(J)
    def h(i, j): return math.hypot(max(bi0 - i, 0, i - bi1), max(bj0 - j, 0, j - bj1))
    rv = (VIA_D / 2 - TW / 2) / G + 0.6
    R_ = int(math.ceil(rv))
    disk = [(a, b) for a in range(-R_, R_ + 1) for b in range(-R_, R_ + 1) if a * a + b * b <= rv * rv]
    def via_ok(i, j): return all(g.free(L, net, i + a, j + b) for L in (0, 1) for a, b in disk)
    best, prev, openh = {}, {}, []
    for s in src:
        best[s] = 0.0; heapq.heappush(openh, (h(s[1], s[2]), 0.0, s))
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    n = 0
    while openh:
        f, c, s = heapq.heappop(openh)
        if s in dst:
            path = [s]
            while s in prev: s = prev[s]; path.append(s)
            return path[::-1]
        if c > best.get(s, 1e18): continue
        if max_cost is not None and f > max_cost: return None        # only detours left
        n += 1
        if n > limit: return None
        L, i, j = s
        nbrs = []
        for di, dj, w in moves:
            q = (L, i + di, j + dj)
            if q in dst or q in src or g.free(L, net, i + di, j + dj): nbrs.append((q, w))
        if via_ok(i, j): nbrs.append(((1 - L, i, j), via_cost + (VIA_PEN if vpen and vpen[j * g.nx + i] else 0.0)))
        for q, w in nbrs:
            nc = c + w
            if nc < best.get(q, 1e18):
                best[q] = nc; prev[q] = s; heapq.heappush(openh, (nc + h(q[1], q[2]), nc, q))
    return None

def line_free(g, L, net, a, b):
    """the straight centre-line from cell a to cell b only crosses free cells (sampled every quarter cell;
    a point of the line is never more than half a cell diagonal from the cell it is checked against)"""
    (i0, j0), (i1, j1) = a, b
    n = int(max(abs(i1 - i0), abs(j1 - j0)) * 4) + 1
    for s in range(1, n):
        if not g.free(L, net, int(round(i0 + (i1 - i0) * s / n)), int(round(j0 + (j1 - j0) * s / n))): return False
    return True

def smooth(g, L, net, pts):
    """string pulling: replace grid staircases by the longest straight segments that keep the clearance"""
    if len(pts) < 3: return pts
    out, i = [pts[0]], 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not line_free(g, L, net, pts[i], pts[j]): j -= 1
        out.append(pts[j]); i = j
    return out

def emit(board, g, ni, net, path):
    """turn a cell path into tracks (per layer, collinear runs merged) and vias at layer changes"""
    runs, cur = [], [path[0]]
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            runs.append(cur); cur = [b]
        else:
            cur.append(b)
    runs.append(cur)
    nseg = nvia = 0; ids = []
    for r in runs:
        L = r[0][0]
        pts = smooth(g, L, net, simplify([(c[1], c[2]) for c in r]))
        xy = [(g.x0 + i * G, g.y0 + j * G) for i, j in pts]
        for (x0, y0), (x1, y1) in zip(xy, xy[1:]):
            ids.append(add_track(board, ni, L, x0, y0, x1, y1)); g.mark_seg(L, net, x0, y0, x1, y1, TW + CL + MARGIN); nseg += 1
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            x, y = g.x0 + a[1] * G, g.y0 + a[2] * G
            ids.append(add_via(board, ni, x, y)); nvia += 1
            for L in (0, 1): g.mark_seg(L, net, x, y, x, y, VIA_D / 2 + CL + TW / 2 + MARGIN)
    return nseg, nvia, ids

def astar_soft(gf, gh, net, src, dst, penalty=30.0, via_cost=20.0, limit=6000000, vpen=None):
    """like astar2, but cells blocked only by other nets' tracks (gf) are passable at a penalty;
    pads, zones, board edge and protected nets' tracks (gh) stay hard"""
    I = [c[1] for c in dst]; J = [c[2] for c in dst]
    bi0, bi1, bj0, bj1 = min(I), max(I), min(J), max(J)
    def h(i, j): return math.hypot(max(bi0 - i, 0, i - bi1), max(bj0 - j, 0, j - bj1))
    rv = (VIA_D / 2 - TW / 2) / G + 0.6; R_ = int(math.ceil(rv))
    disk = [(a, b) for a in range(-R_, R_ + 1) for b in range(-R_, R_ + 1) if a * a + b * b <= rv * rv]
    def cost(L, i, j):
        if (L, i, j) in src or (L, i, j) in dst: return 0.0
        if not gh.free(L, net, i, j): return None
        return 0.0 if gf.free(L, net, i, j) else penalty
    best, prev, openh = {}, {}, []
    for s_ in src: best[s_] = 0.0; heapq.heappush(openh, (h(s_[1], s_[2]), 0.0, s_))
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    n = 0
    while openh:
        f, c, s_ = heapq.heappop(openh)
        if s_ in dst:
            path = [s_]
            while s_ in prev: s_ = prev[s_]; path.append(s_)
            return path[::-1]
        if c > best.get(s_, 1e18): continue
        n += 1
        if n > limit: return None
        L, i, j = s_
        for di, dj, w in moves:
            e = cost(L, i + di, j + dj)
            if e is None: continue
            q = (L, i + di, j + dj); nc = c + w + e
            if nc < best.get(q, 1e18): best[q] = nc; prev[q] = s_; heapq.heappush(openh, (nc + h(q[1], q[2]), nc, q))
        vc, ok = 0.0, True
        for L2 in (0, 1):
            for a, b in disk:
                if not gh.free(L2, net, i + a, j + b): ok = False; break
                if not gf.free(L2, net, i + a, j + b): vc = penalty
            if not ok: break
        if ok:
            q = (1 - L, i, j); nc = c + via_cost + vc + (VIA_PEN if vpen and vpen[j * gh.nx + i] else 0.0)
            if nc < best.get(q, 1e18): best[q] = nc; prev[q] = s_; heapq.heappush(openh, (nc + h(i, j), nc, q))
    return None

def rip_along(board, g, net, path, protect=()):
    """remove other-net tracks/vias whose keep-out the path (or its vias) enters; returns their net names"""
    pts = [(L, g.x0 + i * G, g.y0 + j * G, TW / 2) for L, i, j in path]
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            pts += [(L, g.x0 + a[1] * G, g.y0 + a[2] * G, VIA_D / 2) for L in (0, 1)]
    ripped, kill = set(), []
    for t in board.GetTracks():
        if t.GetNetCode() == net or t.GetNetname() in protect: continue
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition(); segs = [((0, 1), p.x / NM, p.y / NM, p.x / NM, p.y / NM, t.GetWidth() / NM / 2)]
        else:
            L = 0 if t.GetLayer() == pcbnew.F_Cu else 1; s, e = t.GetStart(), t.GetEnd()
            segs = [((L,), s.x / NM, s.y / NM, e.x / NM, e.y / NM, t.GetWidth() / NM / 2)]
        for layers, ax, ay, bx, by, hw in segs:
            dx, dy = bx - ax, by - ay; ll = dx * dx + dy * dy; hit = False
            for (L, x, y, r) in pts:
                if L not in layers: continue
                tt = 0.0 if ll == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ll))
                if (ax + tt * dx - x) ** 2 + (ay + tt * dy - y) ** 2 <= (hw + r + CL + MARGIN) ** 2: hit = True; break
            if hit: kill.append(t); ripped.add(t.GetNetname()); break
    saved = [snapshot(t) for t in kill]
    for t in kill: board.Remove(t)
    return ripped, saved

def plane_cells(board, g, net, src, layer=pcbnew.B_Cu, L=1, win=3.0):
    """free grid cells inside the largest filled island of `net` on `layer`, within win mm of the source cells"""
    best, area = None, 0
    for z in board.Zones():
        if z.GetNetCode() != net or not z.IsOnLayer(layer): continue
        fl = z.GetFilledPolysList(layer)
        for k in range(fl.OutlineCount()):
            isl = pcbnew.SHAPE_POLY_SET(); isl.AddOutline(fl.COutline(k))
            for h in range(fl.HoleCount(k)): isl.AddHole(fl.CHole(k, h))
            a = isl.Area()
            if a > area: best, area = isl, a
    if best is None: return set()
    I = [c[1] for c in src]; J = [c[2] for c in src]; R = int(win / G)
    out = set()
    for j in range(min(J) - R, max(J) + R + 1, 2):
        for i in range(min(I) - R, max(I) + R + 1, 2):
            if g.free(L, net, i, j) and best.Contains(pcbnew.VECTOR2I(mm(g.x0 + i * G), mm(g.y0 + j * G))):
                out.add((L, i, j))
    return out

def remove_floating(board, open_):
    """delete groups of tracks/vias that reach no pad (pieces left over from a rip-up)"""
    n = 0
    for net, groups in open_.items():
        for grp in groups:
            if any(it[0] == 'pad' for it in grp): continue
            for it in grp:
                board.Remove(it[4]); n += 1
    return n

def prune_stubs(board):
    """Clean up dead ends with KiCad's own connectivity: a track end that KiCad calls dangling is pulled back to
    the farthest point where another item joins the segment (or the segment is deleted); a via connected on one
    layer only is deleted when the tracks it joins also touch each other without it."""
    removed = trimmed = 0
    def on(t, q): return t.HitTest(q, 0)
    for it in range(60):
        board.BuildConnectivity(); c = board.GetConnectivity()
        changed = False
        for t in [x for x in board.GetTracks() if x.GetClass() == 'PCB_TRACK']:
            pos = pcbnew.VECTOR2I(0, 0)
            if not c.TestTrackEndpointDangling(t, True, pos): continue
            s0, e0 = t.GetStart(), t.GetEnd()
            ds = (pos.x - s0.x) ** 2 + (pos.y - s0.y) ** 2 <= (pos.x - e0.x) ** 2 + (pos.y - e0.y) ** 2
            keep, dead = (e0, s0) if ds else (s0, e0)
            dx, dy = dead.x - keep.x, dead.y - keep.y; ll = dx * dx + dy * dy
            pts = []
            for o in list(c.GetConnectedTracks(t)) + list(c.GetConnectedPads(t)):
                if o.GetClass() == 'PCB_TRACK': pts += [o.GetStart(), o.GetEnd()]
                else: pts.append(o.GetPosition())
            best = None
            for q in pts:
                if not on(t, q): continue
                s_ = 0 if ll == 0 else ((q.x - keep.x) * dx + (q.y - keep.y) * dy) / ll
                if 0.02 < s_ < 0.98 and (best is None or s_ > best): best = s_
            if best is None:
                board.Remove(t); removed += 1
            else:
                (t.SetStart if ds else t.SetEnd)(pcbnew.VECTOR2I(int(keep.x + dx * best), int(keep.y + dy * best))); trimmed += 1
            changed = True
            break                                          # connectivity changed: rebuild it
        if changed: continue
        zones = [z for z in board.Zones() if z.GetNetCode() and not z.GetIsRuleArea()]
        for v in [x for x in board.GetTracks() if x.GetClass() == 'PCB_VIA']:
            q = v.GetPosition()
            conn = list(c.GetConnectedTracks(v)) + list(c.GetConnectedPads(v))
            zl = {L for z in zones if z.GetNetCode() == v.GetNetCode() for L in (pcbnew.F_Cu, pcbnew.B_Cu)
                  if z.IsOnLayer(L) and z.HitTestFilledArea(L, q)}
            lays = set(zl)
            for o in conn:
                if o.GetClass() in ('PCB_TRACK', 'PCB_ARC'): lays.add(o.GetLayer())
                else: lays |= {L for L in (pcbnew.F_Cu, pcbnew.B_Cu) if o.IsOnLayer(L)}
            if len(lays) >= 2: continue
            if not conn:                                   # touches nothing, or one pour on one side only
                board.Remove(v); removed += 1; changed = True; break
            if len(conn) == 1 and not zl:
                board.Remove(v); removed += 1; changed = True; break
            if not zl and all(o.GetClass() == 'PCB_TRACK' for o in conn):
                ts = conn; par = list(range(len(ts)))
                def f(a):
                    while par[a] != a: a = par[a]
                    return a
                for i in range(len(ts)):
                    for j in range(i + 1, len(ts)):
                        if any(on(ts[j], q) for q in (ts[i].GetStart(), ts[i].GetEnd())) or \
                           any(on(ts[i], q) for q in (ts[j].GetStart(), ts[j].GetEnd())): par[f(i)] = f(j)
                if len({f(i) for i in range(len(ts))}) == 1:
                    board.Remove(v); removed += 1; changed = True; break
        if not changed: break
    return removed, trimmed

BLOCKED = {}                    # nets a ripper must keep off after a rollback (kept across complete() calls)
NO_RIP = {'TG1', 'TG2', 'BG1', 'BG2', 'BST1', 'BST2', 'SW1', 'SW2'}   # gate drive / switch node: not ripped for GND

def detour_limit(src, dst, k=4.0, extra=15.0):
    """cost cap for a route: k x the gap between the two clusters + extra mm + two vias. A longer way round is worse
    than ripping up a signal track (a 97 mm gate-drive loop once wrecked the GND plane under the buck stage)."""
    I = [c[1] for c in dst]; J = [c[2] for c in dst]
    gap = min(math.hypot(max(min(I) - c[1], 0, c[1] - max(I)), max(min(J) - c[2], 0, c[2] - max(J))) for c in src)
    return k * gap + extra / G + 40.0

def complete(board, zones, ox, oy, W, H, skip=(), rippable=(), only=None, order=(), rounds=14, rip=True, no_rip=(), cap=False):
    """skip: nets not routed here; rippable: skipped nets whose tracks may still be ripped up;
    only: route just these nets; rip: allow rip-up. GND targets are the filled GND planes (top pour, bottom plane).
    A rip-up is a transaction: the ripped nets must route again normally in the next round (they may not rip
    anything themselves); if one cannot, the rip-up is rolled back and the ripping net tries again with those
    nets' tracks kept hard. no_rip: nets that may never be ripped up; cap: refuse very long normal routes."""
    log = []
    zr = {n: r for n, r in zones}
    rank = {n: k for k, n in enumerate(order)}
    protect = (set(skip) - set(rippable)) | set(no_rip)   # nets whose tracks may not be ripped up
    tx, blocked, tries = None, BLOCKED, {}
    for rnd in range(rounds):
        open_ = clusters(board)
        nf = remove_floating(board, open_)
        if nf:
            log.append(f'r{rnd}: removed {nf} floating track/via pieces'); open_ = clusters(board)
        g = build_grid(board, zones, ox, oy, W, H)
        if rnd == 0: vpen = via_penalty_map(board, g)
        failed = []
        def prio(kv):                                  # GND last: later tracks would cut into its plane targets
            nm = board.GetNetInfo().GetNetItem(kv[0]).GetNetname()
            return (nm == 'GND', rank.get(nm, len(rank)), kv[0])
        for net, groups in sorted(open_.items(), key=prio):
            ni = board.GetNetInfo().GetNetItem(net); name = ni.GetNetname()
            if (only is not None and name not in only) or (only is None and name in skip): continue
            if tx and name not in tx['victims']: continue  # while a rip-up is on trial only its victims route
            groups.sort(key=len, reverse=True)
            main = groups[0]
            for grp in groups[1:]:
                src = {c for it in grp for c in item_cells(g, it)}
                dst = {c for it in main for c in item_cells(g, it)}
                for (x0, y0, x1, y1) in (zr.get(name, []) if name != 'GND' else []):
                    i0, j0 = g.cell(ox + x0 + 0.3, oy + y0 + 0.3); i1, j1 = g.cell(ox + x1 - 0.3, oy + y1 - 0.3)
                    dst |= {(0, i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)}
                if name == 'GND':                              # a via into the bottom plane, or the top pour, will do
                    dst |= plane_cells(board, g, net, src, win=5.0) | plane_cells(board, g, net, src, pcbnew.F_Cu, 0, win=5.0)
                dst -= src
                mc = detour_limit(src, dst) if cap and name != 'GND' else None
                path = astar2(g, net, src, dst, vpen=vpen, max_cost=mc)
                if path:
                    nseg, nvia, ids = emit(board, g, ni, net, path)
                    if tx and name in tx['victims']: tx['vids'] += ids
                    log.append(f'r{rnd} {name}: routed ({nseg} segments, {nvia} vias)')
                    main = main + grp
                else:
                    failed.append((net, ni, name, src, dst))
        if tx:
            vfail = sorted({f[2] for f in failed if f[2] in tx['victims']})
            if vfail:                                      # roll the rip-up back
                remove_ids(board, tx['ids'] + tx['vids']); restore(board, tx['saved'])
                protect.discard(tx['ripper']); blocked.setdefault(tx['ripper'], set()).update(vfail)
                log.append(f"r{rnd} rollback: {vfail} could not be re-routed; {tx['ripper']} will keep off them")
                tx = None
                continue
            log.append(f"r{rnd} rip-up by {tx['ripper']} kept"); tx = None
            continue                                       # the other nets waited this round: re-plan them
        if not failed: break
        if not rip:
            log += [f'r{rnd} {f[2]}: NOT routed' for f in failed]; break
        for net, ni, name, src, dst in failed:
            if tries.get(name, 0) >= 8: continue
            tries[name] = tries.get(name, 0) + 1
            hard = protect | blocked.get(name, set())
            gh = build_grid(board, zones, ox, oy, W, H, tracks=False, hard_nets=tuple(hard))
            path = astar_soft(g, gh, net, src, dst, vpen=vpen)
            if not path:
                log.append(f'r{rnd} {name}: NOT routed even with rip-up'); continue
            ripped, saved = rip_along(board, g, net, path, protect=hard)
            g = build_grid(board, zones, ox, oy, W, H)
            _, _, ids = emit(board, g, ni, net, path)
            protect.add(name)
            tx = dict(ripper=name, ids=ids, victims=set(ripped), saved=saved, vids=[])
            log.append(f'r{rnd} {name}: routed by ripping up {sorted(ripped)} (re-routed next round)')
            break                                          # re-plan after every rip-up
    return log
