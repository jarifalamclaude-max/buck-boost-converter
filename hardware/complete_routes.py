"""
Finish the connections Freerouting leaves open (route.py calls complete(board) after importing the session).

1. connectivity: union-find over pads, tracks, vias and filled zones of every net -> open clusters
2. for each open link: drop a via next to a pad of each cluster (short top-layer stub), then
   route between the two vias on the bottom layer with a grid A* (0.1 mm grid) that keeps the
   track/clearance rules (0.25 mm track, 0.21 mm gap) against every other net
3. new copper is marked in the grids so later routes avoid it

Runs inside KiCad's python (pcbnew). Pure python + heapq, no extra packages.
"""
import math, heapq
import pcbnew

G = 0.1                         # grid pitch, mm
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

    def free(self, L, net, i, j):
        if not (0 <= i < self.nx and 0 <= j < self.ny): return False
        k = j * self.nx + i; v = self.c[L][k]
        return v == 0 or (v == 1 and self.owner[L].get(k) == net)

def build_grid(board, zones, ox, oy, W, H):
    g = Grid(ox, oy, W, H)
    r_tr = CL + TW / 2
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
    for t in board.GetTracks():
        net = t.GetNetCode() or None
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
            items.setdefault(t.GetNetCode(), []).append(('via', (p.x, p.y), [0, 1], t.GetWidth() // 2, None))
        else:
            L = 0 if t.GetLayer() == pcbnew.F_Cu else 1
            items.setdefault(t.GetNetCode(), []).append(('trk', (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y), [L], t.GetWidth() // 2, None))
    fills = {}
    for z in board.Zones():
        for L, lay in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
            if z.IsOnLayer(lay) and z.GetNetCode():
                fills.setdefault(z.GetNetCode(), []).append((L, z.GetFilledPolysList(lay)))
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
def via_sites(g, net, px, py, rmax=2.6, bbox=None):
    """via positions near (px, py) reachable by a straight top-layer stub, sorted by distance.
    Cells inside the anchor pad (bbox, mm) are its own copper and are not checked."""
    pi, pj = g.cell(px, py); out = []
    def inpad(i, j, m=0.0):
        if not bbox: return False
        x, y = g.x0 + i * G, g.y0 + j * G
        return bbox[0] - m <= x <= bbox[2] + m and bbox[1] - m <= y <= bbox[3] + m
    rv = int(math.ceil((VIA_D / 2 - TW / 2) / G))
    R = int(rmax / G)
    for dj in range(-R, R + 1):
        for di in range(-R, R + 1):
            d = math.hypot(di, dj)
            if d < 3 or d > R: continue
            i, j = pi + di, pj + dj
            if inpad(i, j, VIA_D / 2 + 0.05): continue                     # no via in / touching the pad
            ok = all(g.free(L, net, i + a, j + b) for L in (0, 1) for a in range(-rv, rv + 1) for b in range(-rv, rv + 1) if a * a + b * b <= rv * rv)
            if not ok: continue
            steps = int(d) + 1                          # stub clear on the top layer
            cells = [(int(round(pi + di * s / steps)), int(round(pj + dj * s / steps))) for s in range(steps + 1)]
            if all(inpad(a, b) or g.free(0, net, a, b) for a, b in cells[1:]):
                out.append((d * G, i, j))
    out.sort()
    return out[:40]

def astar(g, net, sources, targets):
    """bottom-layer path from any source cell to any target cell"""
    tset = {(i, j) for _, i, j in targets}
    if not tset: return None
    tx = sum(i for i, j in tset) / len(tset); ty = sum(j for i, j in tset) / len(tset)
    openh, best, prev = [], {}, {}
    for cost, i, j in sources:
        best[(i, j)] = cost / G; heapq.heappush(openh, (cost / G + math.hypot(i - tx, j - ty) * 0.5, cost / G, i, j))
    moves = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    n = 0
    while openh:
        f, c, i, j = heapq.heappop(openh)
        if (i, j) in tset:
            path = [(i, j)]
            while (i, j) in prev: i, j = prev[(i, j)]; path.append((i, j))
            return path[::-1]
        if c > best.get((i, j), 1e18): continue
        n += 1
        if n > 400000: return None
        for di, dj, w in moves:
            a, b = i + di, j + dj
            if not g.free(1, net, a, b): continue
            nc = c + w
            if nc < best.get((a, b), 1e18):
                best[(a, b)] = nc; prev[(a, b)] = (i, j)
                heapq.heappush(openh, (nc + math.hypot(a - tx, b - ty) * 0.5, nc, a, b))
    return None

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

def add_via(board, net, x, y):
    v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DR))
    v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH); board.Add(v)

def anchor_points(group):
    pts = []
    for it in group:
        if it[0] == 'pad' and 0 in it[2]: pts.append((it[3][0] / NM, it[3][1] / NM, it[4], tuple(v / NM for v in it[1])))
        elif it[0] == 'trk' and it[2] == [0]: pts += [(it[1][0] / NM, it[1][1] / NM, 'trk', None), (it[1][2] / NM, it[1][3] / NM, 'trk', None)]
        elif it[0] == 'via': pts.append((it[1][0] / NM, it[1][1] / NM, 'via', None))
    return pts

def item_cells(g, it, zones_by_net=None):
    """grid cells (layer, i, j) covered by a cluster item"""
    k, out = it[0], []
    if k == 'pad':
        x0, y0, x1, y1 = (v / NM for v in it[1])
        i0, j0 = g.cell(x0, y0); i1, j1 = g.cell(x1, y1)
        for L in it[2]:
            out += [(L, i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]
    elif k == 'via':
        i, j = g.cell(it[1][0] / NM, it[1][1] / NM); out += [(0, i, j), (1, i, j)]
    else:
        ax, ay, bx, by = (v / NM for v in it[1]); n = int(max(abs(bx - ax), abs(by - ay)) / G) + 1
        out += [(it[2][0],) + g.cell(ax + (bx - ax) * s / n, ay + (by - ay) * s / n) for s in range(n + 1)]
    return out

def astar2(g, net, src, dst, via_cost=12.0, limit=1500000):
    """two-layer grid search; src/dst = sets of (layer, i, j). Returns [(layer, i, j), ...]"""
    if not src or not dst: return None
    I = [c[1] for c in dst]; J = [c[2] for c in dst]
    bi0, bi1, bj0, bj1 = min(I), max(I), min(J), max(J)
    def h(i, j): return math.hypot(max(bi0 - i, 0, i - bi1), max(bj0 - j, 0, j - bj1))
    rv = int(math.ceil((VIA_D / 2 - TW / 2) / G))
    disk = [(a, b) for a in range(-rv, rv + 1) for b in range(-rv, rv + 1) if a * a + b * b <= rv * rv]
    def via_ok(i, j): return all(g.free(L, net, i + a, j + b) or (L, i + a, j + b) in src or (L, i + a, j + b) in dst for L in (0, 1) for a, b in disk)
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
        n += 1
        if n > limit: return None
        L, i, j = s
        nbrs = []
        for di, dj, w in moves:
            q = (L, i + di, j + dj)
            if q in dst or q in src or g.free(L, net, i + di, j + dj): nbrs.append((q, w))
        if via_ok(i, j): nbrs.append(((1 - L, i, j), via_cost))
        for q, w in nbrs:
            nc = c + w
            if nc < best.get(q, 1e18):
                best[q] = nc; prev[q] = s; heapq.heappush(openh, (nc + h(q[1], q[2]), nc, q))
    return None

def emit(board, g, ni, net, path):
    """turn a cell path into tracks (per layer, collinear runs merged) and vias at layer changes"""
    runs, cur = [], [path[0]]
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            runs.append(cur); cur = [b]
        else:
            cur.append(b)
    runs.append(cur)
    nseg = nvia = 0
    for r in runs:
        L = r[0][0]
        pts = simplify([(c[1], c[2]) for c in r])
        xy = [(g.x0 + i * G, g.y0 + j * G) for i, j in pts]
        for (x0, y0), (x1, y1) in zip(xy, xy[1:]):
            add_track(board, ni, L, x0, y0, x1, y1); g.mark_seg(L, net, x0, y0, x1, y1, TW + CL); nseg += 1
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            x, y = g.x0 + a[1] * G, g.y0 + a[2] * G
            add_via(board, ni, x, y); nvia += 1
            for L in (0, 1): g.mark_seg(L, net, x, y, x, y, VIA_D / 2 + CL + TW / 2)
    return nseg, nvia

def complete(board, zones, ox, oy, W, H, skip=('GND',)):
    open_ = clusters(board)
    log = []
    g = build_grid(board, zones, ox, oy, W, H)
    zr = {n: r for n, r in zones}
    for net, groups in sorted(open_.items()):
        ni = board.GetNetInfo().GetNetItem(net); name = ni.GetNetname()
        if name in skip: continue
        groups.sort(key=len, reverse=True)
        main = groups[0]
        for grp in groups[1:]:
            src = {c for it in grp for c in item_cells(g, it)}
            dst = {c for it in main for c in item_cells(g, it)}
            for (x0, y0, x1, y1) in zr.get(name, []):            # fixed power copper of this net (top layer)
                i0, j0 = g.cell(ox + x0 + 0.3, oy + y0 + 0.3); i1, j1 = g.cell(ox + x1 - 0.3, oy + y1 - 0.3)
                dst |= {(0, i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)}
            path = astar2(g, net, src, dst)
            if path:
                nseg, nvia = emit(board, g, ni, net, path)
                log.append(f'{name}: routed ({nseg} segments, {nvia} vias)')
                main = main + grp
            else:
                log.append(f'{name}: NOT routed ({len(grp)} items)')
    return log
