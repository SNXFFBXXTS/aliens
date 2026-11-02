"""Character creation: each character IS a Japanese symbol (in the font), two-toned skin/clothes, with its gear
shown as smaller symbols placed on it (hat on top, weapon at the hand, pack or coat behind) x 10 archetypes.

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


# ── the player is ONE symbol; gear is shown as edits to that symbol (colour zones and extra brush strokes) ──
WEAPON_STROKE = {   # (angle in degrees from straight down, length as a share of the symbol, colour, tip colour)
    "revolver": (-80, 0.22, (70, 74, 84), (200, 204, 210)), "shotgun": (-82, 0.38, (70, 74, 84), (110, 76, 46)),
    "derringer": (-80, 0.14, (90, 94, 104), (220, 200, 120)), "knife": (-30, 0.2, (200, 204, 210), (240, 240, 245)),
    "axe": (-20, 0.36, (110, 76, 46), (200, 204, 210)), "scalpel": (-25, 0.14, (220, 224, 230), (255, 255, 255)),
    "wrench": (-25, 0.26, (150, 154, 164), (200, 204, 210)), "staff": (-5, 0.6, (110, 76, 46), None),
    "deck": (-90, 0.18, (60, 64, 80), None), "tome": (-90, 0.16, (110, 60, 50), None)}
_CACHE = {}


def _stroke(a, x0, y0, ang, length, width, col, tip=None):
    """paint a brush stroke into an RGBA float array, soft-edged, thicker in the middle"""
    H, W = a.shape[:2]
    dx, dy = math.sin(math.radians(ang)), math.cos(math.radians(ang))
    yy, xx = np.mgrid[0:H, 0:W]
    px, py = xx - x0, yy - y0
    t = np.clip(px * dx + py * dy, 0, length)
    d = np.hypot(px - t * dx, py - t * dy)
    wid = width * (0.65 + 0.35 * np.sin(np.pi * t / max(1, length)))
    alpha = np.clip(wid / 2 + 0.6 - d, 0, 1)
    for k in range(3):
        a[..., k] = a[..., k] * (1 - alpha) + col[k] * alpha
    a[..., 3] = np.maximum(a[..., 3], alpha * 255)
    if tip:
        m = alpha * (t > length * 0.75)
        for k in range(3):
            a[..., k] = a[..., k] * (1 - m) + tip[k] * m


def char_image(body, size, arch, skin, mut=None):
    """the character as one RGBA image: the body symbol, coloured skin/clothes/hat, with gear painted onto it"""
    key = (body, size, arch["name"], skin, mut)
    if key in _CACHE:
        return _CACHE[key]
    hat, weapon, back, extra, coat, trim = arch["look"]
    pad = int(size * 0.45)
    W = H = size + pad * 2
    try:
        f = ImageFont.truetype(CJK, size, index=0)
    except OSError:
        f = ImageFont.load_default()
    img = Image.new("L", (W, H), 0)
    ImageDraw.Draw(img).text((W // 2, H // 2), body, font=f, fill=255, anchor="mm")
    alpha = np.array(img).astype(np.float32)
    ink = alpha > 128
    ys, xs = np.nonzero(ink)
    top, bot, left, right = ys.min(), ys.max(), xs.min(), xs.max()
    gh = bot - top + 1
    stroke_w = max(2.0, float(np.median(np.diff(np.nonzero(ink[(top + bot) // 2])[0])[:1] if False else [size * 0.09])))
    a = np.zeros((H, W, 4), np.float32)
    yy = np.arange(H)[:, None]
    col = np.zeros((H, W, 3), np.float32)
    col[:] = coat
    col[(yy < top + gh * 0.42).repeat(W, 1)] = skin                 # skin above, clothes below
    if hat:                                                          # the top of the symbol is the hat
        hc = trim if hat in ("goggles", "circlet") else tuple(int(v * 0.8) for v in coat)
        band = (yy < top + gh * (0.16 if hat not in ("goggles", "circlet") else 0.24)).repeat(W, 1)
        if hat in ("goggles", "circlet"):
            band &= (yy > top + gh * 0.14).repeat(W, 1)
        col[band] = hc
    if extra in ("belt", "vest", "scarf"):                           # a band of colour across it
        y0, y1 = {"belt": (0.6, 0.66), "vest": (0.42, 0.62), "scarf": (0.36, 0.42)}[extra]
        col[((yy > top + gh * y0) & (yy < top + gh * y1)).repeat(W, 1)] = trim
    a[..., :3] = col
    a[..., 3] = alpha
    if back in ("pack", "cloak", "duster"):                          # a darker stroke down its back
        dark = tuple(int(v * 0.55) for v in coat)
        ln = gh * (0.5 if back == "pack" else 0.75)
        bx = left + (right - left) * 0.18
        behind = np.zeros_like(a)
        _stroke(behind, bx - size * 0.06, top + gh * 0.3, 8, ln, size * 0.11, dark)
        m = behind[..., 3:4] / 255 * (1 - a[..., 3:4] / 255)          # only where the symbol isn't
        a[..., :3] = a[..., :3] * (1 - m) + behind[..., :3] * m
        a[..., 3:4] = np.maximum(a[..., 3:4], behind[..., 3:4])
    if weapon in WEAPON_STROKE:                                      # an extra brush stroke from the hand
        ang, ln, c1, tip = WEAPON_STROKE[weapon]
        mid = ink & (np.arange(H)[:, None] > top + gh * 0.35) & (np.arange(H)[:, None] < top + gh * 0.6)
        my, mx = np.nonzero(mid)
        hx = mx.max() if len(mx) else right
        hy = int(np.mean(my[mx >= hx - 2])) if len(mx) else (top + bot) // 2
        _stroke(a, hx - size * 0.02, hy, 180 + ang if ang < -60 else ang, gh * ln, size * 0.075, c1, tip)
    if mut:                                                          # mutation: glowing flecks in the strokes
        r = random.Random(mut)
        g = trim
        for _ in range(14):
            k = r.randrange(len(ys))
            y, x = ys[k], xs[k]
            a[max(0, y - 1):y + 2, max(0, x - 1):x + 2, :3] = g
    out = np.clip(a, 0, 255).astype(np.uint8)
    srf = pygame.image.frombuffer(out.tobytes(), (W, H), "RGBA").copy()
    _CACHE[key] = srf
    return srf


def draw_char(screen, cx, cy, size, body, arch, skin, mut=None, bob=0, sway=0.0):
    srf = char_image(body, size, arch, skin, mut)
    sh = srf.copy()
    sh.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
    sh.set_alpha(110)
    w, h = srf.get_size()
    screen.blit(sh, (cx - w // 2 + max(2, size // 40), cy - h // 2 + bob + max(2, size // 40)))
    screen.blit(srf, (cx - w // 2, cy - h // 2 + bob))


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
        pygame.draw.ellipse(screen, (20, 26, 18), (cx - 150, 512, 300, 46))
        pygame.draw.ellipse(screen, (6, 8, 6), (cx - 80, 520, 160, 24))
        bob = int(round(math.sin(t * 2.2) * 3))
        mut = st["mut"] if a["name"] == "Mutant Pilgrim" else None
        draw_char(screen, cx, 390, 220, BODIES[st["body"]][0], a, SKINS[st["skin"]][1], mut, bob, math.sin(t * 1.3))
        nm = big.render(st["name"], True, (245, 240, 230))
        screen.blit(nm, (cx - nm.get_width() // 2, 96))
        g, meaning = BODIES[st["body"]]
        gl = cjk.render(g, True, a["look"][5])
        screen.blit(gl, (cx - 120, 588))
        screen.blit(small.render(f"Body {st['body'] + 1}/20 — {meaning}", True, (180, 180, 190)), (cx - 66, 600))
        screen.blit(small.render(f"Skin: {SKINS[st['skin']][0]}", True, (150, 150, 165)), (cx - 66, 622))
        for i in range(20):                                            # all 20 bodies
            x = 352 + (i % 10) * 44
            y = 668 + (i // 10) * 56
            if i == st["body"]:
                pygame.draw.rect(screen, a["look"][5], (x - 4, y - 6, 44, 52), 2, border_radius=6)
            draw_char(screen, x + 18, y + 22, 30, BODIES[i][0], a, SKINS[st["skin"]][1])
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
