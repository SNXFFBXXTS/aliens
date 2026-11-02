"""Each region has a culture, gone dystopian: Aztec forests, Egyptian deserts, Soviet tundra, rural decay,
alien tech. Adds props, ruin layouts and scattered relics. Imported by structures.py (registers itself)."""
import math
import numpy as np
import weird
import structures as st
from weird import canvas, put, line, disc, F

CULTURE = {"forest": "aztec", "jungle": "aztec", "swamp": "aztec",
           "desert": "egypt", "salt": "egypt", "badlands": "egypt", "savanna": "egypt",
           "tundra": "soviet", "taiga": "soviet", "icesheet": "soviet", "drift": "soviet", "hills": "soviet",
           "grass": "rural", "meadow": "rural", "beach": "rural",
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
    c = canvas()
    for k, y in enumerate((9, 11.5, 14)):
        _fill(c, 0, y - 0.8, 15.9, y + 0.8, "1" if k % 2 == 0 else "2")
        line(c, 0, y - 0.8, 15.9, y - 0.8, "3")
    for x in np.arange(2, 15, 4.5):                                  # valves and brackets
        disc(c, x, 7.5, 1, "3"); line(c, x, 8, x, 15.5, "2")
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


NEW = {
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
NAMES = {"steppyr": "stepped pyramid", "serpent": "serpent head", "stela": "carved stela", "skullrack": "skull rack",
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
  {"Y": "steppyr", "x": "solid", "s": "serpent", "e": "stela", "p": "pipes", "n": "neon", "F": "fire"},
  "A stepped pyramid rises out of the canopy, glyphs worn smooth. Someone bolted a dish to the shrine at the top and ran cables down its steps.")
L("aztec_court", "an old ball court", {"forest", "jungle", "swamp"},
  ["##########", "#  R   R #", "#   __   #", "#  K  c  #", "####  ####"], {"R": "ballring", "K": "skullrack", "c": "cables"},
  "Two long walls and a stone ring high up. A rack of skulls watches the empty court. Something still plays here at night.")
L("aztec_plaza", "a plaza of carved heads", {"forest", "jungle"},
  ["s e s e s", "         ", "e  _A_  e", "         ", "s n s n s"], {"s": "serpent", "e": "stela", "A": "altar", "n": "neon"},
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
L("pylonline", "a line of power pylons", {"grass", "meadow", "savanna", "tundra", "hills", "desert", "badlands"},
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
  [" c   I   c ", "  K _A_ K  ", " n   M   n "], {"I": "idol", "A": "altar", "K": "cables", "n": "neon", "M": "mech", "c": "candle"},
  "An idol plugged into a nest of cables, a dead mech kneeling before it, neon halos buzzing overhead.")

LAYOUTS = {"aztec": ["aztec_temple", "aztec_court", "aztec_plaza", "shrine", "cemetery"],
           "egypt": ["egypt_pyramid", "egypt_temple", "egypt_tombs", "mechyard", "caravan"],
           "soviet": ["soviet", "pipeline", "woodpecker", "radome", "bunker"],
           "rural": ["silos", "pylonline", "farmstead", "neonstrip", "windfarm"],
           "alien": ["shrine_tech", "neonstrip", "mechyard", "monolith", "stones"]}

# relics scattered through the land, not just in ruin sites
SCATTER = {"aztec": [("p_stela", 0.006), ("p_serpent", 0.004), ("p_pipes", 0.003), ("p_neon", 0.002), ("p_cables", 0.004)],
           "egypt": [("p_column", 0.008), ("p_sarcoph", 0.002), ("p_anubis", 0.002), ("p_pylon", 0.003), ("p_mech", 0.0015)],
           "soviet": [("p_statue", 0.0015), ("p_pylon", 0.004), ("p_pipes", 0.004), ("p_cctv", 0.002)],
           "rural": [("p_pylon", 0.004), ("p_billboard", 0.002), ("p_silo", 0.0012), ("p_cctv", 0.0015)],
           "alien": [("p_cables", 0.005), ("p_neon", 0.003), ("p_mech", 0.002)]}
for b, cul in CULTURE.items():
    if b in weird.BIOMES:
        fam, acc, kinds, marks = weird.BIOMES[b]
        weird.BIOMES[b] = (fam, acc, list(kinds) + SCATTER[cul], marks)
