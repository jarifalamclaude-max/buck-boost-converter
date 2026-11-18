"""
Build the two PDF guides (Banglish + English technical terms):
  docs/SafeBuck-80_Component_Guide.pdf   kon component keno (why each part)
  docs/SafeBuck-80_Build_Guide.pdf       noob-friendly build + first power-up guide
and docs/SafeBuck-80_Schematic.pdf (exported from the KiCad schematic).
HTML sources are kept in docs/src/ so they can be edited.

Run:  python3 docs/make_docs.py      (needs kicad-cli + node with Playwright)
"""
import os, sys, html, subprocess, json, base64
DOCS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DOCS)
sys.path.insert(0, os.path.join(ROOT, 'hardware'))
from netlist import PARTS

SRC = os.path.join(DOCS, 'src'); os.makedirs(SRC, exist_ok=True)
IMG = os.path.join(DOCS, 'img')
R = json.load(open(os.path.join(ROOT, 'calc', 'results.json')))
E = html.escape

CSS = """
<style>
 body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:10.5pt;line-height:1.45;color:#1b1b1b}
 h1{font-size:21pt;margin:0 0 2mm;color:#0d3b66} h2{font-size:14pt;color:#0d3b66;border-bottom:2px solid #0d3b66;padding-bottom:1mm;margin-top:7mm}
 h3{font-size:11.5pt;margin:4mm 0 1mm;color:#222}
 .sub{color:#555;margin-bottom:5mm} table{border-collapse:collapse;width:100%;margin:2mm 0 3mm;font-size:9pt}
 th,td{border:1px solid #bbb;padding:1.2mm 1.6mm;vertical-align:top;text-align:left} th{background:#e8eef5}
 .card{border:1px solid #c9d6e3;border-left:4px solid #0d3b66;border-radius:2mm;padding:2mm 3mm;margin:2.5mm 0;break-inside:avoid}
 .warn{border-left-color:#c0392b;background:#fdf1f0} .ok{border-left-color:#2e7d32;background:#f1f8f1}
 code{background:#f2f2f2;padding:0 1mm;border-radius:1mm;font-size:9pt} .small{font-size:8.5pt;color:#444}
 img{max-width:100%} .two{display:flex;gap:4mm} .two>div{flex:1}
 ol li,ul li{margin:0.8mm 0} .pb{break-before:page}
</style>"""

def page(title, body):
    return f'<!doctype html><html><head><meta charset="utf-8"><title>{E(title)}</title>{CSS}</head><body>{body}</body></html>'

def img_tag(name, width='100%'):
    p = os.path.join(IMG, name)
    if not os.path.exists(p): return ''
    return f'<img style="width:{width}" src="data:image/png;base64,{base64.b64encode(open(p, "rb").read()).decode()}">'

def bom_table(block):
    rows = ''.join(f'<tr><td>{E(p["ref"])}</td><td>{E(p["value"])}</td><td>{E(p["mpn"] or "generic")}</td>'
                   f'<td>{E(p["lcsc"] or ("DNP" if p["dnp"] else "-"))}</td><td>{E(p["role"])}</td></tr>'
                   for p in PARTS if p['block'] == block)
    return f'<table><tr><th>Ref</th><th>Value</th><th>MPN</th><th>LCSC</th><th>Kaj (role)</th></tr>{rows}</table>'

fe = R.get('front_end', {}).get('ladder', {})
head = R.get('headline', [])
eff_rows = ''.join(f"<tr><td>{h['vin']} V</td><td>{h['vout']} V</td><td>{h['iout']} A</td><td>{h['region']}</td><td>{h['eta']}–{h['eta_ds']} %</td></tr>" for h in head)

# ====================================================================== component guide
comp = f"""
<h1>SafeBuck-80 — Kon component, keno</h1>
<div class="sub">80 W protected 4-switch buck-boost · 9–36 V in · 1.6–36 V / 0.9–8.3 A out (CV + CC) · 72 × 54 mm · 2-layer 2 oz</div>

<h2>1. Puro circuit ta ek nojore</h2>
<p><b>VIN (J1)</b> → F1 fuse → D1 TVS → <b>LM74930 + Q1/Q2</b> (ulta polarity block, over/under-voltage cut-off)
→ <b>LT8390 + Q3–Q6 + L1</b> (4-switch synchronous buck-boost: input er cheye output beshi ba kom dutoi) → R31 (CC current sense)
→ F2 → <b>VOUT+ (J2)</b>. VOUT− er return path e <b>Q7</b> (low-side switch) ache. Output e keu battery ulta lagale Q7 1–6 µs er moddhe off hoy
ar <b>red OUT LED</b> jole. Input ulta dile <b>red IN LED</b> jole, kichu gorom hoy na.</p>
<div class="card"><b>Keno 4-switch buck-boost?</b> QS-1212CCBD te UC3843 (non-synchronous, diode diye) — diode e 0.5 V drop, 80 W e
onek gorom. LT8390 te 4-ta MOSFET synchronous switch kore, tai efficiency 93–97 % (hisab nicher table e), ar input 9 V hok ba 36 V,
output jekono voltage (1.6–36 V) smooth bhabe dey — buck, boost ar buck-boost mode nije nije bodlay.</div>

<h2>2. Main IC</h2>
<div class="card"><h3>U1 — LT8390 (Analog Devices) · LCSC C673802</h3>
<ul><li>60 V, 4-switch synchronous buck-boost controller, peak-current-mode (buck e peak-buck, boost e peak-boost) — stable ar fast.</li>
<li><b>CV + CC dutoi ek IC te:</b> FB pin (1.00 V) diye voltage, CTRL pin diye output current limit (RV2 pot). Eta-i "CC/CV module" er kaj.</li>
<li>±15 % <b>spread spectrum</b> (SYNC/SPRD → INTVCC): EMI peak kome.</li>
<li>ISP/ISN e 0.75 V hole (62.5 A) sathe sathe switching bondho — output short e MOSFET bache. SS → VREF 100 k = "keep-running" mode: short hole CC te current limit kore chalte thake, latch kore na.</li>
<li>Abs max 60 V: tai input e ~43 V er upore LM74930 cut-off kore dey.</li>
<li>FB pin abs max 6 V: R46 (10 k) + D14 (5.1 V zener) pin take rokkha kore — output e CV er cheye onek beshi voltage er battery lagaleo.</li></ul></div>
<div class="card"><h3>U2 — LM74930-Q1 (Texas Instruments) · LCSC C22428070</h3>
<ul><li>Ideal-diode + load-switch controller, −65 V porjonto ulta voltage sojjo kore. Q2 (DGATE) ulta polarity block kore, Q1 (HGATE) over-voltage/under-voltage e line kete dey.</li>
<li>UV/OV ladder (R5 280k, R6 17.8k, R7 4.22k): <b>UV {fe.get('uv_fall', 7.6):.1f} V (falling) / {fe.get('uv_rise', 8.3):.1f} V (rising), OV {fe.get('ov_rise', 41.0):.1f} V cut-off, {fe.get('ov_fall', 37.6):.1f} V e abar on</b>.</li>
<li>CdVdT (C5 3.3 nF + R4 100 Ω) inrush ke ~1.3–2.6 A te rakhe — hot-plug e spark/fuse problem nai.</li>
<li>D17 (15 V zener, TI er DZ1): chalu obosthay input short hole C5 Q1 er gate ke upore dhore rakhe — zener VGS 15 V er niche rakhe (Q1 limit 20 V).</li>
<li>FLT pin → red IN LED. Built-in circuit breaker disable kora (TMR, ILIM → GND; CS+/CS−/ISCP → C): F1 fuse shudhu MOSFET short hole last resort.</li>
<li>MODE → VS, OVCLAMP → GND, NC pin float, exposed pad (RTN) float — datasheet onujayi.</li></ul></div>

<h2>3. Power parts</h2>
<div class="card"><h3>Q3–Q6 — CSD18532Q5B ×4 (TI, 60 V) · LCSC C882766</h3>
LT8390 er gate drive 5 V (INTVCC), tai <b>logic-level</b> MOSFET lagbe: 4.5 V e 4.3 mΩ max. Gate charge kom (~19 nC @4.5 V) — LT8390 er
INTVCC regulator e loss kom (~0.6–1 W @36 V). 60 V rating, OV cut-off (~43 V, worst 46 V) er upore margin. SON 5×6 package, PCB te heat chhore dey.
(CSD18540Q5B ar o bhalo, kintu JLCPCB te stock e 2-ta — tai eta.)</div>
<div class="card"><h3>Q1, Q2, Q7 — CSD19532Q5B ×3 (TI, 100 V) · LCSC C473333</h3>
Input protection (Q1/Q2) ar output reverse-battery switch (Q7). Q7 ke output voltage + ulta battery = ~70 V porjonto block korte hoy, tai 100 V.
4.9 mΩ (@10 V) — 8 A te mattro ~0.3 W. Avalanche rating 274 mJ: fault e wiring inductance er energy (hisab: 0.6–19 mJ) easily sojjo kore.</div>
<div class="card"><h3>D15 — PMEG10030ELP (Nexperia 100 V 3 A Schottky) · LCSC C5260346</h3>GND theke VOUT_C (anode GND). Motor/solenoid er moto inductive load hole converter bondho howar muhurte coil er current eta diye ghore — VOUT_C ~−1 V e thake, tai Q11 false trip kore na ar Q7 e avalanche hoy na. Ulta battery hit eo VOUT_C ke ~−1.5 V er niche jete dey na (LT8390 er VOUT/ISP/ISN pin bache). Low-leakage (450 nA @100 V) bole normal e loss nai.</div>
<div class="card"><h3>L1 — Coilcraft XAL1510-103 (10 µH) · LCSC C3911782</h3>
10 µH keno: slope-compensation er jonno L &gt; 10·VOUT·RSENSE/f = 3.6 µH lagbe, ar ripple current ~30–40 % e rakhte 10 µH thik.
Isat 26.3 A (soft saturation) &gt; peak current limit max 21.7 A. DCR 9 mΩ max (kom loss), shielded (EMI kom), AEC-Q200.</div>
<div class="card"><h3>R15 3 mΩ (RSENSE) · R31 12 mΩ (RIS)</h3>
R15: LT8390 er inductor peak-current sense — limit 11.7–21.7 A (datasheet threshold / 3 mΩ). R31: output current sense — CC full scale
100 mV / 12 mΩ = <b>8.33 A</b>. Duto-i Kelvin connection (net-tie NT1–NT4) diye — power current sense line diye jay na, tai accurate.</div>
<div class="card"><h3>Capacitors</h3>
<ul><li><b>C7, C8 (2×10 µF 100 V X7S 1210):</b> hot loop 1 er input cap, MOSFET er thik niche. 100 V rating keno: ceramic e DC-bias e capacitance kome —
36 V e 100 V cap ~45 % thake, 50 V cap hole ~20 % thakto.</li>
<li><b>C11 (100 µF 63 V electrolytic):</b> ESR ~0.35 Ω — input cable er inductance + ceramic cap er LC resonance damp kore (Middlebrook). Hot-plug e voltage spike kome.</li>
<li><b>C12–C14, C36 (4×10 µF 100 V) + C18 (47 µF 50 V hybrid polymer, Panasonic ZA):</b> output ripple ar load step. 300 kHz e ceramic er reactance kom na — tai hybrid o ripple current bhag kore (~2.2 A worst corner e, 85 °C e rating ~2.5 A).</li>
<li>C19/C20/C21/C22/C23: IC pin er bypass — protitar pin er 2–5 mm er moddhe.</li></ul></div>
<div class="card"><h3>F1 15 A, F2 10 A (Littelfuse 451 NANO²)</h3>
Normal fault (ulta, short, over-voltage) e fuse kete na — electronics-i protect kore. Fuse shudhu kono MOSFET nijei short hoye gele aagun thekate.</div>
<div class="card"><h3>D1 — SMBJ60CA (bidirectional TVS)</h3>
Bidirectional bole −60 V ulta input eo conduct kore na (LM74930 block korbe), kintu cable er fast spike (hot-plug, inductive kick) clamp kore. 60 V standoff, clamp 96.8 V (&lt; 100 V of Q1/Q2).</div>

<h2>4. "Smoke-tester" protection er chhoto part gulo</h2>
<table><tr><th>Part</th><th>Ki kore</th></tr>
<tr><td>Q7 + R32/D10/C32/R33</td><td>VG10 supply (input theke 10 V zener) diye Q7 er gate on rakhe. Input na thakle Q7 off — output e battery lagale drain hoy na.</td></tr>
<tr><td>Q9 (Q_P) + R36/R37/R38</td><td>R31 e ~1.0 V (≈83 A) dekhlei Q7 off (output e ulta battery, high CV setting e).</td></tr>
<tr><td>Q11 (Q_N) + D13/D16/R44/R47</td><td>OUT+ GND er cheye ~1.85 V niche gelei Q7 off (ulta battery, kom CV setting e — review agent er dhora bug er fix). Duita diode (D13, D16) threshold baray jate inductive load er freewheel (−1 V) e trip na kore; R47 diode leakage theke Q11 er E-B junction bachay.</td></tr>
<tr><td>Q10 (Q_R) + D11/R39–R42</td><td>Q7 off howar por, battery ulta thakle oi battery-r power diyei Q7 ke off dhore rakhe.</td></tr>
<tr><td>Q8 + R34/R35</td><td>Jekono trip signal (TRIP) e Q7 er gate GND e tene dey (~100 mA, &lt;1 µs).</td></tr>
<tr><td>R45 + C20</td><td>LT8390 VOUT pin e 100 Ω / 1 µF filter — ulta battery hit e pin positive thake, ar VOUT_C negative holeo pin e &lt; 4 mA.</td></tr>
<tr><td>R46 + D14</td><td>FB pin er series 10 k + 5.1 V zener: output e CV er 6× er beshi voltage er battery lagaleo FB &lt; 6 V.</td></tr>
<tr><td>D15</td><td>VOUT_C clamp Schottky (upore dekhun).</td></tr>
<tr><td>D17</td><td>Q1 gate-source 15 V clamp (input short while running).</td></tr>
<tr><td>R28/R29 + D8/D9</td><td>ISP/ISN pin er ±1 V abs max rokkha kore.</td></tr>
<tr><td>TH1 (PTC 470 Ω)</td><td>Board 105 °C hole CC current kome (foldback), ~130 °C e switching bondho; thanda hole abar chalu.</td></tr>
<tr><td>LED2 / D4–D7 / R11/R12</td><td>Red IN: FLT (OV/UV) ba input ulta hole jole.</td></tr>
<tr><td>LED3 / D12 / R43</td><td>Red OUT: output e battery ulta hole, oi battery-r power diye jole.</td></tr>
<tr><td>C35</td><td>LM74930 common-source node er 1 µF (TI Figure 8-1 onujayi).</td></tr></table>

<h2>5. Hisab (calc/design.py theke)</h2>
<table><tr><th>VIN</th><th>VOUT</th><th>IOUT</th><th>Mode</th><th>Efficiency (est.)</th></tr>{eff_rows}</table>
<p class="small">Efficiency duita estimate: conservative physics model – datasheet-formula model. Real board e ±2 % hote pare. 57-ta design check er 56-ta pass;
je ekta "fail" seta info: heatsink chhara 80 W e board +46 °C gorom hoy (board 72 × 54 mm kora hoyeche; 65 × 48 e +57 °C chilo).
Ghorer temperature e heatsink chhara chole; box er bhitore ba 40 °C er beshi gorome 40×40 mm heatsink lagan (tokhon +26 °C).</p>

<h2 class="pb">6. Full BOM</h2>
<h3>Input protection</h3>{bom_table('input')}
<h3>Converter</h3>{bom_table('converter')}
<h3>Output</h3>{bom_table('output')}
<p class="small">Generic passive (LCSC code thakleo) — same size ar rating er jekono 1 % resistor / X7R-C0G capacitor cholbe. DNP = board e jayga ache, lagano hoy na.</p>
"""
def write_component_guide():
    open(os.path.join(SRC, 'component_guide.html'), 'w').write(page('SafeBuck-80 Component Guide', comp))

# ====================================================================== build guide
def build_html():
  return f"""
<h1>SafeBuck-80 — Noob-friendly Build Guide</h1>
<div class="sub">Kono experience chhara-i: file download → JLCPCB order → first power-up → CV/CC set → protection test.</div>
<div class="card warn"><b>Safety:</b> eta 80 W power supply. 36 V porjonto DC safe, kintu short-circuit e cable gorom hoy, battery theke boro spark hoy.
Prothombar sobsomoy <b>current-limited bench supply</b> diye chalaben. Box er bhitore ba gorom jaygay ghonta dhore 80 W chalale heatsink lagan.</div>

<h2>0. Ki ki lagbe</h2>
<ul><li>Ei repo (GitHub page e <b>Code → Download ZIP</b>).</li>
<li>Bench power supply (0–30 V, current limit shoho). Na thakle 12 V adapter + 2 A fuse.</li>
<li>Multimeter (10 A range shoho), ekta load (12 V bulb / 10 Ω 25 W resistor), 1.5 mm² (16 AWG) wire.</li>
<li>Box er bhitore / 40 °C er beshi gorome full power er jonno: 40×40×10 mm aluminium heatsink, 1 mm thermal pad, 3× M3 screw + nylon spacer.</li>
<li>Nije solder korle (Option B): hot-air station, solder paste, flux, tweezers — U1/U2 hand solder kora kothin.</li></ul>

<h2>1. JLCPCB te order (Option A — recommended)</h2>
<ol>
<li><a href="https://jlcpcb.com">jlcpcb.com</a> → <b>Order Now</b> → <b>Add gerber file</b> → <code>jlcpcb/SafeBuck-80_gerbers.zip</code> upload.</li>
<li>Settings: <b>Layers 2</b>, Dimension auto (72 × 54 mm), <b>PCB Thickness 1.6 mm</b>, <b>Outer Copper Weight 2 oz</b> (khub important),
Surface finish HASL lead-free ba ENIG, color jekono.</li>
<li><b>PCB Assembly</b> on → Top side → PCBA type <b>Standard</b> (extended part ar through-hole part er jonno lagbe) → quantity 2 ba 5.</li>
<li>Next → BOM: <code>jlcpcb/SafeBuck-80_BOM.csv</code>, CPL: <code>jlcpcb/SafeBuck-80_CPL.csv</code> upload.</li>
<li>Part list e protita line "matched" kina dekhun (LCSC number already deya). Kono part out of stock dekhale same value/package er onno part select korun —
<b>U1, U2, Q1–Q7, L1, R15, R31 change korben na</b> (egula exact lagbe).</li>
<li><b>Placement preview</b> khub mon diye dekhun: U1/U2 er pin-1 dot, MOSFET, diode/LED er dag (cathode), C11/C18 er + side silkscreen er sathe milche kina.
Ulta dekhale oi part er rotation 90/180 ghuran. Order e <b>"Confirm Parts Placement"</b> option thakle select korun — JLC engineer check kore pathabe.</li>
<li>J1, J2 (screw terminal) ar RV1, RV2 (pot) through-hole part: JLC ke diye lagaben (THT assembly) othoba BOM theke bad diye nije solder korben (shohoj).</li>
<li>Order + payment. Shadharonoto 1–2 shoptaho.</li></ol>

<h2>2. Nije assemble (Option B — experienced der jonno)</h2>
<p>Order: U2 (QFN) → U1 (TSSOP-EP, exposed pad e paste) → Q1–Q7 → L1 → baki SMD → J1, J2, RV1, RV2. Stencil + hot air/reflow use korun.
U1 er exposed pad GND e solder na hole IC gorom hoye bondho hobe.</p>

<h2>3. Prothom check (power chhara)</h2>
<ol><li>Magnifier diye U1/U2 er pin e solder bridge ache kina.</li>
<li>Multimeter (resistance): J1 + theke − : &gt; 1 kΩ hote hobe (short na). J2 + theke −: &gt; 1 kΩ.</li>
<li>C11, C18 er + chinho, LED gulo silkscreen er sathe milche kina.</li></ol>

<h2>4. First power-up (smoke test, step by step)</h2>
<ol>
<li>RV1 (CV) <b>counter-clockwise 25 paak</b> ghurie minimum e rakhun (output ~1.6 V). RV2 (CC) majhamajhi.</li>
<li>Bench supply: <b>12 V, current limit 0.2 A</b>. J1 er + ar − (silkscreen dekhun) e lagan, J2 te kichu na.</li>
<li>Expected: <b>green LED jolbe</b>, red LED gulo bondho, input current ~20–40 mA. Kichu gorom hobe na.</li>
<li>J2 te multimeter: ~1.6 V. RV1 clockwise ghuran → voltage barbe (25 paak e full range ~1.6–39 V; 36 V er beshi set korben na). (Kono kono 3296 pot e direction ulta — meter dekhe bujhun.)</li>
<li>12 V set kore load (bulb) lagan, supply current limit 3 A koren. Bulb jolbe, voltage thik thakbe.</li>
<li><b>CC set:</b> load khule, J2 te multimeter (10 A range) direct lagan (short) → current dekhaben → RV2 ghurie jei current limit chan set korun (0.9–8.3 A).</li></ol>

<h2>5. Protection test (ichhe kore vhul connection)</h2>
<table><tr><th>Test (supply current limit 1 A rakhun)</th><th>Expected</th></tr>
<tr><td>Input + ar − ulta (12 V)</td><td>Red IN LED jolbe, output 0, kichu gorom na. Thik kore lagale abar chalu.</td></tr>
<tr><td>Input 7 V (UV) / 45 V (OV)</td><td>Output bondho, red IN LED (OV/UV). 8.2 V er upore / 39 V er niche abar chalu.</td></tr>
<tr><td>Output short (J2 + ar − jor)</td><td>CC limit e current, green LED on, board halka gorom. Short khulle abar normal.</td></tr>
<tr><td>Output e 12 V battery <b>ulta</b> (converter chalu, CV jekono)</td><td>Q7 ~1–6 µs e off, <b>red OUT LED</b>, battery theke current nai. Battery khulle abar normal.</td></tr>
<tr><td>Output e battery thik polarity te, input bondho</td><td>Battery drain hoy na (Q7 off), shudhu µA leakage.</td></tr></table>
<div class="card warn"><b>OUT− ke kokhono VIN− er sathe bahire jorben na (common ground na).</b> OUT− Q7 diye switch kora. Jorle converter cholbe, kintu (1) output e ulta battery ar block hobe na (F2 kete jabe), (2) tokhon input o ulta dile supply Q7 er body diode diye short hobe. Load ar supply alada (floating) rakhun — bench smoke-tester e emnitei thake.</div>
<div class="card warn"><b>Power limit:</b> CC pot emon bhabe set korun jate VOUT × ICC ≤ 80 W (jemon 36 V e ≤ 2.2 A). Beshi load dile board gorom hobe, PTC ~105 °C e current komabe; F1 (15 A) shudhu last resort.</div>

<h2>6. Full power (80 W)</h2>
<ul><li>Board er niche heatsink: thermal pad diye MOSFET/U1 area er bottom side heatsink e chepe lagan, M3 nylon spacer.</li>
<li>Input wire 1.5 mm² (9 V e 9.5 A input current), terminal screw tight.</li>
<li>Max: 8.3 A (CC max) ar 80 W — duto limit-i manben (jemon 24 V e 3.3 A).</li>
<li>Board 105 °C hole TH1 nije current komay; eta hole heatsink/airflow baran.</li></ul>

<h2>7. LED er mane</h2>
<table><tr><th>LED</th><th>Mane</th></tr><tr><td>Green (LED1)</td><td>Controller er power (INTVCC 5 V) ache.</td></tr>
<tr><td>Red IN (LED2)</td><td>Input ulta, ba input &gt; ~43 V / &lt; 7.5 V.</td></tr><tr><td>Red OUT (LED3)</td><td>Output e battery ulta lagano.</td></tr></table>

<h2>8. Troubleshooting</h2>
<table><tr><th>Problem</th><th>Check</th></tr>
<tr><td>Green LED jole na</td><td>Input &gt; 8.2 V? Red IN jolche? Polarity? U1 pin 7 (VIN) e voltage? EN pin (9) &gt; 1.22 V?</td></tr>
<tr><td>Green jole, output 0</td><td>CTRL (U1 pin 13) &gt; 0.3 V? (RV2 khub kom hole latch) RV2 ektu clockwise. Red OUT jolche?</td></tr>
<tr><td>Output voltage set hoy na</td><td>RV1 er solder, R25 (5.23 k) at U1 pin 19.</td></tr>
<tr><td>Load e voltage pore jay</td><td>CC limit kom set — RV2 clockwise. TP1 (ISMON) = 0.25 V + 10 × I × 12 mΩ.</td></tr>
<tr><td>Whine/shabdo, garom</td><td>Compensation (R22/C29/C30) start value — oscilloscope e load-step dekhe tune korun (README "limitations").</td></tr></table>

<h2>9. PCB</h2>
<div class="two"><div>{img_tag('pcb_top.png')}<p class="small">Top (power + parts)</p></div><div>{img_tag('pcb_bottom.png')}<p class="small">Bottom (GND plane, mirrored)</p></div></div>
<p>Bottom side er silkscreen e <b>BRACU Duburi logo</b> ar <b>"Designed by Jarif Alam"</b> lekha ache (bottom e kono part nei, tai heatsink lagano jay;
thermal pad logo-r upor dile kono shomossha nei).</p>
"""
def write_build_guide():
    open(os.path.join(SRC, 'build_guide.html'), 'w').write(page('SafeBuck-80 Build Guide', build_html()))

def render_pcb():
    """top / bottom copper + silkscreen renders of the routed board for the build guide"""
    os.makedirs(IMG, exist_ok=True)
    pcb = os.path.join(ROOT, 'hardware', 'kicad', 'SafeBuck-80.kicad_pcb')
    for name, layers, extra in (('pcb_top', 'F.Cu,F.Silkscreen,F.Mask,Edge.Cuts', []), ('pcb_bottom', 'B.Cu,B.Silkscreen,Edge.Cuts', ['--mirror'])):
        svg = os.path.join(IMG, name + '.svg')
        subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layers, '--page-size-mode', '2', '--exclude-drawing-sheet'] + extra + ['-o', svg, pcb], check=True, capture_output=True)
        subprocess.run(['node', os.path.join(DOCS, 'svg2png.js'), svg, os.path.join(IMG, name + '.png'), '1400'], check=True)
        os.remove(svg)


if __name__ == '__main__':
    render_pcb(); write_component_guide(); write_build_guide()
    sch = os.path.join(ROOT, 'hardware', 'kicad', 'SafeBuck-80.kicad_sch')
    subprocess.run(['kicad-cli', 'sch', 'export', 'pdf', '-o', os.path.join(DOCS, 'SafeBuck-80_Schematic.pdf'), sch], check=True)
    subprocess.run(['node', os.path.join(DOCS, 'print_pdf.js'),
                    os.path.join(SRC, 'component_guide.html'), os.path.join(DOCS, 'SafeBuck-80_Component_Guide.pdf'),
                    os.path.join(SRC, 'build_guide.html'), os.path.join(DOCS, 'SafeBuck-80_Build_Guide.pdf')], check=True)
