"""Drawing a zone's picture (palette indices), apart from the game so it can run in worker processes.
The game works out what's in and round the zone (World.build_inputs); this paints it. Pure: same inputs, same picture."""
import os
import numpy as np
import proto
import weird
import buildings
import structures  # noqa: F401  (registers the ruin props in weird; it pulls in cultures too)

CS = proto.ZS
M = 3                                                    # margin of neighbouring cells round the zone
UNDER = {"road", "trail", "plaza", "house", "bonfire", "bridge"}     # drawn as flowing bands over the land
_species, _worlds = {}, {}


def warm(seed):
    """get a worker ready before it's needed"""
    _species.setdefault(seed, weird.Species(seed))
    _worlds.setdefault(seed, proto.World(seed))


def paint_zone(seed, cx, cy, B, dens, roads, trails, W, H, species=None):
    """B = the zone's cells plus an M-cell margin; roads/trails = centre lines in world coords.
    Returns (img, feats, fires, fsprites)."""
    if species is None:                                  # in a worker: one flora set per world, kept
        species = _species.get(seed) or _species.setdefault(seed, weird.Species(seed))
    if roads is None:                                    # trace the roads here (slow, so not in the game's process)
        wd = _worlds.get(seed) or _worlds.setdefault(seed, proto.World(seed))
        box = (cx - 0.3, cy - 0.3, cx + 1.3, cy + 1.3)    # (same as World.lines)
        roads, trails = proto.road_lines(wd, *box), proto.trail_lines(wd, *box)
    fires, fsprites = set(), {}
    b = B[M:M + CS, M:M + CS]
    p = weird.Painter8(CS, CS)
    j, i = np.mgrid[0:CS, 0:CS]
    R = proto.rnd_cells(cx * CS + i, cy * CS + j, seed + 99)
    # what the ground is made of under everything: paths, props and buildings stand on the land round them
    G = B.copy()
    for y in range(B.shape[0]):
        for x in range(B.shape[1]):
            c = B[y, x]
            if c in UNDER or c.startswith("p_") or c.startswith("f_") or c in weird.BUILT:
                win = B[max(0, y - 2):y + 3, max(0, x - 2):x + 3].ravel()
                want = [w for w in win if (w in weird.WATER) == (c == "bridge") and w not in UNDER
                        and not w.startswith("p_") and not w.startswith("f_") and w not in weird.BUILT]
                G[y, x] = max(set(want), key=want.count) if want else ("river" if c == "bridge" else "grass")
    zseed = (cx * 7919 + cy * 104729 + seed) & 0xFFFFFFFF
    weird.ground_pass(p, G, M, CS, zseed, cx * CS * weird.TS, cy * CS * weird.TS)
    items = []
    dens = dens
    for y in range(CS):
        for x in range(CS):
            c = b[y, x]
            if c.startswith("f_"):             # furniture (drawn live by the game) stands on the room's floor
                nbr = [B[y + M + oy, x + M + ox] for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                fl = [n for n in nbr if n in buildings.FLOORS]
                c = max(set(fl), key=fl.count) if fl else "hfloor"
            if c in weird.WALLS:               # walls join up with the walls next to them
                W_ = weird.WALLS
                weird.built(p, x, y, c, R[y, x], nb=(B[y + M - 1, x + M] in W_, B[y + M + 1, x + M] in W_,
                                                      B[y + M, x + M - 1] in W_, B[y + M, x + M + 1] in W_))
            elif c in weird.BUILT:
                weird.built(p, x, y, c, R[y, x])
            elif c in UNDER and c not in ("house", "bonfire"):
                continue
            else:                              # trees, plants, props: the ground is already down
                if c == "p_fence":             # a fence running up the screen is drawn edge-on: skinny
                    F_ = ("p_fence", "p_fencev")
                    if (B[y + M - 1, x + M] in F_ or B[y + M + 1, x + M] in F_) and not (
                            B[y + M, x + M - 1] in F_ or B[y + M, x + M + 1] in F_):
                        c = "p_fencev"
                weird.paint(p, species, x, y, c, R[y, x], defer=items, mode="thing", mult=dens)
    to_px = lambda L: [(pts - (cx, cy)) * CS * weird.TS for pts in L]
    weird.flow_bands(p, B, M, CS, zseed,
                     ox=cx * CS * weird.TS, oy=cy * CS * weird.TS, roads=to_px(roads), trails=to_px(trails))
    # big things from the zones next door that lean over the border: their shadows (and rocks/peaks) belong here too
    nb = []
    for y in range(-1, CS + 3):
        for x in range(-2, CS + 2):
            if 0 <= x < CS and 0 <= y < CS:
                continue
            gx, gy = cx * CS + x, cy * CS + y
            if not (0 <= gx // CS < W and 0 <= gy // CS < H):
                continue
            hit = weird.pick_big(species, B[gy - cy * CS + M, gx - cx * CS + M], proto.rnd_cells(np.array(gx), np.array(gy), seed + 99))
            if hit:
                nb.append((hit[0], x, y, hit[1], hit[2], hit[3], True))
    # (everything below only touches this zone's own image)
    def jit(kind, x, y):                     # nudge natural things off the grid a little, up and down too
        if kind.startswith("p_") or kind == "hut":
            return 0
        return int(weird._h(np.array(cx * CS + x), np.array(cy * CS + y), 4411) * 15) - 7
    bigs = sorted([it for it in items + nb if it[6]], key=lambda it: (it[2], it[1]))
    for (kind, x, y, spr, m, dx, _) in bigs:                 # every shadow first...
        p.big_shadow(x, y, spr, dx, jit(kind, x, y))
    for (kind, x, y, spr, m, dx, big) in sorted(items, key=lambda it: (it[2], it[1])):
        if not big and kind not in weird.SWAY and kind != "fire":       # small props from structures
            p.shadow(x, y, spr, dx)
            p.sprite(x, y, spr, m, dx=dx)
    for (kind, x, y, spr, m, dx, _) in bigs:                 # ...then the things that don't move
        if kind not in weird.SWAY:
            p.big_body(x, y, spr, m, dx, jit(kind, x, y))
    feats = []
    for (kind, x, y, spr, m, dx, big) in sorted(items, key=lambda it: (it[2], it[1])):
        gx, gy = cx * CS + x, cy * CS + y
        if kind == "fire":
            feats.append(("fire", gx * weird.TS, gy * weird.TS, None))
            fires.add((gx, gy))
        elif kind in weird.SWAY:
            key = (os.getpid(), id(spr), tuple(sorted(m.items())))   # (ids are per process)
            fsprites[key] = (spr, m, kind)
            n = spr.shape[0]
            j_ = jit(kind, x, y)
            if big:
                feats.append((kind, gx * weird.TS + weird.TS // 2 - n // 2 + dx, (gy + 1) * weird.TS - n + j_, key))
            else:
                feats.append((kind, gx * weird.TS + dx, gy * weird.TS + j_ // 2, key))
    return p.img, feats, fires, fsprites
