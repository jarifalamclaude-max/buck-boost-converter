"""
Generate the KiCad 7 schematic (kicad/SafeBuck-80.kicad_sch) and the project symbol library
(kicad/SafeBuck.kicad_sym) from netlist.py.

Style: every pin gets a short wire and a net label, so the drawing is an exact copy of netlist.py
(labels with the same name are connected). Symbols come from the standard KiCad 7 libraries except
LT8390, LM74930 and the SOT-23 diodes, which are in the project library SafeBuck.kicad_sym.
Symbol UUIDs = netlist.sym_uuid(ref), the same IDs the PCB footprints carry, so
"Update PCB from Schematic" finds everything already linked.

Run:  python3 make_schematic.py      (plain python, no KiCad module needed)
"""
import os, sys, uuid, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netlist import PARTS, nets, sym_uuid

KDIR = os.path.join(HERE, 'kicad')
SYMDIR = '/usr/share/kicad/symbols'
PROJECT = 'SafeBuck-80'
ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, 'SafeBuck-80/root-sheet'))
G = 2.54

# ------------------------------------------------------------------ tiny s-expression reader/writer
class Q(str):
    """a quoted string atom"""

def parse(text):
    tokens, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in '()':
            tokens.append(c); i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == '\\': buf.append('\n' if text[j + 1] == 'n' else text[j + 1]); j += 2
                else: buf.append(text[j]); j += 1
            tokens.append(Q(''.join(buf))); i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()': j += 1
            tokens.append(text[i:j]); i = j
    stack = [[]]
    for t in tokens:
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t)
    return stack[0]

def dump(x, ind=0):
    """serialize, keeping element order; short lists stay on one line"""
    if isinstance(x, list):
        parts = [dump(e, ind + 1) for e in x]
        one = '(' + ' '.join(parts) + ')'
        if len(one) <= 100 and '\n' not in one:
            return one
        out = '(' + parts[0]
        for e, s in zip(x[1:], parts[1:]):
            out += ('\n' + '  ' * (ind + 1) + s) if isinstance(e, list) else (' ' + s)
        return out + ')'
    if isinstance(x, Q):
        return '"' + x.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
    return str(x)

def find(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]

_libs = {}
def lib_symbol(lib, name):
    """symbol from a KiCad library, with 'extends' resolved; returned as a fresh tree"""
    if lib not in _libs:
        _libs[lib] = {s[1]: s for s in find(parse(open(f'{SYMDIR}/{lib}.kicad_sym').read())[0], 'symbol')}
    syms = _libs[lib]
    s = syms[name]
    ext = find(s, 'extends')
    if not ext:
        return parse(dump(s))[0]
    parent = lib_symbol(lib, ext[0][1])
    child_props = {p[1]: p for p in find(s, 'property')}
    out = [parent[0], Q(name)]
    for e in parent[2:]:
        if isinstance(e, list) and e[0] == 'property' and e[1] in child_props:
            out.append(child_props.pop(e[1]))
        elif isinstance(e, list) and e[0] == 'symbol':
            out.append([e[0], Q(name + e[1][len(ext[0][1]):])] + e[2:])
        else:
            out.append(e)
    out[2:2] = list(child_props.values())
    return parse(dump(out))[0]

def pins_of(sym):
    """[(number, x, y, angle)] connection points in symbol coordinates (y up)"""
    out = []
    for sub in find(sym, 'symbol'):
        for p in find(sub, 'pin'):
            at = find(p, 'at')[0]
            num = find(p, 'number')[0][1]
            out.append((str(num), float(at[1]), float(at[2]), int(float(at[3]))))
    return out

# ------------------------------------------------------------------ project symbols (SafeBuck lib)
def ic_symbol(name, ref, value, left, right, bottom, width=25.4, fp='', ds='', desc=''):
    """rectangle IC: left/right lists of (number, pin name) top->bottom (None = gap), bottom list"""
    rows = max(len(left), len(right))
    top = (rows + 1) * G / 2.0
    top = round(top / G + 0.5) * G
    ybot = top - (rows + 1) * G
    hw = width / 2
    pins = []
    def pin(num, nm, x, y, ang, typ='passive'):
        pins.append([ 'pin', typ, 'line', ['at', f'{x:g}', f'{y:g}', str(ang)], ['length', '5.08'],
                      ['name', Q(nm), ['effects', ['font', ['size', '1.27', '1.27']]]],
                      ['number', Q(num), ['effects', ['font', ['size', '1.27', '1.27']]]]])
    for i, p in enumerate(left):
        if p: pin(p[0], p[1], -hw - 5.08, top - G * (i + 1), 0)
    for i, p in enumerate(right):
        if p: pin(p[0], p[1], hw + 5.08, top - G * (i + 1), 180)
    nb = len(bottom)
    for i, p in enumerate(bottom):
        x = (i - (nb - 1) / 2) * G * 2
        pin(p[0], p[1], x, ybot - 5.08, 90, p[2] if len(p) > 2 else 'passive')
    font = ['effects', ['font', ['size', '1.27', '1.27']]]
    hide = ['effects', ['font', ['size', '1.27', '1.27']], 'hide']
    sym = ['symbol', Q(name), ['in_bom', 'yes'], ['on_board', 'yes'],
           ['property', Q('Reference'), Q(ref), ['at', '0', f'{top + 1.27:g}', '0'], font],
           ['property', Q('Value'), Q(value), ['at', '0', f'{ybot - 1.27:g}', '0'], font],
           ['property', Q('Footprint'), Q(fp), ['at', '0', '0', '0'], hide],
           ['property', Q('Datasheet'), Q(ds), ['at', '0', '0', '0'], hide],
           ['property', Q('ki_description'), Q(desc), ['at', '0', '0', '0'], hide],
           ['symbol', Q(f'{name}_0_1'),
            ['rectangle', ['start', f'{-hw:g}', f'{top:g}'], ['end', f'{hw:g}', f'{ybot:g}'],
             ['stroke', ['width', '0.254'], ['type', 'default']], ['fill', ['type', 'background']]]],
           ['symbol', Q(f'{name}_1_1')] + pins]
    return sym

def diode_sot23(name, value, zener=False, desc=''):
    """SOT-23 diode: pin 1 = anode, pin 3 = cathode (BAS21 / BZX84 pinout)"""
    font = ['effects', ['font', ['size', '1.27', '1.27']]]
    hide = ['effects', ['font', ['size', '1.27', '1.27']], 'hide']
    body = [['polyline', ['pts', ['xy', '-1.27', '1.27'], ['xy', '-1.27', '-1.27'], ['xy', '1.27', '0'], ['xy', '-1.27', '1.27']],
             ['stroke', ['width', '0.254'], ['type', 'default']], ['fill', ['type', 'none']]]]
    if zener:
        body.append(['polyline', ['pts', ['xy', '0.762', '1.27'], ['xy', '1.27', '1.27'], ['xy', '1.27', '-1.27'], ['xy', '1.778', '-1.27']],
                     ['stroke', ['width', '0.254'], ['type', 'default']], ['fill', ['type', 'none']]])
    else:
        body.append(['polyline', ['pts', ['xy', '1.27', '1.27'], ['xy', '1.27', '-1.27']],
                     ['stroke', ['width', '0.254'], ['type', 'default']], ['fill', ['type', 'none']]])
    def pin(num, nm, x, ang):
        return ['pin', 'passive', 'line', ['at', f'{x:g}', '0', str(ang)], ['length', '2.54'],
                ['name', Q(nm), font], ['number', Q(num), font]]
    return ['symbol', Q(name), ['pin_names', ['offset', '1.016'], 'hide'], ['in_bom', 'yes'], ['on_board', 'yes'],
            ['property', Q('Reference'), Q('D'), ['at', '0', '2.54', '0'], font],
            ['property', Q('Value'), Q(value), ['at', '0', '-2.54', '0'], font],
            ['property', Q('Footprint'), Q('Package_TO_SOT_SMD:SOT-23'), ['at', '0', '0', '0'], hide],
            ['property', Q('Datasheet'), Q(''), ['at', '0', '0', '0'], hide],
            ['property', Q('ki_description'), Q(desc), ['at', '0', '0', '0'], hide],
            ['symbol', Q(f'{name}_0_1')] + body,
            ['symbol', Q(f'{name}_1_1'), pin('1', 'A', -3.81, 0), pin('3', 'K', 3.81, 180)]]

CUSTOM = {
    'LT8390': ic_symbol('LT8390', 'U', 'LT8390',
        left=[('7', 'VIN'), ('9', 'EN/UVLO'), ('8', 'INTVCC'), ('12', 'VREF'), ('11', 'LOADEN'), ('13', 'CTRL'),
              None, ('18', 'SS'), ('20', 'VC'), ('19', 'FB'), ('21', 'RT'), ('22', 'SYNC/SPRD'), ('10', 'TEST')],
        right=[('2', 'BST1'), ('4', 'TG1'), ('3', 'SW1'), ('1', 'BG1'), ('5', 'LSP'), ('6', 'LSN'), None,
               ('27', 'BST2'), ('25', 'TG2'), ('26', 'SW2'), ('28', 'BG2'), ('24', 'VOUT'), ('23', 'LOADTG'), None,
               ('14', 'ISP'), ('15', 'ISN'), ('16', 'ISMON'), ('17', 'PGOOD')],
        bottom=[('29', 'GND')], width=22.86, fp='SafeBuck:LT8390_FE28_EB_TSSOP-28_EP4.75x2.74mm',
        ds='https://www.analog.com/media/en/technical-documentation/data-sheets/lt8390.pdf',
        desc='60 V synchronous 4-switch buck-boost controller with spread spectrum (FE28)'),
    'LM74930': ic_symbol('LM74930', 'U', 'LM74930-Q1',
        left=[('22', 'VS'), ('6', 'EN'), ('7', 'MODE'), ('4', 'UVLO'), ('5', 'OV'), ('16', 'OVCLAMP'), ('9', 'TMR'),
              ('11', 'ILIM'), ('10', 'IMON'), ('12', 'FLT'), ('13', 'GND')],
        right=[('2', 'A'), ('15', 'OUT'), ('14', 'HGATE'), ('1', 'DGATE'), ('3', 'SW'), ('23', 'CAP'), None,
               ('24', 'C'), ('20', 'CS+'), ('19', 'CS-'), ('18', 'ISCP')],
        bottom=[('8', 'NC', 'no_connect'), ('17', 'NC', 'no_connect'), ('21', 'NC', 'no_connect'), ('25', 'RTN')],
        width=20.32, fp='Package_DFN_QFN:HVQFN-24-1EP_4x4mm_P0.5mm_EP2.1x2.1mm',
        ds='https://www.ti.com/lit/ds/symlink/lm74930-q1.pdf',
        desc='Ideal diode controller with load switch, OV/UV protection (VQFN-24); EP (RTN) must float'),
    'D_SOT23': diode_sot23('D_SOT23', 'BAS21', desc='Switching diode, SOT-23 (pin 1 A, pin 3 K)'),
    'DZ_SOT23': diode_sot23('DZ_SOT23', 'BZX84Cxx', zener=True, desc='Zener diode, SOT-23 (pin 1 A, pin 3 K)'),
}

def symbol_for(p):
    fp, ref, val = p['fp'], p['ref'], p['value']
    if ref == 'U1': return 'SafeBuck', 'LT8390'
    if ref == 'U2': return 'SafeBuck', 'LM74930'
    if 'TDSON' in fp: return 'Transistor_FET', p['mpn']                    # CSD18532Q5B / CSD19532Q5B
    if 'SOT-23' in fp and ref.startswith('Q'):
        return 'Device', 'Q_NPN_BEC' if '3904' in val else 'Q_PNP_BEC'
    if 'SOT-23' in fp and ref.startswith('D'):
        return 'SafeBuck', 'DZ_SOT23' if 'BZX' in val else 'D_SOT23'
    if ref == 'D1': return 'Device', 'D_TVS'
    if ref.startswith('D'): return 'Device', 'D'
    if ref.startswith('LED'): return 'Device', 'LED'
    if ref.startswith('TH'): return 'Device', 'Thermistor_PTC'
    if ref.startswith('RV'): return 'Device', 'R_Potentiometer'
    if ref.startswith('R'): return 'Device', 'R'
    if 'CP_Elec' in fp: return 'Device', 'C_Polarized'
    if ref.startswith('C'): return 'Device', 'C'
    if ref.startswith('L'): return 'Device', 'L'
    if ref.startswith('F'): return 'Device', 'Fuse'
    if ref.startswith('J'): return 'Connector', 'Screw_Terminal_01x02'
    if ref.startswith('TP'): return 'Connector', 'TestPoint'
    if ref.startswith('H'): return 'Mechanical', 'MountingHole'
    if ref.startswith('NT'): return 'Device', 'NetTie_2'
    raise ValueError(ref)

# ------------------------------------------------------------------ layout
BLOCKS = [('input', '1. INPUT PROTECTION  -  LM74930: reverse -60 V, OV 41 V, UV 7.6 V', 12.7, 38.1, 190.5),
          ('converter', '2. 4-SWITCH BUCK-BOOST  -  LT8390, 300 kHz spread spectrum, CV (RV1) + CC (RV2)', 210.82, 38.1, 205.74),
          ('output', '3. OUTPUT  -  CC sense, Q7 reverse-battery switch, trips Q9/Q11, hold Q10', 431.8, 38.1, 152.4),
          ('mech', 'MECHANICAL', 431.8, 360.0, 152.4)]

def uid(*k):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'SafeBuck-80/sch/' + '/'.join(k)))

def snap(v): return round(v / 1.27) * 1.27

def build():
    allnets = nets()
    singles = {n for n, m in allnets.items() if len(m) == 1}
    used = {}
    for p in PARTS:
        lib, name = symbol_for(p)
        key = f'{lib}:{name}'
        if key not in used:
            used[key] = parse(dump(CUSTOM[name]))[0] if lib == 'SafeBuck' else lib_symbol(lib, name)
    items, texts = [], []
    font = ['effects', ['font', ['size', '1.27', '1.27']]]
    for bname, title, bx, by, bw in BLOCKS:
        texts.append(['text', Q(title), ['at', f'{bx:g}', f'{by - 7.62:g}', '0'],
                      ['effects', ['font', ['size', '2.54', '2.54'], ['thickness', '0.508'], 'bold'], ['justify', 'left', 'bottom']],
                      ['uuid', uid('t', bname)]])
        x, y, rowh = bx, by, 0
        for p in [q for q in PARTS if q['block'] == bname]:
            lib, name = symbol_for(p)
            sym = used[f'{lib}:{name}']
            pins = pins_of(sym)
            xs = [pp[1] for pp in pins] or [0]; ys = [pp[2] for pp in pins] or [0]
            lw = max([len(n) for n in p['pins'].values()] + [4]) * 1.0 + 3.81
            w = max(xs) - min(xs) + (lw if any(a == 0 for _, _, _, a in pins) else 0) \
                + (lw if any(a == 180 for _, _, _, a in pins) else 0) + 22.0
            h = max(ys) - min(ys) + 15.24
            if x + w > bx + bw:
                x, y, rowh = bx, y + rowh, 0
            ox = snap(x - min(xs) + (lw if any(a == 0 for _, _, _, a in pins) else 0) + 2.54)
            oy = snap(y + max(ys) + 7.62)
            items.append(place(p, lib, name, pins, ox, oy, singles))
            x += w; rowh = max(rowh, h)
    return used, items, texts

def place(p, lib, name, pins, ox, oy, singles):
    ref = p['ref']
    font = ['effects', ['font', ['size', '1.27', '1.27']]]
    hide = ['effects', ['font', ['size', '1.27', '1.27']], 'hide']
    out = []
    ys = [pp[2] for pp in pins] or [0]
    xs = [pp[1] for pp in pins] or [0]
    rx = ox + max(xs + [0]) + 2.54
    sym = ['symbol', ['lib_id', Q(f'{lib}:{name}')], ['at', f'{ox:g}', f'{oy:g}', '0'], ['unit', '1'],
           ['in_bom', 'no' if ref.startswith(('NT', 'H')) else 'yes'], ['on_board', 'yes'],
           ['dnp', 'yes' if p['dnp'] else 'no'], ['uuid', Q(sym_uuid(ref))],
           ['property', Q('Reference'), Q(ref), ['at', f'{snap(rx):g}', f'{oy - 1.27:g}', '0'],
            ['effects', ['font', ['size', '1.27', '1.27']], ['justify', 'left']]],
           ['property', Q('Value'), Q(p['value']), ['at', f'{snap(rx):g}', f'{oy + 1.27:g}', '0'],
            ['effects', ['font', ['size', '1.27', '1.27']], ['justify', 'left']]],
           ['property', Q('Footprint'), Q(p['fp']), ['at', f'{ox:g}', f'{oy:g}', '0'], hide],
           ['property', Q('Datasheet'), Q(''), ['at', f'{ox:g}', f'{oy:g}', '0'], hide]]
    for k, v in (('MPN', p['mpn']), ('Manufacturer', p['mfr']), ('LCSC', p['lcsc']), ('Role', p['role'])):
        if v: sym.append(['property', Q(k), Q(v), ['at', f'{ox:g}', f'{oy:g}', '0'], hide])
    for num, *_ in pins:
        sym.append(['pin', Q(num), ['uuid', Q(uid('pin', ref, num))]])
    sym.append(['instances', ['project', Q(PROJECT), ['path', Q('/' + ROOT_UUID), ['reference', Q(ref)], ['unit', '1']]]])
    out.append(sym)
    for num, px, py, ang in pins:
        X, Y = ox + px, oy - py                    # library y is up, schematic y is down
        net = p['pins'].get(num)
        if net is None or net.startswith('NC_') or net in singles:
            out.append(['no_connect', ['at', f'{X:g}', f'{Y:g}'], ['uuid', Q(uid('nc', ref, num))]])
            continue
        dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[ang]
        X2, Y2 = X + dx * 2.54, Y + dy * 2.54
        out.append(['wire', ['pts', ['xy', f'{X:g}', f'{Y:g}'], ['xy', f'{X2:g}', f'{Y2:g}']],
                    ['stroke', ['width', '0'], ['type', 'default']], ['uuid', Q(uid('w', ref, num))]])
        lang, just = ('180', 'right') if dx < 0 else ('0', 'left')
        out.append(['label', Q(net), ['at', f'{X2:g}', f'{Y2:g}', lang], ['fields_autoplaced'],
                    ['effects', ['font', ['size', '1.27', '1.27']], ['justify', just, 'bottom']],
                    ['uuid', Q(uid('l', ref, num))]])
    return out

def write():
    used, items, texts = build()
    libsyms = []
    for key, s in used.items():
        s = parse(dump(s))[0]
        s[1] = Q(key)
        libsyms.append(s)
    notes = ['text', Q('Generated from hardware/netlist.py by make_schematic.py - edit netlist.py and re-run, do not hand-edit.\n'
                       'Every pin has a net label; labels with the same name are connected.  GND = power ground (one node).\n'
                       'OUT- (OUTN) is switched by Q7: never connect OUT- to VIN- externally.'),
             ['at', '12.7', '405', '0'], ['effects', ['font', ['size', '1.778', '1.778']], ['justify', 'left', 'bottom']],
             ['uuid', uid('notes')]]
    sch = ['kicad_sch', ['version', '20230121'], ['generator', 'eeschema'], ['uuid', Q(ROOT_UUID)], ['paper', Q('A2')],
           ['title_block', ['title', Q('SafeBuck-80  -  80 W protected buck-boost (LT8390 + LM74930)')],
            ['date', Q(datetime.date(2026, 11, 18).isoformat())], ['rev', Q('1.0')],
            ['comment', '1', Q('9-36 V in, 1.5-36 V / 0.9-8.3 A out (CV + CC), 65 x 48 mm, 2-layer 2 oz')],
            ['comment', '2', Q('Wrong wiring on input or output only lights a red LED')]],
           ['lib_symbols'] + libsyms] + [e for grp in items for e in grp] + texts + [notes] + \
          [['sheet_instances', ['path', Q('/'), ['page', Q('1')]]]]
    path = os.path.join(KDIR, PROJECT + '.kicad_sch')
    open(path, 'w').write(dump(sch) + '\n')
    lib = ['kicad_symbol_lib', ['version', '20220914'], ['generator', 'kicad_symbol_editor']] + \
          [parse(dump(CUSTOM[k]))[0] for k in CUSTOM]
    open(os.path.join(KDIR, 'SafeBuck.kicad_sym'), 'w').write(dump(lib) + '\n')
    open(os.path.join(KDIR, 'sym-lib-table'), 'w').write(
        '(sym_lib_table\n  (version 7)\n  (lib (name "SafeBuck")(type "KiCad")(uri "${KIPRJMOD}/SafeBuck.kicad_sym")(options "")(descr "SafeBuck-80 project symbols"))\n)\n')
    open(os.path.join(KDIR, 'fp-lib-table'), 'w').write(
        '(fp_lib_table\n  (version 7)\n  (lib (name "SafeBuck")(type "KiCad")(uri "${KIPRJMOD}/SafeBuck.pretty")(options "")(descr "SafeBuck-80 project footprints"))\n)\n')
    print('wrote', path, 'symbols used:', len(used))
    return path

if __name__ == '__main__':
    write()
