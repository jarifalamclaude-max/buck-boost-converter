"""
Rip-up-and-reroute completion router for the connections Freerouting leaves open.

Works on plain data (tracks/vias from the Specctra session, pads/zones from the placed board),
so nothing has to be deleted from a live KiCad board:
  * hard obstacles: pads, mounting holes, board edge, fixed power copper (zone rectangles)
  * soft obstacles: existing tracks and vias - a new route may cross them at a cost; the crossed
    tracks are ripped up and their nets are routed again
  * two-layer grid A* (0.1 mm), 0.25 mm tracks, 0.21 mm clearance, 0.7/0.35 mm vias
Returns the final track/via lists; route.py writes them into a fresh board.
"""
import math, heapq, re
from collections import defaultdict

G = 0.1
TW, CL = 0.20, 0.205
VIA_D, VIA_DR = 0.6, 0.3
RT = CL + TW / 2                       # keep-out radius around copper for a new track centreline

def parse_ses(path):
    from make_schematic import parse, find
    root = parse(open(path).read())[0]
    routes = find(root, 'routes')[0]
    res = float(find(routes, 'resolution')[0][2]); um = 1.0 / res        # session unit -> um
    T, V = [], []
    for net in find(find(routes, 'network_out')[0], 'net'):
        name = str(net[1])
        for w in find(net, 'wire'):
            for p in find(w, 'path'):
                wd = float(p[2]) * um / 1000
                if wd > 0.6: continue                                     # our fixed power-zone wires
                c = [float(v) * um / 1000 for v in p[3:]]
                pts = [(c[i], -c[i + 1]) for i in range(0, len(c) - 1, 2)]
                L = 0 if str(p[1]) == 'F.Cu' else 1
                for a, b in zip(pts, pts[1:]): T.append([name, L, a[0], a[1], b[0], b[1], wd, True])
        for v in find(net, 'via'):
            m = re.search(r'_(\d+):(\d+)_um', str(v[1]))
            d = int(m.group(1)) / 1000 if m else VIA_D
            V.append([name, float(v[2]) * um / 1000, -float(v[3]) * um / 1000, d, True])
    return T, V

class Router:
    def __init__(self, pads, zones, box):
        """pads: [(net, ref, (x0,y0,x1,y1), layers, (cx,cy), npth)]; zones: {net: [(x0,y0,x1,y1) abs mm]}; box: (x0,y0,x1,y1)"""
        self.x0, self.y0 = box[0], box[1]
        self.nx, self.ny = int((box[2] - box[0]) / G) + 1, int((box[3] - box[1]) / G) + 1
        self.hard = [dict(), dict()]                       # cell -> net name or '#'
        self.soft = [defaultdict(set), defaultdict(set)]   # cell -> {('t'|'v', index)}
        self.pads, self.zones = pads, zones
        e = 0.3 + TW / 2
        for L in (0, 1):
            self._rect_hard(L, '#', box[0] - 1, box[1] - 1, box[2] + 1, box[1] + e)
            self._rect_hard(L, '#', box[0] - 1, box[3] - e, box[2] + 1, box[3] + 1)
            self._rect_hard(L, '#', box[0] - 1, box[1] - 1, box[0] + e, box[3] + 1)
            self._rect_hard(L, '#', box[2] - e, box[1] - 1, box[2] + 1, box[3] + 1)
        for net, ref, bb, layers, c, npth in pads:
            if npth:
                for L in (0, 1): self._rect_hard(L, '#', bb[0] - 0.3 - TW / 2, bb[1] - 0.3 - TW / 2, bb[2] + 0.3 + TW / 2, bb[3] + 0.3 + TW / 2)
                continue
            for L in layers: self._rect_hard(L, net or '#', bb[0] - RT, bb[1] - RT, bb[2] + RT, bb[3] + RT)
        for net, rects in zones.items():
            for r in rects: self._rect_hard(0, net, r[0] - RT, r[1] - RT, r[2] + RT, r[3] + RT)

    def cell(self, x, y): return int(round((x - self.x0) / G)), int(round((y - self.y0) / G))
    def xy(self, i, j): return self.x0 + i * G, self.y0 + j * G

    def _rect_hard(self, L, net, x0, y0, x1, y1):
        i0, j0 = self.cell(x0, y0); i1, j1 = self.cell(x1, y1); h = self.hard[L]
        for j in range(max(0, j0), min(self.ny, j1 + 1)):
            for i in range(max(0, i0), min(self.nx, i1 + 1)):
                k = (i, j); o = h.get(k)
                h[k] = net if o is None or o == net else '#'

    def _seg_cells(self, ax, ay, bx, by, r):
        i0, j0 = self.cell(min(ax, bx) - r, min(ay, by) - r); i1, j1 = self.cell(max(ax, bx) + r, max(ay, by) + r)
        dx, dy = bx - ax, by - ay; ll = dx * dx + dy * dy
        for j in range(max(0, j0), min(self.ny, j1 + 1)):
            y = self.y0 + j * G
            for i in range(max(0, i0), min(self.nx, i1 + 1)):
                x = self.x0 + i * G
                t = 0.0 if ll == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ll))
                px, py = ax + t * dx - x, ay + t * dy - y
                if px * px + py * py <= r * r: yield (i, j)

    def add_soft(self, kind, idx, item):
        if kind == 't':
            net, L, ax, ay, bx, by, w, _ = item
            for k in self._seg_cells(ax, ay, bx, by, w / 2 + RT): self.soft[L][k].add(('t', idx))
        else:
            net, x, y, d, _ = item
            for L in (0, 1):
                for k in self._seg_cells(x, y, x, y, d / 2 + RT): self.soft[L][k].add(('v', idx))

    def del_soft(self, kind, idx, item):
        if kind == 't':
            net, L, ax, ay, bx, by, w, _ = item
            for k in self._seg_cells(ax, ay, bx, by, w / 2 + RT): self.soft[L][k].discard(('t', idx))
        else:
            net, x, y, d, _ = item
            for L in (0, 1):
                for k in self._seg_cells(x, y, x, y, d / 2 + RT): self.soft[L][k].discard(('v', idx))

def route_all(pads, zones, box, T, V, skip=('GND',), max_attempts=120, log=print):
    R = Router(pads, zones, box)
    for i, t in enumerate(T): R.add_soft('t', i, t)
    for i, v in enumerate(V): R.add_soft('v', i, v)

    def owner(kind, idx): return (T[idx] if kind == 't' else V[idx])[0]

    def clusters(net):
        items = []
        for p in pads:
            if p[0] == net and not p[5]: items.append(('p', p))
        for i, t in enumerate(T):
            if t[7] and t[0] == net: items.append(('t', t))
        for i, v in enumerate(V):
            if v[4] and v[0] == net: items.append(('v', v))
        zr = zones.get(net, [])
        n = len(items); par = list(range(n + 1))
        def f(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        def pts(it):
            k, d = it
            if k == 'p': return [d[4]]
            if k == 'v': return [(d[1], d[2])]
            return [(d[2], d[3]), (d[4], d[5])]
        def layers(it):
            k, d = it
            return d[3] if k == 'p' else ([0, 1] if k == 'v' else [d[1]])
        def near(it, x, y):
            k, d = it
            if k == 'p': b = d[2]; return b[0] - 0.02 <= x <= b[2] + 0.02 and b[1] - 0.02 <= y <= b[3] + 0.02
            if k == 'v': return (x - d[1]) ** 2 + (y - d[2]) ** 2 <= (d[3] / 2 + 0.02) ** 2
            ax, ay, bx, by = d[2:6]; dx, dy = bx - ax, by - ay; ll = dx * dx + dy * dy
            t = 0 if ll == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / ll))
            return (ax + t * dx - x) ** 2 + (ay + t * dy - y) ** 2 <= (d[6] / 2 + 0.02) ** 2
        for a in range(n):
            for b in range(a + 1, n):
                if not set(layers(items[a])) & set(layers(items[b])): continue
                if any(near(items[b], x, y) for x, y in pts(items[a])) or any(near(items[a], x, y) for x, y in pts(items[b])):
                    par[f(a)] = f(b)
                elif items[a][0] == 'p' and items[b][0] == 'p':
                    A, B = items[a][1][2], items[b][1][2]
                    if A[0] <= B[2] and B[0] <= A[2] and A[1] <= B[3] and B[1] <= A[3]: par[f(a)] = f(b)
            if zr and 0 in layers(items[a]) and any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for x, y in pts(items[a]) for r in zr):
                par[f(a)] = f(n)
        groups = defaultdict(list)
        for a in range(n): groups[f(a)].append(items[a])
        gl = list(groups.values())
        if zr:                                           # the zone itself belongs to the cluster holding it
            for gi, g_ in enumerate(gl):
                pass
        return gl, (f(n) if zr else None), {id(it): f(a) for a, it in enumerate(items)}

    def cells_of(it):
        k, d = it; out = set()
        if k == 'p':
            b = d[2]; i0, j0 = R.cell(b[0], b[1]); i1, j1 = R.cell(b[2], b[3])
            for L in d[3]: out |= {(L, i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)}
        elif k == 'v':
            i, j = R.cell(d[1], d[2]); out |= {(0, i, j), (1, i, j)}
        else:
            ax, ay, bx, by = d[2:6]; n = int(max(abs(bx - ax), abs(by - ay)) / G) + 1
            out |= {(d[1],) + R.cell(ax + (bx - ax) * s / n, ay + (by - ay) * s / n) for s in range(n + 1)}
        return out

    rv = int(math.ceil((VIA_D / 2 - TW / 2) / G))
    disk = [(a, b) for a in range(-rv, rv + 1) for b in range(-rv, rv + 1) if a * a + b * b <= rv * rv]

    def search(net, src, dst, rip_cost):
        I = [c[1] for c in dst]; J = [c[2] for c in dst]
        bi0, bi1, bj0, bj1 = min(I), max(I), min(J), max(J)
        def h(i, j): return math.hypot(max(bi0 - i, 0, i - bi1), max(bj0 - j, 0, j - bj1))
        def cost(L, i, j):
            if (L, i, j) in src or (L, i, j) in dst: return 0.0
            if not (0 <= i < R.nx and 0 <= j < R.ny): return None
            o = R.hard[L].get((i, j))
            if o is not None and o != net: return None
            s = R.soft[L].get((i, j))
            if s:
                others = {owner(*x) for x in s} - {net}
                if others:
                    if not rip_cost or others & set(skip): return None
                    return rip_cost
            return 0.0
        best, prev, openh = {}, {}, []
        for s in src: best[s] = 0.0; heapq.heappush(openh, (h(s[1], s[2]), 0.0, s))
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
            if n > 1200000: return None
            L, i, j = s
            for di, dj, w in moves:
                ec = cost(L, i + di, j + dj)
                if ec is None: continue
                q = (L, i + di, j + dj); nc = c + w + ec
                if nc < best.get(q, 1e18): best[q] = nc; prev[q] = s; heapq.heappush(openh, (nc + h(q[1], q[2]), nc, q))
            vc = 0.0; ok = True                               # via to the other layer
            for L2 in (0, 1):
                for a, b in disk:
                    e = cost(L2, i + a, j + b)
                    if e is None: ok = False; break
                    vc = max(vc, e)
                if not ok: break
            if ok:
                q = (1 - L, i, j); nc = c + 12.0 + vc
                if nc < best.get(q, 1e18): best[q] = nc; prev[q] = s; heapq.heappush(openh, (nc + h(i, j), nc, q))
        return None

    def rip_net(name):
        for i, t_ in enumerate(T):
            if t_[0] == name and t_[7]: t_[7] = False; R.del_soft('t', i, t_)
        for i, v_ in enumerate(V):
            if v_[0] == name and v_[4]: v_[4] = False; R.del_soft('v', i, v_)

    def commit(net, path):
        """add tracks/vias for the path; whole nets whose copper it crosses are ripped up and returned"""
        ripped = set()
        def rip_at(L, i, j):
            for kind, idx in list(R.soft[L].get((i, j), ())):
                o = owner(kind, idx)
                if o != net and o not in skip: ripped.add(o)
        runs, cur = [], [path[0]]
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]: runs.append(cur); cur = [b]
            else: cur.append(b)
        runs.append(cur)
        for r in runs:
            for (L, i, j) in r: rip_at(L, i, j)
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]:
                for L in (0, 1):
                    for da, db in disk: rip_at(L, a[1] + da, a[2] + db)
        for rn in ripped: rip_net(rn)
        for r in runs:
            L = r[0][0]; pts = [(c[1], c[2]) for c in r]
            simp = [pts[0]]
            for k in range(1, len(pts) - 1):
                p0, p1, p2 = simp[-1], pts[k], pts[k + 1]
                if (p1[0] - p0[0]) * (p2[1] - p1[1]) != (p1[1] - p0[1]) * (p2[0] - p1[0]): simp.append(p1)
            simp.append(pts[-1])
            for (i0, j0), (i1, j1) in zip(simp, simp[1:]):
                x0, y0 = R.xy(i0, j0); x1, y1 = R.xy(i1, j1)
                T.append([net, L, x0, y0, x1, y1, TW, True]); R.add_soft('t', len(T) - 1, T[-1])
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]:
                x, y = R.xy(a[1], a[2]); V.append([net, x, y, VIA_D, True]); R.add_soft('v', len(V) - 1, V[-1])
        return ripped

    nets = sorted({p[0] for p in pads if p[0] and p[0] not in skip})
    queue = list(nets); attempts = 0; failed = set()
    while queue and attempts < max_attempts:
        net = queue.pop(0)
        groups, zroot, _ = clusters(net)
        if len(groups) <= 1: continue
        if net in skip: continue
        groups.sort(key=len, reverse=True)
        main = groups[0]
        for grp in groups[1:]:
            attempts += 1
            src = set().union(*[cells_of(it) for it in grp])
            dst = set().union(*[cells_of(it) for it in main])
            for r in zones.get(net, []):
                i0, j0 = R.cell(r[0] + 0.3, r[1] + 0.3); i1, j1 = R.cell(r[2] - 0.3, r[3] - 0.3)
                dst |= {(0, i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)}
            path = search(net, src, dst, None) or (search(net, src, dst, 60.0) if attempts < max_attempts * 0.6 else None)
            if not path:
                log(f'  {net}: no path'); failed.add(net); continue
            ripped = commit(net, path)
            main = main + grp
            log(f'  {net}: routed' + (f', ripped up {sorted(ripped)}' if ripped else ''))
            if ripped and net not in queue: queue.append(net)     # re-check this net after the rip-up
            for rn in ripped:
                if rn not in queue and rn not in skip: queue.append(rn)
            if ripped: break                              # clusters of this net may have changed
    return [t for t in T if t[7]], [v for v in V if v[4]], failed
