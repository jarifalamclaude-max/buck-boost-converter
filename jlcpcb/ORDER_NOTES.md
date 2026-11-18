# JLCPCB order notes — SafeBuck-80

Upload these three files, nothing else is needed:

| File | Where on jlcpcb.com |
|---|---|
| `SafeBuck-80_gerbers.zip` | **Order Now → Add gerber file** |
| `SafeBuck-80_BOM.csv` | PCB Assembly → **BOM** |
| `SafeBuck-80_CPL.csv` | PCB Assembly → **CPL / Pick and Place** |

## PCB settings

| Option | Choose | Why |
|---|---|---|
| Base material | FR-4 | |
| Layers | **2** | |
| Dimensions | auto (65 × 48 mm) | |
| PCB thickness | 1.6 mm | |
| **Outer copper weight** | **2 oz** | Carries 9.5 A input. The layout uses 0.2 mm tracks / 0.205 mm gaps, the 2 oz minimum |
| Surface finish | HASL lead-free (or ENIG) | |
| Via covering | Tented | |
| Remove order number | optional ("Specify a location" puts it under the silkscreen text) | |

## PCB Assembly settings

| Option | Choose |
|---|---|
| PCBA type | **Standard** (the board has extended parts and through-hole parts) |
| Assembly side | Top side |
| Tooling holes | Added by JLCPCB |
| Confirm parts placement | **Yes**, so a JLC engineer checks the rotations before production |

## Things to check before paying

1. **BOM match:** every line has an LCSC number. Stock was checked on 2026-11-18. If a part is out of stock:
   * Passives: choose another part with the same value, size and voltage.
   * **Do not substitute** U1 (LT8390), U2 (LM74930), Q1–Q7, L1, R15, R31, D15, C7/C8/C12–C14/C36 (10 µF **100 V**) or TH1.
   * Only one exception: if C18 (EEHZA1H470P) is out of stock, use EEHZC1H470P (LCSC C454346). It has the same footprint but a
     lower ripple rating, so with 9 V input stay at or below 65 W.
2. **Placement preview:** compare each of these with the silkscreen:
   * the pin-1 dot of U1 and U2;
   * the 4-lead side of every MOSFET (Q1–Q7);
   * the cathode bar of the diodes and LEDs;
   * the "+" of C11 and C18.

   If a part is rotated wrongly, change its rotation in the JLC preview by 90° or 180°. The CPL already applies the usual
   KiCad → JLC corrections for SOT-23, QFN, TSSOP and electrolytic caps.
3. **Through-hole parts** (J1, J2 screw terminals; RV1, RV2 pots): let JLC fit them (THT assembly), or delete them from the
   BOM and solder them yourself. They are easy, large pins.
4. **Not fitted (DNP):** R18, C26, R19, C27 (snubbers), the net-ties NT1–NT4, the test points and the mounting holes are not in
   the BOM. That is intentional.
5. **Smallest parts:** D16 is SOD-523 and R47 is 0402. Both are standard for JLC.

## After delivery

Follow `docs/SafeBuck-80_Build_Guide.pdf`, section 3 onwards: visual check, then the first power-up with a current-limited
supply.
