#!/bin/bash
# Build the PCB placement, list courtyard overlaps and render a PNG preview.
# Output goes to $OUT (default: ./build).
cd "$(dirname "$0")"
OUT=${OUT:-$(pwd)/build}; mkdir -p "$OUT"
/usr/bin/python3 build_pcb.py > "$OUT/build.log" 2>&1
grep -E "NOT PLACED|NO ROOM|outside board|Error|Traceback" "$OUT/build.log"
awk '/courtyards_overlap/{getline; getline a; getline b; match(a,/Footprint [A-Z0-9]+/); x=substr(a,RSTART+10,RLENGTH-10); match(b,/Footprint [A-Z0-9]+/); y=substr(b,RSTART+10,RLENGTH-10); print x"-"y}' kicad/drc_placement.rpt | sort -u | tr '\n' ' '; echo
echo "overlaps: $(grep -c courtyards_overlap kicad/drc_placement.rpt)"
kicad-cli pcb export svg --layers "F.Cu,F.Courtyard,Edge.Cuts,F.Silkscreen" --page-size-mode 2 --exclude-drawing-sheet -o "$OUT/pcb_place.svg" kicad/SafeBuck-80_placed.kicad_pcb >/dev/null 2>&1 && echo "svg: $OUT/pcb_place.svg"
