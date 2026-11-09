"""Real town buildings: walls, a door onto the street, windows, rooms and furniture, under a roof
that lifts off when you walk in.

Cell codes:
  hwall  house wall (blocks you and your sight)     hwin   window (blocks you, not your sight)
  hdoor  doorway (walk through)                     hfloor floor inside
  htile  stone-tiled floor (kitchens)               hrug   rug
Furniture cells start "f_" (see FURN) and are drawn by the game in a clean RimWorld-ish style.

Buildings never straddle two zones, so every zone makes exactly the same houses however it's generated.
"""
import math
import numpy as np

HOUSE = {"hwall", "hwin", "hdoor", "hfloor", "htile", "hrug"}
FLOORS = {"hfloor", "htile", "hrug"}
KEEP_OFF = {"road", "plaza", "bonfire", "bridge", "river", "lake", "shallow", "ocean", "deep", "lava",
            "mountain", "peak", "volcano", "seaice", "house"} | HOUSE

# Furniture, RimWorld-style, drawn by the game (rl.Game.furniture). Two-cell pieces have a part per cell.
FURN = {
    "f_bed0": ("bed", True), "f_bed1": ("bed", True),           # head (north) and foot
    "f_tab0": ("dining table", True), "f_tab1": ("dining table", True),   # west and east half
    "f_chair": ("chair", False), "f_arm": ("armchair", False),
    "f_end": ("end table", True), "f_dress": ("dresser", True), "f_lamp": ("standing lamp", True),
    "f_stove": ("stove", True), "f_shelf": ("shelf", True), "f_plant": ("potted plant", True),
    "f_crate": ("crate", True), "f_sink": ("washbasin", True),
}
FURN_BLOCK = {k for k, (_, blk) in FURN.items() if blk}


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
        return c in FLOORS or c == "hdoor" or (c.startswith("f_") and c not in FURN_BLOCK)

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
        if any(str(b[y, x]) not in FLOORS for (x, y) in cells):
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


def _edge(room, x, y):
    rx0, ry0, rx1, ry1 = room
    return x in (rx0, rx1) or y in (ry0, ry1)


def _furnish(H, rng, room, role, door_in):
    """fill one room. room = interior rect (x0, y0, x1, y1) inclusive"""
    rx0, ry0, rx1, ry1 = room
    cells = [(x, y) for y in range(ry0, ry1 + 1) for x in range(rx0, rx1 + 1)]
    near_door = lambda q: abs(q[0] - door_in[0]) + abs(q[1] - door_in[1]) <= 1
    corners = [(rx0, ry0), (rx1, ry0), (rx0, ry1), (rx1, ry1)]
    walls = [q for q in cells if _edge(room, *q) and q not in corners and not near_door(q)]
    rng.shuffle(corners)
    rng.shuffle(walls)

    def one(code, spots):
        for q in spots:
            if not near_door(q) and H.put({q: code}):
                return q
        return None

    if role in ("bed", "studio"):
        beds = 2 if role == "bed" and rx1 - rx0 >= 4 and rng.random() < 0.5 else 1
        xs = list(range(rx0, rx1 + 1))
        rng.shuffle(xs)
        made = 0
        for x in xs:                                            # beds: heads against the north wall
            if made >= beds:
                break
            if not near_door((x, ry0)) and not near_door((x, ry0 + 1)) and \
                    H.put({(x, ry0): "f_bed0", (x, ry0 + 1): "f_bed1"}):
                made += 1
                one("f_end", [(x + 1, ry0), (x - 1, ry0)])     # a bedside table
        one("f_dress", walls)
        one("f_lamp", corners)
        rw, rh = min(4, rx1 - rx0 - 1), min(3, ry1 - ry0 - 2)   # a rug in the middle of the floor
        if rw >= 2 and rh >= 2:
            ux = (rx0 + rx1 - rw + 1) // 2
            uy = max(ry0 + 2, (ry0 + ry1 - rh + 1) // 2 + 1)
            for y in range(uy, min(uy + rh, ry1 + 1)):
                for x in range(ux, ux + rw):
                    if str(H.b[y, x]) == "hfloor":
                        H.b[y, x] = "hrug"
    if role in ("living", "studio"):
        one("f_stove", [q for q in walls if q[1] == ry0] + walls)
        one("f_shelf", walls)
        if role == "living":
            one("f_sink", walls)
        # a table in the open with chairs at its ends
        open_ = [(x, y) for (x, y) in cells if rx0 + 1 <= x <= rx1 - 2 and ry0 + 1 <= y <= ry1 - 1]
        rng.shuffle(open_)
        for (x, y) in open_:
            if H.put({(x, y): "f_tab0", (x + 1, y): "f_tab1"}):
                one("f_chair", [(x - 1, y)])
                one("f_chair", [(x + 2, y)])
                if rng.random() < 0.6:
                    one("f_chair", [(x, y + 1), (x + 1, y + 1)])
                break
        one("f_plant", corners)
        if role == "living" and rng.random() < 0.7:
            one("f_arm", corners + walls)
        if rng.random() < 0.5:
            one("f_crate", corners + walls)


def stamp(b, rng, x0, y0, w, h, door_side):
    """build a house in cells x0..x0+w-1, y0..y0+h-1. door_side: 'n', 's', 'w' or 'e' (towards the street)"""
    b[y0:y0 + h, x0:x0 + w] = "hwall"
    b[y0 + 1:y0 + h - 1, x0 + 1:x0 + w - 1] = "hfloor"
    walls = []                                                 # outer wall cells, not corners
    for x in range(x0 + 1, x0 + w - 1):
        walls += [(x, y0, "n"), (x, y0 + h - 1, "s")]
    for y in range(y0 + 1, y0 + h - 1):
        walls += [(x0, y, "w"), (x0 + w - 1, y, "e")]
    side = [q for q in walls if q[2] == door_side]
    dx, dy, _ = side[len(side) // 2 + int(rng.integers(-1, 2)) if len(side) > 2 else len(side) // 2]
    b[dy, dx] = "hdoor"
    door_in = {"n": (dx, dy + 1), "s": (dx, dy - 1), "w": (dx + 1, dy), "e": (dx - 1, dy)}[door_side]
    ix0, iy0, ix1, iy1 = x0 + 1, y0 + 1, x0 + w - 2, y0 + h - 2
    rooms = [((ix0, iy0, ix1, iy1), "studio")]
    split = None
    if ix1 - ix0 + 1 >= 7:                                     # wide: a wall down the middle, two rooms
        sx = (ix0 + ix1) // 2 + int(rng.integers(-1, 2))
        if abs(sx - door_in[0]) > 1:
            gy = int(rng.integers(iy0, iy1 + 1))
            b[iy0:iy1 + 1, sx] = "hwall"
            b[gy, sx] = "hdoor"
            split = (sx, None)
            left, right = (ix0, iy0, sx - 1, iy1), (sx + 1, iy0, ix1, iy1)
            front = left if door_in[0] < sx else right
            rooms = [(front, "living"), (right if front is left else left, "bed")]
    elif iy1 - iy0 + 1 >= 6:                                   # deep: a wall across, two rooms
        sy = (iy0 + iy1) // 2 + int(rng.integers(0, 2))
        if abs(sy - door_in[1]) > 1:
            gx = int(rng.integers(ix0, ix1 + 1))
            b[sy, ix0:ix1 + 1] = "hwall"
            b[sy, gx] = "hdoor"
            split = (None, sy)
            top, bot = (ix0, iy0, ix1, sy - 1), (ix0, sy + 1, ix1, iy1)
            front = top if door_in[1] < sy else bot
            rooms = [(front, "living"), (bot if front is top else top, "bed")]
    for (x, y, s) in walls:                                    # windows here and there
        if abs(x - dx) + abs(y - dy) > 1 and b[y, x] == "hwall" and rng.random() < 0.3:
            if split is None or (x != split[0] and y != split[1]):
                b[y, x] = "hwin"
    for (room, role) in rooms:                                 # kitchens get stone tiles
        if role == "living" and rng.random() < 0.6:
            rx0, ry0, rx1, ry1 = room
            b[ry0:ry1 + 1, rx0:rx1 + 1] = "htile"
    H = _House(b, door_in)
    for room, role in rooms:
        _furnish(H, rng, room, role, door_in)


def town(b, ok, rng, lx, ly, pr, reach, angles, zw, zh, gx0, gy0, ZS):
    """houses along the lanes out of a town square, and a few tucked in between"""
    taken = np.zeros(b.shape, bool)

    def try_house(cx, cy, w, h, door_side):
        x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
        if _fits(b, ok, taken, x0, y0, w, h, zw, zh, gx0, gy0, ZS):
            stamp(b, rng, x0, y0, w, h, door_side)
            taken[y0:y0 + h, x0:x0 + w] = True

    for a in angles:
        ca, sa = math.cos(a), math.sin(a)
        t = pr + 2.5
        while t < reach - 1:
            for side in (-1, 1):
                w, h = int(rng.integers(7, 12)), int(rng.integers(6, 9))
                keep = rng.random() < 0.8
                px, py = -sa * side, ca * side                 # away from the lane, on this side
                ext = abs(px) * w / 2 + abs(py) * h / 2
                cx, cy = lx + ca * t + px * (2.3 + ext), ly + sa * t + py * (2.3 + ext)
                if abs(px) > abs(py):
                    door = "w" if px > 0 else "e"
                else:
                    door = "n" if py > 0 else "s"
                if keep:
                    try_house(cx, cy, w, h, door)
            t += rng.uniform(5.0, 7.5)
    for _ in range(16):                                        # small ones tucked in between
        a, r = rng.uniform(0, 6.28), rng.uniform(pr + 2, reach)
        w, h = int(rng.integers(6, 8)), int(rng.integers(5, 7))
        door = ["n", "s", "w", "e"][int(rng.integers(4))]
        try_house(lx + math.cos(a) * r, ly + math.sin(a) * r, w, h, door)


def find(codes, ox=0, oy=0):
    """the houses in a zone's cells, as (x0, y0, x1, y1) inclusive rects in world cells.
    A house's walls (with its door and windows) are one closed ring, so they give its outline;
    floors and furniture are inside it."""
    h, w = codes.shape
    is_house = np.isin(codes, ["hwall", "hwin", "hdoor"])
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
