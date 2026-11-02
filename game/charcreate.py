"""Character creation: 20 bodies drawn from Japanese characters (given a head, coloured like clothing,
with anchor points for hat / hands / back so they can wear and hold gear) x 10 archetypes.

Keys: up/down archetype, left/right body, C skin, R randomise, N new name, Enter keep, Esc quit.
Saves the chosen character to ~/.local/share/roguelike/character.json.
"""
import json, math, os, random, time
import numpy as np
import pygame
from PIL import Image, ImageDraw, ImageFont

CJK = "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"
UI = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
UIB = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
N = 64                                   # sprite canvas

# 20 bodies: (glyph, what it means)
BODIES = [("人", "person"), ("大", "big"), ("天", "heaven"), ("夫", "husband"), ("太", "thick"), ("女", "woman"),
          ("子", "child"), ("兵", "soldier"), ("立", "stand"), ("走", "run"), ("光", "light"), ("元", "origin"),
          ("兄", "elder brother"), ("先", "ahead"), ("鬼", "demon"), ("侍", "samurai"), ("央", "centre"),
          ("ス", "su"), ("ヌ", "nu"), ("メ", "me")]

SKINS = [("Umber", (150, 104, 76)), ("Ochre", (206, 160, 118)), ("Pale", (232, 206, 186)), ("Ash", (176, 176, 168)),
         ("Moss", (126, 170, 104)), ("Dusk", (138, 132, 190))]

# 10 archetypes. stats: STR AGI TOU WIT CHA LCK. kit visuals: hat, weapon, back, extra, coat colour, trim colour
ARCH = [
    dict(name="Bounty Hunter", tag="Bebop", blurb="Chases warrants across the dead worlds for whatever they pay. Never asks why.",
         stats=(5, 7, 5, 5, 4, 5), traits=[("Tracker", "+ follows tracks others miss"), ("Quick draw", "+ shoots first in a fight"),
                                          ("Broke", "- starts with almost no money")],
         kit=["Revolver", "Duster coat", "Wide-brim hat", "Handcuffs", "Warrant"], look=("cowboy", "revolver", "duster", None, (110, 74, 48), (210, 170, 90))),
    dict(name="Netrunner", tag="Bebop", blurb="Talks to machines better than people. Breaks locks, cameras and minds made of code.",
         stats=(2, 6, 3, 9, 4, 6), traits=[("Wired", "+ hacks terminals and drones"), ("Night owl", "+ sharper at night"),
                                          ("Frail", "- low health")],
         kit=["Deck", "Hoodie", "Goggles", "Energy drinks", "Spare cables"], look=("hood", "deck", None, "goggles", (60, 64, 92), (90, 230, 210))),
    dict(name="Ex-Cop", tag="Bebop", blurb="Used to wear a badge. Still has the arm they gave you when you lost yours.",
         stats=(7, 4, 7, 5, 5, 3), traits=[("Iron arm", "+ hits hard, blocks blades"), ("Old habits", "+ spots lies"),
                                          ("Bad back", "- carries less")],
         kit=["Shotgun", "Armour vest", "Cap", "Bonsai", "Notebook"], look=("cap", "shotgun", None, "vest", (64, 78, 72), (180, 180, 170))),
    dict(name="Grifter", tag="Bebop", blurb="Owes money on four planets. Smiles their way out of most of it.",
         stats=(3, 7, 3, 6, 8, 7), traits=[("Silver tongue", "+ better prices, talks down fights"), ("Lucky", "+ finds more loot"),
                                          ("Gambler", "- can't walk past a bet")],
         kit=["Derringer", "Deck of cards", "Silk scarf", "Fake ID", "Lipstick"], look=(None, "derringer", None, "scarf", (150, 36, 60), (240, 210, 90))),
    dict(name="Drifter Pilot", tag="Bebop", blurb="Can fly anything with an engine. Crashed the last one. That's why you're here.",
         stats=(5, 8, 5, 5, 4, 4), traits=[("Ace", "+ flies and repairs ships"), ("Brawler", "+ fights well unarmed"),
                                          ("Drifting", "- forgets what they're doing")],
         kit=["Knife", "Flight jacket", "Aviator goggles", "Cigarettes", "Ship part"], look=("goggles", "knife", None, "scarf", (42, 66, 120), (230, 190, 70))),
    dict(name="Survivalist", tag="Zomboid", blurb="Was ready for the end before it came. Boards up windows for fun.",
         stats=(6, 5, 7, 5, 3, 4), traits=[("Forager", "+ finds food and water"), ("Light sleeper", "+ wakes when danger comes"),
                                          ("Paranoid", "- hates crowds")],
         kit=["Fire axe", "Backpack", "Beanie", "Canned beans", "Matches"], look=("beanie", "axe", "pack", None, (86, 96, 54), (170, 120, 60))),
    dict(name="Field Medic", tag="Zomboid", blurb="Patched up the dying until there were none left to patch. Steady hands, tired eyes.",
         stats=(3, 5, 4, 8, 6, 4), traits=[("Steady hands", "+ heals better, stops bleeding"), ("Calm", "+ doesn't panic"),
                                          ("Squeamish", "- hates gore")],
         kit=["Scalpel", "Medkit", "Scrubs", "Painkillers", "Bandages"], look=("cap2", "scalpel", "pack", None, (70, 140, 130), (230, 230, 230))),
    dict(name="Colony Engineer", tag="RimWorld", blurb="Built half a colony before the raid. Will build the rest out of scrap if they have to.",
         stats=(5, 4, 5, 7, 4, 5), traits=[("Builder", "+ builds and repairs fast"), ("Tinkerer", "+ makes parts from junk"),
                                          ("Slow", "- walks slower")],
         kit=["Wrench", "Toolbelt", "Hard hat", "Duct tape", "Blueprint"], look=("hardhat", "wrench", None, "belt", (190, 110, 36), (240, 210, 80))),
    dict(name="Mutant Pilgrim", tag="Qud", blurb="Born changed, walking the salt roads to somewhere sacred. The change is still going.",
         stats=(6, 5, 6, 4, 3, 6), traits=[("Mutation", "+ a random mutation"), ("Pilgrim", "+ walks far without tiring"),
                                          ("Outcast", "- towns don't trust you")],
         kit=["Staff", "Travel cloak", "Hood", "Water skin", "Prayer beads"], look=("hood", "staff", "cloak", "mutation", (120, 96, 70), (130, 220, 120))),
    dict(name="Esper", tag="Qud", blurb="Hears thoughts like radio static. Some of the voices aren't from people.",
         stats=(3, 5, 4, 9, 6, 4), traits=[("Telepath", "+ senses minds through walls"), ("Psychic shield", "+ resists mind attacks"),
                                          ("Migraines", "- powers hurt to use")],
         kit=["Tome", "Robe", "Circlet", "Incense", "Strange stone"], look=("circlet", "tome", "cloak", None, (70, 46, 110), (200, 140, 255))),
]
MUTATIONS = ["Carapace (+ armour, - speed)", "Quills (hurts what hits you)", "Photosynthetic skin (+ heals in sun)",
             "Electrical generation (shocks)", "Night vision", "Regeneration", "Extra arms (+ carry, + grip)"]
FIRST = ["Kaito", "Rin", "Juno", "Vex", "Mara", "Toshi", "Calla", "Ezra", "Nori", "Dax", "Yuki", "Sable", "Ike",
         "Wren", "Hiro", "Lux", "Moss", "Saki", "Fen", "Rook", "Aiko", "Bastian", "Kenji", "Odile"]
LAST = ["Kurogane", "Vance", "Hollow", "Ashby", "Mizuno", "Crane", "Tetsu", "Graves", "Okabe", "Reyes", "Sorrow",
        "Black", "Hayashi", "Quill", "Starling", "Noda", "Marlowe", "Ibuki"]

# small pixel art for gear: chars = colours (h hat, H hat dark, b band/trim, w metal, W dark metal, g grip, p pack,
# P pack dark, x glow)
GEAR = {
    "cowboy": ["   hhhh   ", "   hbbh   ", "hhhhhhhhhh", " HHHHHHHH "],
    "cap": ["  hhhh   ", " hhhhhhhh", "  HH     "],
    "cap2": ["  hhhh  ", " hhbhhh ", " hhhhhh "],
    "hardhat": ["  hhhh  ", " hhhhhh ", "hhhhhhhh", "HHHHHHHH"],
    "beanie": ["  bb  ", " hhhh ", "hhhhhh", "HHHHHH"],
    "hood": ["  hhhh  ", " hh  hh ", "hh    hh", "h      h", "h      h"],
    "goggles": ["WbbWWbbW"],
    "circlet": ["x b  b x"],
    "revolver": ["WWWWWw", "Wgg   ", " gg   "],
    "shotgun": ["wwwwwwwWgg", "     WWgg "],
    "derringer": ["Wwww", "gg  "],
    "axe": ["WWw ", "WWWw", "  g ", "  g ", "  g ", "  g "],
    "scalpel": ["w", "w", "g", "g"],
    "wrench": ["w w", "www", " g ", " g ", " g "],
    "staff": [" x ", "xgx", " g ", " g ", " g ", " g ", " g ", " g ", " g ", " g ", " g "],
    "knife": ["w", "w", "w", "g", "g"],
    "deck": ["WWWWW", "WxxxW", "WxxxW", "WWWWW"],
    "tome": ["PPPP", "PxxP", "PPPP"],
    "pack": ["pppp", "pPPp", "pppp", "pPPp", "pppp"],
}


def _font(path, size):
    try:
        return pygame.font.Font(path, size)
    except Exception:
        return pygame.font.Font(None, size)


class Body:
    """one character drawn from a glyph, with anchors for gear"""

    def __init__(self, glyph):
        try:
            f = ImageFont.truetype(CJK, 48, index=0)
        except OSError:
            f = ImageFont.load_default()
        img = Image.new("L", (N, N), 0)
        ImageDraw.Draw(img).text((N // 2, 40), glyph, font=f, fill=255, anchor="mm")
        m = np.array(img) > 110
        ys, xs = np.nonzero(m)
        top, bot = ys.min(), ys.max()
        tx = int(np.mean(xs[ys < top + 4]))
        self.head = (tx, top - 6)                          # the edit: a head above the glyph
        yy, xx = np.mgrid[0:N, 0:N]
        self.headmask = (xx - tx) ** 2 + (yy - (top - 6)) ** 2 <= 4.6 ** 2
        self.mask = m
        mid = (ys > top + (bot - top) * 0.3) & (ys < top + (bot - top) * 0.65)
        self.rhand = (int(xs[mid].max()), int(np.mean(ys[mid][xs[mid] >= xs[mid].max() - 1])))
        self.lhand = (int(xs[mid].min()), int(np.mean(ys[mid][xs[mid] <= xs[mid].min() + 1])))
        self.top, self.bot = top, bot
        self.back = (int(np.mean(xs)), int(top + (bot - top) * 0.35))
        self.waist = int(top + (bot - top) * 0.45)


def _stamp(a, art, x0, y0, cols):
    for j, row in enumerate(art):
        for i, ch in enumerate(row):
            if ch != " " and ch in cols:
                x, y = x0 + i, y0 + j
                if 0 <= x < N and 0 <= y < N:
                    a[y, x] = cols[ch] + (255,)


def render(body, arch, skin, mut=None):
    """the character as an RGBA array (N x N)"""
    hat, weapon, back, extra, coat, trim = arch["look"]
    a = np.zeros((N, N, 4), np.uint8)
    dark = tuple(int(v * 0.6) for v in coat)
    cols = {"h": coat if hat not in ("goggles", "circlet") else trim, "H": dark, "b": trim, "w": (200, 204, 210),
            "W": (90, 94, 104), "g": (110, 76, 46), "p": (120, 100, 60), "P": (80, 64, 40), "x": trim}
    if back == "cloak":                                      # behind everything: a cloak hanging off the shoulders
        for y in range(body.top + 2, body.bot + 2):
            w = 4 + (y - body.top) * 0.35
            for x in range(int(body.back[0] - w), int(body.back[0] + w) + 1):
                if 0 <= x < N and 0 <= y < N:
                    a[y, x] = dark + (255,)
    if back == "pack":
        _stamp(a, GEAR["pack"], body.back[0] - 6, body.back[1] - 2, cols)
    up = body.top + (body.bot - body.top) * 0.33              # skin above, clothes below
    ys, xs = np.nonzero(body.mask)
    for y, x in zip(ys, xs):
        a[y, x] = (skin if y < up else coat) + (255,)
    if back == "duster":                                      # a long coat flaring out at the bottom
        for y in range(int(body.top + (body.bot - body.top) * 0.6), body.bot + 1):
            row = xs[ys == y]
            if len(row):
                for x in range(row.min() - 2, row.max() + 3):
                    if 0 <= x < N and not body.mask[y, x]:
                        a[y, x] = dark + (255,)
    a[body.headmask] = skin + (255,)
    hx, hy = body.head
    if extra == "vest":
        for y in range(int(up), body.waist + 3):
            row = xs[ys == y]
            if len(row):
                a[y, row.min():row.max() + 1][body.mask[y, row.min():row.max() + 1]] = trim + (255,)
    if extra == "scarf":
        _stamp(a, ["bbbbbb", " bb   ", " b    "], hx - 3, hy + 4, cols)
    if extra == "belt":
        row = xs[ys == body.waist]
        if len(row):
            a[body.waist, row.min() - 1:row.max() + 2] = trim + (255,)
            a[body.waist + 1, row.min():row.max() + 1:3] = (90, 94, 104, 255)
    if extra == "mutation" and mut:
        r = random.Random(mut)
        glow = {"Carapace": (90, 70, 110), "Quills": (230, 220, 200), "Photosynthetic": (90, 220, 90),
                "Electrical": (120, 220, 255), "Night": (240, 240, 120), "Regeneration": (240, 90, 120), "Extra": coat}
        g = next((v for k, v in glow.items() if mut.startswith(k)), trim)
        if mut.startswith("Quills"):
            for k in range(6):
                x, y = body.back[0] - 6 + k * 2, body.back[1] - 2 + (k % 2)
                a[y - 3:y, x] = g + (255,)
        elif mut.startswith("Extra"):
            lx, ly = body.lhand
            for k in range(7):
                if 0 <= lx - k < N and ly + 6 - k // 2 < N:
                    a[ly + 6 - k // 2, lx - k] = skin + (255,)
        else:
            for _ in range(10):
                y, x = ys[r.randrange(len(ys))], xs[r.randrange(len(xs))]
                a[y, x] = g + (255,)
    if hat in ("goggles", "circlet"):
        _stamp(a, GEAR[hat], hx - 4, hy - 1, cols)
    elif hat:
        art = GEAR[hat]
        _stamp(a, art, hx - len(art[0]) // 2, hy - 4 - len(art) + 3, cols)
    if weapon:
        art = GEAR[weapon]
        rx, ry = body.rhand
        gy = next((j for j, row in enumerate(art) if "g" in row), 0)
        gx = art[gy].index("g") if "g" in art[gy] else 0
        _stamp(a, art, rx + 1 - gx, ry - gy, cols)
    return a


def to_surface(a, scale):
    s = pygame.image.frombuffer(a.tobytes(), (N, N), "RGBA").copy()
    return pygame.transform.scale(s, (N * scale, N * scale))


def wrap(font, text, w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if font.size(t)[0] > w and cur:
            lines.append(cur); cur = wd
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def run(screen, root, shot=None, setup=None):
    """the character creation screen. Returns when Esc is pressed. (shot = save one frame there and return: testing)"""
    pygame.display.set_caption("New drifter")
    big, mid, small, tiny = _font(UIB, 34), _font(UIB, 20), _font(UI, 16), _font(UI, 13)
    cjk = _font(CJK, 40)
    bodies = [Body(g) for g, _ in BODIES]
    st = dict(arch=0, body=0, skin=1, name=f"{random.choice(FIRST)} {random.choice(LAST)}", mut=random.choice(MUTATIONS))
    cache, msg, msg_t = {}, "", 0
    clock = pygame.time.Clock()
    t0 = time.monotonic()
    if setup:
        st.update(setup)
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
            if e.type == pygame.KEYDOWN:
                k = e.key
                if k == pygame.K_ESCAPE:
                    return
                if k in (pygame.K_UP, pygame.K_w):
                    st["arch"] = (st["arch"] - 1) % len(ARCH)
                elif k in (pygame.K_DOWN, pygame.K_s):
                    st["arch"] = (st["arch"] + 1) % len(ARCH)
                elif k in (pygame.K_LEFT, pygame.K_a):
                    st["body"] = (st["body"] - 1) % len(BODIES)
                elif k in (pygame.K_RIGHT, pygame.K_d):
                    st["body"] = (st["body"] + 1) % len(BODIES)
                elif k == pygame.K_c:
                    st["skin"] = (st["skin"] + 1) % len(SKINS)
                elif k == pygame.K_n:
                    st["name"] = f"{random.choice(FIRST)} {random.choice(LAST)}"
                elif k == pygame.K_r:
                    st.update(arch=random.randrange(len(ARCH)), body=random.randrange(len(BODIES)),
                              skin=random.randrange(len(SKINS)), name=f"{random.choice(FIRST)} {random.choice(LAST)}",
                              mut=random.choice(MUTATIONS))
                elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    a = ARCH[st["arch"]]
                    d = dict(name=st["name"], archetype=a["name"], body=BODIES[st["body"]][0], skin=SKINS[st["skin"]][0],
                             stats=dict(zip(("STR", "AGI", "TOU", "WIT", "CHA", "LCK"), a["stats"])),
                             traits=[t for t, _ in a["traits"]], kit=a["kit"],
                             mutation=st["mut"] if a["name"] == "Mutant Pilgrim" else None)
                    os.makedirs(root, exist_ok=True)
                    with open(os.path.join(root, "character.json"), "w") as f:
                        json.dump(d, f, indent=1, ensure_ascii=False)
                    msg, msg_t = f"{st['name']} is ready. (Preview: the game will start from here once it's built. Esc to quit.)", time.monotonic()
        a = ARCH[st["arch"]]
        key = (st["arch"], st["body"], st["skin"], st["mut"])
        if key not in cache:
            mut = st["mut"] if a["name"] == "Mutant Pilgrim" else None
            cache[key] = render(bodies[st["body"]], a, SKINS[st["skin"]][1], mut)
        img = cache[key]
        sw, sh = screen.get_size()
        t = time.monotonic() - t0
        screen.fill((10, 9, 14))
        for i in range(70):                                            # a few drifting stars
            x = (i * 157 + int(t * (3 + i % 5))) % sw
            y = (i * 97) % sh
            c = 60 + (i * 37) % 120
            screen.fill((c, c, c + 20), (x, y, 2, 2))
        screen.blit(big.render("NEW DRIFTER", True, (240, 220, 160)), (30, 18))
        screen.blit(small.render("Stranded on a dead world. Pick who you were before the crash.", True, (150, 150, 165)), (32, 62))
        # archetypes
        for i, ar in enumerate(ARCH):
            y = 110 + i * 52
            on = i == st["arch"]
            pygame.draw.rect(screen, (34, 30, 46) if on else (18, 16, 26), (24, y, 300, 46), border_radius=8)
            if on:
                pygame.draw.rect(screen, ar["look"][5], (24, y, 4, 46), border_radius=2)
            screen.blit(mid.render(ar["name"], True, (240, 235, 220) if on else (170, 165, 180)), (38, y + 3))
            screen.blit(tiny.render(ar["tag"], True, ar["look"][5] if on else (110, 110, 125)), (40, y + 26))
        # the character
        cx = 560
        pygame.draw.ellipse(screen, (20, 26, 18), (cx - 150, 520, 300, 46))
        pygame.draw.ellipse(screen, (6, 8, 6), (cx - 70, 528, 140, 22))
        bob = int(round(math.sin(t * 2.2) * 3))
        screen.blit(to_surface(img, 6), (cx - N * 3, 168 + bob))
        nm = big.render(st["name"], True, (245, 240, 230))
        screen.blit(nm, (cx - nm.get_width() // 2, 110))
        g, meaning = BODIES[st["body"]]
        gl = cjk.render(g, True, a["look"][5])
        screen.blit(gl, (cx - 120, 576))
        screen.blit(small.render(f"Body {st['body'] + 1}/20 — {meaning}", True, (180, 180, 190)), (cx - 66, 590))
        screen.blit(small.render(f"Skin: {SKINS[st['skin']][0]}", True, (150, 150, 165)), (cx - 66, 612))
        for i in range(20):                                            # all 20 bodies
            th = cache.get(("thumb", i, st["arch"], st["skin"]))
            if th is None:
                th = to_surface(render(bodies[i], a, SKINS[st["skin"]][1], st["mut"] if a["name"] == "Mutant Pilgrim" else None), 1)
                cache[("thumb", i, st["arch"], st["skin"])] = th
            x = 352 + (i % 10) * 44 - 6
            y = 650 + (i // 10) * 60 - 8
            if i == st["body"]:
                pygame.draw.rect(screen, a["look"][5], (x, y, 52, 60), 2, border_radius=6)
            screen.blit(th, (x - 6, y - 4))
        # stats, traits, gear
        rx = 860
        pygame.draw.rect(screen, (18, 16, 26), (rx - 16, 100, 420, 600), border_radius=10)
        screen.blit(mid.render(a["name"], True, a["look"][5]), (rx, 112))
        for j, ln in enumerate(wrap(small, a["blurb"], 380)):
            screen.blit(small.render(ln, True, (200, 198, 210)), (rx, 142 + j * 20))
        y = 214
        for lab, v in zip(("STR", "AGI", "TOU", "WIT", "CHA", "LCK"), a["stats"]):
            screen.blit(small.render(lab, True, (170, 170, 180)), (rx, y))
            pygame.draw.rect(screen, (40, 36, 52), (rx + 50, y + 5, 200, 10), border_radius=4)
            pygame.draw.rect(screen, a["look"][5], (rx + 50, y + 5, 20 * v, 10), border_radius=4)
            screen.blit(tiny.render(str(v), True, (200, 200, 210)), (rx + 258, y + 1))
            y += 24
        y += 10
        screen.blit(mid.render("Traits", True, (230, 225, 210)), (rx, y)); y += 28
        traits = list(a["traits"])
        if a["name"] == "Mutant Pilgrim":
            traits[0] = ("Mutation", "+ " + st["mut"])
        for tname, td in traits:
            good = td.startswith("+")
            screen.blit(small.render(tname, True, (130, 220, 140) if good else (235, 110, 110)), (rx, y))
            screen.blit(tiny.render(td[2:], True, (170, 170, 180)), (rx + 130, y + 2))
            y += 22
        y += 10
        screen.blit(mid.render("Equipped", True, (230, 225, 210)), (rx, y)); y += 28
        hat, weapon, back, extra, _, _ = a["look"]
        slots = [("Head", hat), ("Hand", weapon), ("Back", back), ("Extra", extra)]
        names = {None: "—", "cowboy": "wide-brim hat", "cap": "cap", "cap2": "surgical cap", "hardhat": "hard hat",
                 "beanie": "beanie", "hood": "hood", "goggles": "goggles", "circlet": "circlet", "duster": "duster coat",
                 "pack": "backpack", "cloak": "cloak", "vest": "armour vest", "scarf": "scarf", "belt": "toolbelt",
                 "mutation": "mutation"}
        for sl, it in slots:
            screen.blit(small.render(sl, True, (150, 150, 165)), (rx, y))
            screen.blit(small.render(names.get(it, it), True, (220, 218, 230)), (rx + 70, y))
            y += 21
        y += 8
        screen.blit(mid.render("Carrying", True, (230, 225, 210)), (rx, y)); y += 28
        for j, it in enumerate(a["kit"]):
            screen.blit(small.render("· " + it, True, (200, 198, 210)), (rx + (j % 2) * 190, y + (j // 2) * 21))
        # keys + message
        keys = "Up/Down: who you were    Left/Right: body    C skin    N name    R random    Enter keep    Esc quit"
        screen.blit(small.render(keys, True, (130, 130, 145)), (30, sh - 30))
        if msg and time.monotonic() - msg_t < 6:
            m = small.render(msg, True, (240, 220, 160))
            screen.blit(m, (sw // 2 - m.get_width() // 2, sh - 60))
        pygame.display.flip()
        if shot:
            pygame.image.save(screen, shot)
            return
        clock.tick(30)
