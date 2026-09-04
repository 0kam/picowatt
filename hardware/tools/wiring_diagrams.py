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


def frame(title, body, width, height, footer=None):
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
    if footer is None:
        footer = ("赤 = ＋側の線　青 = −側の線　⌒ = 交差（接続しない）　"
                  "端子台の VBus には何も繋がない")
    head += text(18, height - 12, footer, 12, "#555", anchor="start")
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


def power_svg(missing_gnd=False):
    """Bench hookup for power measurement.

    missing_gnd=True draws the classic mistake instead: supply "-" wired
    straight to the DUT and nothing brought to J5.  The board GND then
    floats and VBUS reads mains hum (0 ... -50 V at 50/60 Hz).
    """
    e = board(power_only=True)
    e += box(80, 160, "測定対象 (DUT)", [(130, "＋"), (200, "−")])
    e += box(330, 160, "安定化電源", [(360, "＋"), (460, "−")])
    ytop = sy(63.9) - 9
    yj5 = sy(65) - 9
    e.append(wire(f"M 360,150 L 360,180 L {sx(25.5):.0f},180 "
                  f"L {sx(25.5):.0f},{ytop:.0f}", RED))
    e.append(wire(f"M {sx(18.5):.0f},{ytop:.0f} L {sx(18.5):.0f},205 "
                  f"L 130,205 L 130,159", RED))
    if not missing_gnd:
        e.append(wire("M 200,150 L 200,196 " + hop_r(sx(25.5), 196)
                      + f"L {sx(74):.0f},196 L {sx(74):.0f},{yj5:.0f}", BLUE))
        e.append(wire(f"M 460,150 L 460,168 L {sx(79.08):.0f},168 "
                      f"L {sx(79.08):.0f},{yj5:.0f}", BLUE))
        return frame("消費電力測定のつなぎ方（INA228 は J2 に 1 枚だけ）", e, 760, 700)

    # --- the mistake: DUT "-" goes straight back to the supply ---------------
    e.append(wire("M 200,150 L 200,168 L 460,168 L 460,159", BLUE))
    e.append(label(330, 190, "− は電源へ直行（これ自体は間違いではない）", BLUE, 11))
    # J5 left empty: dashed ghost of the missing link + a big cross
    e.append(f'<path d="M 460,168 L {sx(79.08):.0f},168 L {sx(79.08):.0f},{yj5:.0f}" '
             f'fill="none" stroke="{FAINT}" stroke-width="4.5" '
             f'stroke-dasharray="9 8" stroke-linecap="round"/>')
    cx, cy = sx(76.5), sy(65)
    e.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="30" fill="none" '
             f'stroke="{RED}" stroke-width="4"/>')
    e.append(f'<line x1="{cx-21:.0f}" y1="{cy-21:.0f}" x2="{cx+21:.0f}" y2="{cy+21:.0f}" '
             f'stroke="{RED}" stroke-width="4"/>')
    e.append(f'<line x1="{cx+21:.0f}" y1="{cy-21:.0f}" x2="{cx-21:.0f}" y2="{cy+21:.0f}" '
             f'stroke="{RED}" stroke-width="4"/>')
    e.append(label(cx - 30, cy + 84, "J5 に何も来ていない", RED, 13))
    e.append(label(cx - 30, cy + 104, "→ 基板の GND が宙に浮く", RED, 12))

    # --- what the app then shows: the VBUS trace -----------------------------
    px, py, pw, ph = 640, 230, 330, 200
    e.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="8" '
             f'fill="#ffffff" stroke="#666" stroke-width="1.8"/>')
    e.append(text(px + pw/2, py + 24, "このとき VBUS はこう見える", 13, weight="bold"))
    ax0, ax1 = px + 52, px + pw - 16          # plot area (x)
    y0, y53 = py + 50, py + ph - 60           # 0 V and -53 V rows
    e.append(f'<line x1="{ax0}" y1="{y0}" x2="{ax1}" y2="{y0}" stroke="#999" stroke-width="1"/>')
    e.append(f'<line x1="{ax0}" y1="{y53}" x2="{ax1}" y2="{y53}" stroke="#999" '
             f'stroke-width="1" stroke-dasharray="4 4"/>')
    e.append(text(ax0 - 6, y0 + 4, "0 V", 11, "#555", anchor="end"))
    e.append(text(ax0 - 6, y53 + 4, "−53 V", 11, RED, anchor="end", weight="bold"))
    import math
    pts = []
    n = 120
    for k in range(n + 1):
        f = k / n
        x = ax0 + (ax1 - ax0) * f
        y = y0 + (y53 - y0) * (0.5 - 0.5 * math.cos(2 * math.pi * 3 * f))
        pts.append(f"{x:.1f},{y:.1f}")
    e.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{RED}" '
             f'stroke-width="2.5" stroke-linejoin="round"/>')
    e.append(f'<line x1="{ax0}" y1="{y53+14}" x2="{ax0 + (ax1-ax0)/3:.0f}" y2="{y53+14}" '
             f'stroke="#555" stroke-width="1.2"/>')
    e.append(text(ax0 + (ax1 - ax0) / 6, y53 + 30, "20 ms = 50 Hz（商用電源）", 11, "#555"))
    e.append(text(px + pw/2, py + ph - 6, "0 V と −数十 V の間を往復＝実在しない電圧", 11, RED))
    e.append(label(px + pw/2, py + ph + 30, "CLI は WARNING: bus voltage goes negative を出す", "#555", 11))

    return frame("よくある間違い：電源の − を J5 に繋ぎ忘れる", e, 1000, 700,
                 footer="灰色の破線 = 本来あるべき線。安定化電源の − から J5 へ 1 本足せば直る")


def vbus_reference_svg():
    """Concept figure: what VBUS is measured against, and why J5 matters."""
    W, H = 820, 556
    e = []
    # --- INA228 module block -------------------------------------------------
    bx0, by0, bx1, by1 = 250, 80, 520, 300
    e.append(f'<rect x="{bx0}" y="{by0}" width="{bx1-bx0}" height="{by1-by0}" rx="10" '
             f'fill="#faf8f1" stroke="#9aa3ad" stroke-width="1.8"/>')
    e.append(text((bx0 + bx1) / 2, by0 + 24, "INA228 モジュール（ch0）", 14, weight="bold"))
    y_p, y_m, x_sh = 130, 200, 330         # VIN+ / VIN- rows, shunt column
    # shunt path VIN+ -> 15 mOhm -> VIN-
    e.append(f'<line x1="{bx0}" y1="{y_p}" x2="{x_sh}" y2="{y_p}" stroke="{RED}" stroke-width="3"/>')
    e.append(f'<line x1="{x_sh}" y1="{y_p}" x2="{x_sh}" y2="{y_p+20}" stroke="{RED}" stroke-width="3"/>')
    e.append(f'<rect x="{x_sh-17}" y="{y_p+20}" width="34" height="30" fill="#e8e8e8" stroke="#888"/>')
    e.append(text(x_sh, y_p + 39, "15mΩ", 9, "#444"))
    e.append(f'<line x1="{x_sh}" y1="{y_p+50}" x2="{x_sh}" y2="{y_m}" stroke="{RED}" stroke-width="3"/>')
    e.append(f'<line x1="{x_sh}" y1="{y_m}" x2="{bx0}" y2="{y_m}" stroke="{RED}" stroke-width="3"/>')
    e.append(f'<circle cx="{bx0}" cy="{y_p}" r="6" fill="{RED}"/>')
    e.append(f'<circle cx="{bx0}" cy="{y_m}" r="6" fill="{RED}"/>')
    e.append(text(bx0 - 8, y_p - 9, "VIN+", 12, anchor="end", weight="bold"))
    e.append(text(bx0 - 8, y_m - 9, "VIN−", 12, anchor="end", weight="bold"))
    # VBus jumper -> A/D
    x_ad = 410
    e.append(f'<line x1="{x_sh}" y1="{y_p}" x2="{x_ad}" y2="{y_p}" stroke="{RED}" '
             f'stroke-width="3" stroke-dasharray="6 4"/>')
    e.append(text(x_sh + 6, y_p - 10, "VBusジャンパ(閉)", 9, "#555", anchor="start"))
    e.append(f'<path d="M {x_ad},{y_p-20} L {x_ad+45},{y_p} L {x_ad},{y_p+20} z" '
             f'fill="#d7dde8" stroke="#555" stroke-width="1.5"/>')
    e.append(text(x_ad + 13, y_p + 4, "A/D", 10, "#333"))
    e.append(text(x_ad + 55, y_p + 4, "= VBUS", 12, anchor="start", weight="bold"))
    # A/D reference -> GND pin (bottom centre of the block)
    x_g = 385
    e.append(f'<line x1="{x_ad}" y1="{y_p+20}" x2="{x_ad}" y2="{y_m+60}" stroke="{BLUE}" stroke-width="3"/>')
    e.append(f'<line x1="{x_ad}" y1="{y_m+60}" x2="{x_g}" y2="{y_m+60}" stroke="{BLUE}" stroke-width="3"/>')
    e.append(f'<line x1="{x_g}" y1="{y_m+60}" x2="{x_g}" y2="{by1}" stroke="{BLUE}" stroke-width="3"/>')
    e.append(f'<circle cx="{x_g}" cy="{by1}" r="6" fill="{BLUE}"/>')
    e.append(text(x_g + 12, by1 + 16, "GND ピン", 12, anchor="start", weight="bold"))
    e.append(text(x_sh, y_m + 40, "A/D は VBUS を", 11, "#555"))
    e.append(text(x_sh, y_m + 56, "自分の GND ピン基準で測る", 11, "#555"))

    # --- carrier GND plane + J5 ---------------------------------------------
    y_pl = 400
    e.append(f'<rect x="230" y="{y_pl}" width="330" height="30" rx="6" fill="#dde7d6" stroke="#5a6b5a"/>')
    e.append(text(395, y_pl + 20, "キャリア基板の GND ベタ（Pico の GND も同電位）", 11, "#333"))
    e.append(f'<line x1="{x_g}" y1="{by1+6}" x2="{x_g}" y2="{y_pl}" stroke="{BLUE}" stroke-width="3"/>')
    e.append(f'<rect x="560" y="{y_pl-12}" width="62" height="50" rx="4" fill="{TERM}"/>')
    e.append(screw(580, y_pl + 12)); e.append(screw(602, y_pl + 12))
    e.append(text(591, y_pl + 56, "J5 (GND)", 12, weight="bold"))

    # --- bench: supply on the left, DUT on the right ------------------------
    e += box(30, 130, "安定化電源", [(60, "−"), (130, "＋")])
    e += box(660, 130, "測定対象", [(690, "＋"), (760, "−")])
    e.append(wire(f"M 130,150 L 130,172 L 228,172 L 228,{y_p} L {bx0-6},{y_p}", RED, marker=False))
    e.append(wire(f"M {bx0-6},{y_m} L 212,{y_m} L 212,325 " + hop_r(x_g, 325)
                  + "L 690,325 L 690,159", RED))
    e.append(wire("M 760,150 L 760,345 " + hop_l(x_g, 345) + "L 60,345 L 60,159", BLUE))
    e.append(dot(60, 345, BLUE))
    # THE GND link
    e.append(wire(f"M 60,345 L 60,470 L 580,470 L 580,{y_pl+30}", BLUE))
    e.append(label(330, 495, "GND リンク：電源の − → J5。これが無いと GND ピンの電位が決まらず、", BLUE, 11))
    e.append(label(330, 512, "浮いた基板が商用電源の 50/60 Hz を拾って VBUS が暴れる", BLUE, 11))
    return frame("VBUS は「INA228 の GND ピン」基準で測られる", e, W, H,
                 footer="⌒ = 交差（接続しない）　GND リンクにはほぼ電流が流れないが、無いと測定の基準が消える")


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



# ---------------------------------------------------------------------------
# Breadboard hookup (no carrier board)
# ---------------------------------------------------------------------------

GREEN, ORANGE = "#2e7d32", "#ef6c00"          # SDA / SCL
RAIL_Y = {"3V3": 560, "GND": 585, "SDA": 610, "SCL": 635}
RAIL_C = {"3V3": RED, "GND": BLUE, "SDA": GREEN, "SCL": ORANGE}


def rtext(x, y, t, size=8, fill=INK):
    """Text rotated -90 deg (reads bottom-to-top), anchored at its start."""
    return (f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="start" font-family="sans-serif" '
            f'transform="rotate(-90 {x:.0f} {y:.0f})">{esc(t)}</text>')


def thin(d, color, faded=False):
    op = ' stroke-opacity="0.25"' if faded else ""
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3" '
            f'stroke-linejoin="round" stroke-linecap="round"{op}/>')


def bb_ina(x0, ch, color, note, faded=False):
    """INA228 breakout: screw terminals on top, 8-pin header at the bottom."""
    y0, y1 = 230, 400
    e = [f'<rect x="{x0}" y="{y0}" width="160" height="{y1-y0}" rx="4" '
         f'fill="{MODULE}" stroke="#9aa3ad" stroke-width="1.5"/>']
    e.append(f'<rect x="{x0+55}" y="{y0-8}" width="100" height="44" rx="3" fill="{TERM}"/>')
    for k, nm in enumerate(("VIN−", "VBus", "VIN+")):
        sx_ = x0 + 70 + 35 * k
        e.append(screw(sx_, y0 + 14))
        e.append(text(sx_, y0 + 50, nm, 10, "#999" if nm == "VBus" else INK,
                      weight="normal" if nm == "VBus" else "bold"))
    e.append(text(x0 + 80, y0 + 95, "INA228", 12, "#8a8a8a"))
    e.append(text(x0 + 80, y0 + 112, note, 9, "#777"))
    pins = ("VIN", "GND", "SCL", "SDA", "VBUS", "VIN-", "VIN+", "ALRT")
    for k, nm in enumerate(pins):
        px = x0 + 10 + 20 * k
        e.append(f'<circle cx="{px}" cy="{y1-6}" r="3.5" fill="#8b8b83"/>')
        e.append(rtext(px + 3, y1 - 14, nm, 8, "#555"))
    e.append(f'<rect x="{x0-4}" y="{y1+8}" width="168" height="20" rx="10" fill="{color}"/>')
    e.append(text(x0 + 80, y1 + 22, ch, 11, "#ffffff", weight="bold"))
    if faded:
        e.append(f'<rect x="{x0-6}" y="{y0-12}" width="172" height="{y1-y0+45}" '
                 f'rx="4" fill="#ffffff" fill-opacity="0.6"/>')
    return e


def bb_pico():
    """Pico 2 seen from the top, USB up: pins 1-20 down the left, 40-21 down the right."""
    x0, x1, y0 = 70, 180, 220
    e = [f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="315" rx="4" '
         f'fill="{MODULE}" stroke="#9aa3ad" stroke-width="1.5"/>',
         f'<rect x="{(x0+x1)/2-16}" y="{y0-10}" width="32" height="22" fill="#c9c9c9" stroke="#8a8a8a"/>',
         text((x0 + x1) / 2, y0 + 6, "USB", 8, "#666"),
         text((x0 + x1) / 2, y0 + 170, "Pico 2", 14, weight="bold"),
         text((x0 + x1) / 2, y0 + 188, "（上から見た図）", 9, "#777")]
    for k in range(20):
        y = y0 + 15 + 15 * k
        for x in (x0, x1):
            e.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="#8b8b83"/>')
        e.append(text(x0 + 10, y + 3, str(k + 1), 7, "#999", anchor="start"))
        e.append(text(x1 - 10, y + 3, str(40 - k), 7, "#999", anchor="end"))
    return e


def pin_y(n):
    return 235 + 15 * ((n - 1) if n <= 20 else (40 - n))


def breadboard_svg(efficiency=False):
    W, H = 920, 750
    e = ['<g transform="translate(0,30)">'] + bb_pico()
    e += bb_ina(260, "#1 = ch0 0x40 入力", "#b26a00", "A0 は開けたまま")
    e += bb_ina(470, "#2 = ch1 0x41 出力", "#00796b",
                "裏の A0 を閉じる" if efficiency else "効率測定のときだけ", faded=not efficiency)
    # OLED
    e.append('<rect x="690" y="270" width="140" height="130" rx="3" fill="#2b2b33"/>')
    e.append('<rect x="702" y="290" width="116" height="70" fill="#10131f"/>')
    e.append(text(760, 284, "OLED SSD1306", 10, "#cccccc"))
    for k, nm in enumerate(("GND", "VDD", "SCK", "SDA")):
        px = 730 + 20 * k
        e.append(f'<circle cx="{px}" cy="394" r="3.5" fill="#8b8b83"/>')
        e.append(rtext(px + 3, 386, nm, 8, "#cccccc"))
    e.append(text(760, 420, "ピン順はロットで違う。実物のシルクで確認", 9, "#c62828"))

    # --- rails --------------------------------------------------------------
    taps = {"3V3": (180, pin_y(36), 210), "GND": (180, pin_y(38), 225),
            "SDA": (70, pin_y(6), 52), "SCL": (70, pin_y(7), 40)}
    for nm, (px, py, vx) in taps.items():
        y = RAIL_Y[nm]
        e.append(thin(f"M {px},{py} L {vx},{py} L {vx},{y} L 880,{y}", RAIL_C[nm]))
        e.append(dot(px, py, RAIL_C[nm]))
        e.append(label(vx if vx > 100 else 46, y - 7 if vx > 100 else y + 4, nm, RAIL_C[nm], 10))
    e.append(text(186, pin_y(36) - 6, "pin36 3V3 OUT", 8, RED, anchor="start"))
    e.append(text(186, pin_y(38) - 6, "pin38 GND", 8, BLUE, anchor="start"))
    e.append(text(64, pin_y(6) - 6, "pin6 GP4 SDA", 8, GREEN, anchor="end"))
    e.append(text(64, pin_y(7) + 12, "pin7 GP5 SCL", 8, ORANGE, anchor="end"))

    # device drops onto the rails
    def drops(x0, faded=False):
        for k, nm in enumerate(("3V3", "GND", "SCL", "SDA")):
            px = x0 + 10 + 20 * k
            e.append(thin(f"M {px},394 L {px},{RAIL_Y[nm]}", RAIL_C[nm], faded))
            if not faded:
                e.append(dot(px, RAIL_Y[nm], RAIL_C[nm]))
    drops(260)
    drops(470, faded=not efficiency)
    for k, nm in enumerate(("GND", "3V3", "SCL", "SDA")):
        px = 730 + 20 * k
        e.append(thin(f"M {px},394 L {px},{RAIL_Y[nm]}", RAIL_C[nm]))
        e.append(dot(px, RAIL_Y[nm], RAIL_C[nm]))

    # --- bench side: boxes and the power path --------------------------------
    ysc = 230 + 14 - 9                 # top of the terminal screws
    v1m, v1p = 330, 400                # INA #1 VIN- / VIN+ screws
    v2m, v2p = 540, 610                # INA #2
    if not efficiency:
        e += box(40, 160, "測定対象 (DUT)", [(70, "−"), (170, "＋")])
        e += box(470, 160, "安定化電源", [(500, "＋"), (600, "−")])
        e.append(wire(f"M 500,150 L 500,180 L {v1p},180 L {v1p},{ysc}", RED))
        e.append(wire(f"M {v1m},{ysc} L {v1m},200 L 170,200 L 170,159", RED))
        e.append(wire("M 600,150 L 600,205 L 880,205 L 880,585", BLUE))
        e.append(wire("M 70,150 L 70,185 L 24,185 L 24,20 L 880,20 L 880,205", BLUE, marker=False))
        e.append(dot(880, 205, BLUE))
        title = "ブレッドボード配線：消費電力測定（INA228 1 枚）"
    else:
        e += box(20, 140, "安定化電源", [(45, "−"), (125, "＋")])
        e += box(230, 200, "DC-DC (DUT)", [(250, "−"), (290, "＋"), (370, "＋"), (410, "−")])
        e.append(text(270, 122, "入力", 10, "#666"))
        e.append(text(390, 122, "出力", 10, "#666"))
        e += box(500, 150, "電子負荷", [(530, "＋"), (620, "−")])
        e.append(wire(f"M 125,150 L 125,195 " + hop_r(290, 195) + f"L {v1p},195 L {v1p},{ysc}", RED))
        e.append(wire(f"M {v1m},{ysc} L {v1m},210 L 290,210 L 290,159", RED))
        e.append(wire(f"M 370,150 L 370,190 " + hop_r(530, 190) + f"L {v2p},190 L {v2p},{ysc}", RED))
        e.append(wire(f"M {v2m},{ysc} L {v2m},212 L 530,212 L 530,159", RED))
        e.append(wire("M 410,150 L 410,178 " + hop_r(530, 178) + "L 620,178 L 620,159", BLUE))
        e.append(wire("M 620,150 L 620,205 L 880,205 L 880,585", BLUE))
        e.append(wire("M 45,150 L 45,170 L 24,170 L 24,20 L 880,20 L 880,205", BLUE, marker=False))
        e.append(wire("M 250,150 L 250,166 L 214,166 L 214,20", BLUE, marker=False))
        e.append(dot(214, 20, BLUE)); e.append(dot(880, 205, BLUE))
        title = "ブレッドボード配線：DC-DC 効率測定（INA228 2 枚）"
    e.append(label(835, 470, "GND リンク", BLUE, 11))
    e.append(label(835, 487, "電源の − → GND レール", BLUE, 9))
    e.append(label(835, 504, "忘れると VBUS が暴れる", RED, 9))
    e.append(text(560, 665, "レール = ブレッドボードの横一列（または電源レール）。● = 接続、●の無い交差は繋がっていない",
                  10, "#555"))
    e.append(text(560, 680, "I2C プルアップは INA228 基板上の 10kΩ で足りる。INA228 の VBus ジャンパは両方とも閉じる",
                  10, "#555"))
    e.append("</g>")
    return frame(title, e, W, H,
                 footer="赤 = ＋側 / 3V3　青 = −側 / GND　緑 = SDA　橙 = SCL　⌒ = 交差（接続しない）")


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(out, exist_ok=True)
    for name, svg in (("wiring-power.svg", power_svg()),
                      ("wiring-efficiency.svg", efficiency_svg()),
                      ("wiring-floating-gnd.svg", power_svg(missing_gnd=True)),
                      ("vbus-reference.svg", vbus_reference_svg()),
                      ("breadboard-power.svg", breadboard_svg()),
                      ("breadboard-efficiency.svg", breadboard_svg(efficiency=True))):
        with open(os.path.join(out, name), "w") as f:
            f.write(svg)
        print("wrote", os.path.join(out, name))


if __name__ == "__main__":
    main()
