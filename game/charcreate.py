"""Character creation: each character IS a Japanese symbol (in the font), two-toned skin/clothes, with its gear
shown as smaller symbols placed on it (hat on top, weapon at the hand, pack or coat behind).

30 archetypes plus "Make your own" (pick everything, spend stat points, choose traits, type a name).
The character spars with a training dummy: moves depend on the weapon (F, or it shows off when idle).

Keys: up/down who you were, left/right body, C skin, N name, R random, F fight, Enter keep, Esc quit.
In the builder: Tab to edit, up/down pick a row, left/right change it, type a name, Tab/Esc to stop editing.
Saves the chosen character to ~/.local/share/roguelike/character.json.
"""
import json, math, os, random, time
import pygame
import heads

import fonts
CJK, UI, UIB = fonts.find(fonts.CJK), fonts.find(fonts.UI), fonts.find(fonts.UIB)

BODIES = [("人", "person"), ("大", "big"), ("天", "heaven"), ("夫", "husband"), ("太", "thick"), ("女", "woman"),
          ("子", "child"), ("兵", "soldier"), ("立", "stand"), ("走", "run"), ("光", "light"), ("元", "origin"),
          ("兄", "elder brother"), ("先", "ahead"), ("鬼", "demon"), ("侍", "samurai"), ("央", "centre"),
          ("ス", "su"), ("ヌ", "nu"), ("メ", "me")]
SKINS = [("Umber", (150, 104, 76)), ("Ochre", (206, 160, 118)), ("Pale", (232, 206, 186)), ("Ash", (176, 176, 168)),
         ("Moss", (126, 170, 104)), ("Dusk", (138, 132, 190)), ("Rust", (190, 96, 70)), ("Chrome", (200, 210, 220))]
COLOURS = [("Leather", (110, 74, 48)), ("Navy", (42, 66, 120)), ("Olive", (86, 96, 54)), ("Crimson", (150, 36, 60)),
           ("Teal", (70, 140, 130)), ("Violet", (70, 46, 110)), ("Ash", (64, 78, 72)), ("Orange", (190, 110, 36)),
           ("Bone", (196, 186, 160)), ("Black", (64, 60, 74))]
TRIMS = [("Gold", (210, 170, 90)), ("Cyan", (90, 230, 210)), ("Silver", (180, 180, 170)), ("Yellow", (240, 210, 90)),
         ("Pink", (240, 110, 190)), ("Green", (130, 220, 120)), ("Lilac", (200, 140, 255)), ("White", (235, 235, 235))]

# gear: code -> (symbol, name)
HATS = {None: ("", "—"), "cowboy": ("笠", "wide-brim hat"), "cap": ("帽", "cap"), "hardhat": ("冑", "hard hat"),
        "beanie": ("帽", "beanie"), "hood": ("巾", "hood"), "goggles": ("眼", "goggles"), "circlet": ("冠", "circlet"),
        "helmet": ("冑", "helmet"), "bandana": ("巾", "bandana"), "crown": ("冠", "crown"), "visor": ("眼", "visor")}
WEAPONS = {None: ("", "—"), "revolver": ("銃", "revolver"), "shotgun": ("砲", "shotgun"), "derringer": ("弾", "derringer"),
           "rifle": ("銃", "rifle"), "knife": ("刀", "knife"), "katana": ("剣", "katana"), "axe": ("斧", "axe"),
           "scalpel": ("刃", "scalpel"), "wrench": ("工", "wrench"), "crowbar": ("鉄", "crowbar"), "pan": ("鍋", "frying pan"),
           "hoe": ("鍬", "hoe"), "spade": ("鋤", "spade"), "staff": ("杖", "staff"), "whip": ("鞭", "whip"),
           "fists": ("拳", "fists"), "claws": ("爪", "claws"), "mecharm": ("機", "machine arm"), "tome": ("書", "tome"),
           "deck": ("電", "deck"), "orb": ("珠", "orb"), "sax": ("楽", "saxophone"), "bow": ("弓", "bow"),
           "shield": ("盾", "riot shield"), "flask": ("瓶", "flasks")}
# old Japanese and Chinese weapons: you can pick one to start with, and they turn up in the world (items.ITEMS)
OLD_WEAPONS = {
    "katana": ("剣", "katana", "Japan", "blade"), "wakizashi": ("脇", "wakizashi", "Japan", "blade"),
    "tanto": ("短", "tantō", "Japan", "blade"), "naginata": ("薙", "naginata", "Japan", "staff"),
    "yari": ("槍", "yari", "Japan", "staff"), "kusarigama": ("鎌", "kusarigama", "Japan", "whip"),
    "kanabo": ("棒", "kanabō", "Japan", "heavy"), "yumi": ("弓", "yumi", "Japan", "bow"),
    "jian": ("剑", "jian", "China", "blade"), "dao": ("刀", "dao", "China", "blade"),
    "guandao": ("偃", "guan dao", "China", "heavy"), "ji": ("戟", "ji halberd", "China", "staff"),
    "meteor": ("錘", "meteor hammer", "China", "whip"), "hooks": ("鉤", "hook swords", "China", "blade"),
    "butterfly": ("蝶", "butterfly swords", "China", "blade"), "chukonu": ("弩", "chu-ko-nu", "China", "bow"),
}
WEAPONS.update({k: (g, n) for k, (g, n, _, _) in OLD_WEAPONS.items()})

# clothes: what you wear changes your colours (jacket over the middle, trousers on the legs) and helps a little
JACKETS = [
    dict(name="Flight jacket", col=(112, 72, 44), hem=(206, 190, 160), armour=1, speed=0, carry=0,
         what="Cracked leather, sheepskin collar. Takes a knock."),
    dict(name="Haori", col=(38, 48, 104), hem=(225, 225, 215), armour=0, speed=5, carry=0,
         what="A light indigo coat tied with white cord. Nothing holds you back."),
    dict(name="Colony parka", col=(196, 112, 34), hem=(60, 58, 70), armour=1, speed=0, carry=3,
         what="Hi-vis orange, colony issue. Deep pockets."),
    dict(name="Lamellar coat", col=(96, 100, 110), hem=(170, 56, 48), armour=2, speed=-6, carry=0,
         what="Iron plates laced with red cord. Heavy, and hard to get through."),
    dict(name="Silk tangzhuang", col=(156, 34, 58), hem=(214, 172, 88), armour=0, speed=7, carry=0,
         what="Red silk, knotted gold buttons. Light and quick."),
]
TROUSERS = [
    dict(name="Cargo trousers", col=(84, 96, 52), hem=None, armour=0, speed=0, carry=4,
         what="Pockets on the pockets."),
    dict(name="Hakama", col=(44, 42, 54), hem=(150, 150, 165), armour=0, speed=3, carry=1,
         what="Wide pleated trousers. They hide which way your feet are going."),
    dict(name="Work jeans", col=(46, 70, 126), hem=(150, 120, 70), armour=1, speed=0, carry=1,
         what="Heavy denim, double-stitched. Hard to bite through."),
    dict(name="Kung fu trousers", col=(50, 50, 60), hem=(230, 230, 230), armour=0, speed=8, carry=0,
         what="Black cotton, tied at the ankle. Made for moving."),
    dict(name="Plated greaves", col=(118, 118, 126), hem=(64, 62, 74), armour=1, speed=-4, carry=0,
         what="Trousers with iron plates sewn down the shins."),
]


def outfit_bonus(jacket, trousers):
    """(armour, speed %, carry kg) from what you're wearing (None = your own old clothes: nothing extra)"""
    got = [c for c in ((JACKETS[jacket] if jacket is not None else None),
                       (TROUSERS[trousers] if trousers is not None else None)) if c]
    return tuple(sum(c[k] for c in got) for k in ("armour", "speed", "carry"))


def bonus_text(c):
    bits = [f"+{c['armour']} armour" if c["armour"] else "", f"{c['speed']:+d}% speed" if c["speed"] else "",
            f"+{c['carry']} kg carry" if c["carry"] else ""]
    return ", ".join(b for b in bits if b) or "nothing extra"


BACKS = {None: ("", "—"), "duster": ("衣", "duster coat"), "pack": ("包", "backpack"), "cloak": ("套", "cloak"),
         "quiver": ("矢", "quiver"), "tank": ("缶", "tank")}
EXTRAS = {None: ("", "—"), "vest": ("甲", "armour vest"), "scarf": ("巾", "scarf"), "belt": ("帯", "toolbelt"),
          "mutation": ("変", "mutation"), "chain": ("鎖", "chains"), "beads": ("珠", "beads"), "goggles": ("眼", "goggles")}

# how each weapon fights
STYLE = {"revolver": "gun", "shotgun": "gun", "derringer": "gun", "rifle": "gun", "knife": "blade", "katana": "blade",
         "axe": "heavy", "scalpel": "blade", "wrench": "heavy", "crowbar": "heavy", "pan": "heavy", "hoe": "heavy",
         "spade": "heavy", "staff": "staff", "whip": "whip", "fists": "unarmed", "claws": "unarmed", "mecharm": "unarmed",
         "tome": "magic", "deck": "magic", "orb": "magic", "sax": "magic", "bow": "bow", "shield": "shield",
         "flask": "throw", None: "unarmed"}
STYLE.update({k: v[3] for k, v in OLD_WEAPONS.items()})
MOVES = {"gun": ["Snap shot", "Fan the hammer", "Diving shot"], "blade": ["Slash", "Thrust", "Spinning cut"],
         "heavy": ["Overhead smash", "Wide swing", "Shoulder charge"], "staff": ["Sweep", "Vault kick", "Twirl"],
         "whip": ["Crack", "Lash", "Snare"], "unarmed": ["Jab-cross", "Roundhouse", "Uppercut"],
         "magic": ["Bolt", "Nova", "Levitate"], "bow": ["Loose", "Double shot", "Rain"], "shield": ["Bash", "Block", "Charge"],
         "throw": ["Lob", "Splash", "Smoke"]}

STATS = ("STR", "AGI", "TOU", "WIT", "CHA", "LCK")
GOOD = [("Tracker", "follows tracks others miss"), ("Quick draw", "shoots first in a fight"), ("Wired", "hacks terminals and drones"),
        ("Iron arm", "hits hard, blocks blades"), ("Silver tongue", "better prices, talks down fights"), ("Lucky", "finds more loot"),
        ("Ace", "flies and repairs ships"), ("Brawler", "fights well unarmed"), ("Forager", "finds food and water"),
        ("Steady hands", "heals better"), ("Builder", "builds and repairs fast"), ("Tough", "shrugs off hits"),
        ("Night owl", "sharper at night"), ("Sprinter", "runs faster"), ("Cook", "makes better meals"),
        ("Green thumb", "grows food anywhere"), ("Beast friend", "animals don't attack first"), ("Telepath", "senses minds")]
BAD = [("Broke", "starts with almost no money"), ("Frail", "low health"), ("Bad back", "carries less"),
       ("Gambler", "can't walk past a bet"), ("Paranoid", "hates crowds"), ("Squeamish", "hates gore"), ("Slow", "walks slower"),
       ("Outcast", "towns don't trust you"), ("Migraines", "powers hurt to use"), ("Wanted", "bounty hunters after you"),
       ("Addict", "needs a fix"), ("Night terrors", "sleeps badly"), ("Clumsy", "drops things"), ("Loud", "everything hears you")]


def A(name, tag, blurb, stats, traits, kit, look, head=None):
    return dict(name=name, tag=tag, blurb=blurb, stats=stats,
                traits=[(t, ("+ " if i < 2 else "- ") + d) for i, (t, d) in enumerate(traits)], kit=kit, look=look,
                head=head)


L = lambda c: dict(COLOURS)[c]
T = lambda c: dict(TRIMS)[c]
ARCH = [
    A("Bounty Hunter", "Drift", "Chases warrants across the dead worlds for whatever they pay. Never asks why.", (5, 7, 5, 5, 4, 5),
      [("Tracker", "follows tracks others miss"), ("Quick draw", "shoots first in a fight"), ("Broke", "starts with almost no money")],
      ["Revolver", "Duster coat", "Wide-brim hat", "Handcuffs", "Warrant"], ("cowboy", "revolver", "duster", None, L("Leather"), T("Gold"))),
    A("Netrunner", "Drift", "Talks to machines better than people. Breaks locks, cameras and minds made of code.", (2, 6, 3, 9, 4, 6),
      [("Wired", "hacks terminals and drones"), ("Night owl", "sharper at night"), ("Frail", "low health")],
      ["Deck", "Hoodie", "Goggles", "Energy drinks"], ("hood", "deck", None, "goggles", (60, 64, 92), T("Cyan"))),
    A("Ex-Cop", "Drift", "Used to wear a badge. Still has the arm they gave you when you lost yours.", (7, 4, 7, 5, 5, 3),
      [("Iron arm", "hits hard, blocks blades"), ("Old habits", "spots lies"), ("Bad back", "carries less")],
      ["Shotgun", "Armour vest", "Cap", "Bonsai"], ("cap", "shotgun", None, "vest", L("Ash"), T("Silver"))),
    A("Grifter", "Drift", "Owes money on four planets. Smiles their way out of most of it.", (3, 7, 3, 6, 8, 7),
      [("Silver tongue", "better prices, talks down fights"), ("Lucky", "finds more loot"), ("Gambler", "can't walk past a bet")],
      ["Derringer", "Cards", "Silk scarf", "Fake ID"], (None, "derringer", None, "scarf", L("Crimson"), T("Yellow"))),
    A("Drifter Pilot", "Drift", "Can fly anything with an engine. Crashed the last one. That's why you're here.", (5, 8, 5, 5, 4, 4),
      [("Ace", "flies and repairs ships"), ("Brawler", "fights well unarmed"), ("Drifting", "forgets what they're doing")],
      ["Knife", "Flight jacket", "Aviator goggles", "Ship part"], ("goggles", "knife", None, "scarf", L("Navy"), T("Gold"))),
    A("Survivalist", "Zomboid", "Was ready for the end before it came. Boards up windows for fun.", (6, 5, 7, 5, 3, 4),
      [("Forager", "finds food and water"), ("Light sleeper", "wakes when danger comes"), ("Paranoid", "hates crowds")],
      ["Fire axe", "Backpack", "Beanie", "Canned beans"], ("beanie", "axe", "pack", None, L("Olive"), (170, 120, 60))),
    A("Field Medic", "Zomboid", "Patched up the dying until there were none left to patch.", (3, 5, 4, 8, 6, 4),
      [("Steady hands", "heals better"), ("Calm", "doesn't panic"), ("Squeamish", "hates gore")],
      ["Scalpel", "Medkit", "Scrubs", "Bandages"], ("cap", "scalpel", "pack", None, L("Teal"), T("White"))),
    A("Colony Engineer", "RimWorld", "Built half a colony before the raid. Will build the rest out of scrap.", (5, 4, 5, 7, 4, 5),
      [("Builder", "builds and repairs fast"), ("Tinkerer", "makes parts from junk"), ("Slow", "walks slower")],
      ["Wrench", "Toolbelt", "Hard hat", "Duct tape"], ("hardhat", "wrench", None, "belt", L("Orange"), T("Yellow"))),
    A("Mutant Pilgrim", "Qud", "Born changed, walking the salt roads to somewhere sacred. The change is still going.", (6, 5, 6, 4, 3, 6),
      [("Mutation", "a random mutation"), ("Pilgrim", "walks far without tiring"), ("Outcast", "towns don't trust you")],
      ["Staff", "Travel cloak", "Hood", "Water skin"], ("hood", "staff", "cloak", "mutation", (120, 96, 70), T("Green"))),
    A("Esper", "Qud", "Hears thoughts like radio static. Some of the voices aren't from people.", (3, 5, 4, 9, 6, 4),
      [("Telepath", "senses minds through walls"), ("Psychic shield", "resists mind attacks"), ("Migraines", "powers hurt to use")],
      ["Tome", "Robe", "Circlet", "Strange stone"], ("circlet", "tome", "cloak", None, L("Violet"), T("Lilac"))),
    # ── 20 more ──
    A("Smuggler", "Drift", "Knows every customs blind spot between here and the rim. Their cargo is never what it says.", (4, 7, 4, 6, 6, 6),
      [("Silver tongue", "better prices"), ("Hidden pockets", "carries contraband unseen"), ("Wanted", "bounty hunters after you")],
      ["Derringer", "Long coat", "Bandana", "Sealed crate"], ("bandana", "derringer", "duster", None, L("Black"), T("Gold"))),
    A("Gunslinger", "Drift", "Two holsters, one rule. The fastest hands left on the planet, probably.", (4, 9, 4, 4, 5, 5),
      [("Quick draw", "shoots first"), ("Trick shot", "ricochets bullets"), ("Loud", "everything hears you")],
      ["Revolver", "Duster coat", "Wide-brim hat", "Spurs"], ("cowboy", "revolver", "duster", "belt", L("Bone"), T("Silver"))),
    A("Ronin", "Drift", "Their master died, their clan scattered. The sword is all that's left, and it's enough.", (6, 8, 5, 5, 3, 4),
      [("Iai", "cuts first, cuts once"), ("Discipline", "doesn't panic"), ("Outcast", "towns don't trust you")],
      ["Katana", "Robe", "Sedge hat", "Whetstone"], ("cowboy", "katana", "cloak", None, L("Black"), T("Pink"))),
    A("Martial Artist", "Drift", "Be like water. Hits like a shuttle. Fights barefoot on principle.", (6, 9, 6, 4, 4, 4),
      [("Brawler", "fights well unarmed"), ("Flow", "dodges more"), ("Bad back", "carries less")],
      ["Fists", "Wraps", "Headband", "Nunchaku"], ("bandana", "fists", None, "belt", L("Navy"), T("Yellow"))),
    A("Jazz Musician", "Drift", "Plays the dead bars of dead towns. The music makes things stop and listen. Some things.", (3, 6, 3, 6, 9, 6),
      [("Charm", "calms people and beasts"), ("Lucky", "finds more loot"), ("Night terrors", "sleeps badly")],
      ["Saxophone", "Fedora", "Smart suit", "Reeds"], ("cap", "sax", None, "scarf", L("Black"), T("Gold"))),
    A("Bartender", "Drift", "Heard every story twice. Pours a drink that could strip paint, and makes you like it.", (5, 4, 6, 6, 8, 5),
      [("Listener", "hears rumours"), ("Iron gut", "eats anything"), ("Addict", "needs a fix")],
      ["Shotgun", "Apron", "Bottles", "Rag"], (None, "shotgun", None, "vest", L("Crimson"), T("White"))),
    A("Cook", "RimWorld", "Can turn anything into a meal. Has turned some things into a meal they shouldn't have.", (5, 5, 6, 5, 6, 5),
      [("Cook", "makes better meals"), ("Iron gut", "eats anything"), ("Clumsy", "drops things")],
      ["Frying pan", "Apron", "Spices", "Cleaver"], ("cap", "pan", None, "belt", L("Bone"), T("Gold"))),
    A("Preacher", "RimWorld", "Lost faith in one god, found three more out here. Converts are rare. Hymns are loud.", (4, 4, 5, 6, 8, 6),
      [("Sermon", "rallies allies"), ("Calm", "doesn't panic"), ("Loud", "everything hears you")],
      ["Holy book", "Robe", "Beads", "Bell"], (None, "tome", "cloak", "beads", L("Black"), T("White"))),
    A("Scavenger", "Zomboid", "Strips buildings bare in minutes. Knows which floorboards hide things.", (5, 6, 5, 6, 3, 7),
      [("Lucky", "finds more loot"), ("Light step", "quieter"), ("Paranoid", "hates crowds")],
      ["Crowbar", "Backpack", "Beanie", "Torch"], ("beanie", "crowbar", "pack", None, L("Ash"), (170, 120, 60))),
    A("Ship Mechanic", "Drift", "Talks to engines. The engines talk back. Mostly about how badly you've treated them.", (6, 4, 6, 8, 3, 5),
      [("Ace", "repairs ships"), ("Tinkerer", "makes parts from junk"), ("Night terrors", "sleeps badly")],
      ["Wrench", "Overalls", "Goggles", "Spare parts"], ("goggles", "wrench", "tank", "belt", L("Orange"), T("Silver"))),
    A("Courier", "RimWorld", "Delivers anything, anywhere, once. Never been late. Never opened a package. Probably.", (4, 9, 5, 5, 5, 5),
      [("Sprinter", "runs faster"), ("Pathfinder", "never gets lost"), ("Frail", "low health")],
      ["Knife", "Courier bag", "Cap", "Parcel"], ("cap", "knife", "pack", None, L("Teal"), T("Yellow"))),
    A("Hunter", "RimWorld", "Reads the land like a page. Never wastes an arrow, never wastes a kill.", (5, 7, 5, 5, 3, 5),
      [("Tracker", "follows tracks"), ("Beast friend", "animals don't attack first"), ("Loner", "worse in groups")],
      ["Bow", "Quiver", "Hood", "Snares"], ("hood", "bow", "quiver", None, L("Olive"), T("Gold"))),
    A("Prospector", "Zomboid", "Spent twenty years looking for the big seam. Found it once. Lost it in a card game.", (7, 4, 7, 5, 3, 6),
      [("Miner", "digs fast"), ("Tough", "shrugs off hits"), ("Gambler", "can't walk past a bet")],
      ["Spade", "Hard hat", "Lantern", "Ore sample"], ("hardhat", "spade", "pack", None, L("Leather"), T("Yellow"))),
    A("Farmer", "RimWorld", "Grew food in the ash when nothing else would. Patient. Very patient. Unnervingly patient.", (6, 4, 7, 5, 5, 4),
      [("Green thumb", "grows food anywhere"), ("Tough", "shrugs off hits"), ("Slow", "walks slower")],
      ["Hoe", "Straw hat", "Seeds", "Water can"], ("cowboy", "hoe", None, None, L("Olive"), T("Yellow"))),
    A("Mercenary", "RimWorld", "Fought on every side of every war. Loyal to whoever pays, until they don't.", (7, 6, 7, 4, 3, 4),
      [("Soldier", "better with rifles"), ("Tough", "shrugs off hits"), ("Wanted", "bounty hunters after you")],
      ["Rifle", "Helmet", "Armour vest", "Grenade"], ("helmet", "rifle", "pack", "vest", L("Olive"), T("Silver"))),
    A("Riot Cop", "Zomboid", "Held the line when the city fell. Still holding it, out of habit.", (7, 3, 9, 4, 4, 3),
      [("Shield wall", "blocks most hits"), ("Iron arm", "hits hard"), ("Slow", "walks slower")],
      ["Riot shield", "Helmet", "Baton", "Cuffs"], ("visor", "shield", None, "vest", L("Black"), T("Silver"))),
    A("Chemist", "Zomboid", "Makes medicine, fuel and things that go bang, sometimes on purpose.", (3, 5, 4, 9, 4, 5),
      [("Alchemy", "brews from scraps"), ("Steady hands", "heals better"), ("Migraines", "fumes hurt")],
      ["Flasks", "Lab coat", "Goggles", "Burner"], ("goggles", "flask", "pack", None, L("Bone"), T("Green"))),
    A("Beast Tamer", "Qud", "Walks with things that eat other people. Talks to them in clicks and whistles.", (5, 6, 6, 5, 6, 5),
      [("Beast friend", "animals don't attack first"), ("Whip hand", "controls a beast"), ("Outcast", "towns don't trust you")],
      ["Whip", "Fur cloak", "Bone charm", "Treats"], ("bandana", "whip", "cloak", "chain", L("Leather"), T("Pink"))),
    A("Oracle", "Qud", "Sees a few seconds ahead. Sometimes a few years. Never the bit that would help.", (2, 5, 4, 9, 7, 7),
      [("Foresight", "dodges what's coming"), ("Telepath", "senses minds"), ("Frail", "low health")],
      ["Orb", "Veil", "Crown of wire", "Incense"], ("crown", "orb", "cloak", "beads", L("Violet"), T("Cyan"))),
    A("Cyborg", "Qud", "More machine than meat now. The meat bit is getting quieter every year.", (8, 5, 8, 6, 2, 3),
      [("Plated", "armour built in"), ("Machine arm", "crushing grip"), ("Addict", "needs power cells")],
      ["Machine arm", "Power cell", "Visor", "Oil"], ("visor", "mecharm", "tank", None, L("Ash"), T("Cyan"))),
    A("Chimera", "Qud", "Grown in a vat out of several animals. Remembers being all of them.", (8, 7, 6, 3, 2, 5),
      [("Claws", "rips armour"), ("Night vision", "sees in the dark"), ("Outcast", "towns don't trust you")],
      ["Claws", "Mane", "Tail", "Collar"], (None, "claws", None, "mutation", (120, 70, 50), T("Green"))),
    # ── the drifting crew: old late-night-anime types, each with a twist ──
    A("Lounge Singer", "Drift", "Croons in bars with nobody left to drink in. The mic cable doubles as a garrotte.", (3, 7, 3, 6, 9, 5),
      [("Charm", "calms people and beasts"), ("Last call", "knows every back door"), ("Stage fright", "freezes when watched")],
      ["Mic on a long cable", "Evening dress", "Silk scarf", "Lipstick"], (None, "whip", None, "scarf", L("Crimson"), T("Gold"))),
    A("Bounty Clerk", "Drift", "Stamped other people's warrants for twelve years. Got bored of the paperwork, came to collect one.", (3, 6, 4, 8, 6, 5),
      [("Paper trail", "knows every bounty going"), ("Polite", "people tell them things"), ("Frail", "low health")],
      ["Derringer", "Rubber stamp", "Clipboard", "Tie"], ("cap", "derringer", None, "belt", L("Navy"), T("Silver"))),
    A("Noodle Mechanic", "Drift", "Ran a noodle cart with an engine stolen off a warship. Fixes ships between orders.", (6, 5, 6, 7, 5, 4),
      [("Cook", "makes better meals"), ("Builder", "builds and repairs fast"), ("Loud", "everything hears you")],
      ["Wrench", "Apron", "Ladle", "Warship part"], ("bandana", "wrench", "pack", None, L("Orange"), T("Yellow"))),
    A("Rock Wrangler", "Drift", "Lassoed asteroids off the belt for a living. Treats the whole sky like cattle.", (6, 7, 6, 4, 5, 5),
      [("Ace", "flies and repairs ships"), ("Lasso", "pulls things to you"), ("Wanted", "bounty hunters after you")],
      ["Lasso", "Spurs", "Wide-brim hat", "Flight goggles"], ("cowboy", "whip", None, "goggles", L("Leather"), T("Cyan"))),
    A("Lapsed Monk", "Drift", "Left the temple to race ships. Kept the beads, lost the faith, found it again in a crash.", (5, 8, 5, 6, 4, 4),
      [("Discipline", "doesn't panic"), ("Ace", "flies and repairs ships"), ("Night terrors", "sleeps badly")],
      ["Staff", "Prayer beads", "Racing jacket", "Incense"], ("bandana", "staff", "cloak", "beads", L("Ash"), T("Lilac"))),
    A("Undertaker", "Drift", "Buries what the bounty hunters leave behind. Plays slow jazz at the graveside, charges for encores.", (7, 4, 7, 5, 5, 4),
      [("Grave calm", "fear doesn't stick"), ("Iron gut", "eats anything"), ("Bad back", "carries less")],
      ["Spade", "Black duster", "Wide-brim hat", "Trumpet"], ("cowboy", "spade", "duster", None, L("Black"), T("Silver"))),
    # ── the severed: their heads come off, and that's the point ──
    A("Head Thrower", "Severed", "Their head comes off. It always comes back. Mostly. Nobody asks where it's been.", (6, 7, 5, 4, 3, 5),
      [("Boomerang", "head flies out and back"), ("Thick neck", "takes a hit"), ("Headless", "half blind while it's out")],
      ["Neck brace", "Rope", "Bandages"], (None, None, "pack", "scarf", L("Leather"), T("Gold")),
      dict(power="boomerang", glyph="首")),
    A("Ember Saint", "Severed", "Burned at a stake they didn't die on. Their head still smoulders, and spits.", (3, 5, 4, 8, 6, 4),
      [("Ember spit", "head spits fire"), ("Warm", "doesn't feel the cold"), ("Smouldering", "things see you in the dark")],
      ["Tinderbox", "Ash-grey robe", "Ash"], (None, "tome", "cloak", None, L("Crimson"), T("Yellow")),
      dict(power="fire", glyph="炎")),
    A("Frost Widow", "Severed", "Froze in the first winter with everyone she loved. Thawed. They didn't.", (3, 6, 5, 7, 4, 5),
      [("Frost spit", "head spits ice that holds"), ("Still", "creatures notice you later"), ("Cold hands", "heals slowly")],
      ["Veil", "Locket", "Frozen ring"], ("hood", None, "cloak", None, L("Navy"), T("White")),
      dict(power="frost", glyph="氷")),
    A("Storm Oracle", "Severed", "Was struck on the landing pad and heard everything at once. Their head still crackles.", (2, 6, 3, 9, 5, 6),
      [("Storm spit", "lightning that jumps"), ("Foresight", "sees trouble coming"), ("Migraines", "powers hurt to use")],
      ["Copper wire", "Rubber boots", "Charm"], ("circlet", "orb", None, None, L("Violet"), T("Yellow")),
      dict(power="storm", glyph="雷")),
    A("Rot Priest", "Severed", "Tended the sick until the sickness tended them. What their head spits doesn't stop.", (4, 4, 7, 6, 3, 5),
      [("Rot spit", "hurts and keeps hurting"), ("Iron gut", "eats anything"), ("Reek", "everything smells you")],
      ["Censer", "Stained robe", "Herbs"], ("hood", "staff", "cloak", None, L("Olive"), T("Green")),
      dict(power="rot", glyph="腐")),
    A("Gate Warden", "Severed", "Kept the colony gate for nine years. Their head still circles it, looking for the next one.", (7, 3, 8, 4, 4, 4),
      [("Orbit ward", "head circles and blocks"), ("Steadfast", "doesn't get knocked down"), ("Slow", "walks slower")],
      ["Riot shield", "Gate key", "Lamp"], ("helmet", "shield", None, "vest", L("Ash"), T("Silver")),
      dict(power="shield", glyph="盾")),
    A("Chain Monk", "Severed", "Took a vow, then a chain, then their own head to swing on it. The vow was about letting go.", (6, 8, 6, 5, 3, 3),
      [("Chain whirl", "head whirls wide"), ("Flow", "dodges more"), ("Outcast", "towns don't trust you")],
      ["Chain", "Prayer beads", "Wraps"], ("bandana", "whip", None, "beads", L("Orange"), T("Gold")),
      dict(power="spin", glyph="鎖")),
    A("Bell Ringer", "Severed", "Rang the warning bell the night they came. Never stopped. Their head is the bell now.", (5, 5, 6, 5, 5, 5),
      [("Scream", "head stuns all round you"), ("Loud", "everything hears you"), ("Deafened", "can't hear what's coming")],
      ["Bell rope", "Wax plugs", "Lantern"], ("cap", "fists", None, None, L("Bone"), T("Gold")),
      dict(power="nova", glyph="鐘")),
    A("Watcher", "Severed", "Was on the night shift when the planet first looked back. Now their eye goes where they can't.", (3, 7, 4, 8, 3, 6),
      [("Send it off", "see through your head"), ("Night owl", "sharper at night"), ("Paranoid", "hates crowds")],
      ["Binoculars", "Notebook", "Torch"], ("goggles", "knife", "pack", None, L("Teal"), T("Cyan")),
      dict(power="scout", glyph="眼")),
    A("Bone Twin", "Severed", "Was born with someone else's skull grown into theirs. Throws it. It throws itself back.", (5, 8, 5, 4, 4, 6),
      [("Boomerang", "head flies out and back"), ("Lucky", "finds more loot"), ("Outcast", "towns don't trust you")],
      ["Bone charm", "Twine", "Chalk"], (None, None, "duster", "chain", L("Black"), T("Lilac")),
      dict(power="boomerang", glyph="骨")),
]
for _a in ARCH:                                    # the older characters get heads that suit them (heads.ARCH_HEADS)
    if not _a.get("head") and _a["name"] in heads.ARCH_HEADS:
        _a["head"] = dict(zip(("power", "glyph"), heads.ARCH_HEADS[_a["name"]]))
CUSTOM = dict(name="Make your own", tag="You", blurb="Build them from nothing: body, colours, gear, stats and traits.")

MUTATIONS = ["Carapace (+ armour, - speed)", "Quills (hurts what hits you)", "Photosynthetic skin (+ heals in sun)",
             "Electrical generation (shocks)", "Night vision", "Regeneration", "Extra arms (+ carry, + grip)"]
FIRST = ["Kaito", "Rin", "Juno", "Vex", "Mara", "Toshi", "Calla", "Ezra", "Nori", "Dax", "Yuki", "Sable", "Ike",
         "Wren", "Hiro", "Lux", "Moss", "Saki", "Fen", "Rook", "Aiko", "Bastian", "Kenji", "Odile"]
LAST = ["Kurogane", "Vance", "Hollow", "Ashby", "Mizuno", "Crane", "Tetsu", "Graves", "Okabe", "Reyes", "Sorrow",
        "Black", "Hayashi", "Quill", "Starling", "Noda", "Marlowe", "Ibuki"]


def _font(path, size):
    try:
        return pygame.font.Font(path, size)
    except Exception:
        return pygame.font.Font(None, size)


_FONTS, _GL = {}, {}


def glyph(text, size, col):
    k = (text, size, col)
    if k not in _GL:
        if size not in _FONTS:
            _FONTS[size] = _font(CJK, size)
        _GL[k] = _FONTS[size].render(text, True, col)
    return _GL[k]


def draw_head(screen, cx, cy, size, ch, skin, tilt=0):
    """a head: its kanji in skin colour with a dark outline, so it reads over anything"""
    ol = glyph(ch, size, (12, 10, 14))
    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        blit_rot(screen, ol, cx + ox, cy + oy, tilt)
    blit_rot(screen, glyph(ch, size, tuple(skin)), cx, cy, tilt)


_TUT = {}
TUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "tutorials")


def tutorial_frames(power, fw=208, fh=130):
    """the recorded clip of a head power (tools/make_tutorials.py), as a list of frames; [] if it's missing"""
    if power not in _TUT:
        try:
            strip = pygame.image.load(os.path.join(TUT_DIR, power + ".jpg")).convert()
            _TUT[power] = [strip.subsurface((k * fw, 0, fw, fh)) for k in range(strip.get_width() // fw)]
        except (pygame.error, FileNotFoundError):
            _TUT[power] = []
    return _TUT[power]


def draw_tutorial(screen, power, accent, t, mid, tiny):
    """a looping clip of the power in the real game, with numbered steps beside it"""
    x0, y0, w, h = 340, 632, 512, 142
    pygame.draw.rect(screen, (18, 16, 26), (x0, y0, w, h), border_radius=8)
    pygame.draw.rect(screen, accent, (x0, y0, 3, h), border_radius=2)
    frames = tutorial_frames(power)
    if frames:
        f = frames[int(t * 15) % len(frames)]
        screen.blit(f, (x0 + 8, y0 + 6))
        pygame.draw.rect(screen, (60, 56, 70), (x0 + 8, y0 + 6, f.get_width(), f.get_height()), 1)
        if int(t * 2) % 2 == 0:                               # a little REC light, it's real footage
            pygame.draw.circle(screen, (220, 50, 50), (x0 + 20, y0 + 18), 4)
    P = heads.POWERS[power]
    tx = x0 + 228
    screen.blit(tiny.render("TUTORIAL", True, (130, 128, 140)), (tx, y0 + 6))
    screen.blit(mid.render(P["name"], True, accent), (tx, y0 + 20))
    y = y0 + 48
    for n, step in enumerate(heads.TUTORIAL[power], 1):
        lines = wrap(tiny, step, w - 236 - 22)
        screen.blit(tiny.render(f"{n}.", True, accent), (tx, y))
        for ln in lines:
            screen.blit(tiny.render(ln, True, (205, 202, 214)), (tx + 16, y))
            y += 16
        y += 3


def blit_rot(screen, surf, cx, cy, ang):
    if ang:
        surf = pygame.transform.rotate(surf, ang)
    screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))


def draw_char(screen, cx, cy, size, body, look, skin, mut=None, pose=None, head=None, clothes=None):
    """the body symbol, two-toned (skin above, clothes below), gear symbols placed on it, posed for a move.
    head = the head's kanji (drawn on top of the body), "" if it's off somewhere, None for the old headless look
    clothes = (jacket index, trousers index): jacket over the middle, trousers on the legs (None = own clothes)"""
    hat, weapon, back, extra, coat, trim = look
    jk = JACKETS[clothes[0]] if clothes and clothes[0] is not None else None
    tr = TROUSERS[clothes[1]] if clothes and clothes[1] is not None else None
    if jk:
        coat = jk["col"]
    p = pose or {}
    dx, dy, tilt = p.get("dx", 0), p.get("dy", 0), p.get("tilt", 0)
    dark = tuple(int(v * 0.55) for v in coat)
    g_coat = glyph(body, size, coat)
    w, h = g_coat.get_size()
    bx, by = cx + dx, cy + dy
    gs = int(size * 0.42)
    if back:
        b = glyph(BACKS[back][0], int(size * 0.62), dark)
        blit_rot(screen, b, bx - int(w * 0.32), by - int(h * 0.02), tilt * 0.6)
    two = pygame.Surface((w, h), pygame.SRCALPHA)               # two-toned body: skin over the top
    two.blit(g_coat, (0, 0))
    two.blit(glyph(body, size, skin), (0, 0), pygame.Rect(0, 0, w, int(h * 0.42)))

    def band(col, y0, y1):                                     # one horizontal slice of the body in another colour
        y0, y1 = int(h * y0), int(h * y1)
        two.blit(glyph(body, size, col), (0, y0), pygame.Rect(0, y0, w, y1 - y0))
    if tr:
        band(tr["col"], 0.68, 1.0)
        if tr["hem"]:
            band(tr["hem"], 0.93, 1.0)                         # cuffs / ankle ties
    if jk and jk["hem"]:
        band(jk["hem"], 0.63, 0.68)                            # the jacket's hem
    if extra and extra != "mutation":
        e = glyph(EXTRAS[extra][0], int(size * 0.3), trim)
        two.blit(e, (w // 2 - e.get_width() // 2, int(h * (0.42 if extra != "scarf" else 0.3))))
    if extra == "mutation":
        m = glyph("変", int(size * 0.3), trim)
        two.blit(m, (int(w * 0.02), int(h * 0.35)))
    sh = glyph(body, size, (0, 0, 0)).copy()
    sh.set_alpha(110)
    blit_rot(screen, sh, bx + max(2, size // 40), by + max(2, size // 40), tilt)
    blit_rot(screen, two, bx, by, tilt)
    if extra == "mutation" and mut and mut.startswith("Extra"):
        blit_rot(screen, glyph("手", int(size * 0.32), skin), bx - int(w * 0.62), by + int(h * 0.1), tilt)
    rad = math.radians(tilt)
    lift = 0
    if head:                                                   # the head: a kanji in skin, outlined, sat on top
        hs = int(size * 0.44)
        hxh, hyh = bx - int(math.sin(rad) * h * 0.5), by - int(h * 0.5)
        draw_head(screen, hxh, hyh, hs, head, skin, tilt)
        lift = int(hs * 0.62)
    if hat and head != "":                                     # (no head, no hat: it went with the head)
        hg = glyph(HATS[hat][0], gs, trim if hat in ("goggles", "circlet", "visor", "crown") else coat)
        hx, hy = bx + int(math.sin(rad) * h * 0.55) * -1, by - int(h * 0.52) - lift
        blit_rot(screen, hg, hx, hy, tilt)
    if weapon:
        wg = glyph(WEAPONS[weapon][0], gs, p.get("wcol", (205, 208, 215)))
        wx = bx + int(w * 0.5) + p.get("wdx", 0)
        wy = by + int(h * 0.05) + p.get("wdy", 0)
        blit_rot(screen, wg, wx, wy, p.get("wang", 0))


def pose_for(style, move, u, size):
    """keyframes for a move at progress u (0..1). Returns the pose, effects and when it hits."""
    s = size / 220
    if move not in MOVES.get(style, ()):                      # switched character mid-move: use their first move
        move = MOVES.get(style, MOVES["unarmed"])[0]
    ease = lambda x: 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, x)))
    p, fx = {}, []
    hit = None
    if style == "gun":
        n = {"Snap shot": 1, "Fan the hammer": 3, "Diving shot": 1}[move]
        if move == "Diving shot":
            p["dx"] = -60 * s * ease(u * 2) if u < 0.5 else -60 * s * (1 - ease((u - 0.5) * 2))
            p["dy"] = 30 * s * math.sin(math.pi * u)
            p["tilt"] = 25 * math.sin(math.pi * u)
        for k in range(n):
            t0 = 0.25 + k * 0.18
            if t0 < u < t0 + 0.1:
                p["wdx"] = -14 * s
                p["wang"] = 18
                fx.append(("flash", k))
            if abs(u - t0) < 0.04:
                hit = ("tracer", k)
    elif style in ("blade", "heavy", "staff", "whip"):
        if move in ("Slash", "Overhead smash", "Sweep", "Crack", "Lash"):
            wind = ease(u / 0.35) if u < 0.35 else 1 - ease((u - 0.35) / 0.2) * 2 if u < 0.55 else -1 + ease((u - 0.55) / 0.45)
            p["wang"] = 70 * wind
            p["wdy"] = -30 * s * wind
            p["dx"] = 40 * s * math.sin(math.pi * max(0, min(1, (u - 0.3) / 0.5)))
            p["tilt"] = -8 * wind
            if abs(u - 0.45) < 0.03:
                hit = ("slash", 0)
            if 0.38 < u < 0.55:
                fx.append(("arc", 0))
        elif move in ("Thrust", "Shoulder charge", "Vault kick", "Snare"):
            f = math.sin(math.pi * max(0, min(1, (u - 0.2) / 0.5)))
            p["dx"] = 90 * s * f
            p["wdx"] = 40 * s * f
            p["wang"] = -80 if move == "Thrust" else 0
            p["tilt"] = -15 * f if move != "Vault kick" else -40 * f
            p["dy"] = -40 * s * f if move == "Vault kick" else 0
            if abs(u - 0.45) < 0.03:
                hit = ("thrust", 0)
        else:   # spins
            p["tilt"] = 360 * ease((u - 0.2) / 0.6)
            p["wang"] = 360 * ease((u - 0.2) / 0.6)
            p["dx"] = 30 * s * math.sin(math.pi * u)
            if abs(u - 0.6) < 0.03:
                hit = ("slash", 0)
            if 0.3 < u < 0.8:
                fx.append(("arc", 1))
    elif style == "unarmed":
        if move == "Jab-cross":
            for k, t0 in enumerate((0.25, 0.5)):
                f = math.sin(math.pi * max(0, min(1, (u - t0) / 0.18)))
                if f > 0:
                    p["dx"] = 50 * s * f
                    p["wdx"] = 40 * s * f
                if abs(u - t0 - 0.09) < 0.03:
                    hit = ("punch", k)
        elif move == "Roundhouse":
            f = math.sin(math.pi * max(0, min(1, (u - 0.2) / 0.5)))
            p["tilt"] = -55 * f
            p["dx"] = 60 * s * f
            p["dy"] = -15 * s * f
            if abs(u - 0.45) < 0.03:
                hit = ("punch", 0)
        else:
            f = math.sin(math.pi * max(0, min(1, (u - 0.25) / 0.45)))
            p["dy"] = -70 * s * f
            p["dx"] = 40 * s * f
            p["wdy"] = -50 * s * f
            p["tilt"] = 10 * f
            if abs(u - 0.45) < 0.03:
                hit = ("punch", 0)
    elif style == "magic":
        if move == "Levitate":
            p["dy"] = -50 * s * math.sin(math.pi * u)
        p["wdy"] = -20 * s * math.sin(math.pi * u)
        fx.append(("glow", u))
        if abs(u - 0.55) < 0.03:
            hit = ("bolt", 0) if move != "Nova" else ("nova", 0)
    elif style == "bow":
        n = {"Loose": 1, "Double shot": 2, "Rain": 3}[move]
        p["wdx"] = -10 * s * math.sin(math.pi * u)
        for k in range(n):
            if abs(u - (0.35 + k * 0.15)) < 0.03:
                hit = ("arrow", k)
    elif style == "shield":
        f = math.sin(math.pi * max(0, min(1, (u - 0.2) / 0.5)))
        if move == "Block":
            p["wdx"] = 10 * s * f
            p["dx"] = -10 * s * f
            if abs(u - 0.45) < 0.03:
                hit = ("block", 0)
        else:
            p["dx"] = (120 if move == "Charge" else 60) * s * f
            p["wdx"] = 30 * s * f
            if abs(u - 0.45) < 0.03:
                hit = ("bash", 0)
    elif style == "throw":
        f = math.sin(math.pi * max(0, min(1, (u - 0.15) / 0.3)))
        p["wdy"] = -50 * s * f
        p["wang"] = 120 * f
        if abs(u - 0.6) < 0.03:
            hit = ("splash", 0)
    return p, fx, hit


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
    """the character creation screen. Returns the character on Enter, None on Esc (outside the builder)."""
    pygame.display.set_caption("New drifter")
    big, mid, small, tiny = _font(UIB, 32), _font(UIB, 19), _font(UI, 15), _font(UI, 13)
    cjk = _font(CJK, 40)
    rn = lambda: f"{random.choice(FIRST)} {random.choice(LAST)}"
    st = dict(arch=0, body=0, skin=1, name=rn(), mut=random.choice(MUTATIONS), jacket=None, trousers=None, weapon=None)
    WLIST = [None] + list(OLD_WEAPONS)                         # the weapon picker: their own, then the old weapons
    picking = None                                            # row in the weapon picker while it's open
    # the builder's own character
    cu = dict(body=15, skin=1, coat=0, trim=0, hat=1, weapon=1, back=1, extra=0,
              stats=[5, 5, 5, 5, 5, 5], good=[0, 1], bad=0)
    hats, weps, backs, extras = list(HATS), list(WEAPONS), list(BACKS), list(EXTRAS)
    editing, row = False, 0
    fight = None                                              # (move name, start time)
    headfx = None                                             # start time of a head demo
    msg, msg_t, hits = "", 0, []
    last_input = time.monotonic()
    clock = pygame.time.Clock()
    t0 = time.monotonic() - ((setup or {}).get("t") or 0)      # (recordings can start part-way through)
    if setup:
        st.update(setup)
    items = [CUSTOM] + ARCH
    ROWS = ["Body", "Skin", "Clothes", "Trim", "Head", "Hand", "Back", "Extra"] + list(STATS) + ["Good trait 1", "Good trait 2", "Flaw", "Name"]

    def current():
        """(display archetype dict, look tuple, body symbol, skin rgb)"""
        if st["arch"] == 0:
            look = (hats[cu["hat"]], weps[cu["weapon"]], backs[cu["back"]], extras[cu["extra"]],
                    COLOURS[cu["coat"]][1], TRIMS[cu["trim"]][1])
            a = dict(CUSTOM, stats=tuple(cu["stats"]),
                     traits=[(GOOD[cu["good"][0]][0], "+ " + GOOD[cu["good"][0]][1]), (GOOD[cu["good"][1]][0], "+ " + GOOD[cu["good"][1]][1]),
                             (BAD[cu["bad"]][0], "- " + BAD[cu["bad"]][1])],
                     kit=[n for n in (HATS[look[0]][1], WEAPONS[look[1]][1], BACKS[look[2]][1], EXTRAS[look[3]][1]) if n != "—"],
                     look=look)
            return a, pick(look), BODIES[cu["body"]][0], SKINS[cu["skin"]][1]
        a = items[st["arch"]]
        return a, pick(a["look"]), BODIES[st["body"]][0], SKINS[st["skin"]][1]

    def pick(look):
        """the look with the weapon from the picker in their hand"""
        return (look[0], st["weapon"]) + tuple(look[2:]) if st["weapon"] else look

    def wear(key, n):                                         # J / T: next jacket / trousers (then back to their own)
        v = st[key]
        st[key] = 0 if v is None else (None if v + 1 >= n else v + 1)

    def outfit_key(k):
        """J, T and X work everywhere on this screen. True if the key was one of them"""
        nonlocal picking
        if k == pygame.K_j:
            wear("jacket", len(JACKETS))
        elif k == pygame.K_t:
            wear("trousers", len(TROUSERS))
        elif k == pygame.K_x:
            picking = WLIST.index(st["weapon"])
        else:
            return False
        return True

    def change(r, d):
        if r < 8:
            key, n = [("body", 20), ("skin", len(SKINS)), ("coat", len(COLOURS)), ("trim", len(TRIMS)), ("hat", len(hats)),
                      ("weapon", len(weps)), ("back", len(backs)), ("extra", len(extras))][r]
            cu[key] = (cu[key] + d) % n
        elif r < 14:
            k = r - 8
            spent = sum(cu["stats"])
            if d > 0 and spent < 32 and cu["stats"][k] < 10:
                cu["stats"][k] += 1
            elif d < 0 and cu["stats"][k] > 1:
                cu["stats"][k] -= 1
        elif r < 16:
            i = r - 14
            v = cu["good"][i]
            while True:
                v = (v + d) % len(GOOD)
                if v != cu["good"][1 - i]:
                    break
            cu["good"][i] = v
        elif r == 16:
            cu["bad"] = (cu["bad"] + d) % len(BAD)

    while True:
        now = time.monotonic()
        a, look, body, skin = current()
        style = STYLE.get(look[1], "unarmed")
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
            if e.type != pygame.KEYDOWN:
                continue
            last_input = now
            k = e.key
            if picking is not None:                            # the weapon picker has the keys
                L = "abcdefghijklmnoprstuvwxyz"[:len(WLIST)]
                if k in (pygame.K_ESCAPE, pygame.K_q, pygame.K_x):
                    picking = None
                elif k in (pygame.K_UP, pygame.K_w):
                    picking = (picking - 1) % len(WLIST)
                elif k in (pygame.K_DOWN, pygame.K_s):
                    picking = (picking + 1) % len(WLIST)
                elif k in (pygame.K_RETURN, pygame.K_KP_ENTER) or (e.unicode and e.unicode in L):
                    if k not in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        picking = L.index(e.unicode)
                    st["weapon"], picking = WLIST[picking], None
                    fight = None
                continue
            if editing:
                if k in (pygame.K_ESCAPE, pygame.K_TAB) or (k == pygame.K_q and ROWS[row] != "Name"):
                    editing = False
                elif ROWS[row] != "Name" and outfit_key(k):
                    pass
                elif k in (pygame.K_UP,):
                    row = (row - 1) % len(ROWS)
                elif k in (pygame.K_DOWN,):
                    row = (row + 1) % len(ROWS)
                elif k in (pygame.K_LEFT, pygame.K_RIGHT) and ROWS[row] != "Name":
                    change(row, 1 if k == pygame.K_RIGHT else -1)
                elif ROWS[row] == "Name":
                    if k == pygame.K_BACKSPACE:
                        st["name"] = st["name"][:-1]
                    elif e.unicode and e.unicode.isprintable() and len(st["name"]) < 24:
                        st["name"] += e.unicode
                elif k == pygame.K_f:
                    fight = (MOVES[style][int(now) % 3], now)
                continue
            if k == pygame.K_ESCAPE:
                return
            if k in (pygame.K_UP, pygame.K_w):
                st["arch"] = (st["arch"] - 1) % len(items)
            elif k in (pygame.K_DOWN, pygame.K_s):
                st["arch"] = (st["arch"] + 1) % len(items)
            elif k in (pygame.K_LEFT, pygame.K_a):
                if st["arch"] == 0:
                    cu["body"] = (cu["body"] - 1) % 20
                else:
                    st["body"] = (st["body"] - 1) % len(BODIES)
            elif k in (pygame.K_RIGHT, pygame.K_d):
                if st["arch"] == 0:
                    cu["body"] = (cu["body"] + 1) % 20
                else:
                    st["body"] = (st["body"] + 1) % len(BODIES)
            elif k == pygame.K_TAB and st["arch"] == 0:
                editing, row = True, 0
            elif k == pygame.K_c:
                if st["arch"] == 0:
                    cu["skin"] = (cu["skin"] + 1) % len(SKINS)
                else:
                    st["skin"] = (st["skin"] + 1) % len(SKINS)
            elif outfit_key(k):
                fight = None
            elif k == pygame.K_n:
                st["name"] = rn()
            elif k == pygame.K_h:
                headfx = now
            elif k == pygame.K_f:
                mv = MOVES[style]
                prev = fight[0] if fight else None
                fight = (mv[(mv.index(prev) + 1) % 3] if prev in mv else mv[0], now)
            elif k == pygame.K_r:
                st.update(arch=random.randrange(1, len(items)), body=random.randrange(len(BODIES)),
                          skin=random.randrange(len(SKINS)), name=rn(), mut=random.choice(MUTATIONS))
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                a, look, body, skin = current()                # (anything changed earlier this frame counts)
                d = dict(name=st["name"], archetype=a["name"], body=body, skin_rgb=skin, look=list(look[:4]),
                         head=a.get("head") or heads.default_head(look),
                         coat=look[4], trim=look[5], stats=dict(zip(STATS, a["stats"])),
                         traits=[t for t, _ in a["traits"]], kit=a["kit"],
                         mutation=st["mut"] if look[3] == "mutation" else None,
                         jacket=st["jacket"], trousers=st["trousers"],
                         weapon_item=look[1] if look[1] in OLD_WEAPONS else None)
                os.makedirs(root, exist_ok=True)
                with open(os.path.join(root, "character.json"), "w") as f:
                    json.dump(d, f, indent=1, ensure_ascii=False)
                return d                                          # into the world
        if fight is None and headfx is None and now - last_input > 2.5 and int(now * 10) % 40 == 0:   # shows off when idle
            if random.random() < 0.5:
                fight = (random.choice(MOVES[style]), now)
            else:
                headfx = now
        hd = a.get("head") or heads.default_head(look)
        sw, sh = screen.get_size()
        t = now - t0
        screen.fill((10, 9, 14))
        for i in range(70):
            x = (i * 157 + int(t * (3 + i % 5))) % sw
            y = (i * 97) % sh
            c = 60 + (i * 37) % 120
            screen.fill((c, c, c + 20), (x, y, 2, 2))
        screen.blit(big.render("NEW DRIFTER", True, (240, 220, 160)), (30, 14))
        screen.blit(small.render("Stranded on a dead world. Pick who you were before the crash, or make your own.", True, (150, 150, 165)), (32, 54))
        # list (scrolls)
        top_i = max(0, min(len(items) - 13, st["arch"] - 6))
        for j in range(13):
            i = top_i + j
            if i >= len(items):
                break
            ar = items[i]
            y = 86 + j * 47
            on = i == st["arch"]
            accent = (240, 220, 160) if i == 0 else ar["look"][5]
            pygame.draw.rect(screen, (34, 30, 46) if on else (18, 16, 26), (24, y, 300, 42), border_radius=8)
            if on:
                pygame.draw.rect(screen, accent, (24, y, 4, 42), border_radius=2)
            screen.blit(mid.render(ar["name"], True, (240, 235, 220) if on else (170, 165, 180)), (38, y + 1))
            screen.blit(tiny.render(ar["tag"], True, accent if on else (110, 110, 125)), (40, y + 23))
        screen.blit(tiny.render(f"{st['arch'] + 1} / {len(items)}", True, (120, 120, 135)), (260, 700))
        # the fight: character vs dummy
        cx, cy = 520, 380
        pose, fxs, hit = {}, [], None
        if fight:
            u = (now - fight[1]) / 1.4
            if u >= 1:
                fight = None
            else:
                pose, fxs, hit = pose_for(style, fight[0], u, 200)
                if hit and (not hits or hits[-1][2] != (fight[1], hit)):
                    hits.append((now, hit[0], (fight[1], hit)))
        if not fight:
            pose = {"dy": math.sin(t * 2.2) * 3}
        pygame.draw.ellipse(screen, (20, 26, 18), (cx - 180, 500, 470, 50))
        dummy_x = cx + 230
        shake = 0
        for (ht, kind, _) in hits[-4:]:
            age = now - ht
            if age < 0.35:
                shake = 10 * math.sin(age * 60) * (1 - age / 0.35)
        dummy = glyph("木", 150, (120, 100, 70))
        blit_rot(screen, dummy, dummy_x + int(shake), cy + 20, shake * 0.8)
        screen.blit(tiny.render("training dummy", True, (110, 110, 120)), (dummy_x - 40, cy + 110))
        mut = st["mut"] if look[3] == "mutation" else None
        # the head demo: where the head is, and what it does to the dummy
        hu = (now - headfx) / 1.6 if headfx else None
        if hu is not None and hu >= 1:
            headfx, hu = None, None
        pw = hd["power"]
        away = hu is not None and (pw in ("boomerang", "shield", "spin", "scout") or hu < 0.75)   # it always comes off
        draw_char(screen, cx, cy, 200, body, look, skin, mut, pose, head="" if away else hd["glyph"],
                  clothes=(st["jacket"], st["trousers"]))
        if hu is not None:
            hx0, hy0 = cx + int(pose.get("dx", 0)), cy - 125
            P = heads.POWERS[pw]
            if pw == "boomerang":                              # out to the dummy and back, spinning
                k = math.sin(math.pi * hu)
                hx, hy = hx0 + (dummy_x - hx0) * k, hy0 - 90 * math.sin(2 * math.pi * hu)
                draw_head(screen, int(hx), int(hy), 88, hd["glyph"], skin, hu * 1440)
                if abs(hu - 0.5) < 0.03 and (not hits or hits[-1][2] != (headfx, "bm")):
                    hits.append((now, "head", (headfx, "bm")))
            elif pw in ("fire", "frost", "storm", "rot"):      # the head pops off, spits at the dummy, flies back on
                out_ = min(1.0, hu / 0.12) if hu < 0.5 else max(0.0, 1 - (hu - 0.5) / 0.25)
                shx, shy = hx0 + 100 * out_, hy0 - 30 * math.sin(out_ * math.pi / 2)
                if hu < 0.75:
                    draw_head(screen, int(shx), int(shy), 88, hd["glyph"], skin, -12 * out_)
                v = min(1.0, max(0.0, (hu - 0.12) / 0.33))
                if 0.12 <= hu < 0.45:
                    px_ = hx0 + 100 + (dummy_x - hx0 - 100) * v
                    blit_rot(screen, glyph(P["glyph"], 70, P["col"]), int(px_), int(shy + 70 * v + 60 * v * v), hu * 400)
                elif hu >= 0.45 and (not hits or hits[-1][2] != (headfx, "spit")):
                    hits.append((now, "head", (headfx, "spit")))
                if hu >= 0.45:
                    a_ = 1 - (hu - 0.45) / 0.55
                    if pw == "storm":
                        for j in range(3):
                            pts = [(dummy_x + 30 * j, cy - 40 + 20 * j)] + [(dummy_x + 60 + 40 * q + random.randint(-15, 15),
                                   cy - 60 + 30 * j + random.randint(-20, 20)) for q in range(3)]
                            pygame.draw.lines(screen, P["col"], False, pts, 3)
                    else:
                        for q in range(10):
                            ang = q * 0.63 + hu * 3
                            r_ = 30 + 90 * (1 - a_)
                            pygame.draw.circle(screen, P["col"], (dummy_x + int(math.cos(ang) * r_), cy + int(math.sin(ang) * r_ * 0.6)),
                                               max(2, int(9 * a_)))
            elif pw in ("shield", "spin"):                     # round and round you
                rad_ = 150 if pw == "shield" else 235
                ang = hu * (4 if pw == "shield" else 9) * math.pi
                hx, hy = cx + math.cos(ang) * rad_, cy - 20 + math.sin(ang) * rad_ * 0.55
                if pw == "spin":
                    pygame.draw.line(screen, (150, 150, 160), (cx, cy - 60), (int(hx), int(hy)), 3)
                draw_head(screen, int(hx), int(hy), 88, hd["glyph"], skin, ang * 57)
                if math.hypot(hx - dummy_x, hy - cy) < 80 and (not hits or now - hits[-1][0] > 0.25):
                    hits.append((now, "head", (headfx, round(hu, 2))))
            elif pw == "nova":                                 # it lifts off your shoulders and screams
                lift_ = min(1.0, hu / 0.1) if hu < 0.6 else max(0.0, 1 - (hu - 0.6) / 0.15)
                if hu < 0.75:
                    draw_head(screen, hx0 + random.randint(-4, 4), int(hy0 - 90 * lift_) + random.randint(-4, 4), 88,
                              hd["glyph"], skin, 0)
                screen.set_clip(pygame.Rect(332, 84, 524, 540))     # the rings stay in the middle
                for q in range(3):
                    r_ = int(((hu * 1.6 + q * 0.18) % 1.0) * 300)
                    pygame.draw.circle(screen, look[5], (hx0, int(hy0 - 90 * lift_)), r_, 3)
                screen.set_clip(None)
                if abs(hu - 0.3) < 0.03 and (not hits or hits[-1][2] != (headfx, "nova")):
                    hits.append((now, "head", (headfx, "nova")))
            elif pw == "scout":                                # Red eye: lifts off, lasers every which way
                lift_ = min(1.0, hu / 0.12) if hu < 0.85 else max(0.0, 1 - (hu - 0.85) / 0.15)
                hx, hy = hx0 + random.randint(-2, 2), int(hy0 - 70 * lift_)
                pygame.draw.circle(screen, (90, 10, 10), (hx, hy), 58)
                if 0.12 < hu < 0.85:
                    rnd = random.Random(int(now * 9))              # a new burst every ~0.1 s, some at the dummy
                    for q in range(rnd.choice((0, 1, 2, 3))):
                        ang = math.atan2(cy - hy, dummy_x - hx) if rnd.random() < 0.5 else rnd.uniform(0, 2 * math.pi)
                        ex, ey = hx + math.cos(ang) * 600, hy + math.sin(ang) * 600
                        pygame.draw.line(screen, (150, 10, 10), (hx, hy), (ex, ey), 9)
                        pygame.draw.line(screen, (255, 40, 40), (hx, hy), (ex, ey), 5)
                        pygame.draw.line(screen, (255, 210, 200), (hx, hy), (ex, ey), 2)
                        if abs(ang - math.atan2(cy - hy, dummy_x - hx)) < 0.05 and (not hits or now - hits[-1][0] > 0.2):
                            hits.append((now, "head", (headfx, round(hu, 2))))
                draw_head(screen, hx, hy, 88, hd["glyph"], skin, 0)
            nm_ = mid.render(P["name"], True, look[5])
            screen.blit(nm_, (cx + 30 - nm_.get_width() // 2, 150))
        # effects
        for (kind, k) in fxs:
            if kind == "flash":
                pygame.draw.circle(screen, (255, 230, 140), (cx + 175 + int(pose.get("dx", 0)), cy + 5), 12)
            elif kind == "arc":
                r = pygame.Rect(cx + 20 + int(pose.get("dx", 0)), cy - 110, 200, 220)
                pygame.draw.arc(screen, (230, 230, 240), r, -1.2, 1.2, 4)
            elif kind == "glow":
                rr = int(30 + 40 * math.sin(math.pi * k))
                pygame.draw.circle(screen, look[5], (cx + 120, cy + int(pose.get("dy", 0))), rr, 3)
        for (ht, kind, _) in hits[-6:]:
            age = now - ht
            if age > 0.6:
                continue
            if kind in ("tracer", "arrow"):
                x0 = cx + 180 + int(age * 900)
                if x0 < dummy_x:
                    pygame.draw.line(screen, (255, 220, 140) if kind == "tracer" else (200, 170, 120), (x0, cy + 5), (x0 + 30, cy + 5), 3)
            if kind == "bolt" and age < 0.3:
                pygame.draw.line(screen, look[5], (cx + 140, cy), (dummy_x, cy + 10), 5)
            if kind == "nova" and age < 0.5:
                pygame.draw.circle(screen, look[5], (cx, cy), int(age * 600), 4)
            if kind == "splash" and age < 0.5:
                for q in range(8):
                    ang = q * 0.785
                    pygame.draw.circle(screen, (120, 220, 120), (dummy_x + int(math.cos(ang) * age * 120), cy + int(math.sin(ang) * age * 80)), 6)
            if age < 0.6 and kind not in ("block",):                  # damage numbers
                num = mid.render(str(3 + (hash(ht) % 9)), True, (255, 120, 110))
                screen.blit(num, (dummy_x + 10, cy - 70 - int(age * 80)))
            if kind == "block" and age < 0.4:
                screen.blit(mid.render("BLOCK", True, (180, 220, 255)), (cx + 120, cy - 90))
        if fight:
            mv = mid.render(fight[0], True, look[5])
            screen.blit(mv, (cx + 30 - mv.get_width() // 2, 150))
        nm = big.render(st["name"] + ("_" if editing and ROWS[row] == "Name" and int(now * 2) % 2 else ""), True, (245, 240, 230))
        screen.blit(nm, (cx + 60 - nm.get_width() // 2, 92))
        bi = cu["body"] if st["arch"] == 0 else st["body"]
        gl = cjk.render(BODIES[bi][0], True, look[5])
        screen.blit(gl, (cx - 140, 572))
        screen.blit(small.render(f"Body {bi + 1}/20 — {BODIES[bi][1]}  ·  Fights with: {WEAPONS[look[1]][1]}  (X weapon)",
                                 True, (180, 180, 190)), (cx - 86, 582))
        jn = JACKETS[st["jacket"]]["name"] if st["jacket"] is not None else "own jacket"
        tn = TROUSERS[st["trousers"]]["name"] if st["trousers"] is not None else "own trousers"
        screen.blit(small.render(f"Wearing: {jn}, {tn}  (J jacket, T trousers)", True, (150, 150, 165)), (cx - 86, 604))
        draw_tutorial(screen, hd["power"], look[5], t, mid, tiny)          # how their head works, in a real game
        # right panel
        rx = 880
        pygame.draw.rect(screen, (18, 16, 26), (rx - 16, 86, 400, 650), border_radius=10)
        if st["arch"] == 0:
            screen.blit(mid.render("Make your own", True, (240, 220, 160)), (rx, 96))
            hint = "Tab: start editing" if not editing else "Up/Down row · Left/Right change · type the name · Tab done"
            screen.blit(tiny.render(hint, True, (150, 150, 165)), (rx, 120))
            vals = [BODIES[cu["body"]][1], SKINS[cu["skin"]][0], COLOURS[cu["coat"]][0],
                    TRIMS[cu["trim"]][0], HATS[look[0]][1], WEAPONS[look[1]][1], BACKS[look[2]][1], EXTRAS[look[3]][1]]
            vals += [str(v) for v in cu["stats"]]
            vals += [GOOD[cu["good"][0]][0], GOOD[cu["good"][1]][0], BAD[cu["bad"]][0], st["name"]]
            for j, (lab, v) in enumerate(zip(ROWS, vals)):
                y = 146 + j * 27
                on = editing and j == row
                if on:
                    pygame.draw.rect(screen, (40, 36, 56), (rx - 8, y - 2, 380, 25), border_radius=5)
                screen.blit(small.render(lab, True, (240, 220, 160) if on else (150, 150, 165)), (rx, y))
                if 8 <= j < 14:
                    sv = cu["stats"][j - 8]
                    pygame.draw.rect(screen, (40, 36, 52), (rx + 120, y + 6, 160, 9), border_radius=4)
                    pygame.draw.rect(screen, look[5], (rx + 120, y + 6, 16 * sv, 9), border_radius=4)
                    screen.blit(tiny.render(str(sv), True, (210, 210, 220)), (rx + 290, y + 1))
                else:
                    col = (130, 220, 140) if lab.startswith("Good") else (235, 110, 110) if lab == "Flaw" else (225, 222, 232)
                    screen.blit(small.render(("‹ " if on else "") + v + (" ›" if on else ""), True, col), (rx + 120, y))
            left = 32 - sum(cu["stats"])
            screen.blit(small.render(f"Stat points left: {left}", True, (240, 220, 160) if left else (150, 150, 165)), (rx, 146 + len(ROWS) * 27))
        else:
            screen.blit(mid.render(a["name"], True, look[5]), (rx, 96))
            for j, ln in enumerate(wrap(small, a["blurb"], 360)):
                screen.blit(small.render(ln, True, (200, 198, 210)), (rx, 124 + j * 19))
            y = 190
            for lab, v in zip(STATS, a["stats"]):
                screen.blit(small.render(lab, True, (170, 170, 180)), (rx, y))
                pygame.draw.rect(screen, (40, 36, 52), (rx + 50, y + 5, 200, 10), border_radius=4)
                pygame.draw.rect(screen, look[5], (rx + 50, y + 5, 20 * v, 10), border_radius=4)
                screen.blit(tiny.render(str(v), True, (200, 200, 210)), (rx + 258, y + 1))
                y += 23
            y += 8
            screen.blit(mid.render("Traits", True, (230, 225, 210)), (rx, y)); y += 26
            traits = list(a["traits"])
            if look[3] == "mutation":
                traits[0] = ("Mutation", "+ " + st["mut"])
            for tname, td in traits:
                good = td.startswith("+")
                screen.blit(small.render(tname, True, (130, 220, 140) if good else (235, 110, 110)), (rx, y))
                screen.blit(tiny.render(td[2:], True, (170, 170, 180)), (rx + 120, y + 2))
                y += 21
            y += 8
            screen.blit(mid.render("Equipped", True, (230, 225, 210)), (rx, y)); y += 26
            for sl, it in (("Head", HATS[look[0]][1]), ("Hand", WEAPONS[look[1]][1]), ("Back", BACKS[look[2]][1]), ("Extra", EXTRAS[look[3]][1])):
                screen.blit(small.render(sl, True, (150, 150, 165)), (rx, y))
                screen.blit(small.render(it, True, (220, 218, 230)), (rx + 70, y))
                y += 20
            y += 8
            screen.blit(mid.render("Carrying", True, (230, 225, 210)), (rx, y)); y += 26
            for j, it in enumerate(a["kit"]):
                screen.blit(small.render("· " + it, True, (200, 198, 210)), (rx + (j % 2) * 185, y + (j // 2) * 20))
            y += ((len(a["kit"]) + 1) // 2) * 20 + 10
            screen.blit(mid.render("Moves", True, (230, 225, 210)), (rx, y)); y += 26
            screen.blit(small.render("  ·  ".join(MOVES[style]), True, look[5]), (rx, y)); y += 28
            P = heads.POWERS[hd["power"]]
            screen.blit(mid.render("Head", True, (230, 225, 210)), (rx, y))
            screen.blit(glyph(hd["glyph"], 22, look[5]), (rx + 60, y))
            screen.blit(small.render(P["name"] + "   (H to try it)", True, look[5]), (rx + 110, y + 3)); y += 26
            for ln in wrap(tiny, P["what"], 360):
                screen.blit(tiny.render(ln, True, (190, 188, 200)), (rx, y)); y += 17
        if picking is not None:                                # the weapon picker, over everything
            px0, py0, pw0 = 360, 96, 470
            ph0 = 70 + len(WLIST) * 25 + 30
            pygame.draw.rect(screen, (14, 12, 20), (px0, py0, pw0, ph0), border_radius=10)
            pygame.draw.rect(screen, look[5], (px0, py0, pw0, ph0), 2, border_radius=10)
            screen.blit(mid.render("Choose a weapon", True, (240, 220, 160)), (px0 + 18, py0 + 12))
            screen.blit(tiny.render("Old weapons of Japan and China. Letter or Enter picks · Q / Esc closes", True,
                                    (150, 150, 165)), (px0 + 18, py0 + 40))
            own = a["look"][1]
            for j, wk in enumerate(WLIST):
                y = py0 + 68 + j * 25
                if j == picking:
                    pygame.draw.rect(screen, (40, 36, 56), (px0 + 10, y - 2, pw0 - 20, 24), border_radius=5)
                on = wk == st["weapon"]
                L = "abcdefghijklmnoprstuvwxyz"[j]
                screen.blit(small.render(L, True, (150, 150, 165)), (px0 + 20, y))
                if wk is None:
                    nm_ = f"Their own: {WEAPONS[own][1]}" if own else "Their own: bare hands"
                    screen.blit(small.render(nm_, True, (240, 235, 220) if on else (190, 188, 200)), (px0 + 76, y))
                    continue
                g_, n_, where, sty = OLD_WEAPONS[wk]
                screen.blit(glyph(g_, 20, look[5] if on else (205, 208, 215)), (px0 + 44, y - 2))
                screen.blit(small.render(n_, True, (240, 235, 220) if on else (190, 188, 200)), (px0 + 76, y))
                screen.blit(tiny.render(f"{where} · fights like a {sty}", True, (120, 120, 135)), (px0 + 250, y + 2))
        keys = "Up/Down who you were   Left/Right body   C skin   N name   R random   F fight   H head   Tab build   Enter begin   Esc quit"
        screen.blit(tiny.render(keys, True, (130, 130, 145)), (30, sh - 24))
        if msg and now - msg_t < 6:
            m = small.render(msg, True, (240, 220, 160))
            screen.blit(m, (sw // 2 - m.get_width() // 2, sh - 50))
        pygame.display.flip()
        if shot:
            if setup and setup.get("head_u") is not None:
                headfx = now - setup["head_u"] * 1.6
                setup = None
                continue
            if setup and setup.get("fight"):
                fight = (setup["fight"], now - setup.get("u", 0.45) * 1.4)
                setup = None
                continue
            pygame.image.save(screen, shot)
            return
        clock.tick(30)


def run_phone(screen, root):
    """the character screen on a phone: upright, everything on big buttons.
    Returns the new character, "continue" (carry on the last game), or None (back out)."""
    import phone
    big, mid, small, tiny = _font(UIB, 24), _font(UIB, 16), _font(UI, 13), _font(UI, 11)
    rn = lambda: f"{random.choice(FIRST)} {random.choice(LAST)}"
    st = dict(arch=random.randrange(len(ARCH)), body=random.randrange(len(BODIES)), skin=random.randrange(len(SKINS)),
              name=rn(), mut=random.choice(MUTATIONS), jacket=None, trousers=None, weapon=None)
    can_go_on = all(os.path.exists(os.path.join(root, f)) for f in ("current.json", "character.json"))
    WLIST = [None] + list(OLD_WEAPONS)
    picking, fight, headfx = False, None, None
    clock = pygame.time.Clock()
    sw, sh = screen.get_size()

    def now_look():
        a = ARCH[st["arch"]]
        look = a["look"]
        if st["weapon"]:
            look = (look[0], st["weapon"]) + tuple(look[2:])
        return a, look

    def wear(key, n):
        v = st[key]
        st[key] = 0 if v is None else (None if v + 1 >= n else v + 1)

    def spar():
        nonlocal fight
        mv = MOVES[STYLE.get(now_look()[1][1], "unarmed")]
        prev = fight[0] if fight else None
        fight = (mv[(mv.index(prev) + 1) % 3] if prev in mv else mv[0], time.monotonic())

    def begin():
        a, look = now_look()
        d = dict(name=st["name"], archetype=a["name"], body=BODIES[st["body"]][0], skin_rgb=SKINS[st["skin"]][1],
                 look=list(look[:4]), head=a.get("head") or heads.default_head(look), coat=look[4], trim=look[5],
                 stats=dict(zip(STATS, a["stats"])), traits=[t for t, _ in a["traits"]], kit=a["kit"],
                 mutation=st["mut"] if look[3] == "mutation" else None, jacket=st["jacket"], trousers=st["trousers"],
                 weapon_item=look[1] if look[1] in OLD_WEAPONS else None)
        os.makedirs(root, exist_ok=True)
        with open(os.path.join(root, "character.json"), "w") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
        return d

    def step(key, n, d):
        st[key] = (st[key] + d) % n

    def buttons():
        """[(label, rect, what it does)] for this frame"""
        if picking:
            out = []
            for j, wk in enumerate(WLIST):
                out.append((wk or "own", pygame.Rect(20, 120 + j * 44, sw - 40, 40), ("pick", wk)))
            out.append(("Back", pygame.Rect(20, 120 + len(WLIST) * 44 + 8, sw - 40, 44), ("close",)))
            return out
        y0, bh, g = 640, 50, 6
        w3 = (sw - 16 - 2 * g) // 3
        R = lambda col, row, span=1: pygame.Rect(8 + col * (w3 + g), y0 + row * (bh + g), w3 * span + g * (span - 1), bh)
        out = [("‹ Who", R(0, 0), ("arch", -1)), ("Random", R(1, 0), ("random",)), ("Who ›", R(2, 0), ("arch", 1)),
               ("‹ Body", R(0, 1), ("body", -1)), ("Skin", R(1, 1), ("skin",)), ("Body ›", R(2, 1), ("body", 1)),
               ("Jacket", R(0, 2), ("jacket",)), ("Trousers", R(1, 2), ("trousers",)), ("Weapon", R(2, 2), ("weapons",)),
               ("Spar", R(0, 3), ("spar",)), ("Head", R(1, 3), ("head",)), ("New name", R(2, 3), ("name",))]
        if can_go_on:
            out += [("Continue", R(0, 4), ("continue",)), ("BEGIN", R(1, 4, 2), ("begin",))]
        else:
            out += [("BEGIN", R(0, 4, 3), ("begin",))]
        return out

    while True:
        now = time.monotonic()
        a, look = now_look()
        style = STYLE.get(look[1], "unarmed")
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return None
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_AC_BACK, pygame.K_ESCAPE, pygame.K_q):
                if picking:
                    picking = False
                elif e.key != pygame.K_q:
                    return None
                continue
            p = phone.pointer(e, screen)
            if not p or p == "skip" or e.type not in (pygame.FINGERDOWN, pygame.MOUSEBUTTONDOWN):
                continue
            _, x, y = p
            if not picking and pygame.Rect(0, 30, sw, 40).collidepoint(x, y):
                st["name"] = rn()
                continue
            hit = next((act for _, r, act in buttons() if r.collidepoint(x, y)), None)
            if not hit:
                continue
            k = hit[0]
            if k == "pick":
                st["weapon"], picking, fight = hit[1], False, None
            elif k == "close":
                picking = False
            elif k == "arch":
                step("arch", len(ARCH), hit[1]); fight = None; st["weapon"] = None
            elif k == "body":
                step("body", len(BODIES), hit[1])
            elif k == "skin":
                step("skin", len(SKINS), 1)
            elif k in ("jacket", "trousers"):
                wear(k, len(JACKETS if k == "jacket" else TROUSERS))
            elif k == "weapons":
                picking = True
            elif k == "random":
                st.update(arch=random.randrange(len(ARCH)), body=random.randrange(len(BODIES)),
                          skin=random.randrange(len(SKINS)), name=rn(), weapon=None,
                          jacket=random.choice([None] + list(range(len(JACKETS)))),
                          trousers=random.choice([None] + list(range(len(TROUSERS)))))
                fight = None
            elif k == "spar":
                spar()
            elif k == "head":
                headfx = now
            elif k == "name":
                st["name"] = rn()
            elif k == "continue":
                return "continue"
            elif k == "begin":
                return begin()
        a, look = now_look()
        style = STYLE.get(look[1], "unarmed")
        hd = a.get("head") or heads.default_head(look)
        screen.fill((10, 9, 14))
        for i in range(40):                                    # drifting stars
            x = (i * 157 + int(now * (3 + i % 5))) % sw
            screen.fill((90, 90, 110), (x, (i * 97) % sh, 2, 2))
        if picking:
            screen.blit(big.render("Choose a weapon", True, (240, 220, 160)), (20, 30))
            screen.blit(tiny.render("Old weapons of Japan and China. Tap one.", True, (150, 150, 165)), (20, 66))
            screen.blit(tiny.render("Their own weapon is first.", True, (150, 150, 165)), (20, 84))
            for label, r, act in buttons():
                on = act[0] == "pick" and act[1] == st["weapon"]
                pygame.draw.rect(screen, (60, 52, 80) if on else (30, 27, 40), r, border_radius=8)
                if act[0] == "close":
                    t = mid.render("Back", True, (240, 235, 220))
                    screen.blit(t, t.get_rect(center=r.center))
                    continue
                wk = act[1]
                if wk is None:
                    own = a["look"][1]
                    screen.blit(mid.render(f"Their own: {WEAPONS[own][1] if own else 'bare hands'}", True,
                                           (240, 235, 220)), (r.x + 14, r.y + 9))
                    continue
                g_, n_, where, sty = OLD_WEAPONS[wk]
                screen.blit(glyph(g_, 24, look[5] if on else (205, 208, 215)), (r.x + 10, r.y + 4))
                screen.blit(mid.render(n_, True, (240, 235, 220)), (r.x + 50, r.y + 9))
                t = tiny.render(f"{where} · {sty}", True, (130, 130, 145))
                screen.blit(t, (r.right - t.get_width() - 12, r.y + 13))
            pygame.display.flip()
            clock.tick(30)
            continue
        screen.blit(tiny.render("NEW DRIFTER  ·  tap the name for another", True, (150, 150, 165)), (12, 10))
        nm = big.render(st["name"], True, (245, 240, 230))
        screen.blit(nm, (sw // 2 - nm.get_width() // 2, 32))
        # them, sparring or idling, with their head showing off when asked
        cx, cy = sw // 2, 245
        pose = {"dy": math.sin(now * 2.2) * 3}
        if fight:
            u = (now - fight[1]) / 1.4
            if u >= 1:
                fight = None
            else:
                pose = pose_for(style, fight[0], u, 150)[0]
        hu = (now - headfx) / 1.6 if headfx else None
        if hu is not None and hu >= 1:
            headfx, hu = None, None
        draw_char(screen, cx, cy, 150, BODIES[st["body"]][0], look, SKINS[st["skin"]][1], None, pose,
                  head="" if hu is not None else hd["glyph"], clothes=(st["jacket"], st["trousers"]))
        if hu is not None:                                     # a simple show of the head: off, round, back on
            ang = hu * 2 * math.pi
            hx, hy = cx + math.sin(ang) * 120, cy - 95 - math.sin(math.pi * hu) * 40
            if hd["power"] == "scout" and 0.1 < hu < 0.9:
                rnd = random.Random(int(now * 9))
                for _ in range(rnd.choice((1, 2, 3))):
                    a_ = rnd.uniform(0, 2 * math.pi)
                    ex, ey = hx + math.cos(a_) * 400, hy + math.sin(a_) * 400
                    pygame.draw.line(screen, (150, 10, 10), (hx, hy), (ex, ey), 7)
                    pygame.draw.line(screen, (255, 40, 40), (hx, hy), (ex, ey), 3)
            draw_head(screen, int(hx), int(hy), 64, hd["glyph"], SKINS[st["skin"]][1], hu * 360)
        # who they are
        y = 340
        t = mid.render(a["name"], True, look[5])
        screen.blit(t, (sw // 2 - t.get_width() // 2, y))
        t = tiny.render(f"{a['tag']}  ·  {ARCH.index(a) + 1}/{len(ARCH)}", True, (130, 130, 145))
        screen.blit(t, (sw // 2 - t.get_width() // 2, y + 22))
        y += 42
        for ln in wrap(small, a["blurb"], sw - 30)[:3]:
            screen.blit(small.render(ln, True, (200, 198, 210)), (15, y))
            y += 17
        y += 6
        for i, (lab, v) in enumerate(zip(STATS, a["stats"])):    # stats in two columns
            x = 15 + (i % 2) * (sw // 2)
            yy = y + (i // 2) * 18
            screen.blit(tiny.render(lab, True, (170, 170, 180)), (x, yy))
            pygame.draw.rect(screen, (40, 36, 52), (x + 34, yy + 4, 150, 8), border_radius=4)
            pygame.draw.rect(screen, look[5], (x + 34, yy + 4, 15 * v, 8), border_radius=4)
        y += 60
        P = heads.POWERS[hd["power"]]
        screen.blit(glyph(hd["glyph"], 18, look[5]), (15, y))
        screen.blit(small.render(f"Head: {P['name']}", True, look[5]), (40, y + 1))
        y += 22
        for ln in wrap(tiny, P["what"], sw - 30)[:2]:
            screen.blit(tiny.render(ln, True, (190, 188, 200)), (15, y))
            y += 15
        y += 6
        jn = JACKETS[st["jacket"]]["name"] if st["jacket"] is not None else "own jacket"
        tn = TROUSERS[st["trousers"]]["name"] if st["trousers"] is not None else "own trousers"
        screen.blit(small.render(f"Fights with: {WEAPONS[look[1]][1]}", True, (220, 218, 230)), (15, y))
        screen.blit(small.render(f"Wearing: {jn}, {tn}", True, (220, 218, 230)), (15, y + 18))
        for label, r, act in buttons():
            hot = act[0] in ("begin", "continue")
            pygame.draw.rect(screen, (96, 80, 50) if act[0] == "begin" else (50, 46, 66) if hot else (34, 30, 46), r,
                             border_radius=10)
            pygame.draw.rect(screen, (240, 220, 160) if hot else (90, 84, 110), r, 2, border_radius=10)
            t = mid.render(label, True, (245, 240, 230))
            screen.blit(t, t.get_rect(center=r.center))
        pygame.display.flip()
        clock.tick(30)
