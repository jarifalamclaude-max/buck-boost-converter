# SafeBuck-80 — PCB layout rules (2 layers, 2 oz copper)

These rules were applied when the board was placed and routed (`hardware/placement.py`,
`hardware/route.py`). If you change the layout, follow them. Most come from the LT8390
datasheet layout section plus the buck-design notes you gave me.

## 1. Stack-up and manufacturing limits

| Item | Value | Why |
|---|---|---|
| Layers | 2 (top = power + parts, bottom = solid GND) | Cheap, and 2 oz copper carries 10 A |
| Copper | 2 oz (70 µm) outer | 9.5 A input current, low I²R heating |
| Board | 65 × 48 mm, 1.6 mm FR-4, 1 mm corner radius | Same size as the QS-1212CCBD module |
| Track / gap (signals) | 0.20 mm / 0.205 mm | JLCPCB minimum for 2 oz copper is 0.2 mm / 0.2 mm (8 mil) |
| Zone clearance | 0.25 mm | Power copper to other nets |
| Via | 0.6 mm pad / 0.3 mm drill | JLCPCB standard via (no extra cost) |
| Copper to board edge | 0.3 mm | JLCPCB routed-edge rule |

## 2. Hot loops (the most important rule)

A 4-switch buck-boost has **two** loops where the current switches in nanoseconds:

* **Hot loop 1 (buck side):** VIN_P → Q3 (switch A) → SW1 → Q4 (switch B) → GND → C7/C8 → back to VIN_P.
* **Hot loop 2 (boost side):** SW2 → Q6 (switch D) → VOUT_C → C12/C13/C14 → GND → Q5 (switch C) → back to SW2.

How it is done on this board:

* Each FET pair sits side by side (Q3 at 270°, Q4 at 90°; Q5 at 90°, Q6 at 270°), so the two
  switching pins face each other along one edge. The input/output ceramic caps sit **directly under**
  the pair and touch the drain of one FET and the source pins of the other.
* The whole loop is closed on the **top layer**, with no vias (zones `VIN_P`, `SW1`, `GND_top1` and
  `SW2`, `VOUT_C`, `GND_top2` in `route.py`). The loop area is about 0.3 cm².
* The hot-loop GND areas are separate zones that are also keepouts for the autorouter, so no signal
  trace can cut the return path.
* The bottom layer under the power stage is solid GND: it acts as an image plane and halves the loop
  inductance.

## 3. Switch nodes (SW1, SW2) — small, but wide enough

* SW1 and SW2 copper is only as large as the current needs (each is a short bar between the FETs plus
  a corridor to the inductor pad). A large switch-node area radiates EMI; a thin one heats up.
* No sensitive trace (FB, CTRL, VC, ISP/ISN, LSP/LSN) runs on the top layer under or next to a switch
  node. On the bottom layer such a trace may cross under a switch node only at right angles.
* The R/C snubber footprints R18/C26 (SW1) and R19/C27 (SW2) are placed but **not fitted**. Fit them only if
  an oscilloscope shows ringing above about 10 V at the switch node.

## 4. Kelvin current sensing

* RSENSE (R15, 3 mΩ) and RIS (R31, 12 mΩ) each have their own sense lines taken from the inside edge of
  the shunt pads through **net-ties** (NT1–NT4). That way the power current never flows in the sense
  lines.
* LSP/LSN and ISP/ISN run as close pairs to U1. ISP/ISN have 10 Ω + antiparallel diodes at U1 (R28,
  R29, D8, D9), which also protects the pins during a reversed-battery hit.

## 5. Controller (U1 LT8390) placement

* All of U1's small parts are within about 5 mm of their pins:
  * VIN, INTVCC, VREF bypass caps on the left;
  * RT, VC compensation, SS, FB divider and the VOUT RC on the right;
  * BST caps at the top corners.
* U1's exposed pad has 10 thermal vias (0.3 mm) into the bottom GND plane. The LT8390 loses up to about
  1 W in its INTVCC regulator at 36 V in.
* The FB bottom resistor (R25) and its 47 pF filter (C33) sit **at the FB pin**. The long trace runs to
  the CV pot (RV1, at the board edge so it can be adjusted), and the pot side of that trace is
  low-impedance.

## 6. Ground

* There is one GND net. Power ground (FET sources, caps) and signal ground (U1 pin 29, RT, SS, VC) meet
  at U1's exposed pad, and the bottom-layer plane connects everything.
* GND stitching vias are added on a 2.6 mm grid wherever both layers are GND. That keeps the two GND
  layers one low-inductance node and spreads heat.

## 7. Thermal

* Bare board at the worst-case point (9 V in, 9 V out, 80 W): about 5.7 W loss, which is about +57 °C board
  rise. **For the full 80 W, screw a 40 × 40 mm aluminium heatsink under the board** with a thermal pad
  (the calculation says the rise then drops to about +27 °C).
* The PTC (TH1) sits next to the buck FETs Q3/Q4. When the board gets too hot it pulls CTRL down and the
  output current folds back (4.7 kΩ at 105 °C). At about 120 °C it stops switching.

## 8. Protection parts placement

* The input protection (F1, D1, Q1, Q2, U2) sits right behind the input terminal J1, so a fault never
  reaches the converter.
* The output reverse-battery switch Q7 sits in the OUT− return next to J2. Its trip circuit (Q8 to Q11) is
  grouped between the inductor and R31, so the trip loops stay short.
* The red LEDs: LED2 (input fault) is next to J1 and LED3 (output reversed) is next to J2. The green LED1
  (power) sits between the pots.
* D15 (the VOUT_C clamp Schottky) and the 4th output capacitor C36 sit right of Q6, on a copper extension of the VOUT_C zone,
  with their GND pads on the top-layer GND pour and stitched to the bottom plane.
* D17 (Q1 gate clamp) sits next to Q1/Q2. R46/D14 (FB protection) sit between U1 and the inductor.
