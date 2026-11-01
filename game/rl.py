#!/usr/bin/env python3
"""Walkable prototype: wander the generated world.

  rl            carry on in your world (makes one the first time)
  rl --new      start a brand new world (new seed)
  rl --seed N   start a world from a given seed

Keys: arrows / WASD / numpad (7 9 1 3 for diagonals) move, hold to keep walking
      M world map, . or numpad 5 wait, Esc saves and quits

The world is split into chunks (one world-map tile = 12 x 12 cells). A chunk is generated the first time
you walk near it, then written to disk, so after that it never changes.
Saves: ~/.local/share/roguelike/
"""
import json, os, sys, time
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy as np
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "proto"))
import proto                                           # noqa: E402
from art import P, B, T, Painter                       # noqa: E402

SCALE = 2
CS = proto.ZS                                          # cells per chunk
PX = T * SCALE                                         # pixels per cell on screen
ROOT = os.environ.get("RL_HOME") or os.path.expanduser("~/.local/share/roguelike")
HUD_H, LOG_H = 30, 58

NAMES = {"deep": "Deep sea", "ocean": "Ocean", "shallow": "Shallows", "beach": "Beach", "seaice": "Sea ice",
         "icesheet": "Ice sheet", "drift": "Snowdrifts", "tundra": "Tundra", "taiga": "Snow forest", "grass": "Grassland",
         "meadow": "Meadow", "savanna": "Savanna", "forest": "Forest", "jungle": "Jungle", "swamp": "Swamp",
         "desert": "Desert", "salt": "Salt flats", "badlands": "Badlands", "hills": "Hills", "mountain": "Mountains",
         "peak": "Snowy peaks", "ash": "Ash wastes", "lava": "Lava", "crust": "Cooling lava", "volcano": "Volcano",
         "fungal": "Fungal forest", "crystal": "Crystal fields", "lake": "Lake", "river": "River", "road": "Road",
         "bridge": "Bridge", "house": "House", "plaza": "Town"}
BLOCKED = {"deep": "The water's too deep to swim.", "ocean": "The water's too deep to swim.",
           "mountain": "The rock face is too steep.", "peak": "The peak is too steep to climb.",
           "house": "Someone lives there.", "lava": "Lava! Far too hot to step in."}
ANIM = {"shallow", "ocean", "deep", "lake", "river", "lava", "crust"}


class World:
    def __init__(self, seed):
        self.seed = seed
        self.dir = os.path.join(ROOT, f"world-{seed}")
        os.makedirs(os.path.join(self.dir, "chunks"), exist_ok=True)
        self.wd = proto.World(seed)
        self.codes, self.surf, self.anim = {}, {}, {}
        self.visited = {tuple(map(int, f[:-5].split("_"))) for f in os.listdir(os.path.join(self.dir, "chunks")) if f.endswith(".json")}
        self.map_img = None

    def inside(self, cx, cy):
        return 0 <= cx < proto.W and 0 <= cy < proto.H

    def chunk(self, cx, cy):
        k = (cx, cy)
        if k in self.codes:
            return self.codes[k]
        path = os.path.join(self.dir, "chunks", f"{cx}_{cy}.json")
        if os.path.exists(path):                                    # been here: it's fixed now
            with open(path) as f:
                b = np.array(json.load(f), dtype="<U10")
        elif self.inside(cx, cy):
            b, _, _ = proto.gen_cells(self.wd, cx, cy, CS, CS)      # first visit: make it, then keep it
            with open(path + ".tmp", "w") as f:
                json.dump(b.tolist(), f)
            os.replace(path + ".tmp", path)
            self.visited.add(k)
        else:
            b = np.full((CS, CS), "deep", dtype="<U10")             # off the edge of the world
        self.codes[k] = b
        self.anim[k] = bool(np.isin(b, list(ANIM)).any())
        return b

    def cell(self, gx, gy):
        b = self.chunk(gx // CS, gy // CS)
        return str(b[gy % CS, gx % CS])

    def surface(self, cx, cy, t):
        k = (cx, cy)
        frame = int(t * 3) if self.anim.get(k) else 0
        hit = self.surf.get(k)
        if hit and hit[0] == frame:
            return hit[1]
        b = self.chunk(cx, cy)
        p = Painter(CS, CS)
        j, i = np.mgrid[0:CS, 0:CS]
        R = proto.rnd_cells(cx * CS + i, cy * CS + j, self.seed + 99)
        for y in range(CS):
            for x in range(CS):
                proto.paint(p, x, y, b[y, x], R[y, x], local=True, t=frame / 3)
        s = pygame.image.frombuffer(p.img.tobytes(), (CS * T, CS * T), "RGB")
        s = pygame.transform.scale(s, (CS * PX, CS * PX))
        if len(self.surf) > 400:
            self.surf.clear()
        self.surf[k] = (frame, s)
        return s

    def world_map(self):
        if self.map_img is None:
            img = proto.render_world(self.wd)
            self.map_img = pygame.image.frombuffer(img.tobytes(), (img.shape[1], img.shape[0]), "RGB").copy()
        return self.map_img


class Game:
    def __init__(self, seed, screen):
        self.w = World(seed)
        self.screen = screen
        self.font = self.load_font(15)
        self.big = self.load_font(22, True)
        self.msgs = []
        self.show_map = False
        self.t0 = time.monotonic()
        self.last_save = time.monotonic()
        self.hero = self.make_hero()
        st = self.load_state()
        if st:
            self.px, self.py = st["px"], st["py"]
            self.say("Welcome back.")
        else:
            self.px, self.py = self.start_spot()
            self.say("You arrive in a small town. The world is yours to wander.")
        self.here = self.w.cell(self.px, self.py)

    # ── setup ──
    def load_font(self, sz, bold=False):
        f = "/usr/share/fonts/noto/NotoSans-%s.ttf" % ("Bold" if bold else "Regular")
        return pygame.font.Font(f if os.path.exists(f) else None, sz)

    def make_hero(self):
        p = Painter(1, 1)
        p.img[:] = 0
        p.bitmap(0, 0, B["hero"], [P["hero"], P["heroC"]])
        s = pygame.image.frombuffer(p.img.tobytes(), (T, T), "RGB").copy()
        s.set_colorkey((0, 0, 0))
        return pygame.transform.scale(s, (PX, PX))

    def start_spot(self):
        towns = self.w.wd.towns
        tx, ty = towns[0] if towns else (proto.W // 2, proto.H // 2)
        gx, gy = tx * CS + CS // 2, ty * CS + CS // 2
        for r in range(0, 30):                       # nearest open ground
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and self.w.cell(gx + dx, gy + dy) not in BLOCKED:
                        return gx + dx, gy + dy
        return gx, gy

    def state_path(self):
        return os.path.join(self.w.dir, "player.json")

    def load_state(self):
        try:
            with open(self.state_path()) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def save(self):
        with open(self.state_path() + ".tmp", "w") as f:
            json.dump({"px": self.px, "py": self.py}, f)
        os.replace(self.state_path() + ".tmp", self.state_path())
        with open(os.path.join(ROOT, "current.json"), "w") as f:
            json.dump({"seed": self.w.seed}, f)
        self.last_save = time.monotonic()

    def say(self, m):
        self.msgs.append(m)
        self.msgs = self.msgs[-3:]

    # ── play ──
    def move(self, dx, dy):
        if self.show_map:
            return
        nx, ny = self.px + dx, self.py + dy
        if not self.w.inside(nx // CS, ny // CS):
            self.say("The edge of the known world. Nothing but sea beyond.")
            return
        before = len(self.w.visited)
        c = self.w.cell(nx, ny)
        if c in BLOCKED:
            self.say(BLOCKED[c])
            return
        self.px, self.py = nx, ny
        if c != self.here:
            nm = NAMES.get(c, c)
            if c in ("shallow", "lake", "river"):
                self.say("You wade through the " + nm.lower() + ".")
            elif c not in ("road", "bridge", "plaza") or self.here not in ("road", "bridge", "plaza"):
                self.say(nm + ".")
            self.here = c
        if len(self.w.visited) > before:
            self.say("New land: you're the first to walk here.")

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            k = e.key
            moves = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
                     pygame.K_a: (-1, 0), pygame.K_d: (1, 0), pygame.K_w: (0, -1), pygame.K_s: (0, 1),
                     pygame.K_h: (-1, 0), pygame.K_l: (1, 0), pygame.K_k: (0, -1), pygame.K_j: (0, 1),
                     pygame.K_KP4: (-1, 0), pygame.K_KP6: (1, 0), pygame.K_KP8: (0, -1), pygame.K_KP2: (0, 1),
                     pygame.K_KP7: (-1, -1), pygame.K_KP9: (1, -1), pygame.K_KP1: (-1, 1), pygame.K_KP3: (1, 1)}
            if k in moves:
                self.move(*moves[k])
            elif k == pygame.K_m:
                self.show_map = not self.show_map
                if self.show_map:
                    self.draw_text_center("Drawing the map…")
            elif k in (pygame.K_PERIOD, pygame.K_KP5):
                self.say("You wait a moment.")
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

    def draw_world(self):
        sw, sh = self.screen.get_size()
        vh = sh - HUD_H - LOG_H
        t = time.monotonic() - self.t0
        cxp = self.px * PX + PX // 2 - sw // 2            # camera: player in the middle
        cyp = self.py * PX + PX // 2 - vh // 2
        self.screen.fill(P["void"])
        c0x, c0y = cxp // (CS * PX), cyp // (CS * PX)
        c1x, c1y = (cxp + sw) // (CS * PX), (cyp + vh) // (CS * PX)
        clip = pygame.Rect(0, HUD_H, sw, vh)
        self.screen.set_clip(clip)
        for cy in range(c0y, c1y + 1):
            for cx in range(c0x, c1x + 1):
                self.screen.blit(self.w.surface(cx, cy, t), (cx * CS * PX - cxp, cy * CS * PX - cyp + HUD_H))
        self.screen.blit(self.hero, (self.px * PX - cxp, self.py * PX - cyp + HUD_H))
        self.screen.set_clip(None)

    def draw_map(self):
        sw, sh = self.screen.get_size()
        m = self.w.world_map()
        avail_w, avail_h = sw - 40, sh - HUD_H - LOG_H - 20
        k = min(avail_w / m.get_width(), avail_h / m.get_height())
        mw, mh = int(m.get_width() * k), int(m.get_height() * k)
        ms = pygame.transform.smoothscale(m, (mw, mh))
        fog = pygame.Surface((mw, mh), pygame.SRCALPHA)
        fog.fill((0, 0, 0, 170))
        tw, th = mw / proto.W, mh / proto.H
        for (cx, cy) in self.w.visited:          # places you've been show clearly
            pygame.draw.rect(fog, (0, 0, 0, 0), (int(cx * tw), int(cy * th), int(tw) + 1, int(th) + 1))
        ms.blit(fog, (0, 0))
        ox, oy = (sw - mw) // 2, HUD_H + 10
        self.screen.fill(P["void"])
        self.screen.blit(ms, (ox, oy))
        if int((time.monotonic() - self.t0) * 3) % 2 == 0:
            x, y = ox + (self.px / CS) * tw, oy + (self.py / CS) * th
            pygame.draw.circle(self.screen, (255, 255, 255), (int(x), int(y)), max(4, int(tw * 0.5)), 2)
        hint = self.font.render("Bright = places you've been.   M or Esc closes the map", True, (170, 170, 170))
        self.screen.blit(hint, (ox, oy + mh + 4))

    def draw_hud(self):
        sw, sh = self.screen.get_size()
        pygame.draw.rect(self.screen, (18, 16, 24), (0, 0, sw, HUD_H))
        pygame.draw.rect(self.screen, (18, 16, 24), (0, sh - LOG_H, sw, LOG_H))
        name = NAMES.get(self.here, self.here)
        self.screen.blit(self.big.render(name, True, (240, 220, 160)), (10, 1))
        info = f"Map square {self.px // CS}, {self.py // CS}    Explored {len(self.w.visited)} / {proto.W * proto.H}    Seed {self.w.seed}"
        img = self.font.render(info, True, (150, 150, 160))
        self.screen.blit(img, (sw - img.get_width() - 10, 6))
        for n, m in enumerate(self.msgs):
            col = (220, 220, 220) if n == len(self.msgs) - 1 else (130, 130, 140)
            self.screen.blit(self.font.render(m, True, col), (10, sh - LOG_H + 3 + n * 18))
        keys = self.font.render("Arrows/WASD move   M map   Esc save & quit", True, (110, 110, 120))
        self.screen.blit(keys, (sw - keys.get_width() - 10, sh - 22))

    def frame(self):
        if self.show_map:
            self.draw_map()
        else:
            self.draw_world()
        self.draw_hud()
        pygame.display.flip()
        if time.monotonic() - self.last_save > 30:
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
    pygame.key.set_repeat(170, 60)
    screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE)
    pygame.display.set_caption("Roguelike prototype")
    screen.fill(P["void"])
    f = pygame.font.Font(None, 36)
    screen.blit(f.render("Making the world…", True, (220, 220, 220)), (40, 40))
    pygame.display.flip()
    g = Game(pick_seed(args), screen)
    g.save()
    if "--shot" in args:                                  # testing: --shot PATH [--moves LRUD...] [--map]
        for ch in args[args.index("--moves") + 1] if "--moves" in args else "":
            g.move(*{"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}[ch])
        g.show_map = "--map" in args
        g.frame()
        pygame.image.save(screen, args[args.index("--shot") + 1])
        g.save()
        print("at", g.px, g.py, g.here, "| visited", len(g.w.visited), "|", " / ".join(g.msgs))
        return
    clock = pygame.time.Clock()
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif not g.handle(e):
                running = False
        g.frame()
        clock.tick(30)
    g.save()
    pygame.quit()


if __name__ == "__main__":
    main()
