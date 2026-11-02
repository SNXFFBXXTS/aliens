"""Weird style: black backgrounds, one colour family per biome, generated alien flora, palette cycling.

Images are 8-bit *palette indices* (not colours). The palette changes every frame for the cycling
families (sea, lava, spore, prism, lumen, bog), so the world shimmers without being redrawn.
Sprites are 16x16 char grids: '1' = body (mid shade), '2' = dark/trunk, '3' = bright tips/eyes.
"""
import colorsys, math, zlib
import numpy as np

T = 16          # design grid the generators think in
RES = 2         # drawn at twice that: thin 1-pixel lines, fine specks
TS = T * RES    # tile size in pixels
PIX = 3         # final look: everything shrunk by this and blown back up (chunky, slightly broken pixels)
BIG = {"canopy": 4, "spire": 4, "coral": 4, "eye": 4, "shroom": 4, "bulb": 4, "peak": 4, "hut": 4, "shard": 3}
_res = RES      # resolution the generators are drawing at right now (BIG kinds draw at 4 = 64 px)

FAM_DEF = {   # dark, mid, bright
    "sea": ("#020814", "#0f4c8a", "#7fe8ff"), "lava": ("#1a0200", "#c42a08", "#fff27a"),
    "ice": ("#06121c", "#5f9fc0", "#f2ffff"), "frost": ("#0a0820", "#5a5ac8", "#e0e6ff"),
    "moss": ("#081202", "#6a9a1c", "#eaff7a"), "bloom": ("#16031a", "#b0307a", "#ffb8e8"),
    "ochre": ("#160d02", "#b0781c", "#ffe28a"), "witch": ("#010f06", "#1f8a4a", "#a8ffb8"),
    "lumen": ("#00120c", "#00b884", "#d0fff4"), "bog": ("#081006", "#5a7a2a", "#dcff60"),
    "dune": ("#160a02", "#c86a28", "#ffdcaa"), "salt": ("#161216", "#b8a4b0", "#fff6fc"),
    "rust": ("#160302", "#b03a1a", "#ffa878"), "stone": ("#0a0810", "#6a6480", "#dcd8ee"),
    "ash": ("#0a0808", "#5a5250", "#cfc6c0"), "spore": ("#12031a", "#9a2ac8", "#ffa8ff"),
    "prism": ("#06041a", "#4a8ad8", "#ffffff"), "brick": ("#120a04", "#9a6a3a", "#ffdcaa"),
    "eye": ("#161200", "#d8b000", "#fffbe0"), "blood": ("#120004", "#a0102a", "#ff8a98"),
    # ground materials for roads and towns
    "dirt": ("#120b06", "#6e5236", "#d6b68c"), "cobble": ("#0c0b0c", "#66625e", "#d2ccc2"),
    "clay": ("#140604", "#7e3a24", "#dc9a78"), "wood": ("#0e0804", "#5e4226", "#c49a68"),
}
FAMS = list(FAM_DEF)
NS = 8                                   # shades per family


def hx(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)


def ramp(d, m, b):
    out = []
    for k in range(NS):
        u = k / (NS - 1)
        c = d + (m - d) * (u / 0.55) if u < 0.55 else m + (b - m) * ((u - 0.55) / 0.45)
        out.append(np.clip(c, 0, 255))
    return out


BASE = {f: ramp(*map(hx, FAM_DEF[f])) for f in FAMS}


def F(fam, k):
    """palette index of shade k (0 dark .. 7 bright) of a family"""
    return 8 + FAMS.index(fam) * NS + k


SHADE = np.zeros(256, np.uint8)            # palette index -> the same thing in shadow
for _f in range(len(FAM_DEF)):
    for _k in range(NS):
        _i = 8 + _f * NS + _k
        SHADE[_i] = 0 if _k <= 1 else 8 + _f * NS + max(0, _k - 3)


def palette(t=0.0):
    pal = np.zeros((256, 3), np.uint8)
    for f in FAMS:
        r = BASE[f]
        for k in range(NS):
            c = r[k]
            if f in ("sea", "lava") and k >= 2:                     # flowing shimmer: shades rotate
                sp = 2 if f == "sea" else 3
                c = r[2 + (k - 2 + int(t * sp)) % (NS - 2)]
            elif f in ("spore", "prism"):                           # hue drift
                h, l, s = colorsys.rgb_to_hls(*(c / 255))
                h = (h + (t * 0.006 if f == "prism" else 0.05 * math.sin(t * 0.12))) % 1   # slow drift
                c = np.array(colorsys.hls_to_rgb(h, l, s)) * 255
            elif f in ("lumen", "bog") and k >= 4:                  # breathing glow, slow
                c = c * (0.9 + 0.1 * math.sin(t * 0.35 + k))
            pal[F(f, k)] = np.clip(c, 0, 255)
    return pal


# ── sprite generators ──
def canvas():
    return np.full((T * _res, T * _res), ".")


def put(c, x, y, ch, over=True):
    """x, y in design units (0-16); lands on the fine grid"""
    n = c.shape[0]
    x, y = int(round(x * _res)), int(round(y * _res))
    if 0 <= x < n and 0 <= y < n and (over or c[y, x] == "."):
        c[y, x] = ch


def line(c, x0, y0, x1, y1, ch):
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * _res) + 1
    for i in range(n + 1):
        put(c, x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n, ch)


def disc(c, cx, cy, r, ch, rng=None, holes=0.0):
    n = c.shape[0]
    for py in range(n):
        for px in range(n):
            x, y = px / _res, py / _res
            if (x - cx) ** 2 + ((y - cy) * 1.1) ** 2 <= r * r and (rng is None or rng.random() > holes):
                c[py, px] = ch


class _Fine:
    def __iter__(self):
        return iter(np.arange(0, T, 1 / _res))


FINE = _Fine()


def mirror(c):
    h = c.shape[1] // 2
    c[:, h:] = c[:, :h][:, ::-1]
    return c


def g_spire(rng):
    c = canvas(); x = 7.5 + rng.uniform(-1, 1); lean = rng.uniform(-0.35, 0.35); h = rng.integers(10, 15)
    px_, py_ = x, 15
    for i in range(h):
        y = 15 - i
        x += lean + rng.uniform(-0.4, 0.4)
        line(c, px_, py_, x, y, "2"); px_, py_ = x, y
        if i > 3 and i % rng.integers(2, 4) == 0:
            d = rng.choice([-1, 1]); bx, by = x, y
            for k in range(rng.integers(2, 5)):
                nx, ny = bx + d, by - 0.6 * k
                line(c, bx, by, nx, ny, "1"); bx, by = nx, ny
            put(c, bx, by - 0.5, "3")
    disc(c, x, 15 - h, 1.3, "3")
    return c


def g_canopy(rng):
    c = canvas(); cx, cy, r = 7.5 + rng.uniform(-1, 1), rng.uniform(4.5, 6.5), rng.uniform(3.8, 5.6)
    line(c, 7.5, 15, cx, cy + 2, "2"); line(c, 8.5, 15, cx + 1, cy + 2, "2")
    disc(c, cx, cy, r, "1", rng, 0.12)
    for _ in range(rng.integers(3, 7)):
        put(c, cx + rng.uniform(-r, r) * 0.7, cy + rng.uniform(-r, r) * 0.6, "3")
    for _ in range(rng.integers(2, 6)):                         # drips
        dx = cx + rng.uniform(-r, r) * 0.8
        for k in range(rng.integers(1, 5)):
            put(c, dx, cy + r * 0.85 + k, "1")
    return c


def g_coral(rng):
    c = canvas()
    def br(x, y, a, ln, d):
        x1, y1 = x + math.sin(a) * ln, y - math.cos(a) * ln
        line(c, x, y, x1, y1, "1" if d else "2")
        if d < 3:
            for s in (-1, 1):
                br(x1, y1, a + s * rng.uniform(0.3, 0.8), ln * rng.uniform(0.55, 0.8), d + 1)
        else:
            put(c, x1, y1, "3")
    br(7.5, 15, rng.uniform(-0.2, 0.2), rng.uniform(4, 6), 0)
    return mirror(c) if rng.random() < 0.6 else c


def g_bulb(rng):
    c = canvas(); top = rng.uniform(2, 5); side = rng.choice([-1, 1]); reach = rng.uniform(3, 6)
    pts = []
    for i in range(40):
        u = i / 39
        x = 7.5 + side * reach * math.sin(u * math.pi * 0.85)
        y = 15 - (15 - top) * math.sin(u * math.pi / 2)
        put(c, x, y, "2"); pts.append((x, y))
    for (x, y) in pts[16::8]:
        dl = rng.integers(1, 4)
        line(c, x, y, x, y + dl, "1")
        disc(c, x, y + dl + 1.2, 1.1, "3")
    return c


def g_eye(rng):
    c = canvas(); cy = rng.uniform(5, 7)
    line(c, 7.5, 15, 7.5, cy + 3, "2"); line(c, 8.5, 15, 8.5, cy + 3, "2")
    disc(c, 7.5, cy, rng.uniform(4.5, 5.5), "1", rng, 0.05)
    disc(c, 7.5, cy, 2.4, "3"); disc(c, 7.5 + rng.uniform(-0.6, 0.6), cy, 1.0, "2")
    for _ in range(rng.integers(2, 5)):
        x = rng.uniform(3, 12)
        line(c, x, cy + 3, x + rng.uniform(-1, 1), cy + 3 + rng.integers(2, 5), "1")
    return c


def g_stalks(rng):
    c = canvas()
    for _ in range(rng.integers(2, 5)):
        x0, h, ph, amp = rng.uniform(2, 13), rng.integers(5, 13), rng.uniform(0, 6), rng.uniform(0.5, 1.5)
        for i in np.arange(0, h, 1 / _res):
            put(c, x0 + amp * math.sin(ph + i * 0.6), 15 - i, "1")
        tx, ty = x0 + amp * math.sin(ph + h * 0.6), 15 - h
        if rng.random() < 0.5:
            put(c, tx - 1, ty, "3"); put(c, tx + 1, ty, "3")
        else:
            disc(c, tx, ty, 1.0, "3")
    return c


def g_shroom(rng):
    c = canvas(); cy, r = rng.uniform(4, 7), rng.uniform(4, 6.5)
    line(c, 7.5, 15, 7.5 + rng.uniform(-1.5, 1.5), cy, "2"); line(c, 8.5, 15, 8.5, cy, "2")
    for y in FINE:
        for x in FINE:
            if y <= cy and (x - 7.5) ** 2 + ((y - cy) * 1.6) ** 2 <= r * r:
                put(c, x, y, "1")
    for _ in range(rng.integers(3, 6)):
        put(c, 7.5 + rng.uniform(-r, r) * 0.7, cy - rng.uniform(0, r * 0.5), "3")
    for x in np.linspace(7.5 - r + 1, 7.5 + r - 1, rng.integers(3, 6)):
        for k in range(rng.integers(2, 6)):
            put(c, x + math.sin(k) * 0.6, cy + 1 + k, "1")
    return c


def g_shard(rng):
    c = canvas()
    for _ in range(rng.integers(1, 4)):
        bx, w, h, tilt = rng.uniform(3, 12), rng.uniform(1.5, 3), rng.integers(5, 14), rng.uniform(-0.25, 0.25)
        for i in np.arange(0, h, 1 / _res):
            half = w * (1 - i / h)
            cx = bx + tilt * i
            for x in np.arange(cx - half, cx + half + 0.01, 1 / _res):
                put(c, x, 15 - i, "1")
            put(c, cx - half, 15 - i, "3")
        put(c, bx + tilt * h, 15 - h, "3")
    return c


def g_ribs(rng):
    c = canvas(); n = rng.integers(2, 4)
    line(c, 1, 14, 14, 14, "2")
    for k in range(n):
        x = 3 + k * (10 / max(1, n - 1)) if n > 1 else 7.5
        h = rng.uniform(6, 11)
        for i in range(30):
            u = i / 29
            put(c, x - 2.5 * math.cos(u * math.pi / 2) + 2.5, 14 - h * math.sin(u * math.pi / 2) * (1 - u * 0.3), "1")
        put(c, x + 2.5, 14 - h * 0.7, "3")
    return c


def g_orbs(rng):
    c = canvas()
    line(c, 6.5, 15, 9.5, 15, "2"); line(c, 7, 14, 9, 14, "2")
    for _ in range(rng.integers(2, 5)):
        ox, oy, r = rng.uniform(3, 12), rng.uniform(2, 10), rng.uniform(0.8, 1.8)
        disc(c, ox, oy, r, "3")
        for k in range(1, rng.integers(2, 5)):
            put(c, ox, oy + r + k * 1.2, "1", over=False)
    return c


def g_rock(rng):
    c = canvas(); cx, cy, r = 7.5 + rng.uniform(-1, 1), rng.uniform(9, 11), rng.uniform(4.5, 6.5)
    disc(c, cx, cy, r, "1", rng, 0.04)
    disc(c, cx + 1.5, cy + 1.5, r * 0.6, "2")
    for _ in range(4):
        put(c, cx - rng.uniform(0, r * 0.6), cy - rng.uniform(0, r * 0.6), "3")
    return c


def g_peak(rng):
    c = canvas(); top = rng.uniform(1, 4); half = rng.uniform(6, 7.5); cx = 7.5 + rng.uniform(-1, 1)
    for y in np.arange(int(top), 16, 1 / _res):
        w = half * (y - top) / (15 - top)
        for x in np.arange(cx - w, cx + w + 0.01, 1 / _res):
            put(c, x, y, "2" if x > cx + w * 0.2 else "1")
        if y < top + 3:
            for x in np.arange(cx - w, cx + w + 0.01, 1 / _res):
                put(c, x, y, "3")
    return c


def g_hut(rng):
    c = canvas(); r = rng.uniform(4.5, 6)
    for y in FINE:
        for x in FINE:
            if y <= 14 and (x - 7.5) ** 2 + ((y - 14) * 1.15) ** 2 <= r * r:
                put(c, x, y, "1")
    line(c, 7, 14, 7, 12, "2"); line(c, 8, 14, 8, 12, "2")
    put(c, 7.5 + rng.choice([-2.5, 2.5]), 11, "3")
    line(c, 7.5, 14 - r * 0.87, 7.5, 14 - r * 0.87 - rng.integers(2, 4), "2")
    put(c, 7.5, 14 - r * 0.87 - 4, "3")
    return c


def g_cone(rng):
    c = g_peak(rng)
    c[c == "3"] = "1"
    for x in range(6, 10):
        put(c, x, 3, "3"); put(c, x, 2, "3")
    return c


def g_willow(rng):
    """drooping strands from a short trunk"""
    c = canvas(); top = rng.uniform(3, 5); cx = 7.5 + rng.uniform(-1, 1)
    line(c, 7.5, 15, cx, top + 2, "2"); line(c, 8.2, 15, cx + 0.7, top + 2, "2")
    for k in range(rng.integers(7, 12)):
        a = rng.uniform(-1.3, 1.3); L = rng.uniform(3, 6); drop = rng.uniform(7, 10)
        x, y = cx, top + 1
        for st in range(14):
            u = st / 13
            nx = cx + math.sin(a) * L * min(1, u * 2)
            ny = top + 1 - math.cos(a) * 1.5 * min(1, u * 3) + max(0, u - 0.3) * drop
            line(c, x, y, nx, ny, "1"); x, y = nx, ny
        put(c, x, y + 0.5, "3")
    return c


def g_tiers(rng):
    """stacked layers, like a frosted pine or a pagoda"""
    c = canvas(); n = int(rng.integers(3, 6)); cx = 7.5
    line(c, cx, 15, cx, 2, "2")
    for k in range(n):
        y = 13 - k * (10 / n); w = (n - k) * rng.uniform(1.0, 1.5) + 1; droop = rng.uniform(0.15, 0.35)
        for x in np.arange(cx - w, cx + w + 0.01, 1 / _res):
            put(c, x, y - (w - abs(x - cx)) * droop * 0.6, "1")
            put(c, x, y - (w - abs(x - cx)) * droop * 0.6 + 0.5, "1")
        put(c, cx - w, y + 0.5, "3"); put(c, cx + w, y + 0.5, "3")
    put(c, cx, 1.5, "3")
    return c


def g_twist(rng):
    """a corkscrew trunk with a ragged ball of leaves"""
    c = canvas(); h = rng.uniform(9, 12); ph = rng.uniform(0, 6)
    px, py = 7.5, 15
    for i in np.arange(0, h, 0.25):
        x = 7.5 + math.sin(ph + i * 0.9) * 1.6; y = 15 - i
        line(c, px, py, x, y, "2"); px, py = x, y
    disc(c, px, py - 1.5, rng.uniform(2.5, 3.8), "1", rng, 0.25)
    for _ in range(rng.integers(2, 5)):
        put(c, px + rng.uniform(-2.5, 2.5), py - 1.5 + rng.uniform(-2, 2), "3")
    return c


def g_fronds(rng):
    """a leaning trunk with long arching fronds"""
    c = canvas(); top = rng.uniform(3, 5.5); lean = rng.uniform(-1.5, 1.5)
    line(c, 7.5, 15, 7.5 + lean, top, "2")
    tx, ty = 7.5 + lean, top
    for k in range(rng.integers(5, 8)):
        a = -math.pi / 2 + rng.uniform(-1.6, 1.6); L = rng.uniform(4, 6.5)
        x, y = tx, ty
        for st in range(12):
            u = (st + 1) / 12
            nx = tx + math.cos(a) * L * u; ny = ty + math.sin(a) * L * u + (u ** 2) * L * 0.8
            line(c, x, y, nx, ny, "1"); x, y = nx, ny
            if st % 3 == 1:
                put(c, nx, ny + 0.6, "1")
    disc(c, tx, ty, 0.9, "3")
    return c


def g_spikes(rng):
    """a dead, thorny tree"""
    c = canvas()
    def br(x, y, a, ln, d):
        x1, y1 = x + math.sin(a) * ln, y - math.cos(a) * ln
        line(c, x, y, x1, y1, "2" if d == 0 else "1")
        if d < 4 and ln > 1:
            for sgn in (-1, 1):
                if rng.random() < 0.8:
                    br(x1, y1, a + sgn * rng.uniform(0.4, 1.1), ln * rng.uniform(0.45, 0.7), d + 1)
    br(7.5, 15, rng.uniform(-0.15, 0.15), rng.uniform(4, 6), 0)
    return c


def g_pillar(rng):
    """a wind-carved rock pillar with a cap"""
    c = canvas(); h = rng.uniform(8, 13); w = rng.uniform(1.4, 2.4)
    for y in np.arange(15 - h, 15.01, 1 / _res):
        ww = w * (1 + 0.25 * math.sin(y * 1.3))
        for x in np.arange(7.5 - ww, 7.5 + ww + 0.01, 1 / _res):
            put(c, x, y, "2" if x > 7.5 + ww * 0.3 else "1")
    disc(c, 7.5, 15 - h, w * 1.6, "1")
    put(c, 7.5 - w, 15 - h, "3")
    return c


def g_tuft(rng):
    """a clump of grass blades at the foot of the cell"""
    c = canvas()
    for _ in range(rng.integers(3, 7)):
        x0 = rng.uniform(2, 14); h = rng.uniform(2.5, 6); bend = rng.uniform(-1.2, 1.2)
        px, py = x0, 15.5
        for st in range(1, 8):
            u = st / 7
            x, y = x0 + bend * u * u, 15.5 - h * u
            line(c, px, py, x, y, "1" if u < 0.7 else "3"); px, py = x, y
    return c


GEN = {"spire": g_spire, "canopy": g_canopy, "coral": g_coral, "bulb": g_bulb, "eye": g_eye, "stalks": g_stalks,
       "shroom": g_shroom, "shard": g_shard, "ribs": g_ribs, "orbs": g_orbs, "rock": g_rock, "peak": g_peak,
       "hut": g_hut, "cone": g_cone, "willow": g_willow, "tiers": g_tiers, "twist": g_twist, "fronds": g_fronds,
       "spikes": g_spikes, "pillar": g_pillar, "tuft": g_tuft}
BIG.update({"willow": 4, "tiers": 4, "twist": 4, "fronds": 4, "spikes": 4, "pillar": 4})
# drawn live every frame (they sway); everything else is painted into the ground once
SWAY = {"canopy", "spire", "coral", "eye", "shroom", "bulb", "willow", "tiers", "twist", "fronds", "stalks", "tuft", "orbs"}
# how much of the listed density shows up in a zone (trees thinned out; rock, peaks, grass, fire as listed)
THIN = {"tuft": 1.0, "rock": 1.0, "peak": 1.0, "hut": 1.0, "cone": 1.0, "fire": 1.0, "shard": 0.6}

# biome: family, accent family for '3' (None = own), [(kind, density)], ground marks per cell
BIOMES = {
    "grass": ("moss", None, [("tuft", 0.45), ("stalks", 0.1), ("twist", 0.05), ("spire", 0.04)], 2),
    "meadow": ("bloom", None, [("tuft", 0.4), ("stalks", 0.15), ("willow", 0.08), ("bulb", 0.05)], 2),
    "savanna": ("ochre", None, [("tuft", 0.5), ("fronds", 0.08), ("spire", 0.05), ("spikes", 0.04)], 2),
    "forest": ("witch", "eye", [("canopy", 0.25), ("tiers", 0.14), ("willow", 0.1), ("twist", 0.08), ("spire", 0.08),
                                ("eye", 0.04), ("tuft", 0.12)], 1),
    "jungle": ("lumen", None, [("coral", 0.22), ("fronds", 0.2), ("bulb", 0.15), ("canopy", 0.1), ("tuft", 0.2)], 2),
    "swamp": ("bog", None, [("tuft", 0.25), ("stalks", 0.25), ("willow", 0.12), ("bulb", 0.08)], 2),
    "taiga": ("frost", None, [("tiers", 0.4), ("spire", 0.12), ("shard", 0.05)], 1),
    "tundra": ("ice", None, [("tuft", 0.12), ("shard", 0.08), ("spikes", 0.04)], 1),
    "icesheet": ("ice", None, [("shard", 0.3)], 1), "drift": ("ice", None, [("shard", 0.12), ("rock", 0.06)], 2),
    "desert": ("dune", None, [("pillar", 0.05), ("ribs", 0.03), ("spikes", 0.02), ("shard", 0.015)], 2),
    "salt": ("salt", None, [("shard", 0.12)], 2),
    "badlands": ("rust", None, [("pillar", 0.1), ("spikes", 0.08), ("ribs", 0.04)], 2),
    "hills": ("moss", None, [("tuft", 0.3), ("rock", 0.1), ("twist", 0.04), ("stalks", 0.06)], 2),
    "mountain": ("stone", None, [("peak", 0.5), ("rock", 0.35)], 1), "peak": ("stone", "ice", [("peak", 0.8), ("rock", 0.2)], 1),
    "ash": ("ash", "lava", [("fire", 0.02), ("spikes", 0.1), ("ribs", 0.04), ("rock", 0.05)], 2),
    "crust": ("ash", "lava", [("fire", 0.03)], 1), "volcano": ("ash", "lava", [("cone", 1.0)], 1),
    "fungal": ("spore", None, [("shroom", 0.3), ("orbs", 0.14), ("bulb", 0.06), ("tuft", 0.1)], 2),
    "crystal": ("prism", None, [("shard", 0.45)], 2),
    "beach": ("salt", None, [("tuft", 0.08), ("fronds", 0.03)], 1),
    "trail": ("brick", None, [], 2),
    "road": ("brick", None, [], 3), "plaza": ("brick", None, [], 3), "house": ("brick", "eye", [("hut", 1.0)], 0),
    "bonfire": ("brick", None, [("fire", 1.0)], 3),
}
WATER = {"deep": 0, "ocean": 1, "shallow": 2, "lake": 2, "river": 2}

WAVE = np.array([list(r) for r in "..11...|.1..1..|1....11".split("|")])
BLOB = np.array([list(r) for r in ".111.|11111|11111|.111.".split("|")])
MARKS = [np.array([list(r) for r in s.split("|")]) for s in
         ("1", "1.|.1", ".1.|1.1", "11", "1|1", "1..|.11", "1.1", ".1|1.", "11.|..1")]


def mutate(c, rng):
    """the weird bit: random eyes, orbs, drips and tendrils sprouting off any plant"""
    ys, xs = np.nonzero(c != ".")
    if not len(ys):
        return
    for _ in range(rng.integers(1, 4)):
        i = rng.integers(len(ys)); x, y = xs[i] / _res, ys[i] / _res
        m = rng.integers(4)
        if m == 0:                                    # an eye
            disc(c, x, y, 1.6, "3"); put(c, x, y, "2")
        elif m == 1:                                  # floating orb
            disc(c, x + rng.integers(-3, 4), y - rng.integers(2, 5), 1.0, "3")
        elif m == 2:                                  # drip
            for k in range(1, rng.integers(3, 6)):
                put(c, x, y + k, "1", over=False)
            put(c, x, y + k + 1, "3", over=False)
        else:                                         # curl
            for k in range(8):
                a = k * 0.8
                put(c, x + math.cos(a) * k * 0.35, y - k * 0.4 + math.sin(a) * 0.8, "1", over=False)


class Species:
    """each world gets its own flora: sprites made from the seed"""

    def __init__(self, seed):
        self.cache = {}
        self.seed = seed

    def get(self, biome, kind, n, big=False):
        global _res
        k = (biome, kind, n, big)
        if k not in self.cache:
            h = zlib.crc32(f"{self.seed}:{biome}:{kind}:{n}".encode())
            rng = np.random.default_rng(h)
            _res = BIG.get(kind, RES) if big else RES
            try:
                spr = GEN[kind](rng)
                if kind not in ("rock", "peak", "hut", "cone") and rng.random() < 0.45:
                    mutate(spr, rng)
            finally:
                _res = RES
            self.cache[k] = spr
        return self.cache[k]


class Painter8:
    def __init__(self, w, h):
        self.img = np.zeros((h * TS, w * TS), np.uint8)

    def cell(self, x, y):
        return self.img[y * TS:(y + 1) * TS, x * TS:(x + 1) * TS]

    def fill(self, x, y, idx):
        self.cell(x, y)[:] = idx

    def sprite(self, x, y, spr, m, dx=0, dy=0):
        c = self.cell(x, y)
        for ch, idx in m.items():
            if idx is None:
                continue
            msk = spr == ch
            if dx or dy:
                msk = np.roll(np.roll(msk, dy, 0), dx, 1)
            c[msk] = idx

    def shadow(self, x, y, spr, dx=0):
        """the sprite's silhouette, sheared down-right and squashed: sun in the top left"""
        ys, xs = np.nonzero(spr != ".")
        if not len(ys):
            return
        base = ys.max()
        h = base - ys
        sx = np.round(xs + dx + h * 0.65 + 2).astype(int)
        sy = np.round(base - h * 0.28 + 1).astype(int)
        c = self.cell(x, y)
        for ox, oy in ((0, 0), (1, 0), (0, 1)):           # thicken so it reads as a solid shape
            X, Y = sx + ox, sy + oy
            ok = (X >= 0) & (X < TS) & (Y >= 0) & (Y < TS)
            c[Y[ok], X[ok]] = SHADE[c[Y[ok], X[ok]]]

    def _origin(self, x, y, spr, dx):
        n = spr.shape[0]
        return x * TS + TS // 2 - n // 2 + dx, (y + 1) * TS - n

    def big_shadow(self, x, y, spr, dx=0):
        """the long shadow of a big sprite: its silhouette sheared down-right; darkens what's beneath"""
        x0, y0 = self._origin(x, y, spr, dx)
        H, W = self.img.shape
        ys, xs = np.nonzero(spr != ".")
        if not len(ys):
            return
        base = ys.max()
        h = base - ys
        sx = np.round(xs + h * 0.7 + 3).astype(int) + x0
        sy = np.round(base - h * 0.3 + 1).astype(int) + y0
        pts = set()
        for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            X, Y = sx + ox, sy + oy
            ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
            pts.update(zip(Y[ok].tolist(), X[ok].tolist()))
        if pts:
            Y, X = np.array(list(pts)).T
            self.img[Y, X] = SHADE[self.img[Y, X]]

    def big_body(self, x, y, spr, m, dx=0):
        x0, y0 = self._origin(x, y, spr, dx)
        H, W = self.img.shape
        for ch, idx in m.items():
            yy, xx = np.nonzero(spr == ch)
            X, Y = xx + x0, yy + y0
            ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
            self.img[Y[ok], X[ok]] = idx

    def draw_big(self, items):
        """all the shadows first, then the bodies back to front, so no shadow cuts across a tree"""
        items = sorted(items, key=lambda it: (it[1], it[0]))
        for (x, y, spr, m, dx) in items:
            self.big_shadow(x, y, spr, dx)
        for (x, y, spr, m, dx) in items:
            self.big_body(x, y, spr, m, dx)

    def stamp(self, x, y, st, idx, px, py):
        c = self.cell(x, y)
        ys, xs = np.nonzero(st == "1")
        ys, xs = ys + py, xs + px
        ok = (ys >= 0) & (ys < TS) & (xs >= 0) & (xs < TS)
        c[ys[ok], xs[ok]] = idx


def ground(p, x, y, fam, r):
    """dark tinted ground with a fine grain"""
    c = p.cell(x, y)
    c[:] = F(fam, 1)
    g = np.random.default_rng(int(r[0] * 1e9) & 0xFFFFFFFF).random((TS, TS))
    c[g < 0.22] = F(fam, 0)
    c[g > 0.94] = F(fam, 2)


def paint(p, sp, x, y, b, r, local=True, defer=None, mode="full"):
    """b = biome code, r = per-cell random numbers (0..1). With a defer list, big/live things are queued
    there to be drawn after all the ground is down. mode: "full", "ground" (no plants/things) or "thing" (only them)."""
    if mode == "thing":
        hit = pick(sp, b, r, local)
        if hit and defer is not None:
            defer.append((hit[0], x, y) + hit[1:])
        return
    rr = lambda i: float(r[i % len(r)])
    pk = lambda i, n: int(rr(i) * n) % n
    pos = lambda i: (pk(i, TS - 3), pk(i + 1, TS - 3))
    if b in WATER:
        depth = WATER[b]
        p.fill(x, y, F("sea", 0) if depth < 2 else F("sea", 1))
        for k in range(3 + 2 * (depth > 0)):                     # ripples (they shimmer with the palette)
            px, py = pos(k * 2)
            st = WAVE if k % 2 == 0 else MARKS[1]
            p.stamp(x, y, st, F("sea", [3, 5, 6][depth] - (k % 3)), px, py)
        return
    if b == "seaice":
        p.fill(x, y, F("ice", 1)); p.stamp(x, y, MARKS[8], F("ice", 5), *pos(0)); p.stamp(x, y, MARKS[0], F("ice", 7), *pos(2)); return
    if b == "lava":
        p.fill(x, y, F("lava", 2))
        for k in range(7):                                       # molten blobs that churn with the palette
            p.stamp(x, y, BLOB if k < 4 else MARKS[[7, 2, 1][k % 3]], F("lava", 3 + k % 5), *pos(k * 2))
        return
    if b == "bridge":
        p.fill(x, y, F("sea", 1))
        for yy in range(10, 24, 3):
            p.cell(x, y)[yy:yy + 2, :] = F("brick", 4 if yy % 6 == 1 else 3)
        return
    fam, acc, kinds, marks = BIOMES.get(b, ("stone", None, [], 1))
    if local:
        ground(p, x, y, fam, r)                                 # dark tinted ground, so shadows have something to fall on
    else:
        p.fill(x, y, 0)
    if b in ("road", "plaza", "house"):
        ground(p, x, y, "brick", r) if local else p.fill(x, y, F("brick", 2))
    if b == "crust":
        p.fill(x, y, F("ash", 1))
        p.stamp(x, y, MARKS[8], F("lava", 3), *pos(0)); p.stamp(x, y, MARKS[5], F("lava", 2), *pos(3))
        marks = 0
    for k in range(2 * marks + (2 if marks else 0)):       # fine specks: more of them, each smaller
        p.stamp(x, y, MARKS[pk(k + 9, len(MARKS))], F(fam, 2 + pk(k + 3, 3)), *pos(k * 2))
    if mode == "ground":
        return
    hit = pick(sp, b, r, local)
    if not hit:
        return
    kind, spr, m, dx, big = hit
    if local and defer is not None and (kind in SWAY or kind == "fire" or big):
        defer.append((kind, x, y, spr, m, dx, big))
        return
    if kind == "fire":
        return
    if local:
        p.shadow(x, y, spr, dx)
    p.sprite(x, y, spr, m, dx=dx)


def pick(sp, b, r, local=True):
    """what grows or stands in this cell: (kind, sprite, colours, dx, big) or None. Pure: the same cell always
    gives the same answer, so neighbouring zones can ask about each other's border cells."""
    if b in WATER or b in ("seaice", "lava", "bridge"):
        return None
    fam, acc, kinds, marks = BIOMES.get(b, ("stone", None, [], 1))
    rr = lambda i: float(r[i % len(r)])
    pk = lambda i, n: int(rr(i) * n) % n
    roll = rr(5)
    for kind, dens in kinds:
        if local:
            dens *= THIN.get(kind, 0.32)
        else:
            dens = 1.0
            if kind in ("tuft", "fire"):
                continue
        if roll < dens:
            m = {"1": F(fam, 4), "2": F(fam, 2), "3": F(acc, 5) if acc else F(fam, 5)}
            if kind == "fire":
                return ("fire", None, m, 0, False)
            big = local and kind in BIG
            spr = sp.get(b, kind, pk(6, 12), big=big)
            dx = (pk(7, 9) - 4) if big else ((pk(7, 5) - 2) if local else 0)
            return (kind, spr, m, dx, big)
        roll -= dens
    return None


def pick_big(sp, b, r):
    """the big sprite (tree/hut/peak) a cell grows, if any: (kind, sprite, colours, dx) or None"""
    hit = pick(sp, b, r)
    if hit and hit[4]:
        return hit[0], hit[1], hit[2], hit[3]
    return None


def fire_frames(seed, nf=6):
    """flickering flames on embers, as RGBA frames (TS x TS)"""
    rng = np.random.default_rng(seed)
    cols = [(255, 246, 200), (255, 200, 70), (245, 120, 35), (180, 45, 20)]
    out = []
    for f in range(nf):
        a = np.zeros((TS, TS, 4), np.uint8)
        a[TS - 5:TS - 3, 9:23] = (70, 34, 20, 255)
        a[TS - 4, 11:21] = (150, 60, 20, 255)
        for x in range(10, 22):
            h = int(rng.uniform(4, 15) * (1 - abs(x - 15.5) / 7.5)) + 1
            for y in range(TS - 5 - h, TS - 4):
                u = (TS - 5 - y) / max(1, h)
                a[y, x] = cols[min(3, int(u * 4))] + (255,)
        for _ in range(rng.integers(1, 4)):                     # sparks
            a[rng.integers(4, TS - 16), rng.integers(9, 23)] = (255, 200, 90, 255)
        out.append(a)
    return out


def sway_frames(spr, m, pal, nf=8, amp=2.0, bob=False):
    """the sprite bending in the wind (top moves most, roots stay put), as RGBA frames"""
    n = spr.shape[0]
    pad = int(math.ceil(amp)) + 1
    ys, xs = np.nonzero(spr != ".")
    cols = np.array([pal[m.get(ch, 0)] for ch in spr[ys, xs]], np.uint8)
    lift = ((n - 1 - ys) / max(1, n - 1)) ** 1.5
    out = []
    for f in range(nf):
        s = math.sin(2 * math.pi * f / nf)
        a = np.zeros((n + 2 * pad, n + 2 * pad, 4), np.uint8)
        if bob:
            X, Y = xs + pad, ys + pad + int(round(s * amp))
        else:
            X, Y = xs + pad + np.round(s * amp * lift).astype(int), ys + pad
        a[Y, X, :3] = cols
        a[Y, X, 3] = 255
        out.append(a)
    return out, pad


# ── roads, paths and town squares as smooth flowing bands (not cell-sized blocks) ──
ROADLIKE = ("road", "plaza", "bonfire", "bridge")


def _blur(a):
    for _ in range(2):
        for ax in (0, 1):
            pad = np.pad(a, [(1, 1) if q == ax else (0, 0) for q in (0, 1)], mode="edge")
            lo = pad[:-2] if ax == 0 else pad[:, :-2]
            mid = pad[1:-1] if ax == 0 else pad[:, 1:-1]
            hi = pad[2:] if ax == 0 else pad[:, 2:]
            a = 0.25 * lo + 0.5 * mid + 0.25 * hi
    return a


def _up(a, m, cs):
    """cell-centred values -> one value per pixel of the zone (bilinear)"""
    s = (np.arange(cs * TS) + 0.5) / TS - 0.5 + m
    i0 = np.floor(s).astype(int)
    t = s - i0
    rows = a[i0] * (1 - t)[:, None] + a[i0 + 1] * t[:, None]
    return rows[:, i0] * (1 - t)[None, :] + rows[:, i0 + 1] * t[None, :]


def _clumpy(shape, rng, scale):
    """soft blotchy noise (0..1) with blobs about `scale` pixels across"""
    h, w = shape
    lo = rng.random((h // scale + 2, w // scale + 2))
    ys, xs = np.arange(h) / scale, np.arange(w) / scale
    y0, x0 = ys.astype(int), xs.astype(int)
    ty, tx = (ys - y0)[:, None], (xs - x0)[None, :]
    return (lo[y0][:, x0] * (1 - ty) * (1 - tx) + lo[y0 + 1][:, x0] * ty * (1 - tx) +
            lo[y0][:, x0 + 1] * (1 - ty) * tx + lo[y0 + 1][:, x0 + 1] * ty * tx)


def _h(a, b, seed):
    """hash of integer arrays -> 0..1"""
    h = (a.astype(np.int64) * 374761393 + b.astype(np.int64) * 668265263 + seed * 982451653) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def _cobbles(p, mask, ox, oy, seed, size=7):
    """irregular cobblestones: jittered Voronoi stones, lit from the top left, dark joints, a few missing"""
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return
    Y, X = ys + oy, xs + ox                              # world pixel coords so stones line up across zones
    gy, gx = Y // size, X // size
    d1 = np.full(len(ys), 1e9); d2 = np.full(len(ys), 1e9)
    sid = np.zeros(len(ys), np.int64); cyy = np.zeros(len(ys)); cxx = np.zeros(len(ys))
    for oy_ in (-1, 0, 1):
        for ox_ in (-1, 0, 1):
            cy_, cx_ = gy + oy_, gx + ox_
            py = cy_ * size + _h(cy_, cx_, seed) * size
            px = cx_ * size + _h(cy_, cx_, seed + 1) * size
            d = (Y - py) ** 2 + ((X - px) * 0.85) ** 2
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            d1 = np.where(closer, d, d1)
            sid = np.where(closer, cy_ * 100003 + cx_, sid)
            cyy = np.where(closer, py, cyy); cxx = np.where(closer, px, cxx)
    joint = np.sqrt(d2) - np.sqrt(d1) < 1.4
    tone = _h(sid, sid // 7, seed + 2)
    light = ((Y - cyy) + (X - cxx)) < -1.5               # top-left of each stone catches the light
    dark = ((Y - cyy) + (X - cxx)) > 2.0
    shade = 2 + (tone * 2.99).astype(int) + light.astype(int) - dark.astype(int)
    out = np.array([F("cobble", int(k)) for k in range(NS)])[np.clip(shade, 1, 6)]
    missing = _h(sid, sid // 3, seed + 3) < 0.07
    out = np.where(missing, F("dirt", 2), out)
    out = np.where(joint, np.where(missing, F("dirt", 1), F("cobble", 0)), out)
    p.img[ys, xs] = out


def _bricks(p, mask, ox, oy, seed, bw=10, bh=5):
    """staggered brick paving with a different colour per brick"""
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return
    Y, X = ys + oy, xs + ox
    row = Y // bh
    Xs = X + (row % 2) * (bw // 2)
    col = Xs // bw
    joint = (Y % bh == 0) | (Xs % bw == 0)
    tone = _h(row, col, seed)
    out = np.array([F("clay", k) for k in range(NS)])[2 + (tone * 2.99).astype(int)]
    out = np.where((Y % bh == 1) & ~joint, np.array([F("clay", k) for k in range(NS)])[3 + (tone * 2.99).astype(int)], out)
    out = np.where(joint, F("clay", 0), out)
    p.img[ys, xs] = out


def _dist(lines, H, W, reach):
    """distance (pixels) from every pixel to the nearest of the polylines, out to `reach`"""
    D = np.full((H, W), 1e9, np.float32)
    for pts in lines:
        for a, b in zip(pts[:-1], pts[1:]):
            x0 = int(max(0, min(a[0], b[0]) - reach)); x1 = int(min(W, max(a[0], b[0]) + reach + 1))
            y0 = int(max(0, min(a[1], b[1]) - reach)); y1 = int(min(H, max(a[1], b[1]) + reach + 1))
            if x0 >= x1 or y0 >= y1:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy or 1e-9
            t = np.clip(((xx - a[0]) * dx + (yy - a[1]) * dy) / L2, 0, 1)
            d = np.hypot(xx - (a[0] + t * dx), yy - (a[1] + t * dy)).astype(np.float32)
            D[y0:y1, x0:x1] = np.minimum(D[y0:y1, x0:x1], d)
    return D


NO_PATH = ("mountain", "peak", "lava", "house", "volcano")


def flow_bands(p, B, m, cs, seed, ox=0, oy=0, roads=(), trails=()):
    """roads and footpaths along their real routes (a defined worn middle, edges that fray and fade into
    the land), plus cobbled squares and brick lanes in towns. B = cell codes of the zone plus an m-cell
    margin; ox, oy = the zone's top-left in world pixels; roads/trails = centre lines in zone pixels."""
    rng = np.random.default_rng(seed)
    H, W = p.img.shape
    g = rng.random((H, W))
    g2 = rng.random((H, W))
    big = _clumpy((H, W), rng, 26)
    small = _clumpy((H, W), rng, 6)
    up = lambda cells: np.repeat(np.repeat(cells, TS, 0), TS, 1)
    inner = B[m:m + cs, m:m + cs]
    water = up(np.isin(inner, list(WATER) + ["bridge"]))
    blocked = up(np.isin(inner, NO_PATH))
    dirt = np.array([F("dirt", k) for k in range(NS)])
    v = big * 0.55 + small * 0.3 + g * 0.3
    wob = (small - 0.5) * 7 + (g - 0.5) * 2.5            # the edge wanders a little, pixel by pixel

    # footpaths: a narrow worn line, scuffed edges
    if len(trails):
        D = _dist(trails, H, W, 16) + wob
        core = (D < 4.5) & ~water & ~blocked
        fade = np.clip(1 - (D - 4.5) / 10, 0, 1)
        scuff = ~core & (g2 < fade * 0.5) & ~water & ~blocked
        p.img[scuff] = dirt[1]
        p.img[core] = dirt[np.clip((v[core] * 2.6).astype(int), 1, 2)]
        pk = core & (g2 > 0.997)
        p.img[pk] = F("cobble", 3)

    # roads: wider, two wheel ruts, puddles, dust thinning out on both sides
    if len(roads):
        D0 = _dist(roads, H, W, 34)
        D = D0 + wob
        core = (D < 14) & ~blocked
        fade = np.clip(1 - (D - 14) / 16, 0, 1)
        spill = ~core & (g2 < fade * 0.55) & ~water & ~blocked
        p.img[spill] = dirt[np.where(g[spill] < 0.4, 1, 2)]
        land = core & ~water
        p.img[land] = dirt[np.clip((v[land] * 3.4).astype(int), 1, 3)]
        rut = land & (np.abs(D0 - 6.5) < 1.2) & (g > 0.15)
        p.img[rut] = dirt[np.where(g[rut] > 0.6, 0, 1)]
        pud = land & (big > 0.76) & (small > 0.55)
        p.img[pud] = dirt[0]
        p.img[pud & ~np.roll(pud, 1, 0)] = F("cobble", 2)
        _bridge(p, core & water, ox, oy, seed)
        for msk, dens in ((land, 0.003),):
            ys, xs = np.nonzero(msk)
            if len(ys):
                k = rng.choice(len(ys), int(len(ys) * dens) + 1)
                for dy, dx, col in ((1, 1, F("dirt", 0)), (0, 0, F("cobble", 4)), (0, 1, F("cobble", 3))):
                    p.img[np.clip(ys[k] + dy, 0, H - 1), np.clip(xs[k] + dx, 0, W - 1)] = col

    # towns: cobbled squares and brick lanes (from the town's cells)
    ragged = (small - 0.5) * 0.11 + (g - 0.5) * 0.035
    rd = _up(_blur(np.isin(B, ROADLIKE).astype(float)), m, cs)
    town = _up(_blur(_blur(np.isin(B, ["plaza", "house", "bonfire"]).astype(float))), m, cs) > 0.05
    band = (rd + ragged > 0.26) & town
    square = _up(_blur(np.isin(B, ["plaza", "bonfire"]).astype(float)), m, cs) + ragged > 0.3
    edge = (rd + ragged > 0.19) & ~band & town & ~water & (g2 < 0.4)
    p.img[edge] = dirt[np.where(g[edge] < 0.4, 1, 2)]
    _cobbles(p, band & square & ~water, ox, oy, seed)
    lane = band & ~square & ~water
    _bricks(p, lane, ox, oy, seed)
    broken = lane & (small > 0.72) & (big > 0.5)
    p.img[broken] = dirt[np.clip((v[broken] * 3).astype(int), 1, 3)]
    _bridge(p, band & water, ox, oy, seed)


def _bridge(p, planks, ox, oy, seed):
    ys, xs = np.nonzero(planks)
    if len(ys):
        Y = ys + oy
        board = Y // 5
        tone = _h(board, board // 3, seed)
        out = np.array([F("wood", k) for k in range(NS)])[3 + (tone * 2.5).astype(int)]
        out = np.where(Y % 5 == 0, F("wood", 0), out)
        knot = _h(Y // 2, (xs + ox) // 3, seed + 5) < 0.02
        out = np.where(knot, F("wood", 1), out)
        p.img[ys, xs] = out


def to_rgb(img8, t=0.0):
    return palette(t)[img8]
