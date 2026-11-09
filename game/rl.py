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
import buildings                                       # noqa: E402
import items                                           # noqa: E402
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
         "wall": "Wall", "wwall": "Timber wall", "ruin": "Rubble", "floor": "Concrete floor", "wfloor": "Floorboards", "hwall": "House", "hwin": "House", "hdoor": "Doorway", "hfloor": "Indoors",
         "htile": "Kitchen", "hrug": "Indoors", "hcarpet": "Lounge", "hcarpetb": "Bedroom", "hlino": "Kitchen",
         "hbath": "Bathroom", "hconc": "Garage", "gdoor": "Garage", "street": "Street",
         "packed": "Packed earth", "scorch": "Scorched ground", "railh": "Railway", "railv": "Railway",
         "mosaic": "Mosaic floor"}
UNDER = {"road", "trail", "plaza", "house", "bonfire", "bridge"}     # drawn as flowing bands over the land
BLOCKED = {"deep": "The water's too deep to swim.", "ocean": "The water's too deep to swim.",
           "mountain": "The rock face is too steep.", "peak": "The peak is too steep to climb.",
           "house": "Someone lives there.", "lava": "Lava! Far too hot to step in.",
           "river": "The current's too strong to wade. Find a bridge.", "lake": "The lake's too deep to wade.",
           "bonfire": "The bonfire's too hot to stand in.", "wall": "A solid wall.", "wwall": "A timber wall.",
           "ruin": "A heap of rubble and broken wall.", "hwall": "A house wall.",
           "hwin": "A window. Grimy glass; shapes move inside, or don't."}


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
        with open(os.path.join(self.dir, "containers.json"), "w") as f:
            json.dump([[x, y, inv] for (x, y), inv in self.containers().items()], f)

    def containers(self):
        """what's left in every container you've opened: (x, y) -> {item: count}"""
        if not hasattr(self, "_cont"):
            self._cont = {}
            try:
                with open(os.path.join(self.dir, "containers.json")) as f:
                    self._cont = {(x, y): {k: n for k, n in inv.items() if k in items.ITEMS} for x, y, inv in json.load(f)}
            except (OSError, ValueError):
                try:                                     # older saves only knew which ones were searched
                    with open(os.path.join(self.dir, "searched.json")) as f:
                        self._cont = {tuple(q): {} for q in json.load(f)}
                except (OSError, ValueError):
                    pass
        return self._cont

    def searched_set(self):
        return self.containers().keys()

    def houses(self, cx, cy):
        """the houses in a loaded zone: (x0, y0, x1, y1) rects in world cells"""
        if not hasattr(self, "_houses"):
            self._houses = {}
        k = (cx, cy)
        if k not in self._houses:
            codes = self.codes.get(k)
            if codes is None:
                return []
            import buildings
            self._houses[k] = buildings.find(codes, cx * CS, cy * CS)
        return self._houses[k]

    def house_bits(self, rect):
        """(furniture [(x, y, code)], outer doors [(x, y, side)]) of a house, cached"""
        if not hasattr(self, "_hbits"):
            self._hbits = {}
        if rect not in self._hbits:
            x0, y0, x1, y1 = rect
            furn, doors = [], []
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    c = self.cell(x, y)
                    if c.startswith("f_"):
                        furn.append((x, y, c))
                    elif c == "hdoor" and (x in (x0, x1) or y in (y0, y1)):
                        doors.append((x, y, "n" if y == y0 else "s" if y == y1 else "w" if x == x0 else "e"))
            self._hbits[rect] = (furn, doors)
        return self._hbits[rect]

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
                if c in UNDER or c.startswith("p_") or c.startswith("f_") or c in weird.BUILT:
                    win = B[max(0, y - 2):y + 3, max(0, x - 2):x + 3].ravel()
                    want = [w for w in win if (w in weird.WATER) == (c == "bridge") and w not in UNDER
                            and not w.startswith("p_") and not w.startswith("f_") and w not in weird.BUILT]
                    G[y, x] = max(set(want), key=want.count) if want else ("river" if c == "bridge" else "grass")
        zseed = (cx * 7919 + cy * 104729 + self.seed) & 0xFFFFFFFF
        weird.ground_pass(p, G, M, CS, zseed, cx * CS * weird.TS, cy * CS * weird.TS)
        items = []
        dens = self.density(cx, cy)
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
        self.inv, self.food, self.water, self.weapon = {}, 100.0, 100.0, None
        self.show_inv, self.searching = False, None
        self.loot, self.pane, self.sel = None, 1, [0, 0]   # an open container (x, y, code), active pane, selections
        self.cap = 12 + self.stat["STR"] * 1.5             # how much you can carry before you slow down
        st = self.load_state()
        if st:
            self.lvl, self.xp, self.turn = st.get("lvl", 1), st.get("xp", 0), st.get("turn", 0)
            self.maxhp = self.base_hp + (self.lvl - 1) * 6
            self.hp = st.get("hp", self.maxhp)
            self.inv = {k: v for k, v in st.get("inv", {}).items() if k in items.ITEMS}
            self.food, self.water = st.get("food", 100.0), st.get("water", 100.0)
            self.weapon = st.get("weapon") if st.get("weapon") in self.inv else None
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
        return pygame.Rect(12, HUD_H + 14, 280, 70)

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
                       "dead": sorted(self.w.dead), "inv": self.inv, "food": round(self.food, 1),
                       "water": round(self.water, 1), "weapon": self.weapon}, f)
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
        d = max(1, random.randint(2, 5) + self.lvl - 1 - m.sp.defn + (self.stat["STR"] - 5) // 2
                + (items.ITEMS[self.weapon][4].get("dmg", 0) if self.weapon else 0))
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
        self.food = max(0.0, self.food - 0.12)          # ~14 minutes from full to starving
        self.water = max(0.0, self.water - 0.18)        # ~9 minutes from full to parched
        for name, v, low in (("hungry", self.food, "Your stomach growls. Find something to eat."),
                             ("thirsty", self.water, "Your mouth is dry. Find water.")):
            band = 0 if v > 25 else 1 if v > 0 else 2
            if band > getattr(self, "_band_" + name, 0):
                self.say(low if band == 1 else f"You're starving." if name == "hungry" else "You're parched.")
            setattr(self, "_band_" + name, band)
        if (self.food <= 0 or self.water <= 0) and self.turn % 12 == 0:
            self.hp -= 1                                  # wasting away
            self.flash["you"] = time.monotonic()
            if self.hp <= 0:
                self.hp, self.dead = 0, True
                self.killer = "hunger" if self.food <= 0 else "thirst"
                self.say("You collapse.")
                return
        fed = self.food > 20 and self.water > 20
        if fed and not near_hostile and self.turn % 8 == 0 and self.hp < self.maxhp:
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
        vkey = (self.px, self.py, r, tint)
        if vkey != getattr(self, "_vkey", None):           # only look again if you moved or the light changed
            self._vkey = vkey
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
        self.food, self.water = max(self.food, 50.0), max(self.water, 50.0)
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
        if c in buildings.FURN_BLOCK:
            return f"A {buildings.FURN[c][0]} is in the way."
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
        if self.dead or self.show_map or self.show_inv or self.loot:
            return
        now = time.monotonic()
        if self.searching:
            if abs(self.vx) + abs(self.vy) > 1.5:
                self.searching = None
                self.say("You stop searching.")
            elif now - self.searching[3] >= self.SEARCH_S:
                self.finish_search()
        keys = pygame.key.get_pressed()
        ix = iy = 0
        for k, (dx, dy) in self.MOVE_KEYS.items():
            if keys[k]:
                ix += dx
                iy += dy
        ix, iy = max(-1, min(1, ix)), max(-1, min(1, iy))
        if ix or iy:
            n = math.hypot(ix, iy)
            spd = SPEED * (0.55 if items.weight(self.inv) > self.cap else 1.0)   # overloaded: you trudge
            tx, ty = ix / n * spd, iy / n * spd
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

    SEARCH_S = 1.0          # seconds to go through a container

    def container_near(self):
        """the closest container within arm's reach: (x, y, code) or None"""
        cx, cy = self.fx + 0.5, self.fy + 0.5
        best = None
        for y in range(self.py - 1, self.py + 2):
            for x in range(self.px - 1, self.px + 2):
                c = self.w.cell(x, y)
                if c in items.LOOT:
                    d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                    if d < 1.45 and (best is None or d < best[0]):
                        best = (d, x, y, c)
        return best[1:] if best else None

    def thing_name(self, code):
        return items.NAMES.get(code) or structures.PROP_NAMES.get(code[2:], code[2:])

    METAL = {"f_fridge", "f_stove", "f_barrel", "f_sink", "p_barrel", "p_car", "p_truck", "p_hull", "p_pod", "p_panel",
             "p_scrap"}

    def start_search(self):
        if self.dead or self.show_map or self.searching:
            return
        q = self.container_near()
        if not q:
            self.say("There's nothing here to search.")
            return
        x, y, c = q
        if (x, y) in self.w.containers():                 # been through it: just open it again
            self.open_loot(x, y, c)
            return
        self.searching = (x, y, c, time.monotonic())       # looking is instant: open it straight away
        self.finish_search()

    def finish_search(self):
        x, y, c, _ = self.searching
        self.searching = None
        got = items.loot(self.w.seed, c, x, y)
        self.w.containers()[(x, y)] = dict(got)
        self.say(f"You search the {self.thing_name(c)}: " + ("nothing worth taking." if not got else
                                                              f"you find {items.describe(got)}."))
        self.open_loot(x, y, c, found=bool(got))

    def open_loot(self, x, y, c, found=None):
        self.amb.fx("open_metal" if c in self.METAL else "open_wood", 1.8)
        if found is True:
            self.amb.fx("found", 1.5)
        elif found is False:
            self.amb.fx("empty", 1.3)
        self.loot = (x, y, c)
        self.pane = 1 if self.w.containers()[(x, y)] else 0
        self.sel = [0, 0]

    ORDER = {"food": 0, "drink": 1, "medical": 2, "weapon": 3, "part": 4}

    def sorted_items(self, inv):
        return sorted(inv, key=lambda k: (self.ORDER[items.ITEMS[k][1]], items.ITEMS[k][0]))

    def inv_list(self):
        return self.sorted_items(self.inv)

    def pane_inv(self, p):
        return self.inv if p == 0 else self.w.containers()[self.loot[:2]]

    def move_item(self, p, k, all_=False):
        """move one (or the whole stack) from pane p to the other"""
        src, dst = self.pane_inv(p), self.pane_inv(1 - p)
        n = src[k] if all_ else 1
        src[k] -= n
        if src[k] <= 0:
            del src[k]
            if p == 0 and self.weapon == k:
                self.weapon = None
        dst[k] = dst.get(k, 0) + n
        self.amb.fx("take", 1.2)

    def take_all(self):
        box = self.w.containers()[self.loot[:2]]
        if not box:
            return
        for k, n in list(box.items()):
            self.inv[k] = self.inv.get(k, 0) + n
        box.clear()
        self.amb.fx("found", 1.2)
        self.say("You take everything.")

    def use_item(self, k):
        name, kind, _, _, eff = items.ITEMS[k]
        if kind == "weapon":
            self.weapon = None if self.weapon == k else k
            self.say(f"You ready the {name}." if self.weapon else f"You put the {name} away.")
            if self.weapon:
                self.amb.fx("equip", 1.3)
            return
        if kind == "part":
            self.say(f"The {name} might be useful for building something. Keep hold of it.")
            return
        if kind == "medical" and self.hp >= self.maxhp:
            self.say("You're not hurt.")
            return
        self.food = min(100.0, self.food + eff.get("food", 0))
        self.water = min(100.0, self.water + eff.get("water", 0))
        self.hp = min(self.maxhp, self.hp + eff.get("hp", 0))
        self.inv[k] -= 1
        if self.inv[k] <= 0:
            del self.inv[k]
        self.amb.fx({"food": "eat", "drink": "drink", "medical": "heal"}[kind], 1.4)
        self.say({"food": f"You eat the {name}.", "drink": f"You drink the {name}.",
                  "medical": f"You use the {name}. That's better."}[kind])

    def drop_item(self, k):
        self.inv[k] -= 1
        if self.inv[k] <= 0:
            del self.inv[k]
            if self.weapon == k:
                self.weapon = None
        self.say(f"You throw away the {items.ITEMS[k][0]}.")

    def bag_input(self, e):
        """keys and clicks while your bag (and maybe a container) is open, Zomboid-style"""
        lists = [self.inv_list(), self.sorted_items(self.pane_inv(1)) if self.loot else []]
        p = self.pane if self.loot else 0
        if e.type == pygame.MOUSEMOTION and getattr(self, "drag", None):
            self.drag["pos"] = e.pos
            return
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1 and getattr(self, "drag", None):
            d, self.drag = self.drag, None                       # dropped: onto the other list moves it across
            for rect, tp in getattr(self, "_panes", []):
                if rect.collidepoint(e.pos) and tp != d["pane"] and d["key"] in self.pane_inv(d["pane"]):
                    shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
                    self.move_item(d["pane"], d["key"], all_=not shift)
                    self.pane = tp
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, rp, i in getattr(self, "_rows", []):
                if rect.collidepoint(e.pos):
                    if self.loot:                                 # pick it up: drag it to the other list
                        self.drag = {"pane": rp, "key": lists[rp][i], "pos": e.pos, "from": e.pos}
                    double = (rp, i) == getattr(self, "_last_click", (None, None))[:2] and \
                        time.monotonic() - self._last_click[2] < 0.35
                    self._last_click = (rp, i, time.monotonic())
                    self.pane, self.sel[rp] = rp, i
                    if double:                                    # double-click: move it across (or use it)
                        k = lists[rp][i]
                        self.move_item(rp, k) if self.loot else self.use_item(k)
                    break
            for rect, what in getattr(self, "_buttons", []):
                if rect.collidepoint(e.pos):
                    self.take_all() if what == "all" else self.close_bag()
        elif e.type == pygame.KEYDOWN:
            k, lst = e.key, lists[p]
            sel = min(self.sel[p], max(0, len(lst) - 1))
            shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
            if k in (pygame.K_ESCAPE, pygame.K_i, pygame.K_TAB) and not (k == pygame.K_TAB and self.loot):
                self.close_bag()
            elif k in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a) and self.loot and k != pygame.K_a:
                self.pane = 1 - self.pane
            elif k in (pygame.K_UP, pygame.K_w, pygame.K_k) and lst:
                self.sel[p] = (sel - 1) % len(lst)
            elif k in (pygame.K_DOWN, pygame.K_s, pygame.K_j) and lst:
                self.sel[p] = (sel + 1) % len(lst)
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e) and lst:
                if self.loot:
                    self.move_item(p, lst[sel], all_=bool(shift))
                else:
                    self.use_item(lst[sel])
            elif k == pygame.K_u and lst and p == 0:
                self.use_item(lst[sel])
            elif k == pygame.K_t and self.loot:
                self.take_all()
            elif k in (pygame.K_x, pygame.K_d, pygame.K_DELETE) and lst and p == 0:
                self.drop_item(lst[sel])
        for q in ((0, 1) if self.loot else (0,)):                 # keep selections on the list
            n = len(self.inv_list() if q == 0 else self.sorted_items(self.pane_inv(1)))
            self.sel[q] = min(self.sel[q], max(0, n - 1))

    def close_bag(self):
        self.show_inv = False
        self.drag = None
        if self.loot:
            self.amb.fx("take", 0.8)
        self.loot = None

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
        if (self.show_inv or self.loot) and e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                                                       pygame.MOUSEMOTION):
            self.bag_input(e)                                     # the bag (and any open container) has the input
            return True
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
            elif k in (pygame.K_e, pygame.K_SPACE) and not self.show_map:
                self.start_search()
            elif k in (pygame.K_i, pygame.K_TAB) and not self.show_map:
                self.show_inv = True
                self.pane, self.sel = 0, [0, 0]
            elif k == pygame.K_v:
                self.show_mini = not getattr(self, "show_mini", True)
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
        pk = (int(t * 12), getattr(self, "trip", 0))            # colours cycle, ~12 steps a second is plenty
        if getattr(self, "_pal", (None,))[0] != pk:
            self._pal = (pk, [tuple(c) for c in weird.palette(t, pk[1])])
        pal = self._pal[1]
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
        self.draw_furniture(S, top, cxp, cyp, sw, vh, c0x, c0y, c1x, c1y, t)
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
        self.draw_doors(S, top, cxp, cyp, sw, vh, c0x, c0y, c1x, c1y)
        S.blit(self.darkness(cxp, cyp, sw, vh), (-(cxp % PX), top - (cyp % PX)))
        glow = self.glow_frames()
        for (fx, fy) in fires:                           # firelight pushes back the dark
            g = glow[int(t * 7 + fx) % len(glow)]
            S.blit(g, (fx - g.get_width() // 2, fy - g.get_height() // 2), special_flags=pygame.BLEND_ADD)
        for (lx_, ly_, big) in getattr(self, "lamps", []):          # lamps light the room a little
            g = self.lamp_glow(big)
            S.blit(g, (lx_ - g.get_width() // 2, ly_ - g.get_height() // 2), special_flags=pygame.BLEND_ADD)
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
        q = self.container_near() if not (self.show_inv or self.loot) else None
        if q:                                                # what you could search, right where it is
            x, y, c = q
            done = (x, y) in self.w.searched_set()
            X, Y = x * PX - cxp + PX // 2, y * PX - cyp + top
            pygame.draw.rect(S, (240, 220, 150) if not done else (110, 110, 120), (x * PX - cxp + 1, y * PX - cyp + top + 1,
                             PX - 2, PX - 2), 1, border_radius=4)
            left = sum(self.w.containers().get((x, y), {}).values())
            label = ("E  search " if not done else "E  open ") + self.thing_name(c) + \
                (f"  ({left} left)" if done and left else "  (empty)" if done else "")
            img = self.small.render(label, True, (245, 235, 205) if not done else (150, 150, 160))
            bg = pygame.Surface((img.get_width() + 10, img.get_height() + 4), pygame.SRCALPHA)
            bg.fill((10, 8, 14, 200))
            S.blit(bg, (X - bg.get_width() // 2, Y - bg.get_height() - 4))
            S.blit(img, (X - img.get_width() // 2, Y - bg.get_height() - 2))
        if self.searching:
            u = min(1.0, (now - self.searching[3]) / self.SEARCH_S)
            bx, by = hx + PX // 2 - 16, hy - 8
            pygame.draw.rect(S, (20, 18, 26), (bx - 1, by - 1, 34, 6))
            pygame.draw.rect(S, (240, 210, 120), (bx, by, int(32 * u), 4))
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
                    gx_, gy_ = wx // PX, (wy + PX - 1) // PX
                    if not self.w.was_seen(gx_, gy_) and not self.w.was_seen(gx_, gy_ - 1):
                        continue                                    # still in the dark: nothing to draw
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

    def draw_doors(self, S, top, cxp, cyp, sw, vh, c0x, c0y, c1x, c1y):
        """houses have no roofs (you see straight in); their front doors are marked so you can find the way in"""
        for zy in range(c0y, c1y + 1):
            for zx in range(c0x, c1x + 1):
                for rect in self.w.houses(zx, zy):
                    for (dx, dy, side) in self.w.house_bits(rect)[1]:
                        X, Y = dx * PX - cxp, dy * PX - cyp + top
                        if -PX < X < sw and top - PX < Y < top + vh and self.w.was_seen(dx, dy):
                            S.blit(self.door_sprite(side), (X, Y))

    def door_sprite(self, side):
        """a front door you can see from the street"""
        key = ("door", side)
        if key not in self.mob_img:
            s = pygame.Surface((PX, PX), pygame.SRCALPHA)
            pygame.draw.rect(s, (40, 30, 24), (4, 2, PX - 8, PX - 3))            # frame
            pygame.draw.rect(s, (128, 86, 50), (7, 5, PX - 14, PX - 9))          # door
            for x in (11, 16, 21):
                pygame.draw.line(s, (96, 62, 36), (x, 6), (x, PX - 6))
            pygame.draw.circle(s, (220, 190, 110), (PX - 11, PX // 2 + 2), 2)   # handle
            pygame.draw.rect(s, (150, 140, 128), (3, PX - 4, PX - 6, 3))          # step
            rot = {"s": 0, "n": 180, "w": -90, "e": 90}[side]
            self.mob_img[key] = pygame.transform.rotate(s, rot)
        return self.mob_img[key]

    BLANKETS = [(70, 100, 150), (150, 64, 60), (80, 118, 76), (150, 120, 60), (110, 80, 130)]
    FABRIC = [(120, 70, 60), (70, 90, 110), (110, 100, 70)]

    def furn_sprite(self, code, var, face=(0, 0)):
        """furniture, top-down and clean (RimWorld-ish): flat colours, a dark outline, a soft shadow"""
        key = ("furn", code, var, face)
        if key in self.mob_img:
            return self.mob_img[key]
        P_ = PX
        wood, dark, light, ink = (126, 90, 58), (84, 58, 38), (162, 122, 82), (30, 24, 22)
        b = pygame.Surface((P_, P_), pygame.SRCALPHA)
        R = lambda col, r, w=0: pygame.draw.rect(b, col, r, w)
        if code == "f_bed0":                                     # head end: pillow, turned-down sheet
            R(wood, (2, 2, P_ - 4, P_ - 2)); R(ink, (2, 2, P_ - 4, P_ - 2), 1)
            R(dark, (2, 2, P_ - 4, 4))
            R((222, 218, 206), (5, 7, P_ - 10, P_ - 7))
            R((242, 240, 232), (7, 8, P_ - 14, 8)); R((190, 186, 176), (7, 8, P_ - 14, 8), 1)
            R(self.BLANKETS[var % 5], (5, 21, P_ - 10, P_ - 21))
        elif code == "f_bed1":                                   # foot end: blanket, footboard
            R(wood, (2, 0, P_ - 4, P_ - 2)); R(ink, (2, 0, P_ - 4, P_ - 2), 1)
            bl = self.BLANKETS[var % 5]
            R(bl, (5, 0, P_ - 10, P_ - 8))
            R(tuple(int(c * 0.8) for c in bl), (5, P_ - 14, P_ - 10, 2))
            R(dark, (2, P_ - 6, P_ - 4, 4))
        elif code in ("f_tab0", "f_tab1"):                       # a two-seat dining table
            r = (4, 6, P_ - 4, P_ - 12) if code == "f_tab0" else (0, 6, P_ - 4, P_ - 12)
            R(wood, r); R(light, (r[0], r[1], r[2], 3)); R(ink, r, 1)
            if code == "f_tab0":
                pygame.draw.circle(b, (228, 226, 218), (P_ // 2 + 2, P_ // 2), 5)
                pygame.draw.circle(b, (190, 120, 70), (P_ // 2 + 2, P_ // 2), 2)
            else:
                R((200, 200, 210), (P_ // 2 - 5, P_ // 2 - 3, 4, 6))
                pygame.draw.circle(b, (240, 220, 150), (P_ // 2 + 3, P_ // 2 - 1), 2)
        elif code == "f_chair":
            R(wood, (9, 9, 14, 14)); R(ink, (9, 9, 14, 14), 1)
            fx_, fy_ = face                                      # back on the side away from the table
            if fx_ > 0: R(dark, (7, 8, 4, 16))
            elif fx_ < 0: R(dark, (P_ - 11, 8, 4, 16))
            elif fy_ > 0: R(dark, (8, 7, 16, 4))
            else: R(dark, (8, P_ - 11, 16, 4))
        elif code == "f_arm":
            fab = self.FABRIC[var % 3]
            R(fab, (5, 6, P_ - 10, P_ - 9)); R(ink, (5, 6, P_ - 10, P_ - 9), 1)
            R(tuple(int(c * 0.7) for c in fab), (5, 6, P_ - 10, 7))
            R(tuple(int(c * 0.8) for c in fab), (5, 6, 5, P_ - 9)); R(tuple(int(c * 0.8) for c in fab), (P_ - 10, 6, 5, P_ - 9))
            R(tuple(min(255, int(c * 1.15)) for c in fab), (11, 14, P_ - 22, P_ - 19))
        elif code == "f_end":
            R(wood, (8, 8, 16, 16)); R(ink, (8, 8, 16, 16), 1)
            pygame.draw.circle(b, (236, 226, 190), (16, 15), 4)
            pygame.draw.circle(b, (255, 214, 120), (16, 15), 2)
        elif code == "f_dress":
            R(wood, (3, 5, P_ - 6, P_ - 10)); R(ink, (3, 5, P_ - 6, P_ - 10), 1)
            for y in (11, 17, 23):
                pygame.draw.line(b, dark, (5, y), (P_ - 6, y))
                pygame.draw.circle(b, (210, 180, 110), (P_ // 2, y - 3), 1)
        elif code == "f_lamp":
            pygame.draw.circle(b, (60, 52, 46), (16, 18), 5)
            pygame.draw.circle(b, (242, 222, 160), (16, 14), 8); pygame.draw.circle(b, ink, (16, 14), 8, 1)
            pygame.draw.circle(b, (255, 245, 210), (16, 14), 3)
        elif code == "f_stove":
            R((72, 74, 80), (3, 4, P_ - 6, P_ - 8)); R(ink, (3, 4, P_ - 6, P_ - 8), 1)
            for cx_, cy_ in ((10, 11), (22, 11), (10, 22), (22, 22)):
                pygame.draw.circle(b, (40, 40, 44), (cx_, cy_), 4)
                pygame.draw.circle(b, (150, 60, 40) if (cx_ + cy_ + var) % 3 == 0 else (60, 60, 64), (cx_, cy_), 2)
        elif code == "f_shelf":
            R(wood, (2, 3, P_ - 4, 12)); R(ink, (2, 3, P_ - 4, 12), 1)
            cols = [(170, 60, 50), (60, 90, 140), (200, 180, 120), (80, 120, 70), (150, 110, 160)]
            x = 4
            while x < P_ - 6:
                wd_ = 2 + (x * 7 + var) % 3
                R(cols[(x + var) % 5], (x, 5, wd_, 8))
                x += wd_ + 1
        elif code == "f_plant":
            for a in range(7):
                ang = a / 7 * 6.283 + var
                pygame.draw.ellipse(b, (70, 130, 64) if a % 2 else (90, 150, 80),
                                    (16 + math.cos(ang) * 7 - 5, 15 + math.sin(ang) * 7 - 4, 10, 8))
            pygame.draw.circle(b, (170, 92, 60), (16, 17), 6); pygame.draw.circle(b, ink, (16, 17), 6, 1)
            pygame.draw.circle(b, (64, 46, 34), (16, 17), 4)
            pygame.draw.circle(b, (100, 170, 90), (16, 16), 3)
        elif code == "f_crate":
            R(light, (5, 5, P_ - 10, P_ - 10)); R(ink, (5, 5, P_ - 10, P_ - 10), 1)
            R(wood, (5, 5, P_ - 10, P_ - 10), 2)
            pygame.draw.line(b, wood, (6, 6), (P_ - 7, P_ - 7), 2); pygame.draw.line(b, wood, (P_ - 7, 6), (6, P_ - 7), 2)
        elif code in ("f_sofa0", "f_sofa1"):                    # 70s sofa, back to the wall: brown cord
            fab = (150, 92, 50) if var % 2 else (120, 80, 60)
            hi = tuple(min(255, int(c * 1.18)) for c in fab)
            r = (3, 4, P_ - 3, P_ - 8) if code == "f_sofa0" else (0, 4, P_ - 3, P_ - 8)
            R(fab, r); R(ink, r, 1)
            R(tuple(int(c * 0.7) for c in fab), (r[0], 4, r[2], 7))                     # the back
            R(tuple(int(c * 0.85) for c in fab), (3 if code == "f_sofa0" else P_ - 8, 4, 5, P_ - 8))   # the arm
            cx0 = 9 if code == "f_sofa0" else 1
            R(hi, (cx0, 12, P_ - 11, P_ - 18))                                          # seat cushion
            pygame.draw.line(b, fab, (cx0, 16), (cx0 + P_ - 12, 16))
        elif code == "f_tv":                                     # wood-cased telly on legs
            R((96, 64, 40), (5, 7, P_ - 10, P_ - 13)); R(ink, (5, 7, P_ - 10, P_ - 13), 1)
            R((40, 50, 48), (8, 10, P_ - 18, P_ - 19)); R((70, 92, 86), (9, 11, 6, 3))
            for k in range(2):
                pygame.draw.circle(b, (200, 180, 120), (P_ - 9, 12 + k * 5), 1)
            pygame.draw.line(b, (30, 30, 30), (P_ // 2, 7), (P_ // 2 - 5, 2)); pygame.draw.line(b, (30, 30, 30), (P_ // 2, 7), (P_ // 2 + 5, 2))
        elif code == "f_ctable":                                 # smoked-glass coffee table
            R((70, 60, 54), (6, 9, P_ - 12, P_ - 18)); R(ink, (6, 9, P_ - 12, P_ - 18), 1)
            R((110, 104, 98), (8, 11, P_ - 16, 3))
            pygame.draw.circle(b, (200, 120, 60), (P_ // 2 + 4, P_ // 2 + 1), 2)          # an ashtray
        elif code == "f_fridge":
            R((230, 228, 216), (4, 4, P_ - 8, P_ - 7)); R(ink, (4, 4, P_ - 8, P_ - 7), 1)
            pygame.draw.line(b, (170, 168, 160), (5, 12), (P_ - 6, 12))
            R((150, 150, 156), (P_ - 10, 14, 2, 8))
        elif code == "f_ward":                                   # wardrobe: two doors
            R(dark, (3, 4, P_ - 6, P_ - 8)); R(ink, (3, 4, P_ - 6, P_ - 8), 1)
            R(wood, (4, 5, P_ // 2 - 5, P_ - 10)); R(wood, (P_ // 2 + 1, 5, P_ // 2 - 5, P_ - 10))
            pygame.draw.circle(b, (210, 180, 110), (P_ // 2 - 3, P_ // 2), 1); pygame.draw.circle(b, (210, 180, 110), (P_ // 2 + 3, P_ // 2), 1)
        elif code in ("f_bath0", "f_bath1"):                     # avocado bath
            av = (150, 172, 96)
            r = (5, 3, P_ - 10, P_ - 3) if code == "f_bath0" else (5, 0, P_ - 10, P_ - 4)
            R(av, r); R(ink, r, 1)
            ir = (9, 8, P_ - 18, P_ - 8) if code == "f_bath0" else (9, 0, P_ - 18, P_ - 9)
            R((176, 196, 128), ir)
            if code == "f_bath0":
                R((180, 180, 186), (P_ // 2 - 2, 4, 4, 3))                                # taps
        elif code == "f_wc":                                     # avocado toilet
            av = (150, 172, 96)
            R(av, (9, 4, P_ - 18, 8)); R(ink, (9, 4, P_ - 18, 8), 1)
            pygame.draw.ellipse(b, av, (8, 11, P_ - 16, P_ - 15)); pygame.draw.ellipse(b, ink, (8, 11, P_ - 16, P_ - 15), 1)
            pygame.draw.ellipse(b, (176, 196, 128), (11, 14, P_ - 22, P_ - 21))
        elif code == "f_bench":                                  # workbench with a vice and tools
            R(wood, (2, 6, P_ - 4, P_ - 12)); R(ink, (2, 6, P_ - 4, P_ - 12), 1)
            R((90, 90, 96), (4, 8, 6, 5))
            pygame.draw.line(b, (170, 60, 50), (14, 10), (24, 16), 2); R((120, 120, 128), (12, 18, 12, 2))
        elif code == "f_barrel":                                 # oil drum
            pygame.draw.circle(b, (50, 90, 130), (16, 16), 10); pygame.draw.circle(b, ink, (16, 16), 10, 1)
            pygame.draw.circle(b, (40, 72, 104), (16, 16), 7, 1)
            pygame.draw.circle(b, (20, 20, 22), (20, 12), 2)
        elif code == "f_sink":
            R((214, 214, 222), (4, 6, P_ - 8, P_ - 12)); R(ink, (4, 6, P_ - 8, P_ - 12), 1)
            pygame.draw.ellipse(b, (150, 160, 172), (8, 10, P_ - 16, P_ - 20))
            R((120, 120, 128), (P_ // 2 - 1, 6, 3, 6))
        mask = pygame.mask.from_surface(b)
        out = pygame.Surface((P_, P_), pygame.SRCALPHA)
        out.blit(mask.to_surface(setcolor=(0, 0, 0, 80), unsetcolor=(0, 0, 0, 0)), (2, 3))   # soft shadow
        out.blit(b, (0, 0))
        self.mob_img[key] = out
        return out

    def draw_furniture(self, S, top, cxp, cyp, sw, vh, c0x, c0y, c1x, c1y, t):
        """the furniture in every house in view"""
        self.lamps = []
        for zy in range(c0y, c1y + 1):
            for zx in range(c0x, c1x + 1):
                for rect in self.w.houses(zx, zy):
                    x0, y0, x1, y1 = rect
                    if x0 * PX - cxp > sw or (x1 + 1) * PX - cxp < 0 or y0 * PX - cyp > vh or (y1 + 1) * PX - cyp < 0:
                        continue
                    var = (x0 * 7 + y0 * 13) % 97
                    cx_, cy_ = self.fx + 0.5, self.fy + 0.5
                    lit = True
                    furn = self.w.house_bits(rect)[0]
                    tables = {(x, y) for x, y, c in furn if c in ("f_tab0", "f_tab1")}
                    for (x, y, c) in furn:
                        face = (0, 0)
                        if c == "f_chair":
                            face = next(((dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                         if (x + dx, y + dy) in tables), (0, 1))
                        X, Y = x * PX - cxp, y * PX - cyp + top
                        S.blit(self.furn_sprite(c, var + x * 3 + y, face), (X, Y))
                        if lit and c in ("f_lamp", "f_end") and (x, y) in self.vis:
                            self.lamps.append((X + PX // 2, Y + PX // 2 - 2, c == "f_lamp"))

    def lamp_glow(self, big):
        key = ("lampglow", big)
        if key not in self.mob_img:
            r = int(PX * (2.6 if big else 1.4))
            yy, xx = np.mgrid[-r:r, -r:r]
            f = np.clip(1 - np.sqrt(xx * xx + yy * yy) / r, 0, 1) ** 2      # soft fall-off, no hard edge
            peak = 46 if big else 30
            a = np.dstack([f * peak, f * peak * 0.78, f * peak * 0.42]).astype(np.uint8)
            self.mob_img[key] = pygame.surfarray.make_surface(a.swapaxes(0, 1))
        return self.mob_img[key]

    def foot_shadow(self):
        if not hasattr(self, "_foot"):
            s = pygame.Surface((PX - 8, 8), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (0, 0, 0, 150), s.get_rect())
            self._foot = s
        return self._foot

    def darkness(self, cxp, cyp, sw, vh):
        """black where you've never looked, dim where you remember, a soft falloff and the time-of-day tint where you see"""
        x0, y0 = cxp // PX, cyp // PX
        _, _, _, tint = self.clock()
        key = (x0, y0, sw, vh, self.px, self.py, self.radius, tuple(tint), id(self.vis))
        if self.dark and self.dark[0] == key:
            return self.dark[1]
        cols, rows = sw // PX + 2, vh // PX + 2
        a = np.zeros((rows, cols, 4), np.uint8)
        a[..., 3] = 255                                          # never seen: black
        seen = np.zeros((rows, cols), bool)                      # remembered: copy from each zone's memory
        for zy in range(y0 // CS, (y0 + rows - 1) // CS + 1):
            for zx in range(x0 // CS, (x0 + cols - 1) // CS + 1):
                m = self.w.seen.get((zx, zy))
                if m is None:
                    continue
                gx0, gy0 = max(x0, zx * CS), max(y0, zy * CS)
                gx1, gy1 = min(x0 + cols, zx * CS + CS), min(y0 + rows, zy * CS + CS)
                if gx0 < gx1 and gy0 < gy1:
                    seen[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0] = m[gy0 - zy * CS:gy1 - zy * CS, gx0 - zx * CS:gx1 - zx * CS]
        a[seen] = (2, 2, 8, 218)
        r = max(1, self.radius)
        if getattr(self, "_vis_arr", (None,))[0] is not self.vis:
            v = np.array(list(self.vis), np.int64).reshape(-1, 2)
            self._vis_arr = (self.vis, v[:, 0], v[:, 1])
        _, vx, vy = self._vis_arr
        i, j = vx - x0, vy - y0                                  # where you can see: tint, fading with distance
        on = (i >= 0) & (i < cols) & (j >= 0) & (j < rows)
        i, j = i[on], j[on]
        d2 = ((vx[on] - self.px) ** 2 + (vy[on] - self.py) ** 2) / (r * r)
        a[j, i, 0], a[j, i, 1], a[j, i, 2] = tint[0], tint[1], tint[2]
        a[j, i, 3] = np.minimum(235, (tint[3] + d2 * 120).astype(np.int64))
        srf = pygame.image.frombuffer(a.tobytes(), (cols, rows), "RGBA")
        srf = pygame.transform.smoothscale(srf, (cols * PX, rows * PX)).convert_alpha()   # soft edges; display format = fast
        self.dark = (key, srf)
        return srf

    def draw_map(self):
        """the world map (M): where you've been is clear, the rest dark but faintly there; towns and you marked"""
        sw, sh = self.screen.get_size()
        m = self.w.world_map()
        avail_w, avail_h = sw - 60, sh - HUD_H - LOG_H - 100
        k = min(avail_w / m.get_width(), avail_h / m.get_height())
        mw, mh = int(m.get_width() * k), int(m.get_height() * k)
        key = (mw, mh, len(self.w.visited))
        if getattr(self, "_wmap", (None,))[0] != key:          # rebuild when you've been somewhere new
            ms = pygame.transform.smoothscale(m, (mw, mh))
            fog = pygame.Surface((mw, mh), pygame.SRCALPHA)
            fog.fill((4, 4, 8, 150))
            tw, th = mw / proto.W, mh / proto.H
            for (cx, cy) in self.w.visited:
                pygame.draw.rect(fog, (0, 0, 0, 0), (int(cx * tw), int(cy * th), int(tw) + 1, int(th) + 1))
            ms.blit(fog, (0, 0))
            self._wmap = (key, ms)
        ms = self._wmap[1]
        tw, th = mw / proto.W, mh / proto.H
        ox, oy = (sw - mw) // 2, HUD_H + 40
        self.screen.fill((6, 6, 10))
        self.screen.blit(self.big.render("World map", True, (240, 220, 160)), (ox, HUD_H + 8))
        pygame.draw.rect(self.screen, (90, 82, 66), (ox - 3, oy - 3, mw + 6, mh + 6), 1)
        self.screen.blit(ms, (ox, oy))
        for (tx, ty) in self.w.wd.towns:                        # towns: a little house, bright if you've been
            x, y = int(ox + (tx + 0.5) * tw), int(oy + (ty + 0.5) * th)
            been = (tx, ty) in self.w.visited
            col = (250, 230, 170) if been else (120, 112, 96)
            pygame.draw.polygon(self.screen, col, [(x - 5, y), (x, y - 5), (x + 5, y)])
            pygame.draw.rect(self.screen, col, (x - 4, y, 8, 5))
        x, y = ox + (self.fx / CS) * tw, oy + (self.fy / CS) * th
        pulse = 4 + 2 * abs(math.sin((time.monotonic() - self.t0) * 3))
        pygame.draw.circle(self.screen, (255, 255, 255), (int(x), int(y)), int(pulse) + 3, 2)
        pygame.draw.circle(self.screen, (255, 90, 70), (int(x), int(y)), 3)
        x0, y0 = ox + (self.px // CS) * tw, oy + (self.py // CS) * th
        pygame.draw.rect(self.screen, (255, 255, 255), (int(x0) - 1, int(y0) - 1, int(tw) + 3, int(th) + 3), 1)
        here = str(self.w.wd.biome[self.py // CS, self.px // CS])
        info = f"You are in: {NAMES.get(here, here)}     Explored {len(self.w.visited)} squares     Towns visited " \
               f"{sum(1 for t in self.w.wd.towns if t in self.w.visited)} / {len(self.w.wd.towns)}"
        self.screen.blit(self.font.render(info, True, (210, 205, 195)), (ox, oy + mh + 8))
        hint = self.small.render("Arrows: travel one square (takes time)    M / Enter / Esc: back    "
                                 "Clear = explored, dark = not yet    house = town", True, (150, 145, 140))
        self.screen.blit(hint, (ox, oy + mh + 30))

    MINI_CELLS, MINI_PX = 64, 3                     # the minimap shows 64 x 64 squares round you, 3 px each

    def code_colour(self, c):
        """one colour per kind of square, for the maps"""
        cc = getattr(self, "_ccol", None)
        if cc is None:
            cc = self._ccol = {}
        if c not in cc:
            fixed = {"deep": (16, 34, 80), "ocean": (22, 44, 96), "shallow": (44, 84, 140), "lake": (40, 78, 136),
                     "river": (50, 96, 150), "bridge": (140, 110, 70), "lava": (210, 80, 30), "mountain": (112, 106, 100),
                     "peak": (170, 168, 170), "road": (150, 122, 82), "trail": (120, 98, 70), "street": (74, 76, 86),
                     "plaza": (126, 120, 110), "bonfire": (240, 150, 60), "house": (200, 170, 120),
                     "hwall": (226, 222, 212), "hwin": (150, 200, 230), "hdoor": (170, 116, 64), "gdoor": (140, 140, 150),
                     "hfloor": (132, 96, 62), "hcarpet": (176, 84, 42), "hcarpetb": (122, 142, 64), "hlino": (204, 190, 140),
                     "hbath": (170, 204, 214), "hconc": (112, 112, 118), "htile": (150, 150, 150), "hrug": (150, 50, 50),
                     "wall": (150, 150, 150), "wwall": (130, 96, 60), "ruin": (110, 104, 96), "floor": (96, 96, 100),
                     "wfloor": (110, 84, 56)}
            if c in fixed:
                col = fixed[c]
            elif c.startswith("f_"):
                col = (96, 72, 50)
            elif c.startswith("p_"):
                col = (140, 128, 112)
            elif c in weird.BIOMES:
                col = tuple(int(v) for v in weird.palette(0)[weird.F(weird.BIOMES[c][0], 3)])
            else:
                col = (90, 90, 90)
            cc[c] = np.array(col, np.uint8)
        return cc[c]

    def minimap(self):
        """the squares round you that you've seen, coloured by what they are (rebuilt when you move)"""
        N = self.MINI_CELLS
        key = (self.px, self.py, id(self.vis))
        if getattr(self, "_mini", (None,))[0] == key:
            return self._mini[1]
        x0, y0 = self.px - N // 2, self.py - N // 2
        img = np.zeros((N, N, 3), np.uint8)
        img[:] = (8, 8, 12)
        for zy in range(y0 // CS, (y0 + N - 1) // CS + 1):
            for zx in range(x0 // CS, (x0 + N - 1) // CS + 1):
                codes, seen = self.w.codes.get((zx, zy)), self.w.seen.get((zx, zy))
                if codes is None or seen is None:
                    continue
                gx0, gy0 = max(x0, zx * CS), max(y0, zy * CS)
                gx1, gy1 = min(x0 + N, zx * CS + CS), min(y0 + N, zy * CS + CS)
                if gx0 >= gx1 or gy0 >= gy1:
                    continue
                sub = codes[gy0 - zy * CS:gy1 - zy * CS, gx0 - zx * CS:gx1 - zx * CS]
                sm = seen[gy0 - zy * CS:gy1 - zy * CS, gx0 - zx * CS:gx1 - zx * CS]
                u, inv = np.unique(sub, return_inverse=True)
                lut = np.array([self.code_colour(str(c)) for c in u], np.uint8)
                col = lut[inv.reshape(sub.shape)]
                col[~sm] = (8, 8, 12)                             # never seen: dark
                img[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0] = col
        dim = np.ones((N, N), bool)                               # what you can see now is brighter
        for (gx, gy) in self.vis:
            i, j = gx - x0, gy - y0
            if 0 <= i < N and 0 <= j < N:
                dim[j, i] = False
        img[dim] = (img[dim] * 0.6).astype(np.uint8)
        srf = pygame.image.frombuffer(np.ascontiguousarray(img).tobytes(), (N, N), "RGB")
        srf = pygame.transform.scale(srf, (N * self.MINI_PX, N * self.MINI_PX))
        self._mini = (key, srf)
        return srf

    def draw_minimap(self):
        sw, sh = self.screen.get_size()
        m = self.minimap()
        size = m.get_width()
        r = pygame.Rect(sw - size - 12, HUD_H + 10, size, size)
        pygame.draw.rect(self.screen, (10, 8, 14), r.inflate(8, 8), border_radius=4)
        self.screen.blit(m, r.topleft)
        pygame.draw.rect(self.screen, (110, 100, 80), r.inflate(8, 8), 1, border_radius=4)
        c = (r.x + (self.fx - self.px + self.MINI_CELLS // 2) * self.MINI_PX + 1,
             r.y + (self.fy - self.py + self.MINI_CELLS // 2) * self.MINI_PX + 1)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(c[0]), int(c[1])), 3)
        fx_, fy_ = getattr(self, "facing", (0, 1))
        pygame.draw.line(self.screen, (255, 230, 150), (int(c[0]), int(c[1])), (int(c[0] + fx_ * 7), int(c[1] + fy_ * 7)), 2)
        lab = self.small.render("V hide   M world map", True, (150, 145, 140))
        self.screen.blit(lab, (r.x, r.bottom + 6))

    def draw_hud(self):
        sw, sh = self.screen.get_size()
        pygame.draw.rect(self.screen, (14, 12, 18), (0, 0, sw, HUD_H))
        pygame.draw.rect(self.screen, (14, 12, 18), (0, sh - LOG_H, sw, LOG_H))
        name = NAMES.get(self.here, self.here)
        self.screen.blit(self.big.render(name, True, (240, 220, 160)), (10, 1))
        bx = 200                                            # health, food and water bars
        for i, (lab, v, top_, col, bgc) in enumerate((
                (f"HP {self.hp}/{self.maxhp}", self.hp, self.maxhp, (220, 50, 60), (60, 10, 14)),
                (f"Food {int(self.food)}", self.food, 100, (220, 150, 60), (60, 36, 12)),
                (f"Water {int(self.water)}", self.water, 100, (80, 150, 230), (14, 34, 60)))):
            x, w = bx + i * 118, 110
            low = top_ and v / top_ <= 0.2 and int(time.monotonic() * 3) % 2     # blink when low
            pygame.draw.rect(self.screen, bgc, (x, 8, w, 14))
            pygame.draw.rect(self.screen, (255, 255, 255) if low else col, (x, 8, int(w * max(0, v) / top_), 14))
            self.screen.blit(self.small.render(lab, True, (255, 255, 255)), (x + 5, 7))
        bx += 3 * 118 - 175
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
        if getattr(self, "show_mini", True) and not self.show_map and not (self.show_inv or self.loot):
            self.draw_minimap()
        if self.sizer and not self.show_map:
            self.draw_sizer()
        if self.show_inv or self.loot:
            self.draw_bag()
        keys = self.small.render("Move: arrows/WASD   E search   I inventory   M map   V minimap   . wait   +/- zoom   Z size   N sound   Esc save & quit", True, (100, 100, 110))
        self.screen.blit(keys, (sw - keys.get_width() - 10, sh - 18))

    def item_icon(self, k):
        """a little drawn picture of each kind of item, Zomboid inventory-style"""
        key = ("icon", k)
        if key in self.mob_img:
            return self.mob_img[key]
        Z = 30
        b = pygame.Surface((Z, Z), pygame.SRCALPHA)
        col = items.ITEMS[k][3]
        ink = (24, 20, 22)
        dk = tuple(int(c * 0.65) for c in col)
        lt = tuple(min(255, int(c * 1.3)) for c in col)
        R = lambda c, r, w=0: pygame.draw.rect(b, c, r, w)
        C = lambda c, p, rad, w=0: pygame.draw.circle(b, c, p, rad, w)
        L = lambda c, a, z, w=1: pygame.draw.line(b, c, a, z, w)
        if k == "beans":                                   # a tin with a label
            R((170, 170, 178), (8, 5, 14, 20)); R(col, (8, 10, 14, 10)); R(ink, (8, 5, 14, 20), 1)
            L((210, 210, 216), (9, 6), (20, 6))
        elif k == "jerky":
            pygame.draw.polygon(b, col, [(5, 20), (10, 8), (24, 6), (22, 12), (12, 22)]); pygame.draw.polygon(b, ink, [(5, 20), (10, 8), (24, 6), (22, 12), (12, 22)], 1)
            L(dk, (9, 17), (21, 9))
        elif k == "bread":
            pygame.draw.ellipse(b, col, (4, 9, 22, 13)); pygame.draw.ellipse(b, ink, (4, 9, 22, 13), 1)
            for x in (10, 15, 20):
                L(dk, (x, 11), (x - 2, 17))
        elif k == "fruit":
            C(col, (15, 17), 8); C(ink, (15, 17), 8, 1); C(lt, (12, 14), 2); L((90, 60, 30), (15, 9), (17, 5), 2)
            pygame.draw.ellipse(b, (90, 150, 70), (17, 4, 7, 4))
        elif k in ("water", "tea"):                        # a bottle / flask
            R(col, (10, 9, 10, 17)); R(ink, (10, 9, 10, 17), 1); R((220, 220, 226), (12, 4, 6, 5)); R(ink, (12, 4, 6, 5), 1)
            R(lt, (12, 12, 2, 10))
        elif k == "bandage":
            C(col, (15, 15), 9); C(ink, (15, 15), 9, 1); C((200, 196, 186), (15, 15), 4); C(ink, (15, 15), 4, 1)
        elif k == "medkit":
            R(col, (5, 8, 20, 16)); R(ink, (5, 8, 20, 16), 1); R((240, 240, 240), (13, 11, 4, 10)); R((240, 240, 240), (10, 14, 10, 4))
            R(dk, (12, 5, 6, 3))
        elif k == "knife":
            pygame.draw.polygon(b, col, [(6, 24), (20, 8), (23, 9), (11, 23)]); R((90, 60, 40), (3, 22, 6, 4))
        elif k == "crowbar":
            L(col, (8, 25), (21, 6), 3); L(col, (21, 6), (25, 8), 3); L(col, (8, 25), (5, 22), 3)
        elif k == "pipe":
            L(dk, (5, 24), (24, 6), 6); L(col, (5, 24), (24, 6), 4); L(lt, (6, 22), (22, 7), 1)
        elif k == "scrap":
            pygame.draw.polygon(b, col, [(4, 12), (14, 5), (26, 10), (22, 23), (8, 24)]); pygame.draw.polygon(b, ink, [(4, 12), (14, 5), (26, 10), (22, 23), (8, 24)], 1)
            C(dk, (12, 13), 2); C(dk, (19, 18), 2)
        elif k == "wire":
            for r in (10, 7, 4):
                C(col, (15, 15), r, 2)
        elif k == "battery":
            R(col, (8, 7, 14, 19)); R(ink, (8, 7, 14, 19), 1); R((200, 200, 205), (12, 4, 6, 3)); R(dk, (8, 15, 14, 4))
        elif k == "circuit":
            R(col, (4, 6, 22, 18)); R(ink, (4, 6, 22, 18), 1); R((30, 30, 34), (10, 11, 8, 7))
            for x in (7, 21):
                L((220, 190, 90), (x, 9), (x, 21))
        elif k == "cloth":
            R(col, (5, 10, 20, 12)); R(ink, (5, 10, 20, 12), 1); C(lt, (25, 16), 6); C(ink, (25, 16), 6, 1)
        elif k == "rope":
            for i, r in enumerate((11, 8, 5)):
                C(col if i % 2 == 0 else dk, (15, 15), r, 3)
        elif k == "fuel":
            pygame.draw.rect(b, col, (8, 5, 14, 21), border_radius=3)
            pygame.draw.rect(b, ink, (8, 5, 14, 21), 1, border_radius=3); R(dk, (11, 11, 8, 9)); L(ink, (15, 12), (15, 18))
        else:
            R(col, (7, 7, 16, 16)); R(ink, (7, 7, 16, 16), 1)
        self.mob_img[key] = b
        return b

    def draw_bag(self):
        """your bag, and the open container beside it (Project Zomboid-style lists: icon, name, category, weight)"""
        sw, sh = self.screen.get_size()
        self._rows, self._buttons, self._panes = [], [], []
        top_, avail = HUD_H + 14, sh - HUD_H - LOG_H - 28
        panes = [(0, "Inventory", self.inv)]
        if self.loot:
            x, y, c = self.loot
            panes.append((1, self.thing_name(c).capitalize(), self.w.containers()[(x, y)]))
        W = 420
        gap = 16
        x0 = (sw - (W * len(panes) + gap * (len(panes) - 1))) // 2
        heads = {"food": "Food", "drink": "Drink", "medical": "Medical", "weapon": "Weapon", "part": "Part"}
        for pi, (p, title, inv) in enumerate(panes):
            r = pygame.Rect(x0 + pi * (W + gap), top_, W, avail)
            self._panes.append((r, p))
            active = (self.pane if self.loot else 0) == p
            d = getattr(self, "drag", None)
            if d and d["pane"] != p and r.collidepoint(d["pos"]):
                active = True                                    # you're dragging over it: light it up
            panel = pygame.Surface(r.size, pygame.SRCALPHA)
            panel.fill((22, 22, 26, 238))
            self.screen.blit(panel, r.topleft)
            pygame.draw.rect(self.screen, (120, 110, 90) if active else (60, 58, 66), r, 2 if active else 1)
            pygame.draw.rect(self.screen, (38, 36, 44), (r.x + 1, r.y + 1, W - 2, 26))       # title bar
            self.screen.blit(self.font.render(title, True, (235, 225, 200)), (r.x + 10, r.y + 4))
            kg = items.weight(inv)
            wtxt = f"{kg:.1f} / {self.cap:.0f} kg" if p == 0 else f"{kg:.1f} kg"
            t = self.small.render(wtxt, True, (230, 120, 100) if p == 0 and kg > self.cap else (170, 165, 160))
            self.screen.blit(t, (r.right - t.get_width() - 10, r.y + 7))
            if p == 0:                                    # how full you are
                u = min(1.0, kg / self.cap)
                pygame.draw.rect(self.screen, (50, 48, 56), (r.x + 10, r.y + 30, W - 20, 5))
                pygame.draw.rect(self.screen, (200, 80, 60) if kg > self.cap else (150, 170, 110),
                                 (r.x + 10, r.y + 30, int((W - 20) * u), 5))
            hy = r.y + 40                                  # column headings
            for lab, cx in (("Name", r.x + 46), ("Category", r.x + 262), ("Weight", r.right - 60)):
                self.screen.blit(self.small.render(lab, True, (130, 126, 120)), (cx, hy))
            pygame.draw.line(self.screen, (60, 58, 66), (r.x + 6, hy + 16), (r.right - 6, hy + 16))
            lst = self.sorted_items(inv)
            y = hy + 22
            rows_fit = (r.bottom - 64 - y) // 34
            sel = self.sel[p]
            first = max(0, min(sel - rows_fit // 2, len(lst) - rows_fit))
            if not lst:
                self.screen.blit(self.font.render("Empty" if p == 1 else "Nothing yet.", True, (120, 116, 126)),
                                 (r.x + 46, y + 6))
            for i, k in enumerate(lst[first:first + rows_fit], start=first):
                name, kind, kgs, col, eff = items.ITEMS[k]
                row = pygame.Rect(r.x + 4, y, W - 8, 32)
                if i == sel:
                    pygame.draw.rect(self.screen, (70, 64, 50) if active else (44, 42, 50), row, border_radius=3)
                elif i % 2:
                    pygame.draw.rect(self.screen, (28, 28, 33), row)
                self.screen.blit(self.item_icon(k), (r.x + 10, y + 1))
                label = name + (f"  ({inv[k]})" if inv[k] > 1 else "") + ("  - in hand" if p == 0 and k == self.weapon else "")
                self.screen.blit(self.font.render(label, True, (235, 230, 220)), (r.x + 46, y + 7))
                self.screen.blit(self.small.render(heads[kind], True, (160, 155, 150)), (r.x + 262, y + 9))
                wt = self.small.render(f"{kgs * inv[k]:.1f}", True, (160, 155, 150))
                self.screen.blit(wt, (r.right - 22 - wt.get_width(), y + 9))
                self._rows.append((row, p, i))
                y += 34
            if lst and active:                             # what the chosen thing does
                k = lst[min(sel, len(lst) - 1)]
                eff = items.ITEMS[k][4]
                what = ", ".join(f"+{v} {n}" for n, v in eff.items()) or "Might be useful for building."
                self.screen.blit(self.small.render(what, True, (190, 180, 150)), (r.x + 12, r.bottom - 52))
            if p == 1 and lst:                             # a Take all button, as in Zomboid
                bt = pygame.Rect(r.right - 104, r.bottom - 34, 94, 24)
                pygame.draw.rect(self.screen, (64, 60, 48), bt, border_radius=3)
                pygame.draw.rect(self.screen, (140, 128, 96), bt, 1, border_radius=3)
                tt = self.small.render("Take all (T)", True, (240, 230, 200))
                self.screen.blit(tt, tt.get_rect(center=bt.center))
                self._buttons.append((bt, "all"))
        help_ = ("Drag items across (Shift: one)   Enter move one   Tab switch side   U use   T take all   X throw away   Esc close"
                 if self.loot else "Up/Down choose   Enter use / eat / hold   X throw away   I close")
        d = getattr(self, "drag", None)
        if d and d["pos"] != d["from"] and d["key"] in self.pane_inv(d["pane"]):
            ic = self.item_icon(d["key"])                        # the item under your mouse while you drag it
            self.screen.blit(ic, (d["pos"][0] - 15, d["pos"][1] - 15))
            n = self.pane_inv(d["pane"])[d["key"]]
            if n > 1:
                self.screen.blit(self.small.render(f"x{n}", True, (255, 240, 200)), (d["pos"][0] + 12, d["pos"][1] + 6))
        hs = self.small.render(help_, True, (190, 185, 175))
        hb = pygame.Rect(0, 0, hs.get_width() + 20, hs.get_height() + 6)
        hb.midtop = (sw // 2, top_ + avail + 2)
        pygame.draw.rect(self.screen, (14, 12, 18), hb, border_radius=3)
        self.screen.blit(hs, (hb.x + 10, hb.y + 3))

    def draw_death(self):
        sw, sh = self.screen.get_size()
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((20, 0, 0, 190))
        self.screen.blit(ov, (0, 0))
        for i, (s, f, col) in enumerate([("You died.", self.big, (255, 90, 90)),
                                         (f"Died of {self.killer} on turn {self.turn}." if self.killer in ("hunger", "thirst")
                                          else f"Killed by a {self.killer} on turn {self.turn}.", self.font, (230, 220, 220)),
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
