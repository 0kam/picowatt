#!/usr/bin/env python3
"""Emit bench wiring diagrams (SVG) that mirror the real board layout.

The board drawing uses the same carrier coordinates as generate.py
(origin bottom-left, mm), so everything sits where it does on the real
rev A/B board: USB on the left, terminal blocks facing the top edge,
J2 = ch0 on the left, J3 = ch1 on the right, J5 top right.

Usage: python3 tools/wiring_diagrams.py   ->  hardware/docs/wiring-*.svg
"""
import os

S = 6.0                 # px per mm
BX, BTOP = 64, 210      # board top-left on the canvas

def sx(x): return BX + S * x
def sy(y): return BTOP + S * (70 - y)

RED, BLUE = "#c62828", "#1565c0"
BOARD, MODULE, TERM = "#dde7d6", "#faf8f1", "#3a7d44"
INK, FAINT = "#333333", "#b9b9b0"

def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;")

def text(x, y, t, size=12, fill=INK, anchor="middle", weight="normal"):
    return (f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" '
            f'font-family="sans-serif">{esc(t)}</text>')

def label(x, y, t, color, size=12):
    w = int(size * (sum(2 if ord(c) > 255 else 1 for c in t) / 2) + 10)
    return (f'<rect x="{x - w/2:.0f}" y="{y - size + 1:.0f}" width="{w}" '
            f'height="{size + 5}" rx="3" fill="#ffffff" fill-opacity="0.9"/>'
            + text(x, y, t, size, color, weight="bold"))

def screw(x, y):
    return (f'<circle cx="{x:.0f}" cy="{y:.0f}" r="7" fill="#e8e8e8" '
            f'stroke="{INK}" stroke-width="1.4"/>'
            f'<line x1="{x-4:.0f}" y1="{y:.0f}" x2="{x+4:.0f}" y2="{y:.0f}" '
            f'stroke="{INK}" stroke-width="1.4"/>')

def wire(d, color, marker=True):
    m = f' marker-end="url(#arr_{ "red" if color == RED else "blue" })"' if marker else ""
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="4.5" '
            f'stroke-linejoin="round" stroke-linecap="round"{m}/>')

def hop_r(x, y):   # crossing hop while travelling right
    return f"L {x-7:.0f},{y:.0f} A 7 7 0 0 1 {x+7:.0f},{y:.0f} "

def hop_l(x, y):   # crossing hop while travelling left
    return f"L {x+7:.0f},{y:.0f} A 7 7 0 0 0 {x-7:.0f},{y:.0f} "

def dot(x, y, color):
    return f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"/>'


def module(cx_mm, ch, color, note):
    """One INA228 socket + module footprint, terminals facing up."""
    x0, x1 = sx(cx_mm - 12.7), sx(cx_mm + 12.7)
    e = [f'<rect x="{x0:.0f}" y="{sy(67.78):.0f}" width="{x1-x0:.0f}" '
         f'height="{sy(47.46)-sy(67.78):.0f}" rx="4" fill="{MODULE}" '
         f'stroke="#9aa3ad" stroke-width="1.5"/>']
    tx0, tx1 = sx(cx_mm - 5.25), sx(cx_mm + 5.25)
    e.append(f'<rect x="{tx0:.0f}" y="{sy(67.44):.0f}" width="{tx1-tx0:.0f}" '
             f'height="{sy(60.44)-sy(67.44):.0f}" rx="3" fill="{TERM}"/>')
    for dx in (-3.5, 0.0, 3.5):
        e.append(screw(sx(cx_mm + dx), sy(63.9)))
    e.append(text(sx(cx_mm - 3.5), sy(58.4), "VIN−", 12, weight="bold"))
    e.append(text(sx(cx_mm + 3.5), sy(58.4), "VIN+", 12, weight="bold"))
    e.append(text(sx(cx_mm), sy(55.8), "VBus(空き)", 10, "#999"))
    e.append(text(sx(cx_mm), sy(51.3), "INA228", 12, "#8a8a8a"))
    for i in range(8):
        e.append(f'<circle cx="{sx(cx_mm - 8.89 + i*2.54):.0f}" '
                 f'cy="{sy(50):.0f}" r="3" fill="#8b8b83"/>')
    # channel badge + note live UNDER the module, on free board area
    e.append(f'<rect x="{sx(cx_mm)-88:.0f}" y="{sy(46.4):.0f}" width="176" '
             f'height="26" rx="13" fill="{color}"/>')
    e.append(text(sx(cx_mm), sy(46.4) + 18, ch, 13, "#ffffff", weight="bold"))
    e.append(text(sx(cx_mm), sy(46.4) + 44, note, 11, "#555"))
    return e


def board(power_only):
    e = [f'<rect x="{BX}" y="{BTOP}" width="{S*92:.0f}" height="{S*70:.0f}" '
         f'rx="6" fill="{BOARD}" stroke="#5a6b5a" stroke-width="2"/>']
    for hx, hy in ((4, 4), (88, 4), (4, 66), (88, 66)):
        e.append(f'<circle cx="{sx(hx):.0f}" cy="{sy(hy):.0f}" r="9" '
                 f'fill="#ffffff" stroke="#8a958a" stroke-width="1.5"/>')

    # Pico 2 + USB
    e.append(f'<rect x="{sx(1):.0f}" y="{sy(29):.0f}" width="{S*51:.0f}" '
             f'height="{S*21:.0f}" rx="4" fill="{MODULE}" stroke="#9aa3ad" '
             f'stroke-width="1.5"/>')
    e.append(text(sx(26.5), sy(17.2), "Pico 2", 15, weight="bold"))
    e.append(f'<rect x="{sx(-2):.0f}" y="{sy(22.5):.0f}" width="{S*9:.0f}" '
             f'height="{S*8:.0f}" fill="#c9c9c9" stroke="#8a8a8a"/>')
    e.append(text(sx(2.4), sy(16.5), "USB", 10, "#666"))
    e.append(wire(f"M {sx(-2.5):.0f},{sy(18.5):.0f} L {sx(-6.5):.0f},{sy(18.5):.0f}",
                  "#777777", marker=False))
    e.append(text(sx(-4.5), sy(21.5), "PCへ", 11, "#555"))

    # INA sockets
    e += module(22, "J2 = ch0 0x40 入力", "#b26a00", "A0 は開けたまま")
    j3note = "裏の A0 を閉じた方" if not power_only else "今回は使わない（空きで OK）"
    e += module(52, "J3 = ch1 0x41 出力", "#00796b", j3note)
    if power_only:
        e.append(f'<rect x="{sx(39.3):.0f}" y="{sy(67.78):.0f}" '
                 f'width="{S*25.4:.0f}" height="{sy(47.46)-sy(67.78):.0f}" '
                 f'rx="4" fill="#ffffff" fill-opacity="0.55"/>')

    # J5 terminal
    e.append(f'<rect x="{sx(70.36):.0f}" y="{sy(68.85):.0f}" '
             f'width="{sx(82.12)-sx(70.36):.0f}" '
             f'height="{sy(57.6)-sy(68.85):.0f}" rx="3" fill="{TERM}"/>')
    e.append(screw(sx(74), sy(65)))
    e.append(screw(sx(79.08), sy(65)))
    e.append(text(sx(76.5), sy(55.6), "J5  GND", 12, weight="bold"))
    e.append(text(sx(76.5), sy(52.0), "2口ともGND", 10, "#666"))

    # OLED
    e.append(f'<rect x="{sx(58.5):.0f}" y="{sy(32.5):.0f}" width="{S*25:.0f}" '
             f'height="{S*27:.0f}" rx="3" fill="#2b2b33"/>')
    e.append(f'<rect x="{sx(60.8):.0f}" y="{sy(26.5):.0f}" width="{S*20.4:.0f}" '
             f'height="{S*11:.0f}" fill="#10131f"/>')
    e.append(text(sx(71), sy(8.5), "OLED", 12, "#cccccc"))

    e.append(f'<circle cx="{sx(79):.0f}" cy="{sy(45):.0f}" r="14" '
             f'fill="#d7dde8" stroke="#8a95a5"/>')
    e.append(text(sx(75.2), sy(47.6), "+", 15, INK, weight="bold"))
    e.append(text(sx(79), sy(41.2), "C1", 10, "#777"))
    e.append(f'<circle cx="{sx(85):.0f}" cy="{sy(39.5):.0f}" r="7" '
             f'fill="#ffffff" stroke="{INK}" stroke-width="1.5"/>')
    e.append(text(sx(85), sy(35.2), "TP1", 10, "#777"))
    return e


def frame(title, body, width, height):
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
            f'<defs>'
            f'<marker id="arr_red" markerUnits="userSpaceOnUse" markerWidth="15" markerHeight="12" refX="11" '
            f'refY="6" orient="auto"><path d="M0,0 L15,6 L0,12 z" '
            f'fill="{RED}"/></marker>'
            f'<marker id="arr_blue" markerUnits="userSpaceOnUse" markerWidth="15" markerHeight="12" refX="11" '
            f'refY="6" orient="auto"><path d="M0,0 L15,6 L0,12 z" '
            f'fill="{BLUE}"/></marker>'
            f'</defs>'
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>')
    head += text(18, 26, title, 17, INK, anchor="start", weight="bold")
    head += text(18, height - 12,
                 "赤 = ＋側の線　青 = −側の線　⌒ = 交差（接続しない）　"
                 "端子台の VBus には何も繋がない", 12, "#555", anchor="start")
    return head + "".join(body) + "</svg>"


def box(x, w, name, terms):
    e = [f'<rect x="{x}" y="40" width="{w}" height="110" rx="8" '
         f'fill="#f2f2f2" stroke="#666" stroke-width="1.8"/>',
         text(x + w/2, 78, name, 14, weight="bold")]
    for tx, sign in terms:
        c = RED if sign == "＋" else BLUE
        e.append(f'<circle cx="{tx}" cy="150" r="7" fill="{c}"/>')
        e.append(text(tx, 138, sign, 13, c, weight="bold"))
    return e


def power_svg():
    e = board(power_only=True)
    e += box(80, 160, "測定対象 (DUT)", [(130, "＋"), (200, "−")])
    e += box(330, 160, "安定化電源", [(360, "＋"), (460, "−")])
    ytop = sy(63.9) - 9
    yj5 = sy(65) - 9
    e.append(wire(f"M 360,150 L 360,180 L {sx(25.5):.0f},180 "
                  f"L {sx(25.5):.0f},{ytop:.0f}", RED))
    e.append(wire(f"M {sx(18.5):.0f},{ytop:.0f} L {sx(18.5):.0f},205 "
                  f"L 130,205 L 130,159", RED))
    e.append(wire("M 200,150 L 200,196 " + hop_r(sx(25.5), 196)
                  + f"L {sx(74):.0f},196 L {sx(74):.0f},{yj5:.0f}", BLUE))
    e.append(wire(f"M 460,150 L 460,168 L {sx(79.08):.0f},168 "
                  f"L {sx(79.08):.0f},{yj5:.0f}", BLUE))
    return frame("消費電力測定のつなぎ方（INA228 は J2 に 1 枚だけ）", e, 760, 700)


def efficiency_svg():
    e = board(power_only=False)
    e += box(60, 130, "安定化電源", [(85, "−"), (165, "＋")])
    e += box(250, 180, "DC-DC (DUT)", [(270, "−"), (305, "＋"), (360, "＋"), (400, "−")])
    e.append(text(287, 122, "入力", 11, "#666"))
    e.append(text(380, 122, "出力", 11, "#666"))
    e += box(500, 140, "電子負荷", [(525, "＋"), (605, "−")])
    x_ch0_p, x_ch0_m = sx(25.5), sx(18.5)
    x_ch1_p, x_ch1_m = sx(55.5), sx(48.5)
    ytop = sy(63.9) - 9
    e.append(wire(f"M 165,150 L 165,175 L {x_ch0_p:.0f},175 L {x_ch0_p:.0f},{ytop:.0f}", RED))
    e.append(wire(f"M {x_ch0_m:.0f},{ytop:.0f} L {x_ch0_m:.0f},210 "
                  + hop_r(x_ch0_p, 210) + "L 305,210 L 305,159", RED))
    e.append(wire("M 270,150 L 270,185 " + hop_l(x_ch0_p, 185)
                  + "L 85,185 L 85,159", BLUE))
    e.append(wire(f"M 85,150 L 72,162 L 40,162 L 40,655 L 700,655 L 700,200 "
                  f"L {sx(79.08):.0f},200 L {sx(79.08):.0f},{sy(65)-9:.0f}", BLUE))
    e.append(wire(f"M 360,150 L 360,190 L {x_ch1_p:.0f},190 L {x_ch1_p:.0f},{ytop:.0f}", RED))
    e.append(wire(f"M {x_ch1_m:.0f},{ytop:.0f} L {x_ch1_m:.0f},215 "
                  + hop_r(x_ch1_p, 215) + "L 525,215 L 525,159", RED))
    e.append(wire("M 605,150 L 605,195 " + hop_l(525, 195)
                  + "L 400,195 L 400,159", BLUE))
    e.append(label(370, 659, "基準 GND（遠回りで OK）", BLUE))
    return frame("DC-DC 効率測定のつなぎ方（J2 = 入力側 / J3 = 出力側）", e, 760, 700)


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(out, exist_ok=True)
    for name, svg in (("wiring-power.svg", power_svg()),
                      ("wiring-efficiency.svg", efficiency_svg())):
        with open(os.path.join(out, name), "w") as f:
            f.write(svg)
        print("wrote", os.path.join(out, name))


if __name__ == "__main__":
    main()
