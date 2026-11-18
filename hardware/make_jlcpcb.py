"""
Make the JLCPCB order package from the routed board + netlist.py:

  jlcpcb/SafeBuck-80_gerbers.zip   Gerber (Protel names) + Excellon drill  -> "PCB" upload
  jlcpcb/SafeBuck-80_BOM.csv       Comment, Designator, Footprint, LCSC Part #  -> "Assembly" BOM
  jlcpcb/SafeBuck-80_CPL.csv       Designator, Mid X, Mid Y, Layer, Rotation    -> "Assembly" CPL

Run:  python3 make_jlcpcb.py   (needs kicad-cli; plain python is enough)
"""
import os, sys, csv, io, re, subprocess, zipfile, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netlist import PARTS

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'jlcpcb')
PCB = os.path.join(HERE, 'kicad', 'SafeBuck-80.kicad_pcb')
LAYERS = 'F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'

# KiCad footprint rotation -> JLCPCB rotation (JLC's library parts are drawn with a different
# zero orientation for these packages). Values are the corrections most KiCad users apply;
# JLCPCB still shows a placement preview before production - always check it.
ROT_FIX = [(r'^Package_TO_SOT_SMD:SOT-23', 180), (r'^SafeBuck:LT8390', 270), (r'^Package_DFN_QFN:', 270),
           (r'^Capacitor_SMD:CP_Elec', 180)]

def no_board_part(p):
    r = p['ref']
    return p['dnp'] or r.startswith(('NT', 'H', 'TP'))

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'failed: {" ".join(cmd)}\n{r.stdout}\n{r.stderr}')
    return r.stdout

def gerbers():
    tmp = tempfile.mkdtemp()
    run(['kicad-cli', 'pcb', 'export', 'gerbers', '--layers', LAYERS, '--subtract-soldermask', '-o', tmp + '/', PCB])
    run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm',
         '--generate-map', '--map-format', 'gerberx2', '-o', tmp + '/', PCB])
    files = sorted(os.listdir(tmp))
    zp = os.path.join(OUT, 'SafeBuck-80_gerbers.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(tmp, f), f)
    shutil.rmtree(tmp)
    return zp, files

def bom():
    groups = {}
    for p in PARTS:
        if no_board_part(p): continue
        fp = p['fp'].split(':')[1]
        key = (p['value'], fp, p['lcsc'])
        groups.setdefault(key, []).append(p['ref'])
    def natural(r): return (re.match(r'[A-Z]+', r).group(), int(re.search(r'\d+', r).group()))
    rows = []
    for (val, fp, lcsc), refs in groups.items():
        refs.sort(key=natural)
        rows.append((val, ','.join(refs), fp, lcsc))
    rows.sort(key=lambda r: natural(r[1].split(',')[0]))
    path = os.path.join(OUT, 'SafeBuck-80_BOM.csv')
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        w.writerows(rows)
    return path, len(rows), sum(len(r[1].split(',')) for r in rows)

def cpl():
    txt = run(['kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '-o', '/dev/stdout', PCB])
    byref = {p['ref']: p for p in PARTS}
    rows = []
    for r in csv.DictReader(io.StringIO(txt)):
        p = byref.get(r['Ref'])
        if p is None or no_board_part(p): continue
        rot = float(r['Rot'])
        for pat, add in ROT_FIX:
            if re.search(pat, p['fp']): rot = (rot + add) % 360; break
        rows.append([r['Ref'], f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm",
                     'Top' if r['Side'].lower().startswith('top') else 'Bottom', f'{rot:g}'])
    path = os.path.join(OUT, 'SafeBuck-80_CPL.csv')
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        w.writerows(rows)
    return path, len(rows)

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    zp, files = gerbers(); print('gerbers:', zp, files)
    print('BOM:', bom())
    print('CPL:', cpl())
