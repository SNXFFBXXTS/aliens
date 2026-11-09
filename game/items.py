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
}

# what turns up where: container code -> (chance of anything, [(item, weight), ...], most items)
LOOT = {
    "f_stove":  (0.7, [("beans", 4), ("bread", 3), ("jerky", 2), ("tea", 2), ("knife", 1)], 2),
    "f_shelf":  (0.8, [("beans", 3), ("water", 3), ("bandage", 2), ("wire", 2), ("battery", 1), ("rope", 1)], 3),
    "f_dress":  (0.6, [("cloth", 4), ("bandage", 2), ("knife", 1), ("water", 1)], 2),
    "f_end":    (0.5, [("bandage", 3), ("water", 2), ("battery", 1), ("medkit", 1)], 1),
    "f_crate":  (0.85, [("beans", 3), ("water", 3), ("scrap", 3), ("rope", 2), ("crowbar", 1), ("fuel", 1)], 3),
    "f_sink":   (0.4, [("water", 4), ("bandage", 1)], 1),
    "f_fridge": (0.75, [("beans", 2), ("water", 3), ("fruit", 2), ("jerky", 2), ("tea", 2)], 3),
    "f_ward":   (0.6, [("cloth", 4), ("rope", 1), ("bandage", 1)], 2),
    "f_bench":  (0.85, [("crowbar", 1), ("pipe", 1), ("wire", 3), ("scrap", 3), ("battery", 1), ("circuit", 1)], 3),
    "f_barrel": (0.5, [("fuel", 1), ("water", 1), ("scrap", 1)], 1),
    "f_drum":    (0.4, [("fuel", 1), ("scrap", 2), ("jerky", 1)], 1),
    "f_crtab":   (0.5, [("beans", 2), ("bread", 1), ("jerky", 2), ("knife", 1)], 2),
    "f_sshelf":  (0.7, [("beans", 2), ("water", 2), ("wire", 2), ("bandage", 2), ("battery", 1), ("rope", 1)], 2),
    "f_bucket":  (0.45, [("water", 3), ("rope", 1)], 1),
    "f_rags":    (0.6, [("cloth", 4), ("bandage", 2)], 2),
    "f_wbarrel": (0.7, [("water", 5)], 2),
    "f_shrine":  (0.6, [("medkit", 1), ("circuit", 1), ("fruit", 2), ("bandage", 1)], 1),
    "p_crate":  (0.8, [("scrap", 4), ("wire", 3), ("beans", 2), ("water", 2), ("circuit", 1), ("crowbar", 1)], 3),
    "p_barrel": (0.6, [("water", 4), ("fuel", 1), ("scrap", 2)], 2),
    "p_rack":   (0.6, [("pipe", 2), ("scrap", 3), ("wire", 2), ("rope", 1), ("battery", 1)], 2),
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
    "scrap": ("*", "dgrey"), "wire": ("~", "yellow"), "battery": ("■", "lgreen"), "circuit": ("≡", "green"),
    "cloth": ("░", "magenta"), "rope": ("§", "brown"), "fuel": ("♦", "yellow"),
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
}


def plural(k, n):
    """'a tin of beans' / '2 tins of beans'"""
    name = ITEMS[k][0]
    if n == 1:
        return ("an " if name[0] in "aeiou" else "a ") + name
    head, sep, tail = name.partition(" of ")
    irregular = {"loaf": "loaves", "knife": "knives", "strip": "strips"}
    last = head.split()[-1]
    if last in irregular:
        head = head[: -len(last)] + irregular[last]
    else:
        head = head + ("es" if head.endswith(("ch", "sh", "x", "s")) else "s")
    return f"{n} {head}{sep}{tail}"
