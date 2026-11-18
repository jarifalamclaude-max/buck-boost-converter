"""
One-command consistency check:  /usr/bin/python3 verify.py
  1. netlist.py sanity (no duplicate refs, single-pin nets only where intended)
  2. schematic  == netlist.py   (kicad-cli exports the schematic netlist, compared net by net)
  3. PCB pads   == netlist.py   (every pad's net in the routed board)
  4. PCB footprints linked to schematic symbols (same UUID path)
  5. KiCad DRC summary of the routed board (errors that matter for manufacturing)
"""
import os, sys, re, subprocess, tempfile, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netlist import PARTS, nets, sym_uuid
import make_schematic as ms

KDIR = os.path.join(HERE, 'kicad')
ok = True
def report(name, good, detail=''):
    global ok
    ok &= good
    print(f"[{'PASS' if good else 'FAIL'}] {name}" + (f"  -  {detail}" if detail else ''))

want = nets()
refs = [p['ref'] for p in PARTS]
report('netlist.py: unique references', len(refs) == len(set(refs)), f'{len(refs)} parts, {len(want)} nets')
singles = sorted(n for n, m in want.items() if len(m) == 1)
report('netlist.py: single-pin nets are only intended no-connects',
       all(n.startswith('NC_') or n in ('RTN', 'U2_SW') for n in singles), ', '.join(singles))

# 2. schematic
tmp = tempfile.mktemp(suffix='.net')
subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', tmp,
                os.path.join(KDIR, 'SafeBuck-80.kicad_sch')], check=True, capture_output=True)
root = ms.parse(open(tmp).read())[0]
got = {}
for n in ms.find(ms.find(root, 'nets')[0], 'net'):
    got[frozenset((str(ms.find(x, 'ref')[0][1]), str(ms.find(x, 'pin')[0][1])) for x in ms.find(n, 'node'))] = str(ms.find(n, 'name')[0][1])
w = {frozenset(v): k for k, v in want.items() if len(v) > 1}
g = {k: v for k, v in got.items() if len(k) > 1}
report('schematic nets == netlist.py', set(w) == set(g),
       f'{len(w)} multi-pin nets; missing {[w[k] for k in w if k not in g]}, extra {[g[k] for k in g if k not in w]}')
comps = ms.find(root, 'components')[0]
report('schematic has every part', len(ms.find(comps, 'comp')) == len(PARTS), f"{len(ms.find(comps, 'comp'))} symbols")

# 3./4./5. PCB (needs KiCad's python)
try:
    import pcbnew
except ImportError:
    print('(run with /usr/bin/python3 for the PCB checks)'); sys.exit(0 if ok else 1)
b = pcbnew.LoadBoard(os.path.join(KDIR, 'SafeBuck-80.kicad_pcb'))
byref = {p['ref']: p for p in PARTS}
bad, unlinked = [], []
for fp in b.GetFootprints():
    p = byref.get(fp.GetReference())
    if p is None: bad.append(fp.GetReference()); continue
    for pad in fp.Pads():
        if pad.GetNumber() and p['pins'].get(pad.GetNumber(), pad.GetNetname()) != pad.GetNetname():
            bad.append(f'{fp.GetReference()}.{pad.GetNumber()}')
    if fp.GetPath().AsString() != '/' + sym_uuid(p['ref']): unlinked.append(fp.GetReference())
report('PCB pad nets == netlist.py', not bad, f'{len(b.GetFootprints())} footprints' + (f', mismatches {bad[:10]}' if bad else ''))
report('PCB footprints linked to schematic symbols', not unlinked, ', '.join(unlinked[:10]))
rpt = tempfile.mktemp(suffix='.rpt')
pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
txt = open(rpt).read()
kinds = collections.Counter(re.findall(r'^\[(\w+)\]', txt, re.M))
serious = {k: v for k, v in kinds.items() if k in ('clearance', 'unconnected_items', 'shorting_items', 'tracks_crossing',
           'copper_edge_clearance', 'hole_near_hole', 'hole_clearance', 'starved_thermal', 'annular_width', 'drill_out_of_range',
           'track_width', 'via_diameter', 'zones_intersect', 'items_not_allowed')}
cosmetic = {k: v for k, v in kinds.items() if k not in serious}
report('DRC: no copper / connectivity errors', not serious, f'{serious or "none"}; cosmetic (silkscreen/library): {cosmetic}')
sys.exit(0 if ok else 1)
