"""Route helper: parse the placed board, pre-flight check routes, emit segments.

Everything here works in carrier coordinates (origin bottom-left of the board,
X right, Y up, mm) and converts to KiCad page coordinates on output.
"""
import math
import re
import uuid as _uuid

OX, OY = 50.0, 120.0
BOARD_W, BOARD_H = 92.0, 70.0
CLEAR = 0.2          # project min_clearance
EDGE_CLEAR = 0.3     # min_copper_edge_clearance
PCB = "hardware/picowatt-carrier.kicad_pcb"


def K(x, y):
    return (round(OX + x, 4), round(OY - y, 4))


def uid():
    return str(_uuid.uuid4())


def _block(s, start):
    d = 0
    for j in range(start, len(s)):
        if s[j] == "(":
            d += 1
        elif s[j] == ")":
            d -= 1
            if d == 0:
                return s[start:j]
    raise ValueError("unbalanced")


def load_pads(path=PCB):
    """Format-agnostic: works on both our generated file and pcbnew's rewrite."""
    s = open(path).read()
    pads, npth = [], []
    for m in re.finditer(r'\n(\t+)\(footprint "([^"]+)"', s):
        ind = m.group(1)
        blk = _block(s, m.start() + 1)
        at = re.search(r'\n' + ind + r'\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk)
        fx, fy = float(at.group(1)), float(at.group(2))
        frot = float(at.group(3) or 0)
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        for pm in re.finditer(r'\n' + ind + r'\t\(pad "([^"]*)" (\w+) (\w+)', blk):
            pblk = _block(blk, pm.start() + 1)
            pat = re.search(r'\(at ([-\d.]+) ([-\d.]+)', pblk)
            psz = re.search(r'\(size ([-\d.]+) ([-\d.]+)\)', pblk)
            if not pat or not psz:
                continue
            px, py = float(pat.group(1)), float(pat.group(2))
            half = max(float(psz.group(1)), float(psz.group(2))) / 2.0
            if frot:
                a = math.radians(frot)
                px, py = (px * math.cos(a) + py * math.sin(a),
                          -px * math.sin(a) + py * math.cos(a))
            cx, cy = fx + px - OX, OY - (fy + py)
            if pm.group(2) == "np_thru_hole":
                npth.append((f"{ref}.hole", cx, cy, half))
                continue
            nm = re.search(r'\(net (?:\d+ )?"?([^")]+)"?\)', pblk)
            net = nm.group(1).strip('"').lstrip("/") if nm else None
            if net and net.startswith("unconnected-"):
                net = None
            pads.append((f"{ref}.{pm.group(1)}", net, cx, cy, half))
    return pads, npth


def _load_pads_old(path=PCB):
    """-> (pads, npth); pads = [(ref.pad, net, x, y, half_extent)]"""
    s = open(path).read()
    pads, npth = [], []
    for m in re.finditer(r'\n\t\(footprint "([^"]+)"\n\t\t\(layer "[^"]+"\)\n\t\t'
                         r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', s):
        fx, fy = float(m.group(2)), float(m.group(3))
        frot = float(m.group(4) or 0)
        blk = _block(s, m.start() + 1)
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        for pm in re.finditer(r'\(pad "([^"]*)" (\w+) (\w+)\s*\n\s*\(at ([-\d.]+) ([-\d.]+)\)'
                              r'\s*\n\s*\(size ([-\d.]+) ([-\d.]+)\)(.*?)\n\t\t\)',
                              blk, re.S):
            num, ptype = pm.group(1), pm.group(2)
            px, py = float(pm.group(4)), float(pm.group(5))
            sx, sy = float(pm.group(6)), float(pm.group(7))
            rest = pm.group(8)
            if frot:
                a = math.radians(frot)
                px, py = px * math.cos(a) + py * math.sin(a),                          -px * math.sin(a) + py * math.cos(a)
            cx, cy = fx + px - OX, OY - (fy + py)
            half = max(sx, sy) / 2.0
            if ptype == "np_thru_hole":
                npth.append((f"{ref}.hole", cx, cy, half))
                continue
            nm = re.search(r'\(net \d+ "([^"]+)"\)', rest)
            pads.append((f"{ref}.{num}", nm.group(1) if nm else None, cx, cy, half))
    return pads, npth


def seg_pt_dist(a, b, p):
    (ax, ay), (bx, by), (px, py) = a, b, p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        t = 0.0
    else:
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(px - qx, py - qy)


def seg_seg_dist(a, b, c, d):
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2 = cross(c, d, a), cross(c, d, b)
    d3, d4 = cross(a, b, c), cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(seg_pt_dist(a, b, c), seg_pt_dist(a, b, d),
               seg_pt_dist(c, d, a), seg_pt_dist(c, d, b))


def explode(routes):
    """routes = [(net, layer, [pts...], width)] -> [(net, layer, p, q, width)]"""
    out = []
    for net, layer, pts, w in routes:
        for i in range(len(pts) - 1):
            if pts[i] != pts[i + 1]:
                out.append((net, layer, pts[i], pts[i + 1], w))
    return out


def check(routes, pads, npth, vias=(), verbose=True):
    """Pre-flight: clearance to foreign pads/holes/segments/edges + connectivity."""
    segs = explode(routes)
    errs = []
    pads = list(pads) + [(f'via{i}', nt, x, y, 0.4)
                         for i, (nt, x, y) in enumerate(vias)]

    for net, layer, p, q, w in segs:
        for ref, pnet, px, py, half in pads:
            if pnet == net:
                continue
            need = w / 2 + half + CLEAR
            got = seg_pt_dist(p, q, (px, py))
            if got < need:
                errs.append(f"{net} {layer} {p}-{q}: pad {ref}[{pnet}] "
                            f"gap {got:.3f} < {need:.3f}")
        for ref, hx, hy, half in npth:
            need = w / 2 + half + CLEAR
            got = seg_pt_dist(p, q, (hx, hy))
            if got < need:
                errs.append(f"{net} {layer} {p}-{q}: NPTH {ref} "
                            f"gap {got:.3f} < {need:.3f}")
        for (x, y) in (p, q):
            pass
        for a, b in ((p, q),):
            for X in (0.0, BOARD_W):
                if min(abs(a[0] - X), abs(b[0] - X)) < w / 2 + EDGE_CLEAR:
                    errs.append(f"{net} {layer} {p}-{q}: board edge X={X}")
            for Y in (0.0, BOARD_H):
                if min(abs(a[1] - Y), abs(b[1] - Y)) < w / 2 + EDGE_CLEAR:
                    errs.append(f"{net} {layer} {p}-{q}: board edge Y={Y}")

    for i in range(len(segs)):
        n1, l1, p1, q1, w1 = segs[i]
        for j in range(i + 1, len(segs)):
            n2, l2, p2, q2, w2 = segs[j]
            if n1 == n2 or l1 != l2:
                continue
            need = w1 / 2 + w2 / 2 + CLEAR
            got = seg_seg_dist(p1, q1, p2, q2)
            if got < need:
                errs.append(f"{n1}/{n2} {l1}: {p1}-{q1} vs {p2}-{q2} "
                            f"gap {got:.3f} < {need:.3f}")

    # connectivity per net: union-find over segment endpoints + pads
    for net in sorted({r[0] for r in routes}):
        nodes = {}

        def find(k):
            nodes.setdefault(k, k)
            while nodes[k] != k:
                nodes[k] = nodes[nodes[k]]
                k = nodes[k]
            return k

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                nodes[ra] = rb

        def snap(pt):
            return (round(pt[0], 3), round(pt[1], 3))

        for n, layer, p, q, w in segs:
            if n != net:
                continue
            union(snap(p), snap(q))
        netpads = [(r, x, y) for r, pn, x, y, _h in pads if pn == net]
        roots = set()
        for r, x, y in netpads:
            key = snap((x, y))
            if key not in nodes:
                errs.append(f"{net}: pad {r} at {key} has no track endpoint")
            else:
                roots.add(find(key))
        if len(roots) > 1:
            errs.append(f"{net}: {len(roots)} disconnected islands")

    if verbose:
        if errs:
            print(f"  {len(errs)} problem(s):")
            for e in errs[:25]:
                print("   -", e)
        else:
            print("  pre-flight OK")
    return errs


def emit(routes, path=PCB, vias=()):
    """Replace all (segment ...) entries in the board with these routes."""
    s = open(path).read()
    s = re.sub(r'\n\t\(segment\n(?:\t\t.*\n)*?\t\)', '', s)
    s = re.sub(r'\n\t\(via\n(?:\t\t.*\n)*?\t\)', '', s)
    lines = []
    for net, layer, p, q, w in explode(routes):
        k1, k2 = K(*p), K(*q)
        lines.append(
            f'\t(segment\n\t\t(start {k1[0]} {k1[1]})\n\t\t(end {k2[0]} {k2[1]})\n'
            f'\t\t(width {w})\n\t\t(layer "{layer}")\n\t\t(net {NET_ID[net]})\n'
            f'\t\t(uuid "{uid()}")\n\t)')
    for nt, x, y in vias:
        k = K(x, y)
        lines.append(
            f'\t(via\n\t\t(at {k[0]} {k[1]})\n\t\t(size 0.8)\n\t\t(drill 0.4)\n'
            f'\t\t(layers "F.Cu" "B.Cu")\n\t\t(net {NET_ID[nt]})\n'
            f'\t\t(uuid "{uid()}")\n\t)')
    i = s.rindex("\n)")
    s = s[:i] + "\n" + "\n".join(lines) + s[i:]
    open(path, "w").write(s)
    return len(lines)


NET_ID = {"GND": 1, "+3V3": 2, "SDA": 3, "SCL": 4, "ALRT0": 5, "ALRT1": 6}
