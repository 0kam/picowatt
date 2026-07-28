"""Audit the saved board: read tracks/vias/pads straight from the file."""
import math, re, sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else '.')
import routelib as R

s = open(R.PCB).read()
OX, OY = R.OX, R.OY

def blocks(text, head):
    for m in re.finditer(r'\n(\t+)\(' + head + r'\b', text):
        yield R._block(text, m.start() + 1)

segs, vias = [], []
for b in blocks(s, 'segment'):
    st = re.search(r'\(start ([-\d.]+) ([-\d.]+)\)', b)
    en = re.search(r'\(end ([-\d.]+) ([-\d.]+)\)', b)
    w  = float(re.search(r'\(width ([\d.]+)\)', b).group(1))
    ly = re.search(r'\(layer "([^"]+)"\)', b).group(1)
    nt = re.search(r'\(net "?([^")]+)"?\)', b).group(1).strip('"')
    p = (float(st.group(1)) - OX, OY - float(st.group(2)))
    q = (float(en.group(1)) - OX, OY - float(en.group(2)))
    segs.append((nt, ly, p, q, w))
for b in blocks(s, 'via'):
    at = re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', b)
    nt = re.search(r'\(net "?([^")]+)"?\)', b).group(1).strip('"')
    vias.append((nt, float(at.group(1)) - OX, OY - float(at.group(2))))

pads, npth = R.load_pads()
# re-attach nets from the KiCad-10 style (net "NAME") form
pads2 = []
for m in re.finditer(r'\n(\t+)\(footprint "([^"]+)"', s):
    ind = m.group(1); blk = R._block(s, m.start() + 1)
    at = re.search(r'\n' + ind + r'\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk)
    fx, fy, frot = float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)
    ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
    for pm in re.finditer(r'\n' + ind + r'\t\(pad "([^"]*)" (\w+) (\w+)', blk):
        pb = R._block(blk, pm.start() + 1)
        pat = re.search(r'\(at ([-\d.]+) ([-\d.]+)', pb)
        psz = re.search(r'\(size ([-\d.]+) ([-\d.]+)\)', pb)
        if not pat or not psz: continue
        px, py = float(pat.group(1)), float(pat.group(2))
        if frot:
            a = math.radians(frot)
            px, py = px*math.cos(a)+py*math.sin(a), -px*math.sin(a)+py*math.cos(a)
        half = max(float(psz.group(1)), float(psz.group(2)))/2
        nm = re.search(r'\(net "?([^")]+)"?\)', pb)
        net = nm.group(1).strip('"') if nm else None
        rec = (f"{ref}.{pm.group(1)}", net, fx+px-OX, OY-(fy+py), half)
        (pads2 if pm.group(2) != 'np_thru_hole' else npth).append(
            rec if pm.group(2) != 'np_thru_hole' else (rec[0], rec[2], rec[3], rec[4]))
print(f"tracks {len(segs)}  vias {len(vias)}  pads {len(pads2)}  npth {len(npth)}")
from collections import Counter, defaultdict
print("pads by net:", dict(Counter(p[1] for p in pads2 if p[1])))
L = defaultdict(float)
for nt, ly, p, q, w in segs: L[nt] += math.hypot(q[0]-p[0], q[1]-p[1])
print("track length:", {k: f"{v:.1f}" for k, v in sorted(L.items())})
print("vias by net:", dict(Counter(v[0] for v in vias)))
print("ALRT0 vertical Xs:", sorted({round(p[0],2) for nt,ly,p,q,w in segs
                                    if nt.lstrip('/')=='ALRT0' and abs(p[0]-q[0])<1e-6}))
print("ALRT1 vertical Xs:", sorted({round(p[0],2) for nt,ly,p,q,w in segs
                                    if nt.lstrip('/')=='ALRT1' and abs(p[0]-q[0])<1e-6}))

obs = [(r, n, x, y, h) for r, n, x, y, h in pads2] + \
      [(f"via@{x:.2f},{y:.2f}", n, x, y, 0.4) for n, x, y in vias]
rows = []
for nt, ly, p, q, w in segs:
    for ref, pn, x, y, half in obs:
        if pn == nt: continue
        need = w/2 + half + R.CLEAR
        got = R.seg_pt_dist(p, q, (x, y))
        rows.append((got-need, got, need, f"{nt} {ly} {p}->{q} vs {ref}[{pn}]"))
    for ref, x, y, half in npth:
        need = w/2 + half + R.CLEAR
        rows.append((R.seg_pt_dist(p,q,(x,y))-need, R.seg_pt_dist(p,q,(x,y)), need,
                     f"{nt} {ly} vs NPTH {ref}"))
rows.sort()
print("\ntightest 8 clearances:")
for m, g, n, d in rows[:8]:
    print(f"  {m:+.3f}mm  (actual {g:.3f} / need {n:.3f})  {d}")
