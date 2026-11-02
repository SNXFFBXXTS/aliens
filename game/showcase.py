"""Biome showcase: `rl --showcase`. A road runs east through 21 zones, one biome each, always daytime,
no creatures. Rebuilt fresh every launch (saved under ~/.local/share/roguelike/showcase-z40/)."""
import math, os, shutil
import numpy as np
import proto
import rl
from rl import CS

Y0 = 30
ZONES = [("town", "Town"), ("grass", "Grassland"), ("meadow", "Meadow (with a lake)"), ("savanna", "Savanna"),
         ("desert", "Desert"), ("salt", "Salt flats"), ("badlands", "Badlands"), ("ash", "Ash wastes"),
         ("volcanic", "Lava fields"), ("hills", "Hills"), ("pass", "Mountain pass"), ("taiga", "Snow forest"),
         ("tundra", "Tundra"), ("icesheet", "Ice sheet"), ("coast", "Frozen coast"), ("beach", "Beach"),
         ("swamp", "Swamp"), ("jungle", "Jungle"), ("forest", "Forest (with a river)"), ("fungal", "Fungal forest"),
         ("crystal", "Crystal fields")]
MAPB = {"town": "grass", "volcanic": "ash", "pass": "hills", "coast": "drift"}   # what the world map shows


def base_of(kind):
    return MAPB.get(kind, kind) if kind != "town" else "grass"


class ShowcaseWorld(rl.World):
    showcase = True
    always_day = True
    zones = ZONES
    dirname = "showcase"

    def __init__(self, seed=4242):
        super().__init__(seed)
        self.dir = os.path.join(rl.ROOT, f"{self.dirname}-z{CS}")
        shutil.rmtree(self.dir, ignore_errors=True)            # fresh every time
        os.makedirs(os.path.join(self.dir, "chunks"), exist_ok=True)
        self.visited = set()
        wd = self.wd
        wd.biome[:] = "deep"
        for k, (kind, _) in enumerate(self.zones):
            wd.biome[Y0, k] = MAPB.get(kind, kind)
        wd.towns = [(0, Y0)]
        wd.rlinks = []
        wd.dlinks = [((k, Y0), (k + 1, Y0)) for k in range(len(self.zones) - 1)]
        wd.ruins, wd.caves = [], []
        self.home = (0, Y0)

    def zone_note(self, cx, cy):
        if cy == Y0 and 0 <= cx < len(self.zones):
            return f"Showcase {cx + 1}/{len(self.zones)}: {self.zones[cx][1]}"
        return None

    def spawn_in(self, b, cx, cy):
        return []

    def density(self, cx, cy):
        """busy, barren, busy, barren..."""
        if self.dirname != "showcase" or cy != Y0:
            return 1.0
        return 2.6 if _busy(cx) else 0.08

    def culture_ruins(self, b, cx):
        """busy zones get two ruin sites from their region's culture, one each side of the road"""
        import structures, cultures
        base = base_of(self.zones[cx][0])
        cul = cultures.CULTURE.get(base)
        if not cul:
            return
        names = cultures.LAYOUTS[cul]
        r = np.random.default_rng(cx * 31 + 7)
        for k, near in enumerate(((13, 8), (27, 32))):
            structures.stamp(b, names[(cx + k) % len(names)], int(r.integers(4)), bool(r.random() < 0.5), r, CS, CS, near)

    def showcase_trails(self, cx):
        """a footpath wandering along beside the road, wiggling off into each zone"""
        out = []
        for k in (-1, 0, 1):
            x = cx + k
            if 0 <= x < len(self.zones):
                u = np.linspace(0, 1, 61)
                px = x + u
                py = Y0 + (31 + 4 * np.sin(px * 5.1) + 2 * np.sin(px * 13.7 + 1)) / CS
                out.append(np.stack([px, py], 1))
        return out

    def lines(self, cx, cy):
        if cy != Y0:
            return [], []
        xs = np.arange(cx * CS - 6, cx * CS + CS + 7)
        road = np.stack([(xs + 0.5) / CS, Y0 + (20 + np.round(2 * np.sin(xs / 9)) + 0.5) / CS], 1)
        # smooth the stair-steps of the cell road into a flowing line
        for _ in range(3):
            road[1:-1, 1] = 0.25 * road[:-2, 1] + 0.5 * road[1:-1, 1] + 0.25 * road[2:, 1]
        return [road], self.showcase_trails(cx)

    def generate(self, cx, cy):
        if cy != Y0 or not 0 <= cx < len(self.zones):
            return np.full((CS, CS), "deep", dtype="<U10")
        kind = self.zones[cx][0]
        j, i = np.mgrid[0:CS, 0:CS]
        X, Y = cx + (i + 0.5) / CS, Y0 + (j + 0.5) / CS
        n1 = proto.fbm(X * 3, Y * 3, 4, 77)
        n2 = proto.fbm(X * 7, Y * 7, 3, 78)
        lo, hi = np.percentile(n1, 3), np.percentile(n1, 97)
        n1 = (n1 - lo) / (hi - lo)
        b = np.full((CS, CS), base_of(kind), dtype="<U10")
        road_y = (20 + np.round(2 * np.sin((cx * CS + np.arange(CS)) / 9))).astype(int)
        near_road = np.abs(j - road_y[None, :]) <= 3
        if kind == "volcanic":
            ridge = np.abs(n1 - 0.5)
            b[ridge < 0.09] = "crust"
            b[ridge < 0.045] = "lava"
        elif kind == "pass":
            b[(n1 > 0.55) & ~near_road] = "mountain"
            b[(n1 > 0.72) & ~near_road] = "peak"
        elif kind == "coast":
            b[j < 13] = "seaice"  # (map shows it as drift so you can travel through)
            b[(j < 13) & (np.abs(n2 - 0.5) < 0.04)] = "shallow"
            b[(j >= 13) & (j < 17)] = "drift"
            b[j >= 17] = "tundra"
        elif kind == "beach":
            b[j < 10] = "ocean"
            b[(j >= 10) & (j < 14)] = "shallow"
            b[(j >= 14) & (j < 24)] = "beach"
        elif kind == "swamp":
            b[(n1 > 0.62) & ~near_road] = "lake"
        elif kind == "meadow":
            b[((i - 12) ** 2 + (j - 9) ** 2 * 1.6 < 40) & ~near_road] = "lake"
        elif kind == "forest":
            rx = 20 + np.round(2.5 * np.sin(j / 5)).astype(int)
            b[np.abs(i - rx) <= 1] = "river"
        elif kind == "icesheet":
            b[n2 > 0.66] = "drift"
        proto.mark_trails(b, cx, Y0, CS, CS, self.showcase_trails(cx))
        # gradual borders: the zones either side bleed in, in scattered patches that thin out towards the middle
        open_land = np.isin(b, proto.BLEND_LAND)
        score = proto.cell_rand(cx * CS + i, j, 991) * 0.55 + proto.fbm(X * 4, Y * 4, 2, 992) * 0.45
        if cx > 0:
            prev = base_of(self.zones[cx - 1][0])
            b[open_land & (score < np.clip((22 - i) / 44, 0, 1) * 0.95)] = prev
        if cx + 1 < len(self.zones):
            nxt = base_of(self.zones[cx + 1][0])
            b[open_land & (score > 1 - np.clip((i - 18) / 44, 0, 1) * 0.95)] = nxt
        # the road
        for x in range(CS):
            for y in (road_y[x],):
                c = b[y, x]
                b[y, x] = "bridge" if c in ("river", "lake", "shallow", "ocean") else "crust" if c == "lava" else "road"
        if kind == "town":
            self._town(b, i, j)
        elif self.dirname == "showcase" and _busy(cx):
            self.culture_ruins(b, cx)
        return b

    def _town(self, b, i, j):
        rng = np.random.default_rng(5)
        cx, cy = CS // 2, 20
        b[(i - cx) ** 2 + (j - cy) ** 2 < 5 ** 2] = "plaza"
        b[cy, cx] = "bonfire"
        for k in range(5):
            a = k * 6.28 / 5 + 0.3
            ca, sa = math.cos(a), math.sin(a)
            for t in np.arange(4, 17, 0.5):
                x, y = int(round(cx + ca * t)), int(round(cy + sa * t))
                if 0 <= x < CS and 0 <= y < CS:
                    b[y, x] = "road"
            for t in np.arange(6.5, 16, 2.2):
                for side in (-1, 1):
                    hx, hy = int(round(cx + ca * t - sa * side * 2)), int(round(cy + sa * t + ca * side * 2))
                    if 0 <= hx < CS and 0 <= hy < CS and b[hy, hx] not in ("road", "plaza") and rng.random() < 0.85:
                        b[hy, hx] = "house"


def _busy(k):
    return k % 2 == 0


class StructureShowcase(ShowcaseWorld):
    """`rl --structures`: a road past every kind of abandoned place, one per zone"""
    dirname = "structures"

    def __init__(self, seed=4243):
        import structures
        self.S = structures
        self.names = list(structures.L)
        pref = ["grass", "forest", "desert", "tundra", "hills", "meadow", "savanna", "jungle", "badlands", "beach", "swamp", "fungal"]
        zl = []
        for n in self.names:
            bs = structures.L[n]["biomes"]
            zl.append((next((b for b in pref if bs is None or b in bs), "grass" if bs is None else sorted(bs)[0]), n))
        self.zones = zl
        super().__init__(seed)

    def zone_note(self, cx, cy):
        if cy == Y0 and 0 <= cx < len(self.zones):
            d = self.S.L[self.zones[cx][1]]
            return f"{cx + 1}/{len(self.zones)}: {d['title'][0].upper() + d['title'][1:]}. {d['desc']}"
        return None

    def generate(self, cx, cy):
        b = super().generate(cx, cy)
        if cy == Y0 and 0 <= cx < len(self.zones):
            name = self.zones[cx][1]
            r = np.random.default_rng(cx)
            if self.S.L[name]["road"]:
                ys, xs = np.nonzero(b == "road")
                near = (int(xs[len(xs) // 2]), int(ys[len(ys) // 2]))
            else:
                near = (20, 13)
            self.S.stamp(b, name, 0, False, r, CS, CS, near)
        return b
