"""Creatures: species made from the world seed (sprite, name, stats, temper), and how they act each turn.

Each biome gets 3 species (+ swimmers in water). They get tougher the further you are from the
start town ("tier"). Sprites are mirrored 16x16 grids: '1' body, '2' dark, '3' eyes/glow.
"""
import math, zlib
import numpy as np
import weird

T = 16
WATER = {"shallow", "lake", "river"}
NO_WALK = {"deep", "ocean", "mountain", "peak", "house", "lava"}

# name parts: per biome a few adjectives, per body plan some nouns
ADJ = {
    "grass": ["moss", "tuft", "seed", "green"], "meadow": ["bloom", "petal", "pollen", "pink"],
    "savanna": ["dust", "amber", "dry", "sun"], "forest": ["bark", "witch", "root", "hollow"],
    "jungle": ["lumen", "vine", "glow", "frond"], "swamp": ["bog", "mire", "rot", "slime"],
    "taiga": ["frost", "pine", "rime", "hoar"], "tundra": ["snow", "pale", "rime", "white"],
    "icesheet": ["ice", "glacier", "cold", "blue"], "drift": ["drift", "snow", "pale", "hush"],
    "desert": ["dune", "sand", "scorch", "sun"], "salt": ["salt", "brine", "white", "crust"],
    "badlands": ["rust", "red", "mesa", "scrap"], "hills": ["tor", "stone", "hill", "crag"],
    "ash": ["ash", "cinder", "soot", "ember"], "crust": ["ember", "magma", "cinder", "slag"],
    "fungal": ["spore", "mycel", "puff", "gill"], "crystal": ["prism", "glass", "shard", "gleam"],
    "beach": ["shell", "tide", "salt", "brine"], "road": ["road", "dust", "wayside", "drifter"],
    "plaza": ["alley", "gutter", "rooftop", "street"], "water": ["eel", "mere", "drowned", "deep"],
}
NOUN = {"legs": ["crawler", "tick", "skitter", "beetle", "strider"], "wings": ["moth", "wisp", "flitter", "gnat"],
        "blob": ["slug", "ooze", "blob", "lump"], "tall": ["stalker", "lurcher", "walker", "shambler"],
        "tentacle": ["maw", "grasper", "tendril", "squid"], "beast": ["hound", "boar", "lurk", "rat"],
        "fish": ["eel", "fin", "lurker", "gulper"]}
TEMPER = ["hostile", "hostile", "timid", "timid", "neutral", "neutral"]
COLOURS = ["blood", "eye", "bloom", "lumen", "ochre", "frost", "spore", "rust", "salt"]


def rng_for(*parts):
    return np.random.default_rng(zlib.crc32(":".join(map(str, parts)).encode()))


def make_sprite(rng, plan):
    c = np.full((T, T), ".")
    def put(x, y, ch):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < 8 and 0 <= y < T:
            c[y, x] = ch
    cy = {"tall": 7, "wings": 7, "blob": 11, "fish": 9}.get(plan, 9)
    rx, ry = rng.uniform(3, 6), rng.uniform(2, 4.5)
    if plan == "tall":
        rx, ry = rng.uniform(2.2, 3.5), rng.uniform(3.5, 5)
    for y in range(T):
        for x in range(8):
            d = ((x + 0.5 - 8) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 1 and rng.random() > 0.06:
                put(x, y, "1" if y < cy + ry * 0.4 else "2")
    if plan in ("legs", "beast", "tall"):                      # legs
        n = {"legs": rng.integers(2, 4), "beast": 2, "tall": 1}[plan]
        for k in range(n):
            lx = 8 - rx * (0.3 + 0.7 * (k + 1) / (n + 1))
            for i in range(rng.integers(2, 5) if plan != "tall" else 6):
                put(lx - i * (0.5 if plan == "legs" else 0.15), cy + ry * 0.7 + i, "2")
    if plan == "wings":
        for i in range(12):
            a = i / 11 * 2.2
            r = rng.uniform(4, 7)
            put(8 - rx * 0.6 - math.sin(a) * r, cy - 1 - math.cos(a) * r * 0.8, "1")
        for y in range(int(cy - 4), int(cy + 2)):
            for x in range(1, 5):
                if rng.random() < 0.35:
                    put(x, y, "2")
    if plan == "tentacle":
        for k in range(rng.integers(2, 4)):
            x0 = 8 - rx * rng.uniform(0.2, 0.9)
            for i in range(rng.integers(3, 6)):
                put(x0 + math.sin(i * 0.9 + k) * 0.8, cy + ry * 0.8 + i, "1")
    if plan == "fish":
        for i in range(4):
            put(8 - rx - i * 0.6, cy - i * 0.5, "2"); put(8 - rx - i * 0.6, cy + i * 0.5, "2")
    # extras
    if rng.random() < 0.5:                                     # horns / antennae
        hx = 8 - rx * rng.uniform(0.2, 0.6)
        for i in range(rng.integers(2, 4)):
            put(hx - i * 0.5, cy - ry - i, "1")
        put(hx - 1.5, cy - ry - 3, "3")
    if rng.random() < 0.35:                                    # spikes along the back
        for x in range(int(8 - rx), 8, 2):
            put(x, cy - ry * math.sqrt(max(0, 1 - ((x + 0.5 - 8) / rx) ** 2)) - 1, "2")
    # eyes
    ne = rng.integers(1, 4)
    for k in range(ne):
        ex = 8 - rng.uniform(0.6, rx * 0.8)
        ey = cy - ry * rng.uniform(0.0, 0.6)
        put(ex, ey, "3")
    c[:, 8:] = c[:, :8][:, ::-1]
    return c


class Species:
    def __init__(self, seed, biome, n):
        r = rng_for(seed, "mob", biome, n)
        self.biome = biome
        self.swims = biome == "water"
        plans = ["fish", "tentacle", "blob"] if self.swims else ["legs", "wings", "blob", "tall", "tentacle", "beast"]
        self.plan = plans[r.integers(len(plans))]
        self.sprite = make_sprite(r, self.plan)
        self.name = ADJ.get(biome, ["odd"])[r.integers(4)] + " " + NOUN[self.plan][r.integers(len(NOUN[self.plan]))]
        self.colour = COLOURS[r.integers(len(COLOURS))]
        self.temper = TEMPER[r.integers(len(TEMPER))]
        self.hp = int(r.integers(6, 15))
        self.atk = (int(r.integers(1, 4)), int(r.integers(3, 7)))
        self.defn = int(r.integers(0, 2))
        self.slow = r.random() < 0.3                              # moves every other turn
        self.sight = int(r.integers(5, 9))


class Bestiary:
    def __init__(self, seed):
        self.seed = seed
        self.cache = {}

    def species(self, biome, n):
        k = (biome, n)
        if k not in self.cache:
            self.cache[k] = Species(self.seed, biome, n)
        return self.cache[k]


class Mob:
    __slots__ = ("id", "biome", "n", "tier", "x", "y", "hp", "maxhp", "angry", "seen", "sp")

    def __init__(self, sp, n, tier, x, y, mid):
        self.id, self.biome, self.n, self.tier, self.x, self.y = mid, sp.biome, n, tier, x, y
        self.sp = sp
        self.maxhp = sp.hp + tier * 6
        self.hp = self.maxhp
        self.angry = sp.temper == "hostile"
        self.seen = False

    @property
    def name(self):
        return (["", "big ", "elder ", "dread ", "ancient "][min(self.tier, 4)]) + self.sp.name

    def dmg(self):
        lo, hi = self.sp.atk
        return lo + self.tier, hi + self.tier * 2

    def to_json(self):
        return {"id": self.id, "b": self.biome, "n": self.n, "t": self.tier, "x": self.x, "y": self.y, "hp": self.hp, "a": self.angry}

    @staticmethod
    def from_json(d, best):
        m = Mob(best.species(d["b"], d["n"]), d["n"], d["t"], d["x"], d["y"], d["id"])
        m.hp, m.angry = d["hp"], d["a"]
        return m


def spawn(best, cells, cx, cy, cs, tier, seed):
    """creatures that live in a chunk the first time it's made"""
    r = rng_for(seed, "spawn", cx, cy)
    out = []
    # most zones are quiet; further out they get busier
    want = r.choice([[0, 0, 0, 0, 1, 1, 2], [0, 0, 1, 1, 2, 2, 3], [0, 1, 1, 2, 2, 3, 4]][min(tier, 2)])
    if np.isin(cells, ["plaza", "house"]).any():
        want = 0                                   # nothing nasty wanders round town
    for k in range(int(want) * 6):
        if len(out) >= want:
            break
        x, y = int(r.integers(cs)), int(r.integers(cs))
        b = str(cells[y, x])
        if b in ("plaza", "house", "bridge") or b in NO_WALK:
            continue
        key = "water" if b in WATER else b
        n = int(r.integers(3))
        out.append(Mob(best.species(key, n), n, tier, cx * cs + x, cy * cs + y, f"{cx}.{cy}.{k}"))
    return out


def can_stand(mob, cell):
    if mob.sp.swims:
        return cell in WATER
    return cell not in NO_WALK and cell not in WATER and cell not in ("plaza", "bridge")


def step_towards(mob, tx, ty, cell_at, occupied, away=False):
    best, bd = None, None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if not dx and not dy:
                continue
            nx, ny = mob.x + dx, mob.y + dy
            if (nx, ny) in occupied or not can_stand(mob, cell_at(nx, ny)):
                continue
            d = (nx - tx) ** 2 + (ny - ty) ** 2
            if best is None or (d > bd if away else d < bd):
                best, bd = (nx, ny), d
    return best
