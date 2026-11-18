"""
SafeBuck-80 — single source of truth for the whole design.

Every part below has: reference, value, KiCad footprint, MPN, its role, and a
pad -> net map that uses the *footprint pad numbers*.  The KiCad schematic, the
PCB, the BOM, the JLCPCB files and the review all come from this file, so they
cannot disagree with each other.

Pad conventions used here (checked against the KiCad 7 footprints):
  - 2-pin R/C/L/fuse/terminal: 1, 2
  - CP_Elec (electrolytic): 1 = +, 2 = -
  - KiCad diode footprints (SOD-123/323, SMB): 1 = cathode, 2 = anode
  - LED_0805: 1 = cathode, 2 = anode
  - SOT-23 BAS21 / BZX84: 1 = anode, 2 = n.c., 3 = cathode
  - SOT-23 MMBT3904 / MMBT5401: 1 = base, 2 = emitter, 3 = collector
  - TDSON-8-1 (TI SON 5x6 'Q5A/Q5B'): 1,2,3 = source, 4 = gate, 5 = drain pad
  - Bourns 3296W: 1, 2 = wiper, 3
  - LT8390 FE (TSSOP-28 + EP): 1..28 per datasheet, 29 = exposed pad (GND)
  - LM74930 RGE (VQFN-24 + EP): 1..24 per datasheet, 25 = exposed pad (RTN, must float)
"""

FP = dict(
    R0402='Resistor_SMD:R_0402_1005Metric',
    R0603='Resistor_SMD:R_0603_1608Metric',
    R0805='Resistor_SMD:R_0805_2012Metric',
    R1206='Resistor_SMD:R_1206_3216Metric',
    R2512='Resistor_SMD:R_2512_6332Metric',
    C0603='Capacitor_SMD:C_0603_1608Metric',
    C0805='Capacitor_SMD:C_0805_2012Metric',
    C1206='Capacitor_SMD:C_1206_3216Metric',
    C1210='Capacitor_SMD:C_1210_3225Metric',
    CP10='Capacitor_SMD:CP_Elec_10x10',
    CP8='Capacitor_SMD:CP_Elec_8x10',
    SON5x6='Package_TO_SOT_SMD:TDSON-8-1',
    SOT23='Package_TO_SOT_SMD:SOT-23',
    SOD123='Diode_SMD:D_SOD-123',
    SOD323='Diode_SMD:D_SOD-323',
    SOD523='Diode_SMD:D_SOD-523',
    SOD128='Diode_SMD:D_SOD-128',
    SMB='Diode_SMD:D_SMB',
    LED0805='LED_SMD:LED_0805_2012Metric',
    FUSE='Fuse:Fuse_Littelfuse-NANO2-451_453',
    IND='Inductor_SMD:L_Coilcraft_XAL1510-103',
    POT='Potentiometer_THT:Potentiometer_Bourns_3296W_Vertical',
    TERM='TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',
    LT8390='SafeBuck:LT8390_FE28_EB_TSSOP-28_EP4.75x2.74mm',
    LM74930='Package_DFN_QFN:HVQFN-24-1EP_4x4mm_P0.5mm_EP2.1x2.1mm',
    TP='TestPoint:TestPoint_Pad_D1.5mm',
    HOLE='MountingHole:MountingHole_3.2mm_M3',
    NETTIE='NetTie:NetTie-2_SMD_Pad0.5mm',
)

# JLCPCB / LCSC part numbers (all checked in stock in the JLCPCB parts library on 2026-11-18).
# Passives are generic: any 1 % resistor / X7R-C0G capacitor of the same size and rating works.
LCSC = {
    # ICs and power semiconductors
    'U1': 'C673802', 'U2': 'C22428070',
    'Q1': 'C473333', 'Q2': 'C473333', 'Q7': 'C473333',
    'Q3': 'C882766', 'Q4': 'C882766', 'Q5': 'C882766', 'Q6': 'C882766',
    'L1': 'C3911782', 'R15': 'C723728', 'R31': 'C19633815',
    'F1': 'C44480', 'F2': 'C44479', 'D1': 'C115824',
    'C7': 'C576517', 'C8': 'C576517', 'C12': 'C576517', 'C13': 'C576517', 'C14': 'C576517', 'C36': 'C576517',
    'C11': 'C128460', 'C18': 'C454653',
    # small semiconductors
    'D2': 'C79596', 'D4': 'C79596', 'D5': 'C79596', 'D6': 'C79596', 'D7': 'C79596', 'D12': 'C2128', 'D13': 'C2128',
    'D3': 'C238878', 'D10': 'C82476', 'D11': 'C2128', 'D8': 'C2128', 'D9': 'C2128',
    'Q8': 'C20526', 'Q11': 'C20526', 'Q9': 'C8326', 'Q10': 'C8326',
    'LED1': 'C2297', 'LED2': 'C84256', 'LED3': 'C84256',
    'TH1': 'C152572', 'RV1': 'C58354', 'RV2': 'C83686', 'J1': 'C8465', 'J2': 'C8465',
    # capacitors
    'C1': 'C55151', 'C2': 'C15725', 'C3': 'C105952', 'C19': 'C105952', 'C20': 'C105952', 'C35': 'C105952',
    'C4': 'C64705', 'C28': 'C21120', 'C5': 'C113805', 'C21': 'C95841',
    'C22': 'C29936', 'C24': 'C29936', 'C25': 'C29936', 'C23': 'C1623', 'C29': 'C21122',
    'C30': 'C14858', 'C32': 'C14663', 'C33': 'C1671', 'C34': 'C57112',
    # resistors
    'R1': 'C17928', 'R3': 'C17513', 'R4': 'C22775', 'R5': 'C17597', 'R6': 'C22821', 'R7': 'C23042',
    'R11': 'C18028', 'R12': 'C18028', 'R16': 'C21189', 'R17': 'C21189', 'R20': 'C22875', 'R21': 'C25803',
    'R22': 'C25804', 'R23': 'C17539', 'R24': 'C23059', 'R25': 'C23068', 'R26': 'C4184', 'R27': 'C25971',
    'R28': 'C22859', 'R29': 'C22859', 'R30': 'C4190', 'R32': 'C17902', 'R33': 'C25804', 'R34': 'C23162',
    'R35': 'C25819', 'R36': 'C23212', 'R37': 'C25971', 'R38': 'C25804', 'R39': 'C25804', 'R40': 'C25803',
    'R41': 'C31850', 'R42': 'C25804', 'R43': 'C17902', 'R44': 'C21190', 'R45': 'C22775', 'R46': 'C25804', 'R47': 'C25741',
    'D14': 'C75074', 'D15': 'C5260346', 'D16': 'C27748', 'D17': 'C603316',
}

import uuid
def sym_uuid(ref):
    """Deterministic UUID shared by the schematic symbol and its PCB footprint (keeps them linked)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'SafeBuck-80/' + ref))

PARTS = []
def part(ref, value, fp, pins, mpn='', mfr='', role='', block='', dnp=False, lcsc=''):
    PARTS.append(dict(ref=ref, value=value, fp=FP.get(fp, fp), pins=pins, mpn=mpn, mfr=mfr,
                      role=role, block=block, dnp=dnp, lcsc=lcsc or LCSC.get(ref, '')))

# =====================================================================================
# 1. INPUT PROTECTION  (LM74930: reverse -60 V, OV cut-off 41 V, UV 7.6 V; F1 for internal failure)
# =====================================================================================
B = 'input'
part('J1', 'VIN 9-36V', 'TERM', {'1': 'VIN_RAW', '2': 'GND'}, 'WJ500V-5.08-2P', 'Kangnex', 'Input screw terminal 5.08 mm, 18 A (pin 1 = +)', B)
part('F1', '15A 65V', 'FUSE', {'1': 'VIN_RAW', '2': 'VIN_F'}, '0451015.MRL', 'Littelfuse', 'Last-resort input fuse (only blows if a MOSFET fails short)', B)
part('D1', 'SMBJ60CA', 'SMB', {'1': 'VIN_F', '2': 'GND'}, 'SMBJ60CA', 'Littelfuse', 'Bidirectional TVS: clamps fast spikes, silent up to 60 V DC either polarity (clamp 96.8 V < 100 V FETs)', B)
part('R1', '1R', 'R1206', {'1': 'VIN_F', '2': 'SNUB'}, '', '', 'Snubber damping resistor (kills cable-LC ringing at hot-plug)', B)
part('C1', '2.2uF 100V X7R', 'C1210', {'1': 'SNUB', '2': 'GND'}, '', '', 'Snubber capacitor', B)
part('C2', '100nF 100V X7R', 'C0603', {'1': 'VIN_F', '2': 'GND'}, '', '', 'LM74930 input bypass (datasheet min 0.1 uF)', B)
part('Q1', 'CSD19532Q5B', 'SON5x6', {'1': 'CSRC', '2': 'CSRC', '3': 'CSRC', '4': 'HGATE', '5': 'VIN_F'},
     'CSD19532Q5B', 'TI', 'Input disconnect FET (HGATE): opens on OV/UV/overcurrent', B)
part('Q2', 'CSD19532Q5B', 'SON5x6', {'1': 'CSRC', '2': 'CSRC', '3': 'CSRC', '4': 'DGATE', '5': 'VIN_P'},
     'CSD19532Q5B', 'TI', 'Ideal-diode FET (DGATE): blocks reverse polarity', B)
part('U2', 'LM74930-Q1', 'LM74930', {
    '1': 'DGATE', '2': 'CSRC', '3': 'U2_SW', '4': 'UVLO', '5': 'OV', '6': 'VS', '7': 'VS', '8': 'NC_U2_8',
    '9': 'GND', '10': 'NC_U2_IMON', '11': 'GND', '12': 'FLT', '13': 'GND', '14': 'HGATE', '15': 'CSRC',
    '16': 'GND', '17': 'NC_U2_17', '18': 'VIN_P', '19': 'VIN_P', '20': 'VIN_P', '21': 'NC_U2_21', '22': 'VS',
    '23': 'CAP', '24': 'VIN_P', '25': 'RTN'},
    'LM74930QRGERQ1', 'TI', 'Input protection controller: reverse/OV/UV + FLT output (breaker disabled: TMR, ILIM to GND, CS+/CS-/ISCP to C)', B)
part('D2', 'BAS21', 'SOT23', {'1': 'VIN_F', '3': 'VSD'}, 'BAS21', '', 'Feeds VS; blocks negative input so VS never goes below -1 V', B)
part('R3', '1k', 'R0805', {'1': 'VSD', '2': 'VS'}, '', '', 'Limits clamp current into D3 during spikes', B)
part('D3', 'BZX84C62', 'SOT23', {'1': 'GND', '3': 'VS'}, 'BZX84C62', '', 'Clamps VS below 70 V abs max', B)
part('C3', '1uF 100V X7R', 'C0805', {'1': 'VS', '2': 'GND'}, '', '', 'VS bypass (datasheet min 1 uF)', B)
part('C4', '220nF 50V X7R', 'C0603', {'1': 'CAP', '2': 'VS'}, '', '', 'Charge-pump capacitor (>=10x Ciss of Q1+Q2), 50 V = >2x the 14 V across it', B)
part('R4', '100R', 'R0603', {'1': 'HGATE', '2': 'CDV'}, '', '', 'RG in series with CdVdT (keeps turn-off fast)', B)
part('C5', '3.3nF 100V X7R', 'C0603', {'1': 'CDV', '2': 'GND'}, '', '', 'CdVdT: inrush 1.3-2.6 A, 1.6 ms ramp', B)
part('D17', 'MM3Z15V', 'SOD323', {'1': 'HGATE', '2': 'CSRC'}, 'MM3Z15VT1G', 'onsemi', 'DZ1 (TI Fig. 8-1): clamps Q1 VGS to 15 V when the input is shorted while running (C5 would hold the gate up)', B)
part('C35', '1uF 100V X7R', 'C0805', {'1': 'CSRC', '2': 'GND'}, '', '', 'CCS: common-source node capacitor (TI LM74930 Fig. 8-1)', B)
part('R5', '280k 1%', 'R0805', {'1': 'VIN_F', '2': 'UVLO'}, '', '', 'UV/OV ladder top (0805 for 60 V)', B)
part('R6', '17.8k 1%', 'R0603', {'1': 'UVLO', '2': 'OV'}, '', '', 'UV/OV ladder middle', B)
part('R7', '4.22k 1%', 'R0603', {'1': 'OV', '2': 'GND'}, '', '', 'UV/OV ladder bottom: OV trip 42.9 V, release 39.4 V (a 36 V supply always restarts)', B)
# RED "IN" LED: lights on FLT (OV / UV / breaker) or when the input is reversed
part('D4', 'BAS21', 'SOT23', {'1': 'VIN_F', '3': 'A1'}, 'BAS21', '', 'RED IN: FLT path feed from input (blocks when reversed)', B)
part('R11', '5.6k', 'R1206', {'1': 'A1', '2': 'RIN2'}, '', '', 'RED IN current limit, shared by both paths (1206 for 60 V)', B)
part('R12', '5.6k', 'R1206', {'1': 'RIN2', '2': 'AIN'}, '', '', 'RED IN current limit', B)
part('D5', 'BAS21', 'SOT23', {'1': 'GND', '3': 'A1'}, 'BAS21', '', 'RED IN: reverse-polarity path from GND', B)
part('LED2', 'RED  IN', 'LED0805', {'2': 'AIN', '1': 'KIN'}, '', '', 'Input fault / reversed input indicator', B)
part('D6', 'BAS21', 'SOT23', {'1': 'KIN', '3': 'FLT'}, 'BAS21', '', 'Protects FLT pin from negative voltage', B)
part('D7', 'BAS21', 'SOT23', {'1': 'KIN', '3': 'VIN_F'}, 'BAS21', '', 'RED IN: reverse path into negative VIN', B)

# =====================================================================================
# 2. POWER STAGE + CONTROLLER (LT8390, 300 kHz +/-15 % spread, peak-buck/peak-boost)
# =====================================================================================
B = 'converter'
part('U1', 'LT8390', 'LT8390', {
    '1': 'BG1', '2': 'BST1', '3': 'SW1', '4': 'TG1', '5': 'LSP', '6': 'LSN', '7': 'VIN_P', '8': 'INTVCC',
    '9': 'EN', '10': 'GND', '11': 'VREF', '12': 'VREF', '13': 'CTRL', '14': 'ISP_R', '15': 'ISN_R',
    '16': 'ISMON', '17': 'PGOOD', '18': 'SS', '19': 'FB', '20': 'VC', '21': 'RT', '22': 'INTVCC',
    '23': 'NC_U1_LOADTG', '24': 'VOUT_U1', '25': 'TG2', '26': 'SW2', '27': 'BST2', '28': 'BG2', '29': 'GND'},
    'LT8390EFE#TRPBF', 'Analog Devices', '4-switch synchronous buck-boost controller (CV via FB, CC via CTRL)', B)
part('Q3', 'CSD18532Q5B', 'SON5x6', {'1': 'SW1', '2': 'SW1', '3': 'SW1', '4': 'TG1', '5': 'VIN_P'}, 'CSD18532Q5B', 'TI', 'Switch A (buck high side), 60 V, 4.3 mOhm max @4.5 V, Qg 19 nC @4.5 V', B)
part('Q4', 'CSD18532Q5B', 'SON5x6', {'1': 'GND', '2': 'GND', '3': 'GND', '4': 'BG1', '5': 'SW1'}, 'CSD18532Q5B', 'TI', 'Switch B (buck low side)', B)
part('Q5', 'CSD18532Q5B', 'SON5x6', {'1': 'GND', '2': 'GND', '3': 'GND', '4': 'BG2', '5': 'SW2'}, 'CSD18532Q5B', 'TI', 'Switch C (boost low side)', B)
part('Q6', 'CSD18532Q5B', 'SON5x6', {'1': 'SW2', '2': 'SW2', '3': 'SW2', '4': 'TG2', '5': 'VOUT_C'}, 'CSD18532Q5B', 'TI', 'Switch D (boost high side)', B)
part('R15', '3m 1% 2512', 'R2512', {'1': 'SW1', '2': 'SWL'}, 'WSL2512R0030FEA (or eq.)', 'Vishay', 'RSENSE inductor current (peak limit 11.7-21.7 A)', B)
part('NT1', 'NetTie', 'NETTIE', {'1': 'LSP', '2': 'SW1'}, '', '', 'Kelvin tap: LSP at RSENSE pad 1', B)
part('NT2', 'NetTie', 'NETTIE', {'1': 'LSN', '2': 'SWL'}, '', '', 'Kelvin tap: LSN at RSENSE pad 2', B)
part('L1', '10uH 26A', 'IND', {'1': 'SWL', '2': 'SW2'}, 'XAL1510-103MED', 'Coilcraft', 'Power inductor 10 uH, Isat 26.3 A (30 % drop), Irms 16 A (20 C rise), DCR 9 mOhm max, AEC-Q200', B)
for i, ref in enumerate(['C7', 'C8']):
    part(ref, '10uF 100V X7S', 'C1210', {'1': 'VIN_P', '2': 'GND'}, 'GRM32EC72A106KE05L', 'Murata', 'CIN ceramic (hot loop 1) — bridges Q3 drain and Q4 source directly', B)
part('C11', '100uF 63V', 'CP10', {'1': 'VIN_P', '2': 'GND'}, 'EEE-FK1J101P', 'Panasonic', 'CIN bulk: ESR 0.35 ohm damps cable LC (Middlebrook)', B)
for ref in ['C12', 'C13', 'C14', 'C36']:
    part(ref, '10uF 100V X7S', 'C1210', {'1': 'VOUT_C', '2': 'GND'}, 'GRM32EC72A106KE05L', 'Murata', 'COUT ceramic (hot loop 2) — bridges Q6 drain and Q5 source directly', B)
part('C18', '47uF 50V hybrid', 'CP8', {'1': 'VOUT_C', '2': 'GND'}, 'EEHZA1H470P', 'Panasonic', 'COUT bulk hybrid polymer 8x10, ESR 30 mOhm, 1.8 A ripple @105 C, 10,000 h', B)
part('C19', '1uF 100V X7R', 'C0805', {'1': 'VIN_P', '2': 'GND'}, '', '', 'LT8390 VIN pin bypass (close to pin 7)', B)
part('R45', '100R', 'R0603', {'1': 'VOUT_C', '2': 'VOUT_U1'}, '', '', 'VOUT pin RC filter + current limit: <4 mA into pin 24 even if VOUT_C goes negative (pin draws <60 uA)', B)
part('C20', '1uF 100V X7R', 'C0805', {'1': 'VOUT_U1', '2': 'GND'}, '', '', 'LT8390 VOUT pin bypass / RC filter (tau 10 us)', B)
part('C21', '10uF 16V X7R', 'C0805', {'1': 'INTVCC', '2': 'GND'}, '', '', 'INTVCC (datasheet min 4.7 uF; 10 uF X7R keeps >4.7 uF at 5 V and works to 125 C)', B)
part('C22', '1uF 16V X7R', 'C0603', {'1': 'INTVCC', '2': 'GND'}, '', '', 'Extra INTVCC decoupling at the pin', B)
part('C23', '470nF 16V X7R', 'C0603', {'1': 'VREF', '2': 'GND'}, '', '', 'VREF bypass (datasheet 0.47 uF)', B)
part('R16', '0R', 'R0603', {'1': 'BST1', '2': 'BST1C'}, '', '', 'BST1 series: 0R, raise to 2-10R if SW1 rings (EMI tune)', B)
part('C24', '1uF 16V X7R', 'C0603', {'1': 'BST1C', '2': 'SW1'}, '', '', 'Bootstrap cap A (>=100x Qg)', B)
part('R17', '0R', 'R0603', {'1': 'BST2', '2': 'BST2C'}, '', '', 'BST2 series: 0R, raise to 2-10R if SW2 rings', B)
part('C25', '1uF 16V X7R', 'C0603', {'1': 'BST2C', '2': 'SW2'}, '', '', 'Bootstrap cap D', B)
part('R18', '2.2R', 'R1206', {'1': 'SW1', '2': 'SN1'}, '', '', 'SW1 RC snubber (DNP, fit only if scope shows ringing)', B, dnp=True)
part('C26', '470pF 100V', 'C0805', {'1': 'SN1', '2': 'GND'}, '', '', 'SW1 RC snubber (DNP)', B, dnp=True)
part('R19', '2.2R', 'R1206', {'1': 'SW2', '2': 'SN2'}, '', '', 'SW2 RC snubber (DNP)', B, dnp=True)
part('C27', '470pF 100V', 'C0805', {'1': 'SN2', '2': 'GND'}, '', '', 'SW2 RC snubber (DNP)', B, dnp=True)
part('R20', '140k 1%', 'R0603', {'1': 'RT', '2': 'GND'}, '', '', 'RT: 300 kHz (datasheet table 1)', B)
part('C28', '220nF 16V X7R', 'C0603', {'1': 'SS', '2': 'GND'}, '', '', 'Soft-start (10x VC cap)', B)
part('R21', '100k 1%', 'R0603', {'1': 'SS', '2': 'VREF'}, '', '', 'SS->VREF 100k = keep-running mode (CC into a short)', B)
part('R22', '10k 1%', 'R0603', {'1': 'VC', '2': 'VCR'}, '', '', 'Compensation R (start value, verify with load step)', B)
part('C29', '22nF X7R', 'C0603', {'1': 'VCR', '2': 'GND'}, '', '', 'Compensation C (zero 723 Hz)', B)
part('C30', '100pF C0G', 'C0603', {'1': 'VC', '2': 'GND'}, '', '', 'Compensation HF pole', B)
part('R23', '200k 1%', 'R0805', {'1': 'VIN_P', '2': 'EN'}, '', '', 'EN/UVLO top: on 7.05 V, off 6.48 V', B)
part('R24', '46.4k 1%', 'R0603', {'1': 'EN', '2': 'GND'}, '', '', 'EN/UVLO bottom', B)
part('RV1', '200k CV', 'POT', {'1': 'VOUT_C', '2': 'FBD', '3': 'FBD'}, '3296W-1-204', 'Bourns', 'CV adjust (25-turn): VOUT = 1 V x (RV1+R25)/R25 -> 1.6-39 V (>=35.4 V with a -10 % pot)', B)
part('R25', '5.23k 1%', 'R0603', {'1': 'FBD', '2': 'GND'}, '', '', 'FB divider bottom resistor', B)
part('R46', '10k', 'R0603', {'1': 'FBD', '2': 'FB'}, '', '', 'FB pin series resistor: limits current when a battery above 6x the CV setting back-drives the divider', B)
part('D14', 'MM3Z5V1', 'SOD323', {'1': 'FB', '2': 'GND'}, 'MM3Z5V1T1G', 'onsemi', 'Clamps FB pin below its 6 V abs max (with R46)', B)
part('C33', '47pF C0G', 'C0603', {'1': 'FB', '2': 'GND'}, '', '', 'FB noise filter at the pin (pole ~600 kHz, no loop impact)', B)
part('TH1', 'PRF18BC471', 'R0603', {'1': 'VREF', '2': 'CTRLP'}, 'PRF18BC471QB5RB', 'Murata', 'PTC: 470R cold, 4.7k@105C, 47k@120C -> thermal foldback/shutdown', B)
part('R26', '20k 1%', 'R0603', {'1': 'CTRLP', '2': 'CTRL'}, '', '', 'CTRL divider top', B)
part('RV2', '50k CC', 'POT', {'1': 'CTRL', '2': 'CTRLB', '3': 'CTRLB'}, '3296W-1-503', 'Bourns', 'CC adjust (25-turn): 0.94-8.3 A', B)
part('R27', '4.53k 1%', 'R0603', {'1': 'CTRLB', '2': 'GND'}, '', '', 'CTRL divider bottom (sets CTRL min 0.362 V > 0.34 V latch)', B)
part('C34', '10nF X7R', 'C0603', {'1': 'CTRL', '2': 'GND'}, '', '', 'CTRL noise filter at the pin', B)
part('R28', '10R', 'R0603', {'1': 'ISP_K', '2': 'ISP_R'}, '', '', 'ISP series (protects pin during faults)', B)
part('R29', '10R', 'R0603', {'1': 'ISN_K', '2': 'ISN_R'}, '', '', 'ISN series', B)
part('D8', '1N4148WS', 'SOD323', {'2': 'ISP_R', '1': 'ISN_R'}, '1N4148WS', '', 'Clamp ISP-ISN < 1 V abs max', B)
part('D9', '1N4148WS', 'SOD323', {'2': 'ISN_R', '1': 'ISP_R'}, '1N4148WS', '', 'Clamp (other direction)', B)
part('R30', '2.2k', 'R0603', {'1': 'INTVCC', '2': 'GLED'}, '', '', 'GREEN LED current ~1 mA', B)
part('LED1', 'GREEN ON', 'LED0805', {'2': 'GLED', '1': 'GND'}, '', '', 'Power ON (controller alive)', B)
part('TP1', 'ISMON', 'TP', {'1': 'ISMON'}, '', '', 'Output current monitor: 0.25 V + 10 x V(RIS)', B)
part('TP2', 'PGOOD', 'TP', {'1': 'PGOOD'}, '', '', 'Power good (open drain, low = in regulation)', B)

# =====================================================================================
# 3. OUTPUT: CC sense, low-side reverse-battery switch, fast trip, polarity hold
# =====================================================================================
B = 'output'
part('R31', '12m 1% 2512 2W', 'R2512', {'1': 'VOUT_C', '2': 'OUTF'}, 'WSLP2512R0120FEA (or eq. 2 W)', 'Vishay', 'RIS output current sense (CC full-scale 8.33 A, ISOC 62.5 A)', B)
part('NT3', 'NetTie', 'NETTIE', {'1': 'ISP_K', '2': 'VOUT_C'}, '', '', 'Kelvin tap ISP at RIS pad 1', B)
part('NT4', 'NetTie', 'NETTIE', {'1': 'ISN_K', '2': 'OUTF'}, '', '', 'Kelvin tap ISN at RIS pad 2', B)
part('F2', '10A 65V', 'FUSE', {'1': 'OUTF', '2': 'OUTP'}, '0451010.MRL', 'Littelfuse', 'Last-resort output fuse (never blows in normal faults)', B)
part('J2', 'VOUT', 'TERM', {'1': 'OUTP', '2': 'OUTN'}, 'WJ500V-5.08-2P', 'Kangnex', 'Output terminal 5.08 mm (pin 1 = +). OUT- is switched: never tie to VIN-', B)
part('D15', 'PMEG10030ELP', 'SOD128', {'1': 'VOUT_C', '2': 'GND'}, 'PMEG10030ELPX', 'Nexperia', 'Clamp: VOUT_C never below ~-1 V (inductive-load freewheel, reversed-battery hit); low-leakage 100 V Schottky', B)
part('Q7', 'CSD19532Q5B', 'SON5x6', {'1': 'GND', '2': 'GND', '3': 'GND', '4': 'QLSG', '5': 'OUTN'}, 'CSD19532Q5B', 'TI', 'Q_LS low-side output switch, 100 V: blocks reversed battery', B)
part('R32', '10k', 'R1206', {'1': 'VIN_P', '2': 'VG'}, '', '', 'VG10 supply feed (1206: up to 33 V across)', B)
part('D10', 'BZX84C10', 'SOT23', {'1': 'GND', '3': 'VG'}, 'BZX84C10', '', 'VG10 = min(VIN, 10 V) gate supply', B)
part('C32', '100nF 25V X7R', 'C0603', {'1': 'VG', '2': 'GND'}, '', '', 'VG10 decoupling', B)
part('R33', '10k', 'R0603', {'1': 'VG', '2': 'QLSG'}, '', '', 'Q_LS gate pull-up (slow, gentle turn-on)', B)
part('Q8', 'MMBT3904', 'SOT23', {'1': 'QTB', '2': 'GND', '3': 'QLSG'}, 'MMBT3904', '', 'Q_T: pulls Q_LS gate low on any trip', B)
part('R34', '4.7k', 'R0603', {'1': 'TRIP', '2': 'QTB'}, '', '', 'Q_T base resistor', B)
part('R35', '47k', 'R0603', {'1': 'QTB', '2': 'GND'}, '', '', 'Q_T base pull-down', B)
part('Q9', 'MMBT5401', 'SOT23', {'1': 'QPB', '2': 'VOUT_C', '3': 'QPC'}, 'MMBT5401', '', 'Q_P: fast over-current trip at ~1.0 V across RIS', B)
part('R36', '6.8k', 'R0603', {'1': 'VOUT_C', '2': 'QPB'}, '', '', 'Q_P base-emitter (threshold divider)', B)
part('R37', '4.53k', 'R0603', {'1': 'QPB', '2': 'OUTF'}, '', '', 'Q_P base to RIS low side', B)
part('R38', '10k', 'R0603', {'1': 'QPC', '2': 'TRIP'}, '', '', 'Q_P collector to TRIP', B)
part('Q10', 'MMBT5401', 'SOT23', {'1': 'QRB', '2': 'QRE', '3': 'QRC'}, 'MMBT5401', '', 'Q_R: holds Q_LS off while OUT- > OUT+ (battery reversed)', B)
part('D11', '1N4148WS', 'SOD323', {'2': 'OUTN', '1': 'QRE2'}, '1N4148WS', '', 'Blocks normal-polarity voltage (<=36 V) from Q_R emitter', B)
part('R39', '10k', 'R0603', {'1': 'QRE2', '2': 'QRE'}, '', '', 'Q_R emitter resistor', B)
part('R40', '100k', 'R0603', {'1': 'QRE', '2': 'QRB'}, '', '', 'Q_R E-B resistor (no reverse stress)', B)
part('R41', '22k', 'R0603', {'1': 'QRB', '2': 'OUTP'}, '', '', 'Q_R base to OUT+', B)
part('R42', '10k', 'R0603', {'1': 'QRC', '2': 'TRIP'}, '', '', 'Q_R collector to TRIP', B)
part('Q11', 'MMBT3904', 'SOT23', {'1': 'QNB', '2': 'QNE', '3': 'QLSG'}, 'MMBT3904', '', 'Q_N: pulls Q_LS gate low when OUT+ is dragged >1.85 V below GND (reversed battery at low CV setting)', B)
part('D16', '1N4148WT', 'SOD523', {'2': 'QNE', '1': 'QNE2'}, '1N4148WT', '', 'Q_N second emitter diode: trip threshold -1.85 V, so an inductive load freewheeling through D15 (-1 V) never trips Q7', B)
part('D13', '1N4148WS', 'SOD323', {'2': 'QNE2', '1': 'OUTP'}, '1N4148WS', '', 'Q_N emitter diode: blocks normal OUT+ (up to 39 V) from the 6 V base-emitter junction', B)
part('R47', '100k', 'R0402', {'1': 'QNE', '2': 'QNB'}, '', '', 'Q_N emitter-base shunt: D13/D16 leakage never reverse-biases the EB junction', B)
part('R44', '1k', 'R0603', {'1': 'QNB', '2': 'GND'}, '', '', 'Q_N base to GND (base drive ~1 mA during a fault)', B)
part('D12', '1N4148WS', 'SOD323', {'2': 'OUTN', '1': 'RO1'}, '1N4148WS', '', 'RED OUT: conducts only when OUT- > OUT+ (<=36 V reverse in normal use)', B)
part('R43', '10k', 'R1206', {'1': 'RO1', '2': 'AOUT'}, '', '', 'RED OUT current limit (<=35 V battery: 0.1 W)', B)
part('LED3', 'RED OUT', 'LED0805', {'2': 'AOUT', '1': 'OUTP'}, '', '', 'Reversed battery on output (powered by the battery itself)', B)

# mechanical
for i, ref in enumerate(['H1', 'H2', 'H3']):
    part(ref, 'M3', 'HOLE', {}, '', '', 'Mounting hole M3', 'mech')


def nets():
    """net -> list of (ref, pad)"""
    out = {}
    for p in PARTS:
        for pad, n in p['pins'].items():
            out.setdefault(n, []).append((p['ref'], pad))
    return out


if __name__ == '__main__':
    ns = nets()
    refs = [p['ref'] for p in PARTS]
    assert len(refs) == len(set(refs)), 'duplicate refs'
    singles = sorted(n for n, m in ns.items() if len(m) == 1)
    print(f"{len(PARTS)} parts, {len(ns)} nets")
    print('single-pin nets (must be intentional n.c./test points):', singles)
