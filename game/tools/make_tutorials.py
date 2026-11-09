"""Records the tutorial clips shown on the selection screen: each head power used in a real game world, against
creatures held still for the camera. Writes game/assets/tutorials/<power>.jpg, a filmstrip of 208x130 frames at 15 fps.
Run:  python3 game/tools/make_tutorials.py   (takes about a minute; re-run whenever the powers change)"""
import os, sys, json, time, shutil, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"
HOME = tempfile.mkdtemp(prefix="rl-tut-")
os.environ["RL_HOME"] = HOME
GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GAME)
import pygame
from PIL import Image
import rl, charcreate, mobs, heads

FW, FH, FPS, SECS = 208, 130, 15, 3.6
OUT = os.path.join(GAME, "assets", "tutorials")
pygame.init()
screen = pygame.display.set_mode((1280, 800))
names = {a["name"]: a for a in charcreate.ARCH}

for power, cls in heads.CLASS_FOR.items():
    a = names[cls]
    hat, weapon, back, extra, coat, trim = a["look"]
    json.dump({"name": "Tutorial", "archetype": cls, "body": "人", "skin_rgb": [206, 160, 118],
               "look": [hat, weapon, back, extra], "coat": list(coat), "trim": list(trim),
               "stats": dict(zip(charcreate.STATS, a["stats"])), "traits": [t for t, _ in a["traits"]], "kit": a["kit"],
               "mutation": None, "head": a["head"]}, open(os.path.join(HOME, "character.json"), "w"), ensure_ascii=False)
    for f in os.listdir(HOME):
        if f.startswith("world-"):
            shutil.rmtree(os.path.join(HOME, f))
    g = rl.Game(4242, screen)
    g.turn = 300
    for _ in range(60):                                       # somewhere open to the east
        if all(not g.blocked(g.px + k, g.py) for k in range(1, 7)):
            break
        g.px += 1; g.py += 1; g.update(0.01)
    g.update(0.01); g._vkey = None; g.update_view()
    g.facing = (1, 0)
    g.zoom = 4; g.set_size(1.0)
    sp = g.w.best.species("grass", 0)
    where = {"shield": ((1, 0), (-1, 1), (0, -2)), "spin": ((2, 0), (-2, 1), (1, 2)), "nova": ((2, 0), (-2, 1), (1, 2)),
             "scout": ((8, -3), (9, -2), (10, -4))}.get(power, ((4, 0), (5, -1), (5, 1)))
    for j, (dx, dy) in enumerate(where):
        m = mobs.Mob(sp, 0, 3, g.px + dx, g.py + dy, f"tut{j}")
        g.w.mobs[m.id] = m
        g.mob_fx[m.id] = {"stun": 999}                         # held still for the camera
    for _ in range(30):                                       # let the area finish loading
        g.frame()
    frames, start = [], time.monotonic()
    steps = int(SECS * 30)
    for i in range(steps):
        demo = [m for m in g.w.mobs.values() if m.id.startswith("tut")]
        aim = lambda m: (m.x + 0.5, m.y + 0.5)
        if i in (8, 50) or (power in ("fire", "frost", "storm", "rot", "boomerang") and i == 75):
            g.head_ready = 0
            if power == "scout":
                g.use_head((g.px + 9, g.py - 3)) if i == 8 else None
            elif demo and power not in ("shield", "spin", "nova"):
                g.use_head(aim(demo[min(len(demo) - 1, (i // 40))]))
            elif i == 8:
                g.use_head()
        g.update(1 / 30)
        g.frame()
        if i % (30 // FPS) == 0:
            sub = screen.subsurface(pygame.Rect(240, 150, 800, 500)).copy()
            im = Image.frombytes("RGB", sub.get_size(), pygame.image.tobytes(sub, "RGB")).resize((FW, FH), Image.LANCZOS)
            frames.append(im)
        time.sleep(max(0, (i + 1) / 30 - (time.monotonic() - start)))   # cooldowns run on real time
    strip = Image.new("RGB", (FW * len(frames), FH))
    for k, im in enumerate(frames):
        strip.paste(im, (k * FW, 0))
    strip.save(os.path.join(OUT, f"{power}.jpg"), quality=82)
    print(power, len(frames), "frames")
shutil.rmtree(HOME, ignore_errors=True)
