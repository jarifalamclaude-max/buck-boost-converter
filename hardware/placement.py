"""Placement table: ref -> (x_mm, y_mm, rotation_deg) in board-local coordinates.
(0,0) = top-left corner of the 72 x 54 mm board (parts inside the first 65 x 48 mm), y grows downward, rotation is CCW.

Power stage (see docs/layout-rules.md):
  QA(Q3) rot270 + QB(Q4) rot90 side by side: SW1 copper along their TOP edge,
  QA drain (VIN_P) and QB source (GND) at the BOTTOM edge, bridged by C7/C8 directly
  underneath -> hot loop 1 ~0.3 cm^2.  QC(Q5) rot90 + QD(Q6) rot270 mirror this for
  hot loop 2 with C12-C14.  RSENSE R15 joins SW1 to the inductor's left pad.
"""
PLACE = {
    'H1': (3.5, 3.5, 0), 'H2': (68.5, 3.5, 0), 'H3': (3.5, 50.5, 0),
    # terminals (wire entry at the board edge)
    'J1': (5.5, 22.52, 270),     # wire entry faces the left edge; pin1 GND y=22.52, pin2 VIN+ y=27.6
    'J2': (66.0, 44.28, 90),     # wire entry faces the right edge; pin1 OUT- y=44.28, pin2 OUT+ y=39.2
    # ---- power stage
    'Q3': (15.6, 14.8, 270), 'Q4': (21.3, 14.8, 90),
    'C7': (18.45, 20.25, 0), 'C8': (18.45, 23.55, 0),
    'R15': (26.2, 14.4, 270),
    'L1': (38.0, 27.4, 0),       # Coilcraft XAL1510: pad1 (SWL) x=32.7, pad2 (SW2) x=43.3
    'Q5': (49.6, 13.6, 90), 'Q6': (55.3, 13.6, 270),
    'C12': (52.4, 18.95, 180), 'C13': (52.4, 22.25, 180), 'C14': (52.4, 25.55, 180),
    'C18': (60.1, 22.9, 270),
    'C36': (61.9, 8.9, 0), 'D15': (61.9, 13.6, 90),      # 4th COUT MLCC + VOUT_C clamp Schottky, right of Q6
    'R31': (59.6, 30.4, 0),
    'F2': (59.6, 34.25, 180),
    'Q7': (50.2, 42.4, 0),
    'C11': (14.0, 5.6, 0),
    # ---- controller (top centre). U1 rot0: gate pins at the top of both columns,
    #      analog pins (VREF/CTRL/ISP left, VC/RT/FB/SS right) at the lower half.
    'U1': (37.4, 7.0, 0),
    # bypass caps left of U1, rotated 180 so pad 1 (signal) faces the pin and the GND pad faces away
    'C19': (31.2, 6.86, 180), 'C21': (31.26, 8.97, 180), 'C22': (31.35, 10.92, 180),   # VIN, INTVCC (pins 7-8)
    'C23': (31.35, 12.52, 180), 'C34': (32.56, 14.06, 180),                        # VREF, CTRL filter (pins 12-13)
    'C20': (42.4, 4.4, 0), 'R45': (44.6, 4.4, 0),                          # VOUT pin 24 RC filter
    'R20': (42.4, 6.0, 0), 'R22': (42.4, 7.6, 0), 'C29': (45.4, 7.6, 90), 'C30': (42.4, 9.2, 0),  # RT, VC
    'R25': (45.4, 2.4, 90), 'C33': (47.0, 2.4, 90),                        # FB bottom + filter
    'C28': (42.4, 10.8, 0), 'R21': (42.4, 12.4, 0),                        # SS
    'C24': (32.75, 3.75, 90),                                             # BST1 cap at pins 2-3
    'C25': (42.05, 3.75, 90),                                             # BST2 cap at pins 26-27
    'R23': (27.0, 4.6, 90), 'R24': (27.0, 8.4, 90),                        # EN/UVLO
    'R26': (29.4, 10.6, 90),
    'RV1': (29.4, 44.6, 0), 'RV2': (41.2, 44.6, 0),
    'R28': (49.8, 1.6, 0), 'R29': (53.2, 1.6, 0), 'D8': (49.8, 3.6, 0), 'D9': (53.6, 3.6, 0),
    'TP1': (40.4, 14.8, 0),
    'R46': (38.0, 17.4, 0), 'D14': (34.0, 17.4, 0),       # FB series R + 5.1 V clamp
    # ---- input protection (left / bottom-left)
    'F1': (6.0, 33.4, 0),                    # pad1 VIN_RAW under J1 pin1, pad2 VIN_F
    'D1': (12.0, 36.4, 90),                  # TVS right after the fuse
    'Q2': (17.4, 30.2, 90), 'Q1': (17.4, 37.4, 270),
    'U2': (24.4, 31.0, 180),
    'R1': (9.0, 40.2, 90), 'C1': (12.0, 41.8, 0), 'C2': (8.6, 36.6, 90),
    'D2': (22.4, 35.8, 0), 'R3': (25.6, 35.6, 90), 'D3': (25.4, 39.0, 0), 'C3': (22.6, 38.6, 90),
    'C4': (24.6, 34.6, 0), 'C35': (20.6, 34.6, 0), 'D17': (14.0, 32.4, 90), 'R4': (21.8, 26.6, 90), 'C5': (23.6, 26.6, 90),
    'R5': (25.6, 21.2, 90), 'R6': (25.6, 24.4, 90), 'R7': (25.6, 27.6, 90),
    'LED2': (1.6, 33.6, 90),
    'D4': (3.4, 38.0, 0), 'R11': (8.453, 44.819, 90), 'R12': (15.508, 43.328, 90),
    'D5': (11.712, 45.2, 0), 'D6': (20.6, 43.4, 0), 'D7': (13.236, 24.678, 0),
    'TH1': (13.4, 9.6, 90),
    # ---- output protection small-signal, grouped by function (courtyard-exact, see docs/layout-rules.md)
    #  region A (between L1 and C12-C14 / R31): Q_R hold-off (Q10), Q_P trip (Q9), Q_N trip (Q11)
    'Q10': (48.0, 22.8, 0), 'R40': (48.0, 25.35, 0), 'R39': (48.0, 26.9, 0),
    'R41': (47.6, 28.5, 0), 'R38': (50.3, 28.75, 90), 'Q9': (53.5, 29.45, 180),
    'Q11': (48.0, 32.1, 0), 'R44': (50.85, 32.45, 90), 'R36': (53.6, 32.0, 0), 'R37': (53.6, 33.55, 0),
    'D16': (52.5, 37.3, 0), 'R47': (52.75, 38.7, 0),   # SOD-523 / 0402 to fit beside Q7
    'D13': (47.75, 34.85, 0), 'D11': (51.3, 35.35, 0), 'R42': (47.6, 36.65, 0), 'D12': (51.3, 37.45, 0),
    #  region B (below L1): VG10 gate supply + trip transistor Q8, then LED1 / pot divider row
    'R32': (32.35, 37.65, 0), 'C32': (36.2, 37.65, 0), 'D10': (39.7, 37.65, 0), 'Q8': (43.75, 37.65, 0),
    'LED1': (31.8, 40.7, 0), 'R30': (35.1, 40.7, 0), 'R27': (38.2, 40.7, 0), 'R35': (41.3, 40.7, 0), 'R34': (44.4, 40.7, 0),
    'R33': (45.0, 43.6, 90),
    #  region D (bottom edge, next to the output terminal): RED OUT indicator
    'R43': (46.3, 46.45, 0), 'LED3': (50.6, 46.5, 0),
    # Kelvin net-ties: real position computed in build_pcb.place_tie()
    'NT1': (0, 0, 0), 'NT2': (0, 0, 0), 'NT3': (0, 0, 0), 'NT4': (0, 0, 0),
}
