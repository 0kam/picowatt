#!/usr/bin/env python3
# WARNING -----------------------------------------------------------------
# This is the generator that produced the initial KiCad project.  From here
# on the .kicad_sch / .kicad_pcb files are the source of truth -- re-running
# this script OVERWRITES them and would discard any routing or hand edits.
# Keep it only to regenerate placement from scratch after a layout change.
# Usage:  python3 tools/generate.py <output-dir>
# -------------------------------------------------------------------------
#!/usr/bin/env python3
"""Generate the picowatt carrier-board KiCad project.

Geometry is authored in "carrier coordinates": origin at the bottom-left corner
of the board, X to the right, Y up, millimetres.  KiCad uses Y-down, so every
emitted coordinate goes through K().
"""

import os
import re
import sys
import uuid as _uuid

OUT = sys.argv[1] if len(sys.argv) > 1 else "hardware"
PROJECT = "picowatt-carrier"
KSTOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"

BOARD_W = 92.0
BOARD_H = 70.0
OX, OY = 50.0, 120.0          # carrier (0,0) -> kicad page (50,120)

SCH_VER = 20250114
PCB_VER = 20241229
GEN_VER = "9.0"


def K(x, y):
    """carrier mm (Y-up) -> kicad mm (Y-down)"""
    return (round(OX + x, 4), round(OY - y, 4))


def uid():
    return str(_uuid.uuid4())


def n(v):
    """format a number the way KiCad does"""
    s = f"{float(v):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


# --------------------------------------------------------------------------
# minimal S-expression parser / serializer (for reusing stock .kicad_mod files)
# --------------------------------------------------------------------------

def sexp_parse(text):
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()]+', text)
    pos = 0

    def rd():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            out = []
            while tokens[pos] != ")":
                out.append(rd())
            pos += 1
            return out
        return tok

    return rd()


def sexp_dump(node, depth=0):
    pad = "\t" * depth
    if isinstance(node, str):
        return node
    if not node:
        return "()"
    head = node[0]
    simple = all(isinstance(c, str) for c in node[1:])
    if simple:
        return "(" + " ".join([head] + list(node[1:])) + ")"
    parts = ["(" + (head if isinstance(head, str) else sexp_dump(head, depth + 1))]
    for child in node[1:]:
        if isinstance(child, str):
            parts[-1] += " " + child
        else:
            parts.append(pad + "\t" + sexp_dump(child, depth + 1))
    parts.append(pad + ")")
    return "\n".join(parts)


def find(node, head):
    for c in node[1:]:
        if isinstance(c, list) and c and c[0] == head:
            return c
    return None


def find_all(node, head):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == head]


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --------------------------------------------------------------------------
# placement table  (carrier coordinates)
# --------------------------------------------------------------------------

PICO_CX, PICO_CY = 26.5, 18.5          # centre of the Pico 2 outline
INA0_X, INA_Y = 22.0, 50.0             # centre of the 1x8 header row
INA1_X = 52.0
OLED_X, OLED_Y = 71.0, 31.0            # centre of the 1x4 header row

# passives: value is the position of pad 1
R_ROW_A, R_ROW_B = 39.5, 45.0

REF_AT = {
    "R1": (1.27, 2.6), "R2": (1.27, 2.6), "R3": (1.27, -2.6), "R4": (1.27, -2.6),
    "C1": (1.25, -3.4), "C2": (2.5, 2.2), "TP1": (0.0, 2.2),
}

PARTS = [
    # ref, symbol, value, footprint, x, y, rotation
    ("J1", "Raspberry_Pi_Pico2", "Pico 2", "picowatt:Pico2_Socket_2x20_P2.54mm", PICO_CX, PICO_CY, 0),
    ("J2", "INA228_Breakout", "INA228 ch0", "picowatt:INA228_Breakout_Socket_1x08", INA0_X, INA_Y, 0),
    ("J3", "INA228_Breakout", "INA228 ch1", "picowatt:INA228_Breakout_Socket_1x08", INA1_X, INA_Y, 0),
    ("J4", "SSD1306_OLED", "SSD1306 0.96\"", "picowatt:OLED_SSD1306_Socket_1x04", OLED_X, OLED_Y, 0),
    ("J5", "Screw_Terminal_1x02", "GND", "TerminalBlock_CUI:TerminalBlock_CUI_TB007-508-02_1x02_P5.08mm_Horizontal", 79.08, 63.0, 180),
    # pullups sit directly on the tracks they tap, so they need no extra routing
    ("R1", "R", "10k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical", 28.35, 45.0, 0),
    ("R2", "R", "10k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical", 58.35, 45.0, 0),
    ("R3", "R", "2.2k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical", 74.81, 38.0, 0),
    ("R4", "R", "2.2k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical", 69.73, 34.5, 0),
    ("C1", "C_Polarized", "10uF", "Capacitor_THT:CP_Radial_D5.0mm_P2.50mm", 78.0, 45.0, 0),
    ("C2", "C", "100nF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", 40.0, 45.0, 0),
    ("TP1", "TestPoint", "GND", "TestPoint:TestPoint_Loop_D2.50mm_Drill1.0mm", 85.0, 39.5, 0),
]

MOUNT = [
    ("H1", "MountingHole:MountingHole_3.2mm_M3", 4.0, 4.0, "M3"),
    ("H2", "MountingHole:MountingHole_3.2mm_M3", 88.0, 4.0, "M3"),
    ("H3", "MountingHole:MountingHole_3.2mm_M3", 4.0, 66.0, "M3"),
    ("H4", "MountingHole:MountingHole_3.2mm_M3", 88.0, 66.0, "M3"),
]

NETS = ["GND", "+3V3", "SDA", "SCL", "ALRT0", "ALRT1"]

PINNET = {
    "J1": {6: "SDA", 7: "SCL", 9: "ALRT0", 10: "ALRT1", 36: "+3V3",
           3: "GND", 8: "GND", 13: "GND", 18: "GND", 23: "GND", 28: "GND",
           33: "GND", 38: "GND"},
    "J2": {1: "+3V3", 2: "GND", 3: "SCL", 4: "SDA", 8: "ALRT0"},
    "J3": {1: "+3V3", 2: "GND", 3: "SCL", 4: "SDA", 8: "ALRT1"},
    "J4": {1: "GND", 2: "+3V3", 3: "SCL", 4: "SDA"},
    "J5": {1: "GND", 2: "GND"},
    "R1": {1: "+3V3", 2: "ALRT0"},
    "R2": {1: "+3V3", 2: "ALRT1"},
    "R3": {1: "SDA", 2: "+3V3"},
    "R4": {1: "+3V3", 2: "SCL"},
    "C1": {1: "+3V3", 2: "GND"},
    "C2": {1: "+3V3", 2: "GND"},
    "TP1": {1: "GND"},
}

PICO_PINS = [
    "GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND", "GP6", "GP7",
    "GP8", "GP9", "GND", "GP10", "GP11", "GP12", "GP13", "GND", "GP14", "GP15",
    "GP16", "GP17", "GND", "GP18", "GP19", "GP20", "GP21", "GND", "GP22", "RUN",
    "GP26", "GP27", "AGND", "GP28", "ADC_VREF", "3V3_OUT", "3V3_EN", "GND",
    "VSYS", "VBUS",
]
INA_PINS = ["VIN", "GND", "SCL", "SDA", "VBUS", "VIN-", "VIN+", "ALRT"]
OLED_PINS = ["GND", "VDD", "SCK", "SDA"]

DNP = {"R3", "R4"}


# --------------------------------------------------------------------------
# symbol library
# --------------------------------------------------------------------------

FONT = "(effects (font (size 1.27 1.27)))"
FONTH = "(effects (font (size 1.27 1.27)) (hide yes))"

# pin geometry per symbol, filled while building: {sym: {pinnum: (x, y, side)}}
PINPOS = {}
SYM_BLOCKS = {}


def sym_pin(x, y, angle, length, name, number, etype="passive"):
    return (f'(pin {etype} line (at {n(x)} {n(y)} {n(angle)}) (length {n(length)})\n'
            f'\t\t\t\t(name {q(name)} {FONT})\n'
            f'\t\t\t\t(number {q(number)} {FONT})\n'
            f'\t\t\t)')


def rect(x1, y1, x2, y2, fill="none"):
    return (f'(rectangle (start {n(x1)} {n(y1)}) (end {n(x2)} {n(y2)})\n'
            f'\t\t\t\t(stroke (width 0.254) (type default)) (fill (type {fill}))\n'
            f'\t\t\t)')


def props(ref, val, refat, valat, desc, ki_fp_filters=None):
    out = [
        f'(property "Reference" {q(ref)} (at {n(refat[0])} {n(refat[1])} 0) {FONT})',
        f'(property "Value" {q(val)} (at {n(valat[0])} {n(valat[1])} 0) {FONT})',
        f'(property "Footprint" "" (at 0 0 0) {FONTH})',
        f'(property "Datasheet" "~" (at 0 0 0) {FONTH})',
        f'(property "Description" {q(desc)} (at 0 0 0) {FONTH})',
    ]
    return out


def build_symbol(name, body, pins, refpre, val, refat, valat, desc,
                 hide_pin_names=False, hide_pin_numbers=False):
    PINPOS[name] = {}
    hdr = [f'(symbol {q(name)}']
    if hide_pin_numbers:
        hdr.append('\t\t(pin_numbers (hide yes))')
    hdr.append('\t\t(pin_names (offset %s)%s)' %
               ("0" if hide_pin_names else "0.508",
                " (hide yes)" if hide_pin_names else ""))
    hdr.append('\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)')
    for p in props(refpre, val, refat, valat, desc):
        hdr.append("\t\t" + p)
    hdr.append(f'\t\t(symbol {q(name + "_0_1")}')
    for g in body:
        hdr.append("\t\t\t" + g)
    hdr.append("\t\t)")
    hdr.append(f'\t\t(symbol {q(name + "_1_1")}')
    for pdef, ppos in pins:
        hdr.append("\t\t\t" + pdef)
        PINPOS[name][ppos[0]] = (ppos[1], ppos[2])
    hdr.append("\t\t)")
    hdr.append("\t)")
    block = "\n".join(hdr)
    SYM_BLOCKS[name] = block
    return block


def make_symbol_lib():
    syms = []

    # ---- Raspberry Pi Pico 2 -------------------------------------------
    body = [rect(-25.4, -27.94, 25.4, 27.94)]
    pins = []
    for i in range(20):                       # pins 1..20 on the left
        num = i + 1
        y = 25.4 - i * 2.54
        pins.append((sym_pin(-30.48, y, 0, 5.08, PICO_PINS[i], str(num)),
                     (num, -30.48, y)))
    for i in range(20):                       # pins 21..40 on the right
        num = 21 + i
        y = -22.86 + i * 2.54
        pins.append((sym_pin(30.48, y, 180, 5.08, PICO_PINS[num - 1], str(num)),
                     (num, 30.48, y)))
    syms.append(build_symbol(
        "Raspberry_Pi_Pico2", body, pins, "J", "Pico 2",
        (-25.4, 29.21), (-25.4, -30.48),
        "Raspberry Pi Pico 2 (RP2350) module, 2x20 2.54mm, rows 17.78mm apart"))

    # ---- Adafruit INA228 breakout ---------------------------------------
    body = [rect(-10.16, -12.7, 10.16, 12.7)]
    pins = []
    for i, nm in enumerate(INA_PINS):
        y = 8.89 - i * 2.54
        pins.append((sym_pin(-15.24, y, 0, 5.08, nm, str(i + 1)), (i + 1, -15.24, y)))
    syms.append(build_symbol(
        "INA228_Breakout", body, pins, "J", "INA228",
        (-10.16, 13.97), (-10.16, -15.24),
        "Adafruit INA228 power monitor breakout (PID 5832), 1x8 2.54mm header"))

    # ---- SSD1306 OLED ----------------------------------------------------
    body = [rect(-10.16, -7.62, 10.16, 7.62)]
    pins = []
    for i, nm in enumerate(OLED_PINS):
        y = 3.81 - i * 2.54
        pins.append((sym_pin(-15.24, y, 0, 5.08, nm, str(i + 1)), (i + 1, -15.24, y)))
    syms.append(build_symbol(
        "SSD1306_OLED", body, pins, "J", "SSD1306",
        (-10.16, 8.89), (-10.16, -10.16),
        "SSD1306 128x64 I2C OLED module, 1x4 header (GND/VDD/SCK/SDA)"))

    # ---- passives --------------------------------------------------------
    body = [rect(-1.016, -2.54, 1.016, 2.54)]
    pins = [(sym_pin(0, 3.81, 270, 1.27, "~", "1"), (1, 0, 3.81)),
            (sym_pin(0, -3.81, 90, 1.27, "~", "2"), (2, 0, -3.81))]
    syms.append(build_symbol("R", body, pins, "R", "R", (2.032, 0), (-2.032, 0),
                             "Resistor", hide_pin_names=True, hide_pin_numbers=True))

    body = [
        f'(polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762))\n'
        f'\t\t\t\t(stroke (width 0.508) (type default)) (fill (type none))\n\t\t\t)',
        f'(polyline (pts (xy -2.032 0.762) (xy 2.032 0.762))\n'
        f'\t\t\t\t(stroke (width 0.508) (type default)) (fill (type none))\n\t\t\t)',
    ]
    pins = [(sym_pin(0, 3.81, 270, 2.794, "~", "1"), (1, 0, 3.81)),
            (sym_pin(0, -3.81, 90, 2.794, "~", "2"), (2, 0, -3.81))]
    syms.append(build_symbol("C", body, pins, "C", "C", (2.54, 0), (-2.54, 0),
                             "Unpolarized capacitor",
                             hide_pin_names=True, hide_pin_numbers=True))

    body = [
        f'(polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762))\n'
        f'\t\t\t\t(stroke (width 0.508) (type default)) (fill (type none))\n\t\t\t)',
        f'(polyline (pts (xy -2.032 0.762) (xy 2.032 0.762))\n'
        f'\t\t\t\t(stroke (width 0.508) (type default)) (fill (type none))\n\t\t\t)',
        f'(polyline (pts (xy -1.27 2.286) (xy -1.27 1.524))\n'
        f'\t\t\t\t(stroke (width 0.254) (type default)) (fill (type none))\n\t\t\t)',
        f'(polyline (pts (xy -1.651 1.905) (xy -0.889 1.905))\n'
        f'\t\t\t\t(stroke (width 0.254) (type default)) (fill (type none))\n\t\t\t)',
    ]
    pins = [(sym_pin(0, 3.81, 270, 2.794, "~", "1"), (1, 0, 3.81)),
            (sym_pin(0, -3.81, 90, 2.794, "~", "2"), (2, 0, -3.81))]
    syms.append(build_symbol("C_Polarized", body, pins, "C", "C_Polarized",
                             (2.54, 0), (-2.54, 0), "Polarized capacitor",
                             hide_pin_names=True, hide_pin_numbers=True))

    # ---- screw terminal --------------------------------------------------
    body = [rect(-2.54, -3.81, 2.54, 3.81),
            f'(circle (center 0 1.27) (radius 0.635)\n'
            f'\t\t\t\t(stroke (width 0.254) (type default)) (fill (type none))\n\t\t\t)',
            f'(circle (center 0 -1.27) (radius 0.635)\n'
            f'\t\t\t\t(stroke (width 0.254) (type default)) (fill (type none))\n\t\t\t)']
    pins = [(sym_pin(-7.62, 1.27, 0, 5.08, "Pin_1", "1"), (1, -7.62, 1.27)),
            (sym_pin(-7.62, -1.27, 0, 5.08, "Pin_2", "2"), (2, -7.62, -1.27))]
    syms.append(build_symbol("Screw_Terminal_1x02", body, pins, "J", "Screw_Terminal",
                             (-2.54, 5.08), (-2.54, -6.35),
                             "2-position 5.08mm screw terminal block"))

    # ---- test point ------------------------------------------------------
    body = [f'(circle (center 0 1.27) (radius 0.762)\n'
            f'\t\t\t\t(stroke (width 0.254) (type default)) (fill (type none))\n\t\t\t)']
    pins = [(sym_pin(0, -2.54, 90, 2.54, "1", "1"), (1, 0, -2.54))]
    syms.append(build_symbol("TestPoint", body, pins, "TP", "TestPoint",
                             (2.54, 2.54), (2.54, 0), "Test point / wire loop",
                             hide_pin_names=True, hide_pin_numbers=True))

    # ---- mounting hole ---------------------------------------------------
    body = [f'(circle (center 0 0) (radius 1.27)\n'
            f'\t\t\t\t(stroke (width 0.254) (type default)) (fill (type none))\n\t\t\t)']
    syms.append(build_symbol("MountingHole", body, [], "H", "MountingHole",
                             (2.54, 1.27), (2.54, -1.27), "Mounting hole"))

    out = ["(kicad_symbol_lib",
           f"\t(version {SCH_VER})",
           '\t(generator "picowatt-gen")',
           f'\t(generator_version {q(GEN_VER)})']
    for s in syms:
        out.append("\t" + s)
    out.append(")")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# custom footprints
# --------------------------------------------------------------------------

def fp_pad(num, x, y, shape="circle", size=1.6, drill=1.0):
    return (f'\t(pad {q(str(num))} thru_hole {shape}\n'
            f'\t\t(at {n(x)} {n(y)})\n'
            f'\t\t(size {n(size)} {n(size)})\n'
            f'\t\t(drill {n(drill)})\n'
            f'\t\t(layers "*.Cu" "*.Mask")\n'
            f'\t\t(remove_unused_layers no)\n'
            f'\t\t(uuid {q(uid())})\n'
            f'\t)')


def fp_npth(x, y, dia):
    return (f'\t(pad "" np_thru_hole circle\n'
            f'\t\t(at {n(x)} {n(y)})\n'
            f'\t\t(size {n(dia)} {n(dia)})\n'
            f'\t\t(drill {n(dia)})\n'
            f'\t\t(layers "F&B.Cu" "*.Mask")\n'
            f'\t\t(uuid {q(uid())})\n'
            f'\t)')


def fp_line(x1, y1, x2, y2, layer, width=0.12):
    return (f'\t(fp_line\n\t\t(start {n(x1)} {n(y1)})\n\t\t(end {n(x2)} {n(y2)})\n'
            f'\t\t(stroke (width {n(width)}) (type solid))\n'
            f'\t\t(layer {q(layer)})\n\t\t(uuid {q(uid())})\n\t)')


def fp_box(x1, y1, x2, y2, layer, width=0.12):
    return "\n".join([
        fp_line(x1, y1, x2, y1, layer, width),
        fp_line(x2, y1, x2, y2, layer, width),
        fp_line(x2, y2, x1, y2, layer, width),
        fp_line(x1, y2, x1, y1, layer, width),
    ])


def fp_text(kind, text, x, y, layer, size=1.0, thick=0.15, hide=False, angle=0):
    h = " (hide yes)" if hide else ""
    return (f'\t(fp_text {kind} {q(text)}\n\t\t(at {n(x)} {n(y)} {n(angle)})\n'
            f'\t\t(layer {q(layer)}){h}\n\t\t(uuid {q(uid())})\n'
            f'\t\t(effects (font (size {n(size)} {n(size)}) (thickness {n(thick)})))\n\t)')


def fp_prop(name, value, x, y, layer, hide=False, size=1.0):
    h = "\n\t\t(hide yes)" if hide else ""
    return (f'\t(property {q(name)} {q(value)}\n\t\t(at {n(x)} {n(y)} 0)\n'
            f'\t\t(layer {q(layer)}){h}\n\t\t(uuid {q(uid())})\n'
            f'\t\t(effects (font (size {n(size)} {n(size)}) (thickness 0.15)))\n\t)')


def fp_header(name, desc, tags):
    return (f'(footprint {q(name)}\n'
            f'\t(version {PCB_VER})\n'
            f'\t(generator "picowatt-gen")\n'
            f'\t(generator_version {q(GEN_VER)})\n'
            f'\t(layer "F.Cu")\n'
            f'\t(descr {q(desc)})\n'
            f'\t(tags {q(tags)})\n'
            f'\t(attr through_hole)')


def make_fp_pico():
    p = [fp_header(
        "Pico2_Socket_2x20_P2.54mm",
        "Socket for a Raspberry Pi Pico 2 (RP2350). Two 1x20 2.54mm rows "
        "17.78mm apart. Origin at the centre of the 51x21mm module outline. "
        "Micro-USB B overhangs the -X edge.",
        "raspberry pi pico pico2 rp2350 socket")]
    p.append(fp_prop("Reference", "REF**", 18.0, 0, "F.SilkS"))
    p.append(fp_prop("Value", "Pico2_Socket_2x20_P2.54mm", 0, 12.2, "F.Fab", hide=True))
    p.append(fp_prop("Datasheet", "", 0, 0, "F.Fab", hide=True))
    p.append(fp_prop("Description", "", 0, 0, "F.Fab", hide=True))

    for i in range(20):                             # pins 1..20, +Y row
        x = -24.13 + i * 2.54
        p.append(fp_pad(i + 1, x, 8.89, "rect" if i == 0 else "circle"))
    for i in range(20):                             # pins 21..40, -Y row
        x = 24.13 - i * 2.54
        p.append(fp_pad(21 + i, x, -8.89))

    for layer in ("F.SilkS", "F.Fab"):
        p.append(fp_box(-25.5, -10.5, 25.5, 10.5, layer))
    # micro-USB B shell, overhanging the -X edge by 1.3mm
    p.append(fp_box(-26.8, -4.0, -18.87, 4.0, "F.Fab"))
    p.append(fp_text("user", "USB", -22.5, 0, "F.SilkS", size=1.0))
    p.append(fp_text("user", "${REFERENCE}", 0, 0, "F.Fab", size=1.5))
    # pin 1 marker
    p.append(fp_line(-25.5, 6.5, -22.5, 6.5, "F.SilkS", 0.2))
    p.append(fp_box(-25.85, -10.85, 25.85, 10.85, "F.CrtYd", 0.05))
    p.append(")")
    return "\n".join(p) + "\n"


def make_fp_ina():
    p = [fp_header(
        "INA228_Breakout_Socket_1x08",
        "Socket for the Adafruit INA228 breakout (PID 5832). 1x8 2.54mm row. "
        "Origin at the centre of the header row. Module outline 25.40x20.32mm "
        "extends +2.54/-17.78mm in Y; screw terminal faces -Y. "
        "Pads 5/6/7 (VBUS, VIN-, VIN+) carry the measured supply potential.",
        "adafruit ina228 power monitor breakout socket")]
    p.append(fp_prop("Reference", "REF**", 0, -4.5, "F.SilkS"))
    p.append(fp_prop("Value", "INA228_Breakout_Socket_1x08", 0, -19.5, "F.Fab", hide=True))
    p.append(fp_prop("Datasheet", "", 0, 0, "F.Fab", hide=True))
    p.append(fp_prop("Description", "", 0, 0, "F.Fab", hide=True))

    for i in range(8):
        p.append(fp_pad(i + 1, -8.89 + i * 2.54, 0.0, "rect" if i == 0 else "circle"))
    # M2.5 standoff holes, matching the breakout's own 2.5mm mounting holes
    for sx in (-10.16, 10.16):
        p.append(fp_npth(sx, -15.24, 2.8))

    for layer in ("F.SilkS", "F.Fab"):
        p.append(fp_box(-12.70, -17.78, 12.70, 2.54, layer))
    # screw terminal body, wire entry towards -Y
    p.append(fp_box(-5.25, -17.44, 5.25, -10.44, "F.Fab"))
    p.append(fp_text("user", "term", 0, -14.0, "F.SilkS", size=1.0))
    p.append(fp_text("user", "${REFERENCE}", 0, -6.5, "F.Fab", size=1.5))
    # pin-1 marker and the "do not touch" band over pads 5..7
    p.append(fp_line(-12.70, 1.6, -9.9, 1.6, "F.SilkS", 0.2))
    p.append(fp_text("user", "VIN+/-", 5.7, 1.6, "F.SilkS", size=0.8))
    p.append(fp_box(-12.95, -18.03, 12.95, 2.79, "F.CrtYd", 0.05))
    p.append(")")
    return "\n".join(p) + "\n"


def make_fp_oled():
    p = [fp_header(
        "OLED_SSD1306_Socket_1x04",
        "Socket for the Akizuki 112031 SSD1306 0.96\" 128x64 I2C OLED module "
        "(silk GND/VDD/SCK/SDA). 1x4 2.54mm row, origin at the centre of the "
        "header row. Module 25x27mm, header 1.5mm from its top edge, "
        "M2.5 holes on a 21x23mm pitch.",
        "ssd1306 oled 128x64 i2c akizuki 112031 socket")]
    p.append(fp_prop("Reference", "REF**", -16.0, 11.0, "F.SilkS"))
    p.append(fp_prop("Value", "OLED_SSD1306_Socket_1x04", 0, 27.4, "F.Fab", hide=True))
    p.append(fp_prop("Datasheet", "", 0, 0, "F.Fab", hide=True))
    p.append(fp_prop("Description", "", 0, 0, "F.Fab", hide=True))

    for i in range(4):
        p.append(fp_pad(i + 1, -3.81 + i * 2.54, 0.0, "rect" if i == 0 else "circle"))
    # M2.5 standoff holes: measured 21 x 23mm pitch, 0.5mm below the header row
    for sx in (-10.5, 10.5):
        for sy in (0.5, 23.5):
            p.append(fp_npth(sx, sy, 2.8))

    for layer in ("F.SilkS", "F.Fab"):
        p.append(fp_box(-12.5, -1.5, 12.5, 25.5, layer))
    p.append(fp_box(-12.2, 3.3, 12.2, 23.2, "F.Fab"))       # glass panel
    p.append(fp_box(-10.87, 7.82, 10.87, 18.68, "F.Fab"))   # active area
    p.append(fp_box(-5.0, 22.0, 5.0, 25.5, "F.SilkS"))      # FPC wrap keep-out
    p.append(fp_text("user", "FPC", 0, 23.8, "F.SilkS", size=0.8))
    p.append(fp_text("user", "${REFERENCE}", 0, 13.0, "F.Fab", size=1.5))
    p.append(fp_line(-5.2, -2.2, -2.4, -2.2, "F.SilkS", 0.2))
    p.append(fp_box(-12.75, -1.75, 12.75, 25.75, "F.CrtYd", 0.05))
    p.append(")")
    return "\n".join(p) + "\n"


# --------------------------------------------------------------------------
# schematic
# --------------------------------------------------------------------------

SCH_POS = {
    "J1": (76.2, 127.0), "J2": (215.9, 60.96), "J3": (215.9, 111.76),
    "J4": (215.9, 160.02), "J5": (215.9, 198.12), "TP1": (259.08, 198.12),
    "R1": (309.88, 60.96), "R2": (330.2, 60.96), "R3": (350.52, 60.96),
    "R4": (370.84, 60.96), "C1": (309.88, 121.92), "C2": (330.2, 121.92),
}
for _i in range(4):
    SCH_POS[f"H{_i + 1}"] = (63.5 + _i * 20.32, 248.92)

STUB = 5.08


def sch_symbol(ref, lib, value, fp, x, y, dnp=False, in_bom=True):
    d = "yes" if dnp else "no"
    b = "yes" if in_bom else "no"
    return (f'\t(symbol\n\t\t(lib_id {q("picowatt:" + lib)})\n'
            f'\t\t(at {n(x)} {n(y)} 0)\n\t\t(unit 1)\n'
            f'\t\t(exclude_from_sim no)\n\t\t(in_bom {b})\n\t\t(on_board yes)\n'
            f'\t\t(dnp {d})\n\t\t(uuid {q(uid())})\n'
            f'\t\t(property "Reference" {q(ref)} (at {n(x)} {n(y - 2.54)} 0) {FONT})\n'
            f'\t\t(property "Value" {q(value)} (at {n(x)} {n(y + 2.54)} 0) {FONT})\n'
            f'\t\t(property "Footprint" {q(fp)} (at {n(x)} {n(y)} 0) {FONTH})\n'
            f'\t\t(property "Datasheet" "~" (at {n(x)} {n(y)} 0) {FONTH})\n'
            f'\t\t(property "Description" "" (at {n(x)} {n(y)} 0) {FONTH})\n'
            f'\t\t(instances\n\t\t\t(project {q(PROJECT)}\n'
            f'\t\t\t\t(path {q("/" + ROOT_UUID)}\n'
            f'\t\t\t\t\t(reference {q(ref)}) (unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)')


def sch_wire(x1, y1, x2, y2):
    return (f'\t(wire (pts (xy {n(x1)} {n(y1)}) (xy {n(x2)} {n(y2)}))\n'
            f'\t\t(stroke (width 0) (type default))\n\t\t(uuid {q(uid())})\n\t)')


def sch_label(text, x, y, angle, just):
    return (f'\t(label {q(text)}\n\t\t(at {n(x)} {n(y)} {n(angle)})\n'
            f'\t\t(effects (font (size 1.27 1.27)) (justify {just} bottom))\n'
            f'\t\t(uuid {q(uid())})\n\t)')


def make_schematic():
    out = ["(kicad_sch",
           f"\t(version {SCH_VER})",
           '\t(generator "eeschema")',
           f'\t(generator_version {q(GEN_VER)})',
           f'\t(uuid {q(ROOT_UUID)})',
           '\t(paper "A3")',
           '\t(title_block',
           '\t\t(title "picowatt carrier board")',
           '\t\t(rev "A")',
           '\t\t(comment 1 "Pico 2 + 2x INA228 + SSD1306 OLED carrier")',
           '\t\t(comment 2 "All logic on I2C0: GP4=SDA GP5=SCL, ALERT on GP6/GP7")',
           '\t)',
           "\t(lib_symbols"]
    for block in LIB_SYMBOL_BLOCKS:
        out.append("\t\t" + block)
    out.append("\t)")

    for ref, sym, val, fp, _x, _y, _r in PARTS:
        sx, sy = SCH_POS[ref]
        out.append(sch_symbol(ref, sym, val, fp, sx, sy, dnp=(ref in DNP)))
        for pin, net in sorted(PINNET.get(ref, {}).items()):
            px, py = PINPOS[sym][pin]
            ax, ay = sx + px, sy - py
            if px < 0:
                bx, by, ang, just = ax - STUB, ay, 0, "right"
            elif px > 0:
                bx, by, ang, just = ax + STUB, ay, 0, "left"
            elif py > 0:
                bx, by, ang, just = ax, ay - STUB, 90, "left"
            else:
                bx, by, ang, just = ax, ay + STUB, 90, "right"
            out.append(sch_wire(ax, ay, bx, by))
            out.append(sch_label(net, bx, by, ang, just))

        used = set(PINNET.get(ref, {}))
        for pin, (px, py) in sorted(PINPOS[sym].items()):
            if pin in used:
                continue
            out.append(f'\t(no_connect (at {n(sx + px)} {n(sy - py)}) '
                       f'(uuid {q(uid())}))')

    for ref, fp, _x, _y, size in MOUNT:
        sx, sy = SCH_POS[ref]
        out.append(sch_symbol(ref, "MountingHole", size, fp, sx, sy, in_bom=False))

    out.append('\t(sheet_instances\n\t\t(path "/" (page "1"))\n\t)')
    out.append("\t(embedded_fonts no)")
    out.append(")")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# PCB
# --------------------------------------------------------------------------

LAYERS_BLOCK = """	(layers
		(0 "F.Cu" signal)
		(2 "B.Cu" signal)
		(9 "F.Adhes" user "F.Adhesive")
		(11 "B.Adhes" user "B.Adhesive")
		(13 "F.Paste" user)
		(15 "B.Paste" user)
		(5 "F.SilkS" user "F.Silkscreen")
		(7 "B.SilkS" user "B.Silkscreen")
		(1 "F.Mask" user)
		(3 "B.Mask" user)
		(17 "Dwgs.User" user "User.Drawings")
		(19 "Cmts.User" user "User.Comments")
		(21 "Eco1.User" user "User.Eco1")
		(23 "Eco2.User" user "User.Eco2")
		(25 "Edge.Cuts" user)
		(27 "Margin" user)
		(31 "F.CrtYd" user "F.Courtyard")
		(29 "B.CrtYd" user "B.Courtyard")
		(35 "F.Fab" user)
		(33 "B.Fab" user)
	)"""


def regen_uuids(node):
    if not isinstance(node, list):
        return
    for c in node:
        if isinstance(c, list) and c and c[0] == "uuid":
            c[1] = q(uid())
        else:
            regen_uuids(c)


def load_footprint(libid, ref, value, x, y, pinnets, dnp=False, ref_at=None, rot=0):
    lib, name = libid.split(":", 1)
    if lib == "picowatt":
        path = os.path.join(OUT, "picowatt.pretty", name + ".kicad_mod")
    else:
        path = os.path.join(KSTOCK, lib + ".pretty", name + ".kicad_mod")
    node = sexp_parse(open(path).read())
    node[1] = q(libid)
    node[1:] = [c for c in node[1:]
                if not (isinstance(c, list) and c[0] in
                        ("version", "generator", "generator_version"))]
    regen_uuids(node)

    li = next(i for i, c in enumerate(node)
              if isinstance(c, list) and c[0] == "layer")
    node.insert(li + 1, ["uuid", q(uid())])
    node.insert(li + 1, ["at", n(x), n(y)] + ([n(rot)] if rot else []))

    for p in find_all(node, "property"):
        if p[1] == '"Reference"':
            p[2] = q(ref)
            if ref.startswith("H") and not find(p, "hide"):
                p.append(["hide", "yes"])
            if ref_at:
                at = find(p, "at")
                at[1], at[2] = n(ref_at[0]), n(ref_at[1])
        elif p[1] == '"Value"':
            p[2] = q(value)
    if dnp:
        node.append(["attr", "dnp"])

    for pad in find_all(node, "pad"):
        num = pad[1].strip('"')
        try:
            key = int(num)
        except ValueError:
            continue
        net = pinnets.get(key)
        if net:
            pad.append(["net", str(NET_IDX[net]), q("/" + net)])
        else:
            nm = unconnected_name(ref, key)
            if nm:
                pad.append(["net", str(UNCONN[nm]), q(nm)])
    return "\t" + sexp_dump(node, 1)


PIN_NAMES = {}
UNCONN = {}


def unconnected_name(ref, pin):
    """eeschema names a pin with no connection unconnected-(REF-PINNAME-PadN)."""
    names = PIN_NAMES.get(ref)
    if not names or pin > len(names):
        return None
    nm = f"unconnected-({ref}-{names[pin - 1]}-Pad{pin})"
    if nm not in UNCONN:
        UNCONN[nm] = len(NETS) + 1 + len(UNCONN)
    return nm


def gr_line(x1, y1, x2, y2, layer, width=0.1):
    return (f'\t(gr_line (start {n(x1)} {n(y1)}) (end {n(x2)} {n(y2)})\n'
            f'\t\t(stroke (width {n(width)}) (type solid))\n'
            f'\t\t(layer {q(layer)}) (uuid {q(uid())})\n\t)')


def gr_text(text, x, y, layer, size=1.2, thick=0.2, just="left"):
    return (f'\t(gr_text {q(text)}\n\t\t(at {n(x)} {n(y)} 0)\n'
            f'\t\t(layer {q(layer)}) (uuid {q(uid())})\n'
            f'\t\t(effects (font (size {n(size)} {n(size)}) (thickness {n(thick)}))'
            f' (justify {just}))\n\t)')


SILK_A = [
    "picowatt carrier  rev A",
    "PSU+ -> ch0 VIN+ [15m] VIN- -> DUT+   DUT- -> GND",
    "eff: DUT out -> ch1 VIN+ [15m] VIN- -> load",
]
SILK_B = [
    "ch0 = 0x40   ch1 = 0x41 (close A0)",
    "close VBus jumper on both INA228",
    "J2/J3 pins 5-7: NC, supply potential",
]


def make_pcb():
    out = ["(kicad_pcb",
           f"\t(version {PCB_VER})",
           '\t(generator "pcbnew")',
           f'\t(generator_version {q(GEN_VER)})',
           '\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)',
           '\t(paper "A3")',
           '\t(title_block\n\t\t(title "picowatt carrier board")\n\t\t(rev "A")\n\t)',
           LAYERS_BLOCK,
           '\t(setup\n\t\t(pad_to_mask_clearance 0)\n'
           '\t\t(allow_soldermask_bridges_in_footprints no)\n\t)']

    # build footprints first: that is what registers the unconnected-() nets
    fps = []
    for ref, sym, val, fp, cx, cy, rot in PARTS:
        kx, ky = K(cx, cy)
        fps.append(load_footprint(fp, ref, val, kx, ky,
                                  PINNET.get(ref, {}), dnp=(ref in DNP),
                                  ref_at=REF_AT.get(ref), rot=rot))
    for ref, fp, cx, cy, size in MOUNT:
        kx, ky = K(cx, cy)
        fps.append(load_footprint(fp, ref, size, kx, ky, {}))

    out.append('\t(net 0 "")')
    for name in NETS:
        out.append(f'\t(net {NET_IDX[name]} {q("/" + name)})')
    for nm, idx in sorted(UNCONN.items(), key=lambda kv: kv[1]):
        out.append(f'\t(net {idx} {q(nm)})')
    out.extend(fps)

    # board outline
    c = [K(0, 0), K(BOARD_W, 0), K(BOARD_W, BOARD_H), K(0, BOARD_H)]
    for i in range(4):
        a, b = c[i], c[(i + 1) % 4]
        out.append(gr_line(a[0], a[1], b[0], b[1], "Edge.Cuts", 0.1))

    for i, line in enumerate(SILK_A):
        tx, ty = K(2.0, 34.8 - i * 2.2)
        out.append(gr_text(line, tx, ty, "F.SilkS",
                           size=1.2 if i == 0 else 1.0, thick=0.2 if i == 0 else 0.16))
    for line, cy in (("GND  <- PSU(-)", 55.5), ("R3/R4 = DNP", 52.5)):
        tx, ty = K(66.0, cy)
        out.append(gr_text(line, tx, ty, "F.SilkS", size=1.0, thick=0.16))
    for i, line in enumerate(SILK_B):
        tx, ty = K(9.0, 6.0 - i * 2.0)
        out.append(gr_text(line, tx, ty, "F.SilkS", size=1.0, thick=0.16))

    # GND pour on both layers
    poly = [K(0.3, 0.3), K(BOARD_W - 0.3, 0.3),
            K(BOARD_W - 0.3, BOARD_H - 0.3), K(0.3, BOARD_H - 0.3)]
    pts = " ".join(f"(xy {n(p[0])} {n(p[1])})" for p in poly)
    out.append(f'\t(zone\n\t\t(net {NET_IDX["GND"]}) (net_name "/GND")\n'
               f'\t\t(layers "F.Cu" "B.Cu")\n\t\t(uuid {q(uid())})\n'
               f'\t\t(name "GND")\n\t\t(hatch edge 0.508)\n'
               f'\t\t(connect_pads (clearance 0.5))\n'
               f'\t\t(min_thickness 0.25)\n\t\t(filled_areas_thickness no)\n'
               f'\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
               f'\t\t(polygon (pts {pts}))\n\t)')
    out.append(")")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# project scaffolding
# --------------------------------------------------------------------------

KICAD_PRO = """{
  "board": {
    "design_settings": {
      "defaults": {
        "board_outline_line_width": 0.1,
        "copper_line_width": 0.2,
        "copper_text_size_h": 1.5,
        "copper_text_size_v": 1.5,
        "copper_text_thickness": 0.3,
        "other_line_width": 0.15,
        "silk_line_width": 0.15,
        "silk_text_size_h": 1.0,
        "silk_text_size_v": 1.0,
        "silk_text_thickness": 0.15
      },
      "rules": {
        "min_clearance": 0.2,
        "min_copper_edge_clearance": 0.3,
        "min_through_hole_diameter": 0.3,
        "min_track_width": 0.2,
        "min_via_annular_width": 0.13,
        "min_via_diameter": 0.6
      }
    }
  },
  "meta": {
    "filename": "%(project)s.kicad_pro",
    "version": 3
  },
  "net_settings": {
    "classes": [
      {
        "bus_width": 12.0,
        "clearance": 0.2,
        "diff_pair_gap": 0.25,
        "diff_pair_width": 0.2,
        "line_style": 0,
        "microvia_diameter": 0.3,
        "microvia_drill": 0.1,
        "name": "Default",
        "pcb_color": "rgba(0, 0, 0, 0.000)",
        "schematic_color": "rgba(0, 0, 0, 0.000)",
        "track_width": 0.4,
        "via_diameter": 0.8,
        "via_drill": 0.4,
        "wire_width": 6.0
      }
    ],
    "meta": {
      "version": 4
    }
  },
  "sheets": [
    [
      "%(root)s",
      "Root"
    ]
  ],
  "text_variables": {}
}
"""

SYM_LIB_TABLE = """(sym_lib_table
  (version 7)
  (lib (name "picowatt")(type "KiCad")(uri "${KIPRJMOD}/picowatt.kicad_sym")(options "")(descr "picowatt carrier board symbols"))
)
"""

FP_LIB_TABLE = """(fp_lib_table
  (version 7)
  (lib (name "picowatt")(type "KiCad")(uri "${KIPRJMOD}/picowatt.pretty")(options "")(descr "picowatt carrier board footprints"))
)
"""


def main():
    global ROOT_UUID, NET_IDX, LIB_SYMBOL_BLOCKS
    ROOT_UUID = uid()
    NET_IDX = {name: i + 1 for i, name in enumerate(NETS)}
    PIN_NAMES.update({"J1": PICO_PINS, "J2": INA_PINS, "J3": INA_PINS,
                      "J4": OLED_PINS})

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "picowatt.pretty"), exist_ok=True)

    # footprints first: the PCB generator reads them back off disk
    for fname, text in (
        ("Pico2_Socket_2x20_P2.54mm", make_fp_pico()),
        ("INA228_Breakout_Socket_1x08", make_fp_ina()),
        ("OLED_SSD1306_Socket_1x04", make_fp_oled()),
    ):
        with open(os.path.join(OUT, "picowatt.pretty", fname + ".kicad_mod"), "w") as f:
            f.write(text)

    libtext = make_symbol_lib()
    with open(os.path.join(OUT, "picowatt.kicad_sym"), "w") as f:
        f.write(libtext)

    LIB_SYMBOL_BLOCKS = []
    for name, block in SYM_BLOCKS.items():
        LIB_SYMBOL_BLOCKS.append(block.replace(q(name), q("picowatt:" + name), 1))

    with open(os.path.join(OUT, PROJECT + ".kicad_sch"), "w") as f:
        f.write(make_schematic())
    with open(os.path.join(OUT, PROJECT + ".kicad_pcb"), "w") as f:
        f.write(make_pcb())
    with open(os.path.join(OUT, PROJECT + ".kicad_pro"), "w") as f:
        f.write(KICAD_PRO % {"project": PROJECT, "root": ROOT_UUID})
    with open(os.path.join(OUT, "sym-lib-table"), "w") as f:
        f.write(SYM_LIB_TABLE)
    with open(os.path.join(OUT, "fp-lib-table"), "w") as f:
        f.write(FP_LIB_TABLE)

    print(f"wrote {OUT}/  ({len(PARTS)} parts, {len(MOUNT)} holes, {len(NETS)} nets)")


if __name__ == "__main__":
    main()
