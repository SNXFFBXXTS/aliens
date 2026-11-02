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
                sp = 5 if f == "sea" else 7
                c = r[2 + (k - 2 + int(t * sp)) % (NS - 2)]
            elif f in ("spore", "prism"):                           # hue drift
                h, l, s = colorsys.rgb_to_hls(*(c / 255))
                h = (h + (t * 0.08 if f == "prism" else 0.06 * math.sin(t * 0.9))) % 1
                c = np.array(colorsys.hls_to_rgb(h, l, s)) * 255
            elif f in ("lumen", "bog") and k >= 4:                  # breathing glow
                c = c * (0.8 + 0.2 * math.sin(t * 1.6 + k))
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


GEN = {"spire": g_spire, "canopy": g_canopy, "coral": g_coral, "bulb": g_bulb, "eye": g_eye, "stalks": g_stalks,
       "shroom": g_shroom, "shard": g_shard, "ribs": g_ribs, "orbs": g_orbs, "rock": g_rock, "peak": g_peak,
       "hut": g_hut, "cone": g_cone}

# biome: family, accent family for '3' (None = own), [(kind, local density)], ground marks per cell
BIOMES = {
    "grass": ("moss", None, [("stalks", 0.12), ("spire", 0.02)], 2),
    "meadow": ("bloom", None, [("stalks", 0.18), ("bulb", 0.04)], 2),
    "savanna": ("ochre", None, [("stalks", 0.1), ("spire", 0.035)], 2),
    "forest": ("witch", "eye", [("canopy", 0.3), ("spire", 0.12), ("eye", 0.03)], 1),
    "jungle": ("lumen", None, [("coral", 0.3), ("bulb", 0.2), ("canopy", 0.12)], 2),
    "swamp": ("bog", None, [("stalks", 0.3), ("bulb", 0.1)], 2),
    "taiga": ("frost", None, [("spire", 0.3), ("shard", 0.05)], 1),
    "tundra": ("ice", None, [("shard", 0.04), ("stalks", 0.03)], 1),
    "icesheet": ("ice", None, [("shard", 0.06)], 1), "drift": ("ice", None, [("rock", 0.05)], 2),
    "desert": ("dune", None, [("ribs", 0.02), ("shard", 0.015)], 2),
    "salt": ("salt", None, [("shard", 0.06)], 2),
    "badlands": ("rust", None, [("ribs", 0.04), ("spire", 0.04)], 2),
    "hills": ("moss", None, [("rock", 0.12), ("stalks", 0.08)], 2),
    "mountain": ("stone", None, [("rock", 0.75)], 1), "peak": ("stone", "ice", [("peak", 0.6), ("rock", 0.3)], 1),
    "ash": ("ash", "lava", [("ribs", 0.04), ("spire", 0.04), ("rock", 0.05)], 2),
    "crust": ("ash", "lava", [], 1), "volcano": ("ash", "lava", [("cone", 1.0)], 1),
    "fungal": ("spore", None, [("shroom", 0.28), ("orbs", 0.12)], 2),
    "crystal": ("prism", None, [("shard", 0.38)], 2),
    "beach": ("salt", None, [("stalks", 0.02)], 1),
    "road": ("brick", None, [], 3), "plaza": ("brick", None, [], 3), "house": ("brick", "eye", [("hut", 1.0)], 0),
}
WATER = {"deep": 0, "ocean": 1, "shallow": 2, "lake": 2, "river": 2}

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


def paint(p, sp, x, y, b, r, local=True, defer=None):
    """b = biome code, r = per-cell random numbers (0..1). With a defer list, big sprites are queued
    there (x, y, sprite, colours, dx) to be drawn with p.big() after all the ground is down."""
    """b = biome code, r = per-cell random numbers (0..1)"""
    rr = lambda i: float(r[i % len(r)])
    pk = lambda i, n: int(rr(i) * n) % n
    pos = lambda i: (pk(i, TS - 3), pk(i + 1, TS - 3))
    if b in WATER:
        depth = WATER[b]
        p.fill(x, y, F("sea", 0) if depth < 2 else F("sea", 1))
        for k in range(1 + (depth > 0)):
            px, py = pos(k * 2)
            st = MARKS[7] if k == 0 else MARKS[1]
            p.stamp(x, y, st, F("sea", [3, 5, 6][depth] - k), px, py)
        return
    if b == "seaice":
        p.fill(x, y, F("ice", 1)); p.stamp(x, y, MARKS[8], F("ice", 5), *pos(0)); p.stamp(x, y, MARKS[0], F("ice", 7), *pos(2)); return
    if b == "lava":
        p.fill(x, y, F("lava", 1))
        for k in range(3):
            p.stamp(x, y, MARKS[[7, 2, 1][k]], F("lava", 4 + k), *pos(k * 2))
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
        return
    for k in range(2 * marks + (2 if marks else 0)):       # fine specks: more of them, each smaller
        p.stamp(x, y, MARKS[pk(k + 9, len(MARKS))], F(fam, 2 + pk(k + 3, 3)), *pos(k * 2))
    roll = rr(5)
    for kind, dens in kinds:
        dens = 1.0 if not local else dens * 0.32
        if roll < dens:
            m = {"1": F(fam, 4), "2": F(fam, 2), "3": F(acc, 5) if acc else F(fam, 5)}
            if local and defer is not None and kind in BIG:
                defer.append((x, y, sp.get(b, kind, pk(6, 8), big=True), m, pk(7, 9) - 4))
                return
            spr = sp.get(b, kind, pk(6, 8))
            dx = (pk(7, 5) - 2) if local else 0
            if local:
                p.shadow(x, y, spr, dx)
            p.sprite(x, y, spr, m, dx=dx)
            return
        roll -= dens


def pick_big(sp, b, r):
    """the big sprite (tree/hut/peak) this cell grows, if any: (sprite, colours, dx) or None.
    Same rolls as paint(), so a zone can draw its neighbours' trees that lean over the border."""
    if b in WATER or b in ("seaice", "lava", "bridge", "crust"):
        return None
    fam, acc, kinds, marks = BIOMES.get(b, ("stone", None, [], 1))
    rr = lambda i: float(r[i % len(r)])
    pk = lambda i, n: int(rr(i) * n) % n
    roll = rr(5)
    for kind, dens in kinds:
        dens = dens * 0.32
        if roll < dens:
            if kind not in BIG:
                return None
            m = {"1": F(fam, 4), "2": F(fam, 2), "3": F(acc, 5) if acc else F(fam, 5)}
            return sp.get(b, kind, pk(6, 8), big=True), m, pk(7, 9) - 4
        roll -= dens
    return None


def to_rgb(img8, t=0.0):
    return palette(t)[img8]
