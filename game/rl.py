#!/usr/bin/env python3
"""Walkable prototype: wander the generated world, meet its creatures, fight.

  rl            character creation (preview)
  rl --play     carry on in your world (makes one the first time)
  rl --new      start a brand new world (new seed)
  rl --seed N   start a world from a given seed

Keys: arrows / WASD / numpad (7 9 1 3 diagonals) move, walk into a creature to attack,
      . or numpad 5 wait a turn, M world map, Esc saves and quits

Turn-based: every step or attack is one turn, then the creatures act.
The world is split into chunks (one world-map tile = 12 x 12 cells). A chunk is generated the first time
it comes near you, then written to disk with the creatures living there, so it never changes after that.
Saves: ~/.local/share/roguelike/
"""
import json, math, os, queue, random, sys, threading, time, warnings
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", message=".*avx2.*")
import numpy as np
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto                                           # noqa: E402
import weird                                           # noqa: E402
import mobs                                            # noqa: E402
import immersion as im                                 # noqa: E402
import structures                                      # noqa: E402
from weird_proto import world8                         # noqa: E402
from art import P, B, T, Painter                       # noqa: E402

SCALE = 2
CS = proto.ZS                                          # cells per chunk
PX = T * SCALE                                         # pixels per cell on screen
ROOT = os.environ.get("RL_HOME") or os.path.expanduser("~/.local/share/roguelike")
HUD_H, LOG_H = 30, 80
ACTIVE = 28                                            # creatures further away than this sleep
SPEED = 5.0          # walking speed, cells a second
ACCEL = 14.0         # how quickly you get up to speed
FRICTION = 11.0      # how quickly you stop when you let go (glide ~ SPEED / FRICTION cells)
BODY = 0.3           # half the width of your body, in cells
TICK_S = 0.35        # the world takes a turn this often, in seconds
ATTACK_S = 0.4       # fastest you can swing

NAMES = {"deep": "Deep sea", "ocean": "Ocean", "shallow": "Shallows", "beach": "Beach", "seaice": "Sea ice",
         "icesheet": "Ice sheet", "drift": "Snowdrifts", "tundra": "Tundra", "taiga": "Snow forest", "grass": "Grassland",
         "meadow": "Meadow", "savanna": "Savanna", "forest": "Forest", "jungle": "Jungle", "swamp": "Swamp",
         "desert": "Desert", "salt": "Salt flats", "badlands": "Badlands", "hills": "Hills", "mountain": "Mountains",
         "peak": "Snowy peaks", "ash": "Ash wastes", "lava": "Lava", "crust": "Cooling lava", "volcano": "Volcano",
         "fungal": "Fungal forest", "crystal": "Crystal fields", "lake": "Lake", "river": "River", "road": "Road",
         "bridge": "Bridge", "house": "House", "plaza": "Town", "trail": "Trail", "bonfire": "Town",
         "wall": "Wall", "wwall": "Timber wall", "ruin": "Rubble", "floor": "Concrete floor", "wfloor": "Floorboards",
         "packed": "Packed earth", "scorch": "Scorched ground", "railh": "Railway", "railv": "Railway",
         "mosaic": "Mosaic floor"}
UNDER = {"road", "trail", "plaza", "house", "bonfire", "bridge"}     # drawn as flowing bands over the land
BLOCKED = {"deep": "The water's too deep to swim.", "ocean": "The water's too deep to swim.",
           "mountain": "The rock face is too steep.", "peak": "The peak is too steep to climb.",
           "house": "Someone lives there.", "lava": "Lava! Far too hot to step in.",
           "river": "The current's too strong to wade. Find a bridge.", "lake": "The lake's too deep to wade.",
           "bonfire": "The bonfire's too hot to stand in.", "wall": "A solid wall.", "wwall": "A timber wall.",
           "ruin": "A heap of rubble and broken wall."}


class World:
    def __init__(self, seed):
        self.seed = seed
        self.dir = os.path.join(ROOT, f"world-{seed}-z{CS}")     # zone size in the name: old saves don't clash
        os.makedirs(os.path.join(self.dir, "chunks"), exist_ok=True)
        self.wd = proto.World(seed)
        self.species = weird.Species(seed)
        self.best = mobs.Bestiary(seed)
        self.codes, self.surf = {}, {}
        self.mobs = {}                          # id -> Mob, for every loaded chunk
        self.feats = {}                         # chunk -> live things drawn every frame: (kind, world px, world py, key)
        self.lock = threading.Lock()            # guards self.ready
        self.clock_ = threading.RLock()         # guards making/loading zones (the background builder does it too)
        self.ready, self.queued = {}, set()
        self.jobs = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()
        self.fsprites = {}                      # key -> (sprite, colours, kind)
        self.fires = set()                      # cells with flames in them
        self.seen = {}                          # chunk -> bool array of cells you've laid eyes on
        self.dead = set()
        self.visited = {tuple(map(int, f[:-5].split("_"))) for f in os.listdir(os.path.join(self.dir, "chunks")) if f.endswith(".json")}
        self.map_img = None
        self.home = self.wd.towns[0] if self.wd.towns else (proto.W // 2, proto.H // 2)

    def inside(self, cx, cy):
        return 0 <= cx < proto.W and 0 <= cy < proto.H

    def tier(self, cx, cy):
        d = ((cx - self.home[0]) ** 2 + (cy - self.home[1]) ** 2) ** 0.5
        return min(4, int(d / 13))

    def path(self, cx, cy):
        return os.path.join(self.dir, "chunks", f"{cx}_{cy}.json")

    def chunk(self, cx, cy):
        k = (cx, cy)
        if k in self.codes:
            return self.codes[k]
        with self.clock_:
            if k in self.codes:
                return self.codes[k]
            return self._chunk(cx, cy)

    def _chunk(self, cx, cy):
        k = (cx, cy)
        p = self.path(cx, cy)
        new_mobs = []
        fresh = False
        if os.path.exists(p):                                       # been here: it's fixed now
            with open(p) as f:
                d = json.load(f)
            if isinstance(d, list):                                 # older save without creatures
                d = {"cells": d, "mobs": None}
            b = np.array(d["cells"], dtype="<U10")
            if d.get("seen"):
                self.seen[k] = np.array([[(row >> i) & 1 for i in range(CS)] for row in d["seen"]], bool)
            if d.get("mobs") is None:
                new_mobs = self.spawn_in(b, cx, cy)
                fresh = True
            else:
                new_mobs = [mobs.Mob.from_json(m, self.best) for m in d["mobs"]]
        elif self.inside(cx, cy):
            b = self.generate(cx, cy)                               # first visit: make it, then keep it
            new_mobs = self.spawn_in(b, cx, cy)
            self.visited.add(k)
            fresh = True
        else:
            b = np.full((CS, CS), "deep", dtype="<U10")             # off the edge of the world
        self.codes[k] = b
        self.seen.setdefault(k, np.zeros((CS, CS), bool))
        for m in new_mobs:
            if m.id not in self.dead:
                self.mobs[m.id] = m
        if fresh:
            self.write_chunk(cx, cy)
        return b

    always_day = False
    showcase = False

    def generate(self, cx, cy):
        b, _, _ = proto.gen_cells(self.wd, cx, cy, CS, CS)
        return b

    def spawn_in(self, b, cx, cy):
        return mobs.spawn(self.best, b, cx, cy, CS, self.tier(cx, cy), self.seed)

    def density(self, cx, cy):
        """how thickly things grow in a zone (the showcase alternates busy and barren)"""
        return 1.0

    def lines(self, cx, cy):
        """centre lines (world coords) of the roads and footpaths near zone (cx, cy)"""
        box = (cx - 0.3, cy - 0.3, cx + 1.3, cy + 1.3)
        return proto.road_lines(self.wd, *box), proto.trail_lines(self.wd, *box)

    def write_chunk(self, cx, cy):
        p = self.path(cx, cy)
        here = [m.to_json() for m in self.mobs.values() if m.x // CS == cx and m.y // CS == cy]
        with open(p + ".tmp", "w") as f:
            seen = [int(sum(1 << i for i in range(CS) if row[i])) for row in self.seen[(cx, cy)]]
            json.dump({"cells": self.codes[(cx, cy)].tolist(), "mobs": here, "seen": seen}, f)
        os.replace(p + ".tmp", p)

    def save(self):
        for (cx, cy) in self.codes:
            if self.inside(cx, cy):
                self.write_chunk(cx, cy)

    def cell(self, gx, gy):
        b = self.chunk(gx // CS, gy // CS)
        return str(b[gy % CS, gx % CS])

    def mob_at(self, x, y):
        for m in self.mobs.values():
            if m.x == x and m.y == y:
                return m
        return None

    def remember(self, cells):
        for (x, y) in cells:
            self.chunk(x // CS, y // CS)
            self.seen[(x // CS, y // CS)][y % CS, x % CS] = True

    def was_seen(self, x, y):
        a = self.seen.get((x // CS, y // CS))
        return a is not None and a[y % CS, x % CS]

    def surface(self, cx, cy):
        """the zone as a pygame surface (palette indices; colours come from the cycling palette at draw time).
        Usually already built in the background by the prefetcher; otherwise built now."""
        k = (cx, cy)
        if k in self.surf:
            return self.surf[k]
        with self.lock:
            done = self.ready.pop(k, None)
        if done is None:
            done = self.build(cx, cy)
        img, feats, fires, fsprites = done
        self.feats[k] = feats
        self.fires |= fires
        self.fsprites.update(fsprites)
        s = pygame.image.frombuffer(img.tobytes(), (CS * weird.TS, CS * weird.TS), "P")
        s.set_palette([tuple(c) for c in weird.palette(0)])
        s = pygame.transform.scale(s, (CS * PX, CS * PX))
        if len(self.surf) > 40:
            self.surf.clear()
        self.surf[k] = s
        return s

    def surface_if_ready(self, cx, cy):
        k = (cx, cy)
        if k in self.surf or k in self.ready:
            return self.surface(cx, cy)
        if not self.inside(cx, cy):
            return None                          # past the edge of the world: just darkness
        self.prefetch([k])
        return None

    def prefetch(self, zones):
        """ask the background builder to get these zones ready"""
        for k in zones:
            if k not in self.surf and k not in self.ready and k not in self.queued and self.inside(*k):
                self.queued.add(k)
                self.jobs.put(k)

    def _worker(self):
        while True:
            k = self.jobs.get()
            try:
                if k not in self.surf:
                    out = self.build(*k)
                    with self.lock:
                        self.ready[k] = out
            except Exception:
                pass
            finally:
                self.queued.discard(k)

    def build(self, cx, cy):
        """draw a zone into a palette-index image (no pygame, so it can run in the background)"""
        fires, fsprites = set(), {}
        b = self.chunk(cx, cy)
        p = weird.Painter8(CS, CS)
        j, i = np.mgrid[0:CS, 0:CS]
        R = proto.rnd_cells(cx * CS + i, cy * CS + j, self.seed + 99)
        # the zone plus a margin of its neighbours, so roads flow smoothly across borders
        M = 3
        B = np.empty((CS + 2 * M, CS + 2 * M), dtype="<U10")
        B[M:M + CS, M:M + CS] = b
        for y in range(-M, CS + M):
            for x in range(-M, CS + M):
                if not (0 <= x < CS and 0 <= y < CS):
                    gx, gy = cx * CS + x, cy * CS + y
                    B[y + M, x + M] = self.cell(gx, gy) if self.inside(gx // CS, gy // CS) else "deep"
        # what the ground is made of under everything: paths, props and buildings stand on the land round them
        G = B.copy()
        for y in range(B.shape[0]):
            for x in range(B.shape[1]):
                c = B[y, x]
                if c in UNDER or c.startswith("p_") or c in weird.BUILT:
                    win = B[max(0, y - 2):y + 3, max(0, x - 2):x + 3].ravel()
                    want = [w for w in win if (w in weird.WATER) == (c == "bridge") and w not in UNDER
                            and not w.startswith("p_") and w not in weird.BUILT]
                    G[y, x] = max(set(want), key=want.count) if want else ("river" if c == "bridge" else "grass")
        zseed = (cx * 7919 + cy * 104729 + self.seed) & 0xFFFFFFFF
        weird.ground_pass(p, G, M, CS, zseed, cx * CS * weird.TS, cy * CS * weird.TS)
        items = []
        dens = self.density(cx, cy)
        for y in range(CS):
            for x in range(CS):
                c = b[y, x]
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
                    weird.paint(p, self.species, x, y, c, R[y, x], defer=items, mode="thing", mult=dens)
        roads, trails = self.lines(cx, cy)
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
                if not self.inside(gx // CS, gy // CS):
                    continue
                hit = weird.pick_big(self.species, self.cell(gx, gy), proto.rnd_cells(np.array(gx), np.array(gy), self.seed + 99))
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
                key = (id(spr), tuple(sorted(m.items())))
                fsprites[key] = (spr, m, kind)
                n = spr.shape[0]
                j_ = jit(kind, x, y)
                if big:
                    feats.append((kind, gx * weird.TS + weird.TS // 2 - n // 2 + dx, (gy + 1) * weird.TS - n + j_, key))
                else:
                    feats.append((kind, gx * weird.TS + dx, gy * weird.TS + j_ // 2, key))
        return p.img, feats, fires, fsprites

    def world_map(self):
        if self.map_img is None:
            img = weird.to_rgb(world8(self.wd, self.species))
            self.map_img = pygame.image.frombuffer(np.ascontiguousarray(img).tobytes(), (img.shape[1], img.shape[0]), "RGB").copy()
        return self.map_img


class Game:
    def __init__(self, seed, screen, world=None, character=None):
        self.w = world or World(seed)
        self.char = character or self.load_character()
        self.screen = screen
        self.font = self.load_font(15)
        self.big = self.load_font(22, True)
        self.small = self.load_font(12)
        self.msgs = []
        self.show_map = False
        self.t0 = time.monotonic()
        self.last_save = time.monotonic()
        self.hero = self.make_hero()
        self.amb = im.Ambience()
        self.vis = set()
        self.dark = None                    # cached darkness overlay
        self.last_desc = {}
        self.mob_img = {}
        self.flash = {}                     # mob id / "you" -> time of last hit
        self.mob_pos = {}                   # mob id -> where it's drawn (eases towards its square)
        self.size = self.load_settings().get("size", 0.55)   # how big people and creatures are next to the scenery
        self.sizer = False                  # the size slider is showing
        self.dead = False
        self.killer = ""
        self.lvl, self.xp, self.turn = 1, 0, 0
        stt = (self.char or {}).get("stats", {})
        self.stat = {k: stt.get(k, 5) for k in ("STR", "AGI", "TOU", "WIT", "CHA", "LCK")}
        self.base_hp = 15 + self.stat["TOU"] * 3                 # toughness decides how much you can take
        self.maxhp = self.base_hp
        st = self.load_state()
        if st:
            self.lvl, self.xp, self.turn = st.get("lvl", 1), st.get("xp", 0), st.get("turn", 0)
            self.maxhp = self.base_hp + (self.lvl - 1) * 6
            self.hp = st.get("hp", self.maxhp)
            self.w.dead = set(st.get("dead", []))
            self.px, self.py = st["px"], st["py"]
            for i in self.w.dead:
                self.w.mobs.pop(i, None)
            self.say("Welcome back.")
        else:
            self.px, self.py = self.start_spot()
            self.hp = self.maxhp
            who = f"{self.char['name']}, {self.char['archetype'].lower()}, " if self.char else "You "
            self.say(who + ("arrive" if not self.char else "arrives") + " in town. M opens the world map (travel with the arrows, M again to zoom in).")
        self.here = self.w.cell(self.px, self.py)
        self.fx, self.fy = float(self.px), float(self.py)   # smooth position (cells); px, py = the cell you're in
        self.vx = self.vy = 0.0
        self._cell = (self.px, self.py)
        self.next_tick = time.monotonic() + TICK_S
        self.update_view()
        for i in self.w.dead:
            self.w.mobs.pop(i, None)

    # ── setup ──
    def load_font(self, sz, bold=False):
        f = "/usr/share/fonts/noto/NotoSans-%s.ttf" % ("Bold" if bold else "Regular")
        return pygame.font.Font(f if os.path.exists(f) else None, sz)

    def load_character(self):
        try:
            with open(os.path.join(ROOT, "character.json")) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def char_look(self):
        """in the world you're just your symbol: no gear symbols round it (they stay in the menu)"""
        c = self.char
        return (None, None, None, None, tuple(c["coat"]), tuple(c["trim"]))

    def hero_surface(self, left):
        """you, as your symbol with its gear, facing the way you walk"""
        key = ("hero", left)
        if key not in self.mob_img:
            import charcreate
            s = pygame.Surface((PX * 3, PX * 3), pygame.SRCALPHA)
            charcreate.draw_char(s, PX * 3 // 2, PX * 3 // 2, int(PX * 1.1), self.char["body"], self.char_look(),
                                 tuple(self.char["skin_rgb"]), None)
            rim = pygame.mask.from_surface(s).to_surface(setcolor=(235, 230, 215, 120), unsetcolor=(0, 0, 0, 0))
            out = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):  # a faint light outline so you stand out
                out.blit(rim, (ox, oy))
            out.blit(s, (0, 0))
            self.mob_img[key] = pygame.transform.flip(out, True, False) if left else out
        return self.mob_img[key]

    def make_hero(self):
        p = Painter(1, 1)
        p.img[:] = 0
        p.bitmap(0, 0, B["hero"], [P["hero"], P["heroC"]])
        s = pygame.image.frombuffer(p.img.tobytes(), (T, T), "RGB").copy()
        s.set_colorkey((0, 0, 0))
        return pygame.transform.scale(s, (PX, PX))

    def mob_sprite(self, m):
        k = (m.biome, m.n, m.angry)
        if k not in self.mob_img:
            pal = weird.palette(0)
            spr = m.sp.sprite
            img = np.zeros((T, T, 3), np.uint8)
            img[spr == "1"] = pal[weird.F(m.sp.colour, 6)]
            img[spr == "2"] = pal[weird.F(m.sp.colour, 3)]
            img[spr == "3"] = (255, 70, 60) if m.angry else (240, 240, 200)
            img[(img == 0).all(-1) & (spr != ".")] = (1, 1, 1)
            s = pygame.image.frombuffer(img.tobytes(), (T, T), "RGB").copy()
            s.set_colorkey((0, 0, 0))
            self.mob_img[k] = pygame.transform.scale(s, (PX, PX))
        return self.mob_img[k]

    def start_spot(self):
        tx, ty = self.w.home
        gx, gy = tx * CS + CS // 2, ty * CS + CS // 2
        for r in range(0, 30):                       # nearest open ground
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and self.w.cell(gx + dx, gy + dy) not in BLOCKED and not self.w.mob_at(gx + dx, gy + dy):
                        return gx + dx, gy + dy
        return gx, gy

    SIZE_MIN, SIZE_MAX = 0.3, 1.2

    def load_settings(self):
        try:
            with open(os.path.join(ROOT, "settings.json")) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_settings(self):
        st = self.load_settings()
        st["size"] = round(self.size, 3)
        with open(os.path.join(ROOT, "settings.json"), "w") as f:
            json.dump(st, f)

    def set_size(self, v):
        v = max(self.SIZE_MIN, min(self.SIZE_MAX, v))
        if abs(v - self.size) > 1e-4:
            self.size = v
            self._sized = {}

    def sized(self, key, srf):
        """a sprite at the chosen character size (cached)"""
        c = getattr(self, "_sized", None)
        if c is None:
            c = self._sized = {}
        if key not in c:
            w, h = srf.get_size()
            c[key] = pygame.transform.smoothscale(srf, (max(1, int(w * self.size)), max(1, int(h * self.size))))
        return c[key]

    def slider_rect(self):
        sw, sh = self.screen.get_size()
        return pygame.Rect(sw - 300, HUD_H + 14, 280, 70)

    def draw_sizer(self):
        r = self.slider_rect()
        panel = pygame.Surface(r.size, pygame.SRCALPHA)
        panel.fill((10, 8, 16, 215))
        self.screen.blit(panel, r.topleft)
        pygame.draw.rect(self.screen, (90, 80, 110), r, 1)
        self.screen.blit(self.font.render(f"Character size  {int(self.size * 100)}%", True, (230, 225, 210)),
                         (r.x + 12, r.y + 8))
        tr = self.track_rect()
        pygame.draw.rect(self.screen, (60, 55, 75), tr, border_radius=3)
        u = (self.size - self.SIZE_MIN) / (self.SIZE_MAX - self.SIZE_MIN)
        pygame.draw.rect(self.screen, (200, 170, 90), (tr.x, tr.y, int(tr.w * u), tr.h), border_radius=3)
        pygame.draw.circle(self.screen, (245, 235, 200), (tr.x + int(tr.w * u), tr.centery), 9)
        self.screen.blit(self.small.render("drag, or [ ]   Z to close", True, (130, 125, 140)), (r.x + 12, r.y + 50))

    def track_rect(self):
        r = self.slider_rect()
        return pygame.Rect(r.x + 14, r.y + 34, r.w - 28, 8)

    def slide_to(self, mx):
        tr = self.track_rect()
        u = max(0.0, min(1.0, (mx - tr.x) / tr.w))
        self.set_size(self.SIZE_MIN + u * (self.SIZE_MAX - self.SIZE_MIN))

    def state_path(self):
        return os.path.join(self.w.dir, "player.json")

    def load_state(self):
        try:
            with open(self.state_path()) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def save(self):
        self.w.save()
        with open(self.state_path() + ".tmp", "w") as f:
            json.dump({"px": self.px, "py": self.py, "hp": self.hp, "lvl": self.lvl, "xp": self.xp, "turn": self.turn,
                       "dead": sorted(self.w.dead)}, f)
        os.replace(self.state_path() + ".tmp", self.state_path())
        if not self.w.showcase:
            with open(os.path.join(ROOT, "current.json"), "w") as f:
                json.dump({"seed": self.w.seed}, f)
        self.last_save = time.monotonic()

    def say(self, m):
        if self.msgs and self.msgs[-1] == m:            # don't stack the same line while you lean on a wall
            return
        self.msgs.append(m)
        self.msgs = self.msgs[-4:]

    # ── turns ──
    def act(self, dx, dy):
        if self.show_map or self.dead:
            return
        if getattr(self, "facing", None) != (dx, dy):
            self.facing = (dx, dy)               # first press in a new direction: just turn and look (free)
            self.update_view()
            return
        nx, ny = self.px + dx, self.py + dy
        m = self.w.mob_at(nx, ny)
        if m:
            self.attack(m)
            self.end_turn()
            return
        if not self.w.inside(nx // CS, ny // CS):
            self.say("The edge of the known world. Nothing but sea beyond.")
            return
        c = self.w.cell(nx, ny)
        if (nx, ny) in self.w.fires and c != "bonfire":
            self.say("Flames! You keep back from the fire.")
            return
        if c in BLOCKED:
            self.say(BLOCKED[c])
            return
        if c in structures.BLOCKING:
            self.say(f"A {structures.PROP_NAMES.get(c[2:], c[2:])} is in the way.")
            return
        before = len(self.w.visited)
        self.px, self.py = nx, ny
        self.last_moved = time.monotonic()
        if c != self.here:
            if c == "shallow":
                self.say("You wade into knee-deep water.")
            self.here = c                     # (the land is named once per zone, in update_view)
        if len(self.w.visited) > before and random.random() < 0.15:
            self.say("New land: you're the first to walk here.")
        self.end_turn()

    def travel(self, dx, dy):
        """move one square on the world map; time passes, then you're in that square's zone"""
        tx, ty = self.px // CS + dx, self.py // CS + dy
        if not self.w.inside(tx, ty):
            self.say("Nothing but open sea that way.")
            return
        b = str(self.w.wd.biome[ty, tx])
        if b in ("deep", "ocean", "shallow", "seaice"):
            self.say("You'd need a boat to cross the water.")
            return
        if b in ("peak", "lava", "volcano"):
            self.say({"peak": "The peaks are impassable.", "lava": "A sea of lava blocks the way.",
                      "volcano": "The volcano's heart is far too hot."}[b])
            return
        if any(max(abs(m.x - self.px), abs(m.y - self.py)) <= 3 and m.angry for m in self.w.mobs.values()):
            self.say("You can't slip away while something's on your heels.")
            return
        gx, gy = tx * CS + self.px % CS, ty * CS + self.py % CS
        spot = None
        for r in range(CS):                      # nearest open ground in the new zone
            for oy in range(-r, r + 1):
                for ox in range(-r, r + 1):
                    if max(abs(ox), abs(oy)) == r:
                        x, y = gx + ox, gy + oy
                        if x // CS == tx and y // CS == ty and self.w.cell(x, y) not in BLOCKED and \
                                self.w.cell(x, y) not in ("shallow", "lake", "river") and not self.w.mob_at(x, y):
                            spot = (x, y)
                            break
                if spot:
                    break
            if spot:
                break
        if not spot:
            self.say("You can't find a way in there.")
            return
        self.px, self.py = spot
        self.turn += 60
        c = self.w.cell(self.px, self.py)
        self.here = c
        self.update_view()

    def wait(self):
        if not self.dead and not self.show_map:
            self.end_turn()

    def attack(self, m):
        if self.char:                                       # do one of your weapon's moves
            import charcreate
            style = charcreate.STYLE.get(self.char["look"][1], "unarmed")
            self.anim = (style, random.choice(charcreate.MOVES[style]), time.monotonic())
        hit = min(0.95, max(0.3, 0.82 + (self.lvl - m.sp.defn - m.tier) * 0.04 + (self.stat["AGI"] - 5) * 0.02))
        if not m.angry:
            m.angry = True
            self.say(f"The {m.name} turns on you!")
        if random.random() > hit:
            self.say(f"You miss the {m.name}.")
            return
        d = max(1, random.randint(2, 5) + self.lvl - 1 - m.sp.defn + (self.stat["STR"] - 5) // 2)
        m.hp -= d
        self.flash[m.id] = time.monotonic()
        self.amb.fx("hit")
        if m.hp <= 0:
            self.w.mobs.pop(m.id, None)
            self.w.dead.add(m.id)
            gain = 4 + m.tier * 6 + m.maxhp // 3
            self.xp += gain
            self.say(f"You kill the {m.name}. (+{gain} xp)")
            self.amb.fx("kill", 0.7)
            while self.xp >= self.lvl * 25:
                self.xp -= self.lvl * 25
                self.lvl += 1
                self.maxhp += 4 + self.stat["TOU"] // 2
                self.hp = self.maxhp
                self.say(f"You feel stronger: level {self.lvl}! Fully healed.")
                self.amb.fx("level")
        else:
            self.say(f"You hit the {m.name} for {d}.")

    def end_turn(self):
        self.turn += 1
        occupied = {(m.x, m.y) for m in self.w.mobs.values()} | {(self.px, self.py)}
        near_hostile = False
        for m in list(self.w.mobs.values()):
            dist = max(abs(m.x - self.px), abs(m.y - self.py))
            if dist > ACTIVE:
                continue
            if not m.seen and (m.x, m.y) in self.vis:
                m.seen = True
                self.say(f"You see a {m.name}." + (" It looks hostile." if m.angry else ""))
            if m.sp.slow and self.turn % 2:
                continue
            target = None
            if dist == 1 and m.angry:
                self.hurt_by(m)
                near_hostile = True
                if self.dead:
                    return
                continue
            if m.angry and dist <= m.sp.sight:
                target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied)
                near_hostile = True
            elif m.sp.temper == "timid" and dist <= m.sp.sight:
                target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied, away=True)
            elif random.random() < 0.3:
                tx, ty = m.x + random.randint(-3, 3), m.y + random.randint(-3, 3)
                target = mobs.step_towards(m, tx, ty, self.w.cell, occupied)
            if target:
                occupied.discard((m.x, m.y))
                m.x, m.y = target
                occupied.add(target)
        if not near_hostile and self.turn % 8 == 0 and self.hp < self.maxhp:
            self.hp += 1
        self.update_view()

    def clock(self):
        return im.daytime(200 if self.w.always_day else self.turn)

    def zone_mood(self):
        """the zone's main ground type picks the ambience, so it doesn't flicker as you step between trees and paths"""
        k = (self.px // CS, self.py // CS)
        if getattr(self, "_mood", (None,))[0] != k:
            b = self.w.chunk(*k)
            vals, counts = np.unique(b, return_counts=True)
            order = [str(v) for _, v in sorted(zip(counts, vals), reverse=True)]
            mood = "plaza" if "plaza" in order else next((v for v in order if v not in ("road", "house", "bridge")), order[0])
            self._mood = (k, mood)
        return self._mood[1]

    def update_view(self):
        """what you can see from here, at this time of day"""
        day, phase, r, tint = self.clock()
        r = min(r, im.THICK.get(self.here, 99))
        self.radius = r
        self.vis = im.fov(self.px, self.py, r, self.w.cell)   # all round you, as far as you can see
        self.w.remember(self.vis)
        self.dark = None
        self.amb.area(self.zone_mood(), phase == "Night")
        zx, zy = self.px // CS, self.py // CS                # get the zones round you ready before you get there
        lx, ly = self.px % CS, self.py % CS
        near = [(zx + dx, zy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        near.sort(key=lambda q: abs((q[0] - zx) * CS + CS / 2 - lx - CS / 2 * 0) + abs((q[1] - zy) * CS - ly + CS / 2))
        self.w.prefetch(near)
        zk = (self.px // CS, self.py // CS)
        if zk != getattr(self, "_zone", None):          # new zone: name the land if it's changed, then anything found
            self._zone = zk
            mood = self.zone_mood()
            if mood != getattr(self, "_named", None) and not self.w.showcase:
                self._named = mood
                d = im.describe(mood) if self.turn - self.last_desc.get(mood, -9999) > 150 else None
                if d:
                    self.last_desc[mood] = self.turn
                self.say(NAMES.get(mood, mood) + "." + (" " + d if d else ""))
            if not self.w.showcase and zk not in getattr(self, "_found", set()):
                d = structures.describe(self.w.wd, *zk)
                if d:
                    self._found = getattr(self, "_found", set()) | {zk}
                    self.say(d)
        note = getattr(self.w, "zone_note", None)
        if note:
            n = note(self.px // CS, self.py // CS)
            if n and n != getattr(self, "_note", None):
                self._note = n
                self.say(n)
        if phase != getattr(self, "phase", phase):
            self.say({"Dawn": "The sky pales. Dawn.", "Day": "Full daylight.", "Dusk": "The light goes amber, then violet. Dusk.",
                      "Night": "Night falls. You can barely see past your hands."}[phase])
        self.phase = phase

    def hurt_by(self, m):
        if random.random() > 0.7 - (self.stat["AGI"] - 5) * 0.02:
            self.say(f"The {m.name} misses you.")
            return
        lo, hi = m.dmg()
        d = random.randint(lo, hi)
        self.hp -= d
        self.flash["you"] = time.monotonic()
        self.amb.fx("hurt")
        verb = {"legs": "bites", "wings": "stings", "blob": "burns", "tall": "claws", "tentacle": "lashes",
                "beast": "mauls", "fish": "bites"}.get(m.sp.plan, "hits")
        self.say(f"The {m.name} {verb} you for {d}.")
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
            self.killer = m.name

    def respawn(self):
        self.dead = False
        self.xp = 0
        self.hp = self.maxhp
        self.px, self.py = self.start_spot()
        self.here = self.w.cell(self.px, self.py)
        self.update_view()
        self.say("You wake up back in town, aching all over. (You lost your xp towards the next level.)")
        self.save()

    MOVE_KEYS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
                 pygame.K_a: (-1, 0), pygame.K_d: (1, 0), pygame.K_w: (0, -1), pygame.K_s: (0, 1),
                 pygame.K_KP4: (-1, 0), pygame.K_KP6: (1, 0), pygame.K_KP8: (0, -1), pygame.K_KP2: (0, 1),
                 pygame.K_KP7: (-1, -1), pygame.K_KP9: (1, -1), pygame.K_KP1: (-1, 1), pygame.K_KP3: (1, 1)}

    def blocked(self, x, y):
        """why you can't stand in cell (x, y), or None if you can"""
        if not self.w.inside(x // CS, y // CS):
            return "The edge of the known world. Nothing but sea beyond."
        c = self.w.cell(x, y)
        if (x, y) in self.w.fires and c != "bonfire":
            return "Flames! You keep back from the fire."
        if c in BLOCKED:
            return BLOCKED[c]
        if c in structures.BLOCKING:
            return f"A {structures.PROP_NAMES.get(c[2:], c[2:])} is in the way."
        return None

    def box_cells(self, fx, fy):
        """cells your body overlaps when standing at (fx, fy)"""
        cx, cy = fx + 0.5, fy + 0.5
        b = max(0.18, min(0.4, BODY * self.size / 0.55))       # smaller people fit through tighter gaps
        return {(x, y) for x in range(math.floor(cx - b), math.floor(cx + b) + 1)
                for y in range(math.floor(cy - b), math.floor(cy + b) + 1)}

    def sync(self):
        if (self.px, self.py) != self._cell:          # moved by something else (respawn, travel, loading)
            self.fx, self.fy = float(self.px), float(self.py)
            self.vx = self.vy = 0.0
            self._cell = (self.px, self.py)

    def update(self, dt):
        """real time: glide about, bump into things, and let the world take its turns"""
        self.sync()
        if self.dead or self.show_map:
            return
        now = time.monotonic()
        keys = pygame.key.get_pressed()
        ix = iy = 0
        for k, (dx, dy) in self.MOVE_KEYS.items():
            if keys[k]:
                ix += dx
                iy += dy
        ix, iy = max(-1, min(1, ix)), max(-1, min(1, iy))
        if ix or iy:
            n = math.hypot(ix, iy)
            tx, ty = ix / n * SPEED, iy / n * SPEED
            a = min(1.0, dt * ACCEL)
            self.vx += (tx - self.vx) * a
            self.vy += (ty - self.vy) * a
            if (ix, iy) != getattr(self, "facing", None):
                self.facing = (ix, iy)
                self.dark = None
        else:                                          # let go: skate to a stop
            f = math.exp(-dt * FRICTION)
            self.vx *= f
            self.vy *= f
            if abs(self.vx) < 0.05 and abs(self.vy) < 0.05:
                self.vx = self.vy = 0.0
        for axis in (0, 1):                            # move one axis at a time so you slide along walls
            d = (self.vx if axis == 0 else self.vy) * dt
            if not d:
                continue
            nfx, nfy = (self.fx + d, self.fy) if axis == 0 else (self.fx, self.fy + d)
            old = self.box_cells(self.fx, self.fy)
            hit = None
            for q in self.box_cells(nfx, nfy) - old:
                m = self.w.mob_at(*q)
                if m:
                    hit = ("mob", m)
                    break
                why = self.blocked(*q)
                if why:
                    hit = ("wall", why)
                    break
            if hit is None:
                self.fx, self.fy = nfx, nfy
                continue
            if axis == 0:
                self.vx = 0.0
            else:
                self.vy = 0.0
            if hit[0] == "mob":
                if now - getattr(self, "last_attack", 0) >= ATTACK_S:
                    self.last_attack = now
                    self.attack(hit[1])
            else:
                # Corner help: if you're only a little off a gap (a doorway, a path between trees),
                # ease sideways into line with it instead of snagging on the edge.
                if (ix == 0) if axis == 1 else (iy == 0):
                    other = self.fx if axis == 1 else self.fy
                    line = round(other)
                    ahead = (line, self.py + (1 if d > 0 else -1)) if axis == 1 else \
                            (self.px + (1 if d > 0 else -1), line)
                    if abs(other - line) > 0.01 and not self.blocked(*ahead) and not self.w.mob_at(*ahead):
                        step = math.copysign(min(abs(line - other), SPEED * dt), line - other)
                        if axis == 1:
                            self.fx += step
                        else:
                            self.fy += step
                        continue
                if now - getattr(self, "last_bump", 0) > 1.5:
                    self.last_bump = now
                    self.say(hit[1])
        if abs(self.vx) + abs(self.vy) > 0.4:
            self.last_moved = now
        cell = (math.floor(self.fx + 0.5), math.floor(self.fy + 0.5))
        if cell != (self.px, self.py):
            self.enter(*cell)
        if now >= self.next_tick:                      # the world moves on whether you do or not
            self.next_tick = max(self.next_tick + TICK_S, now)
            self.end_turn()

    def enter(self, x, y):
        before = len(self.w.visited)
        self.px, self.py = x, y
        self._cell = (x, y)
        c = self.w.cell(x, y)
        if c != self.here:
            if c == "shallow":
                self.say("You wade into knee-deep water.")
            self.here = c                     # (the land is named once per zone, in update_view)
        self.update_view()
        if len(self.w.visited) > before and random.random() < 0.15:
            self.say("New land: you're the first to walk here.")

    WHISPERS = ["IT SEES YOU.", "the trees are breathing.", "you have been here before.", "don't look behind you.",
                "your hands are not your hands.", "the ground is listening.", "something is wearing the sky.",
                "count your fingers.", "THE STARS ARE WRONG.", "you were never alone out here.", "it remembers your name.",
                "the colours are louder now.", "wake up."]

    def acid(self, t, now, w, h):
        """post effects on the view: ghost trails, colour split, melting waves, glitches, the eye"""
        lvl = getattr(self, "trip", 0)
        if lvl == 0:
            self._ghost = None
            return
        view = self.screen.subsurface((0, HUD_H, w, h))
        if random.random() < 0.0009 * lvl and now > getattr(self, "_eye_until", 0) + 8:   # something watches
            self._eye = (random.randint(80, w - 80), random.randint(60, h - 60), now, random.choice([60, 90, 140]))
            self._eye_until = now + 2.2
        if now < getattr(self, "_eye_until", 0):
            self.draw_eye(view, now)
        g = getattr(self, "_ghost", None)
        if g is not None and g.get_size() == (w, h):              # trails: the last frame lingers
            g.set_alpha((0, 55, 85, 115)[lvl])
            view.blit(g, (0, 0))
        src = view.copy()
        A = (0, 2.0, 3.5, 6.0)[lvl]                                 # melting: strips of rows slide in slow waves
        band = 3
        view.fill((0, 0, 0))
        for y in range(0, h, band):
            sh = int(A * math.sin(y * 0.035 + t * 1.1) + A * 0.6 * math.sin(y * 0.11 - t * 1.9))
            view.blit(src, (sh, y), (0, y, w, band))
        k = (0, 2, 3, 5)[lvl] + int(round(1.5 * math.sin(t * 0.7)))
        if k > 0:                                                   # colour split: red one way, blue the other
            r_ = pygame.surfarray.pixels_red(view)
            r_[k:] = r_[:-k].copy()
            del r_
            b_ = pygame.surfarray.pixels_blue(view)
            b_[:-k] = b_[k:].copy()
            del b_
        if random.random() < 0.0015 * lvl and now > getattr(self, "_glitch_until", 0) + 3:
            self._glitch_until = now + random.uniform(0.12, 0.35)
            self._glitch = random.choice(["tear", "invert", "tear", "burn"])
            if random.random() < 0.35:
                self.say(random.choice(self.WHISPERS))
        if now < getattr(self, "_glitch_until", 0):                 # hallucination
            kind = self._glitch
            src = view.copy()
            for _ in range(random.randint(3, 8)):
                y0 = random.randint(0, h - 20); bh = random.randint(4, 40)
                if kind == "tear":
                    view.blit(src, (random.randint(-80, 80), y0), (0, y0, w, bh))
                elif kind == "invert":
                    view.fill((255, 255, 255), (0, y0, w, bh), special_flags=pygame.BLEND_RGB_SUB)
                    view.blit(src, (0, y0), (0, y0, w, bh), special_flags=pygame.BLEND_RGB_SUB)
                    sub = view.subsurface((0, y0, w, min(bh, h - y0)))
                    inv = pygame.Surface(sub.get_size()); inv.fill((255, 255, 255))
                    inv.blit(src, (0, 0), (0, y0, w, bh), special_flags=pygame.BLEND_RGB_SUB)
                    sub.blit(inv, (0, 0))
                else:
                    view.fill(random.choice([(255, 0, 60), (0, 255, 200), (255, 220, 0)]), (0, y0, w, bh),
                              special_flags=pygame.BLEND_RGB_ADD)
        self._ghost = view.copy()

    def draw_eye(self, view, now):
        """a huge eye opens at the edge of the dark, stares at you, blinks, fades"""
        ex, ey, t0, r = self._eye
        u = (now - t0) / 2.2
        open_ = math.sin(min(1, u) * math.pi)                       # opens then closes
        if 0.45 < u < 0.52:
            open_ *= 0.1                                            # blink
        hh = max(2, int(r * 0.55 * open_))
        s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        c = (r + 2, r + 2)
        a = int(200 * open_)
        pygame.draw.ellipse(s, (235, 230, 210, a), (2, c[1] - hh, r * 2, hh * 2))
        hx = (self.px * PX - ex) * 0.0                               # it looks at you
        pygame.draw.circle(s, (random.choice([180, 200]), 40, 160, a), c, int(r * 0.38))
        pygame.draw.circle(s, (5, 0, 10, a), c, int(r * 0.18))
        pygame.draw.circle(s, (255, 255, 255, a), (c[0] - r // 8, c[1] - r // 8), max(2, r // 14))
        view.blit(s, (ex - c[0], ey - c[1]))

    def set_zoom(self, d):
        self.zoom = max(0, min(len(self.ZOOMS) - 1, getattr(self, "zoom", 2) + d))
        self.dark = None
        self.say(f"Zoom {int(self.ZOOMS[self.zoom] * 100)}%")

    def handle(self, e):
        if self.sizer and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and \
                self.slider_rect().inflate(0, 10).collidepoint(e.pos):
            self.dragging = True
            self.slide_to(e.pos[0])
            return True
        if e.type == pygame.MOUSEMOTION and getattr(self, "dragging", False):
            self.slide_to(e.pos[0])
            return True
        if e.type == pygame.MOUSEBUTTONUP and getattr(self, "dragging", False):
            self.dragging = False
            self.save_settings()
            return True
        if e.type == pygame.MOUSEWHEEL and not self.show_map:
            self.set_zoom(1 if e.y > 0 else -1)
        if e.type == pygame.KEYDOWN:
            k = e.key
            if self.dead:
                if k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.respawn()
                elif k == pygame.K_ESCAPE:
                    return False
                return True
            moves = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
                     pygame.K_a: (-1, 0), pygame.K_d: (1, 0), pygame.K_w: (0, -1), pygame.K_s: (0, 1),
                     pygame.K_h: (-1, 0), pygame.K_l: (1, 0), pygame.K_k: (0, -1), pygame.K_j: (0, 1),
                     pygame.K_KP4: (-1, 0), pygame.K_KP6: (1, 0), pygame.K_KP8: (0, -1), pygame.K_KP2: (0, 1),
                     pygame.K_KP7: (-1, -1), pygame.K_KP9: (1, -1), pygame.K_KP1: (-1, 1), pygame.K_KP3: (1, 1)}
            if k in moves and self.show_map:
                self.travel(*moves[k])
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.show_map:
                self.show_map = False
            elif k in moves:
                pass                                # walking is read from the held keys every frame (update)
            elif k in (pygame.K_KP_PLUS, pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_MINUS, pygame.K_MINUS):
                self.set_zoom(+1 if k in (pygame.K_KP_PLUS, pygame.K_EQUALS, pygame.K_PLUS) else -1)
            elif k == pygame.K_t:
                self.trip = (getattr(self, "trip", 0) + 1) % 4
                self.say(["Trip off. Everything is ordinary. Suspiciously ordinary.", "Trip: mild.", "Trip: strong.",
                          "Trip: full send."][self.trip])
            elif k == pygame.K_z:
                self.sizer = not self.sizer
                if not self.sizer:
                    self.save_settings()
            elif k in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                self.set_size(self.size + (0.05 if k == pygame.K_RIGHTBRACKET else -0.05))
                self.sizer = True
                self.save_settings()
            elif k == pygame.K_n:
                self.say("Sound on." if self.amb.toggle() else "Sound off.")
            elif k == pygame.K_m:
                self.show_map = not self.show_map
                if self.show_map:
                    self.draw_text_center("Drawing the map…")
            elif k in (pygame.K_PERIOD, pygame.K_KP5):
                self.wait()
            elif k == pygame.K_ESCAPE:
                if self.show_map:
                    self.show_map = False
                else:
                    return False
        return True

    # ── drawing ──
    def draw_text_center(self, s):
        img = self.big.render(s, True, (230, 230, 230))
        self.screen.blit(img, img.get_rect(center=self.screen.get_rect().center))
        pygame.display.flip()

    ZOOMS = (0.5, 0.75, 1.0, 1.5, 2.0)

    def draw_world(self):
        """draw the view; zoomed views are drawn at their own size, then scaled to fit"""
        SW, SH = self.screen.get_size()
        VH = SH - HUD_H - LOG_H
        z = self.ZOOMS[getattr(self, "zoom", 2)]
        if z == 1.0:
            S, top, sw, vh = self.screen, HUD_H, SW, VH
        else:
            sw, vh = int(SW / z), int(VH / z)
            if getattr(self, "_view", None) is None or self._view.get_size() != (sw, vh):
                self._view = pygame.Surface((sw, vh)).convert()
            S, top = self._view, 0
        now = time.monotonic()
        t = now - self.t0
        self.sync()
        cxp = int(self.fx * PX) + PX // 2 - sw // 2       # camera: player in the middle
        cyp = int(self.fy * PX) + PX // 2 - vh // 2
        S.fill((0, 0, 0))
        c0x, c0y = cxp // (CS * PX), cyp // (CS * PX)
        c1x, c1y = (cxp + sw) // (CS * PX), (cyp + vh) // (CS * PX)
        S.set_clip(pygame.Rect(0, top, sw, vh))
        pal = [tuple(c) for c in weird.palette(t, getattr(self, "trip", 0))]   # colours cycle every frame
        here = (self.px // CS, self.py // CS)
        for cy in range(c0y, c1y + 1):
            for cx in range(c0x, c1x + 1):
                # your own zone is drawn now if it must be; the ones round it pop in when the builder has them
                srf = self.w.surface(cx, cy) if (cx, cy) == here else self.w.surface_if_ready(cx, cy)
                if srf is None:
                    continue
                srf.set_palette(pal)
                S.blit(srf, (cx * CS * PX - cxp, cy * CS * PX - cyp + top))
        fires = self.draw_live(S, top, t, cxp, cyp, sw, vh, c0x, c0y, c1x, c1y)
        if len(self.mob_pos) > 400:
            self.mob_pos.clear()
        for m in self.w.mobs.values():
            sx, sy = self.mob_pos.get(m.id, (m.x, m.y))       # glide between squares instead of jumping
            if abs(sx - m.x) + abs(sy - m.y) > 3:
                sx, sy = m.x, m.y
            k = min(1.0, (now - getattr(self, "_last_draw", now)) * 12)
            sx, sy = sx + (m.x - sx) * k, sy + (m.y - sy) * k
            self.mob_pos[m.id] = (sx, sy)
            x, y = int(sx * PX) - cxp, int(sy * PX) - cyp + top
            if (m.x, m.y) in self.vis and -PX < x < sw and top - PX < y < top + vh:
                fx_, fy_ = x + PX // 2, y + PX - 4                  # where its feet are
                sh = self.sized("foot", self.foot_shadow())
                S.blit(sh, (fx_ - sh.get_width() // 2, fy_ - sh.get_height() // 2 - 1))
                spr = self.sized(("mob",) + (m.biome, m.n, m.angry), self.mob_sprite(m))
                if now - self.flash.get(m.id, 0) < 0.15:
                    spr = spr.copy(); spr.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
                w_, h_ = spr.get_size()
                S.blit(spr, (fx_ - w_ // 2, fy_ + 4 - h_))
                if m.hp < m.maxhp:
                    bw, by = max(8, w_ - 4), fy_ + 4 - h_ - 4
                    pygame.draw.rect(S, (60, 0, 0), (fx_ - bw // 2, by, bw, 3))
                    pygame.draw.rect(S, (230, 50, 50), (fx_ - bw // 2, by, int(bw * m.hp / m.maxhp), 3))
        self._last_draw = now
        S.blit(self.darkness(cxp, cyp, sw, vh), (-(cxp % PX), top - (cyp % PX)))
        glow = self.glow_frames()
        for (fx, fy) in fires:                           # firelight pushes back the dark
            g = glow[int(t * 7 + fx) % len(glow)]
            S.blit(g, (fx - g.get_width() // 2, fy - g.get_height() // 2), special_flags=pygame.BLEND_ADD)
        hx, hy = int(self.fx * PX) - cxp, int(self.fy * PX) - cyp + top
        z_ = self.size
        feet = hy + PX - 4                                   # your feet stay at the bottom of your square
        mid = feet - int(PX * 0.6 * z_)                      # and the rest of you scales up from there
        sh = self.sized("foot", self.foot_shadow())
        S.blit(sh, (hx + PX // 2 - sh.get_width() // 2, feet - sh.get_height() // 2 - 1))
        if self.char:
            import charcreate
            left = getattr(self, "facing", (1, 0))[0] < 0
            anim = getattr(self, "anim", None)
            if anim and now - anim[2] < 0.55:              # doing a move: draw it live, posed
                u = (now - anim[2]) / 0.55
                pose, fxs, hit = charcreate.pose_for(anim[0], anim[1], u, int(PX * 1.1))
                d = PX * 3
                tmp = pygame.Surface((d, d), pygame.SRCALPHA)
                pose = dict(pose)
                for k_ in ("dx", "wdx"):
                    pose[k_] = pose.get(k_, 0) * 0.35
                charcreate.draw_char(tmp, d // 2, d // 2, max(4, int(PX * 1.1 * z_)), self.char["body"], self.char_look(),
                                     tuple(self.char["skin_rgb"]), None, pose)
                if left:
                    tmp = pygame.transform.flip(tmp, True, False)
                S.blit(tmp, (hx + PX // 2 - d // 2, mid - d // 2))
                if "flash" in [f[0] for f in fxs]:
                    pygame.draw.circle(S, (255, 230, 140), (hx + PX // 2 + int((-PX if left else PX) * z_), mid), max(2, int(5 * z_)))
            else:                                          # fighting-game idle: bounce, squash and stretch, sway
                hs = self.hero_surface(left)
                w0, h0 = hs.get_size()
                walking = now - getattr(self, "last_moved", 0) < 0.22
                b = abs(math.sin(now * (9.0 if walking else 5.0)))       # 0..1, the bounce
                sx = (1 + 0.06 * (0.5 - b)) * z_
                sy = (1 - 0.08 * (0.5 - b)) * z_
                tilt = 3 * math.sin(now * 2.4)
                if walking:
                    tilt += -9 if not left else 9                         # lean into the step
                img = pygame.transform.smoothscale(hs, (max(1, int(w0 * sx)), max(1, int(h0 * sy))))
                img = pygame.transform.rotate(img, tilt)
                lift = int(b * (7 if walking else 4) * z_)
                S.blit(img, (hx + PX // 2 - img.get_width() // 2,
                             mid - lift - img.get_height() // 2 + int((h0 * sy - h0 * z_) / 2)))
        else:
            hs = self.sized("hero-old", self.hero)
            S.blit(hs, (hx + PX // 2 - hs.get_width() // 2, feet + 4 - hs.get_height()))
        S.set_clip(None)
        if S is not self.screen:
            scale = pygame.transform.scale if z > 1 else pygame.transform.smoothscale
            self.screen.blit(scale(S, (SW, VH)), (0, HUD_H))
        self.acid(t, now, SW, VH)
        if now - self.flash.get("you", 0) < 0.2:           # red flash when you're hurt
            ov = pygame.Surface((SW, VH), pygame.SRCALPHA)
            ov.fill((200, 0, 0, 60))
            self.screen.blit(ov, (0, HUD_H))

    def live_frames(self, key):
        if key not in self.live_cache:
            spr, m, kind = self.w.fsprites[key]
            amp = {"tuft": 2.5, "stalks": 2.0, "shroom": 1.0, "orbs": 1.5}.get(kind, 2.5)
            frames, pad = weird.sway_frames(spr, m, weird.palette(0), nf=8, amp=amp, bob=(kind == "orbs"))
            surfs = [self.crunch(pygame.image.frombuffer(a.tobytes(), (a.shape[1], a.shape[0]), "RGBA")) for a in frames]
            self.live_cache[key] = (surfs, pad)
        return self.live_cache[key]

    def crunch(self, srf):
        """(was: chunky pixels; trees and grass stay crisp, only paths are crunched now)"""
        return srf.convert_alpha()

    def glow_frames(self):
        if not hasattr(self, "_glow"):
            out = []
            r = int(PX * 3.2)
            yy, xx = np.mgrid[-r:r, -r:r]
            d = np.sqrt(xx ** 2 + yy ** 2) / r
            for k in (0.8, 0.9, 1.0, 0.85):
                fall = np.clip(1 - d, 0, 1) ** 2 * k
                a = np.zeros((2 * r, 2 * r, 3), np.uint8)
                a[..., 0], a[..., 1], a[..., 2] = (fall * 120).astype(np.uint8), (fall * 60).astype(np.uint8), (fall * 18).astype(np.uint8)
                out.append(pygame.image.frombuffer(a.tobytes(), (2 * r, 2 * r), "RGB").copy())
            self._glow = out
        return self._glow

    def draw_live(self, S, top, t, cxp, cyp, sw, vh, c0x, c0y, c1x, c1y):
        """grass and trees swaying (a gust rolls across the land), fires flickering; returns firelight spots"""
        if not hasattr(self, "live_cache"):
            self.live_cache = {}
            self.fire_surfs = [self.crunch(pygame.image.frombuffer(a.tobytes(), (a.shape[1], a.shape[0]), "RGBA"))
                               for a in weird.fire_frames(11)]
        fires = []
        ylo, yhi = top - 90, top + vh + 10
        for cy in range(c0y - 1, c1y + 2):
            for cx in range(c0x - 1, c1x + 2):
                for (kind, wx, wy, key) in self.w.feats.get((cx, cy), ()):
                    sx, sy = wx - cxp, wy - cyp + top
                    if sx < -90 or sx > sw + 10 or sy < ylo or sy > yhi:
                        continue
                    if kind == "fire":
                        S.blit(self.fire_surfs[int(t * 9 + (wx * 7 + wy * 3) % 6) % 6], (sx, sy))
                        if (wx // PX, wy // PX) in self.vis:
                            fires.append((sx + PX // 2, sy + PX * 3 // 4))
                        continue
                    surfs, pad = self.live_frames(key)
                    phase = t * 1.6 - (wx * 0.0045 + wy * 0.0018)        # the wave travels across the land
                    f = int((phase / 6.2832) % 1 * len(surfs))
                    S.blit(surfs[f], (sx - pad, sy - pad))
        return fires

    def foot_shadow(self):
        if not hasattr(self, "_foot"):
            s = pygame.Surface((PX - 8, 8), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (0, 0, 0, 150), s.get_rect())
            self._foot = s
        return self._foot

    def darkness(self, cxp, cyp, sw, vh):
        """black where you've never looked, dim where you remember, a soft falloff and the time-of-day tint where you see"""
        x0, y0 = cxp // PX, cyp // PX
        key = (x0, y0, sw, vh, self.turn, self.px, self.py)
        if self.dark and self.dark[0] == key:
            return self.dark[1]
        cols, rows = sw // PX + 2, vh // PX + 2
        _, _, _, tint = self.clock()
        a = np.zeros((rows, cols, 4), np.uint8)
        r = max(1, self.radius)
        for j in range(rows):
            for i in range(cols):
                gx, gy = x0 + i, y0 + j
                if (gx, gy) in self.vis:
                    d2 = ((gx - self.px) ** 2 + (gy - self.py) ** 2) / (r * r)
                    a[j, i] = (tint[0], tint[1], tint[2], min(235, int(tint[3] + d2 * 120)))
                elif self.w.was_seen(gx, gy):
                    a[j, i] = (2, 2, 8, 218)
                else:
                    a[j, i] = (0, 0, 0, 255)
        srf = pygame.image.frombuffer(a.tobytes(), (cols, rows), "RGBA")
        srf = pygame.transform.smoothscale(srf, (cols * PX, rows * PX)).convert_alpha()   # soft edges; display format = fast
        self.dark = (key, srf)
        return srf

    def draw_map(self):
        sw, sh = self.screen.get_size()
        m = self.w.world_map()
        avail_w, avail_h = sw - 40, sh - HUD_H - LOG_H - 20
        k = min(avail_w / m.get_width(), avail_h / m.get_height())
        mw, mh = int(m.get_width() * k), int(m.get_height() * k)
        ms = pygame.transform.smoothscale(m, (mw, mh))
        fog = pygame.Surface((mw, mh), pygame.SRCALPHA)
        fog.fill((0, 0, 0, 105))
        tw, th = mw / proto.W, mh / proto.H
        for (cx, cy) in self.w.visited:          # places you've been show clearly
            pygame.draw.rect(fog, (0, 0, 0, 0), (int(cx * tw), int(cy * th), int(tw) + 1, int(th) + 1))
        ms.blit(fog, (0, 0))
        ox, oy = (sw - mw) // 2, HUD_H + 10
        self.screen.fill((0, 0, 0))
        self.screen.blit(ms, (ox, oy))
        if int((time.monotonic() - self.t0) * 3) % 2 == 0:
            x, y = ox + (self.px / CS) * tw, oy + (self.py / CS) * th
            pygame.draw.circle(self.screen, (255, 255, 255), (int(x), int(y)), max(4, int(tw * 0.5)), 2)
        x0, y0 = ox + (self.px // CS) * tw, oy + (self.py // CS) * th
        pygame.draw.rect(self.screen, (255, 255, 255), (int(x0) - 1, int(y0) - 1, int(tw) + 3, int(th) + 3), 1)
        hint = self.font.render("Arrows: travel one square (takes time)   M / Enter: zoom in   Bright = places you've been", True, (170, 170, 170))
        self.screen.blit(hint, (ox, oy + mh + 4))

    def draw_hud(self):
        sw, sh = self.screen.get_size()
        pygame.draw.rect(self.screen, (14, 12, 18), (0, 0, sw, HUD_H))
        pygame.draw.rect(self.screen, (14, 12, 18), (0, sh - LOG_H, sw, LOG_H))
        name = NAMES.get(self.here, self.here)
        self.screen.blit(self.big.render(name, True, (240, 220, 160)), (10, 1))
        bx = 230                                            # health bar
        pygame.draw.rect(self.screen, (60, 10, 14), (bx, 8, 160, 14))
        pygame.draw.rect(self.screen, (220, 50, 60), (bx, 8, int(160 * self.hp / self.maxhp), 14))
        self.screen.blit(self.small.render(f"HP {self.hp}/{self.maxhp}", True, (255, 255, 255)), (bx + 6, 7))
        danger = 1 + self.w.tier(self.px // CS, self.py // CS)
        day, phase, _, _ = self.clock()
        who = f"{self.char['name']} ({self.char['archetype']})   " if self.char else ""
        info = who + f"Lv {self.lvl}   XP {self.xp}/{self.lvl * 25}   Day {day}, {phase}   Danger " + "*" * danger
        self.screen.blit(self.font.render(info, True, (190, 190, 200)), (bx + 175, 5))
        expl = self.font.render(f"Explored {len(self.w.visited)}   Seed {self.w.seed}", True, (110, 110, 120))
        self.screen.blit(expl, (sw - expl.get_width() - 10, 6))
        for n, msg in enumerate(self.msgs):
            col = (225, 225, 225) if n == len(self.msgs) - 1 else (125, 125, 135)
            self.screen.blit(self.font.render(msg, True, col), (10, sh - LOG_H + 2 + n * 19))
        if self.sizer and not self.show_map:
            self.draw_sizer()
        keys = self.small.render("Move: arrows WASD numpad   . wait   +/- zoom   Z size   T trip   M map   N sound   Esc save & quit", True, (100, 100, 110))
        self.screen.blit(keys, (sw - keys.get_width() - 10, sh - 18))

    def draw_death(self):
        sw, sh = self.screen.get_size()
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((20, 0, 0, 190))
        self.screen.blit(ov, (0, 0))
        for i, (s, f, col) in enumerate([("You died.", self.big, (255, 90, 90)),
                                         (f"Killed by a {self.killer} on turn {self.turn}.", self.font, (230, 220, 220)),
                                         ("Press Enter to wake up back in town.   Esc quits.", self.font, (170, 160, 160))]):
            img = f.render(s, True, col)
            self.screen.blit(img, img.get_rect(center=(sw // 2, sh // 2 - 30 + i * 32)))

    def frame(self):
        if self.show_map:
            self.draw_map()
        else:
            self.draw_world()
        self.draw_hud()
        if self.dead:
            self.draw_death()
        pygame.display.flip()
        if time.monotonic() - self.last_save > 30 and not self.dead:
            self.save()


def pick_seed(args):
    if "--seed" in args:
        return int(args[args.index("--seed") + 1])
    if "--new" not in args:
        try:
            with open(os.path.join(ROOT, "current.json")) as f:
                return int(json.load(f)["seed"])
        except (OSError, ValueError, KeyError):
            pass
    return int.from_bytes(os.urandom(3), "little")


def main():
    args = sys.argv[1:]
    os.makedirs(ROOT, exist_ok=True)
    pygame.init()
    pygame.key.set_repeat()                               # off: held keys are read every frame by Game.update
    screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE)
    pygame.display.set_caption("Roguelike prototype")
    if not any(f in args for f in ("--play", "--new", "--seed", "--showcase", "--structures", "--shot")):
        import charcreate                                # the game opens on character creation
        ch = charcreate.run(screen, ROOT)
        if not ch:
            pygame.quit()
            return
        args.append("--new")                             # a new character gets a new world
    screen.fill((0, 0, 0))
    f = pygame.font.Font(None, 36)
    screen.blit(f.render("Making the world…", True, (220, 220, 220)), (40, 40))
    pygame.display.flip()
    if "--structures" in args:
        import showcase
        g = Game(None, screen, world=showcase.StructureShowcase())
        pygame.display.set_caption("Roguelike prototype: structures showcase")
    elif "--showcase" in args:
        import showcase
        g = Game(None, screen, world=showcase.ShowcaseWorld())
        pygame.display.set_caption("Roguelike prototype: biome showcase")
    else:
        g = Game(pick_seed(args), screen)
    g.save()
    if "--shot" in args:                                  # testing: --shot PATH [--moves LRUDW...] [--map]
        for ch in args[args.index("--moves") + 1] if "--moves" in args else "":
            if ch == "W":
                g.wait()
            else:
                g.act(*{"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}[ch])
        g.show_map = "--map" in args
        g.frame()
        pygame.image.save(screen, args[args.index("--shot") + 1])
        g.save()
        print("at", g.px, g.py, g.here, "| hp", g.hp, "lvl", g.lvl, "xp", g.xp, "| mobs loaded", len(g.w.mobs), "|", " / ".join(g.msgs))
        return
    clock = pygame.time.Clock()
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif not g.handle(e):
                running = False
        g.update(min(0.05, clock.get_time() / 1000))
        g.frame()
        clock.tick(60)
    if not g.dead:
        g.save()
    pygame.quit()


if __name__ == "__main__":
    main()
