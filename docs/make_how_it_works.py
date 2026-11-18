"""
SafeBuck-80 — "Sohoj bhashay" explainer PDF (Banglish):
  * buck / boost / buck-boost kivabe kaj kore (chobi + example number)
  * component er chehara chena (package drawings)
  * board map: kon part kothay + protiti part ki kaj kore, value keno, na thakle ki hoto
  * vul connection e kon part bachay, design ta kivabe banano holo
Output: docs/src/how_it_works.html -> docs/SafeBuck-80_How_It_Works.pdf
Run:    python3 docs/make_how_it_works.py   (needs node + Playwright, see print_pdf.js)
"""
import os, sys, json, html, base64, subprocess
DOCS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(DOCS)
sys.path.insert(0, os.path.join(ROOT, 'hardware'))
from netlist import PARTS
E = html.escape
R = json.load(open(os.path.join(ROOT, 'calc', 'results.json')))
POS = {p['ref']: p for p in json.load(open(os.path.join(DOCS, 'img', 'part_positions.json')))['parts']}
BYREF = {p['ref']: p for p in PARTS}
IMG_W, IMG_H, BW, BH = 1600, 1200, 72.0, 54.0
S = IMG_W / BW
BOARD = base64.b64encode(open(os.path.join(DOCS, 'img', 'board_top_render.jpg'), 'rb').read()).decode()

# ----------------------------------------------------------------------------- small SVG helpers
OR, BL, GR, RD, GY = '#e8590c', '#1c7ed6', '#2f9e44', '#c92a2a', '#868e96'
def sw_h(x1, x2, y, on, lab, c='#222'):
    s = f'<circle cx="{x1}" cy="{y}" r="3.5" fill="{c}"/><circle cx="{x2}" cy="{y}" r="3.5" fill="{c}"/>'
    s += (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{c}" stroke-width="3"/>' if on else
          f'<line x1="{x1}" y1="{y}" x2="{x2-6}" y2="{y-22}" stroke="{c}" stroke-width="3"/>')
    st = 'ON' if on else 'OFF'
    return s + f'<text x="{(x1+x2)/2}" y="{y-28}" class="l">{lab}</text><text x="{(x1+x2)/2}" y="{y+20}" class="st {st}">{st}</text>'
def sw_v(x, y1, y2, on, lab, c='#222'):
    s = f'<circle cx="{x}" cy="{y1}" r="3.5" fill="{c}"/><circle cx="{x}" cy="{y2}" r="3.5" fill="{c}"/>'
    s += (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{c}" stroke-width="3"/>' if on else
          f'<line x1="{x}" y1="{y2}" x2="{x-22}" y2="{y1+6}" stroke="{c}" stroke-width="3"/>')
    st = 'ON' if on else 'OFF'
    return s + f'<text x="{x+10}" y="{(y1+y2)/2-2}" class="l" text-anchor="start">{lab}</text><text x="{x+10}" y="{(y1+y2)/2+14}" class="st {st}" text-anchor="start">{st}</text>'
def coil(x, y, n=4, w=24, lab='L'):
    d = f'M{x},{y} ' + ' '.join(f'a{w/2},{w/2} 0 0 1 {w},0' for _ in range(n))
    return f'<path d="{d}" fill="none" stroke="#222" stroke-width="3"/><text x="{x+n*w/2}" y="{y-20}" class="l">{lab}</text>'
def cap(x, y1, y2, lab='C'):
    m = (y1 + y2) / 2
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{m-5}" class="wr"/><line x1="{x}" y1="{m+5}" x2="{x}" y2="{y2}" class="wr"/>'
            f'<line x1="{x-14}" y1="{m-5}" x2="{x+14}" y2="{m-5}" stroke="#222" stroke-width="3"/><line x1="{x-14}" y1="{m+5}" x2="{x+14}" y2="{m+5}" stroke="#222" stroke-width="3"/>'
            f'<text x="{x+18}" y="{m+4}" class="l" text-anchor="start">{lab}</text>')
def load(x, y1, y2, lab='Load'):
    m = (y1 + y2) / 2
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{m-22}" class="wr"/><line x1="{x}" y1="{m+22}" x2="{x}" y2="{y2}" class="wr"/>'
            f'<rect x="{x-16}" y="{m-22}" width="32" height="44" rx="4" fill="#fff" stroke="#222" stroke-width="2"/><text x="{x}" y="{m+4}" class="l s">{lab}</text>')
def batt(x, y1, y2, lab):
    m = (y1 + y2) / 2
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{m-6}" class="wr"/><line x1="{x}" y1="{m+6}" x2="{x}" y2="{y2}" class="wr"/>'
            f'<line x1="{x-16}" y1="{m-6}" x2="{x+16}" y2="{m-6}" stroke="#222" stroke-width="3"/><line x1="{x-8}" y1="{m+6}" x2="{x+8}" y2="{m+6}" stroke="#222" stroke-width="5"/>'
            f'<text x="{x-22}" y="{m-12}" class="l" text-anchor="end">+</text><text x="{x-22}" y="{m+4}" class="l" text-anchor="end">{lab}</text>')
def hl(d, c=OR):
    return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="11" stroke-opacity=".35" stroke-linejoin="round"/><path d="{d}" fill="none" stroke="{c}" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#ar{c[1:]})"/>'
def svg(w, h, body, cls='dg'):
    marks = ''.join(f'<marker id="ar{c[1:]}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for c in (OR, BL, GR, RD))
    return f'<svg class="{cls}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg"><defs>{marks}</defs>{body}</svg>'

def buck(phase):
    a_on, b_on = phase == 1, phase == 2
    b = batt(50, 50, 200, '24 V') + f'<path d="M50,50 H120 M170,50 H220 M318,50 H400 V200 H50" class="wr"/><path d="M220,50 V95 M220,160 V200 M400,50 H470 V95 M470,150 V200 H400" class="wr"/>'
    b += sw_h(120, 170, 50, a_on, 'A (Q3)') + sw_v(220, 95, 160, b_on, 'B (Q4)') + coil(222, 50, 4, 24, 'L1') + cap(400, 50, 200, 'C') + load(470, 95, 150 + 0, '12 V')
    if phase == 1:
        b += hl('M50,185 V50 H120 M170,50 H220 M318,50 H470 V150 M470,200 H50')
        b += '<text x="260" y="224" class="nt">L1 e current <tspan fill="#e8590c">barche</tspan> — shakti jomche</text>'
    else:
        b += hl('M470,200 H220 V160 M220,95 V50 H318 M318,50 H470 V150')
        b += '<text x="260" y="224" class="nt">L1 nijer jomano shakti diye <tspan fill="#e8590c">current chalu rakhe</tspan></text>'
    return svg(520, 236, b)

def boost(phase):
    c_on, d_on = phase == 1, phase == 2
    b = batt(50, 50, 200, '12 V') + '<path d="M50,50 H90 M188,50 H230 M300,50 H360 V200 H50 M230,50 V95 M230,160 V200 M360,50 H450 V95 M450,150 V200 H360" class="wr"/>'
    b += coil(92, 50, 4, 24, 'L1') + sw_v(230, 95, 160, c_on, 'C (Q5)') + sw_h(250, 300, 50, d_on, 'D (Q6)') + cap(360, 50, 200, 'C') + load(450, 95, 150, '24 V')
    b += '<path d="M230,50 H250" class="wr"/>'
    if phase == 1:
        b += hl('M50,185 V50 H230 V200 H50') + hl('M360,90 H450 V150', BL)
        b += '<text x="260" y="224" class="nt">L1 charge hocche · load chalay <tspan fill="#1c7ed6">C</tspan></text>'
    else:
        b += hl('M50,185 V50 H300 M300,50 H450 V150 M450,200 H50')
        b += '<text x="260" y="224" class="nt">input + L1 <tspan fill="#e8590c">eksathe</tspan> dhakka dey → beshi volt</text>'
    return svg(520, 236, b)

def wave():
    T = 120; x0 = 60
    sq, tri = '', ''
    for k in range(3):
        a = x0 + k * T
        sq += f'L{a},40 L{a+T/2},40 L{a+T/2},95 L{a+T},95 '
        tri += f'L{a+T/2},140 L{a+T},180 '
    b = f'<path d="M{x0},95 {sq}" fill="none" stroke="{OR}" stroke-width="2.5"/>'
    b += f'<path d="M{x0},180 {tri}" fill="none" stroke="{BL}" stroke-width="2.5"/><line x1="{x0}" y1="160" x2="{x0+3*T}" y2="160" stroke="{BL}" stroke-dasharray="5 4"/>'
    b += f'<text x="{x0-6}" y="44" class="l" text-anchor="end">24 V</text><text x="{x0-6}" y="99" class="l" text-anchor="end">0 V</text>'
    b += f'<text x="{x0-6}" y="144" class="l" text-anchor="end">7.67 A</text><text x="{x0-6}" y="164" class="l" text-anchor="end">6.67</text><text x="{x0-6}" y="184" class="l" text-anchor="end">5.67 A</text>'
    b += f'<text x="{x0+T/4}" y="32" class="l s">A on</text><text x="{x0+3*T/4}" y="32" class="l s">B on</text>'
    b += f'<path d="M{x0},200 H{x0+T}" stroke="#222" marker-end="url(#ar{RD[1:]})"/><text x="{x0+T/2}" y="216" class="l s">1 cycle = 3.33 µs (300 kHz)</text>'
    b += f'<text x="{x0+3*T+12}" y="70" class="l" text-anchor="start" fill="{OR}">SW node (switch er majhkhane)</text>'
    b += f'<text x="{x0+3*T+12}" y="150" class="l" text-anchor="start" fill="{BL}">L1 current (triangle)</text><text x="{x0+3*T+12}" y="166" class="l s" text-anchor="start" fill="{BL}">dash = gor 6.67 A = output</text>'
    return svg(640, 225, b)

def pwm():
    b = ''
    for i, (d, v) in enumerate(((0.25, 6), (0.5, 12), (0.75, 18))):
        y = 20 + i * 62; T = 100; p = f'M60,{y+40} '
        for k in range(4):
            a = 60 + k * T
            p += f'L{a},{y} L{a+d*T},{y} L{a+d*T},{y+40} L{a+T},{y+40} '
        b += f'<path d="{p}" fill="none" stroke="{OR}" stroke-width="2"/>'
        ya = y + 40 - 40 * d
        b += f'<line x1="60" y1="{ya}" x2="460" y2="{ya}" stroke="{BL}" stroke-width="2.5" stroke-dasharray="6 4"/>'
        b += f'<text x="52" y="{y+24}" class="l" text-anchor="end">{int(d*100)} %</text><text x="470" y="{ya+5}" class="l" text-anchor="start" fill="{BL}">gor = {v} V</text>'
    return svg(560, 205, b)

def fourswitch():
    b = batt(40, 60, 230, 'VIN') + '<path d="M40,60 H100 M150,60 H190 M190,60 V110 M190,175 V230 M190,60 H220 M268,60 H300 M396,60 H440 M440,60 V110 M440,175 V230 M440,60 H470 M520,60 H580 V230 H40 M580,60 H640 V120 M640,170 V230 H580" class="wr"/>'
    b += sw_h(100, 150, 60, True, 'A · Q3', '#444') + sw_v(190, 110, 175, False, 'B · Q4', '#444') + sw_v(440, 110, 175, False, 'C · Q5', '#444') + sw_h(470, 520, 60, True, 'D · Q6', '#444')
    b += f'<rect x="220" y="50" width="48" height="20" rx="3" fill="#fff" stroke="#222" stroke-width="2"/><text x="244" y="64" class="l s">R15</text><text x="244" y="40" class="l s">3 mΩ</text>'
    b += coil(300, 60, 4, 24, 'L1 10 µH') + cap(580, 60, 230, 'Cout') + load(640, 120, 170, 'Load')
    b += '<text x="70" y="150" class="l s" text-anchor="start">Cin</text><text x="300" y="215" class="nt">buck "half" (A,B) — L1 — boost "half" (C,D)</text>'
    b += '<text x="40" y="250" class="l s" text-anchor="start">(chobi: switch er ekta obostha dekhano; asol obostha mode onujayi bodlay — nicher table)</text>'
    return svg(700, 260, b)

def loop():
    def box(x, y, w, h, t1, t2='', c='#0d3b66'):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#fff" stroke="{c}" stroke-width="2"/><text x="{x+w/2}" y="{y+h/2-(4 if t2 else -4)}" class="l">{t1}</text>' + (f'<text x="{x+w/2}" y="{y+h/2+13}" class="l s">{t2}</text>' if t2 else '')
    b = box(10, 15, 170, 46, 'RV1 + R25 (CV knob)', 'output volt er tukro → FB') + box(10, 85, 170, 46, 'R31 12 mΩ', 'output current → ISP/ISN') + box(10, 155, 170, 46, 'R15 3 mΩ', 'L1 current → LSP/LSN')
    b += box(250, 60, 190, 96, 'U1 · LT8390', '') + '<text x="345" y="122" class="l s">FB = 1.00 V rakhte chay</text><text x="345" y="138" class="l s">current ≤ CC limit (RV2)</text>'
    b += box(510, 60, 150, 96, 'Gate drive', 'TG1 BG1 BG2 TG2') + '<text x="585" y="140" class="l s">→ Q3 Q4 Q5 Q6</text>'
    for y in (38, 108, 178):
        b += f'<path d="M180,{y} H215 V108 H245" fill="none" stroke="{BL}" stroke-width="2" marker-end="url(#ar{BL[1:]})"/>'
    b += f'<path d="M440,108 H505" stroke="{OR}" stroke-width="2.5" marker-end="url(#ar{OR[1:]})"/><text x="472" y="98" class="l s">duty</text>'
    b += f'<path d="M585,156 V205 H95 V201" fill="none" stroke="{GY}" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#ar{RD[1:]})"/><text x="345" y="222" class="l s">output bodlay → abar mapa hoy (300,000 bar / second)</text>'
    return svg(680, 230, b)

def blocks():
    items = [('INPUT', 'J1 · F1 · D1', '9–36 V'), ('DARWAN', 'U2 + Q1 · Q2', 'ulta / OV / UV'), ('CONVERTER', 'U1 + Q3–Q6 + L1', 'buck · boost'),
             ('MAPA', 'R31 · F2', 'CC current'), ('OUTPUT GUARD', 'Q7 + Q8–Q11', 'ulta battery'), ('OUTPUT', 'J2', '1.6–36 V · ≤8.33 A')]
    b = ''
    for i, (t, s1, s2) in enumerate(items):
        x = 8 + i * 113
        b += f'<rect x="{x}" y="10" width="100" height="74" rx="8" fill="#eef3f9" stroke="#0d3b66" stroke-width="2"/><text x="{x+50}" y="32" class="l">{t}</text><text x="{x+50}" y="52" class="l s">{s1}</text><text x="{x+50}" y="70" class="l s">{s2}</text>'
        if i < 5: b += f'<path d="M{x+100},47 H{x+111}" stroke="{OR}" stroke-width="3" marker-end="url(#ar{OR[1:]})"/>'
    return svg(690, 95, b)

# ----------------------------------------------------------------------------- package drawings
def pkg(kind):
    k = kind; b = ''
    if k == 'res':   b = '<rect x="35" y="25" width="50" height="26" fill="#1e1e1e"/><rect x="30" y="25" width="9" height="26" fill="#cfd4da"/><rect x="81" y="25" width="9" height="26" fill="#cfd4da"/><text x="60" y="43" fill="#fff" font-size="11" text-anchor="middle">103</text>'
    if k == 'shunt': b = '<rect x="12" y="24" width="96" height="30" fill="#2b2b2b"/><rect x="8" y="24" width="20" height="30" fill="#cfd4da"/><rect x="92" y="24" width="20" height="30" fill="#cfd4da"/><text x="60" y="44" fill="#fff" font-size="11" text-anchor="middle">R003</text>'
    if k == 'mlcc':  b = '<rect x="35" y="22" width="50" height="32" fill="#b08a5a"/><rect x="30" y="22" width="10" height="32" fill="#cfd4da"/><rect x="80" y="22" width="10" height="32" fill="#cfd4da"/>'
    if k == 'elec':  b = '<rect x="30" y="8" width="60" height="60" fill="#222"/><circle cx="60" cy="38" r="27" fill="#d6d9dc" stroke="#999"/><path d="M60,11 A27,27 0 0 0 60,65 Z" fill="#333"/><text x="74" y="42" font-size="12" text-anchor="middle">+</text>'
    if k == 'ind':   b = '<rect x="28" y="6" width="64" height="64" rx="6" fill="#4a4d52"/><text x="60" y="43" fill="#ddd" font-size="12" text-anchor="middle">103</text>'
    if k == 'fet':   b = '<rect x="35" y="14" width="50" height="46" rx="2" fill="#1e1e1e"/><circle cx="42" cy="21" r="2.5" fill="#888"/>' + ''.join(f'<rect x="{38+i*12}" y="60" width="7" height="8" fill="#cfd4da"/>' for i in range(4)) + '<rect x="38" y="6" width="44" height="8" fill="#cfd4da"/>'
    if k == 'sot':   b = '<rect x="44" y="24" width="32" height="24" fill="#1e1e1e"/><rect x="56" y="14" width="8" height="10" fill="#cfd4da"/><rect x="46" y="48" width="8" height="10" fill="#cfd4da"/><rect x="66" y="48" width="8" height="10" fill="#cfd4da"/><text x="60" y="40" fill="#fff" font-size="9" text-anchor="middle">1AM</text>'
    if k == 'diode': b = '<rect x="44" y="27" width="32" height="20" fill="#1e1e1e"/><rect x="47" y="27" width="5" height="20" fill="#ddd"/><rect x="34" y="33" width="10" height="8" fill="#cfd4da"/><rect x="76" y="33" width="10" height="8" fill="#cfd4da"/>'
    if k == 'tvs':   b = '<rect x="30" y="20" width="60" height="36" fill="#1e1e1e"/><rect x="20" y="30" width="10" height="16" fill="#cfd4da"/><rect x="90" y="30" width="10" height="16" fill="#cfd4da"/><text x="60" y="43" fill="#fff" font-size="9" text-anchor="middle">band nai</text>'
    if k == 'led':   b = '<rect x="40" y="26" width="40" height="24" fill="#f1f3f5" stroke="#aaa"/><circle cx="60" cy="38" r="7" fill="#e03131"/><rect x="36" y="26" width="6" height="24" fill="#cfd4da"/><rect x="78" y="26" width="6" height="24" fill="#cfd4da"/>'
    if k == 'fuse':  b = '<rect x="26" y="24" width="68" height="28" fill="#efe6cf" stroke="#b9ad8f"/><rect x="22" y="24" width="12" height="28" fill="#cfd4da"/><rect x="86" y="24" width="12" height="28" fill="#cfd4da"/><text x="60" y="42" font-size="9" text-anchor="middle">F 15</text>'
    if k == 'pot':   b = '<rect x="30" y="12" width="60" height="50" rx="3" fill="#1f5fbf"/><circle cx="76" cy="24" r="8" fill="#d4a017"/><line x1="70" y1="24" x2="82" y2="24" stroke="#5c4400" stroke-width="2"/><text x="52" y="48" fill="#fff" font-size="10" text-anchor="middle">204</text>'
    if k == 'term':  b = '<rect x="18" y="12" width="84" height="54" rx="3" fill="#2f9e44"/><circle cx="40" cy="39" r="12" fill="#c0c4c8"/><circle cx="80" cy="39" r="12" fill="#c0c4c8"/><line x1="32" y1="39" x2="48" y2="39" stroke="#555" stroke-width="3"/><line x1="72" y1="39" x2="88" y2="39" stroke="#555" stroke-width="3"/>'
    if k == 'tssop': b = '<rect x="40" y="6" width="40" height="64" fill="#1e1e1e"/><circle cx="47" cy="13" r="2.5" fill="#888"/>' + ''.join(f'<rect x="32" y="{9+i*4.3}" width="8" height="2.4" fill="#cfd4da"/><rect x="80" y="{9+i*4.3}" width="8" height="2.4" fill="#cfd4da"/>' for i in range(14)) + '<text x="60" y="42" fill="#fff" font-size="9" text-anchor="middle" transform="rotate(-90 60 40)">LT8390</text>'
    if k == 'qfn':   b = '<rect x="38" y="16" width="44" height="44" fill="#1e1e1e"/><circle cx="44" cy="22" r="2.5" fill="#888"/>' + ''.join(f'<rect x="{42+i*6.4}" y="58" width="3" height="3" fill="#cfd4da"/><rect x="{42+i*6.4}" y="15" width="3" height="3" fill="#cfd4da"/>' for i in range(6))
    if k == 'tp':    b = '<circle cx="60" cy="38" r="16" fill="#c9a227"/><circle cx="60" cy="38" r="8" fill="#e6c34d"/>'
    if k == 'hole':  b = '<circle cx="60" cy="38" r="24" fill="#c9a227"/><circle cx="60" cy="38" r="15" fill="#fff" stroke="#999"/>'
    if k == 'tie':   b = '<rect x="22" y="28" width="22" height="20" fill="#c9a227"/><rect x="76" y="28" width="22" height="20" fill="#c9a227"/><rect x="44" y="35" width="32" height="6" fill="#c9a227"/>'
    return f'<svg class="pk" viewBox="0 0 120 76">{b}</svg>'

PKGS = [
    ('res', 'Chip resistor', '0402–1206 size · kalo upor, dui mathay sada/rupali', 'Upore number code thake (103 = 10 kΩ, 01C ityadi). 0402 er moto khub chhoto gulay kichu lekha thake na.', 'R1–R47 (beshirbhag), TH1 (PTC dekhte same)'),
    ('shunt', 'Current-sense resistor (2512)', 'boro lomba resistor, 6.3 × 3.2 mm', 'Milli-ohm value — R003 = 3 mΩ, R012 = 12 mΩ. Etar upor diye main current jay.', 'R15, R31'),
    ('mlcc', 'Ceramic capacitor (MLCC)', 'badami/dhusor chhoto block', 'Kono lekha thake na! Value janar upay BOM ar board er silkscreen ref (C7, C12 …).', 'C1–C5, C7, C8, C12–C14, C19–C36 …'),
    ('elec', 'Electrolytic / hybrid capacitor', 'rupali can, kalo plastic base', 'Upore kalo ardhek-chand = minus (−) side. Ulta lagale fete jete pare.', 'C11 (100 µF), C18 (47 µF)'),
    ('ind', 'Power inductor', 'boro dhusor square (15 × 15 mm)', 'Board er sobcheye boro part. "103" = 10 µH.', 'L1'),
    ('fet', 'Power MOSFET (5 × 6 mm)', 'kalo chapta, ek pashe 4 pa, onno pashe boro tab', 'Kone chhoto dot = pin 1. Upore part number (CSD18532 / CSD19532).', 'Q1–Q7'),
    ('sot', 'SOT-23 (3 pa)', 'chhoto kalo, 1 pa upore 2 pa niche', 'Ek-i chehara te transistor, diode ba zener hote pare — upore 2–3 akkhorer code.', 'Q8–Q11, D2–D7, D10'),
    ('diode', 'Chhoto diode (SOD-323/523/128)', 'kalo, ek mathay dag (band)', 'Dag/band = cathode (−). Dag er dik silkscreen er sathe milate hoy.', 'D8, D9, D11–D17, D15 (boro)'),
    ('tvs', 'TVS diode (SMB)', 'boro kalo, dui pashe pa', 'SMBJ60CA bidirectional — tai kono band nai, je dike-i lagano jay.', 'D1'),
    ('led', 'LED (0805)', 'sada/sossho, majhe rong', 'Niche/upore sobuj dag ba T chinho = cathode.', 'LED1 sobuj, LED2/LED3 lal'),
    ('fuse', 'SMD fuse (NANO2)', 'ceramic body, rupali matha', 'Upore amp lekha (15 / 10). Normal fault e kokhono kete na.', 'F1 15 A, F2 10 A'),
    ('pot', 'Trimpot 3296W (25-turn)', 'nil box, upore pitoler screw', '204 = 200 kΩ (CV), 503 = 50 kΩ (CC). 25 bar ghurale ek matha theke onno matha.', 'RV1 (CV), RV2 (CC)'),
    ('term', 'Screw terminal 5.08 mm', 'plastic block, upore screw', 'Board er kinare, tar dhukano mukh baire. Silkscreen e + / − lekha.', 'J1 input, J2 output'),
    ('tssop', 'IC — TSSOP-28', 'kalo lomba, dui pashe 14 ta kore pa', 'Niche boro metal pad (gorom ber korar jonno). Dot = pin 1.', 'U1 LT8390'),
    ('qfn', 'IC — QFN-24 (4 × 4 mm)', 'chhoto kalo square, kono pa beriye nei', 'Pad gulo niche-r kinare; chokhe solder dekha kothin — JLC assembly kore.', 'U2 LM74930'),
    ('tp', 'Test point', 'gol copper pad', 'Multimeter er probe ekhane dhorbe.', 'TP1 (ISMON)'),
    ('tie', 'Net-tie', 'shudhu copper er akar — kono component na', 'Duita net ke thik ek jaygay jore (Kelvin sense). Kinte hoy na, BOM e nai.', 'NT1–NT4'),
    ('hole', 'Mounting hole M3', 'gol foto', 'Screw/standoff diye board atkano + heatsink lagano.', 'H1, H2, H3'),
]

# ----------------------------------------------------------------------------- board maps
def bbox_px(ref):
    p = POS[ref]; x0, y0, x1, y1 = p['box']
    return x0 * S, y0 * S, x1 * S, y1 * S
def board_map(refs, color=OR, title='', full=False, maxh_mm=105):
    boxes = [bbox_px(r) for r in refs if r in POS]
    if full:
        cx0, cy0, cx1, cy1 = 0, 0, IMG_W, IMG_H
    else:
        cx0 = max(0, min(b[0] for b in boxes) - 70); cy0 = max(0, min(b[1] for b in boxes) - 70)
        cx1 = min(IMG_W, max(b[2] for b in boxes) + 70); cy1 = min(IMG_H, max(b[3] for b in boxes) + 70)
        if cx1 - cx0 < 600: m = (600 - (cx1 - cx0)) / 2; cx0, cx1 = max(0, cx0 - m), min(IMG_W, cx1 + m)
        if cy1 - cy0 < 380: m = (380 - (cy1 - cy0)) / 2; cy0, cy1 = max(0, cy0 - m), min(IMG_H, cy1 + m)
    w, h = cx1 - cx0, cy1 - cy0
    disp_w = min(184.0, maxh_mm * w / h)
    fs = w / disp_w * 2.9               # ~2.9 mm tall labels
    hole = ''.join(f'<rect x="{b[0]-4}" y="{b[1]-4}" width="{b[2]-b[0]+8}" height="{b[3]-b[1]+8}" rx="4" fill="#000"/>' for b in boxes)
    mid = f'm{abs(hash(tuple(refs))) % 10**8}'
    o = f'<defs><mask id="{mid}"><rect x="0" y="0" width="{IMG_W}" height="{IMG_H}" fill="#fff"/>{hole}</mask></defs>'
    o += f'<use href="#board"/><rect x="0" y="0" width="{IMG_W}" height="{IMG_H}" fill="#000" fill-opacity=".55" mask="url(#{mid})"/>'
    o += ''.join(f'<rect x="{b[0]-4}" y="{b[1]-4}" width="{b[2]-b[0]+8}" height="{b[3]-b[1]+8}" rx="4" fill="none" stroke="{color}" stroke-width="{fs*0.16:.1f}"/>' for b in boxes)
    placed = []
    def clash(r):
        if r[0] < cx0 or r[2] > cx1 or r[1] < cy0 or r[3] > cy1: return True
        return any(not (r[2] < q[0] or r[0] > q[2] or r[3] < q[1] or r[1] > q[3]) for q in placed)
    for ref, b in zip([r for r in refs if r in POS], boxes):
        tw, th = fs * 0.62 * len(ref) + fs * 0.5, fs * 1.25
        bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        cands = [(bx - tw / 2, b[1] - th - 6), (bx - tw / 2, b[3] + 6), (b[2] + 6, by - th / 2), (b[0] - tw - 6, by - th / 2),
                 (b[2] + 6, b[1] - th), (b[0] - tw - 6, b[3]), (bx - tw / 2, b[1] - 2 * th - 8), (bx - tw / 2, b[3] + th + 8)]
        pick = next((c for c in cands if not clash((c[0], c[1], c[0] + tw, c[1] + th))), cands[0])
        placed.append((pick[0], pick[1], pick[0] + tw, pick[1] + th))
        o += (f'<rect x="{pick[0]:.0f}" y="{pick[1]:.0f}" width="{tw:.0f}" height="{th:.0f}" rx="{fs*0.25:.0f}" fill="{color}"/>'
              f'<text x="{pick[0]+tw/2:.0f}" y="{pick[1]+th*0.78:.0f}" font-size="{fs:.0f}" font-weight="700" fill="#fff" text-anchor="middle" font-family="DejaVu Sans">{ref}</text>')
    cap_ = f'<figcaption>{E(title)}</figcaption>' if title else ''
    return f'<figure class="map"><svg viewBox="{cx0:.0f} {cy0:.0f} {w:.0f} {h:.0f}" style="width:{disp_w:.0f}mm">{o}</svg>{cap_}</figure>'

def overview_map():
    o = '<use href="#board"/><rect width="1600" height="1200" fill="#000" fill-opacity=".25"/>'
    for name, refs, c in BLOCKS:
        for r in refs:
            if r in POS:
                b = bbox_px(r)
                o += f'<rect x="{b[0]-3}" y="{b[1]-3}" width="{b[2]-b[0]+6}" height="{b[3]-b[1]+6}" rx="4" fill="{c}" fill-opacity=".55" stroke="{c}" stroke-width="4"/>'
    leg = ''.join(f'<span class="lg"><i style="background:{c}"></i>{E(n)}</span>' for n, _, c in BLOCKS)
    return f'<figure class="map"><svg viewBox="0 0 1600 1200" style="width:184mm">{o}</svg><figcaption>{leg}</figcaption></figure>'

# ----------------------------------------------------------------------------- part cards
# (refs, what it physically is, value, ki kaj kore, value keno, na thakle ki hoto)
def C(refs, kind, value, kaj, keno, na): return dict(refs=refs.split(), kind=kind, value=value, kaj=kaj, keno=keno, na=na)
ff = R['front_end']['ladder']
GROUPS = [
 ('A', 'Input: tar lagano, fuse, spike chhakni', '#f08c00', [
  C('J1', 'Screw terminal', '5.08 mm, 2 pin', 'Input er tar (9–36 V) ekhane lage. Silkscreen e + ar − lekha.', '18 A rated, tar er mukh board er kinare baire dike — tar lagate shubidha.', 'Tar solder korte hoto, khulte-lagate jhamela.'),
  C('F1', 'Fuse (NANO2)', '15 A, 65 V', 'Sesh rokkha-kobach. Shudhu kono MOSFET puro short hoye gele kete jay.', 'Sobcheye beshi input current 9.5 A (9 V → 35 V, 80 W). 15 A > 1.4 × 9.5 A — normal kaje kokhono kate na.', 'Kono part short hoye gele battery/supply puro current dhalto → tar gorom, agun.'),
  C('D1', 'TVS diode (bidirectional)', 'SMBJ60CA', 'Hothat asha spike (tar khola-lagano, motor er kick) ke 96.8 V er niche kete dey.', '60 V porjonto chup (dui dike-i), tai input ulta dileo conduct kore na. 96.8 V < Q1/Q2 er 100 V.', 'Ekta boro spike e Q1/Q2/U2 nosto hote parto.'),
  C('R1 C1', 'Resistor + ceramic capacitor (snubber)', '1 Ω + 2.2 µF', 'Lomba tar + ceramic capacitor mile "dolna" (LC ringing) toiri kore — hot-plug e voltage 2 gun porjonto lafate pare. R1 ei dolna thamay.', '1 Ω pray tar er impedance er soman → sobcheye bhalo damping.', 'Plug korar muhurte voltage lafiye U2/LT8390 er limit par hote parto.'),
  C('C2', 'Ceramic capacitor', '100 nF 100 V', 'U2 er input pin er pashe chhoto "local battery" — noise shushe ney.', 'Datasheet minimum 0.1 µF.', 'U2 er sense e noise dhuke vul trip korte parto.'),
 ]),
 ('B', 'Input darwan: LM74930 + Q1 / Q2', '#e64980', [
  C('U2', 'IC (QFN-24) — ideal-diode + switch controller', 'LM74930-Q1', 'Input er darwan. Ulta polarity hole Q2 bondho, voltage beshi/kom hole Q1 bondho, plug korar somoy dhire dhire on (inrush komay). Fault hole FLT pin → lal IN LED.', '−65 V porjonto ulta voltage sojjo kore; dui MOSFET (back-to-back) chalate pare.', 'Ulta tar dile sorasori LT8390 ar MOSFET pure jeto.'),
  C('Q1 Q2', 'Power MOSFET (100 V)', 'CSD19532Q5B', 'Q2 = "ideal diode": shudhu thik dike current jete dey. Q1 = on/off gate: OV/UV hole kete dey. Duita mukhomukhi (source-source) — karon protiti MOSFET er bhitore ekta diode ache, ekta diye dui dik atkano jay na.', '100 V: TVS clamp 96.8 V er upore. Sadharon diode hole 9.5 A × 0.5 V = 4.75 W gorom; dui FET e mot ~1 W.', 'Ulta polarity/over-voltage atkano jeto na, ba diode diye korle onek gorom.'),
  C('D2 R3 D3 C3', 'Diode + resistor + 62 V zener + capacitor', 'BAS21 · 1 kΩ · BZX84C62 · 1 µF', 'U2 er VS (power) pin ke khaoyay. D2 ulta voltage atkay, D3 voltage ke 62 V er niche rakhe (pin limit 70 V), R3 zener er current simito kore, C3 filter.', 'Datasheet: VS e minimum 1 µF; 62 V zener D1 spike er somoy pin bachay.', 'Spike e U2 er VS pin pure jete parto.'),
  C('C4', 'Ceramic capacitor', '220 nF 50 V', 'Charge-pump capacitor: U2 eta diye input er cheye ~14 V beshi voltage banay — N-MOSFET on korte gate ke source er upore tulte hoy.', 'Q1 + Q2 er gate capacitance er ≥10 gun (74 nF dorkar); 50 V = across voltage er 2 gun+.', 'Q1/Q2 kokhono on hoto na — board e power-i ashto na.'),
  C('R4 C5', 'Resistor + capacitor (CdVdT)', '100 Ω + 3.3 nF', 'Plug korar somoy Q1 er gate dhire dhire othay → output capacitor gulo dhire charge hoy.', f'Inrush {R["front_end"]["inrush"]["I_inrush"][0]:.1f}–{R["front_end"]["inrush"]["I_inrush"][2]:.1f} A, ramp {R["front_end"]["inrush"]["t_ramp_36V"]*1e3:.1f} ms. R4 bondho howa druto rakhe.', 'Plug korlei spark, boro current spike — connector/fuse er khoti.'),
  C('D17', '15 V zener', 'MM3Z15V', 'Chalu obosthay input short hole C5 Q1 er gate charge dhore rakhe; zener gate-source ke 15 V er niche rakhe.', 'Q1 er VGS limit 20 V; TI reference circuit er DZ1.', 'Oi bises fault e Q1 er gate fete jete parto.'),
  C('C35', 'Ceramic capacitor', '1 µF 100 V', 'Q1–Q2 er majher (common source) node ke sthir rakhe.', 'TI LM74930 datasheet er reference (CCS).', 'Switching er somoy U2 vul bujhte parto.'),
  C('R5 R6 R7', '1 % resistor ladder', '280 kΩ · 17.8 kΩ · 4.22 kΩ', 'Input voltage er tukro U2 er UVLO ar OV pin e dey — U2 "mepe" sidhanto ney.', f'UV: {ff["uv_fall"]:.1f} V e bondho / {ff["uv_rise"]:.1f} V e chalu. OV: {ff["ov_rise"]:.1f} V e bondho / {ff["ov_fall"]:.1f} V e abar chalu — 36 V supply sobsomoy chole, 60 V er onek niche kate.', 'Voltage beshi hole LT8390 (60 V max) pure jeto; kom hole MOSFET adha-on hoye gorom hoto.'),
 ]),
 ('C', 'Lal IN LED: input fault / ulta input', '#c92a2a', [
  C('LED2', 'LED (lal)', 'RED IN', 'Input ulta, OV ba UV hole jole.', '~1 mA e bhalo dekha jay.', 'Board chup thakto, bujhte partena keno chalu hocche na.'),
  C('R11 R12', 'Resistor (1206)', '5.6 kΩ × 2', 'LED er current simito kore. Dui dik er path (thik + ulta) dutoi share kore.', 'Mot 11.2 kΩ: 12 V e 0.8 mA, 60 V e 5 mA; 1206 size 0.15 W ar 60 V sojjo kore.', 'LED sathe sathe pure jeto.'),
  C('D4 D6', 'Diode (BAS21)', 'BAS21', 'Thik polarity te fault path: VIN → D4 → R11/R12 → LED2 → D6 → U2 FLT pin (fault e GND kore dey) → LED jole.', 'D6 FLT pin ke negative voltage theke bachay.', 'FLT pin ulta voltage e nosto hote parto.'),
  C('D5 D7', 'Diode (BAS21)', 'BAS21', 'Ulta input path: GND (ekhon +) → D5 → R11/R12 → LED2 → D7 → VIN (ekhon −) — U2 er sahajjo charai LED jole.', 'BAS21 250 V, onek margin.', 'Ulta input dile LED jolto na — bujhtei parten na vul hoyeche.'),
 ]),
 ('D', 'Power stage: 4 switch + L1 + capacitor', '#1c7ed6', [
  C('Q3 Q4', 'Power MOSFET (60 V)', 'CSD18532Q5B', 'Q3 = switch A, Q4 = switch B — "buck half". Buck mode e era palakrome on-off kore.', '60 V (input sorbochcho 46 V e kete jay). Rds(on) max 4.3 mΩ → kom gorom; gate charge 19 nC → druto switch.', 'Converter hoto na.'),
  C('Q5 Q6', 'Power MOSFET (60 V)', 'CSD18532Q5B', 'Q5 = switch C, Q6 = switch D — "boost half". Boost mode e era palakrome kaj kore; buck mode e D sobsomoy on.', 'Q3/Q4 er moto same part — BOM chhoto, ek dhoroner 4 ta.', 'Input er cheye beshi output (boost) hoto na.'),
  C('L1', 'Power inductor', 'XAL1510 10 µH, Isat 26.3 A', 'Converter er "flywheel": switch on thakle shakti jomay, off hole chere dey. Current hothat bodlate dey na.', f'Peak current limit max {R["current_limit"]["max"]:.1f} A < Isat; ripple ~2 A; DCR 9 mΩ. 10 µH > slope-compensation minimum 4.25 µH.', 'Kono converter-i hoy na — switch gulo shudhu short kore pure jeto.'),
  C('R15 NT1 NT2', 'Current-sense resistor 2512 + net-tie', '3 mΩ 1 %', 'L1 er current mape: 10 A e 30 mV. U1 protiti cycle e dekhe, 11.7–21.7 A er beshi hote dey na.', 'Choto value → kom loss (0.2 W). Net-tie diye sense track thik resistor er pad theke ney (Kelvin) — boro current er copper drop maap vul kore na.', 'U1 current bujhto na → short e MOSFET/L1 pure jeto, ar peak-current-mode control chalto na.'),
  C('C7 C8', 'Ceramic capacitor (1210)', '10 µF 100 V X7S', 'Input side "hot loop": switch A er dhakka (pulse) current ekdom kach theke dey.', '100 V = 36 V er 2 gun+ (ceramic voltage barle capacitance haray). Q3–Q4 er thik pashe.', 'Switching noise, voltage spike, MOSFET er stress barto.'),
  C('C11', 'Electrolytic capacitor', '100 µF 63 V', 'Input er boro tank + damping: lomba tar ar ceramic er dolna thamay.', 'ESR 0.35 Ω ≈ tar er impedance 0.33 Ω (Middlebrook) → stable. 63 V > 43 V × 1.4.', 'Lomba tar e converter dolte (oscillate) parto.'),
  C('C12 C13 C14 C36', 'Ceramic capacitor (1210)', '10 µF 100 V X7S × 4', 'Output side "hot loop": boost mode e switch D diye pulse current ase, era shushe ney.', '100 V = 35 V er 2 gun+; 4 ta te RMS current bhag hoy (protiti 0.81 A).', 'Output e ripple/noise onek barto.'),
  C('C18', 'Hybrid polymer capacitor', '47 µF 50 V', 'Output er boro tank: ripple komay, load hothat bodlale voltage dhore rakhe.', 'ESR 30 mΩ; ripple sob khetre < 1 % (worst 136 mV @ 24 V). 50 V > 44 V (pot +10 % + OVP).', 'Load step e voltage dip/overshoot beshi hoto.'),
  C('C24 C25', 'Ceramic capacitor', '1 µF 16 V', 'Bootstrap: upore-r switch (A ar D) er gate ke SW node er upore tulte chhoto "lift battery". Low-side on thakle INTVCC theke charge hoy.', 'Gate charge er ≥100 gun (0.56 µF dorkar). U1 er pin er thik pashe.', 'Q3/Q6 kokhono puro on hoto na → gorom hoye nosto.'),
 ]),
 ('E', 'Brain: U1 LT8390 ar tar sathi', '#7048e8', [
  C('U1', 'IC (TSSOP-28) — 4-switch buck-boost controller', 'LT8390', 'Puro converter er brain: output voltage ar current mape, 4 ta MOSFET er gate e signal dey, buck/boost/buck-boost mode nije bodlay.', '60 V, CV + CC ek IC te, peak-current-mode (stable), ±15 % spread spectrum (EMI kom).', '—'),
  C('C19', 'Ceramic capacitor', '1 µF 100 V', 'U1 er VIN pin er bypass.', 'Pin 7 er pashe.', 'U1 noise e reset/vul kaj korte parto.'),
  C('R45 C20', 'Resistor + capacitor', '100 Ω + 1 µF', 'U1 er VOUT pin e filter; output negative hoye gele pin e current < 4 mA rakhe.', 'τ = 10 µs; pin nije < 60 µA ney.', 'Fault e VOUT pin nosto hote parto.'),
  C('C21 C22', 'Ceramic capacitor', '10 µF + 1 µF 16 V', 'INTVCC (U1 er bhitorer 5 V) — MOSFET gate chalanor shakti ekhan theke.', 'Datasheet min 4.7 µF; 10 µF X7R 5 V e-o > 4.7 µF thake.', 'Gate drive durbol → MOSFET gorom.'),
  C('C23', 'Ceramic capacitor', '470 nF', 'VREF (2.0 V reference) sthir rakhe — CTRL ar SS er ekhan theke voltage ney.', 'Datasheet 0.47 µF.', 'CC limit dolto.'),
  C('R20', '1 % resistor', '140 kΩ', 'Switching frequency thik kore: 300 kHz (±15 % spread).', 'Kom freq → switching loss kom; beshi freq → choto L. 300 kHz majhamajhi.', 'U1 chalu-i hoto na (RT pin dorkar).'),
  C('C28 R21', 'Capacitor + resistor', '220 nF + 100 kΩ', 'Soft-start: chalu korle output ~10.7 ms dhore dhire othe. R21 → VREF = "keep-running": short e latch na kore CC te chalte thake.', 'C28 = VC capacitor er 10 gun (datasheet).', 'Chalu korlei boro overshoot/inrush.'),
  C('R22 C29 C30', 'Compensation network', '10 kΩ · 22 nF · 100 pF', 'Brain er "reflex": load bodlale koto druto ar koto smooth thik korbe. Zero 723 Hz.', 'Shuru-r value — prothom test e load-step diye check korte hobe.', 'Output dolto (oscillation) ba onek dhire thik hoto.'),
  C('R23 R24', '1 % resistor divider', '200 kΩ + 46.4 kΩ', 'EN/UVLO: input 7.05 V er upore U1 chalu, 6.48 V er niche bondho.', 'U2 er UV (7.5 V) er niche — tai U2 aage kate, U1 porishkar bhabe thame.', 'Kom voltage e U1 adha-chalu hoye MOSFET gorom korto.'),
 ]),
 ('F', 'Knob, sense ar LED (U1 er chhoto network)', '#0ca678', [
  C('RV1 R25', 'Trimpot 25-turn + 1 % resistor', '200 kΩ + 5.23 kΩ', 'CV knob. Output voltage er tukro FB pin e jay; U1 FB = 1.00 V rakhe. VOUT = 1 V × (RV1 + R25) / R25.', f'Range {R["lt8390_nets"]["FB"]["vmin"]:.1f}–{R["lt8390_nets"]["FB"]["vmax"]:.0f} V (pot −10 % holeo ≥ 35 V).', 'Voltage set kora jeto na; FB khola hole output sorbochcho e uthe jeto.'),
  C('R46 D14 C33', 'Resistor + 5.1 V zener + capacitor', '10 kΩ · MM3Z5V1 · 47 pF', 'FB pin er bodyguard: output e onek beshi voltage er battery lagaleo FB pin 5.4 V er niche (limit 6 V). C33 noise filter.', '36 V battery te zener e mattro 1.8 mA. Pole 339 kHz — loop e probhab nai.', 'Boro battery lagale U1 er FB pin pure jeto.'),
  C('TH1 R26 RV2 R27 C34', 'PTC thermistor + resistor + 25-turn trimpot + capacitor', '470 Ω PTC · 20 kΩ · 50 kΩ · 4.53 kΩ · 10 nF', 'CC knob: CTRL pin e 0.36–1.45 V → current limit 0.94–8.33 A. TH1 board gorom hole resistance barie CTRL namay: 120 °C e max ~5.4 A, ~130 °C e switching bondho, thanda hole abar chalu.', 'CTRL min 0.362 V > 0.34 V latch threshold; max 1.45 V ≥ full-scale 1.35 V.', 'Current limit set kora jeto na, ar overheating e kono brake thakto na.'),
  C('R28 R29 D8 D9', '10 Ω resistor × 2 + diode × 2 (ulto-palta)', '10 Ω · 1N4148WS', 'ISP/ISN pin (R31 er voltage mape) er rokkha: fault e R31 e koyek volt uthleo pin e < 1 V.', 'Pin er limit 1 V; diode ~0.8 V e clamp kore, ISOC 0.75 V tobuo pouchay.', 'Ulta battery er spike e U1 er sense pin nosto.'),
  C('R30 LED1', 'Resistor + LED (sobuj)', '2.2 kΩ · GREEN ON', 'U1 er INTVCC 5 V thakle jole = controller chalu.', '~1 mA.', 'Board chalu kina bujhte multimeter lagto.'),
  C('TP1', 'Test point', 'ISMON', 'Output current mapar point: 0.25 V = 0 A, 1.25 V = 8.33 A (0.25 V + 10 × R31 er voltage).', 'Ammeter charai current dekha jay.', 'Shudhu shubidha komto.'),
 ]),
 ('G', 'Output: current sense, fuse, terminal', '#f59f00', [
  C('R31 NT3 NT4', 'Current-sense resistor 2512 + net-tie', '12 mΩ 1 % 2 W', 'Output current mape (CC er jonno): 8.33 A e 100 mV. Q9 o eta dekhe ulta battery er spike dhore.', '8.33 A e 0.83 W (2 W rated). ISOC 0.75 V = 62.5 A e U1 sathe sathe thame.', 'CC (current limit) kaj korto na.'),
  C('F2', 'Fuse (NANO2)', '10 A, 65 V', 'Output er sesh rokkha-kobach (normal fault e kate na — Q7 ar CC aage kaj kore).', 'Max output 8.33 A.', 'Q7 short hoye gele battery theke boro current.'),
  C('J2', 'Screw terminal', '5.08 mm, 2 pin', 'Output er tar. Square pad = minus (OUT−).', 'OUT− Q7 diye switch kora — kokhono IN− er sathe jora diben na (protection bypass hoye jabe).', '—'),
  C('D15', 'Schottky diode (100 V)', 'PMEG10030ELP', 'Output ke −1 V er niche namte dey na (inductive load off hole, ulta battery er dhakka).', 'Low-leakage, 100 V.', 'Output capacitor/U1 negative voltage e nosto hote parto.'),
 ]),
 ('H', 'Output guard: Q7 + trip transistor', '#d6336c', [
  C('Q7', 'Power MOSFET (100 V)', 'CSD19532Q5B', 'OUT− er return path e "dorja". Normally on. Ulta battery hole off → current bondho (tar bhitorer diode-o ulto dike).', '100 V: off obosthay VOUT + battery (sorbochcho ~70 V) sojjo korte hoy.', 'Output e battery ulta lagalei boro current, MOSFET/capacitor pure jeto.'),
  C('R32 D10 C32', 'Resistor + 10 V zener + capacitor', '10 kΩ · BZX84C10 · 100 nF', 'Q7 er gate supply: VG = min(VIN, 10 V). 9 V input e-o 8.3 V.', 'Q7 er gate limit 20 V — zener 10 V e rakhe.', 'Q7 on hoto na, ba beshi voltage e gate fete jeto.'),
  C('R33', 'Resistor', '10 kΩ', 'Q7 er gate ke VG te tule — dhire, norom bhabe on kore.', 'Trip transistor sohojei eta ke harate pare (1 mA).', 'Q7 on hoto na.'),
  C('Q8 R34 R35', 'NPN transistor + resistor', 'MMBT3904 · 4.7 kΩ · 47 kΩ', '"Trip transistor": TRIP signal elei Q7 er gate 0 V kore → Q7 off.', 'R35 base ke niche rakhe — noise e vul trip na.', 'Sensor gulo dhorleo Q7 bondho korar keu thakto na.'),
  C('Q9 R36 R37 R38', 'PNP transistor + resistor', 'MMBT5401 · 6.8 kΩ · 4.53 kΩ · 10 kΩ', 'Q_P: R31 e ~1.0 V (≈83 A spike) dekhlei TRIP. Ulta battery hot-plug e 0.6–2.5 µs e Q7 bondho.', f'Trip {R["qp_trip"]["I25"]:.0f} A @25 °C, {R["qp_trip"]["I100"]:.0f} A @100 °C — ISOC 62.5 A er upore, tai normal short e chatter nai.', 'Ulta battery er prothom dhakka thamano jeto na.'),
  C('Q10 D11 R39 R40 R41 R42', 'PNP transistor + diode + resistor', 'MMBT5401 · 1N4148WS · 10k/100k/22k/10k', 'Q_R: jotokkhon OUT− > OUT+ (battery ulta lagano), totokkhon TRIP dhore rakhe → Q7 off thake. Battery nijei eke chalay.', 'D11 normal polarity te (≤ 36 V) block kore; R40 transistor er ulto stress atkay.', 'Q7 ekbar off hoye abar on hoto → bar bar dhakka.'),
  C('Q11 D13 D16 R47 R44', 'NPN transistor + 2 diode + resistor', 'MMBT3904 · 1N4148WS/WT · 100 kΩ · 1 kΩ', 'Q_N: OUT+ GND er cheye 1.89 V er beshi niche gele sorasori Q7 er gate namay — kom CV setting e ulta battery er jonno.', 'Duita diode → threshold −1.89 V, tai inductive load er −1 V (D15) e vul trip nai. Diode gulo normal +39 V block kore.', 'Kom voltage setting e ulta battery dhora porto deri te.'),
 ]),
 ('I', 'Lal OUT LED ar mounting hole', '#495057', [
  C('D12 R43 LED3', 'Diode + resistor + LED (lal)', '1N4148WS · 10 kΩ · RED OUT', 'Output e battery ulta lagale jole — battery nijei LED chalay (board off thakleo).', '36 V battery te 0.11 W; ~3.5 V battery theke dekha jay.', 'Ulta lagano bujhtei parten na.'),
  C('H1 H2 H3', 'Mounting hole', 'M3', 'Standoff/screw diye board ar heatsink atkano. Charpashe GND stitching via — gorom chhorie dey.', 'Full 80 W e niche heatsink dile board +26 °C (na dile +46 °C).', '—'),
 ]),
]
BLOCKS = [(f'{g[0]}. {g[1]}', [r for c in g[3] for r in c['refs']], g[2]) for g in GROUPS]

def cards_html():
    out = ''
    for key, title, color, cards in GROUPS:
        refs = [r for c in cards for r in c['refs']]
        out += f'<h2 class="pb" id="g{key}"><span class="gk" style="background:{color}">{key}</span> {E(title)}</h2>'
        out += board_map(refs, color, f'{title} — kon part kothay (baki board halka kalo)', maxh_mm=92)
        for c in cards:
            mpn = BYREF.get(c['refs'][0], {}).get('lcsc') or ''
            out += (f'<div class="pc" style="border-left-color:{color}"><div class="ph"><b>{E(" · ".join(c["refs"]))}</b><span>{E(c["kind"])}</span><em>{E(c["value"])}</em></div>'
                    f'<dl><dt>Ki kaj kore</dt><dd>{E(c["kaj"])}</dd><dt>Value keno</dt><dd>{E(c["keno"])}</dd>'
                    + (f'<dt>Na thakle</dt><dd>{E(c["na"])}</dd>' if c['na'] != '—' else '') + '</dl></div>')
    return out

# ----------------------------------------------------------------------------- page
head = {(h['vin'], h['vout']): h for h in R['headline']}
def hrow(vi, vo):
    h = head[(vi, vo)]
    return f'<tr><td>{vi} V → {vo} V</td><td>{h["iout"]} A</td><td>{h["region"]}</td><td>{h["eta"]}–{h["eta_ds"]} %</td></tr>'

CSS = """
@page{size:A4}
body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:10pt;line-height:1.45;color:#1b1b1b;margin:0}
h1{font-size:23pt;margin:0 0 1mm;color:#0d3b66;line-height:1.15} h2{font-size:14.5pt;color:#0d3b66;border-bottom:2px solid #0d3b66;padding-bottom:1mm;margin:6mm 0 3mm}
h3{font-size:11.5pt;margin:4mm 0 1.5mm;color:#0d3b66} p{margin:1.5mm 0}
.pb{break-before:page} .sub{color:#555;margin-bottom:4mm}
table{border-collapse:collapse;width:100%;margin:2mm 0 3mm;font-size:9pt} th,td{border:1px solid #bbb;padding:1.2mm 1.8mm;vertical-align:top;text-align:left} th{background:#e8eef5}
.box{border:1px solid #c9d6e3;border-left:4px solid #0d3b66;border-radius:2mm;padding:2mm 3mm;margin:2.5mm 0;break-inside:avoid;background:#f7fafc}
.easy{border-left-color:#e8590c;background:#fff6ef} .ok{border-left-color:#2f9e44;background:#f1f8f1} .warn{border-left-color:#c92a2a;background:#fdf1f0}
.dg{width:100%;max-height:72mm;display:block;margin:1mm auto} .dg text,.pk text{font-family:'DejaVu Sans'}
.dg .l{font-size:12px;text-anchor:middle;fill:#222} .dg .s{font-size:10.5px;fill:#444} .dg .nt{font-size:12.5px;text-anchor:middle;fill:#222;font-weight:700}
.dg .st{font-size:11px;text-anchor:middle;font-weight:700} .dg .ON{fill:#2f9e44} .dg .OFF{fill:#c92a2a} .dg .wr{stroke:#222;stroke-width:2.2;fill:none}
.ph2>div{break-inside:avoid} .ph2 .dg{max-height:58mm}
.two{display:flex;gap:4mm;align-items:flex-start} .two>div{flex:1}
figure{margin:2mm 0;break-inside:avoid;text-align:center} figure svg{max-width:100%;border-radius:2mm} figcaption{font-size:8.5pt;color:#555;margin-top:1mm}
.lg{display:inline-block;margin:0.6mm 2.5mm;font-size:8.5pt} .lg i{display:inline-block;width:3mm;height:3mm;border-radius:.6mm;margin-right:1mm;vertical-align:-0.4mm}
.pc{border:1px solid #d5dce3;border-left:5px solid #888;border-radius:2mm;padding:1.6mm 3mm;margin:2mm 0;break-inside:avoid}
.ph{display:flex;gap:3mm;align-items:baseline;flex-wrap:wrap;border-bottom:1px dashed #ccd;padding-bottom:.8mm;margin-bottom:.8mm}
.ph b{font-size:11pt;color:#0d3b66} .ph span{color:#333} .ph em{font-style:normal;margin-left:auto;font-family:'DejaVu Sans Mono';font-size:8.8pt;background:#eef1f4;padding:0 1.5mm;border-radius:1mm}
dl{display:grid;grid-template-columns:24mm 1fr;gap:.6mm 2mm;margin:0} dt{font-weight:700;color:#555;font-size:8.8pt} dd{margin:0}
.gk{display:inline-block;color:#fff;border-radius:1.2mm;padding:0 2mm;margin-right:1mm}
.pkgs{display:grid;grid-template-columns:1fr 1fr;gap:2mm} .pkg{display:flex;gap:2mm;border:1px solid #dde3ea;border-radius:2mm;padding:1.5mm;break-inside:avoid;font-size:8.6pt;line-height:1.35}
.pk{width:27mm;flex:none;background:#2a6b45;border-radius:1.5mm} .pkg b{color:#0d3b66;font-size:9.4pt}
.toc li{margin:.8mm 0} .big{font-size:11pt} code{background:#f1f3f5;padding:0 1mm;border-radius:1mm;font-size:9pt}
.cover{text-align:center} .cover svg{width:178mm;border-radius:3mm}
ol.steps li{margin:1.6mm 0}
"""

body = f"""
<svg width="0" height="0" style="position:absolute"><defs><image id="board" href="data:image/jpeg;base64,{BOARD}" width="{IMG_W}" height="{IMG_H}"/></defs></svg>
<h1>SafeBuck-80 — sohoj bhashay</h1>
<div class="sub big">Buck-boost kivabe kaj kore, board er protiti part konta ki ar keno — ar design ta kivabe banano holo.</div>
<div class="cover"><svg viewBox="0 0 1600 1200"><use href="#board"/></svg></div>
<p class="small" style="text-align:center;color:#555">SafeBuck-80 v1.1 · 72 × 54 mm · 2 layer, 2 oz copper · Designed by Jarif Alam · Duburi</p>
<div class="box"><b>Ei PDF e ki ache</b>
<ol class="toc"><li>Board ta ek nojore ki kore</li><li>Agey 4 ta jinis bujhi (voltage, switch, inductor, capacitor)</li><li>Buck kivabe kaj kore — dhape dhape, chobi soho</li>
<li>Boost ar 4-switch buck-boost</li><li>Brain (LT8390) kivabe thik kore koto volt / koto amp</li><li>Component er chehara chena</li>
<li>Board map + protiti part (A–I, sob 113 ta): ki kaj kore, value keno, na thakle ki hoto</li><li>Vul connection korle kon part bachay</li><li>Design ta kivabe banalam</li></ol></div>

<h2 class="pb">1. Board ta ek nojore ki kore</h2>
<p>SafeBuck-80 ekta <b>automatic buck-boost converter</b>: input e 9–36 V jai dao, output e tumi je voltage set korbe (1.6–36 V) seta-i debe — input er cheye kom hok (<b>buck</b>) ba beshi (<b>boost</b>). Sathe current er limit (<b>CC</b>, 0.94–8.33 A) set kora jay — battery charge ba LED chalanor jonno. Sorbochcho 80 W.</p>
{blocks()}
<div class="two"><div class="box ok"><b>Duita knob</b><br>RV1 = <b>CV</b> (koto volt) · RV2 = <b>CC</b> (sorbochcho koto amp). Duitai 25-turn trimpot — onek bar ghurate hoy, tai sukkho bhabe set kora jay.</div>
<div class="box warn"><b>Tinta LED</b><br>Sobuj ON = controller chalu · Lal IN = input ulta / beshi / kom volt · Lal OUT = output e battery ulta.</div></div>
<div class="box easy"><b>"Smoke-tester" er dorshon:</b> jekono vul connection (input ulta, output e battery ulta, output short, beshi voltage, beshi gorom) e board pure jabe na — shudhu ekta lal LED jolbe ba current kome jabe. Fuse (F1, F2) shudhu sesh rokkha — normal vul e kate na.</div>

<h2>2. Agey 4 ta jinis bujhi</h2>
<table><tr><th style="width:24%">Jinis</th><th>Pani-r udahoron diye</th><th style="width:30%">Ei board e</th></tr>
<tr><td><b>Voltage / Current / Power</b></td><td>Voltage = pani-r chap (pressure), current = koto pani boichhe (flow). Power = chap × flow (W = V × A).</td><td>12 V × 6.67 A = 80 W</td></tr>
<tr><td><b>Switch (MOSFET)</b></td><td>Ekta kol (tap) ja 1 second e 300,000 bar khola-bondho kora jay. On = pray 0 Ω (4 mΩ), off = puro bondho. Majhamajhi rakhle gorom hoy — tai shudhu puro on ba puro off.</td><td>Q3, Q4, Q5, Q6 (switch A B C D)</td></tr>
<tr><td><b>Inductor (L)</b></td><td>Bhari chaka (flywheel) ba lomba pipe e bhari pani: ekbar boite shuru korle hothat thamano jay na. Current barle shakti jomay, current komle seta ferot dey.</td><td>L1 10 µH</td></tr>
<tr><td><b>Capacitor (C)</b></td><td>Pani-r tank: voltage dhore rakhe, jhatka (ripple) shushe ney.</td><td>C7–C36, C11, C18</td></tr>
<tr><td><b>Diode</b></td><td>Ek-mukhi valve: ek dike pani jete dey, ulto dike na.</td><td>D1–D17 (protection e)</td></tr></table>

<h2 class="pb">3. Buck kivabe kaj kore — dhape dhape</h2>
<h3>3.1 Somossa: 24 V theke 12 V lagbe, 6.67 A (80 W)</h3>
<div class="two"><div class="box warn"><b>Resistor diye komale (linear)</b><br>Bakhi 12 V resistor e "khoy" hoy: 12 V × 6.67 A = <b>80 W gorom</b> — ekta heater! Efficiency 50 %.</div>
<div class="box ok"><b>Buck diye</b><br>Loss mattro <b>{head[(24,12)]['Ploss']} W</b> — efficiency {head[(24,12)]['eta']}–{head[(24,12)]['eta_ds']} %. Input theke lage mattro {head[(24,12)]['iin']} A (output 6.67 A er-o kom!).</div></div>
<h3>3.2 Mul buddhi: druto on-off kore "gor" (average) neya</h3>
<p>Switch ta jodi somoy er 50 % on ar 50 % off thake, tahole gor voltage = 24 V er 50 % = 12 V. 25 % on rakhle 6 V, 75 % e 18 V. On thakar ongsho ke bole <b>duty cycle (D)</b>.</p>
{pwm()}
<div class="box easy" style="text-align:center"><b class="big">Buck: V<sub>out</sub> = D × V<sub>in</sub></b> &nbsp; (24 V × 0.5 = 12 V)</div>
<p>Kintu kacha on-off (24 V, 0 V, 24 V…) load e dile load jhatka khabe. Tai majhe <b>L1 (flywheel)</b> ar <b>C (tank)</b> boshano hoy — era jhatka ke mosrin DC te bodle dey. Ekhon dekhi ek cycle e ki ghote:</p>
<div class="ph2"><div><h3>Dhap 1 — A on, B off</h3>{buck(1)}<p>Input → A → L1 → load → ferot. L1 er dui pashe 24 − 12 = 12 V, tai current barte thake (12 V / 10 µH = 1.2 A protiti µs e). L1 shakti jomay.</p></div>
<div><h3>Dhap 2 — A off, B on</h3>{buck(2)}<p>Input bichchinno. Kintu L1 current hothat thamate dey na — B diye GND theke current tene load e pathay. Ekhon L1 er upor −12 V, tai current dhire komte thake.</p></div></div>
<h3>3.3 Current er chobi (24 V → 12 V, 6.67 A)</h3>
{wave()}
<p>Protiti cycle 3.33 µs: 1.67 µs A on (current 5.67 → 7.67 A), 1.67 µs B on (7.67 → 5.67 A). Load er kache gor <b>6.67 A</b>, capacitor baki chhoto dheu (ripple) shushe ney — output e ripple mattro ~21 mV. Eta 1 second e 300,000 bar hoy.</p>
<div class="box"><b>Keno B te diode na, MOSFET? (synchronous)</b> Purono design (jemon QS-1212 er UC3843) e B er jaygay diode thake: 0.5 V × 6.67 A ≈ 3.3 W gorom. MOSFET (4.3 mΩ) e oi kaje loss mattro ~0.1 W. Tai efficiency 95 %+.</div>
<div class="box warn"><b>A ar B kokhono eksathe on na!</b> Hole input sorasori GND e short (shoot-through). U1 majhe khub chhoto "dead time" rakhe — ekta puro off hole tarpor onyota on.</div>

<h2 class="pb">4. Boost ar 4-switch buck-boost</h2>
<h3>4.1 Boost: 12 V theke 24 V (input er cheye beshi)</h3>
<div class="ph2"><div><h3>Dhap 1 — C on, D off</h3>{boost(1)}<p>L1 sorasori input theke GND e — current bare, shakti jome. Load ke ei somoy capacitor chalay (nil).</p></div>
<div><h3>Dhap 2 — C off, D on</h3>{boost(2)}<p>L1 current thamate dey na, nijer voltage input er sathe <b>jog kore</b> output e dhele dey → output input er cheye beshi.</p></div></div>
<div class="box easy" style="text-align:center"><b class="big">Boost: V<sub>out</sub> = V<sub>in</sub> / (1 − D)</b> &nbsp; (12 V / (1 − 0.5) = 24 V)</div>
<h3>4.2 SafeBuck-80 er asol power stage: 4 switch, 1 inductor</h3>
{fourswitch()}
<table><tr><th>Obostha</th><th>Mode</th><th>A (Q3)</th><th>B (Q4)</th><th>C (Q5)</th><th>D (Q6)</th></tr>
<tr><td>V<sub>in</sub> &gt; V<sub>out</sub> (jemon 24 → 12 V)</td><td><b>Buck</b></td><td>switch kore</td><td>switch kore</td><td>sobsomoy off</td><td>sobsomoy on</td></tr>
<tr><td>V<sub>in</sub> &lt; V<sub>out</sub> (jemon 12 → 24 V)</td><td><b>Boost</b></td><td>sobsomoy on</td><td>sobsomoy off</td><td>switch kore</td><td>switch kore</td></tr>
<tr><td>V<sub>in</sub> ≈ V<sub>out</sub> (jemon 12 → 12 V)</td><td><b>Buck-boost</b></td><td colspan="4">char ta-i kaj kore — ek cycle e kichu ongsho buck er moto, kichu boost er moto</td></tr></table>
<p>Mode bodlano U1 nije kore — tumi shudhu knob ghurao. Kichu hisab kora operating point (calc/design.py):</p>
<table><tr><th>Input → Output</th><th>Current</th><th>Mode</th><th>Efficiency</th></tr>{hrow(24,12)}{hrow(12,5)}{hrow(12,12)}{hrow(12,24)}{hrow(9,35)}{hrow(36,5)}</table>

<h2>5. Brain: U1 (LT8390) kivabe thik kore</h2>
<p>Gari-r <b>cruise control</b> er moto: speed (voltage) mepe accelerator (duty) kom-beshi kore. U1 tin jaygay chokh rakhe:</p>
{loop()}
<ul><li><b>CV (voltage):</b> RV1 + R25 output er ekta tukro FB pin e dey. U1 sobsomoy FB = 1.00 V rakhte chay. Output kome gele duty barai, beshi hole komay.</li>
<li><b>CC (current):</b> R31 (12 mΩ) e output current er voltage. RV2 je limit set kore, current tar beshi hote chaile U1 voltage namiye dey.</li>
<li><b>Peak limit (protiti cycle):</b> R15 (3 mΩ) diye L1 er current. 11.7–21.7 A er beshi hote dey na — short e MOSFET bache. Ei "peak-current-mode" control loop ke stable ar druto kore.</li></ul>
<div class="box easy"><b>Battery charge udahoron:</b> CV 14.4 V, CC 5 A set korle — khali battery te prothome current 5 A e atke thake (CC), voltage dhire bare. 14.4 V e pouchale CV shuru, current nije nije kome. Je limit aage pouchay, sei-i jete.</div>

<h2 class="pb">6. Component er chehara chena</h2>
<p>Board e je je dhoroner part ache, dekhte kemon ar kivabe chinbe (chobi gulo simplified — asol rong ektu alada hote pare):</p>
<div class="pkgs">{''.join(f'<div class="pkg">{pkg(k)}<div><b>{E(n)}</b><br><i>{E(look)}</i><br>{E(how)}<br><span style="color:#0d3b66">Board e: {E(where)}</span></div></div>' for k, n, look, how, where in PKGS)}</div>

<h2 class="pb">7. Board map — kon block kothay</h2>
<p>Rong diye block gulo dekhano holo. Porer page gulote protiti block alada kore zoom kora, part gulo chinhito, ar protiti part er bakkha.</p>
{overview_map()}
{cards_html()}

<h2 class="pb">8. Vul connection korle kon part bachay</h2>
<table><tr><th style="width:24%">Vul / ghotona</th><th>Ki hoy</th><th style="width:24%">Kon part</th></tr>
<tr><td>Input + / − ulta</td><td>Q2 bondho thake, kono current dhoke na, kichu gorom hoy na. Lal IN LED jole.</td><td>U2, Q2, D5/D7, LED2</td></tr>
<tr><td>Input {ff['ov_rise']:.1f} V er beshi</td><td>Q1 off, lal IN jole. {ff['ov_fall']:.1f} V er niche nemle nije abar chalu.</td><td>U2, Q1, R5–R7</td></tr>
<tr><td>Input {ff['uv_fall']:.1f} V er kom</td><td>Q1 off ({ff['uv_rise']:.1f} V e abar chalu); U1 nijeo 6.48 V e thame.</td><td>U2, R5–R7, R23/R24</td></tr>
<tr><td>Plug korar spark / spike</td><td>Inrush 1.3–2.6 A e simito; spike 96.8 V e clamp; tar er dolna damp.</td><td>R4/C5, D1, R1/C1, C11</td></tr>
<tr><td>Output short</td><td>CC limit (RV2) e current atke thake, board chalte thake ("keep-running"). Khub hard short: 62.5 A e U1 sathe sathe pause.</td><td>U1, R31, R15, R21</td></tr>
<tr><td>Output e battery ulta</td><td>Q9 (spike) ba Q11 (OUT+ &lt; −1.89 V) → Q8 → Q7 off, 0.6–5.8 µs e. Q10 Q7 ke off dhore rakhe. Lal OUT jole.</td><td>Q7–Q11, D15, LED3</td></tr>
<tr><td>Output e CV er cheye beshi voltage er battery</td><td>FB pin 5.4 V er niche thake.</td><td>R46, D14</td></tr>
<tr><td>Beshi gorom</td><td>120 °C e current ~5.4 A e name, ~130 °C e switching bondho, thanda hole abar chalu.</td><td>TH1 (PTC)</td></tr>
<tr><td>Kono MOSFET nijei short (part nosto)</td><td>Fuse kete jay — sesh rokkha.</td><td>F1, F2</td></tr></table>
<div class="box warn"><b>Ja board atkate pare na:</b> 60 V er beshi input (TVS clamp 60 V er upor); output e 36 V er beshi battery; OUT− ke IN− er sathe jora (Q7 bypass hoye jay); heatsink charai lomba somoy full 80 W (board +46 °C — heatsink dile +26 °C).</div>

<h2 class="pb">9. Design ta kivabe banalam</h2>
<ol class="steps">
<li><b>Requirement:</b> QS-1212CCBD er moto 80 W auto buck-boost — 9–36 V in, 1.6–36 V out, CV + CC, ar "smoke-tester" protection: vul connection e kichu pure na, shudhu lal LED.</li>
<li><b>Topology:</b> 4-switch synchronous buck-boost. QS-1212 er UC3843 + diode design e diode onek gorom hoy. LT8390 nilam: 60 V, CV + CC ek IC te, 4 ta MOSFET chalay, spread spectrum, JLC te pawa jay.</li>
<li><b>Protection architecture:</b> input e LM74930 + duita mukhomukhi MOSFET (ulta, OV, UV, inrush); output e low-side Q7 + transistor trip circuit (ulta battery); FB/ISP-ISN clamp; PTC thermal foldback; fuse shudhu sesh rokkha.</li>
<li><b>Part bachai:</b> protiti part er LCSC number (JLC assembly). Ceramic capacitor rating ≥ 2 × voltage, MOSFET 60/100 V margin, inductor saturation &gt; current limit max.</li>
<li><b>Hisab (calc/design.py):</b> current limit, inductor, ripple, loss, temperature, sob threshold, ar ulta-battery hot-plug er numeric simulation — 57 ta check, 56 PASS (1 ta info: heatsink charai +46 °C).</li>
<li><b>Ek netlist theke sob:</b> <code>hardware/netlist.py</code> → schematic (<code>make_schematic.py</code>) → PCB (<code>build_pcb.py</code> + <code>placement.py</code>) → routing (Freerouting + nijer completion router <code>route.py</code>) → <code>verify.py</code> (schematic = netlist = PCB).</li>
<li><b>Layout rule:</b> hot loop (C7/C8 ↔ Q3/Q4, C12–C36 ↔ Q5/Q6) chhoto; Kelvin sense net-tie; 2 oz copper; GND pour + stitching via; gate track chhoto (TG2 97 → 44 mm).</li>
<li><b>Check:</b> KiCad DRC — 0 unconnected, 0 clearance error. Independent review er poramorsho fix.</li>
<li><b>Board 72 × 54 mm:</b> gorom komate ektu boro (+57 → +46 °C), terminal er mukh baire.</li>
<li><b>Fabrication:</b> <code>make_jlcpcb.py</code> → gerber, BOM, CPL (JLCPCB), KiCad project <code>kicad/</code> folder e.</li></ol>
<div class="box warn"><b>Sotti kotha:</b> board ta ekhono banano/test kora hoyni — sob hisab ar software check. Prothom bar chalu korar somoy Build Guide er dhap (current-limited supply, kom voltage diye shuru) mene cholo. Compensation (R22/C29) load-step test e thik korte hote pare.</div>
"""

html_doc = f'<!doctype html><html><head><meta charset="utf-8"><title>SafeBuck-80 How It Works</title><style>{CSS}</style></head><body>{body}</body></html>'

# every part in the netlist must be explained
covered = {r for g in GROUPS for c in g[3] for r in c['refs']}
missing = [p['ref'] for p in PARTS if p['ref'] not in covered]
extra = sorted(covered - set(BYREF))
assert not missing and not extra, (missing, extra)

src = os.path.join(DOCS, 'src', 'how_it_works.html')
open(src, 'w').write(html_doc)
pdf = os.path.join(DOCS, 'SafeBuck-80_How_It_Works.pdf')
subprocess.run(['node', os.path.join(DOCS, 'print_pdf.js'), src, pdf], check=True)
print('parts explained:', len(covered), '/', len(PARTS))
