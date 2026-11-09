"""Each region has a culture, gone dystopian: Aztec forests, Egyptian deserts, Soviet tundra, rural decay,
alien tech. Adds props, ruin layouts and scattered relics. Imported by structures.py (registers itself)."""
import math
import numpy as np
import weird
import structures as st
from weird import canvas, put, line, disc, F

CULTURE = {"forest": "aztec", "jungle": "aztec", "swamp": "aztec",
           "desert": "egypt", "salt": "egypt", "badlands": "egypt", "savanna": "egypt",
           "tundra": "soviet", "taiga": "soviet", "icesheet": "soviet", "drift": "soviet",
           "hills": "roman", "meadow": "roman", "beach": "roman",
           "grass": "rural",
           "fungal": "alien", "crystal": "alien", "ash": "alien", "crust": "alien"}


def _fill(c, x0, y0, x1, y1, ch):
    for y in np.arange(y0, y1, 0.25):
        line(c, x0, y, x1, y, ch)


# ── Aztec ──
def p_steppyr(r):
    c = canvas()
    tiers = 5
    for k in range(tiers):
        w = 7.4 - k * 1.25; y1 = 15.5 - k * 1.9; y0 = y1 - 1.9
        _fill(c, 7.5 - w, y0, 7.5 + w, y1, "1")
        line(c, 7.5 - w, y0, 7.5 + w, y0, "3")                       # lit ledge
        line(c, 7.5 + w * 0.55, y0 + 0.4, 7.5 + w, y1, "2")
        for gx in np.arange(7.5 - w + 0.6, 7.5 + w - 0.4, 1.3):     # carved glyphs
            put(c, gx, y0 + 1.0, "2")
    _fill(c, 6.6, 15.5 - tiers * 1.9, 8.4, 15.5, "2")               # the stair
    for y in np.arange(15.5 - tiers * 1.9, 15.5, 0.5):
        line(c, 6.6, y, 8.4, y, "1")
    _fill(c, 6, 4.3, 9, 6.0, "1"); put(c, 7.5, 5.2, "2")             # shrine on top
    line(c, 9, 4.3, 11.5, 1, "2"); disc(c, 11.8, 1.2, 1.1, "3")      # a dish bolted to it
    for x0 in (3, 12):                                               # cables hanging off
        for k in range(10):
            put(c, x0 + k * 0.15, 6 + k * 0.6 + math.sin(k) * 0.2, "2")
    return c


def p_serpent(r):
    c = canvas()
    _fill(c, 3, 9, 13, 15, "1")
    _fill(c, 4, 11.5, 12, 13, "2")                                   # open jaws
    for x in np.arange(4.5, 12, 1.4):
        line(c, x, 11.5, x + 0.3, 12.4, "3"); line(c, x + 0.6, 13, x + 0.8, 12.2, "3")
    disc(c, 5, 10, 0.8, "3"); disc(c, 11, 10, 0.8, "3")
    for k in range(6):                                               # feather crest
        a = -2.6 + k * 0.42
        line(c, 8, 9, 8 + math.cos(a) * 6, 9 + math.sin(a) * 5, "1")
    return c


def p_stela(r):
    c = canvas()
    _fill(c, 5, 2, 10.5, 15.5, "1")
    line(c, 5, 2, 10.5, 2, "3"); line(c, 10.5, 2, 10.5, 15.5, "2")
    for y in np.arange(3.5, 14.5, 1.6):
        for x in np.arange(6, 10, 1.4):
            if r.random() < 0.7:
                put(c, x, y, "2"); put(c, x + 0.5, y + 0.5, "3" if r.random() < 0.2 else "2")
    return c


def p_skullrack(r):
    c = canvas()
    for x in (2, 13):
        line(c, x, 15, x, 4, "2")
    for y in (5, 8, 11):
        line(c, 2, y, 13, y, "2")
        for x in np.arange(3, 12.5, 1.5):
            disc(c, x, y + 0.9, 0.65, "1"); put(c, x - 0.25, y + 0.8, "2"); put(c, x + 0.25, y + 0.8, "2")
    return c


def p_ballring(r):
    c = canvas()
    _fill(c, 2, 8, 13.5, 15.5, "1")
    line(c, 2, 8, 13.5, 8, "3")
    for a in np.linspace(0, 6.283, 80):
        put(c, 7.75 + math.cos(a) * 2.4, 4.8 + math.sin(a) * 2.4, "3"); put(c, 7.75 + math.cos(a) * 1.9, 4.8 + math.sin(a) * 1.9, "1")
    return c


# ── Egyptian ──
def p_pyramid(r):
    c = canvas()
    for y in np.arange(1.5, 15.6, 0.25):
        w = (y - 1.5) / 14 * 7.6
        for x in np.arange(7.5 - w, 7.5 + w, 0.25):
            put(c, x, y, "2" if x > 7.5 + (y - 1.5) * 0.12 else "1")
    for y in np.arange(3, 15.5, 1.2):                                # stone courses
        w = (y - 1.5) / 14 * 7.6
        line(c, 7.5 - w, y, 7.5 + w * 0.15, y, "2")
    disc(c, 7.5, 1.8, 0.7, "3")                                      # capstone
    for x in (4.5, 10.5):                                            # scaffolding up one face
        line(c, x, 15.5, x, 15.5 - abs(x - 7.5) * 1.3 - 3, "2")
    for y in np.arange(9, 15, 1.5):
        line(c, 4.5, y, 10.5, y - 0.2, "2")
    put(c, 7.5, 0.6, "3")
    return c


def p_sphinx(r):
    c = canvas()
    _fill(c, 1, 11, 13, 15, "1")                                     # lying body
    _fill(c, 1, 13.5, 6, 15.5, "1")                                  # paws
    _fill(c, 9, 5, 13.5, 11, "1")                                    # head
    for y in np.arange(5.5, 11, 1.2):                                # nemes stripes
        line(c, 8.5, y, 9.2, y + 1.5, "2"); line(c, 14, y, 13.4, y + 1.5, "2")
    put(c, 10.3, 7.4, "3"); put(c, 12.2, 7.4, "3")
    line(c, 1, 11, 9, 11, "3")
    line(c, 11, 9.2, 11.6, 9.6, "2")                                 # broken nose
    return c


def p_column(r):
    c = canvas()
    h = r.uniform(9, 13)
    _fill(c, 6, 15.5 - h, 9, 15.5, "1")
    for x in (6.7, 7.5, 8.3):
        line(c, x, 15.5 - h, x, 15.5, "2")
    for k in range(5):                                               # lotus capital
        a = -2.3 + k * 0.4
        line(c, 7.5, 15.5 - h, 7.5 + math.cos(a) * 3, 15.5 - h + math.sin(a) * 2.5, "3")
    if r.random() < 0.4:
        line(c, 6, 9, 9, 10.5, "2")                                  # crack
    return c


def p_sarcoph(r):
    c = canvas()
    _fill(c, 2, 10, 13.5, 14.5, "1")
    disc(c, 3.5, 12.2, 1.6, "3")
    for x in np.arange(5.5, 13, 1.6):
        line(c, x, 10.5, x, 14, "2")
    line(c, 2, 14.5, 13.5, 14.5, "2")
    return c


def p_anubis(r):
    c = canvas()
    _fill(c, 5, 12.5, 10, 15.5, "2")                                 # plinth
    _fill(c, 6.3, 6, 8.7, 12.5, "1")                                 # body
    _fill(c, 6.6, 3, 8.4, 6, "1")                                    # head
    line(c, 8.4, 4.5, 10.5, 5, "1")                                  # snout
    line(c, 6.8, 3, 6.4, 0.5, "1"); line(c, 8.2, 3, 8.6, 0.5, "1")   # ears
    put(c, 8, 4, "3")
    line(c, 6.3, 7, 4.5, 11, "1"); line(c, 4.5, 4, 4.5, 15, "2")     # staff
    return c


# ── dystopian / industrial ──
def p_pylon(r):
    c = canvas()
    for y in np.arange(1, 15.6, 0.25):
        w = 0.7 + (y - 1) / 14.5 * 3.3
        put(c, 7.5 - w, y, "1"); put(c, 7.5 + w, y, "1")
    for k in range(7):
        y0 = 2 + k * 1.9
        w0 = 0.7 + (y0 - 1) / 14.5 * 3.3; w1 = 0.7 + (y0 + 1.9 - 1) / 14.5 * 3.3
        line(c, 7.5 - w0, y0, 7.5 + w1, y0 + 1.9, "2"); line(c, 7.5 + w0, y0, 7.5 - w1, y0 + 1.9, "2")
    for y, w in ((3, 6), (6, 5)):                                    # arms with insulators
        line(c, 7.5 - w, y, 7.5 + w, y, "1")
        for x in (7.5 - w, 7.5 + w):
            line(c, x, y, x, y + 1, "3")
            for k in range(8):                                       # sagging wire stubs
                put(c, x + (k if x > 7.5 else -k) * 0.25, y + 1 + math.sin(k / 7 * math.pi) * 0.9 + k * 0.1, "2")
    return c


def p_neon(r):
    c = canvas()
    line(c, 3, 15.5, 3, 4, "2"); line(c, 12, 15.5, 12, 4, "2")
    _fill(c, 2.5, 3, 12.5, 9, "2")
    shape = r.integers(3)
    if shape == 0:                                                   # an eye
        for a in np.linspace(0, 6.283, 60):
            put(c, 7.5 + math.cos(a) * 3.5, 6 + math.sin(a) * 1.6, "3")
        disc(c, 7.5, 6, 0.8, "3")
    elif shape == 1:                                                 # a cross
        line(c, 7.5, 3.6, 7.5, 8.4, "3"); line(c, 5, 5.5, 10, 5.5, "3")
    else:                                                            # letters, half of them dead
        for x in np.arange(3.5, 12, 1.8):
            if r.random() < 0.65:
                line(c, x, 4, x, 8, "3"); line(c, x, 4, x + 1, 4, "3")
            else:
                line(c, x, 4, x, 8, "1")
    return c


def p_billboard(r):
    c = canvas()
    line(c, 4, 15.5, 4, 8, "2"); line(c, 11, 15.5, 11, 8, "2")
    _fill(c, 0.5, 2, 15, 8, "1")
    for _ in range(r.integers(3, 6)):                                # torn, peeling
        x, y = r.uniform(1, 13), r.uniform(2.5, 7)
        _fill(c, x, y, x + r.uniform(1, 3), y + r.uniform(0.5, 1.5), "2")
    for x in np.arange(2, 13, 2.5):
        if r.random() < 0.6:
            line(c, x, 3.5, x + 1.6, 3.5, "3")
    return c


def p_pipes(r):
    """an old pipeline lying in the undergrowth: a round, shaded pipe with flanged joints, saddles under it,
    a valve wheel, and sometimes a broken, hollow end"""
    c = canvas()
    cy, rad = 11.0, 2.3
    x1 = 15.9 if r.random() < 0.6 else r.uniform(11.5, 14)          # broken short, sometimes
    for y in np.arange(cy - rad, cy + rad, 0.25):                    # the barrel, lit from above
        u = (y - cy) / rad
        ch = "3" if u < -0.6 else "2" if u > 0.4 else "1"
        line(c, 0, y, x1, y, ch)
    for x in np.arange(r.uniform(1, 3), x1 - 1, r.uniform(4.5, 6)):   # flanges at the joints
        _fill(c, x, cy - rad - 0.6, x + 0.9, cy + rad + 0.6, "2")
        line(c, x, cy - rad - 0.6, x, cy + rad + 0.6, "3")
        for by in (cy - rad - 0.2, cy + rad + 0.2):
            put(c, x + 0.45, by, "3")                                # bolts
    for x in (r.uniform(2, 4), r.uniform(9, 12)):                    # saddles holding it up
        if x < x1 - 1:
            _fill(c, x - 0.8, cy + rad, x + 0.8, 15.6, "2")
            line(c, x - 1.4, 15.6, x + 1.4, 15.6, "2")
    if x1 < 15.9:                                                    # the broken end: dark and hollow
        for y in np.arange(cy - rad + 0.4, cy + rad - 0.4, 0.25):
            put(c, x1 - 0.3, y, "2"); put(c, x1 - 0.6, y, "2")
        for y in np.arange(cy - rad, cy + rad, 0.6):
            put(c, x1 + r.uniform(0, 0.8), y, "1")
    elif r.random() < 0.7:                                           # a valve wheel on a stem
        vx = r.uniform(5, 11)
        line(c, vx, cy - rad, vx, 5.5, "2")
        for a in np.linspace(0, 2 * math.pi, 40):
            put(c, vx + 2.2 * math.cos(a), 4.2 + 1.1 * math.sin(a), "2")
        line(c, vx - 2.2, 4.2, vx + 2.2, 4.2, "2"); line(c, vx, 3.1, vx, 5.3, "2")
        put(c, vx - 1, 3.4, "3")
    return c


def p_cables(r):
    c = canvas()
    line(c, 1.5, 15.5, 1.5, 2, "2"); line(c, 14, 15.5, 14, 3, "2")
    for k in range(r.integers(2, 5)):
        sag = r.uniform(3, 8)
        for x in np.arange(1.5, 14, 0.25):
            u = (x - 1.5) / 12.5
            put(c, x, 2.5 + k * 0.6 + sag * math.sin(u * math.pi), "1")
    put(c, 14, 3, "3")
    return c


def p_mech(r):
    c = canvas()
    _fill(c, 4, 7, 11, 12.5, "1")                                    # torso slumped
    _fill(c, 5, 3.5, 9.5, 7, "1")                                    # head
    line(c, 5.5, 5, 9, 5, "3")                                       # dead visor
    line(c, 11, 8, 14.5, 13, "2"); line(c, 14.5, 13, 15.5, 15.5, "2")   # arm on the ground
    line(c, 5, 12.5, 2, 15.5, "2"); line(c, 9, 12.5, 11, 15.5, "2")    # legs
    for _ in range(4):
        put(c, r.uniform(4.5, 10.5), r.uniform(7.5, 12), "2")         # holes
    line(c, 9.5, 3.5, 11.5, 0.5, "2"); put(c, 11.5, 0.5, "3")       # antenna
    return c


def p_cctv(r):
    c = canvas()
    line(c, 7.5, 15.5, 7.5, 3, "2")
    _fill(c, 7.5, 2, 12, 4, "1")
    disc(c, 12, 3, 0.7, "3")
    line(c, 7.5, 6, 6, 7.5, "2")
    return c


def p_silo(r):
    c = canvas()
    _fill(c, 4.5, 4, 10.5, 15.5, "1")
    disc(c, 7.5, 4, 3, "1")
    for y in np.arange(5, 15, 1.8):
        line(c, 4.5, y, 10.5, y, "2")
    for y in np.arange(5, 15.5, 0.8):                                # ladder
        line(c, 10.5, y, 11.3, y, "3")
    line(c, 4.5, 4, 10.5, 15.5, "2") if r.random() < 0.3 else None
    return c


def p_statue(r):
    c = canvas()
    _fill(c, 3, 12.5, 12, 15.5, "2")                                 # plinth
    _fill(c, 4, 9.5, 11, 12.5, "1")                                  # shoulders
    _fill(c, 5.5, 3, 9.5, 9.5, "1")                                  # a huge stern head
    line(c, 5.5, 3, 9.5, 3, "3")
    line(c, 6.3, 5.3, 7.1, 5.3, "2"); line(c, 7.9, 5.3, 8.7, 5.3, "2")
    line(c, 6.6, 8, 8.4, 8, "2")
    line(c, 9.5, 4, 8.5, 9.5, "2")                                   # a crack down the face
    return c


# ── Roman ──
def p_rcolumn(r):
    c = canvas()
    broken = r.random() < 0.5
    top = 2.5 if not broken else r.uniform(5, 10)
    _fill(c, 5.5, 13.5, 9.5, 15.5, "2")                              # base
    _fill(c, 6.2, top + 1.2, 8.8, 13.5, "1")
    for x in (6.7, 7.5, 8.3):                                        # fluting
        line(c, x, top + 1.5, x, 13.3, "2")
    if not broken:
        _fill(c, 5, 1.5, 10, 3.2, "1")                               # Corinthian capital
        for k in range(4):
            disc(c, 5.4 + k * 1.4, 2.2, 0.6, "2")
        line(c, 4.6, 1.5, 10.4, 1.5, "3")
    else:
        for k in range(6):                                           # jagged break
            put(c, 6.2 + k * 0.5, top + 1.2 - (k % 2) * 0.6, "3")
    if r.random() < 0.35:                                            # a spray tag on it
        line(c, 6.4, 9, 8.6, 10, "3"); line(c, 6.4, 10, 8.6, 9, "3")
    return c


def p_drums(r):
    c = canvas()
    for k, (x, y, rr) in enumerate(((3.5, 13.5, 1.8), (7.5, 14, 1.8), (11.5, 13.2, 1.8))):
        if k == 2 and r.random() < 0.4:
            continue
        _fill(c, x - 1.5, y - rr, x + 1.5, y + rr * 0.6, "1")
        disc(c, x + 1.5, y - rr * 0.2, rr * 0.8, "2")
        line(c, x - 1.5, y - rr, x + 1.5, y - rr, "3")
    return c


def p_arch(r):
    c = canvas()
    _fill(c, 2, 4, 5, 15.5, "1"); _fill(c, 10.5, 4, 13.5, 15.5, "1")
    for a in np.linspace(math.pi, 2 * math.pi, 90):                  # the arch and its voussoirs
        for rr in np.arange(2.8, 5.8, 0.25):
            put(c, 7.75 + math.cos(a) * rr, 7 + math.sin(a) * rr, "1")
        put(c, 7.75 + math.cos(a) * 5.8, 7 + math.sin(a) * 5.8, "3")
    for a in np.linspace(math.pi, 2 * math.pi, 9):
        line(c, 7.75 + math.cos(a) * 2.8, 7 + math.sin(a) * 2.8, 7.75 + math.cos(a) * 5.8, 7 + math.sin(a) * 5.8, "2")
    _fill(c, 1.5, 1, 14, 2, "1")
    if r.random() < 0.5:                                             # half of it has fallen
        for y in np.arange(0, 9, 0.25):
            line(c, 11 + math.sin(y) * 0.8, y, 15.9, y, ".")
    line(c, 5, 4, 5, 15.5, "2"); line(c, 13.5, 4, 13.5, 15.5, "2")
    return c


def p_aqueduct(r):
    c = canvas()
    _fill(c, 0, 1, 15.9, 3, "1"); line(c, 0, 1, 15.9, 1, "3")         # the channel on top
    for k in range(2):
        x0 = k * 8
        _fill(c, x0, 3, x0 + 1.6, 15.5, "1")
        for a in np.linspace(math.pi, 2 * math.pi, 50):
            for rr in np.arange(2.6, 3.4, 0.25):
                put(c, x0 + 4.8 + math.cos(a) * rr, 7 + math.sin(a) * rr * 1.2, "1")
        line(c, x0 + 1.6, 3, x0 + 1.6, 15.5, "2")
    _fill(c, 14.3, 3, 15.9, 15.5, "1")
    if r.random() < 0.4:
        for y in np.arange(0, 6, 0.25):
            line(c, 12 + math.sin(y * 2) * 0.6, y, 15.9, y, ".")
    return c


def p_pediment(r):
    c = canvas()
    for y in np.arange(1, 5, 0.25):                                  # the pediment
        w = (y - 1) / 4 * 7.6
        line(c, 7.75 - w, y, 7.75 + w, y, "1")
    line(c, 0.2, 5, 15.3, 5, "3")
    _fill(c, 0.5, 5, 15, 6.4, "2")                                   # frieze
    for x in np.arange(1.2, 14.6, 1.2):
        put(c, x, 5.7, "1")
    for x in (2, 5.6, 9.2, 12.8):                                    # columns
        if x == 12.8 and r.random() < 0.5:
            _fill(c, x - 0.7, 12, x + 0.7, 13.6, "1"); continue      # one has fallen
        _fill(c, x - 0.7, 6.4, x + 0.7, 13.6, "1")
        line(c, x, 6.6, x, 13.4, "2")
    for k in range(3):                                               # steps
        _fill(c, 0.2 - k * 0.3 + 0.6, 13.6 + k * 0.7, 15.3 + k * 0.3 - 0.6, 14.3 + k * 0.7, "2" if k % 2 else "1")
    line(c, 4, 5.4, 11, 5.4, "3") if r.random() < 0.5 else None     # graffiti across the frieze
    return c


def p_rstatue(r):
    c = canvas()
    _fill(c, 5, 12, 10.5, 15.5, "2")                                 # plinth
    _fill(c, 6.2, 5, 9.4, 12, "1")                                   # a draped figure, head long gone
    for k in range(4):
        line(c, 6.4 + k * 0.8, 6, 6.8 + k * 0.6, 11.8, "2")
    line(c, 6.2, 5, 9.4, 5, "3")
    line(c, 9.4, 6, 11, 8.5, "1")                                    # one arm, raised
    return c


def p_amphora(r):
    c = canvas()
    for y in np.arange(7, 14.5, 0.25):
        w = 1.8 * math.sin((y - 6.5) / 8 * math.pi) + 0.4
        line(c, 7.5 - w, y, 7.5 + w, y, "1")
    line(c, 6.8, 6, 8.2, 6, "2"); line(c, 6.5, 7.5, 5.8, 9, "2"); line(c, 8.5, 7.5, 9.2, 9, "2")
    line(c, 6, 10.5, 9, 10.5, "3")
    return c


def p_milestone(r):
    c = canvas()
    _fill(c, 6, 7, 9.5, 15.5, "1")
    disc(c, 7.75, 7, 1.75, "1")
    for y in (9, 10.5, 12):
        line(c, 6.6, y, 8.9, y, "2")
    return c


def p_fencev(r):
    """a fence running up the screen: seen edge-on it's just a skinny line of posts and rails"""
    c = canvas()
    line(c, 7.2, 0, 7.2, 15.9, "1"); line(c, 8.2, 0, 8.2, 15.9, "1")
    for y in (4, 12):
        _fill(c, 6.8, y - 1.5, 8.7, y + 1.5, "2"); line(c, 6.8, y - 1.5, 8.7, y - 1.5, "3")
    return c


NEW = {
    "rcolumn": (p_rcolumn, 4, True, ("salt", 5), ("salt", 3), ("bloom", 6)),
    "drums": (p_drums, 2, True, ("salt", 5), ("salt", 3), ("salt", 6)),
    "arch": (p_arch, 6, True, ("dune", 5), ("dune", 3), ("dune", 6)),
    "aqueduct": (p_aqueduct, 8, True, ("dune", 5), ("dune", 3), ("dune", 6)),
    "pediment": (p_pediment, 8, True, ("salt", 5), ("salt", 3), ("bloom", 6)),
    "rstatue": (p_rstatue, 5, True, ("salt", 5), ("salt", 3), ("salt", 6)),
    "amphora": (p_amphora, 2, True, ("clay", 4), ("clay", 2), ("ochre", 5)),
    "milestone": (p_milestone, 2, True, ("stone", 4), ("stone", 2), ("stone", 5)),
    "fencev": (p_fencev, 2, True, ("wood", 4), ("wood", 2), ("wood", 5)),
    "steppyr": (p_steppyr, 8, True, ("stone", 4), ("stone", 2), ("lumen", 6)),
    "serpent": (p_serpent, 4, True, ("stone", 4), ("stone", 2), ("lumen", 6)),
    "stela": (p_stela, 4, True, ("stone", 4), ("stone", 2), ("lumen", 5)),
    "skullrack": (p_skullrack, 4, True, ("salt", 5), ("wood", 2), ("salt", 6)),
    "ballring": (p_ballring, 4, True, ("stone", 4), ("stone", 2), ("stone", 6)),
    "pyramid": (p_pyramid, 8, True, ("dune", 5), ("dune", 3), ("blood", 6)),
    "sphinx": (p_sphinx, 6, True, ("dune", 5), ("dune", 3), ("lumen", 6)),
    "column": (p_column, 4, True, ("dune", 5), ("dune", 3), ("ochre", 6)),
    "sarcoph": (p_sarcoph, 2, True, ("ochre", 5), ("ochre", 2), ("frost", 6)),
    "anubis": (p_anubis, 5, True, ("ash", 2), ("ash", 1), ("eye", 7)),
    "pylon": (p_pylon, 8, True, ("cobble", 4), ("cobble", 2), ("blood", 6)),
    "neon": (p_neon, 4, True, ("cobble", 2), ("cobble", 1), ("bloom", 7)),
    "billboard": (p_billboard, 6, True, ("salt", 3), ("rust", 2), ("blood", 5)),
    "pipes": (p_pipes, 4, True, ("rust", 4), ("rust", 2), ("rust", 6)),
    "cables": (p_cables, 4, False, ("ash", 1), ("cobble", 2), ("eye", 6)),
    "mech": (p_mech, 6, True, ("cobble", 4), ("rust", 2), ("lumen", 6)),
    "cctv": (p_cctv, 4, True, ("cobble", 4), ("cobble", 2), ("blood", 7)),
    "silo": (p_silo, 6, True, ("rust", 4), ("rust", 2), ("salt", 5)),
    "statue": (p_statue, 6, True, ("cobble", 4), ("cobble", 2), ("cobble", 6)),
}
NAMES = {"rcolumn": "column", "drums": "fallen column", "arch": "arch", "aqueduct": "aqueduct", "pediment": "temple front",
         "rstatue": "headless statue", "amphora": "amphora", "milestone": "milestone", "fencev": "fence",
         "steppyr": "stepped pyramid", "serpent": "serpent head", "stela": "carved stela", "skullrack": "skull rack",
         "ballring": "ball-court ring", "pyramid": "pyramid", "sphinx": "sphinx", "column": "column", "sarcoph": "sarcophagus",
         "anubis": "jackal statue", "pylon": "pylon", "neon": "neon sign", "billboard": "billboard", "pipes": "pipes",
         "cables": "cables", "mech": "dead mech", "cctv": "camera pole", "silo": "silo", "statue": "statue"}

for n, spec in NEW.items():
    st.PROPS[n] = spec
    st.PROP_NAMES[n] = NAMES[n]
    weird.GEN["p_" + n] = spec[0]
    weird.BIG["p_" + n] = spec[1]
    weird.PROP_COLOURS["p_" + n] = {"1": F(*spec[3]), "2": F(*spec[4]), "3": F(*spec[5])}
    if spec[2]:
        st.BLOCKING.add("p_" + n)
st.BLOCKING.add("p_solid")                    # invisible footprint of a big monument
st.PROP_NAMES["solid"] = "monument"

# ruin sites (x = the monument's footprint, so you walk round it, not through it)
L = st.layout
L("aztec_temple", "a stepped temple in the trees", {"forest", "jungle", "swamp"},
  ["s   xxx   s", "    xxx    ", "e   xYx   e", "           ", "p   ___   n", "  e _F_ e  "],
  {"Y": "steppyr", "x": "solid", "s": "stone", "e": "stone", "p": "pipes", "n": "neon", "F": "fire"},
  "A stepped pyramid rises out of the canopy, glyphs worn smooth. Someone bolted a dish to the shrine at the top and ran cables down its steps.")
L("aztec_court", "an old ball court", {"forest", "jungle", "swamp"},
  ["##########", "#  R   R #", "#   __   #", "#  K  c  #", "####  ####"], {"R": "ballring", "K": "rack", "c": "cables"},
  "Two long walls and a stone ring high up. A rack of skulls watches the empty court. Something still plays here at night.")
L("aztec_plaza", "a plaza of carved heads", {"forest", "jungle"},
  ["s e s e s", "         ", "e  _A_  e", "         ", "s n s n s"], {"s": "stone", "e": "stone", "A": "altar", "n": "neon"},
  "Serpent heads ring a plaza, jaws open. A neon sign flickers over the altar, selling something to nobody.")
L("egypt_pyramid", "a great pyramid", {"desert", "salt", "badlands", "savanna"},
  ["  xxxxx  ", "  xxxxx  ", "  xxYxx  ", "         ", "o       o", " S     Z "],
  {"Y": "pyramid", "x": "solid", "o": "obelisk", "S": "sphinx", "Z": "pylon"},
  "A pyramid blots out the sky, wrapped in rusted scaffolding, a red beacon blinking at its tip. A sphinx with no nose keeps watch.")
L("egypt_temple", "a temple of columns", {"desert", "salt", "badlands"},
  ["C C C C C", "         ", "A ..... A", "  ..T..  ", "C C C C C"], {"C": "column", "A": "anubis", "T": "sarcoph"},
  "Columns with lotus tops stand round an open sarcophagus. The jackal statues' eyes are lit from inside.")
L("egypt_tombs", "a valley of tombs", {"desert", "badlands", "salt"},
  ["%%%  %%%  %%%", "%T%  %T%  %T%", "%+%  %+%  %+%", "             ", "  M      o   "], {"T": "sarcoph", "M": "mech", "o": "obelisk"},
  "Tomb doors cut into broken walls, every one pried open. A dead mech lies where it was left guarding them.")
L("pylonline", "a line of power pylons", {"tundra"},
  ["P     P     P     P"], {"P": "pylon"}, "Pylons stride across the land, their wires long gone. They still hum.")
L("neonstrip", "a dead neon strip", {"grass", "ash", "fungal", "crystal", "badlands", "savanna"},
  ["B   n   B   n", "             ", "  c  J  c  Y ", "             ", "n   B   K   n"],
  {"B": "billboard", "n": "neon", "c": "cctv", "J": "scrap", "Y": "car", "K": "cables"},
  "Billboards and neon signs for things no one remembers, half of them still lit. Cameras turn to follow you.")
L("mechyard", "a mech graveyard", {"ash", "badlands", "desert", "tundra", "crystal", "salt"},
  ["  M    J    M  ", "               ", "J    M    M   J", "               ", "  M    J    M  "], {"M": "mech", "J": "scrap"},
  "Dozens of dead war machines lie where they fell, rusting in rows, visors dark. Mostly dark.")
L("soviet", "a brutalist block", {"tundra", "taiga", "icesheet", "drift", "hills"},
  ["#########   ", "#.......#  S", "#.T...B.#   ", "#.......#   ", "####+#### c ", "   pppp     "],
  {"S": "statue", "T": "table", "B": "bed", "c": "cctv", "p": "pipes"},
  "A concrete block, windows punched out. A giant stone head glowers over the yard. The pipes still knock.")
L("pipeline", "a pipeline", {"tundra", "taiga", "icesheet", "drift", "desert", "salt"},
  ["pppppppppppppppp", "      c         "], {"p": "pipes", "c": "cctv"},
  "A pipeline runs off to the horizon, sweating rust. Something is still being pumped somewhere.")
L("silos", "a silo farm", {"grass", "meadow", "savanna"},
  ["ffffffffffff", "f  O    O  f", "f    B     f", "f  O   P   f", "ffffff  ffff"], {"O": "silo", "B": "billboard", "P": "pylon"},
  "Grain silos gone to rust, a billboard promising a better harvest. The fields round it grew nothing for years.")
L("shrine_tech", "a wired shrine", {"fungal", "crystal", "ash", "jungle"},
  [" c   I   c ", "  K _A_ K  ", " n   M   n "], {"I": "obelisk", "A": "altar", "K": "cables", "n": "neon", "M": "mech", "c": "candle"},
  "An idol plugged into a nest of cables, a dead mech kneeling before it, neon halos buzzing overhead.")

L("roman_temple", "a Roman temple", {"hills", "meadow", "beach", "grass"},
  ["  xxxxx  ", "  xxPxx  ", "   ~~~   ", " C ~~~ C ", " S ~~~ S ", "   ~~~   ", " D     n "],
  {"P": "pediment", "x": "solid", "C": "rcolumn", "S": "rstatue", "D": "drums", "n": "neon"},
  "A temple front still standing, columns cracked, a mosaic floor leading up to it. Someone has sprayed over the frieze.")
L("roman_forum", "a ruined forum", {"hills", "meadow", "grass", "beach"},
  ["C C C C C C", "           ", "~~~~~~~~~~~", "~D~~~S~~~D~", "~~~~~~~~~~~", "           ", "C C C C C C"],
  {"C": "rcolumn", "D": "drums", "S": "rstatue"},
  "Two rows of columns, half of them snapped, round a cracked mosaic square. Headless statues still hold their poses.")
L("aqueduct", "an aqueduct", {"hills", "meadow", "grass", "savanna"},
  ["A   A   A   A   A"], {"A": "aqueduct"},
  "Stone arches march across the land, carrying water that stopped flowing centuries ago. You can walk under them.")
L("colosseum", "a broken amphitheatre", {"hills", "meadow", "grass"},
  ["    %%%%%    ", "  %%  R  %%  ", " %    _    % ", " %  _____  % ", "%  _______  %", "%R ___D___ R%",
   "%  _______  %", " %  _____  % ", " %         % ", "  %%  +  %%  ", "    %% %%    "], {"R": "arch", "D": "drums"},
  "A ring of crumbling stone round a sandy floor. The crowd is long gone, but the arches still frame it.")
L("villa", "a ruined villa", {"hills", "meadow", "beach"},
  ["%%%%%%%%%", "%~~~~%,,%", "%~~a~%,,%", "%~~~~+,a%", "%%+%%%%%%", "  S   m  "],
  {"a": "amphora", "S": "rstatue", "m": "milestone"},
  "A villa's walls stand knee-high round mosaic floors. Amphorae still sit where they were stored.")
L("triumph", "a triumphal arch", {"hills", "meadow", "grass", "beach"},
  [" m   xRx   m ", "     _ _     "], {"R": "arch", "x": "solid", "m": "milestone"},
  "A great arch stands alone in the open, carved with victories nobody remembers.")

LAYOUTS = {"roman": ["roman_temple", "roman_forum", "aqueduct", "colosseum", "villa", "triumph"],"aztec": ["aztec_temple", "aztec_court", "aztec_plaza", "shrine", "cemetery"],
           "egypt": ["egypt_pyramid", "egypt_temple", "egypt_tombs", "mechyard", "caravan"],
           "soviet": ["soviet", "pipeline", "woodpecker", "radome", "bunker"],
           "rural": ["silos", "farmstead", "neonstrip", "windfarm"],
           "alien": ["shrine_tech", "neonstrip", "mechyard", "monolith", "stones"]}

# relics scattered through the land, not just in ruin sites
SCATTER = {"roman": [("p_rcolumn", 0.006), ("p_drums", 0.005), ("p_rstatue", 0.002), ("p_amphora", 0.003), ("p_milestone", 0.002)],"aztec": [("p_pipes", 0.0008), ("p_neon", 0.0015), ("p_cables", 0.002)],   # no stelae or serpent heads: they read as faces
           "egypt": [("p_column", 0.008), ("p_sarcoph", 0.002), ("p_anubis", 0.002), ("p_pylon", 0.0004), ("p_mech", 0.0015)],
           "soviet": [("p_statue", 0.0015), ("p_pylon", 0.0005), ("p_pipes", 0.0008), ("p_cctv", 0.002)],
           "rural": [("p_pylon", 0.0006), ("p_billboard", 0.002), ("p_silo", 0.0012), ("p_cctv", 0.0015)],
           "alien": [("p_cables", 0.005), ("p_neon", 0.003), ("p_mech", 0.002)]}
for b, cul in CULTURE.items():
    if b in weird.BIOMES:
        fam, acc, kinds, marks = weird.BIOMES[b]
        weird.BIOMES[b] = (fam, acc, list(kinds) + SCATTER[cul], marks)
