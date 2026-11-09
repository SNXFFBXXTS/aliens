"""Heads. Everyone's head is a kanji floating over their body, and it comes off. What it does depends on who you are:

  boomerang  throw it; it flies out, arcs back, hits everything on the way. You're headless till it's back.
  fire / frost / storm / rot   it spits a burning / freezing / chaining / rotting character at what you aim at
  shield     it orbits you, taking blows meant for you and clipping anything close
  spin       it whirls round you on a chain, wide and fast, hitting everything in reach
  nova       it screams: a ring that hits and stuns everything round you
  scout      you send it off to look; you see what it sees, until it comes home

F uses it toward where you're facing; right-click aims it at the mouse.
"""

POWERS = {
    "boomerang": dict(name="Boomerang", what="Throw your head. It arcs back, hitting everything on the way.", cd=0.4),
    "fire": dict(name="Ember spit", what="Your head spits a burning character.", cd=0.7, glyph="炎",
                 col=(255, 150, 70), dmg=6),
    "frost": dict(name="Frost spit", what="A freezing character. What it hits can't move for a while.", cd=0.8,
                  glyph="氷", col=(160, 215, 255), dmg=4),
    "storm": dict(name="Storm spit", what="A lightning character that jumps to two more things nearby.", cd=0.9,
                  glyph="雷", col=(250, 245, 140), dmg=5),
    "rot": dict(name="Rot spit", what="A rotting character. What it hits keeps hurting.", cd=0.7, glyph="腐",
                col=(150, 205, 90), dmg=2),
    "shield": dict(name="Orbit ward", what="Your head circles you for a while, taking blows and clipping what's close.",
                   cd=6.0, time=8.0),
    "spin": dict(name="Chain whirl", what="Your head whirls round you on a chain, wide and fast.", cd=5.0, time=4.0),
    "nova": dict(name="Scream", what="Your head screams. Everything round you is hit and stunned.", cd=5.0),
    "scout": dict(name="Send it off", what="Send your head ahead to look. You see what it sees.", cd=2.0, time=7.0),
}


def default_head(look):
    """for the older characters: a head power that suits how they fight"""
    weapon = look[1] if look else None
    if weapon in ("tome", "orb", "deck", "sax"):
        return {"power": "fire", "glyph": "頭"}
    if weapon == "shield":
        return {"power": "shield", "glyph": "頭"}
    if weapon in ("whip", "staff"):
        return {"power": "spin", "glyph": "頭"}
    return {"power": "boomerang", "glyph": "頭"}
