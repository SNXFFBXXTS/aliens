"""Shanty settlements: what the colonists built after the colony failed.

Shacks are hand-made from whatever was to hand: corrugated iron, scrap planks, tarp, plates cut from the ship's
hull, patched where it gave out. They have holes you can see through, some have caved in, some have a lean-to off
the side. Dirt or pallet floors. Inside: a mattress on the floor, an oil-drum stove, a crate for a table, a scrap
shelf, a bucket, rags, and sometimes a shrine to whatever they turned to.

Cell codes:
  walls  swall_iron  swall_wood  swall_tarp  swall_hull   (block you and your sight)
         sgap        a broken bit of wall (blocks you, not your sight)
  sdoor  doorway with a rag hanging in it        debris   caved-in wall, rubble you can climb over
  floors sdirt (packed dirt)  spallet (pallet boards)     mud   the trodden ground of the settlement
  (the old 70s-estate codes hwall/hwin/hdoor/gdoor/h* floors still load and draw, for old saves)
Furniture cells start "f_" (see FURN) and are drawn by the game.
Shacks never straddle two zones, so every zone makes the same ones however it's generated.
"""
import math
import numpy as np

S_WALLS = ("swall_iron", "swall_wood", "swall_tarp", "swall_hull")
WALLS = set(S_WALLS) | {"sgap", "hwall", "hwin"}
DOORS = {"sdoor", "hdoor", "gdoor"}
FLOORS = {"sdirt", "spallet", "debris", "hfloor", "htile", "hrug", "hcarpet", "hcarpetb", "hlino", "hbath", "hconc"}
HOUSE = WALLS | DOORS | FLOORS
KEEP_OFF = {"road", "street", "plaza", "bonfire", "bridge", "river", "lake", "shallow", "ocean", "deep", "lava",
            "mountain", "peak", "volcano", "seaice", "house", "mud"} | HOUSE

FURN = {
    # the shanty's things
    "f_matt0": ("mattress", False), "f_matt1": ("mattress", False),      # on the floor; head (north) and foot
    "f_drum": ("oil-drum stove", True), "f_crtab": ("crate table", True), "f_stool": ("stool", False),
    "f_sshelf": ("scrap shelf", True), "f_bucket": ("bucket", True), "f_rags": ("pile of rags", False),
    "f_shrine": ("shrine", True), "f_wbarrel": ("water barrel", True), "f_crate": ("crate", True),
    # older furniture (70s estates in old saves)
    "f_bed0": ("bed", True), "f_bed1": ("bed", True), "f_tab0": ("dining table", True), "f_tab1": ("dining table", True),
    "f_sofa0": ("sofa", True), "f_sofa1": ("sofa", True), "f_bath0": ("bath", True), "f_bath1": ("bath", True),
    "f_chair": ("chair", False), "f_arm": ("armchair", False), "f_end": ("bedside table", True),
    "f_dress": ("dresser", True), "f_ward": ("wardrobe", True), "f_lamp": ("standard lamp", True),
    "f_stove": ("cooker", True), "f_shelf": ("cupboard", True), "f_fridge": ("fridge", True), "f_sink": ("sink", True),
    "f_wc": ("toilet", True), "f_tv": ("television", True), "f_ctable": ("coffee table", True),
    "f_plant": ("rubber plant", True), "f_bench": ("workbench", True), "f_barrel": ("oil drum", True),
}
FURN_BLOCK = {k for k, (_, blk) in FURN.items() if blk}


def _material(rng):
    return S_WALLS[int(rng.choice(4, p=[0.38, 0.36, 0.14, 0.12]))]


def shack(rng):
    """one shack as a grid of cell codes ("" = outside), its front door on the south side"""
    w, h = int(rng.integers(5, 9)), int(rng.integers(4, 7))
    lean = rng.random() < 0.5
    side = ("w" if rng.random() < 0.5 else "e") if lean else None
    W = w + (2 if lean else 0)
    g = np.full((h, W), "", dtype=object)
    mx = 2 if side == "w" else 0                                  # where the main shack starts
    mats = {s: _material(rng) for s in "nsew"}                    # each side built from one thing, then patched
    for y in range(h):
        for x in range(w):
            if x in (0, w - 1) or y in (0, h - 1):
                s_ = "n" if y == 0 else "s" if y == h - 1 else "w" if x == 0 else "e"
                g[y, mx + x] = mats[s_] if rng.random() > 0.22 else _material(rng)
            else:
                g[y, mx + x] = "sdirt"
    if rng.random() < 0.4:                                        # some laid pallets down
        for y, x in zip(*np.nonzero(g == "sdirt")):
            if rng.random() < 0.75:
                g[y, x] = "spallet"
    if lean:                                                      # lean-to: a covered strip along one side
        ly0 = int(rng.integers(0, max(1, h - 3)))
        ly1 = min(h - 1, ly0 + int(rng.integers(3, h + 1)))
        ox = 0 if side == "w" else mx + w                         # its outer wall column and its floor column
        fx = 1 if side == "w" else mx + w
        wx = 0 if side == "w" else mx + w + 1
        for y in range(ly0, ly1 + 1):
            end = y in (ly0, ly1)
            g[y, wx] = "swall_tarp" if rng.random() < 0.6 else "swall_wood"
            g[y, fx] = ("swall_tarp" if rng.random() < 0.5 else "swall_wood") if end else "sdirt"
        if ly1 < h - 1 or ly0 > 0:                                # one end left open to the weather
            g[ly1, fx] = "sdirt"
        inner = mx if side == "w" else mx + w - 1                 # a way through from the shack
        gy = int(rng.integers(max(1, ly0 + 1), max(2, min(h - 1, ly1))))
        if 0 < gy < h - 1:
            g[gy, inner] = "sdoor"
    g[h - 1, mx + int(rng.integers(1, w - 1))] = "sdoor"          # the front door, on the south wall
    hh, ww = g.shape
    for y in range(hh):                                           # holes you can see through
        for x in range(ww):
            if g[y, x] in S_WALLS:
                corner = sum(1 for ox_, oy_ in ((1, 0), (-1, 0)) if 0 <= x + ox_ < ww and g[y, x + ox_] in WALLS) and \
                    sum(1 for ox_, oy_ in ((0, 1), (0, -1)) if 0 <= y + oy_ < hh and g[y + oy_, x] in WALLS)
                near_door = any(0 <= y + oy_ < hh and 0 <= x + ox_ < ww and g[y + oy_, x + ox_] == "sdoor"
                                for ox_, oy_ in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if not corner and not near_door and rng.random() < 0.1:
                    g[y, x] = "sgap"
    if rng.random() < 0.3:                                        # a stretch of wall caved in
        x0 = mx + int(rng.integers(1, max(2, w - 2)))
        for x in (x0, x0 + 1):
            if g[0, x] in WALLS:
                g[0, x] = "debris"
    return g


def _door_side(g):
    h, w = g.shape
    for y, x in zip(*np.nonzero(g == "sdoor")):
        if y == h - 1:
            return "s"
        if y == 0:
            return "n"
        if x == 0:
            return "w"
        if x == w - 1:
            return "e"
    return "s"


def oriented(g, door_side):
    """turn a shack so its front door faces door_side"""
    for _ in range(4):
        if _door_side(g) == door_side:
            return g
        g = np.rot90(g)
    return g


def _fits(b, ok, taken, x0, y0, g, zw, zh, gx0, gy0, ZS):
    h, w = g.shape
    if x0 - 1 < 0 or y0 - 1 < 0 or x0 + w + 1 > zw or y0 + h + 1 > zh:
        return False
    if (gx0 + x0 - 1) // ZS != (gx0 + x0 + w) // ZS or (gy0 + y0 - 1) // ZS != (gy0 + y0 + h) // ZS:
        return False                                           # would cross into the next zone
    foot = b[y0:y0 + h, x0:x0 + w][g != ""]
    return bool(ok[y0 - 1:y0 + h + 1, x0 - 1:x0 + w + 1].all()
                and not taken[y0 - 1:y0 + h + 1, x0 - 1:x0 + w + 1].any()
                and not np.isin(foot, list(KEEP_OFF)).any())


class _House:
    """a building being furnished: keeps everyone able to walk from the door to every free bit of floor"""

    def __init__(self, b, start):
        self.b, self.start = b, start

    def walkable(self, x, y):
        c = str(self.b[y, x])
        return c in FLOORS or c in DOORS or (c.startswith("f_") and c not in FURN_BLOCK)

    def connected(self):
        b = self.b
        seen, stack = {self.start}, [self.start]
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in seen and 0 <= ny < b.shape[0] and 0 <= nx < b.shape[1] and self.walkable(nx, ny):
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        return seen

    def put(self, cells):
        b = self.b
        if any(not (0 <= y < b.shape[0] and 0 <= x < b.shape[1]) or str(b[y, x]) not in ("sdirt", "spallet")
               for (x, y) in cells):
            return False
        before = {q: str(b[q[1], q[0]]) for q in cells}
        floor_before = len(self.connected())
        for (x, y), c in cells.items():
            b[y, x] = c
        blocked = sum(1 for c in cells.values() if c in FURN_BLOCK)
        if len(self.connected()) < floor_before - blocked:   # shut something off: take it back
            for (x, y), c in before.items():
                b[y, x] = c
            return False
        return True


def _furnish(H, rng, cells):
    """what someone living in a shack would have"""
    b = H.b
    wall = lambda x, y: str(b[y, x]) in WALLS
    near_door = lambda x, y: any(str(b[y + dy, x + dx]) in DOORS for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    cells = [q for q in cells if not near_door(*q)]
    rng.shuffle(cells)
    by_wall = [q for q in cells if any(wall(q[0] + dx, q[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    corner = [q for q in by_wall if (wall(q[0] - 1, q[1]) or wall(q[0] + 1, q[1])) and
              (wall(q[0], q[1] - 1) or wall(q[0], q[1] + 1))]
    middle = [q for q in cells if q not in by_wall]

    def one(code, spots):
        for q in spots:
            if H.put({q: code}):
                return q
        return None

    for (x, y) in by_wall:                                      # a mattress on the floor, head to a wall
        if wall(x, y - 1) and (x, y + 1) in cells and H.put({(x, y): "f_matt0", (x, y + 1): "f_matt1"}):
            break
    one("f_drum", corner)
    at = one("f_crtab", middle + by_wall)
    if at:
        one("f_stool", [(at[0] + 1, at[1]), (at[0] - 1, at[1]), (at[0], at[1] + 1)])
    if rng.random() < 0.7:
        one("f_sshelf", by_wall)
    if rng.random() < 0.6:
        one("f_bucket", corner + by_wall)
    if rng.random() < 0.5:
        one("f_rags", cells)
    if rng.random() < 0.35:
        one("f_wbarrel", corner + by_wall)
    if rng.random() < 0.4:
        one("f_crate", corner + by_wall)
    if rng.random() < 0.25:                                     # what they turned to
        one("f_shrine", by_wall)


def stamp(b, rng, x0, y0, g):
    h, w = g.shape
    for j in range(h):
        for i in range(w):
            if g[j, i]:
                b[y0 + j, x0 + i] = g[j, i]
    start = None
    for y, x in zip(*np.nonzero(g == "sdoor")):                 # just inside a door
        for ox, oy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            if 0 <= y + oy < h and 0 <= x + ox < w and g[y + oy, x + ox] in ("sdirt", "spallet"):
                start = (x0 + x + ox, y0 + y + oy)
                break
        if start:
            break
    if start:
        floor = [(x0 + i, y0 + j) for j in range(h) for i in range(w) if g[j, i] in ("sdirt", "spallet")]
        _furnish(_House(b, start), rng, floor)


def settlement(b, ok, rng, lx, ly, zw, zh, gx0, gy0, ZS):
    """shacks scattered round a muddy clearing with a fire, mostly facing in. Returns their front doors (local cells)."""
    taken = np.zeros(b.shape, bool)
    base = int(rng.integers(1 << 30))
    doors = []
    for k in range(40):
        r = np.random.default_rng([base, k])                    # every shack has its own dice
        ang, dist = r.uniform(0, 2 * math.pi), r.uniform(7, 30)
        cx, cy = lx + math.cos(ang) * dist, ly + math.sin(ang) * dist
        tx, ty = lx - cx, ly - cy                               # door faces back toward the fire, mostly
        if r.random() < 0.25:
            tx, ty = -ty, tx
        door = ("e" if tx > 0 else "w") if abs(tx) > abs(ty) else ("s" if ty > 0 else "n")
        g = oriented(shack(r), door)
        h, w = g.shape
        x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
        zx0 = (gx0 + int(math.floor(cx))) // ZS * ZS - gx0    # wholly inside the zone its middle is in
        zy0 = (gy0 + int(math.floor(cy))) // ZS * ZS - gy0
        x0 = min(max(x0, zx0 + 1), zx0 + ZS - 1 - w)
        y0 = min(max(y0, zy0 + 1), zy0 + ZS - 1 - h)
        if _fits(b, ok, taken, x0, y0, g, zw, zh, gx0, gy0, ZS):
            stamp(b, r, x0, y0, g)
            taken[y0:y0 + h, x0:x0 + w] = g != ""
            for y, x in zip(*np.nonzero(g == "sdoor")):
                if y in (0, h - 1) or x in (0, w - 1):
                    doors.append((x0 + x, y0 + y, door))
                    break
    return doors


def find(codes, ox=0, oy=0):
    """the buildings in a zone's cells, as (x0, y0, x1, y1) inclusive rects in world cells (found by their walls)"""
    h, w = codes.shape
    is_house = np.isin(codes, list(WALLS | DOORS | {"debris"}))
    seen = np.zeros((h, w), bool)
    out = []
    for y, x in zip(*np.nonzero(is_house)):
        if seen[y, x]:
            continue
        stack, x0, y0, x1, y1 = [(x, y)], x, y, x, y
        seen[y, x] = True
        while stack:
            cx, cy = stack.pop()
            x0, y0, x1, y1 = min(x0, cx), min(y0, cy), max(x1, cx), max(y1, cy)
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 0 <= nx < w and 0 <= ny < h and is_house[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((nx, ny))
        if x1 - x0 >= 2 and y1 - y0 >= 2:
            out.append((ox + int(x0), oy + int(y0), ox + int(x1), oy + int(y1)))
    return out
