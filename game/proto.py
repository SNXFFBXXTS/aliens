#!/usr/bin/env python3
"""Graphics prototype: world map + biomes + zoomed-in local areas + animated lava/water.

  python3 proto.py [seed]      writes out/tiles.png, out/world.png, out/world_mini.png, out/zone_*.png, out/lava.gif

The world is a set of smooth noise "fields" (height, temperature, moisture, volcanic, weirdness).
The world map samples them once per tile; a local zone samples the *same* fields at 12 cells per
world tile with extra detail, so zooming in always matches the map. That's also how places stay
permanent later: same seed + same coordinates = same place.
"""
import heapq, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from art import P, B, S, T, Painter, dark, mix

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
W, H = 112, 70           # world map in tiles
ZS = 12                  # local cells per world tile


# ── noise ──
def hash2(ix, iy, seed):
    h = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + seed * 982451653) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def vnoise(x, y, seed):
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hash2(ix, iy, seed), hash2(ix + 1, iy, seed)
    c, d = hash2(ix, iy + 1, seed), hash2(ix + 1, iy + 1, seed)
    return (a + (b - a) * ux) + ((c + (d - c) * ux) - (a + (b - a) * ux)) * uy


def fbm(x, y, oct, seed):
    tot, amp, norm, f = 0, 1.0, 0, 1.0
    for o in range(oct):
        tot = tot + vnoise(x * f, y * f, seed + o * 101) * amp
        norm += amp; amp *= 0.5; f *= 2.03
    return tot / norm


def cell_rand(ix, iy, seed):
    return hash2(np.asarray(ix), np.asarray(iy), seed)


class World:
    def __init__(self, seed):
        self.seed = seed
        rng = np.random.default_rng(seed)
        # volcanic hotspots
        self.hot = [(rng.uniform(0.15, 0.85) * W, rng.uniform(0.25, 0.75) * H) for _ in range(3)]
        ys, xs = np.mgrid[0:H, 0:W] + 0.5
        raw = self.raw(xs, ys, 5)
        # thresholds from the world itself so every seed has a sensible mix
        self.norm = {k: (np.percentile(raw[k], 2), np.percentile(raw[k], 98)) for k in ("m", "f")}
        f = self.fields(xs, ys, 5)
        e = f["e"]
        self.th = {"sea": np.percentile(e, 44)}
        land = e[e >= self.th["sea"]]
        self.th.update(hill=np.percentile(land, 72), mount=np.percentile(land, 88), peak=np.percentile(land, 97),
                       deep=np.percentile(e[e < self.th["sea"]], 45), shallow=np.percentile(e[e < self.th["sea"]], 82),
                       fung=0.9, crys=0.1)
        self.f = f
        self.biome = self.classify(f)
        self.rivers()
        self.places(rng)
        self.roads()

    # ── fields ──
    def raw(self, X, Y, oct):
        s = self.seed
        # warp the coordinates a little so borders wiggle instead of following the noise grid
        X = X + (fbm(X / 7, Y / 7, 4, s + 50) - 0.5) * 7
        Y = Y + (fbm(X / 7, Y / 7, 4, s + 51) - 0.5) * 7
        e = fbm(X / 34, Y / 34, oct, s + 1)
        dx, dy = (X / W - 0.5) * 2, (Y / H - 0.5) * 2
        d = np.sqrt(dx * dx * 0.85 + dy * dy)
        e = e - d * d * 0.32
        v = np.zeros_like(X)
        for hx, hy in self.hot:
            bump = np.exp(-((X - hx) ** 2 + (Y - hy) ** 2) / (2 * 3.2 ** 2))
            e = e + 0.16 * bump
            v = np.maximum(v, bump)
        m = fbm(X / 22, Y / 22, oct, s + 2)
        f = fbm(X / 11, Y / 11, max(3, oct - 2), s + 5)
        tn = fbm(X / 26, Y / 26, 3, s + 3)
        return {"e": e, "v": v, "m": m, "f": f, "tn": tn}

    def fields(self, X, Y, oct):
        r = self.raw(X, Y, oct)
        for k in ("m", "f"):
            lo, hi = self.norm[k]
            r[k] = np.clip((r[k] - lo) / (hi - lo), 0, 1)
        lat = np.abs(Y / H - 0.5) * 2
        r["t"] = 1.08 - lat * 1.12 + (r["tn"] - 0.5) * 0.5
        return r

    def classify(self, f, local=False):
        e, t, m, v, w = f["e"], f["t"], f["m"], f["v"], f["f"]
        th = self.th
        sea = th["sea"]
        h = (e - sea) / (1 - sea)
        t = t - np.maximum(0, e - th["hill"]) * 3.0      # high ground is colder
        b = np.full(e.shape, "grass", dtype="<U10")
        b[m > 0.45] = "meadow"
        b[m > 0.56] = "forest"
        b[(m > 0.66) & (t > 0.62)] = "jungle"
        b[(m > 0.62) & (h < 0.05)] = "swamp"
        b[(t > 0.58) & (m > 0.38) & (m < 0.52)] = "savanna"
        b[(t > 0.6) & (m < 0.4)] = "desert"
        b[(t > 0.5) & (m < 0.46) & (e > th["hill"] - 0.01)] = "badlands"
        b[(b == "desert") & (w > 0.78)] = "salt"
        b[(w > th["fung"]) & (m > 0.5) & (t > 0.3)] = "fungal"
        b[(t < 0.3)] = "tundra"
        b[(t < 0.3) & (m > 0.48)] = "taiga"
        b[(t < 0.13)] = "icesheet"
        b[(e > th["hill"]) & np.isin(b, ["grass", "meadow", "forest", "tundra"])] = "hills"
        b[(e > th["hill"]) & (w < th["crys"])] = "crystal"
        b[(h < 0.025) & (t > 0.32)] = "beach"
        b[e > th["mount"]] = "mountain"
        b[e > th["peak"]] = "peak"
        b[v > 0.3] = "ash"
        if local:
            ridge = np.abs(fbm(f["X"] / 1.4, f["Y"] / 1.4, 4, self.seed + 9) - 0.5)
            b[(v > 0.4) & (ridge < 0.008 + v * 0.018)] = "lava"
            b[(v > 0.45) & (ridge >= 0.008 + v * 0.018) & (ridge < 0.016 + v * 0.03)] = "crust"
            b[v > 0.985] = "lava"
        else:
            b[v > 0.62] = "lava"
            b[v > 0.9] = "volcano"
        water = e < sea
        b[water] = "shallow"
        b[e < th["shallow"]] = "ocean"
        b[e < th["deep"]] = "deep"
        b[water & (t < 0.14)] = "seaice"
        return b

    # ── rivers, towns, roads (world scale) ──
    def rivers(self):
        """drainage: flood in from the sea, every land tile gets a downhill neighbour; water collects downhill"""
        e, sea = self.f["e"], self.th["sea"]
        rain = 0.3 + self.f["m"]
        filled = e.copy()
        down = {}
        ocean = e < sea
        seen = ocean.copy()
        heap = []
        for y in range(H):
            for x in range(W):
                if seen[y, x]:
                    continue
                edge = x in (0, W - 1) or y in (0, H - 1) or any(
                    0 <= x + dx < W and 0 <= y + dy < H and ocean[y + dy, x + dx] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if edge:
                    seen[y, x] = True; down[(x, y)] = None
                    heapq.heappush(heap, (e[y, x], x, y))
        while heap:
            h, x, y = heapq.heappop(heap)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H and not seen[ny, nx]:
                    seen[ny, nx] = True
                    filled[ny, nx] = max(e[ny, nx], h + 1e-5)
                    down[(nx, ny)] = (x, y)
                    heapq.heappush(heap, (filled[ny, nx], nx, ny))
        acc = {}
        for (x, y) in sorted(down, key=lambda q: -filled[q[1], q[0]]):
            acc[(x, y)] = acc.get((x, y), 0) + rain[y, x]
            d = down[(x, y)]
            if d is not None:
                acc[d] = acc.get(d, 0) + acc[(x, y)]
        self.lakes = {(x, y) for (x, y) in down if filled[y, x] - e[y, x] > 0.012}
        bad = {"lava", "volcano", "ash", "icesheet"}
        self.river, self.rlinks = set(), []
        for q, a in acc.items():
            if a >= 26 and self.biome[q[1], q[0]] not in bad and q not in self.lakes:
                self.river.add(q)
                d = down[q]
                if d is not None:
                    self.rlinks.append((q, d))
                else:   # river mouth: run it into the sea
                    x, y = q
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if 0 <= x + dx < W and 0 <= y + dy < H and e[y + dy, x + dx] < sea:
                            self.rlinks.append((q, (x + dx, y + dy))); break
        for (x, y) in self.lakes:
            if self.biome[y, x] not in bad:
                self.biome[y, x] = "seaice" if self.f["t"][y, x] < 0.25 else "lake"

    def places(self, rng):
        b = self.biome
        ok = np.isin(b, ["grass", "meadow", "savanna", "forest", "desert", "jungle", "tundra", "taiga", "hills", "beach", "badlands"])
        score = rng.random((H, W))
        for (x, y) in self.river:
            score[max(0, y - 1):y + 2, max(0, x - 1):x + 2] += 0.8
        water = np.isin(b, ["shallow", "ocean"])
        near = np.zeros_like(score)
        near[1:, :] += water[:-1, :]; near[:-1, :] += water[1:, :]; near[:, 1:] += water[:, :-1]; near[:, :-1] += water[:, 1:]
        score += (near > 0) * 0.6
        score[~ok] = -1
        for (x, y) in self.river:
            score[y, x] = -1
        self.towns = []
        for idx in np.argsort(-score, axis=None):
            y, x = divmod(int(idx), W)
            if score[y, x] < 0 or len(self.towns) >= 13:
                break
            if all((x - a) ** 2 + (y - c) ** 2 > 10 ** 2 for a, c in self.towns):
                self.towns.append((x, y))
        cand = list(zip(*np.nonzero(np.isin(b, ["hills", "mountain", "badlands", "crystal"]))))
        rng.shuffle(cand)
        self.caves = [(x, y) for y, x in cand[:9]]
        cand = list(zip(*np.nonzero(np.isin(b, ["grass", "desert", "tundra", "ash", "salt", "fungal", "swamp"]))))
        rng.shuffle(cand)
        self.ruins = [(x, y) for y, x in cand[:10] if (x, y) not in self.towns]

    def roads(self):
        cost = {"grass": 1, "meadow": 1, "savanna": 1.2, "beach": 1.5, "forest": 2.2, "desert": 2, "badlands": 2.5, "salt": 1.5,
                "tundra": 2, "taiga": 2.6, "hills": 3, "jungle": 3.5, "swamp": 4, "fungal": 3, "crystal": 4, "ash": 4,
                "mountain": 14, "peak": 40}
        b = self.biome
        def astar(s, g):
            openh, came, gs = [(0, s)], {s: None}, {s: 0}
            while openh:
                _, cur = heapq.heappop(openh)
                if cur == g:
                    break
                cx, cy = cur
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < W and 0 <= ny < H):
                        continue
                    c = cost.get(b[ny, nx])
                    if c is None:
                        continue
                    if (nx, ny) in self.river:
                        c += 5
                    if (nx, ny) in self.road:
                        c *= 0.35                   # reuse existing roads
                    ng = gs[cur] + c
                    if ng < gs.get((nx, ny), 1e18):
                        gs[(nx, ny)] = ng; came[(nx, ny)] = cur
                        heapq.heappush(openh, (ng + abs(nx - g[0]) + abs(ny - g[1]), (nx, ny)))
            if g not in came:
                return []
            p, out = g, []
            while p:
                out.append(p); p = came[p]
            return out[::-1]
        self.road, self.dlinks = set(), []
        ts = self.towns
        if not ts:
            return
        inn, edges = {0}, []
        while len(inn) < len(ts):   # Prim's tree over the towns
            best = min(((i, j) for i in inn for j in range(len(ts)) if j not in inn),
                       key=lambda ij: (ts[ij[0]][0] - ts[ij[1]][0]) ** 2 + (ts[ij[0]][1] - ts[ij[1]][1]) ** 2)
            edges.append(best); inn.add(best[1])
        for i, j in edges:
            path = astar(ts[i], ts[j])
            self.road.update(path)
            self.dlinks += list(zip(path, path[1:]))


# ── painting ──
def paint(p, x, y, b, r, local=False, t=0.0):
    """r: a few random numbers for this cell (array of 8 in 0..1)"""
    rr = lambda i: float(r[i % len(r)])
    pick = lambda i, n: int(rr(i) * n) % n
    sp = lambda i: (pick(i, 12), pick(i + 1, 12))
    jit = 0.965 + rr(7) * 0.07
    def bg(c, k=0.42):
        p.fill(x, y, tuple(min(255, int(v * k * jit)) for v in c))
    if b in ("deep", "ocean", "shallow", "seaice", "lake"):
        base = {"deep": P["deep"], "ocean": P["sea"], "shallow": P["shallow"], "lake": P["shallow"], "seaice": P["iceD"]}[b]
        bg(base, 1.0 if b != "seaice" else 0.75)
        if b == "seaice":
            p.stamp(x, y, S["crack"], [P["iceL"]], *sp(0)); p.stamp(x, y, S["crack2"], [P["ice"]], *sp(2))
            if rr(4) > 0.5: p.stamp(x, y, S["snow"], [P["iceL"]], *sp(4))
            return
        ink = {"deep": P["sea"], "ocean": P["wave"], "shallow": P["foam"], "lake": P["foam"]}[b]
        sh = int(t * 4) % 6
        for k in range(2 if b != "deep" else 1):
            px, py = sp(k * 3)
            p.stamp(x, y, S["wave"] if k == 0 else S["wave2"], [ink], (px + sh) % 13, py)
        return
    if b == "river":
        bg(P["river"], 0.9); p.stamp(x, y, S["wave2"], [P["riverL"]], (pick(0, 12) + int(t * 4)) % 12, pick(1, 12)); return
    if b == "savanna":
        bg(P["savanna"], 0.5)
        for k in range(3): p.stamp(x, y, S["tuft"], [P["savannaL"] if k else P["savanna"]], *sp(k * 2))
        if (not local and rr(5) < 0.5) or (local and rr(5) < 0.06):
            p.bitmap(x, y, B["acacia"], [P["acacia"], P["trunk"]])
        return
    if b == "crust":
        glow = 0.5 + 0.5 * math.sin(t * 2.4 + rr(7) * 6.28)
        bg(P["crust"], 1.6)
        p.stamp(x, y, S["crack"], [mix(P["lavaD"], P["lava"], glow)], *sp(0))
        if rr(4) < 0.5: p.stamp(x, y, S["crack2"], [P["lavaD"]], *sp(3))
        return
    if b == "drift":
        bg(P["snow"], 0.72)
        p.stamp(x, y, S["dune"], [P["iceL"]], *sp(0))
        if rr(5) < 0.08:
            p.bitmap(x, y, B["boulder"], [P["iceL"], P["ice"]])
        return
    if b == "beach":
        bg(P["sand"], 0.55); [p.stamp(x, y, S["grain"], [P["sand"]], *sp(k)) for k in range(4)]; return
    if b == "icesheet":
        bg(P["ice"], 0.62); p.stamp(x, y, S["crack"], [P["iceD"]], *sp(0)); p.stamp(x, y, S["spark"], [P["iceL"]], *sp(3))
        if local and rr(5) < 0.05:
            p.bitmap(x, y, B["boulder"], [P["iceL"], P["iceD"]])
        return
    if b in ("tundra", "taiga"):
        bg(P["snowD"], 0.55)
        for k in range(3): p.stamp(x, y, S["snow"], [P["snow"]], *sp(k * 2))
        if b == "taiga" and (not local or rr(5) < 0.38):
            p.bitmap(x, y, B["snowpine"], [P["pine"], P["trunk"], P["snow"]])
        return
    if b in ("grass", "meadow", "hills", "forest"):
        bg(P["grass"], 0.42)
        for k in range(3 if b != "forest" else 2): p.stamp(x, y, S["tuft"] if k % 2 else S["tuft2"], [P["grassL"] if k else P["grass"]], *sp(k * 2))
        if b == "meadow":
            fc = [P["flowerR"], P["flowerY"], P["flowerB"]][pick(6, 3)]
            p.stamp(x, y, S["flower"], [P["grassL"], fc, P["flowerY"]], *sp(5))
        if b == "hills" and (not local or rr(5) < 0.3):
            p.bitmap(x, y, B["hill"], [P["grassL"]])
        if b == "forest" and (not local or rr(5) < 0.48):
            p.bitmap(x, y, B["tree"], [P["leaf"], P["trunk"], P["leafL"]], dx=pick(6, 3) - 1 if local else 0)
        elif local and b in ("grass", "meadow") and rr(5) < 0.03:
            p.bitmap(x, y, B["bush"], [P["leaf"], P["leafL"]])
        return
    if b == "jungle":
        bg(P["jungle"], 0.6)
        p.stamp(x, y, S["tuft2"], [P["jungleL"]], *sp(0))
        if not local or rr(5) < 0.42:
            p.bitmap(x, y, B["palm"], [P["palm"], P["trunk"]])
        elif rr(6) < 0.5:
            p.bitmap(x, y, B["bush"], [P["jungleL"], P["palm"]])
        return
    if b == "swamp":
        bg(P["swamp"], 0.7)
        if local and rr(4) < 0.3:
            bg(P["swampW"], 1.0); p.stamp(x, y, S["wave2"], [P["reed"]], *sp(1)); return
        if not local or rr(5) < 0.4:
            p.bitmap(x, y, B["reeds"], [P["reed"], P["flowerR"], P["reedL"]])
        else:
            p.stamp(x, y, S["tuft"], [P["reed"]], *sp(2))
        return
    if b in ("desert", "salt"):
        if b == "salt":
            bg(P["salt"], 0.45); p.stamp(x, y, S["hex"], [P["saltL"]], *sp(0)); p.stamp(x, y, S["hex"], [P["salt"]], *sp(3)); return
        bg(P["desert"], 0.5); p.stamp(x, y, S["dune"], [P["dune"]], *sp(0))
        if (not local and rr(5) < 0.25) or (local and rr(5) < 0.025):
            p.bitmap(x, y, B["cactus"], [P["cactus"], P["sandD"]])
        elif local and rr(5) < 0.04:
            p.bitmap(x, y, B["bones"], [P["bone"]])
        return
    if b == "badlands":
        bg(P["mesa"], 0.45); p.stamp(x, y, S["grain"], [P["mesaL"]], *sp(0))
        if not local or rr(5) < 0.3:
            p.bitmap(x, y, B["hill"], [P["mesaL"]])
        return
    if b in ("mountain", "peak"):
        snow = b == "peak"
        bg(P["rock"] if not snow else P["snowD"], 0.42 if not snow else 0.6)
        if local:
            if rr(5) < 0.7:
                p.bitmap(x, y, B["boulder"], [P["snow"] if snow else P["rockL"], P["rock"]], dy=-pick(6, 3))
            p.stamp(x, y, S["pebble"], [P["rockL"]], *sp(2))
        else:
            p.bitmap(x, y, B["peak" if snow else "mountain"], [P["rockL"] if snow else P["rock"], None, P["snow"]])
        return
    if b in ("ash", "lava", "volcano"):
        if b == "lava":
            glow = 0.5 + 0.5 * math.sin(t * 2.4 + rr(7) * 6.28)
            bg(mix(P["lavaD"], P["lava"], glow * 0.5), 1.0)
            for k in range(3):
                px, py = sp(k * 2)
                p.stamp(x, y, S["blob"], [P["lava"], mix(P["lava"], P["lavaL"], glow)], (px + int(t * 2)) % 12, py)
            if rr(5) < 0.35:
                p.stamp(x, y, S["crack2"], [P["crust"]], *sp(4))
            return
        bg(P["ash"], 0.8); p.stamp(x, y, S["grain"], [P["ashL"]], *sp(0)); p.stamp(x, y, S["grain"], [P["ashL"]], *sp(2))
        if b == "volcano":
            p.bitmap(x, y, B["volcano"], [P["rock"], P["lava"], P["lavaL"]])
        elif local and rr(5) < 0.06:
            p.bitmap(x, y, B["boulder"], [P["ashL"], P["rockD"]])
        elif local and rr(5) < 0.09:
            p.bitmap(x, y, B["bones"], [P["bone"]])
        return
    if b == "fungal":
        bg(P["fung"], 0.6)
        p.stamp(x, y, S["spore"], [P["spore"]], *sp(0))
        if not local or rr(5) < 0.25:
            p.bitmap(x, y, B["mushroom"], [P["fungL"], P["fungS"], P["spore"]])
        elif rr(5) < 0.55:
            p.bitmap(x, y, B["smallshroom"], [P["fungL"], P["fungS"], P["spore"]])
        return
    if b == "crystal":
        bg(P["crys"], 0.75)
        p.stamp(x, y, S["spark"], [P["crysL"], P["crysP"]], *sp(0))
        if not local or rr(5) < 0.3:
            p.bitmap(x, y, B["crystal"], [P["crysL"], P["crysP"], P["iceL"]])
        return
    if b == "road":
        bg(P["road"], 0.55); p.stamp(x, y, S["grain"], [P["roadL"]], *sp(0)); p.stamp(x, y, S["pebble"], [P["road"]], *sp(2)); return
    if b == "bridge":
        bg(P["river"], 0.9); p.bitmap(x, y, B["bridge"], [P["roadL"], P["trunk"]], dy=3); return
    if b == "house":
        bg(P["road"], 0.5); p.bitmap(x, y, B["house"], [P["roof"], P["wall"], P["window"]]); return
    if b == "plaza":
        bg(P["road"], 0.62); p.stamp(x, y, S["brick"], [P["roadL"]], *sp(0)); return
    bg(P["void"], 1.0)


def rnd_cells(xs, ys, seed, n=8):
    return np.stack([cell_rand(xs, ys, seed + 31 * i) for i in range(n)], -1)


# ── world map ──
def render_world(wd):
    p = Painter(W, H)
    ys, xs = np.mgrid[0:H, 0:W]
    R = rnd_cells(xs, ys, wd.seed)
    for y in range(H):
        for x in range(W):
            b = wd.biome[y, x]
            if b in ("mountain", "peak", "lava", "volcano", "crystal", "fungal") or (x, y) not in wd.river:
                paint(p, x, y, b, R[y, x])
            else:
                paint(p, x, y, b if b not in ("forest", "jungle", "taiga") else "grass", R[y, x])
    cx = lambda q: q[0] * T + T / 2
    cy = lambda q: q[1] * T + T / 2
    for a, b in wd.rlinks:
        p.line(cx(a), cy(a), cx(b), cy(b), P["river"], 4)
    for a, b in wd.rlinks:
        p.line(cx(a), cy(a), cx(b), cy(b), P["riverL"], 1)
    for a, b in wd.dlinks:
        col = P["trunk"] if (a in wd.river or b in wd.river) else P["roadL"]
        p.line(cx(a), cy(a), cx(b), cy(b), col, 2)
    for (x, y) in wd.ruins:
        paint(p, x, y, wd.biome[y, x], R[y, x]); p.bitmap(x, y, B["ruins"], [P["wall"], P["rockD"]])
    for (x, y) in wd.caves:
        p.bitmap(x, y, B["cave"], [P["rockL"]])
    for (x, y) in wd.towns:
        p.fill(x, y, dark(P["road"], 0.5))
        p.bitmap(x, y, B["town"], [P["wallL"], P["roof"], P["window"]])
    return p.img


# ── a zoomed-in zone ──
def gen_cells(wd, ox, oy, zw, zh):
    """the terrain of a local area: ox, oy = world coords of its top-left; zw x zh cells (ZS per world tile).
    Depends only on the seed and the coordinates, so any piece of the world comes out the same every time."""
    j, i = np.mgrid[0:zh, 0:zw]
    X, Y = ox + (i + 0.5) / ZS, oy + (j + 0.5) / ZS
    f = wd.fields(X, Y, 8)
    f["X"], f["Y"] = X, Y
    b = wd.classify(f, local=True)
    # small lakes in wet low ground
    lake = (fbm(X / 0.7, Y / 0.7, 3, wd.seed + 21) > 0.74) & np.isin(b, ["swamp", "meadow", "forest", "tundra"])
    b[lake] = np.where(f["t"][lake] < 0.3, "seaice", "lake")
    # open water leads in sea ice, drifts on ice sheets
    lead = np.abs(fbm(X / 0.9, Y / 0.9, 3, wd.seed + 23) - 0.5) < 0.02
    b[(b == "seaice") & lead] = "shallow"
    drift = fbm(X / 0.5, Y / 0.5, 2, wd.seed + 24) > 0.66
    b[np.isin(b, ["icesheet", "seaice"]) & drift & ~lead] = "drift"
    # rivers and roads: the world links, wiggled with noise, painted onto cells
    def trace(links, radius, label, wig):
        for a, c in links:
            ax, ay, cx_, cy_ = a[0] + 0.5, a[1] + 0.5, c[0] + 0.5, c[1] + 0.5
            if max(ax, cx_) < ox - 1 or min(ax, cx_) > ox + zw / ZS + 1 or max(ay, cy_) < oy - 1 or min(ay, cy_) > oy + zh / ZS + 1:
                continue
            for s in range(ZS * 2 + 1):
                u = s / (ZS * 2)
                px, py = ax + (cx_ - ax) * u, ay + (cy_ - ay) * u
                n1 = (fbm(np.array(px * 1.7), np.array(py * 1.7), 2, wd.seed + 40) - 0.5) * wig
                n2 = (fbm(np.array(px * 1.7), np.array(py * 1.7), 2, wd.seed + 41) - 0.5) * wig
                lx, ly = (px + n1 - ox) * ZS, (py + n2 - oy) * ZS
                m = (i - lx + 0.5) ** 2 + (j - ly + 0.5) ** 2 <= radius ** 2
                if label == "road":
                    m &= np.isin(b, ["lava"], invert=True)
                    b[m & np.isin(b, ["river", "lake", "shallow", "ocean", "deep"])] = "bridge"
                    b[m & (b != "bridge")] = "road"
                else:
                    b[m & np.isin(b, ["deep", "ocean", "shallow"], invert=True)] = label
    trace(wd.rlinks, 1.4, "river", 1.2)
    trace(wd.dlinks, 0.75, "road", 1.0)
    # towns: a plaza with houses round it
    for n, (tx, ty) in enumerate(wd.towns):
        rng = np.random.default_rng(wd.seed + 5 + n * 7919)   # each town's own layout
        lx, ly = (tx + 0.5 - ox) * ZS, (ty + 0.5 - oy) * ZS
        if -8 < lx < zw + 8 and -8 < ly < zh + 8:
            d2 = (i - lx) ** 2 + (j - ly) ** 2
            ok = np.isin(b, ["river", "bridge", "lake", "shallow", "ocean", "deep", "lava"], invert=True)
            b[(d2 < 4.5 ** 2) & ok] = "plaza"
            for k in range(14):
                a = rng.uniform(0, 6.28); r = rng.uniform(2.2, 5.5)
                hx, hy = int(lx + math.cos(a) * r), int(ly + math.sin(a) * r * 0.8)
                if 0 <= hx < zw and 0 <= hy < zh and ok[hy, hx] and b[hy, hx] != "road":
                    b[hy, hx] = "house"
    return b, X, Y


def render_zone(wd, ox, oy, zw, zh, t=0.0, hero=True):
    b, X, Y = gen_cells(wd, ox, oy, zw, zh)
    p = Painter(zw, zh)
    gx, gy = np.floor(X * ZS).astype(np.int64), np.floor(Y * ZS).astype(np.int64)
    R = rnd_cells(gx, gy, wd.seed + 99)
    for y in range(zh):
        for x in range(zw):
            paint(p, x, y, b[y, x], R[y, x], local=True, t=t)
    if hero:
        walk = ~np.isin(b, ["deep", "ocean", "shallow", "lake", "river", "lava", "mountain", "peak", "house"])
        cands = np.argwhere(walk)
        if len(cands):
            c = cands[np.argmin(((cands - [zh / 2, zw / 2]) ** 2).sum(1))]
            p.bitmap(int(c[1]), int(c[0]), B["hero"], [P["hero"], P["heroC"]])
    return p.img, b


def find(wd, names, rng, near=None):
    pts = np.argwhere(np.isin(wd.biome, names))
    if near is not None:
        pts = np.array([q for q in pts if any(abs(q[0] + dy) < H and abs(q[1] + dx) < W and
                         0 <= q[0] + dy < H and 0 <= q[1] + dx < W and wd.biome[q[0] + dy, q[1] + dx] in near
                         for dx in range(-2, 3) for dy in range(-2, 3))])
    if not len(pts):
        return None
    y, x = pts[rng.integers(len(pts))]
    return int(x), int(y)


def font(sz, bold=False):
    try:
        return ImageFont.truetype("/usr/share/fonts/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/noto/NotoSans-Regular.ttf", sz)
    except OSError:
        return ImageFont.load_default()


def save(arr, name, scale=1):
    im = Image.fromarray(arr)
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(os.path.join(OUT, name))


def tilesheet():
    names = ["deep", "ocean", "shallow", "beach", "seaice", "icesheet", "tundra", "taiga", "grass", "meadow", "savanna", "forest",
             "jungle", "swamp", "desert", "salt", "badlands", "hills", "mountain", "peak", "ash", "lava", "crust", "volcano", "drift", "lake",
             "fungal", "crystal", "river", "road", "bridge", "house", "plaza"]
    cols, cw, chh = 6, 3, 3
    p = Painter(cols * (cw + 1), math.ceil(len(names) / cols) * (chh + 1))
    for n, nm in enumerate(names):
        bx, by = (n % cols) * (cw + 1), (n // cols) * (chh + 1)
        for yy in range(chh):
            for xx in range(cw):
                r = rnd_cells(np.array(bx + xx), np.array(by + yy + n * 7), 3)
                if nm in ("volcano", "house", "bridge", "river", "road", "plaza") and (xx, yy) != (1, 1):
                    paint(p, bx + xx, by + yy, {"volcano": "ash", "house": "plaza", "bridge": "river", "river": "grass", "road": "grass", "plaza": "plaza"}[nm], r, local=True)
                else:
                    paint(p, bx + xx, by + yy, nm, r, local=nm not in ("mountain", "peak", "volcano"))
            if nm in ("river", "road"):
                for xx in range(cw):
                    paint(p, bx + xx, by + 1, nm, rnd_cells(np.array(bx + xx), np.array(by), 5), local=True)
    im = Image.fromarray(p.img).resize((p.img.shape[1] * 2, p.img.shape[0] * 2), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for n, nm in enumerate(names):
        bx, by = (n % cols) * (cw + 1), (n // cols) * (chh + 1)
        d.text((bx * T * 2 + 2, (by + chh) * T * 2 + 4), nm, fill=(220, 220, 220), font=font(18, True))
    im.save(os.path.join(OUT, "tiles.png"))


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1337
    os.makedirs(OUT, exist_ok=True)
    tilesheet()
    wd = World(seed)
    img = render_world(wd)
    save(img, "world.png")
    # minimap: average colour of each tile
    mini = img.reshape(H, T, W, T, 3).mean((1, 3)).astype(np.uint8)
    save(mini, "world_mini.png", 6)
    rng = np.random.default_rng(seed)
    zones = {}
    if wd.towns:
        tt = max(wd.towns, key=lambda q: sum(1 for d in wd.dlinks if d[0] == q or d[1] == q) + (2 if any(abs(q[0] - r[0]) + abs(q[1] - r[1]) <= 2 for r in wd.river) else 0))
        zones["town"] = tt
    hx, hy = wd.hot[0]
    zones["volcano"] = (int(hx), int(hy))
    for nm, (bs, nr) in {"frozen": (["seaice", "icesheet"], ["tundra", "taiga"]), "jungle": (["jungle", "swamp"], None),
                        "fungal": (["fungal"], None), "crystal": (["crystal"], None), "desert": (["desert", "salt"], None)}.items():
        q = find(wd, bs, rng, nr)
        if q:
            zones[nm] = q
    zw, zh = 48, 30
    for nm, (x, y) in zones.items():
        ox, oy = x + 0.5 - zw / ZS / 2, y + 0.5 - zh / ZS / 2
        zimg, _ = render_zone(wd, ox, oy, zw, zh)
        save(zimg, f"zone_{nm}.png", 2)
    # animated lava + water
    vx, vy = wd.hot[0]
    frames = []
    for k in range(10):
        zimg, _ = render_zone(wd, vx - 2.2, vy - 1.2, 40, 24, t=k * 0.63, hero=False)
        frames.append(Image.fromarray(zimg))
    frames[0].save(os.path.join(OUT, "lava.gif"), save_all=True, append_images=frames[1:], duration=160, loop=0)
    with open(os.path.join(OUT, "zones.txt"), "w") as fh:
        for nm, q in zones.items():
            fh.write(f"{nm}: world tile {q}\n")
    print("seed", seed, "towns", len(wd.towns), "river tiles", len(wd.river), "road tiles", len(wd.road), "zones", list(zones))


if __name__ == "__main__":
    main()
