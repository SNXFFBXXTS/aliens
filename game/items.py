"""Things you find: what they are, what they do, and what each kind of container tends to hold.

Containers are searched once; what's inside is decided by the world seed and the container's square, so it's
the same every time (and nothing is made until you look).
"""
import random
import zlib

# id: (name, kind, weight kg, colour, effect)   effect: {"food": n, "water": n, "hp": n, "dmg": n}
ITEMS = {
    "beans":     ("tin of beans", "food", 0.4, (190, 120, 70), {"food": 35}),
    "jerky":     ("strip of jerky", "food", 0.1, (150, 80, 60), {"food": 20}),
    "bread":     ("loaf of stale bread", "food", 0.3, (200, 170, 110), {"food": 25}),
    "fruit":     ("odd fruit", "food", 0.2, (200, 90, 150), {"food": 15, "water": 10}),
    "water":     ("bottle of water", "drink", 0.5, (110, 170, 220), {"water": 45}),
    "tea":       ("flask of cold tea", "drink", 0.5, (170, 130, 80), {"water": 30, "food": 5}),
    "bandage":   ("bandage", "medical", 0.1, (230, 225, 210), {"hp": 8}),
    "medkit":    ("medkit", "medical", 0.8, (220, 60, 60), {"hp": 25}),
    "knife":     ("kitchen knife", "weapon", 0.3, (200, 200, 210), {"dmg": 2}),
    "crowbar":   ("crowbar", "weapon", 1.5, (170, 60, 50), {"dmg": 3}),
    "pipe":      ("length of pipe", "weapon", 2.0, (130, 130, 140), {"dmg": 2}),
    "scrap":     ("piece of scrap metal", "part", 1.0, (140, 140, 150), {}),
    "wire":      ("coil of wire", "part", 0.3, (200, 140, 60), {}),
    "battery":   ("battery", "part", 0.6, (90, 170, 90), {}),
    "circuit":   ("circuit board", "part", 0.2, (60, 140, 80), {}),
    "cloth":     ("bolt of cloth", "part", 0.4, (150, 120, 170), {}),
    "rope":      ("rope", "part", 0.8, (170, 150, 100), {}),
    "fuel":      ("fuel cell", "part", 2.0, (230, 200, 60), {}),
    "wood":      ("bundle of wood", "part", 1.2, (150, 110, 70), {}),
    # old weapons of Japan and China (charcreate.OLD_WEAPONS has their symbols and fighting styles)
    "katana":    ("katana", "weapon", 1.2, (215, 215, 225), {"dmg": 4}),
    "wakizashi": ("wakizashi", "weapon", 0.7, (205, 205, 215), {"dmg": 3}),
    "tanto":     ("tantō", "weapon", 0.3, (200, 200, 210), {"dmg": 2}),
    "naginata":  ("naginata", "weapon", 2.5, (180, 140, 90), {"dmg": 4}),
    "yari":      ("yari spear", "weapon", 2.0, (170, 140, 100), {"dmg": 4}),
    "kusarigama": ("kusarigama", "weapon", 1.5, (160, 160, 170), {"dmg": 3}),
    "kanabo":    ("kanabō club", "weapon", 6.0, (90, 80, 70), {"dmg": 5}),
    "yumi":      ("yumi bow", "weapon", 1.0, (190, 150, 90), {"dmg": 3}),
    "jian":      ("jian", "weapon", 1.0, (220, 220, 200), {"dmg": 3}),
    "dao":       ("dao sabre", "weapon", 1.3, (210, 200, 190), {"dmg": 4}),
    "guandao":   ("guan dao", "weapon", 5.5, (200, 60, 50), {"dmg": 5}),
    "ji":        ("ji halberd", "weapon", 3.0, (190, 170, 120), {"dmg": 4}),
    "meteor":    ("meteor hammer", "weapon", 2.5, (150, 150, 160), {"dmg": 4}),
    "hooks":     ("pair of hook swords", "weapon", 2.0, (200, 200, 210), {"dmg": 3}),
    "butterfly": ("pair of butterfly swords", "weapon", 1.4, (210, 210, 220), {"dmg": 3}),
    "chukonu":   ("chu-ko-nu crossbow", "weapon", 2.2, (160, 120, 80), {"dmg": 3}),
}
OLD = ["katana", "wakizashi", "tanto", "naginata", "yari", "kusarigama", "kanabo", "yumi",
       "jian", "dao", "guandao", "ji", "meteor", "hooks", "butterfly", "chukonu"]

# what turns up where: container code -> (chance of anything, [(item, weight), ...], most items)
LOOT = {
    "f_stove":  (0.7, [("beans", 4), ("bread", 3), ("jerky", 2), ("tea", 2), ("knife", 1)], 2),
    "f_shelf":  (0.8, [("beans", 3), ("water", 3), ("bandage", 2), ("wire", 2), ("battery", 1), ("rope", 1)], 3),
    "f_dress":  (0.6, [("cloth", 4), ("bandage", 2), ("knife", 1), ("water", 1)], 2),
    "f_end":    (0.5, [("bandage", 3), ("water", 2), ("battery", 1), ("medkit", 1)], 1),
    "f_crate":  (0.85, [("beans", 3), ("water", 3), ("scrap", 3), ("rope", 2), ("crowbar", 1), ("fuel", 1)], 3),
    "f_sink":   (0.4, [("water", 4), ("bandage", 1)], 1),
    "f_fridge": (0.75, [("beans", 2), ("water", 3), ("fruit", 2), ("jerky", 2), ("tea", 2)], 3),
    "f_ward":   (0.6, [("cloth", 4), ("rope", 1), ("bandage", 1), ("tanto", 1)], 2),
    "f_bench":  (0.85, [("crowbar", 1), ("pipe", 1), ("wire", 3), ("scrap", 3), ("battery", 1), ("circuit", 1)], 3),
    "f_barrel": (0.5, [("fuel", 1), ("water", 1), ("scrap", 1)], 1),
    "f_drum":    (0.4, [("fuel", 1), ("scrap", 2), ("jerky", 1)], 1),
    "f_crtab":   (0.5, [("beans", 2), ("bread", 1), ("jerky", 2), ("knife", 1)], 2),
    "f_sshelf":  (0.7, [("beans", 2), ("water", 2), ("wire", 2), ("bandage", 2), ("battery", 1), ("rope", 1)], 2),
    "f_bucket":  (0.45, [("water", 3), ("rope", 1)], 1),
    "f_rags":    (0.6, [("cloth", 4), ("bandage", 2)], 2),
    "f_wbarrel": (0.7, [("water", 5)], 2),
    "f_shrine":  (0.7, [("medkit", 1), ("circuit", 1), ("fruit", 2), ("bandage", 1), ("katana", 1), ("jian", 1),
                        ("wakizashi", 1), ("butterfly", 1), ("tanto", 1)], 1),
    "p_crate":  (0.8, [("scrap", 4), ("wire", 3), ("beans", 2), ("water", 2), ("circuit", 1), ("crowbar", 1)], 3),
    "p_barrel": (0.6, [("water", 4), ("fuel", 1), ("scrap", 2)], 2),
    "p_rack":   (0.6, [("pipe", 2), ("scrap", 3), ("wire", 2), ("rope", 1), ("battery", 1), ("naginata", 1),
                       ("yari", 1), ("ji", 1), ("guandao", 1), ("kanabo", 1), ("dao", 1), ("meteor", 1), ("hooks", 1),
                       ("kusarigama", 1), ("yumi", 1), ("chukonu", 1)], 2),
    "p_cart":   (0.6, [("scrap", 3), ("rope", 2), ("beans", 1), ("fuel", 1)], 2),
    "p_wagon":  (0.6, [("scrap", 3), ("cloth", 2), ("rope", 2), ("jerky", 1)], 2),
    "p_scrap":  (0.9, [("scrap", 5), ("wire", 2), ("circuit", 1), ("battery", 1)], 3),
    "p_car":    (0.7, [("scrap", 3), ("battery", 2), ("fuel", 1), ("wire", 2), ("circuit", 1)], 2),
    "p_truck":  (0.7, [("scrap", 3), ("battery", 2), ("fuel", 2), ("wire", 2)], 3),
    "p_hull":   (0.8, [("scrap", 4), ("circuit", 2), ("wire", 2), ("fuel", 1)], 3),
    "p_pod":    (0.8, [("medkit", 1), ("water", 2), ("circuit", 2), ("battery", 1)], 2),
    "p_panel":  (0.6, [("circuit", 2), ("wire", 3), ("battery", 2)], 2),
}

NAMES = {"f_stove": "cooker", "f_shelf": "cupboard", "f_dress": "dresser", "f_end": "bedside table", "f_crate": "box",
         "f_sink": "sink", "f_fridge": "fridge", "f_ward": "wardrobe", "f_bench": "workbench", "f_barrel": "oil drum",
         "f_drum": "oil-drum stove", "f_crtab": "crate table", "f_sshelf": "scrap shelf", "f_bucket": "bucket",
         "f_rags": "pile of rags", "f_wbarrel": "water barrel", "f_shrine": "shrine"}


def loot(seed, code, x, y):
    """what's in the container at (x, y): {item: count}"""
    if code not in LOOT:
        return {}
    chance, table, most = LOOT[code]
    r = random.Random(zlib.crc32(f"{seed}:{code}:{x}:{y}".encode()))
    if r.random() > chance:
        return {}
    got = {}
    for _ in range(r.randint(1, most)):
        it = r.choices([t for t, _ in table], [w for _, w in table])[0]
        got[it] = got.get(it, 0) + 1
    return got


def weight(inv):
    return sum(ITEMS[i][2] * n for i, n in inv.items())


def describe(got):
    if not got:
        return "nothing"
    parts = [(f"{n} x " if n > 1 else "a ") + ITEMS[i][0] for i, n in got.items()]
    return ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]


# MS-DOS look for the menus: (symbol, VGA colour)
GLYPH = {
    "beans": ("%", "brown"), "jerky": ("%", "red"), "bread": ("%", "yellow"), "fruit": ("%", "lmagenta"),
    "water": ("!", "lblue"), "tea": ("!", "brown"),
    "bandage": ("≈", "white"), "medkit": ("♥", "lred"),
    "knife": (")", "white"), "crowbar": (")", "red"), "pipe": (")", "grey"),
    "katana": (")", "white"), "wakizashi": (")", "white"), "tanto": (")", "grey"), "naginata": ("/", "brown"),
    "yari": ("/", "brown"), "kusarigama": ("(", "grey"), "kanabo": ("\\", "dgrey"), "yumi": ("}", "brown"),
    "jian": (")", "yellow"), "dao": (")", "white"), "guandao": ("/", "lred"), "ji": ("/", "yellow"),
    "meteor": ("(", "grey"), "hooks": (")", "lcyan"), "butterfly": (")", "lcyan"), "chukonu": ("}", "brown"),
    "scrap": ("*", "dgrey"), "wire": ("~", "yellow"), "battery": ("■", "lgreen"), "circuit": ("≡", "green"),
    "cloth": ("░", "magenta"), "rope": ("§", "brown"), "fuel": ("♦", "yellow"),
    "wood": ("=", "brown"),
}
CATEGORY = {"food": ("Comestibles", "%"), "drink": ("Drinks", "!"), "medical": ("Medicine", "♥"),
            "weapon": ("Hand weapons", ")"), "part": ("Salvage", "*")}
DESC = {
    "beans": "A dented tin. The label's been peeled off and something drawn on the metal underneath.",
    "jerky": "Dried meat. You don't ask what from.",
    "bread": "Stale, but there's no mould on it. Nothing grows on it at all.",
    "fruit": "It grew here. It's warm, like something alive.",
    "water": "Clear, mostly. Boil it if you can.",
    "tea": "Cold and bitter. Someone made it and never came back to drink it.",
    "bandage": "Clean cloth, rolled tight.",
    "medkit": "A colony-issue kit. Half the vials are gone; the rest are still sealed.",
    "knife": "A kitchen knife. The edge has been kept sharp. Recently.",
    "crowbar": "Heavy, and good for doors that were nailed shut from the inside.",
    "pipe": "A length of pipe with a dark crust at one end.",
    "scrap": "Bent sheet metal from the ship. It might go back where it came from.",
    "wire": "Copper, stripped from the walls of somewhere.",
    "battery": "Still holds a charge. It hums very faintly when you're not holding it.",
    "circuit": "A board from the landing craft's systems. Something's scratched into the back.",
    "cloth": "A bolt of sheeting, for bandages or patching.",
    "rope": "Strong rope, frayed at one end as if it was cut in a hurry.",
    "fuel": "A fuel cell. Precious. The colony would have killed for this. Maybe someone did.",
    "wood": "Dead branches, snapped and bundled. Everything out here burns, eventually.",
    "katana": "Japan. A long curved sword, two hands on the grip. Someone carried it a very long way from Earth.",
    "wakizashi": "Japan. The katana's shorter companion. Quick in tight places.",
    "tanto": "Japan. A short straight dagger, more for the last moment than the first.",
    "naginata": "Japan. A curved blade on a long pole. Sweeps keep things at a distance.",
    "yari": "Japan. A straight spear. Whatever comes at you meets the point first.",
    "kusarigama": "Japan. A sickle on a weighted chain. Swing, snare, pull.",
    "kanabo": "Japan. A studded iron club. Heavy enough that technique stops mattering.",
    "yumi": "Japan. A tall asymmetric bow of bamboo and lacquer, the string still taut.",
    "jian": "China. A straight double-edged sword, the 'gentleman of weapons'. Light and precise.",
    "dao": "China. A single-edged sabre, broad at the tip. The 'general of weapons'.",
    "guandao": "China. A heavy crescent blade on a long shaft, red tassel gone brown.",
    "ji": "China. A spear with a crescent blade bolted to the side. Thrust or hook.",
    "meteor": "China. Two iron weights on a long rope. Hard to learn, harder to get away from.",
    "hooks": "China. Twin swords with hooked tips that lock together into one long whip of steel.",
    "butterfly": "China. A pair of short broad blades, one for each hand.",
    "chukonu": "China. A repeating crossbow with a magazine of bolts on top. Pull the lever, loose, again.",
}


def plural(k, n):
    """'a tin of beans' / '2 tins of beans'"""
    name = ITEMS[k][0]
    if n == 1:
        return ("an " if name[0] in "aeiou" else "a ") + name
    head, sep, tail = name.partition(" of ")
    irregular = {"loaf": "loaves", "knife": "knives", "strip": "strips", "pair": "pairs"}
    last = head.split()[-1]
    if last in irregular:
        head = head[: -len(last)] + irregular[last]
    else:
        head = head + ("es" if head.endswith(("ch", "sh", "x", "s")) else "s")
    return f"{n} {head}{sep}{tail}"


# what you can build (B): name -> (cell codes it takes up, cost {item: n}, what it is)
BUILD = [
    ("Plank wall", ["swall_wood"], {"wood": 2}, "Badly nailed planks. Keeps most things out."),
    ("Scrap wall", ["swall_iron"], {"scrap": 2}, "Sheet iron. Loud when things hit it, which is the point."),
    ("Tarp wall", ["swall_tarp"], {"cloth": 1, "rope": 1}, "Cheap. You can hear through it. So can they."),
    ("Doorway", ["sdoor"], {"wood": 1, "cloth": 1}, "A gap in the wall with a rag over it."),
    ("Pallet floor", ["spallet"], {"wood": 1}, "Keeps you out of the mud."),
    ("Campfire", ["bonfire"], {"wood": 3}, "Light and warmth. Your camp starts where your fire is."),
    ("Bedroll", ["f_matt0", "f_matt1"], {"cloth": 2}, "Somewhere to lie down. It's not sleep, quite."),
    ("Storage crate", ["f_crate"], {"wood": 3}, "Keeps what you put in it. Nobody else can be trusted to."),
    ("Workbench", ["f_bench"], {"wood": 3, "scrap": 2}, "Somewhere to make things, when you know how."),
    ("Water barrel", ["f_wbarrel"], {"scrap": 2, "rope": 1}, "Catches what the sky gives. Mostly water."),
    ("Spiked barricade", ["p_fence"], {"wood": 2}, "Sharpened stakes. Slows them down. Hurts them going over."),
]
