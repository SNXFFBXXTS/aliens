"""Real town buildings: walls, a door onto the street, windows, rooms and furniture, under a roof
that lifts off when you walk in.

Cell codes:
  hwall  house wall (blocks you and your sight)     hwin   window (blocks you, not your sight)
  hdoor  doorway (walk through)                     hfloor floor inside
Furniture uses the ordinary prop codes (p_bed, p_table, ...).

Buildings never straddle two zones, so every zone makes exactly the same houses however it's generated.
"""
import math
import numpy as np

HOUSE = {"hwall", "hwin", "hdoor", "hfloor"}
KEEP_OFF = {"road", "plaza", "bonfire", "bridge", "river", "lake", "shallow", "ocean", "deep", "lava",
            "mountain", "peak", "volcano", "seaice", "house"} | HOUSE
FURNITURE = ["bed", "table", "crate", "barrel", "bench", "rack"]


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
    keep_clear = {(dx, dy)}
    # bigger houses get a second room
    split = None
    if w >= 7 and rng.random() < 0.8:
        sx = x0 + w // 2 + int(rng.integers(-1, 1))
        if sx not in (dx - 1, dx, dx + 1):
            b[y0 + 1:y0 + h - 1, sx] = "hwall"
            gy = int(rng.integers(y0 + 1, y0 + h - 1))
            b[gy, sx] = "hfloor"
            split = (sx, gy)
            keep_clear |= {(sx, gy), (sx - 1, gy), (sx + 1, gy)}
    for (x, y, s) in walls:                                    # windows here and there
        if (x, y) != (dx, dy) and abs(x - dx) + abs(y - dy) > 1 and b[y, x] == "hwall" and rng.random() < 0.3:
            if split is None or x != split[0]:
                b[y, x] = "hwin"
    # inside the door: keep a step clear
    ins = {"n": (dx, dy + 1), "s": (dx, dy - 1), "w": (dx + 1, dy), "e": (dx - 1, dy)}[door_side]
    keep_clear.add(ins)
    # furniture, mostly against the walls
    spots = [(x, y) for y in range(y0 + 1, y0 + h - 1) for x in range(x0 + 1, x0 + w - 1)
             if b[y, x] == "hfloor" and (x, y) not in keep_clear]
    against = [q for q in spots if q[0] in (x0 + 1, x0 + w - 2) or q[1] in (y0 + 1, y0 + h - 2)
               or (split and abs(q[0] - split[0]) == 1)]
    rng.shuffle(against)
    n = min(len(against), 2 + int(rng.integers(0, 3)) + (1 if split else 0))
    placed = 0
    for (x, y) in against:
        if placed >= n:
            break
        # never box anyone in: furniture can't touch other furniture or the door's inside step
        if any(str(b[y + oy, x + ox]).startswith("p_") for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            continue
        b[y, x] = "p_" + ("bed" if placed == 0 else FURNITURE[int(rng.integers(1, len(FURNITURE)))])
        placed += 1


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
                w, h = int(rng.integers(5, 9)), int(rng.integers(4, 7))
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
            t += rng.uniform(4.0, 6.0)
    for _ in range(16):                                        # small ones tucked in between
        a, r = rng.uniform(0, 6.28), rng.uniform(pr + 2, reach)
        w, h = int(rng.integers(4, 6)), int(rng.integers(4, 6))
        door = ["n", "s", "w", "e"][int(rng.integers(4))]
        try_house(lx + math.cos(a) * r, ly + math.sin(a) * r, w, h, door)


def find(codes, ox=0, oy=0):
    """the houses in a zone's cells, as (x0, y0, x1, y1) inclusive rects in world cells.
    A house's walls are one closed ring, so the house cells joined up give its outline;
    furniture inside is within that outline."""
    h, w = codes.shape
    is_house = np.isin(codes, list(HOUSE))
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
