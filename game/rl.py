#!/usr/bin/env python3
"""Walkable prototype: wander the generated world, meet its creatures, fight.

  rl            character creation (preview)
  rl --play     carry on in your world (makes one the first time)
  rl --new      start a brand new world (new seed)
  rl --seed N   start a world from a given seed

Keys: arrows / WASD / numpad (7 9 1 3 diagonals) move, walk into a creature to attack,
      . or numpad 5 wait a turn, M world map, C outfit (clothes + weapon), Q or Esc closes a menu,
      Esc saves and quits

Turn-based: every step or attack is one turn, then the creatures act.
The world is split into chunks (one world-map tile = 12 x 12 cells). A chunk is generated the first time
it comes near you, then written to disk with the creatures living there, so it never changes after that.
Saves: ~/.local/share/roguelike/
"""
import json, math, os, random, sys, threading, time, warnings
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", message=".*avx2.*")
import numpy as np
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proto                                           # noqa: E402
import weird                                           # noqa: E402
import zonepaint                                       # noqa: E402
import mobs                                            # noqa: E402
import immersion as im                                 # noqa: E402
import structures                                      # noqa: E402
import buildings                                       # noqa: E402
import items                                           # noqa: E402
import heads                                           # noqa: E402
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
         "sdirt": "Shack", "spallet": "Shack", "sdoor": "Doorway", "debris": "Caved-in wall", "mud": "Settlement",
         "shanty": "Settlement",
         "packed": "Packed earth", "scorch": "Scorched ground", "railh": "Railway", "railv": "Railway",
         "mosaic": "Mosaic floor"}
UNDER = zonepaint.UNDER                                 # drawn as flowing bands over the land
BLOCKED = {"deep": "The water's too deep to swim.", "ocean": "The water's too deep to swim.",
           "mountain": "The rock face is too steep.", "peak": "The peak is too steep to climb.",
           "house": "Someone lives there.", "lava": "Lava! Far too hot to step in.",
           "river": "The current's too strong to wade. Find a bridge.", "lake": "The lake's too deep to wade.",
           "bonfire": "The bonfire's too hot to stand in.", "wall": "A solid wall.", "wwall": "A timber wall.",
           "ruin": "A heap of rubble and broken wall.", "hwall": "A house wall.",
           "swall_iron": "Rusted iron sheeting. It groans when you lean on it.", "swall_wood": "Planks, nailed up badly.",
           "swall_tarp": "A tarp stretched over poles. Something on the other side moves with it.",
           "swall_hull": "A plate cut from a ship's hull. Someone scratched marks into it.",
           "sgap": "A hole in the wall, too small to get through. It's dark on the other side.",
           "hwin": "A window. Grimy glass; shapes move inside, or don't."}


def opaque(size):
    """a plain RGB surface with no alpha channel. (On Wayland the display format has alpha, so .convert() surfaces
    come out see-through and drew as black when zoomed.)"""
    return pygame.Surface(size, 0, 32, (0xFF0000, 0x00FF00, 0x0000FF, 0))


def _draw_world_map(seed, folder):
    """(runs in its own process) the world map picture, saved into the world's folder"""
    from PIL import Image
    wd = proto.World(seed)
    img = weird.to_rgb(world8(wd, weird.Species(seed)))
    tmp = os.path.join(folder, "worldmap.tmp.png")
    Image.fromarray(np.ascontiguousarray(img)).save(tmp)
    os.replace(tmp, os.path.join(folder, "worldmap.png"))


def make_pool():
    """two worker processes that paint zone pictures (RL_NOPROC=1 paints them in the game instead)"""
    if os.environ.get("RL_NOPROC"):
        return None
    try:
        import concurrent.futures, multiprocessing
        ctx = multiprocessing.get_context("forkserver")      # (plain fork deadlocked with pygame + threads)
        ctx.set_forkserver_preload(["zonepaint"])
        return concurrent.futures.ProcessPoolExecutor(max_workers=2, mp_context=ctx)
    except Exception:
        return None


class World:
    def __init__(self, seed):
        self.seed = seed
        self.dir = os.path.join(ROOT, f"world-{seed}-z{CS}-w{proto.W}")   # sizes in the name: old saves don't clash
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
        self.pending, self.cv, self.focus = set(), threading.Condition(), None   # zones waiting to be drawn
        self.pool = make_pool()                 # zone pictures are painted in other processes: no stutter here
        if self.pool:
            for _ in range(2):                  # wake the workers now (imports, this world's flora + roads)
                self.pool.submit(zonepaint.warm, seed)
        for _ in range(2 if self.pool else 1):
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

    def close(self):
        """stop the zone painters (no leftover processes)"""
        pool, self.pool = getattr(self, "pool", None), None
        if pool is not None:
            procs = list((getattr(pool, "_processes", None) or {}).values())
            pool.shutdown(wait=False, cancel_futures=True)
            for pr in procs:
                pr.terminate()

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
        here = [m.to_json() for m in list(self.mobs.values()) if not m.id.startswith("enc") and m.x // CS == cx and m.y // CS == cy]
        with open(p + ".tmp", "w") as f:
            seen = [int(sum(1 << i for i in range(CS) if row[i])) for row in self.seen[(cx, cy)]]
            json.dump({"cells": self.codes[(cx, cy)].tolist(), "mobs": here, "seen": seen}, f)
        os.replace(p + ".tmp", p)

    def save(self):
        for (cx, cy) in list(self.codes):                    # (a snapshot: the builders add zones any time)
            if self.inside(cx, cy):
                self.write_chunk(cx, cy)
        with open(os.path.join(self.dir, "built.json"), "w") as f:
            json.dump([[x, y, c, o] for (x, y), (c, o) in self.built_set().items()], f)
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

    def set_cell(self, x, y, code):
        """change one square (building, taking down) and have its zone redrawn in the background"""
        k = (x // CS, y // CS)
        self.chunk(*k)
        self.codes[k][y % CS, x % CS] = code
        if not hasattr(self, "stale"):
            self.stale = set()
        self.stale.add(k)
        for cache in ("_houses", "_hbits", "_furn"):            # what was worked out about this zone is out of date
            if hasattr(self, cache):
                getattr(self, cache).clear()
        with self.cv:
            self.queued.add(k)
            self.pending.add(k)
            self.cv.notify_all()

    def furniture(self, cx, cy):
        """every furniture square in a loaded zone, built or found: [(x, y, code)]"""
        if not hasattr(self, "_furn"):
            self._furn = {}
        k = (cx, cy)
        if k not in self._furn:
            codes = self.codes.get(k)
            if codes is None:
                return []
            ys, xs = np.nonzero(np.char.startswith(codes, "f_"))
            self._furn[k] = [(cx * CS + int(x), cy * CS + int(y), str(codes[y, x])) for y, x in zip(ys, xs)]
        return self._furn[k]

    def built_set(self):
        """squares you built yourself: (x, y) -> code"""
        if not hasattr(self, "_built"):
            try:
                with open(os.path.join(self.dir, "built.json")) as f:
                    self._built = {(d[0], d[1]): (d[2], d[3] if len(d) > 3 else "grass") for d in json.load(f)}
            except (OSError, ValueError):
                self._built = {}
        return self._built

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
                    elif c in ("hdoor", "sdoor") and (x in (x0, x1) or y in (y0, y1)):
                        doors.append((x, y, "n" if y == y0 else "s" if y == y1 else "w" if x == x0 else "e"))
            self._hbits[rect] = (furn, doors)
        return self._hbits[rect]

    def cell(self, gx, gy):
        b = self.chunk(gx // CS, gy // CS)
        return str(b[gy % CS, gx % CS])

    def mob_at(self, x, y):
        for m in list(self.mobs.values()):
            if m.x == x and m.y == y:
                return m
        return None

    def remember(self, cells):
        for (x, y) in cells:
            self.chunk(x // CS, y // CS)
            self.seen[(x // CS, y // CS)][y % CS, x % CS] = True

    def remember_rect(self, x0, y0, x1, y1):
        """mark a whole box of cells as seen, one zone at a time"""
        for zy in range(y0 // CS, (y1 - 1) // CS + 1):
            for zx in range(x0 // CS, (x1 - 1) // CS + 1):
                if (zx, zy) not in self.codes or (zx, zy) not in self.seen:
                    continue                             # not loaded yet: never make a zone just to look at it
                gx0, gy0 = max(x0, zx * CS), max(y0, zy * CS)
                gx1, gy1 = min(x1, zx * CS + CS), min(y1, zy * CS + CS)
                self.seen[(zx, zy)][gy0 - zy * CS:gy1 - zy * CS, gx0 - zx * CS:gx1 - zx * CS] = True

    def was_seen(self, x, y):
        a = self.seen.get((x // CS, y // CS))
        return a is not None and a[y % CS, x % CS]

    def surface(self, cx, cy):
        """the zone as a pygame surface (palette indices; colours come from the cycling palette at draw time).
        Usually already built in the background by the prefetcher; otherwise built now."""
        k = (cx, cy)
        if k in self.surf and k not in getattr(self, "stale", set()):
            return self.surf[k]
        with self.lock:
            done = self.ready.pop(k, None)
        if done is None and k in self.surf:                 # being rebuilt: keep showing the old one meanwhile
            return self.surf[k]
        if k in getattr(self, "stale", set()):
            self.stale.discard(k)
            x0, y0 = cx * CS, cy * CS                        # its fires are re-found from the new build
            self.fires = {f for f in self.fires if not (x0 <= f[0] < x0 + CS and y0 <= f[1] < y0 + CS)}
        if done is None:
            done = self.build(cx, cy, here=True)
        img, feats, fires, fsprites = done
        self.feats[k] = feats
        self.fires |= fires
        self.fsprites.update(fsprites)
        s = pygame.image.frombuffer(img.tobytes(), (CS * weird.TS, CS * weird.TS), "P")
        s.set_palette([tuple(c) for c in weird.palette(0)])
        s = pygame.transform.scale(s, (CS * PX, CS * PX))
        if len(self.surf) > 40:                          # full: forget the zones furthest from this one, not all of them
            far = sorted(self.surf, key=lambda q: -max(abs(q[0] - cx), abs(q[1] - cy)))
            for q in far[:len(self.surf) - 32]:
                del self.surf[q]
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
        """ask the background builder to get these zones ready (the one nearest you is always drawn first)"""
        with self.cv:
            for k in zones:
                if k not in self.surf and k not in self.ready and k not in self.queued and self.inside(*k):
                    self.queued.add(k)
                    self.pending.add(k)
            self.cv.notify_all()

    def _worker(self):
        while True:
            with self.cv:
                while not self.pending:
                    self.cv.wait()
                f = self.focus or next(iter(self.pending))      # (where you are, in zones, with the fraction)
                d = lambda q: math.hypot(q[0] + 0.5 - f[0], q[1] + 0.5 - f[1])
                for q in [q for q in self.pending if d(q) > 3]:      # you've moved on: don't bother with those
                    self.pending.discard(q)
                    self.queued.discard(q)
                if not self.pending:
                    continue
                k = min(self.pending, key=d)
                self.pending.discard(k)
            try:
                if k not in self.surf or k in getattr(self, "stale", set()):
                    out = self.build(*k)
                    with self.lock:
                        self.ready[k] = out
            except Exception:
                pass
            finally:
                self.queued.discard(k)

    def build_inputs(self, cx, cy):
        """what the painter needs: the zone plus a margin of its neighbours (so roads flow across borders), etc."""
        b = self.chunk(cx, cy)
        M = zonepaint.M
        B = np.empty((CS + 2 * M, CS + 2 * M), dtype="<U10")
        B[M:M + CS, M:M + CS] = b
        for y in range(-M, CS + M):
            for x in range(-M, CS + M):
                if not (0 <= x < CS and 0 <= y < CS):
                    gx, gy = cx * CS + x, cy * CS + y
                    B[y + M, x + M] = self.cell(gx, gy) if self.inside(gx // CS, gy // CS) else "deep"
        own = type(self).lines is World.lines and getattr(self, "pool", None) is not None
        roads, trails = (None, None) if own else self.lines(cx, cy)    # (None: the worker traces them itself)
        return (self.seed, cx, cy, B, self.density(cx, cy), roads, trails, proto.W, proto.H)

    def build(self, cx, cy, here=False):
        """draw a zone into a palette-index image: in a worker process if there are any (no stutter), else here.
        here=True: the game is waiting for it right now, so don't queue behind the workers"""
        args = self.build_inputs(cx, cy)
        pool = None if here else getattr(self, "pool", None)
        if args[5] is None and pool is None:
            args = args[:5] + self.lines(cx, cy) + args[7:]
        if pool is not None:
            try:
                return pool.submit(zonepaint.paint_zone, *args).result()
            except Exception:
                self.pool = None                         # workers broke: carry on drawing here
        return zonepaint.paint_zone(*args, species=self.species)

    def world_map(self):
        """the whole world as a picture: drawn once (in the background, at start), then kept in the world's folder"""
        if self.map_img is None:
            path = os.path.join(self.dir, "worldmap.png")
            if os.path.exists(path):
                self.map_img = pygame.image.load(path).convert()
            else:
                p = getattr(self, "_map_proc", None)
                if p:
                    try:
                        p.wait(timeout=20)                     # it's nearly done: wait for it
                    except Exception:
                        pass
                if os.path.exists(path):
                    self.map_img = pygame.image.load(path).convert()
                else:
                    img = weird.to_rgb(world8(self.wd, self.species))
                    self.map_img = pygame.image.frombuffer(np.ascontiguousarray(img).tobytes(),
                                                           (img.shape[1], img.shape[0]), "RGB").copy()
                    pygame.image.save(self.map_img, path)
        return self.map_img

    def start_world_map(self):
        """begin drawing the world map in a separate process (so the game doesn't stutter) so M opens straight away"""
        if os.path.exists(os.path.join(self.dir, "worldmap.png")) or getattr(self, "_map_proc", None):
            return
        import subprocess
        code = (f"import sys; sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__))!r}); "
                f"import rl; rl._draw_world_map({self.seed}, {self.dir!r})")
        self._map_proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)


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
        self.head_out, self.head_ready, self.shots, self.rings, self.zaps = None, 0.0, [], [], []
        self.parts, self.pops, self.clouds, self.shake, self.freeze_until, self.flash_fx = [], [], [], 0.0, 0.0, None
        self.mob_fx = {}                    # mob id -> {"stun": turns, "poison": turns}
        self.intent, self.hello, self.speech = {}, {}, []    # why each sent creature is here; greeters; what they said
        self.next_enc, self.enc_n, self.hunt_signs = 40, 0, set()
        self.tame = set()                   # creature ids that are yours now
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
        self.loot, self.mode, self.picked, self.detail = None, "take", set(), None   # open container, menu state
        self.cap = 12 + self.stat["STR"] * 1.5             # how much you can carry before you slow down
        self.headinfo = (self.char.get("head") or heads.default_head(self.char.get("look"))) if self.char else \
            {"power": "boomerang", "glyph": "頭"}
        self.base_cap = self.cap
        self.jacket, self.trousers = (self.char or {}).get("jacket"), (self.char or {}).get("trousers")
        st = self.load_state()
        if st:
            self.lvl, self.xp, self.turn = st.get("lvl", 1), st.get("xp", 0), st.get("turn", 0)
            self.maxhp = self.base_hp + (self.lvl - 1) * 6
            self.hp = st.get("hp", self.maxhp)
            self.inv = {k: v for k, v in st.get("inv", {}).items() if k in items.ITEMS}
            self.food, self.water = st.get("food", 100.0), st.get("water", 100.0)
            self.tame = set(st.get("tame", []))
            self.weapon = st.get("weapon") if st.get("weapon") in self.inv else None
            self.jacket, self.trousers = st.get("jacket", self.jacket), st.get("trousers", self.trousers)
            self.w.dead = set(st.get("dead", []))
            self.px, self.py = st["px"], st["py"]
            for i in self.w.dead:
                self.w.mobs.pop(i, None)
            self.say("Welcome back.")
        else:
            self.px, self.py = self.start_spot()
            self.hp = self.maxhp
            start_w = (self.char or {}).get("weapon_item")          # the old weapon picked at the start, in hand
            if start_w in items.ITEMS:
                self.inv[start_w] = 1
                self.weapon = start_w
            self.new_story = bool(self.char)                # main() opens a new story on a title card
            who = f"{self.char['name']}, {self.char['archetype'].lower()}, " if self.char else "You "
            self.say(who + ("come" if not self.char else "comes") + " down near a settlement. Smoke, but no voices. "
                     "(M world map, E search, I bag)")
        self.wear()
        if not getattr(self.w, "showcase", False):
            self.w.start_world_map()
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

    def wear(self, jacket=False, trousers=False):
        """put on a jacket / trousers (index, None = your own old clothes; False = keep) and feel the difference"""
        import charcreate
        if jacket is not False:
            self.jacket = jacket
        if trousers is not False:
            self.trousers = trousers
        n = (len(charcreate.JACKETS), len(charcreate.TROUSERS))
        self.jacket = self.jacket if isinstance(self.jacket, int) and 0 <= self.jacket < n[0] else None
        self.trousers = self.trousers if isinstance(self.trousers, int) and 0 <= self.trousers < n[1] else None
        self.armour, speed, carry = charcreate.outfit_bonus(self.jacket, self.trousers)
        self.speed_mul = 1 + speed / 100
        self.cap = self.base_cap + carry

    def char_look(self):
        """in the world you're just your symbol: no gear symbols round it (they stay in the menu)"""
        c = self.char
        return (None, None, None, None, tuple(c["coat"]), tuple(c["trim"]))

    def hero_surface(self, left):
        """you, as your symbol with its gear, facing the way you walk"""
        headon = self.head_out is None
        key = ("hero", left, headon, self.jacket, self.trousers)
        if key not in self.mob_img:
            import charcreate
            s = pygame.Surface((PX * 3, PX * 3), pygame.SRCALPHA)
            charcreate.draw_char(s, PX * 3 // 2, PX * 3 // 2, int(PX * 1.1), self.char["body"], self.char_look(),
                                 tuple(self.char["skin_rgb"]), None, head=self.headinfo["glyph"] if headon else "",
                                 clothes=(self.jacket, self.trousers))
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
        if k not in self.mob_img and getattr(m.sp, "glyph", None):   # the changed: a body kanji like yours, gone wrong
            import charcreate
            c = pygame.Surface((PX * 3, PX * 3), pygame.SRCALPHA)
            charcreate.draw_char(c, PX * 3 // 2, PX * 3 // 2, int(PX * 1.1), m.sp.glyph,
                                 (None, None, None, None, (64, 66, 74), (120, 30, 30)), (168, 166, 160), None, head=m.sp.head)
            box = c.get_bounding_rect()
            body = c.subsurface(box).copy()
            rim = pygame.mask.from_surface(body).to_surface(
                setcolor=(170, 30, 30, 170) if m.angry else (200, 200, 200, 80), unsetcolor=(0, 0, 0, 0))
            out = pygame.Surface((box.w + 2, box.h + 2), pygame.SRCALPHA)
            for ox, oy in ((0, 1), (2, 1), (1, 0), (1, 2)):
                out.blit(rim, (ox, oy))
            out.blit(body, (1, 1))
            self.mob_img[k] = out
        if k not in self.mob_img:
            self.mob_img[k] = self._animal_sprite(m)
            sc = getattr(m.sp, "scale", 1.0)                 # tiny to huge
            if sc != 1.0:
                im_ = self.mob_img[k]
                self.mob_img[k] = pygame.transform.smoothscale(im_, (max(4, int(im_.get_width() * sc)),
                                                                     max(4, int(im_.get_height() * sc))))
        return self.mob_img[k]

    def _animal_sprite(self, m):
        """an animal's sprite from its species' pixel plan"""
        pal = weird.palette(0)
        spr = m.sp.sprite
        img = np.zeros((T, T, 3), np.uint8)
        img[spr == "1"] = pal[weird.F(m.sp.colour, 6)]
        img[spr == "2"] = pal[weird.F(m.sp.colour, 3)]
        img[spr == "3"] = (255, 70, 60) if m.angry else (240, 240, 200)
        img[(img == 0).all(-1) & (spr != ".")] = (1, 1, 1)
        body = spr != "."
        img[body] = np.clip(img[body].astype(int) * 1.5 + 25, 0, 255).astype(np.uint8)   # lifted out of the gloom
        s = pygame.image.frombuffer(img.tobytes(), (T, T), "RGB").copy()
        s.set_colorkey((0, 0, 0))
        s = pygame.transform.scale(s, (PX, PX)).convert_alpha()
        rim = pygame.mask.from_surface(s).to_surface(setcolor=(210, 200, 190, 110), unsetcolor=(0, 0, 0, 0))
        out = pygame.Surface((PX, PX), pygame.SRCALPHA)
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):    # a faint outline so they read in the dark
            out.blit(rim, (ox, oy))
        out.blit(s, (0, 0))
        return out

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
                       "water": round(self.water, 1), "weapon": self.weapon, "tame": sorted(self.tame),
                       "jacket": self.jacket, "trousers": self.trousers}, f)
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
        if any(max(abs(m.x - self.px), abs(m.y - self.py)) <= 3 and m.angry for m in list(self.w.mobs.values())):
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
            style = charcreate.STYLE.get(self.weapon if self.weapon in charcreate.STYLE else self.char["look"][1], "unarmed")
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
        self.damage_mob(m, d)

    def damage_mob(self, m, d, how="hit", quiet=False, power=None):
        """hurt a creature (anime-style: sparks, a number, a jolt); kill it, give xp and level up if it dies"""
        if m.id not in self.w.mobs or (m.id in self.tame and power is not None):
            return                                             # your head never hurts your own animals
        fx = self.mob_fx.get(m.id, {})
        x, y = m.x + 0.5, m.y + 0.3
        if fx.get("frozen") and power != "frost":             # frozen things shatter
            d *= 2
            fx["frozen"], fx["stun"] = False, 0
            self.burst(x, y, (190, 230, 255), 22, 8, 3)
            self.popup(x, y - 0.8, "砕", (190, 230, 255), big=True)
        if not m.angry:
            m.angry = True
        if self.intent.get(m.id) in ("hello", "ambush"):
            self.intent[m.id] = "hunt"
        m.hp -= d
        self.flash[m.id] = time.monotonic()
        col = self.INK.get(power, (240, 230, 210))
        self.burst(x, y, col, 8, 5, 3)
        self.burst(x, y, (30, 24, 28), 5, 3, 3, grav=6)       # ink
        self.popup(x + random.uniform(-0.3, 0.3), y - 0.2, str(d), (255, 230, 120) if d >= 15 else (255, 255, 255), big=d >= 15)
        self.juice(shake=2.5, stop=0.025)
        if not quiet:
            self.amb.fx("hit")
        if m.hp <= 0:
            self.w.mobs.pop(m.id, None)
            self.w.dead.add(m.id)
            self.mob_fx.pop(m.id, None)
            self.burst(x, y, col, 26, 9, 4, life=0.7)
            self.burst(x, y, (20, 16, 20), 18, 6, 4, grav=8, life=0.8)
            self.popup(x, y - 1.0, "滅", (255, 80, 70), big=True)
            if getattr(m.sp, "head", None):                    # its head comes off too, and rolls away
                self.parts.append(dict(x=x, y=y - 0.4, vx=random.uniform(-3, 3), vy=-5, t=0.0, life=1.4, col=(170, 170, 175),
                                       size=0, grav=14, glyph=m.sp.head))
            self.juice(shake=6, stop=0.07)
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
        elif not quiet and how:
            self.say(f"You {how} the {m.name} for {d}.")

    def end_turn(self):
        self.turn += 1
        occupied = {(m.x, m.y) for m in list(self.w.mobs.values())} | {(self.px, self.py)}
        near_hostile = False
        for m in list(self.w.mobs.values()):
            dist = max(abs(m.x - self.px), abs(m.y - self.py))
            if dist > ACTIVE and self.intent.get(m.id) != "hunt":
                continue
            if not m.seen and (m.x, m.y) in self.vis:
                m.seen = True
                self.say(f"You see a {m.name}." + (" It looks hostile." if m.angry else ""))
            for c in self.clouds:
                if math.hypot(m.x + 0.5 - c["x"], m.y + 0.5 - c["y"]) <= c["r"]:
                    self.mob_fx.setdefault(m.id, {})["poison"] = 3
                    self.damage_mob(m, 3, "", power="rot")
                    break
            if m.id not in self.w.mobs:
                continue
            fx = self.mob_fx.get(m.id)
            if fx and fx.get("stun", 0) <= 1:
                fx["frozen"] = False
            if fx:
                if fx.get("poison", 0) > 0:
                    fx["poison"] -= 1
                    self.damage_mob(m, 2, quiet=True)
                    if m.id not in self.w.mobs:
                        continue
                if fx.get("stun", 0) > 0:
                    fx["stun"] -= 1
                    continue
            if self.act_with_intent(m, dist, occupied):
                continue
            if m.sp.slow and self.turn % 2:
                continue
            target = None
            if m.id in self.tame:                              # your animal: guards you, follows you
                foes = [o for o in self.w.mobs.values() if o.angry and o.id not in self.tame and
                        max(abs(o.x - self.px), abs(o.y - self.py)) <= 7]
                if foes:
                    f = min(foes, key=lambda o: max(abs(o.x - m.x), abs(o.y - m.y)))
                    if max(abs(f.x - m.x), abs(f.y - m.y)) <= 1:
                        lo, hi = m.dmg()
                        self.damage_mob(f, random.randint(lo, hi) + 2, "", power=None)
                        self.popup(f.x + 0.5, f.y - 0.4, "咬", (240, 200, 160))
                        continue
                    target = mobs.step_towards(m, f.x, f.y, self.w.cell, occupied)
                elif dist > 2:
                    target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied)
                if target:
                    occupied.discard((m.x, m.y)); m.x, m.y = target; occupied.add(target)
                continue
            if dist == 1 and m.angry and getattr(m.sp, "atk_every", 1) > 1 and (self.turn + hash(m.id)) % m.sp.atk_every:
                continue                                       # gathering itself for the next swing
            if m.sp.temper == "territorial" and not m.angry and dist <= 3:
                m.angry = True
                self.say(f"The {m.name} doesn't want you this close.")
                self.popup(m.x + 0.5, m.y - 0.6, "怒", (230, 90, 60), big=True)
            if dist == 1 and m.angry:
                self.hurt_by(m)
                near_hostile = True
                if self.dead:
                    return
                continue
            sight = 60 if self.intent.get(m.id) == "hunt" else m.sp.sight      # hunters know where you are
            if m.angry and dist <= sight and getattr(m.sp, "pack", False) and dist > 2:
                a_ = (hash(m.id) % 8) * math.pi / 4                # pack: each heads for its own side of you
                target = mobs.step_towards(m, self.px + round(math.cos(a_) * 1.5), self.py + round(math.sin(a_) * 1.5),
                                           self.w.cell, occupied)
                near_hostile = True
                if target and dist > 3 and random.random() < 0.35:   # and lunges
                    occupied.discard((m.x, m.y)); m.x, m.y = target; occupied.add(target)
                    target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied)
            elif m.angry and dist <= sight:
                target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied)
                near_hostile = True
            elif m.sp.temper == "timid" and dist <= m.sp.sight:
                target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied, away=True)
            elif m.sp.temper == "curious" and dist <= m.sp.sight and dist > 2 and random.random() < 0.6:
                target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied)   # comes to have a look
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
        self.director()
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
            if "plaza" in order:
                mood = "plaza"
            elif any(v in order for v in ("sdoor", "bonfire", "mud")):
                mood = "shanty"                          # a settlement
            else:
                skip = {"road", "house", "bridge"} | buildings.HOUSE
                mood = next((v for v in order if v not in skip and not v.startswith(("f_", "p_"))), order[0])
            self._mood = (k, mood)
        return self._mood[1]

    def update_view(self):
        """what you can see from here, at this time of day"""
        day, phase, r, tint = self.clock()
        SW, SH = self.screen.get_size()                  # Qud-style: you see the whole screen (user), no line of sight
        z = self.ZOOMS[getattr(self, "zoom", 2)]
        hw, hh = int(SW / z / PX / 2) + 2, int((SH - HUD_H - LOG_H) / z / PX / 2) + 2
        r = max(hw, hh)
        self.radius = r
        vkey = (self.px, self.py, hw, hh, tint)
        seeing_through_head = self.head_out is not None and self.head_out["kind"] in ("boomerang", "scout")
        if vkey != getattr(self, "_vkey", None) and not seeing_through_head:           # only look again if you moved or the light changed
            self._vkey = vkey
            self.vis = {(x, y) for x in range(self.px - hw, self.px + hw + 1) for y in range(self.py - hh, self.py + hh + 1)}
            self.w.remember_rect(self.px - hw, self.py - hh, self.px + hw + 1, self.py + hh + 1)
            self.dark = None
        self.amb.area(self.zone_mood(), phase == "Night")
        zx, zy = self.px // CS, self.py // CS                # get the zones round you ready before you get there
        lx, ly = self.px % CS, self.py % CS
        near = [(zx + dx, zy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        near.sort(key=lambda q: abs((q[0] - zx) * CS + CS / 2 - lx - CS / 2 * 0) + abs((q[1] - zy) * CS - ly + CS / 2))
        self.w.focus = ((self.fx + 0.5 + self.vx * 1.5) / CS, (self.fy + 0.5 + self.vy * 1.5) / CS)  # where you'll be
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
        if self.head_out and self.head_out["kind"] == "shield" and random.random() < 0.9:
            self.say(f"Your heads take the {m.name}'s blow, and give it back.")
            self.popup(self.fx + 0.5, self.fy - 0.3, "護", self.INK["shield"], big=True)
            self.damage_mob(m, 6 + self.lvl, "", power="shield")
            self.juice(shake=4, stop=0.04)
            return
        if random.random() > 0.7 - (self.stat["AGI"] - 5) * 0.02:
            self.say(f"The {m.name} misses you.")
            return
        lo, hi = m.dmg()
        d = random.randint(lo, hi)
        if getattr(self, "armour", 0) and d > 1:              # your jacket / trousers take some of it
            d = max(1, d - self.armour)
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
        if getattr(self, "cold_open", None):
            return
        if self.dead or self.show_map or self.show_inv or self.loot or getattr(self, "build_menu", False) or \
                getattr(self, "outfit", False):
            return
        now = time.monotonic()
        if now < self.freeze_until:                           # hit-stop: everything holds for a beat
            return
        self.update_head(dt)
        self.update_gather()
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
            spd = SPEED * (0.55 if items.weight(self.inv) > self.cap else 1.0) * getattr(self, "speed_mul", 1.0)
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
                if m and m.id in self.tame:
                    continue                                   # you step round your own animal
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

    METAL = {"f_fridge", "f_stove", "f_barrel", "f_sink", "f_drum", "f_bucket", "f_wbarrel", "p_barrel", "p_car", "p_truck", "p_hull", "p_pod", "p_panel",
             "p_scrap"}

    def animal_near(self):
        """a calm, tameable creature within arm's reach"""
        return next((m for m in self.w.mobs.values() if getattr(m.sp, "tameable", False) and not m.angry and
                     m.id not in self.tame and max(abs(m.x - self.px), abs(m.y - self.py)) <= 1), None)

    def feed(self, m):
        food = next((k for k in ("jerky", "fruit", "bread", "beans") if self.inv.get(k)), None)
        if not food:
            self.say(f"The {m.name} sniffs your empty hands.")
            return
        self.inv[food] -= 1
        if not self.inv[food]:
            del self.inv[food]
        if random.random() < (0.75 if m.sp.temper == "curious" else 0.5):
            self.tame.add(m.id)
            self.say(f"The {m.name} eats from your hand. It decides to stay with you.")
            self.popup(m.x + 0.5, m.y - 0.7, "友", (250, 200, 170), big=True)
            self.amb.fx("found", 1.2)
        else:
            self.say(f"The {m.name} snatches the {items.ITEMS[food][0]} and backs off. Maybe next time.")

    def start_search(self):
        if self.dead or self.show_map or self.searching:
            return
        a_ = self.animal_near()
        if a_ and not self.container_near():
            self.feed(a_)
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
        self.mode, self.picked, self.detail = "take", set(), None

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

    LETTERS = "abcdefghijklmnoprstuvwxyzABCDEFGHIJKLMNOPRSTUVWXYZ"   # no q / Q: Q closes menus

    def menu_inv(self):
        """the things the open menu is listing"""
        if self.loot and getattr(self, "mode", "take") == "take":
            return self.w.containers()[self.loot[:2]]
        return self.inv

    def menu_rows(self):
        """[(kind, data, letter)]: category headings and lettered items, Stone Soup-style"""
        inv, rows, n = self.menu_inv(), [], 0
        last = None
        for k in self.sorted_items(inv):
            cat = items.ITEMS[k][1]
            if cat != last:
                rows.append(("head", cat, None))
                last = cat
            rows.append(("item", k, self.LETTERS[n] if n < len(self.LETTERS) else "?"))
            n += 1
        return rows

    def bag_input(self, e):
        """keys (and clicks) while the inventory or a container's menu is up"""
        rows = self.menu_rows()
        by_letter = {L: k for kind, k, L in rows if kind == "item"}
        key = None
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and getattr(self, "_dos_place", None):
            cx, cy = self.dos.cell_at(e.pos, self._dos_place)
            hit = getattr(self, "_row_at", {}).get(cy)
            if hit and not self.detail:
                key = next(L for L, k in by_letter.items() if k == hit)
        elif e.type == pygame.KEYDOWN:
            key = e.unicode or None
            if e.key in (pygame.K_ESCAPE, pygame.K_q):
                key = "ESC"
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                key = "ENTER"
            elif e.key == pygame.K_TAB:
                key = "TAB"
        if not key:
            return
        if self.detail:                                          # an item's description is open
            k = self.detail
            kind = items.ITEMS[k][1]
            act = {"food": "e", "drink": "e", "medical": "a", "weapon": "w"}.get(kind)
            if key == act:
                self.use_item(k)
                self.detail = None
            elif key == "d":
                self.drop_item(k)
                self.detail = None
            elif key in ("ESC", "ENTER", " "):
                self.detail = None
            return
        if key == "ESC" or (key == "i" and not self.loot):
            self.close_bag()
        elif not self.loot:                                      # the inventory: a letter opens that item
            if key in by_letter:
                self.detail = by_letter[key]
        elif key == "TAB":                                       # switch between taking and putting
            self.mode = "put" if self.mode == "take" else "take"
            self.picked = set()
        elif key in by_letter:
            k = by_letter[key]
            self.picked ^= {k}
            self.amb.fx("take", 0.5)
        elif key in (",", "*"):
            self.picked = set(by_letter.values())
        elif key == "-":
            self.picked = set()
        elif key == "ENTER" and self.picked:
            p = 1 if self.mode == "take" else 0                   # take moves box -> bag; put moves bag -> box
            for k in list(self.picked):
                if k in self.pane_inv(p):
                    self.move_item(p, k, all_=True)
            moved = len(self.picked)
            self.picked = set()
            self.say(("You take " if p == 1 else "You put away ") + f"{moved} thing{'s' if moved > 1 else ''}.")
            if p == 1 and not self.w.containers()[self.loot[:2]]:
                self.close_bag()

    def close_bag(self):
        self.show_inv = False
        if self.loot:
            self.amb.fx("take", 0.8)
        self.loot, self.detail, self.picked = None, None, set()

    # ── your head (anime-strength) ──
    IMPACT = {"boomerang": "斬", "fire": "爆", "frost": "凍", "storm": "轟", "rot": "腐", "shield": "護", "spin": "旋",
              "nova": "叫", "scout": "視"}
    INK = {"boomerang": (240, 220, 190), "fire": (255, 140, 50), "frost": (170, 225, 255), "storm": (255, 250, 150),
           "rot": (150, 210, 80), "shield": (230, 220, 200), "spin": (220, 200, 170), "nova": (255, 255, 255),
           "scout": (255, 70, 60)}

    def head_pos(self):
        """where your head sits on you, in cells"""
        return self.fx + 0.5, self.fy + 0.5 - 0.55 * self.size

    # juice: hit-stop, shake, sparks, flashes, impact kanji, speed lines
    def juice(self, shake=0.0, stop=0.0, flash=None):
        now = time.monotonic()
        self.shake = max(getattr(self, "shake", 0.0), shake)
        if stop:
            self.freeze_until = max(getattr(self, "freeze_until", 0.0), now + stop)
        if flash:
            self.flash_fx = (flash, now)

    def burst(self, x, y, col, n=12, speed=6.0, size=3, grav=0.0, life=0.5):
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            v = random.uniform(0.3, 1.0) * speed
            self.parts.append(dict(x=x, y=y, vx=math.cos(a) * v, vy=math.sin(a) * v, t=0.0, life=life * random.uniform(0.6, 1.2),
                                   col=col, size=size, grav=grav))

    def popup(self, x, y, text, col, big=False):
        self.pops.append(dict(x=x, y=y, text=text, col=col, t=0.0, big=big))

    def knock(self, m, sx, sy, cells=1):
        """push a creature away from (sx, sy), if there's room"""
        for _ in range(cells):
            dx, dy = m.x + 0.5 - sx, m.y + 0.5 - sy
            n = math.hypot(dx, dy) or 1
            nx, ny = m.x + int(round(dx / n)), m.y + int(round(dy / n))
            if (nx, ny) == (m.x, m.y) or self.blocked(nx, ny) or self.w.mob_at(nx, ny) or (nx, ny) == (self.px, self.py):
                return
            m.x, m.y = nx, ny

    def use_head(self, target=None):
        """F: toward where you face; right-click: at the mouse (target = (x, y) in cells)"""
        if self.dead or self.show_map:
            return
        now = time.monotonic()
        pw = self.headinfo["power"]
        P = heads.POWERS[pw]
        if now < self.head_ready or self.head_out:
            return
        hx, hy = self.head_pos()
        if target:
            dx, dy = target[0] - hx, target[1] - hy
        else:
            dx, dy = getattr(self, "facing", (0, 1))
        n = math.hypot(dx, dy) or 1.0
        dx, dy = dx / n, dy / n
        self.head_ready = now + P["cd"]
        dmg = 8 + self.lvl * 3 + max(0, self.stat["WIT"] - 5)
        self.speedlines = now
        if pw == "boomerang":
            self.head_out = dict(kind=pw, x=hx, y=hy, vx=dx * 19, vy=dy * 19, gone=0.0, back=False, hit=set(), spin=0.0,
                                 trail=[], dmg=dmg * 2 + max(0, self.stat["STR"] - 5))
            self.say("You throw your head.")
            self.amb.fx("equip", 1.2)
        elif pw in ("fire", "frost", "storm", "rot"):
            self.head_out = dict(kind="spit", power=pw, x=hx, y=hy, ox=hx, oy=hy, dx=dx, dy=dy, t=0.0, fired=False,
                                 dmg=P["dmg"] * 2 + self.lvl * 2)
        elif pw in ("shield", "spin"):
            self.head_out = dict(kind=pw, ang=math.atan2(dy, dx), t=0.0, dur=P["time"], hitcd={}, trail=[],
                                 x=hx, y=hy, dmg=(9 if pw == "shield" else 13) + self.lvl * 2)
            self.say("Your head lifts off and three of it circle you." if pw == "shield" else
                     "You swing your head out on its chain.")
        elif pw == "nova":
            self.head_out = dict(kind="scream", x=hx, y=hy, t=0.0, fired=False, dmg=dmg + 9)
        elif pw == "scout":
            tx, ty = (target if target else (hx + dx * 9, hy + dy * 9))
            d_ = math.hypot(tx - hx, ty - hy)
            if d_ > 12:
                tx, ty = hx + (tx - hx) / d_ * 12, hy + (ty - hy) / d_ * 12
            self.head_out = dict(kind=pw, x=hx, y=hy, tx=tx, ty=ty, t=0.0, dur=P["time"], back=False, beam=0.0,
                                 dmg=dmg)
            self.say("Your head drifts off to look. Whatever it sees, it burns.")

    def scream(self, hx, hy, dmg):
        for k in range(3):
            self.rings.append(dict(x=hx, y=hy, t=-0.08 * k, r=6.5, col=(255, 255, 255)))
        hit = 0
        for m in list(self.w.mobs.values()):
            if math.hypot(m.x + 0.5 - hx, m.y + 0.5 - hy) <= 6.5:
                self.mob_fx.setdefault(m.id, {})["stun"] = 3
                self.knock(m, hx, hy, 2)
                self.damage_mob(m, dmg, "scream at", power="nova")
                hit += 1
        self.popup(hx, hy - 0.8, "叫", (255, 255, 255), big=True)
        self.juice(shake=14, stop=0.12, flash=(255, 255, 255))
        self.say("Your head screams." + (f" {hit} thing{'s' if hit > 1 else ''} reel{'s' if hit == 1 else ''}." if hit else ""))
        self.amb.fx("hurt", 1.6)

    def explode(self, x, y, power, dmg, radius):
        """what a spat character does when it lands"""
        col = self.INK[power]
        self.burst(x, y, col, n=30, speed=9, size=4, life=0.6)
        self.rings.append(dict(x=x, y=y, t=0.0, r=radius, col=col))
        self.popup(x, y - 0.6, self.IMPACT[power], col, big=True)
        hits = [m for m in list(self.w.mobs.values()) if math.hypot(m.x + 0.5 - x, m.y + 0.5 - y) <= radius]
        if power == "storm":                                 # lightning: jumps on to up to six more
            hits = hits[:1]
            last = hits[0] if hits else None
            done = set(id(h) for h in hits)
            for _ in range(6):
                if not last:
                    break
                nxt = min((o for o in list(self.w.mobs.values()) if id(o) not in done and
                           math.hypot(o.x - last.x, o.y - last.y) < 6.5), default=None,
                          key=lambda o: math.hypot(o.x - last.x, o.y - last.y))
                if not nxt:
                    break
                self.zaps.append(dict(a=(last.x + 0.5, last.y + 0.5), b=(nxt.x + 0.5, nxt.y + 0.5), t=time.monotonic()))
                done.add(id(nxt))
                hits.append(nxt)
                last = nxt
            self.juice(shake=9, stop=0.08, flash=(255, 255, 200))
        elif power == "fire":
            self.juice(shake=8, stop=0.06, flash=(255, 150, 60))
        else:
            self.juice(shake=5, stop=0.05)
        for m in hits:
            fx = self.mob_fx.setdefault(m.id, {})
            if power == "frost":
                fx["stun"], fx["frozen"] = 6, True
            elif power == "rot":
                fx["poison"] = 6
            elif power == "fire":
                self.knock(m, x, y, 1)
            self.damage_mob(m, dmg, {"fire": "burn", "frost": "freeze", "storm": "shock", "rot": "rot"}[power], power=power)
        if power == "rot":                                   # and leaves a cloud that keeps eating
            self.clouds.append(dict(x=x, y=y, r=2.4, until=time.monotonic() + 6))

    def head_hits(self, x, y, seen, dmg, how, power):
        m = self.w.mob_at(int(math.floor(x)), int(math.floor(y)))
        if m and m.id not in seen:
            seen.add(m.id)
            self.knock(m, self.fx + 0.5, self.fy + 0.5, 1)
            self.damage_mob(m, dmg, how, power=power)
            self.popup(x, y - 0.5, self.IMPACT[power], self.INK[power])
            return m
        return None

    def update_head(self, dt):
        """the thrown head, spat characters, orbits, screams, clouds, sparks"""
        now = time.monotonic()
        h = self.head_out
        if h:
            k = h["kind"]
            px_, py_ = self.head_pos()
            if "trail" in h:
                h["trail"] = (h["trail"] + [(h["x"], h["y"])])[-7:]
            if k == "boomerang":
                h["spin"] += dt * 1400
                if not h["back"]:
                    h["x"] += h["vx"] * dt
                    h["y"] += h["vy"] * dt
                    h["gone"] += 19 * dt
                    cell = (int(math.floor(h["x"])), int(math.floor(h["y"])))
                    if h["gone"] > 10 or (self.blocked(*cell) and self.w.cell(*cell) not in ("bonfire",)):
                        h["back"], h["hit"] = True, set()
                        if h["gone"] <= 10:
                            self.burst(h["x"], h["y"], (200, 190, 170), 10, 5)
                    self.head_hits(h["x"], h["y"], h["hit"], h["dmg"], "slice through", "boomerang")
                else:
                    dx, dy = px_ - h["x"], py_ - h["y"]
                    d = math.hypot(dx, dy)
                    if d < 0.6:
                        self.head_out = None
                        self.say("Your head comes back to you.")
                        self._vkey = None
                        self.update_view()
                        return
                    h["x"] += dx / d * min(21 * dt, d)
                    h["y"] += dy / d * min(21 * dt, d)
                    self.head_hits(h["x"], h["y"], h["hit"], h["dmg"], "slice through", "boomerang")
            elif k == "spit":                                 # out a little way, spit, back on
                h["t"] += dt
                t_ = h["t"]
                if t_ < 0.12:
                    u = t_ / 0.12
                    h["x"], h["y"] = h["ox"] + h["dx"] * 0.9 * u, h["oy"] + h["dy"] * 0.9 * u - 0.3 * math.sin(u * math.pi)
                elif not h["fired"]:
                    h["fired"] = True
                    pw = h["power"]
                    spread = (-0.28, 0.0, 0.28) if pw == "fire" else (0.0,)   # fire: a fan of three
                    for off in spread:
                        ca, sa = math.cos(off), math.sin(off)
                        vx, vy = h["dx"] * ca - h["dy"] * sa, h["dx"] * sa + h["dy"] * ca
                        self.shots.append(dict(kind=pw, x=h["x"], y=h["y"], vx=vx * 20, vy=vy * 20, life=0.7,
                                               dmg=h["dmg"], spin=0.0, trail=[]))
                    self.juice(shake=3)
                    self.amb.fx("heal" if pw == "fire" else "equip", 1.0)
                elif t_ > 0.25:
                    dx, dy = px_ - h["x"], py_ - h["y"]
                    d = math.hypot(dx, dy)
                    if d < 0.3 or t_ > 0.8:
                        self.head_out = None
                        return
                    h["x"] += dx / d * min(14 * dt, d)
                    h["y"] += dy / d * min(14 * dt, d)
            elif k == "scream":                               # up off your shoulders, shaking, then back down
                h["t"] += dt
                t_ = h["t"]
                lift = 1.0 * min(1.0, t_ / 0.1) * (1.0 if t_ < 0.5 else max(0.0, 1 - (t_ - 0.5) / 0.2))
                shake = 0.1 * math.sin(t_ * 90) if 0.1 < t_ < 0.5 else 0.0
                h["x"], h["y"] = px_ + shake, py_ - lift
                if t_ >= 0.15 and not h["fired"]:
                    h["fired"] = True
                    self.scream(h["x"], h["y"], h["dmg"])
                if t_ >= 0.7:
                    self.head_out = None
                    return
            elif k in ("shield", "spin"):
                h["t"] += dt
                rad = 1.4 if k == "shield" else 3.2
                h["ang"] += dt * (4.0 if k == "shield" else 8.0)
                ghosts = 3 if k == "shield" else 1
                h["heads"] = []
                for gi in range(ghosts):                       # the shield is three of your head at once
                    a_ = h["ang"] + gi * 2 * math.pi / ghosts
                    hx_, hy_ = px_ + math.cos(a_) * rad, py_ + 0.3 + math.sin(a_) * rad
                    h["heads"].append((hx_, hy_, a_))
                    if k == "spin":                            # the whole chain is the weapon, not just the head
                        caught = [m for m in list(self.w.mobs.values())
                                  if math.hypot(m.x + 0.5 - px_, m.y + 0.5 - py_) <= rad + 0.7 and
                                  abs((math.atan2(m.y + 0.5 - py_, m.x + 0.5 - px_) - a_ + math.pi) % (2 * math.pi) - math.pi) < 0.45]
                    else:
                        m = self.w.mob_at(int(math.floor(hx_)), int(math.floor(hy_)))
                        caught = [m] if m else []
                    for m in caught:
                        if now - h["hitcd"].get(m.id, 0) > 0.35:
                            h["hitcd"][m.id] = now
                            self.knock(m, px_, py_, 1)
                            self.damage_mob(m, h["dmg"], "clip" if k == "shield" else "smash", power=k)
                            if k == "spin":
                                self.popup(m.x + 0.5, m.y - 0.2, self.IMPACT[k], self.INK[k])
                h["x"], h["y"] = h["heads"][0][0], h["heads"][0][1]
                if h["t"] >= h["dur"]:
                    self.head_out = None
                    self.say("Your head settles back on your shoulders.")
            elif k == "scout":
                h["t"] += dt
                tx, ty = (px_, py_) if h["back"] or h["t"] > h["dur"] else (h["tx"], h["ty"])
                dx, dy = tx - h["x"], ty - h["y"]
                d = math.hypot(dx, dy)
                if h["t"] > h["dur"]:
                    h["back"] = True
                if h["back"] and d < 0.6:
                    self.head_out = None
                    self.say("Your head comes home. It's seen things.")
                    self._vkey = None
                    self.update_view()
                    return
                if d > 0.05:
                    h["x"] += dx / d * min(11 * dt, d)
                    h["y"] += dy / d * min(11 * dt, d)
                h["beam"] -= dt                               # whatever it sees, it burns
                if h["beam"] <= 0 and not h["back"]:
                    near = sorted((m for m in list(self.w.mobs.values()) if math.hypot(m.x + 0.5 - h["x"], m.y + 0.5 - h["y"]) < 7.5),
                                  key=lambda m: math.hypot(m.x - h["x"], m.y - h["y"]))[:3]
                    for m in near:
                        self.zaps.append(dict(a=(h["x"], h["y"]), b=(m.x + 0.5, m.y + 0.5), t=now, col=self.INK["scout"], straight=True))
                        self.damage_mob(m, h["dmg"], "burn", power="scout")
                    if near:
                        self.juice(shake=4, stop=0.03)
                        h["beam"] = 0.6
            if self.head_out and k in ("boomerang", "scout"):    # you see from your head, not your eyes
                cell = (int(math.floor(self.head_out["x"])), int(math.floor(self.head_out["y"])))
                if cell != getattr(self, "_headcell", None):
                    self._headcell = cell
                    vis = im.fov(cell[0], cell[1], 7 if k == "scout" else 5, self.w.cell)
                    vis |= {(self.px + a, self.py + b) for a in (-1, 0, 1) for b in (-1, 0, 1)}
                    self.vis = vis
                    self.w.remember(vis)
                    self.dark = None
        for sh in list(self.shots):                          # spat characters
            sh["trail"] = (sh["trail"] + [(sh["x"], sh["y"])])[-6:]
            sh["x"] += sh["vx"] * dt
            sh["y"] += sh["vy"] * dt
            sh["life"] -= dt
            sh["spin"] += dt * 700
            cell = (int(math.floor(sh["x"])), int(math.floor(sh["y"])))
            m = self.w.mob_at(*cell)
            wall = self.blocked(*cell) and self.w.cell(*cell) not in ("bonfire",)
            if m or wall or sh["life"] <= 0:
                self.shots.remove(sh)
                radius = {"fire": 1.8, "frost": 2.6, "storm": 0.6, "rot": 2.2}[sh["kind"]]
                self.explode(sh["x"], sh["y"], sh["kind"], sh["dmg"], radius)
        for r in list(self.rings):
            r["t"] += dt
            if r["t"] > 0.5:
                self.rings.remove(r)
        for p in list(self.parts):
            p["t"] += dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += p["grav"] * dt
            p["vx"] *= 0.9
            p["vy"] *= 0.9 if not p["grav"] else 1.0
            if p["t"] > p["life"]:
                self.parts.remove(p)
        for q in list(self.pops):
            q["t"] += dt
            if q["t"] > (0.9 if q["big"] else 0.7):
                self.pops.remove(q)
        self.clouds = [c for c in self.clouds if c["until"] > now]
        for c in self.clouds:                                 # rot clouds puff
            if random.random() < dt * 20:
                a = random.uniform(0, 2 * math.pi)
                r_ = random.uniform(0, c["r"])
                self.parts.append(dict(x=c["x"] + math.cos(a) * r_, y=c["y"] + math.sin(a) * r_, vx=0, vy=-0.6, t=0.0,
                                       life=0.8, col=(120, 170, 60), size=5, grav=0.0))
        self.zaps = [z for z in self.zaps if now - z["t"] < 0.22]
        self.shake = getattr(self, "shake", 0.0) * math.exp(-dt * 9)

    def draw_head_things(self, S, top, cxp, cyp):
        """the head in flight, orbiting or scouting; spat characters; rings, sparks, beams, impact kanji"""
        import charcreate
        z_ = self.size
        hsz = max(8, int(PX * 1.1 * z_ * 0.44))
        to = lambda x, y: (int(x * PX) - cxp, int(y * PX) - cyp + top)
        skin = tuple(self.char["skin_rgb"]) if self.char else (220, 200, 180)
        now = time.monotonic()
        for c in self.clouds:                                 # rot clouds
            X, Y = to(c["x"], c["y"])
            g = pygame.Surface((int(c["r"] * PX * 2), int(c["r"] * PX * 2)), pygame.SRCALPHA)
            pygame.draw.circle(g, (90, 140, 40, 60), (g.get_width() // 2, g.get_height() // 2), g.get_width() // 2)
            S.blit(g, (X - g.get_width() // 2, Y - g.get_height() // 2))
        if now - getattr(self, "speedlines", 0) < 0.22:       # anime speed lines round you as you use it
            u = (now - self.speedlines) / 0.22
            cx_, cy_ = to(*self.head_pos())
            rnd = random.Random(int(self.speedlines * 1000))
            for _ in range(26):
                a = rnd.uniform(0, 2 * math.pi)
                r0 = PX * (1.4 + 2.5 * u) + rnd.uniform(0, PX)
                r1 = r0 + PX * rnd.uniform(1.5, 4)
                pygame.draw.line(S, (235, 235, 225), (cx_ + math.cos(a) * r0, cy_ + math.sin(a) * r0),
                                 (cx_ + math.cos(a) * r1, cy_ + math.sin(a) * r1), 1 + rnd.randint(0, 1))
        h = self.head_out
        if h:
            for i, (tx_, ty_) in enumerate(h.get("trail", [])):  # afterimages
                g = charcreate.glyph(self.headinfo["glyph"], hsz + 4, skin).copy()
                g.set_alpha(25 + i * 18)
                X, Y = to(tx_, ty_)
                S.blit(g, (X - g.get_width() // 2, Y - g.get_height() // 2))
            if h["kind"] == "spin":                            # the chain
                pX, pY = to(*self.head_pos())
                X, Y = to(h["x"], h["y"])
                pygame.draw.line(S, (150, 150, 160), (pX, pY + 6), (X, Y), 3)
            if h["kind"] == "scout":
                X, Y = to(h["x"], h["y"])
                pygame.draw.circle(S, (120, 40, 40), (X, Y), int(PX * 7.5), 1)
            for (hx_, hy_, a_) in (h.get("heads") or [(h["x"], h["y"], math.radians(h.get("spin", 0)))]):
                X, Y = to(hx_, hy_)
                charcreate.draw_head(S, X, Y, hsz + 6, self.headinfo["glyph"], skin, -math.degrees(a_) if h["kind"] in ("shield", "spin") else -h.get("spin", 0))
        for sh in self.shots:
            P = heads.POWERS[sh["kind"]]
            for i, (tx_, ty_) in enumerate(sh["trail"]):
                X, Y = to(tx_, ty_)
                pygame.draw.circle(S, P["col"], (X, Y), 2 + i)
            X, Y = to(sh["x"], sh["y"])
            g = pygame.transform.rotate(charcreate.glyph(P["glyph"], hsz + 12, P["col"]), sh["spin"] % 360)
            S.blit(g, (X - g.get_width() // 2, Y - g.get_height() // 2))
        for r in self.rings:
            if r["t"] < 0:
                continue
            X, Y = to(r["x"], r["y"])
            rr = int((r["t"] / 0.5) ** 0.6 * PX * r.get("r", 4.2))
            if rr > 2:
                pygame.draw.circle(S, r.get("col", (230, 230, 210)), (X, Y), rr, max(1, int(6 * (1 - r["t"] / 0.5))))
        for zp in self.zaps:
            a, b = to(*zp["a"]), to(*zp["b"])
            col = zp.get("col", heads.POWERS["storm"]["col"])
            if zp.get("straight"):
                pygame.draw.line(S, col, a, b, 4)
                pygame.draw.line(S, (255, 230, 220), a, b, 1)
            else:
                pts = [a] + [(a[0] + (b[0] - a[0]) * q / 5 + random.randint(-10, 10),
                              a[1] + (b[1] - a[1]) * q / 5 + random.randint(-10, 10)) for q in (1, 2, 3, 4)] + [b]
                pygame.draw.lines(S, col, False, pts, 4)
                pygame.draw.lines(S, (255, 255, 255), False, pts, 1)
        for p in self.parts:
            X, Y = to(p["x"], p["y"])
            k = 1 - p["t"] / p["life"]
            if p.get("glyph"):                                 # a head, falling and rolling away
                g = pygame.transform.rotate(charcreate.glyph(p["glyph"], hsz + 2, p["col"]), p["t"] * 500)
                g.set_alpha(int(255 * min(1, k * 2)))
                S.blit(g, (X - g.get_width() // 2, Y - g.get_height() // 2))
                continue
            pygame.draw.circle(S, p["col"], (X, Y), max(1, int(p["size"] * k)))
        for q in self.pops:                                   # impact kanji and damage numbers
            u = q["t"] / (0.9 if q["big"] else 0.7)
            X, Y = to(q["x"], q["y"] - u * (0.6 if q["big"] else 1.0))
            scale = (1.6 - 0.6 * min(1, u * 5)) if q["big"] else 1.0
            if q["text"].isdigit():
                f = self.big if q["big"] else self.font
                img = f.render(q["text"], True, q["col"])
                ol = f.render(q["text"], True, (0, 0, 0))
                for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):   # a tight outline
                    S.blit(ol, (X - img.get_width() // 2 + ox, Y - img.get_height() // 2 + oy))
            else:
                img = charcreate.glyph(q["text"], int((PX * 1.3 if q["big"] else PX * 0.8) * scale), q["col"])
                ol = charcreate.glyph(q["text"], int((PX * 1.3 if q["big"] else PX * 0.8) * scale), (0, 0, 0))
                S.blit(ol, (X - img.get_width() // 2 + 3, Y - img.get_height() // 2 + 3))
            img = img.copy()
            img.set_alpha(int(255 * min(1.0, (1 - u) * 3)))
            S.blit(img, (X - img.get_width() // 2, Y - img.get_height() // 2))

    # ── gathering and building ──
    WOODY = {"forest", "jungle", "taiga", "swamp", "savanna", "hills", "meadow", "fungal", "grass"}

    def start_gather(self):
        if self.dead or self.show_map or getattr(self, "gathering", None):
            return
        near = {self.w.cell(self.px + a, self.py + b) for a in (-1, 0, 1) for b in (-1, 0, 1)}
        if not near & self.WOODY:
            self.say("Nothing here to break off. Find trees.")
            return
        self.gathering = time.monotonic()
        self.amb.fx("rummage", 1.2)

    def update_gather(self):
        g = getattr(self, "gathering", None)
        if not g:
            return
        if abs(self.vx) + abs(self.vy) > 1.5:
            self.gathering = None
            self.say("You stop gathering.")
        elif time.monotonic() - g >= 1.2:
            self.gathering = None
            n = random.choice((1, 1, 2))
            self.inv["wood"] = self.inv.get("wood", 0) + n
            self.say(f"You snap off dead branches: {items.plural('wood', n)}." +
                     (" Something in the trees goes quiet while you do it." if random.random() < 0.1 else ""))
            self.amb.fx("open_wood", 1.0)
            self.burst(self.fx + 0.5, self.fy + 0.4, (120, 90, 60), 8, 3, 2, grav=5)

    def build_target(self):
        """the square you'd build on: under the mouse if you've been using it, else the one in front of you"""
        if getattr(self, "_cam", None) and time.monotonic() - getattr(self, "mouse_moved", 0) < 3:
            cxp, cyp, kx, ky, top = self._cam
            mx, my = pygame.mouse.get_pos()
            return int(math.floor((mx * kx + cxp) / PX)), int(math.floor(((my - HUD_H) * ky + cyp) / PX))
        fx_, fy_ = getattr(self, "facing", (0, 1))
        return self.px + fx_, self.py + fy_

    def can_build(self, x, y, code):
        c = self.w.cell(x, y)
        if (x, y) == (self.px, self.py) or self.w.mob_at(x, y):
            return False
        if c in ("sdirt", "spallet") and code.startswith(("f_", "p_")):
            return True                                        # furniture on a floor
        return self.blocked(x, y) is None and c not in weird.WATER and c not in buildings.HOUSE and \
            not c.startswith(("f_", "p_")) and c not in ("bonfire", "bridge", "mud" if code == "spallet" else "")

    def recipe_cells(self, r, x, y):
        return [(x, y + i, code) for i, code in enumerate(items.BUILD[r][1])]

    def afford(self, r):
        return all(self.inv.get(k, 0) >= n for k, n in items.BUILD[r][2].items())

    def place_build(self):
        r = self.placing
        x, y = self.build_target()
        cells = self.recipe_cells(r, x, y)
        name, _, cost, _ = items.BUILD[r]
        if not self.afford(r):
            self.say("You don't have what it takes: " + ", ".join(f"{n} {items.ITEMS[k][0]}" for k, n in cost.items()) + ".")
            return
        if not all(self.can_build(cx, cy, code) for cx, cy, code in cells):
            self.say("You can't build that there.")
            return
        for k, n in cost.items():
            self.inv[k] -= n
            if self.inv[k] <= 0:
                del self.inv[k]
        for cx, cy, code in cells:
            self.w.built_set()[(cx, cy)] = (code, self.w.cell(cx, cy))
            self.w.set_cell(cx, cy, code)
            if code == "f_crate":
                self.w.containers()[(cx, cy)] = {}
            self.burst(cx + 0.5, cy + 0.5, (150, 120, 90), 10, 4, 2, grav=4)
        self.amb.fx("open_wood", 1.2)
        self.juice(shake=1.5)
        self.say(f"You build a {name.lower()}." + (" It's yours. That means something here." if code == "bonfire" else ""))

    def take_down(self):
        x, y = self.build_target()
        b = self.w.built_set()
        if (x, y) not in b:
            self.say("You didn't build that." if self.w.cell(x, y) in buildings.HOUSE else "There's nothing of yours there.")
            return
        code = b[(x, y)][0]
        r = next((i for i, rec in enumerate(items.BUILD) if code in rec[1]), None)
        cells = [(x, y)]
        if code in ("f_matt0", "f_matt1"):                     # both halves of a bedroll
            cells = [(x, y), (x, y + 1)] if code == "f_matt0" else [(x, y - 1), (x, y)]
        for cx, cy in cells:
            if (cx, cy) in b:
                self.w.set_cell(cx, cy, b.pop((cx, cy))[1])
                self.w.containers().pop((cx, cy), None)
        if r is not None:                                     # you get half back
            for k, n in items.BUILD[r][2].items():
                if n // 2:
                    self.inv[k] = self.inv.get(k, 0) + n // 2
        self.amb.fx("open_wood", 0.8)
        self.say("You pull it apart and keep what's worth keeping.")

    def draw_build_menu(self):
        import dosui
        if not hasattr(self, "dos"):
            self.dos = dosui.Dos()
        D = self.dos
        D.clear()
        D.put(1, 0, "Build", "white")
        D.put(1, 1, "What do you want to build?", "yellow")
        y = 3
        for i, (name, cells, cost, what) in enumerate(items.BUILD):
            ok = self.afford(i)
            L = self.LETTERS[i]
            D.put(2, y, f"{L} - ", "white" if ok else "dgrey")
            D.put(6, y, name, "white" if ok else "dgrey")
            cx = 26
            for k, n in cost.items():
                have = self.inv.get(k, 0)
                g, col = items.GLYPH[k]
                D.put(cx, y, g, col if have >= n else "dgrey")
                txt = f" {n} {items.ITEMS[k][0].split(' of ')[-1]} ({have})"
                D.put(cx + 1, y, txt, "grey" if have >= n else "red")
                cx += len(txt) + 3
            D.put(6, y + 1, what, "dgrey")
            y += 2
        D.put(0, 23, "─" * 80, "dgrey")
        D.put(1, 24, "[a-k] choose, then place it: [Enter]/[E]/click builds  [X] takes yours down  [Q] done", "grey")
        self._dos_place = D.blit_to(self.screen)

    def draw_build_ghost(self, S, top, cxp, cyp):
        """where the thing you're placing would go: green if you can, red if you can't"""
        r = self.placing
        x, y = self.build_target()
        cells = self.recipe_cells(r, x, y)
        ok = self.afford(r) and all(self.can_build(cx, cy, code) for cx, cy, code in cells)
        for cx, cy, code in cells:
            X, Y = cx * PX - cxp, cy * PX - cyp + top
            g = pygame.Surface((PX, PX), pygame.SRCALPHA)
            g.fill((80, 200, 110, 70) if ok else (220, 60, 60, 70))
            S.blit(g, (X, Y))
            pygame.draw.rect(S, (120, 240, 150) if ok else (240, 90, 90), (X, Y, PX, PX), 1)
        name = items.BUILD[r][0]
        img = self.small.render(f"{name}  (Enter/click build, X take down, Q done)", True, (230, 230, 220))
        X, Y = x * PX - cxp, y * PX - cyp + top
        bg = pygame.Surface((img.get_width() + 10, img.get_height() + 4), pygame.SRCALPHA)
        bg.fill((10, 8, 14, 200))
        S.blit(bg, (X + PX // 2 - bg.get_width() // 2, Y - 22))
        S.blit(img, (X + PX // 2 - img.get_width() // 2, Y - 20))

    # ── the director: the changed come for a reason, or not at all ──
    HELLO = ["You've still got your head on. That won't last.", "We kept the fire going for you.",
             "Did you hear it too? It says your name wrong.", "Come and sit with us. Everyone's sitting.",
             "Don't go north. North goes on.", "It looked at me once. I liked it.",
             "You came down in the ship. We remember the ship.", "Your head's very loud. Is it always that loud?",
             "We're not hungry. Not for that.", "The trees moved closer last night. Did you notice?"]

    def camp_fires(self):
        return [xy for xy, (c, _) in self.w.built_set().items() if c == "bonfire"]

    def in_camp(self):
        return any(math.hypot(x - self.px, y - self.py) <= 12 for x, y in self.camp_fires())

    def spawn_spot(self, lo, hi, ahead=False):
        """somewhere you can't see, lo..hi squares away (in front of you if ahead)"""
        fx_, fy_ = getattr(self, "facing", (0, 1))
        for _ in range(60):
            if ahead:
                a = math.atan2(fy_, fx_) + random.uniform(-0.6, 0.6)
            else:
                a = random.uniform(0, 2 * math.pi)
            d = random.uniform(lo, hi)
            x, y = self.px + int(round(math.cos(a) * d)), self.py + int(round(math.sin(a) * d))
            c = self.w.cell(x, y)
            if (x, y) not in self.vis and not self.blocked(x, y) and c not in weird.WATER and not self.w.mob_at(x, y) \
                    and c not in ("mud", "bonfire", "plaza"):
                return x, y
        return None

    def send(self, kind, n, spot, angry):
        out = []
        x0, y0 = spot
        for j in range(n):
            for _ in range(12):
                x, y = x0 + random.randint(-2, 2), y0 + random.randint(-2, 2)
                if not self.blocked(x, y) and not self.w.mob_at(x, y) and self.w.cell(x, y) not in weird.WATER:
                    self.enc_n += 1
                    tier = self.w.tier(self.px // CS, self.py // CS)
                    m = mobs.Mob(self.w.best.species("hollow", random.randrange(6)), 0, tier, x, y, f"enc{self.enc_n}")
                    m.angry = angry
                    self.w.mobs[m.id] = m
                    self.intent[m.id] = kind
                    out.append(m)
                    break
        return out

    def director(self):
        """every world turn: maybe something comes. Hunt, lie in wait, or just say hello."""
        for mid in [k for k in self.intent if k not in self.w.mobs]:   # the dead and gone
            self.intent.pop(mid, None)
            self.hello.pop(mid, None)
        for m in list(self.w.mobs.values()):                  # far away: they've gone back where they came from
            if m.id in self.intent and max(abs(m.x - self.px), abs(m.y - self.py)) > 55:
                self.w.mobs.pop(m.id, None)
        hunting = [m for m in self.w.mobs.values() if self.intent.get(m.id) == "hunt"]
        if not hunting and "hunt" in self.hunt_signs:
            self.hunt_signs.clear()
            self.say("It's quiet again. For now.")
        for m in hunting:                                      # signs as they close in
            d = math.hypot(m.x - self.px, m.y - self.py)
            if d < 14 and "near" not in self.hunt_signs:
                self.hunt_signs.add("near")
                self.say("You hear them in the trees now. More than one.")
            if d < 6 and "here" not in self.hunt_signs:
                self.hunt_signs.add("here")
                self.say("They're here.")
        if self.turn < self.next_enc or any(self.intent.get(m.id) in ("hunt", "hello") for m in self.w.mobs.values()):
            return
        night = self.clock()[1] in ("Dusk", "Night")
        tier = self.w.tier(self.px // CS, self.py // CS)
        self.next_enc = self.turn + random.randint(110, 260)
        if self.in_camp():                                    # your fire keeps most things back
            roll = random.choices(["none", "hello", "hunt"], [70, 20, 10 if night else 0])[0]
        elif night:
            roll = random.choices(["none", "hunt", "ambush", "hello"], [15, 50, 25, 10])[0]
        else:
            roll = random.choices(["none", "hunt", "ambush", "hello"], [25, 15 + 5 * tier, 30, 30])[0]
        if roll == "hunt":
            spot = self.spawn_spot(22, 28)
            if spot:
                self.send("hunt", min(7, 3 + tier + (1 if night else 0)), spot, angry=True)
                self.hunt_signs = {"hunt"}
                self.say("Far behind you, something starts to follow.")
        elif roll == "ambush":
            spot = self.spawn_spot(9, 15, ahead=True)
            if spot:
                self.send("ambush", random.randint(2, 4), spot, angry=False)
        elif roll == "hello":
            spot = self.spawn_spot(14, 18)
            if spot:
                for m in self.send("hello", 1, spot, angry=False):
                    self.hello[m.id] = {"phase": "come", "t": 0}

    def act_with_intent(self, m, dist, occupied):
        """the sent ones don't wander: returns True if it has been dealt with"""
        it = self.intent.get(m.id)
        if it == "ambush":
            if dist <= 4:                                      # sprung
                self.intent[m.id] = "hunt"
                m.angry = True
                if "sprung" not in self.hunt_signs:
                    self.hunt_signs |= {"hunt", "sprung"}
                    self.say("They were waiting for you.")
                    self.juice(shake=5, flash=(120, 20, 20))
                self.popup(m.x + 0.5, m.y - 0.6, "襲", (230, 60, 50), big=True)
            return True                                        # until then: utterly still
        if it == "hello":
            h = self.hello.setdefault(m.id, {"phase": "come", "t": 0})
            target = None
            if h["phase"] == "come":
                if dist <= 2:
                    h["phase"], h["t"] = "talk", 0
                    line = random.choice(self.HELLO)
                    self.speech.append((m.id, line, time.monotonic()))
                    self.say(f"The {m.name} says: \"{line}\"")
                elif random.random() < 0.7:                    # slow, steady, not quite walking right
                    target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied)
            elif h["phase"] == "talk":
                h["t"] += 1
                if h["t"] > 9:
                    h["phase"] = "go"
            else:
                target = mobs.step_towards(m, self.px, self.py, self.w.cell, occupied, away=True)
                if dist > 24:
                    self.w.mobs.pop(m.id, None)
            if target:
                occupied.discard((m.x, m.y))
                m.x, m.y = target
                occupied.add(target)
            return True
        return False

    def threat(self):
        """what the status line says: (colour, text)"""
        hunt = [math.hypot(m.x - self.px, m.y - self.py) for m in self.w.mobs.values() if self.intent.get(m.id) == "hunt"]
        if hunt:
            return ((230, 70, 60), "Hunted. They're close." if min(hunt) < 10 else "Hunted. Something is following you.")
        if any(m.angry and math.hypot(m.x - self.px, m.y - self.py) < 12 for m in self.w.mobs.values()):
            return ((230, 120, 60), "Danger near.")
        if any(self.intent.get(m.id) == "ambush" and math.hypot(m.x - self.px, m.y - self.py) < 13
               for m in self.w.mobs.values()):
            return ((220, 180, 80), "Watched. You can't see by what.")
        if any(self.intent.get(m.id) == "hello" for m in self.w.mobs.values()):
            return ((190, 190, 210), "Someone is coming. They don't seem to want a fight.")
        if self.in_camp():
            return ((140, 210, 140), "Camp. Your fire keeps them back.")
        return ((120, 190, 130), "Quiet. Nothing near.")

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

    REEL_WORDS = ["Dust Road", "Last Call", "Rust Moon", "Cold Engine", "Lost Signal", "Ash Rain", "Low Orbit",
                  "Static", "Burnt Sugar", "Slow Gravity", "Paper Moon", "Empty Chair", "Neon Rain", "Long Fall"]
    REEL_FORMS = ["Blues", "Nocturne", "Waltz", "Requiem", "Lullaby", "Serenade", "Overture", "Shuffle", "Rag", "Ballad"]

    def draw_cold_open(self):
        """the title card a new story opens on: an old late-night anime eyecatch. Any key goes on."""
        sw, sh = self.screen.get_size()
        t = time.monotonic() - self.cold_open
        if not getattr(self, "_card", None):
            import charcreate
            r = random.Random(self.w.seed)
            gear = list(self.char.get("look", [None] * 4))[:4]
            look = tuple(gear) + (tuple(self.char["coat"]), tuple(self.char["trim"]))   # the full outfit, gear and all
            coat, trim = look[4], look[5]
            card = pygame.Surface((sw, sh))
            card.fill(tuple(int(v * 0.35) for v in coat))
            pygame.draw.polygon(card, tuple(int(v * 0.85) for v in trim),             # a hard diagonal colour field
                                [(int(sw * 0.52), 0), (sw, 0), (sw, sh), (int(sw * 0.36), sh)])
            pygame.draw.polygon(card, tuple(int(v * 0.55) for v in trim),
                                [(int(sw * 0.50), 0), (int(sw * 0.52), 0), (int(sw * 0.36), sh), (int(sw * 0.34), sh)])
            big = pygame.font.Font(charcreate.CJK, int(sh * 0.8))                     # their body symbol, huge and faint
            g = big.render(self.char["body"], True, (0, 0, 0))
            g.set_alpha(40)
            card.blit(g, (int(sw * 0.02), int(sh * 0.02)))
            fig = pygame.Surface((int(sh * 0.9), int(sh * 0.9)), pygame.SRCALPHA)      # them, flat and bold
            charcreate.draw_char(fig, fig.get_width() // 2, fig.get_height() // 2, int(sh * 0.42), self.char["body"],
                                 look, tuple(self.char["skin_rgb"]), None, clothes=(self.jacket, self.trousers))
            card.blit(fig, (int(sw * 0.62) - fig.get_width() // 2, int(sh * 0.52) - fig.get_height() // 2))
            serif = "/usr/share/fonts/noto/NotoSerif-BoldItalic.ttf"
            try:
                f_small, f_big = pygame.font.Font(serif, 26), pygame.font.Font(serif, 64)
            except OSError:
                f_small, f_big = self.big, self.big
            title = f"{r.choice(self.REEL_WORDS)} {r.choice(self.REEL_FORMS)}"
            card.blit(f_small.render(f"REEL {r.randint(1, 26):02d}", True, (235, 225, 200)), (70, int(sh * 0.30)))
            y = int(sh * 0.36)
            for word in title.upper().split():                                        # stacked, eyecatch-style
                img = f_big.render(word, True, (245, 240, 225))
                card.blit(f_big.render(word, True, (0, 0, 0)), (74, y + 4))
                card.blit(img, (70, y))
                y += int(f_big.get_height() * 0.95)
            sub = f"{self.char['name']}  ·  {self.char['archetype']}"
            card.blit(self.font.render(sub, True, (230, 220, 200)), (72, y + 14))
            card.blit(self.small.render("stranded, day one", True, (200, 190, 170)), (72, y + 40))
            grain = []                                                                 # film grain, a few frames
            for k in range(4):
                n = np.random.default_rng(k).integers(0, 255, (sh // 2, sw // 2), dtype=np.uint8)
                a = np.zeros((sh // 2, sw // 2, 4), np.uint8)
                a[..., 0] = a[..., 1] = a[..., 2] = n
                a[..., 3] = 26
                gs = pygame.image.frombuffer(a.tobytes(), (sw // 2, sh // 2), "RGBA")
                grain.append(pygame.transform.scale(gs, (sw, sh)))
            yy, xx = np.mgrid[0:sh // 4, 0:sw // 4]                                    # vignette
            d = np.sqrt(((xx - sw / 8) / (sw / 8)) ** 2 + ((yy - sh / 8) / (sh / 8)) ** 2)
            va = np.zeros((sh // 4, sw // 4, 4), np.uint8)
            va[..., 3] = np.clip((d - 0.6) * 260, 0, 200).astype(np.uint8)
            vig = pygame.transform.smoothscale(pygame.image.frombuffer(va.tobytes(), (sw // 4, sh // 4), "RGBA"), (sw, sh))
            self._card = (card, grain, vig)
            self.amb.fx("sting", 2.5)
        card, grain, vig = self._card
        jitter = int(2 * math.sin(t * 37)) if t < 2 else 0                            # a little gate weave
        self.screen.fill((0, 0, 0))
        self.screen.blit(card, (0, jitter))
        self.screen.blit(grain[int(t * 12) % len(grain)], (0, 0))
        self.screen.blit(vig, (0, 0))
        bar = int(sh * 0.09)                                                           # letterbox
        pygame.draw.rect(self.screen, (0, 0, 0), (0, 0, sw, bar))
        pygame.draw.rect(self.screen, (0, 0, 0), (0, sh - bar, sw, bar))
        if t > 1.2:
            hint = self.small.render("press any key", True, (150, 145, 135))
            self.screen.blit(hint, (sw - hint.get_width() - 24, sh - bar + 12))
        if t < 0.35:                                                                   # fade up from black
            fade = pygame.Surface((sw, sh))
            fade.set_alpha(int(255 * (1 - t / 0.35)))
            self.screen.blit(fade, (0, 0))

    def handle(self, e):
        if getattr(self, "cold_open", None):
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN) and time.monotonic() - self.cold_open > 0.4:
                self.cold_open, self._card = None, None
            return True
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
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3 and not self.show_map and getattr(self, "_cam", None):
            cxp, cyp, kx, ky, top = self._cam                     # aim your head at the mouse
            wx = (e.pos[0] * kx + cxp) / PX
            wy = ((e.pos[1] - HUD_H) * ky + cyp) / PX
            self.use_head((wx, wy))
        if e.type == pygame.MOUSEWHEEL and not self.show_map:
            self.set_zoom(1 if e.y > 0 else -1)
        if e.type == pygame.MOUSEMOTION:
            self.mouse_moved = time.monotonic()
        if getattr(self, "build_menu", False) and e.type == pygame.KEYDOWN:   # the build menu
            if e.unicode and e.unicode in self.LETTERS[:len(items.BUILD)]:   # (letters first: b is a recipe too)
                self.placing, self.build_menu = self.LETTERS.index(e.unicode), False
            elif e.key in (pygame.K_ESCAPE, pygame.K_q):
                self.build_menu = False
            return True
        if getattr(self, "outfit", False) and e.type == pygame.KEYDOWN:       # the outfit menu (C)
            self.outfit_input(e)
            return True
        if getattr(self, "placing", None) is not None and e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_q):
                self.placing = None
                return True
            if e.type == pygame.KEYDOWN and e.key == pygame.K_b:
                self.placing, self.build_menu = None, True
                return True
            if (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e)) or \
                    (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                self.place_build()
                return True
            if e.type == pygame.KEYDOWN and e.key == pygame.K_x:
                self.take_down()
                return True
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
            if k in moves and self.show_map:          # the map only looks: a cursor moves, you don't
                mx, my = getattr(self, "map_cur", None) or (self.px // CS, self.py // CS)
                dx, dy = moves[k]
                self.map_cur = (max(0, min(proto.W - 1, mx + dx)), max(0, min(proto.H - 1, my + dy)))
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
                self.show_inv, self.detail = True, None
            elif k == pygame.K_f and not self.show_map:
                self.use_head()
            elif k == pygame.K_b and not self.show_map:
                self.build_menu = True
            elif k == pygame.K_c and not self.show_map and self.char:
                self.outfit = True
            elif k == pygame.K_q:                       # Q closes whatever's open (never quits the game)
                if self.show_map:
                    self.show_map = False
                elif self.sizer:
                    self.sizer = False
                    self.save_settings()
            elif k == pygame.K_g and not self.show_map:
                self.start_gather()
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
                self.map_cur = None
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

    ZOOMS = (0.6, 0.8, 1.0, 1.5, 2.0)

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
                self._view = opaque((sw, vh))
            S, top = self._view, 0
        now = time.monotonic()
        t = now - self.t0
        self.sync()
        cxp = int(self.fx * PX) + PX // 2 - sw // 2       # camera: player in the middle
        cyp = int(self.fy * PX) + PX // 2 - vh // 2
        if self.shake > 0.3:                                       # screen shake
            cxp += int(random.uniform(-1, 1) * self.shake)
            cyp += int(random.uniform(-1, 1) * self.shake)
        self._cam = (cxp, cyp, sw / SW, vh / VH, top)            # for aiming with the mouse
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
        for m in list(self.w.mobs.values()):                   # (a snapshot: the loader can add creatures any time)
            sx, sy = self.mob_pos.get(m.id, (m.x, m.y))       # glide between squares instead of jumping
            if abs(sx - m.x) + abs(sy - m.y) > 3:
                sx, sy = m.x, m.y
            k = min(1.0, (now - getattr(self, "_last_draw", now)) * 12)
            sx, sy = sx + (m.x - sx) * k, sy + (m.y - sy) * k
            self.mob_pos[m.id] = (sx, sy)
            x, y = int(sx * PX) - cxp, int(sy * PX) - cyp + top
            if self.intent.get(m.id) == "ambush" and max(abs(m.x - self.px), abs(m.y - self.py)) > 2:
                continue                                       # lying in wait: you don't see them
            if (m.x, m.y) in self.vis and -PX < x < sw and top - PX < y < top + vh:
                fx_, fy_ = x + PX // 2, y + PX - 4                  # where its feet are
                sh = self.sized("foot", self.foot_shadow())
                S.blit(sh, (fx_ - sh.get_width() // 2, fy_ - sh.get_height() // 2 - 1))
                spr = self.sized(("mob", m.biome, m.n, m.angry), self.mob_sprite(m))
                if now - self.flash.get(m.id, 0) < 0.15:
                    spr = spr.copy(); spr.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
                w_, h_ = spr.get_size()
                jit = random.randint(-1, 1) if getattr(m.sp, "glyph", None) and random.random() < 0.3 else 0   # twitching
                S.blit(spr, (fx_ - w_ // 2 + jit, fy_ + 4 - h_))
                if m.id in self.tame:                           # yours
                    import charcreate
                    mk = charcreate.glyph("友", 14, (250, 200, 170))
                    S.blit(mk, (fx_ - mk.get_width() // 2, fy_ + 4 - h_ - 18))
                if m.hp < m.maxhp:
                    bw, by = max(8, w_ - 4), fy_ + 4 - h_ - 4
                    pygame.draw.rect(S, (60, 0, 0), (fx_ - bw // 2, by, bw, 3))
                    pygame.draw.rect(S, (230, 50, 50), (fx_ - bw // 2, by, int(bw * m.hp / m.maxhp), 3))
        self._last_draw = now
        self.speech = [sp for sp in self.speech if now - sp[2] < 5 and sp[0] in self.w.mobs]
        for mid, line, t_ in self.speech:                      # what the greeter said, over its head
            m = self.w.mobs[mid]
            X, Y = int(m.x * PX) - cxp + PX // 2, int(m.y * PX) - cyp + top - int(PX * 1.2)
            img = self.small.render(line, True, (225, 222, 232))
            bg = pygame.Surface((img.get_width() + 14, img.get_height() + 8), pygame.SRCALPHA)
            bg.fill((8, 6, 10, 215))
            S.blit(bg, (X - bg.get_width() // 2, Y - bg.get_height()))
            S.blit(img, (X - img.get_width() // 2, Y - bg.get_height() + 4))
        self.draw_doors(S, top, cxp, cyp, sw, vh, c0x, c0y, c1x, c1y)
        self.draw_fog(S, top, cxp, cyp, sw, vh, t)
        S.blit(self.darkness(cxp, cyp, sw, vh), (-(cxp % PX), top - (cyp % PX)))
        glow = self.glow_frames()
        for (fx, fy) in fires:                           # firelight pushes back the dark
            g = glow[int(t * 7 + fx) % len(glow)]
            S.blit(g, (fx - g.get_width() // 2, fy - g.get_height() // 2), special_flags=pygame.BLEND_ADD)
        if self.clock()[1] in ("Dusk", "Night"):                      # the little light you carry
            g = self.lamp_glow(False)
            flick = 1.0 + 0.04 * math.sin(t * 13) + 0.03 * math.sin(t * 7.3)
            gw = int(g.get_width() * flick)
            g2 = pygame.transform.smoothscale(g, (gw, gw))
            hx0, hy0 = int(self.fx * PX) - cxp + PX // 2, int(self.fy * PX) - cyp + top + PX // 2
            S.blit(g2, (hx0 - gw // 2, hy0 - gw // 2), special_flags=pygame.BLEND_ADD)
            S.blit(g2, (hx0 - gw // 2, hy0 - gw // 2), special_flags=pygame.BLEND_ADD)
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
                                     tuple(self.char["skin_rgb"]), None, pose,
                                     head=self.headinfo["glyph"] if self.head_out is None else "")
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
        self.draw_head_things(S, top, cxp, cyp)
        if getattr(self, "placing", None) is not None:
            self.draw_build_ghost(S, top, cxp, cyp)
        if getattr(self, "gathering", None):                  # gathering takes a moment
            u = min(1.0, (now - self.gathering) / 1.2)
            gx_, gy_ = int(self.fx * PX) - cxp + PX // 2 - 16, int(self.fy * PX) - cyp + top - 8
            pygame.draw.rect(S, (20, 18, 26), (gx_ - 1, gy_ - 1, 34, 6))
            pygame.draw.rect(S, (170, 130, 80), (gx_, gy_, int(32 * u), 4))
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
            pygame.transform.scale(S, (SW, VH), self._zoomed(SW, VH))   # a fast resize: pixel art doesn't need smoothing
            self.screen.blit(self._zoomed_s, (0, HUD_H))
        self.acid(t, now, SW, VH)
        self.screen.blit(self.vignette(SW, VH), (0, HUD_H))      # the edges of your sight close in
        if self.flash_fx and now - self.flash_fx[1] < 0.14:      # an impact flash
            ov = pygame.Surface((SW, VH))
            ov.fill(self.flash_fx[0])
            ov.set_alpha(int(150 * (1 - (now - self.flash_fx[1]) / 0.14)))
            self.screen.blit(ov, (0, HUD_H))
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
                        if -PX < X < sw and top - PX < Y < top + vh and self.w.was_seen(dx, dy) and \
                                self.w.cell(dx, dy) == "hdoor":                # shack doorways are just rags
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
        elif code in ("f_matt0", "f_matt1"):                    # a mattress on the floor: stained, a grey blanket
            top_, bot = (3, 0) if code == "f_matt0" else (0, 3)
            r = (4, top_, P_ - 8, P_ - top_ - bot)
            R((150, 140, 118), r); R(ink, r, 1)
            if code == "f_matt0":
                R((176, 168, 150), (8, 6, P_ - 16, 7))                                  # a flat pillow
                pygame.draw.ellipse(b, (120, 100, 70), (14, 9, 9, 6))                   # a stain on it
            else:
                R((72, 74, 70), (4, 0, P_ - 8, P_ - 9)); R(ink, (4, 0, P_ - 8, P_ - 9), 1)   # blanket, kicked down
            pygame.draw.ellipse(b, (110, 88, 60), (6 + var % 9, 14 + var % 5, 10, 7))
        elif code == "f_drum":                                   # oil drum cut into a stove, embers glowing
            pygame.draw.circle(b, (60, 52, 50), (16, 16), 11); pygame.draw.circle(b, ink, (16, 16), 11, 1)
            pygame.draw.circle(b, (40, 34, 32), (16, 16), 8)
            pygame.draw.circle(b, (150, 60, 30), (16, 16), 5); pygame.draw.circle(b, (220, 120, 50), (15, 15), 2)
            R((50, 44, 40), (22, 2, 4, 8))                                              # a chimney pipe
        elif code == "f_crtab":                                  # a crate used as a table, a tin and a candle stub
            R((110, 86, 56), (5, 5, P_ - 10, P_ - 10)); R(ink, (5, 5, P_ - 10, P_ - 10), 1)
            pygame.draw.line(b, (80, 62, 40), (6, 6), (P_ - 7, P_ - 7), 2)
            R((150, 150, 156), (9, 9, 6, 7))
            pygame.draw.circle(b, (210, 200, 160), (21, 19), 2); pygame.draw.circle(b, (250, 200, 110), (21, 18), 1)
        elif code == "f_stool":                                  # a stool made of a cable drum
            pygame.draw.circle(b, (96, 74, 50), (16, 16), 7); pygame.draw.circle(b, ink, (16, 16), 7, 1)
            pygame.draw.circle(b, (70, 54, 36), (16, 16), 3)
        elif code == "f_sshelf":                                 # planks on bricks, jars and tins
            R((92, 72, 48), (2, 4, P_ - 4, 10)); R(ink, (2, 4, P_ - 4, 10), 1)
            for x, col in ((5, (120, 130, 110)), (11, (150, 140, 120)), (17, (100, 70, 50)), (23, (130, 130, 136))):
                R(col, (x, 6, 4, 6))
        elif code == "f_bucket":
            pygame.draw.circle(b, (110, 110, 112), (16, 16), 7); pygame.draw.circle(b, ink, (16, 16), 7, 1)
            pygame.draw.circle(b, (40, 52, 52), (16, 16), 5)
            pygame.draw.arc(b, (80, 80, 84), (8, 6, 16, 16), 0.3, 2.8, 1)
        elif code == "f_rags":                                   # a heap of rags and old clothes
            for k, col in enumerate(((90, 80, 70), (70, 76, 80), (110, 90, 70), (60, 60, 56))):
                pygame.draw.ellipse(b, col, (5 + (k * 7 + var) % 10, 8 + (k * 5) % 9, 14, 10))
        elif code == "f_wbarrel":                                # a plastic water barrel, faded
            pygame.draw.circle(b, (60, 84, 96), (16, 16), 10); pygame.draw.circle(b, ink, (16, 16), 10, 1)
            pygame.draw.circle(b, (40, 60, 70), (16, 16), 6, 1); pygame.draw.circle(b, (30, 30, 30), (19, 13), 2)
        elif code == "f_shrine":                                 # what they turned to: candles, a twig effigy, the eye
            R((70, 62, 54), (3, 8, P_ - 6, P_ - 12)); R(ink, (3, 8, P_ - 6, P_ - 12), 1)
            R((120, 110, 96), (4, 9, P_ - 8, 3))                                        # a cloth over it
            pygame.draw.circle(b, (150, 30, 34), (16, 18), 5, 1)                        # the eye, daubed in red
            pygame.draw.circle(b, (150, 30, 34), (16, 18), 1)
            for x in (6, 26):                                                            # candle stubs
                R((220, 210, 180), (x - 1, 14, 3, 6)); pygame.draw.circle(b, (255, 210, 120), (x, 13), 1)
            pygame.draw.line(b, (90, 70, 46), (16, 3), (16, 11), 1)                      # a twig effigy, bound with wire
            pygame.draw.line(b, (90, 70, 46), (12, 5), (20, 5), 1)
            pygame.draw.line(b, (140, 140, 150), (14, 7), (18, 7), 1)
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
        """all the furniture in view: found in houses and shacks, or built by you"""
        self.lamps = []
        for zy in range(c0y, c1y + 1):
            for zx in range(c0x, c1x + 1):
                furn = [f for f in self.w.furniture(zx, zy)
                        if -PX < f[0] * PX - cxp < sw + PX and -PX < f[1] * PX - cyp < vh + PX]
                tables = {(x, y) for x, y, c in furn if c in ("f_tab0", "f_tab1")}
                for (x, y, c) in furn:
                    face = (0, 0)
                    if c == "f_chair":
                        face = next(((dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                     if (x + dx, y + dy) in tables), (0, 1))
                    X, Y = x * PX - cxp, y * PX - cyp + top
                    S.blit(self.furn_sprite(c, (x * 7 + y * 13) % 97, face), (X, Y))
                    if c in ("f_lamp", "f_end", "f_drum", "f_shrine") and (x, y) in self.vis:
                        self.lamps.append((X + PX // 2, Y + PX // 2 - 2, c == "f_lamp"))

    def _zoomed(self, w, h):
        if getattr(self, "_zoomed_s", None) is None or self._zoomed_s.get_size() != (w, h):
            self._zoomed_s = opaque((w, h))
        return self._zoomed_s

    def fog_tiles(self):
        """two soft, seamless fog textures (made once): blurred noise, wrapped so they tile"""
        if not hasattr(self, "_fog"):
            out = []
            for k, (n, cut, col, peak) in enumerate(((128, 6, (118, 126, 112), 95), (96, 10, (90, 98, 96), 70))):
                rng = np.random.default_rng(31 + k)
                f = np.fft.fft2(rng.standard_normal((n, n)))
                fy, fx = np.meshgrid(np.fft.fftfreq(n) * n, np.fft.fftfreq(n) * n, indexing="ij")
                f *= np.exp(-(fx ** 2 + fy ** 2) / (2 * cut ** 2))       # keep only big, soft shapes
                v = np.real(np.fft.ifft2(f))
                v = (v - v.min()) / (v.max() - v.min() + 1e-9)
                a = np.clip((v - 0.35) / 0.65, 0, 1) ** 1.6 * peak
                img = np.zeros((n, n, 4), np.uint8)
                img[..., 0], img[..., 1], img[..., 2] = col
                img[..., 3] = a.astype(np.uint8)
                srf = pygame.image.frombuffer(img.tobytes(), (n, n), "RGBA")
                size = PX * (22 if k == 0 else 15)
                out.append(pygame.transform.smoothscale(srf, (size, size)).convert_alpha())
            self._fog = out
        return self._fog

    def draw_fog(self, S, top, cxp, cyp, sw, vh, t):
        """fog drifting over the ground, anchored to the world (it doesn't follow you), thicker at night.
        Only drawn round where you can see (beyond is black anyway), at quarter size and stretched up."""
        Q = 4
        phase = self.clock()[1]
        thick = {"Night": 1.0, "Dusk": 0.85, "Dawn": 0.9}.get(phase, 0.6)
        R = (max(1, self.radius) + 3) * PX                      # the box round your sight
        hx, hy = int(self.fx * PX) - cxp + PX // 2, int(self.fy * PX) - cyp + PX // 2
        box = pygame.Rect(hx - R, hy - R, 2 * R, 2 * R).clip(pygame.Rect(0, 0, sw, vh))
        if box.w <= 0 or box.h <= 0:
            return
        qw, qh = box.w // Q + 2, box.h // Q + 2
        if getattr(self, "_fogbuf", None) is None or self._fogbuf.get_size() != (qw, qh):
            self._fogbuf = pygame.Surface((qw, qh), pygame.SRCALPHA)
        buf = self._fogbuf
        buf.fill((0, 0, 0, 0))
        for k, tile in enumerate(self.fog_tiles()):
            key = ("fogq", k, thick)
            if key not in self.mob_img:                        # the tile at quarter size, at this thickness
                small = pygame.transform.smoothscale(tile, (tile.get_width() // Q, tile.get_height() // Q))
                small.set_alpha(int(255 * thick))
                flat = pygame.Surface(small.get_size(), pygame.SRCALPHA)
                flat.blit(small, (0, 0))
                self.mob_img[key] = flat
            q = self.mob_img[key]
            w, h = q.get_size()
            dx, dy = t * (9 if k == 0 else -14), t * (3 if k == 0 else 5)   # the wind moves it
            ox = int(-((cxp + box.x - dx) / Q) % w) - w
            oy = int(-((cyp + box.y - dy) / Q) % h) - h
            for y in range(oy, qh + h, h):
                for x in range(ox, qw + w, w):
                    buf.blit(q, (x, y))
        half = pygame.transform.smoothscale(buf, (qw * Q // 2, qh * Q // 2))      # smooth to half size,
        S.blit(pygame.transform.scale(half, (qw * Q // 2 * 2, qh * Q // 2 * 2)), (box.x, box.y + top))   # fast doubling

    def vignette(self, w, h):
        key = ("vig", w, h)
        if key not in self.mob_img:
            yy, xx = np.mgrid[0:h // 8, 0:w // 8]
            d = np.sqrt(((xx - w / 16) / (w / 16)) ** 2 + ((yy - h / 16) / (h / 16)) ** 2)
            a = np.zeros((h // 8, w // 8, 4), np.uint8)
            a[..., 3] = np.clip((d - 0.55) * 300, 0, 215).astype(np.uint8)
            self.mob_img[key] = pygame.transform.smoothscale(
                pygame.image.frombuffer(a.tobytes(), (w // 8, h // 8), "RGBA"), (w, h)).convert_alpha()
        return self.mob_img[key]

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
        alpha = np.full(d2.shape, min(tint[3], 120), np.float64)    # one even tint over the whole screen (user)
        if self.clock()[1] in ("Dusk", "Night"):                    # your little light pushes the dark back
            near = np.sqrt((vx[on] - self.px) ** 2 + (vy[on] - self.py) ** 2)
            alpha = alpha * (1 - 0.8 * np.clip(1 - near / 3.2, 0, 1))
        a[j, i, 3] = alpha.astype(np.int64)
        srf = pygame.image.frombuffer(a.tobytes(), (cols, rows), "RGBA")
        half = pygame.transform.smoothscale(srf, (cols * PX // 2, rows * PX // 2))        # soft edges, built at half size
        srf = pygame.transform.scale(half, (cols * PX, rows * PX)).convert_alpha()      # and stretched (display format = fast)
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
        cur = getattr(self, "map_cur", None)
        if cur:                                                  # the look cursor
            x1, y1 = ox + cur[0] * tw, oy + cur[1] * th
            pygame.draw.rect(self.screen, (255, 210, 90), (int(x1) - 2, int(y1) - 2, int(tw) + 5, int(th) + 5), 2)
            b = str(self.w.wd.biome[cur[1], cur[0]])
            seen = cur in self.w.visited
            what = (NAMES.get(b, b) + (", a town" if cur in self.w.wd.towns else "")) if seen else "Unexplored"
            d = max(abs(cur[0] - self.px // CS), abs(cur[1] - self.py // CS))
            self.screen.blit(self.font.render(f"Looking at: {what}  ({d} squares away)", True, (255, 220, 130)),
                             (ox + 200, HUD_H + 14))
        here = str(self.w.wd.biome[self.py // CS, self.px // CS])
        info = f"You are in: {NAMES.get(here, here)}     Explored {len(self.w.visited)} squares     Towns visited " \
               f"{sum(1 for t in self.w.wd.towns if t in self.w.visited)} / {len(self.w.wd.towns)}"
        self.screen.blit(self.font.render(info, True, (210, 205, 195)), (ox, oy + mh + 8))
        hint = self.small.render("Arrows: look around    M / Q / Esc: back    "
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
                     "wfloor": (110, 84, 56), "swall_iron": (120, 110, 104), "swall_wood": (104, 80, 56),
                     "swall_tarp": (80, 92, 110), "swall_hull": (140, 140, 146), "sgap": (60, 56, 52),
                     "sdoor": (120, 90, 60), "debris": (90, 76, 60), "sdirt": (70, 56, 40), "spallet": (96, 74, 50),
                     "mud": (58, 50, 40)}
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
        if not self.show_map and self.char:                          # your head: what it does, and if it's ready
            import charcreate
            P = heads.POWERS[self.headinfo["power"]]
            left_ = self.head_ready - time.monotonic()
            state = "out" if self.head_out else \
                (f"{left_:.1f}s" if left_ > 0 else "ready")
            col = (240, 220, 160) if state == "ready" else (150, 145, 140)
            y0 = sh - LOG_H - 30
            bg = pygame.Surface((300, 26), pygame.SRCALPHA)
            bg.fill((10, 8, 14, 190))
            self.screen.blit(bg, (8, y0))
            self.screen.blit(charcreate.glyph(self.headinfo["glyph"], 20, col), (14, y0 + 1))
            self.screen.blit(self.font.render(f"{P['name']}   {state}   (F / right-click)", True, col), (42, y0 + 4))
        if not self.show_map and not self.sizer:
            col, txt = self.threat()
            img = self.font.render(txt, True, col)
            bg = pygame.Surface((img.get_width() + 30, 26), pygame.SRCALPHA)
            bg.fill((8, 6, 10, 190))
            self.screen.blit(bg, (8, HUD_H + 8))
            pulse = 4 + (2 * abs(math.sin(time.monotonic() * 4)) if col[0] > 200 and col[1] < 150 else 0)
            pygame.draw.circle(self.screen, col, (20, HUD_H + 21), int(pulse))
            self.screen.blit(img, (32, HUD_H + 12))
        if self.sizer and not self.show_map:
            self.draw_sizer()

        keys = self.small.render("Move: WASD   F head   E search   G gather wood   B build   I bag   C outfit   M map   V minimap   +/- zoom   N sound   Esc quit", True, (100, 100, 110))
        self.screen.blit(keys, (sw - keys.get_width() - 10, sh - 18))
        if self.show_inv or self.loot:                       # the menus take over the whole screen, DOS-style
            self.draw_menu()
        if getattr(self, "build_menu", False):
            self.draw_build_menu()
        if getattr(self, "outfit", False):
            self.draw_outfit()

    def outfit_rows(self):
        """[(letter, what, value)] for the outfit menu: jackets, trousers, then the weapons you carry"""
        import charcreate
        rows, n = [], 0
        for kind, lst in (("jacket", charcreate.JACKETS), ("trousers", charcreate.TROUSERS)):
            for i in [None] + list(range(len(lst))):
                rows.append((self.LETTERS[n], kind, i))
                n += 1
        for k in [None] + [k for k in self.sorted_items(self.inv) if items.ITEMS[k][1] == "weapon"]:
            rows.append((self.LETTERS[n] if n < len(self.LETTERS) else "?", "weapon", k))
            n += 1
        return rows

    def outfit_input(self, e):
        if e.key in (pygame.K_ESCAPE, pygame.K_q):
            self.outfit = False
            return
        hit = next((r for r in self.outfit_rows() if e.unicode and r[0] == e.unicode), None)
        if not hit:
            return
        import charcreate
        _, kind, v = hit
        if kind == "weapon":
            if v != self.weapon:
                self.weapon = v
                self.say(f"You ready the {items.ITEMS[v][0]}." if v else "You put your weapon away. Fists, then.")
        else:
            self.wear(**{kind: v})
            lst = charcreate.JACKETS if kind == "jacket" else charcreate.TROUSERS
            self.say(f"You put on the {lst[v]['name'].lower()}." if v is not None else f"You put your own {kind} back on.")
        self.amb.fx("equip", 1.2)

    def draw_outfit(self):
        """C: change jacket, trousers and weapon. A DOS screen like the bag, with you drawn on the right"""
        import dosui, charcreate
        if not hasattr(self, "dos"):
            self.dos = dosui.Dos()
        D = self.dos
        D.clear()
        D.put(1, 0, "Outfit", "white")
        D.put(1, 1, "What do you want to wear and carry?", "yellow")
        arm, spd, car = charcreate.outfit_bonus(self.jacket, self.trousers)
        txt = f"Armour {arm}  Speed {spd:+d}%  Carry {self.cap:.0f} kg"
        D.put(79 - len(txt), 0, txt, "cyan")
        y, last = 3, None
        for L, kind, v in self.outfit_rows():
            if kind != last:
                if last:
                    y += 1
                D.put(1, y, {"jacket": "Jackets", "trousers": "Trousers", "weapon": "Weapons (from your bag)"}[kind], "lblue")
                y += 1
                last = kind
            if y > 22:
                break
            on = v == {"jacket": self.jacket, "trousers": self.trousers, "weapon": self.weapon}[kind]
            col = "white" if on else "grey"
            D.put(2, y, f"{L} {'+' if on else '-'} ", col)
            if kind == "weapon":
                if v is None:
                    D.put(8, y, "bare hands", col)
                else:
                    g, gc = items.GLYPH[v]
                    D.put(6, y, g, gc)
                    D.put(8, y, items.ITEMS[v][0], col)
                    ow = charcreate.OLD_WEAPONS.get(v)
                    D.put(36, y, f"+{items.ITEMS[v][4].get('dmg', 0)} dmg" + (f"  {ow[2]}" if ow else ""), "dgrey")
            else:
                lst = charcreate.JACKETS if kind == "jacket" else charcreate.TROUSERS
                if v is None:
                    D.put(8, y, f"your own {kind}", col)
                else:
                    D.put(6, y, "█", tuple(lst[v]["col"]))
                    D.put(8, y, lst[v]["name"], col)
                    D.put(28, y, charcreate.bonus_text(lst[v]), "dgrey")
            y += 1
        D.put(0, 23, "─" * 80, "dgrey")
        D.put(1, 24, "[letter] wear or hold it   [Q] done   (find old weapons in shrines and racks)", "grey")
        self._dos_place = D.blit_to(self.screen)
        # you, in it, on the right
        sw, sh = self.screen.get_size()
        size = int(sh * 0.3)
        fig = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        gear = list(self.char.get("look", [None] * 4))[:4]
        gear[1] = self.weapon if self.weapon in charcreate.WEAPONS else (None if self.weapon is None else "crowbar")
        look = tuple(gear) + (tuple(self.char["coat"]), tuple(self.char["trim"]))
        charcreate.draw_char(fig, size, size, size, self.char["body"], look, tuple(self.char["skin_rgb"]), None,
                             head=self.headinfo["glyph"], clothes=(self.jacket, self.trousers))
        self.screen.blit(fig, (int(sw * 0.74) - size, int(sh * 0.5) - size))

    def draw_menu(self):
        """the inventory / pick-up menus: a full DOS text screen, Dungeon Crawl Stone Soup-style"""
        import dosui
        if not hasattr(self, "dos"):
            self.dos = dosui.Dos()
        D = self.dos
        D.clear()
        inv = self.menu_inv()
        kg_bag = items.weight(self.inv)
        if self.loot:
            what = self.thing_name(self.loot[2])
            if self.mode == "take":
                D.put(1, 0, f"{what.capitalize()}", "white")
                D.put(1, 1, "Pick up what?", "yellow")
                D.put(16, 1, "(letters mark, ',' all, '-' none, Enter take, Tab put things in)", "dgrey")
            else:
                D.put(1, 0, f"Your pack", "white")
                D.put(1, 1, f"Put what in the {what}?", "yellow")
                D.put(25 + len(what), 1, "(letters mark, Enter put, Tab back)", "dgrey")
        else:
            D.put(1, 0, "Inventory", "white")
            D.put(1, 1, "Choose something to look at it.", "yellow")
        wcol = "lred" if kg_bag > self.cap else "grey"
        txt = f"Pack {kg_bag:4.1f}/{self.cap:.0f} kg"
        D.put(79 - len(txt), 0, txt, wcol)
        rows = self.menu_rows()
        self._row_at = {}
        y = 3
        if not rows:
            D.put(3, y, "There's nothing here." if self.loot and self.mode == "take" else "You aren't carrying anything.",
                  "dgrey")
        for kind, k, L in rows:
            if y > 22:
                D.put(3, 23, "...more (keep taking to see the rest)", "dgrey")
                break
            if kind == "head":
                name, sym = items.CATEGORY[k]
                D.put(1, y, name, "lblue")
            else:
                g, col = items.GLYPH[k]
                mark = "+" if k in getattr(self, "picked", set()) else "-"
                D.put(2, y, f"{L} {mark} ", "white" if mark == "+" else "grey")
                D.put(6, y, g, col)
                name = items.plural(k, inv[k])
                if k == self.weapon and inv is self.inv:
                    name += " (in hand)"
                D.put(8, y, name, "white" if mark == "+" else "grey")
                wt = f"{items.ITEMS[k][2] * inv[k]:.1f} kg"
                D.put(79 - len(wt), y, wt, "dgrey")
                self._row_at[y] = k
            y += 1
        bar = "─" * 80
        D.put(0, 24 - 1, bar, "dgrey")
        foot = ("[a-z] mark  [,] all  [-] none  [Enter] take  [Tab] put in  [Q] leave" if self.loot and self.mode == "take"
                else "[a-z] mark  [Enter] put in  [Tab] take out  [Q] leave" if self.loot
                else "[a-z] look at an item   [Q] close")
        D.put(1, 24, foot, "grey")
        if self.detail and self.detail in self.inv:            # one item, described, with what you can do
            k = self.detail
            name, kind, kg, _, eff = items.ITEMS[k]
            g, col = items.GLYPH[k]
            D.box(8, 6, 64, 13, "grey", "black", f"{g} {name}")
            words, line, yy = items.DESC.get(k, "").split(), "", 8
            for w_ in words:                                     # wrap the description
                if len(line) + len(w_) + 1 > 58:
                    D.put(11, yy, line, "grey")
                    line, yy = "", yy + 1
                line = (line + " " + w_).strip()
            D.put(11, yy, line, "grey")
            stats = ", ".join(f"+{v} {n_}" for n_, v in eff.items())
            D.put(11, 14, (stats + "   " if stats else "") + f"{kg:.1f} kg each, you have {self.inv[k]}", "cyan")
            act = {"food": "[e]at", "drink": "[e] drink", "medical": "[a]pply",
                   "weapon": "[w]ield" if self.weapon != k else "[w] put away"}.get(kind, "")
            D.put(11, 16, f"{act}   [d]rop   [Q] back".strip(), "yellow")
        self._dos_place = D.blit_to(self.screen)

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
        if getattr(self, "cold_open", None):
            self.draw_cold_open()
            pygame.display.flip()
            return
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
            quiet_exit()
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
        g.w.close()
        print("at", g.px, g.py, g.here, "| hp", g.hp, "lvl", g.lvl, "xp", g.xp, "| mobs loaded", len(g.w.mobs), "|", " / ".join(g.msgs))
        return
    if getattr(g, "new_story", False):
        g.cold_open = time.monotonic()
    import signal                                        # rl-stop (or a shutdown) closes the game properly and saves
    signal.signal(signal.SIGTERM, lambda *_: pygame.event.post(pygame.event.Event(pygame.QUIT)))
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
    quiet_exit()                                         # sound off and window gone straight away...
    if not g.dead:
        g.save()                                         # ...then save (it can take a moment in a big world)
    p = getattr(g.w, "_map_proc", None)
    if p and p.poll() is None:
        p.terminate()                                    # an unfinished world map is just redrawn next time
    g.w.close()
    pygame.quit()


def quiet_exit():
    """stop every sound and close the window, so nothing carries on while the game shuts down"""
    try:
        if pygame.mixer.get_init():
            pygame.mixer.stop()
            pygame.mixer.quit()
    except pygame.error:
        pass
    pygame.display.quit()


if __name__ == "__main__":
    main()
