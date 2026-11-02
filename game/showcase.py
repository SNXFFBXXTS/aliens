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
MAPB = {"town": "grass", "volcanic": "ash", "pass": "hills", "coast": "seaice"}   # what the world map shows


def base_of(kind):
    return MAPB.get(kind, kind) if kind != "town" else "grass"


class ShowcaseWorld(rl.World):
    showcase = True
    always_day = True

    def __init__(self, seed=4242):
        super().__init__(seed)
        self.dir = os.path.join(rl.ROOT, f"showcase-z{CS}")
        shutil.rmtree(self.dir, ignore_errors=True)            # fresh every time
        os.makedirs(os.path.join(self.dir, "chunks"), exist_ok=True)
        self.visited = set()
        wd = self.wd
        wd.biome[:] = "deep"
        for k, (kind, _) in enumerate(ZONES):
            wd.biome[Y0, k] = MAPB.get(kind, kind)
        wd.towns = [(0, Y0)]
        wd.rlinks = []
        wd.dlinks = [((k, Y0), (k + 1, Y0)) for k in range(len(ZONES) - 1)]
        wd.ruins, wd.caves = [], []
        self.home = (0, Y0)

    def zone_note(self, cx, cy):
        if cy == Y0 and 0 <= cx < len(ZONES):
            return f"Showcase {cx + 1}/{len(ZONES)}: {ZONES[cx][1]}"
        return None

    def spawn_in(self, b, cx, cy):
        return []

    def generate(self, cx, cy):
        if cy != Y0 or not 0 <= cx < len(ZONES):
            return np.full((CS, CS), "deep", dtype="<U10")
        kind = ZONES[cx][0]
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
            b[j < 13] = "seaice"
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
        trail = np.abs(proto.fbm(X / 0.9, Y / 0.9, 3, 4302) - 0.5) < 0.0065
        b[trail & np.isin(b, ["grass", "meadow", "savanna", "forest", "jungle", "hills", "taiga", "tundra", "desert",
                              "badlands", "fungal", "swamp", "beach", "ash"])] = "trail"
        # soft borders: the edge of the zone before bleeds in
        if cx > 0:
            prev = base_of(ZONES[cx - 1][0])
            blend = (i < 7) & (n2 * 7 > i) & ~np.isin(b, ["river", "lake", "ocean", "shallow", "seaice"])
            b[blend] = prev
        # the road
        for x in range(CS):
            for y in (road_y[x],):
                c = b[y, x]
                b[y, x] = "bridge" if c in ("river", "lake", "shallow", "ocean") else "crust" if c == "lava" else "road"
        if kind == "town":
            self._town(b, i, j)
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
