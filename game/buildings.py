"""Town houses: real 1970s Essex house types, open to the sky (no roofs) so you can see in.

The plans follow what Essex estates actually built in the 70s (and the 1973 Essex Design Guide's push away from plain
boxes): L-plan and T-plan bungalows, semi-detached pairs with integral garages at the ends, short staggered terraces,
link-detached houses with a garage, and a U-shaped courtyard bungalow. Each plan is turned (and maybe mirrored) so
its front door faces the street, then furnished room by room in a 70s way: orange and brown carpets, lino kitchens,
avocado bathroom suites, a telly in the lounge.

Cell codes:
  hwall wall   hwin window   hdoor doorway   gdoor up-and-over garage door (open)
  floors: hfloor hall boards   hcarpet lounge carpet   hcarpetb bedroom carpet   hlino kitchen lino
          hbath bathroom tiles   hconc garage concrete   (htile / hrug from older saves still work)
Furniture cells start "f_" (see FURN) and are drawn by the game.
Houses never straddle two zones, so every zone makes exactly the same houses however it's generated.
"""
import math
import numpy as np

FLOORS = {"hfloor", "htile", "hrug", "hcarpet", "hcarpetb", "hlino", "hbath", "hconc"}
DOORS = {"hdoor", "gdoor"}
HOUSE = {"hwall", "hwin"} | DOORS | FLOORS
KEEP_OFF = {"road", "street", "plaza", "bonfire", "bridge", "river", "lake", "shallow", "ocean", "deep", "lava",
            "mountain", "peak", "volcano", "seaice", "house"} | HOUSE

# Furniture, drawn by the game (rl.Game.furn_sprite). Two-cell pieces have a part per cell.
FURN = {
    "f_bed0": ("bed", True), "f_bed1": ("bed", True),                 # head (north) and foot
    "f_tab0": ("dining table", True), "f_tab1": ("dining table", True),
    "f_sofa0": ("sofa", True), "f_sofa1": ("sofa", True),             # back against the wall to the north
    "f_bath0": ("bath", True), "f_bath1": ("bath", True),
    "f_chair": ("chair", False), "f_arm": ("armchair", False),
    "f_end": ("bedside table", True), "f_dress": ("dresser", True), "f_ward": ("wardrobe", True),
    "f_lamp": ("standard lamp", True), "f_stove": ("cooker", True), "f_shelf": ("cupboard", True),
    "f_fridge": ("fridge", True), "f_sink": ("sink", True), "f_wc": ("toilet", True),
    "f_tv": ("television", True), "f_ctable": ("coffee table", True), "f_plant": ("rubber plant", True),
    "f_crate": ("box", True), "f_bench": ("workbench", True), "f_barrel": ("oil drum", True),
}
FURN_BLOCK = {k for k, (_, blk) in FURN.items() if blk}

ROOM_FLOOR = {"h": "hfloor", "l": "hcarpet", "d": "hcarpet", "b": "hcarpetb", "k": "hlino", "w": "hbath", "g": "hconc"}
HABITABLE = set("hldbkw")

# ── the plans. Rooms are wall-inclusive rects (room, x0, y0, x1, y1) that share their walls; doors (x, y, kind):
#    D front door, B back door, + inside door, G garage door. The front faces south (down) here.
PLANS = {
    "L-plan bungalow": (
        [("b", 0, 0, 6, 5), ("b", 6, 0, 13, 5), ("h", 0, 5, 13, 7), ("w", 0, 7, 4, 10), ("k", 0, 10, 4, 14),
         ("l", 4, 7, 10, 14)],
        [(3, 5, "+"), (9, 5, "+"), (2, 7, "+"), (7, 7, "+"), (4, 12, "+"), (7, 14, "D"), (2, 14, "B")]),
    "T-plan chalet bungalow": (
        [("w", 0, 0, 5, 3), ("b", 0, 3, 5, 7), ("h", 5, 0, 9, 7), ("k", 9, 0, 15, 4), ("b", 9, 4, 15, 7),
         ("l", 3, 7, 11, 13)],
        [(5, 2, "+"), (5, 5, "+"), (9, 2, "+"), (9, 5, "+"), (7, 7, "+"), (7, 13, "D"), (12, 0, "B")]),
    "link-detached house": (
        [("k", 0, 0, 6, 5), ("d", 6, 0, 11, 5), ("l", 0, 5, 11, 11), ("g", 11, 3, 16, 11), ("b", 0, 11, 6, 14)],
        [(6, 3, "+"), (3, 5, "+"), (11, 8, "+"), (3, 11, "+"), (8, 11, "D"), (12, 11, "G"), (13, 11, "G"),
         (14, 11, "G"), (9, 0, "B")]),
    "courtyard bungalow": (
        [("b", 0, 0, 5, 6), ("l", 5, 0, 14, 6), ("k", 14, 0, 19, 6), ("b", 0, 6, 5, 12), ("w", 14, 6, 19, 9),
         ("b", 14, 9, 19, 12)],
        [(5, 3, "+"), (14, 3, "+"), (2, 6, "+"), (16, 6, "+"), (16, 9, "+"), (9, 6, "D"), (17, 0, "B")]),
}
SEMI = ([("g", 0, 0, 4, 10), ("k", 4, 0, 12, 5), ("h", 4, 5, 7, 10), ("l", 7, 5, 12, 10)],
        [(4, 2, "+"), (5, 5, "+"), (7, 8, "+"), (10, 5, "+"), (6, 10, "D"), (1, 10, "G"), (2, 10, "G"),
         (3, 10, "G"), (8, 0, "B")])
TERRACE = ([("k", 0, 0, 6, 4), ("l", 0, 4, 6, 10)], [(2, 4, "+"), (4, 10, "D"), (3, 0, "B")])
KINDS = list(PLANS) + ["semi-detached pair", "terrace"]


def _draw(g, rooms, doors, ox=0, oy=0, mirror_w=None):
    for (ch, x0, y0, x1, y1) in rooms:
        if mirror_w is not None:
            x0, x1 = mirror_w - x1, mirror_w - x0
        x0, x1, y0, y1 = x0 + ox, x1 + ox, y0 + oy, y1 + oy
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if x in (x0, x1) or y in (y0, y1):
                    if g.get((x, y), " ") not in "D+BG":
                        g[(x, y)] = "#"
                else:
                    g[(x, y)] = ch
    for (x, y, ch) in doors:
        g[((mirror_w - x) if mirror_w is not None else x) + ox, y + oy] = ch


def plan(kind):
    """the plan as a char grid (rows), front door to the south"""
    g = {}
    if kind == "semi-detached pair":
        _draw(g, *SEMI)
        _draw(g, *SEMI, ox=12, mirror_w=12)
    elif kind == "terrace":
        for i, dy in enumerate((0, 1, 0)):
            _draw(g, *TERRACE, ox=i * 6, oy=dy)
    else:
        _draw(g, *PLANS[kind])
    w, h = max(x for x, _ in g) + 1, max(y for _, y in g) + 1
    a = np.full((h, w), " ")
    for (x, y), c in g.items():
        a[y, x] = c
    return a


def _door_side(a):
    ys, xs = np.nonzero(a == "D")
    h, w = a.shape
    y, x = ys[0], xs[0]
    return {0: "n", h - 1: "s"}.get(y) or ("w" if x == 0 else "e")


def oriented(kind, door_side, mirror):
    """the plan turned so its (first) front door faces door_side"""
    a = plan(kind)
    if mirror:
        a = np.fliplr(a)
    for _ in range(4):
        if _door_side(a) == door_side:
            return a
        a = np.rot90(a)
    return a


def _fits(b, ok, taken, x0, y0, w, h, zw, zh, gx0, gy0, ZS):
    if x0 - 1 < 0 or y0 - 1 < 0 or x0 + w + 1 > zw or y0 + h + 1 > zh:
        return False
    if (gx0 + x0 - 1) // ZS != (gx0 + x0 + w) // ZS or (gy0 + y0 - 1) // ZS != (gy0 + y0 + h) // ZS:
        return False                                           # would cross into the next zone
    foot = b[y0:y0 + h, x0:x0 + w]
    ring = b[y0 - 1:y0 + h + 1, x0 - 1:x0 + w + 1]
    return bool(ok[y0 - 1:y0 + h + 1, x0 - 1:x0 + w + 1].all()            # dry land all round
                and not taken[y0 - 1:y0 + h + 1, x0 - 1:x0 + w + 1].any()  # at least a step from other houses
                and not np.isin(foot, list(KEEP_OFF)).any()                # not on a road, the square, ...
                and not np.isin(ring, list(HOUSE | {"bonfire", "bridge"})).any())


class _House:
    """a house being furnished: keeps everyone able to walk from the door to every free bit of floor"""

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
        """place {(x, y): code} if every cell is bare floor and nobody gets shut out; True if placed"""
        b = self.b
        if any(not (0 <= y < b.shape[0] and 0 <= x < b.shape[1]) or str(b[y, x]) not in FLOORS for (x, y) in cells):
            return False
        before = {q: str(b[q[1], q[0]]) for q in cells}
        floor_before = len(self.connected())
        for (x, y), c in cells.items():
            b[y, x] = c
        blocked = sum(1 for c in cells.values() if c in FURN_BLOCK)
        if len(self.connected()) < floor_before - blocked:   # cut something off: take it back
            for (x, y), c in before.items():
                b[y, x] = c
            return False
        return True


def _furnish(H, rng, room, role):
    """fill one room (a set of floor cells) the way a 70s household would"""
    b = H.b
    wall = lambda x, y: str(b[y, x]) in ("hwall", "hwin")
    near_door = lambda x, y: any(str(b[y + dy, x + dx]) in DOORS for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    cells = [q for q in room if not near_door(*q)]
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

    def pair(c0, c1, spots, dx, dy, need_wall_north=False):
        for (x, y) in spots:
            if need_wall_north and not (wall(x, y - 1) and (dx == 0 or wall(x + dx, y - 1))):
                continue
            if (x + dx, y + dy) in room and not near_door(x + dx, y + dy) and H.put({(x, y): c0, (x + dx, y + dy): c1}):
                return (x, y)
        return None

    if role == "b":
        at = pair("f_bed0", "f_bed1", by_wall, 0, 1, need_wall_north=True)
        if at:
            one("f_end", [(at[0] + 1, at[1]), (at[0] - 1, at[1])])
            if len(room) >= 20 and rng.random() < 0.5:   # a double room might have a second bed
                pair("f_bed0", "f_bed1", by_wall, 0, 1, need_wall_north=True)
        one("f_ward", by_wall)
        if len(room) >= 16:
            one("f_dress", by_wall)
        if rng.random() < 0.5:
            one("f_lamp", corner)
    elif role == "l":                                   # the lounge: sofa, armchairs, telly, coffee table
        pair("f_sofa0", "f_sofa1", by_wall, 1, 0, need_wall_north=True)
        one("f_tv", by_wall)
        one("f_ctable", middle)
        one("f_arm", by_wall + middle)
        if rng.random() < 0.6:
            one("f_arm", by_wall + middle)
        one("f_lamp", corner)
        one("f_plant", corner)
        if rng.random() < 0.6:
            one("f_shelf", by_wall)
    elif role in ("k", "d"):                            # kitchen (and dining room)
        if role == "k":
            one("f_stove", by_wall)
            one("f_sink", by_wall)
            one("f_fridge", by_wall)
            one("f_shelf", by_wall)
            if rng.random() < 0.5:
                one("f_shelf", by_wall)
        spot = pair("f_tab0", "f_tab1", middle + cells, 1, 0)
        if spot:
            x, y = spot
            one("f_chair", [(x - 1, y)])
            one("f_chair", [(x + 2, y)])
            if rng.random() < 0.7:
                one("f_chair", [(x, y + 1), (x + 1, y + 1), (x, y - 1)])
        if role == "d":
            one("f_shelf", by_wall)
            one("f_plant", corner)
    elif role == "w":                                   # bathroom: avocado suite
        pair("f_bath0", "f_bath1", by_wall, 0, 1, need_wall_north=True)
        one("f_wc", by_wall)
        one("f_sink", by_wall)
    elif role == "g":                                   # garage: workbench, shelves, boxes, an oil drum
        one("f_bench", by_wall)
        one("f_shelf", by_wall)
        for _ in range(int(rng.integers(1, 4))):
            one("f_crate", corner + by_wall)
        if rng.random() < 0.6:
            one("f_barrel", corner + by_wall)
    elif role == "h" and rng.random() < 0.5:
        one("f_plant", corner)


def stamp(b, rng, x0, y0, a):
    """press an oriented plan into the cells at (x0, y0), add windows, furnish it"""
    h, w = a.shape
    for j in range(h):
        for i in range(w):
            ch = a[j, i]
            if ch == " ":
                continue
            b[y0 + j, x0 + i] = {"#": "hwall", "D": "hdoor", "B": "hdoor", "+": "hdoor", "G": "gdoor"}.get(ch) \
                or ROOM_FLOOR[ch]
    get = lambda i, j: a[j, i] if 0 <= i < w and 0 <= j < h else " "
    for j in range(h):                                  # windows: outside walls of rooms people live in
        for i in range(w):
            if a[j, i] != "#":
                continue
            nb = [get(i + 1, j), get(i - 1, j), get(i, j + 1), get(i, j - 1)]
            room = [c for c in nb if c in HABITABLE]
            if " " not in nb or not room or any(c in "D+BG" for c in nb):
                continue
            straight = (get(i - 1, j) == "#" and get(i + 1, j) == "#") or (get(i, j - 1) == "#" and get(i, j + 1) == "#")
            if straight and rng.random() < (0.3 if room[0] == "w" else 0.5):
                b[y0 + j, x0 + i] = "hwin"
    ys, xs = np.nonzero(a == "D")                       # furnish, keeping every room reachable from the front door
    dy, dx = ys[0], xs[0]
    start = next((dx + ox, dy + oy) for ox, oy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                 if get(dx + ox, dy + oy) in ROOM_FLOOR)
    H = _House(b, (x0 + start[0], y0 + start[1]))
    seen = np.zeros(a.shape, bool)
    order = {"k": 0, "w": 1, "b": 2, "l": 3, "d": 4, "g": 5, "h": 6}
    rooms = []
    for j in range(h):
        for i in range(w):
            ch = a[j, i]
            if ch in ROOM_FLOOR and not seen[j, i]:
                cells, stack = set(), [(i, j)]
                seen[j, i] = True
                while stack:
                    ci, cj = stack.pop()
                    cells.add((x0 + ci, y0 + cj))
                    for ni, nj in ((ci + 1, cj), (ci - 1, cj), (ci, cj + 1), (ci, cj - 1)):
                        if get(ni, nj) == ch and not seen[nj, ni]:
                            seen[nj, ni] = True
                            stack.append((ni, nj))
                rooms.append((order[ch], ch, cells))
    for _, ch, cells in sorted(rooms, key=lambda r: r[0]):
        _furnish(H, rng, cells, ch)


def town(b, ok, rng, streets, zw, zh, gx0, gy0, ZS):
    """houses facing the streets (each with a front garden), and one at the end of each close.
    Every candidate house has its own random numbers, so whether one fits never changes the next."""
    taken = np.zeros(b.shape, bool)
    base = int(rng.integers(1 << 30))

    def try_house(cx, cy, a, r):
        h, w = a.shape
        if w + 2 > ZS or h + 2 > ZS:
            return False
        x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
        # slide it wholly inside the zone its centre is in (houses never straddle zones)
        zx0 = (gx0 + int(math.floor(cx))) // ZS * ZS - gx0
        zy0 = (gy0 + int(math.floor(cy))) // ZS * ZS - gy0
        x0 = min(max(x0, zx0 + 1), zx0 + ZS - 1 - w)
        y0 = min(max(y0, zy0 + 1), zy0 + ZS - 1 - h)
        if _fits(b, ok, taken, x0, y0, w, h, zw, zh, gx0, gy0, ZS):
            stamp(b, r, x0, y0, a)
            taken[y0:y0 + h, x0:x0 + w] = a != " "
            return True
        return False

    def facing(px, py):
        """door side for a house lying (px, py) from the street"""
        return ("w" if px > 0 else "e") if px else ("n" if py > 0 else "s")

    for si, (sx, sy, dx, dy, L, kind) in enumerate(streets):
        for side_i, side in enumerate((-1, 1)):
            px, py = -dy * side, dx * side                 # away from the street, on this side
            t, step = 3.0, 0
            while t < L - 2 and step < 12:
                r = np.random.default_rng([base, si, side_i, step])
                step += 1
                placed = None
                if r.random() < 0.92:
                    kinds = list(r.permutation(len(KINDS))[:4])   # if one type won't fit here, try others
                    for ki in kinds:
                        a = oriented(KINDS[int(ki)], facing(px, py), bool(r.random() < 0.5))
                        h, w = a.shape
                        along, depth = (w, h) if dx else (h, w)
                        setback = 2.0 + r.uniform(0, 1.5)      # front garden
                        off = 1.0 + (1 if (px > 0 or py > 0) else 0) + setback + depth / 2
                        cx = sx + 0.5 + dx * (t + along / 2) + px * off
                        cy = sy + 0.5 + dy * (t + along / 2) + py * off
                        if try_house(cx, cy, a, r):
                            placed = along
                            break
                t += placed + r.uniform(1.5, 3.0) if placed else 3.0
        if kind == "close":                                  # the house at the end of the close
            r = np.random.default_rng([base, si, 7])
            a = oriented(KINDS[int(r.integers(len(KINDS)))], facing(dx, dy), bool(r.random() < 0.5))
            h, w = a.shape
            depth = h if dy else w
            try_house(sx + 0.5 + dx * (L + 3.5 + depth / 2), sy + 0.5 + dy * (L + 3.5 + depth / 2), a, r)


def find(codes, ox=0, oy=0):
    """the houses in a zone's cells, as (x0, y0, x1, y1) inclusive rects in world cells.
    A house's walls (with its doors and windows) are joined up, so they give its outline;
    floors and furniture are inside it."""
    h, w = codes.shape
    is_house = np.isin(codes, ["hwall", "hwin", "hdoor", "gdoor"])
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
        out.append((ox + int(x0), oy + int(y0), ox + int(x1), oy + int(y1)))
    return out
