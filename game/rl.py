#!/usr/bin/env python3
"""Walkable prototype: wander the generated world, meet its creatures, fight.

  rl            carry on in your world (makes one the first time)
  rl --new      start a brand new world (new seed)
  rl --seed N   start a world from a given seed

Keys: arrows / WASD / numpad (7 9 1 3 diagonals) move, walk into a creature to attack,
      . or numpad 5 wait a turn, M world map, Esc saves and quits

Turn-based: every step or attack is one turn, then the creatures act.
The world is split into chunks (one world-map tile = 12 x 12 cells). A chunk is generated the first time
it comes near you, then written to disk with the creatures living there, so it never changes after that.
Saves: ~/.local/share/roguelike/
"""
import json, os, random, sys, time, warnings
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", message=".*avx2.*")
import numpy as np
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "proto"))
sys.path.insert(0, HERE)
import proto                                           # noqa: E402
import weird                                           # noqa: E402
import mobs                                            # noqa: E402
from weird_proto import world8                         # noqa: E402
from art import P, B, T, Painter                       # noqa: E402

SCALE = 2
CS = proto.ZS                                          # cells per chunk
PX = T * SCALE                                         # pixels per cell on screen
ROOT = os.environ.get("RL_HOME") or os.path.expanduser("~/.local/share/roguelike")
HUD_H, LOG_H = 30, 80
ACTIVE = 28                                            # creatures further away than this sleep

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


class World:
    def __init__(self, seed):
        self.seed = seed
        self.dir = os.path.join(ROOT, f"world-{seed}")
        os.makedirs(os.path.join(self.dir, "chunks"), exist_ok=True)
        self.wd = proto.World(seed)
        self.species = weird.Species(seed)
        self.best = mobs.Bestiary(seed)
        self.codes, self.surf = {}, {}
        self.mobs = {}                          # id -> Mob, for every loaded chunk
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
        p = self.path(cx, cy)
        new_mobs = []
        fresh = False
        if os.path.exists(p):                                       # been here: it's fixed now
            with open(p) as f:
                d = json.load(f)
            if isinstance(d, list):                                 # older save without creatures
                d = {"cells": d, "mobs": None}
            b = np.array(d["cells"], dtype="<U10")
            if d.get("mobs") is None:
                new_mobs = mobs.spawn(self.best, b, cx, cy, CS, self.tier(cx, cy), self.seed)
                fresh = True
            else:
                new_mobs = [mobs.Mob.from_json(m, self.best) for m in d["mobs"]]
        elif self.inside(cx, cy):
            b, _, _ = proto.gen_cells(self.wd, cx, cy, CS, CS)      # first visit: make it, then keep it
            new_mobs = mobs.spawn(self.best, b, cx, cy, CS, self.tier(cx, cy), self.seed)
            self.visited.add(k)
            fresh = True
        else:
            b = np.full((CS, CS), "deep", dtype="<U10")             # off the edge of the world
        self.codes[k] = b
        for m in new_mobs:
            if m.id not in self.dead:
                self.mobs[m.id] = m
        if fresh:
            self.write_chunk(cx, cy)
        return b

    def write_chunk(self, cx, cy):
        p = self.path(cx, cy)
        here = [m.to_json() for m in self.mobs.values() if m.x // CS == cx and m.y // CS == cy]
        with open(p + ".tmp", "w") as f:
            json.dump({"cells": self.codes[(cx, cy)].tolist(), "mobs": here}, f)
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

    def surface(self, cx, cy):
        """the chunk drawn once as palette indices; colours come from the (cycling) palette at draw time"""
        k = (cx, cy)
        if k in self.surf:
            return self.surf[k]
        b = self.chunk(cx, cy)
        p = weird.Painter8(CS, CS)
        j, i = np.mgrid[0:CS, 0:CS]
        R = proto.rnd_cells(cx * CS + i, cy * CS + j, self.seed + 99)
        for y in range(CS):
            for x in range(CS):
                weird.paint(p, self.species, x, y, b[y, x], R[y, x])
        s = pygame.image.frombuffer(p.img.tobytes(), (CS * T, CS * T), "P")
        s.set_palette([tuple(c) for c in weird.palette(0)])
        s = pygame.transform.scale(s, (CS * PX, CS * PX))
        if len(self.surf) > 600:
            self.surf.clear()
        self.surf[k] = s
        return s

    def world_map(self):
        if self.map_img is None:
            img = weird.to_rgb(world8(self.wd, self.species))
            self.map_img = pygame.image.frombuffer(np.ascontiguousarray(img).tobytes(), (img.shape[1], img.shape[0]), "RGB").copy()
        return self.map_img


class Game:
    def __init__(self, seed, screen):
        self.w = World(seed)
        self.screen = screen
        self.font = self.load_font(15)
        self.big = self.load_font(22, True)
        self.small = self.load_font(12)
        self.msgs = []
        self.show_map = False
        self.t0 = time.monotonic()
        self.last_save = time.monotonic()
        self.hero = self.make_hero()
        self.mob_img = {}
        self.flash = {}                     # mob id / "you" -> time of last hit
        self.dead = False
        self.killer = ""
        self.lvl, self.xp, self.turn = 1, 0, 0
        self.maxhp = 30
        st = self.load_state()
        if st:
            self.lvl, self.xp, self.turn = st.get("lvl", 1), st.get("xp", 0), st.get("turn", 0)
            self.maxhp = 30 + (self.lvl - 1) * 6
            self.hp = st.get("hp", self.maxhp)
            self.w.dead = set(st.get("dead", []))
            self.px, self.py = st["px"], st["py"]
            for i in self.w.dead:
                self.w.mobs.pop(i, None)
            self.say("Welcome back.")
        else:
            self.px, self.py = self.start_spot()
            self.hp = self.maxhp
            self.say("You arrive in a small town. Strange things live out there: walk into them to fight.")
        self.here = self.w.cell(self.px, self.py)
        for i in self.w.dead:
            self.w.mobs.pop(i, None)

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
        with open(os.path.join(ROOT, "current.json"), "w") as f:
            json.dump({"seed": self.w.seed}, f)
        self.last_save = time.monotonic()

    def say(self, m):
        self.msgs.append(m)
        self.msgs = self.msgs[-4:]

    # ── turns ──
    def act(self, dx, dy):
        if self.show_map or self.dead:
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
        if c in BLOCKED:
            self.say(BLOCKED[c])
            return
        before = len(self.w.visited)
        self.px, self.py = nx, ny
        if c != self.here:
            nm = NAMES.get(c, c)
            if c in ("shallow", "lake", "river"):
                self.say("You wade through the " + nm.lower() + ".")
            elif c not in ("road", "bridge", "plaza") or self.here not in ("road", "bridge", "plaza"):
                self.say(nm + ".")
            self.here = c
        if len(self.w.visited) > before and random.random() < 0.15:
            self.say("New land: you're the first to walk here.")
        self.end_turn()

    def wait(self):
        if not self.dead and not self.show_map:
            self.end_turn()

    def attack(self, m):
        hit = min(0.95, max(0.3, 0.82 + (self.lvl - m.sp.defn - m.tier) * 0.04))
        if not m.angry:
            m.angry = True
            self.say(f"The {m.name} turns on you!")
        if random.random() > hit:
            self.say(f"You miss the {m.name}.")
            return
        d = max(1, random.randint(2, 5) + self.lvl - 1 - m.sp.defn)
        m.hp -= d
        self.flash[m.id] = time.monotonic()
        if m.hp <= 0:
            self.w.mobs.pop(m.id, None)
            self.w.dead.add(m.id)
            gain = 4 + m.tier * 6 + m.maxhp // 3
            self.xp += gain
            self.say(f"You kill the {m.name}. (+{gain} xp)")
            while self.xp >= self.lvl * 25:
                self.xp -= self.lvl * 25
                self.lvl += 1
                self.maxhp += 6
                self.hp = self.maxhp
                self.say(f"You feel stronger: level {self.lvl}! Fully healed.")
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
            if not m.seen and dist <= 9:
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

    def hurt_by(self, m):
        if random.random() > 0.7:
            self.say(f"The {m.name} misses you.")
            return
        lo, hi = m.dmg()
        d = random.randint(lo, hi)
        self.hp -= d
        self.flash["you"] = time.monotonic()
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
        self.say("You wake up back in town, aching all over. (You lost your xp towards the next level.)")
        self.save()

    def handle(self, e):
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
            if k in moves:
                self.act(*moves[k])
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

    def draw_world(self):
        sw, sh = self.screen.get_size()
        vh = sh - HUD_H - LOG_H
        now = time.monotonic()
        t = now - self.t0
        cxp = self.px * PX + PX // 2 - sw // 2            # camera: player in the middle
        cyp = self.py * PX + PX // 2 - vh // 2
        self.screen.fill((0, 0, 0))
        c0x, c0y = cxp // (CS * PX), cyp // (CS * PX)
        c1x, c1y = (cxp + sw) // (CS * PX), (cyp + vh) // (CS * PX)
        self.screen.set_clip(pygame.Rect(0, HUD_H, sw, vh))
        pal = [tuple(c) for c in weird.palette(t)]          # the trippy bit: colours cycle every frame
        for cy in range(c0y, c1y + 1):
            for cx in range(c0x, c1x + 1):
                srf = self.w.surface(cx, cy)
                srf.set_palette(pal)
                self.screen.blit(srf, (cx * CS * PX - cxp, cy * CS * PX - cyp + HUD_H))
        for m in self.w.mobs.values():
            x, y = m.x * PX - cxp, m.y * PX - cyp + HUD_H
            if -PX < x < sw and HUD_H - PX < y < HUD_H + vh:
                pygame.draw.rect(self.screen, (0, 0, 0), (x + 2, y + 2, PX - 4, PX - 4))
                spr = self.mob_sprite(m)
                if now - self.flash.get(m.id, 0) < 0.15:
                    spr = spr.copy(); spr.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
                self.screen.blit(spr, (x, y))
                if m.hp < m.maxhp:
                    pygame.draw.rect(self.screen, (60, 0, 0), (x + 3, y - 3, PX - 6, 3))
                    pygame.draw.rect(self.screen, (230, 50, 50), (x + 3, y - 3, int((PX - 6) * m.hp / m.maxhp), 3))
        hx, hy = self.px * PX - cxp, self.py * PX - cyp + HUD_H
        pygame.draw.rect(self.screen, (0, 0, 0), (hx + 2, hy + 2, PX - 4, PX - 4))
        self.screen.blit(self.hero, (hx, hy))
        self.screen.set_clip(None)
        if now - self.flash.get("you", 0) < 0.2:           # red flash when you're hurt
            ov = pygame.Surface((sw, vh), pygame.SRCALPHA)
            ov.fill((200, 0, 0, 60))
            self.screen.blit(ov, (0, HUD_H))

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
        self.screen.fill((0, 0, 0))
        self.screen.blit(ms, (ox, oy))
        if int((time.monotonic() - self.t0) * 3) % 2 == 0:
            x, y = ox + (self.px / CS) * tw, oy + (self.py / CS) * th
            pygame.draw.circle(self.screen, (255, 255, 255), (int(x), int(y)), max(4, int(tw * 0.5)), 2)
        hint = self.font.render("Bright = places you've been.   M or Esc closes the map", True, (170, 170, 170))
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
        info = f"Level {self.lvl}   XP {self.xp}/{self.lvl * 25}   Turn {self.turn}   Danger " + "*" * danger
        self.screen.blit(self.font.render(info, True, (190, 190, 200)), (bx + 175, 5))
        expl = self.font.render(f"Explored {len(self.w.visited)}   Seed {self.w.seed}", True, (110, 110, 120))
        self.screen.blit(expl, (sw - expl.get_width() - 10, 6))
        for n, msg in enumerate(self.msgs):
            col = (225, 225, 225) if n == len(self.msgs) - 1 else (125, 125, 135)
            self.screen.blit(self.font.render(msg, True, col), (10, sh - LOG_H + 2 + n * 19))
        keys = self.small.render("Move/attack: arrows WASD numpad   . wait   M map   Esc save & quit", True, (100, 100, 110))
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
    pygame.key.set_repeat(170, 60)
    screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE)
    pygame.display.set_caption("Roguelike prototype")
    screen.fill((0, 0, 0))
    f = pygame.font.Font(None, 36)
    screen.blit(f.render("Making the world…", True, (220, 220, 220)), (40, 40))
    pygame.display.flip()
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
        g.frame()
        clock.tick(30)
    if not g.dead:
        g.save()
    pygame.quit()


if __name__ == "__main__":
    main()
