"""Immersion: field of view, day/night, place descriptions, ambient sound.

fov()        recursive shadowcasting; mountains/peaks/houses block sight
daytime()    turn -> (day number, phase name, sight radius, tint colour+alpha)
describe()   a sight + sound + smell line for a biome, varied each time
Ambience     generated ambient loops (made once into game/sounds/), quiet crossfades between areas
"""
import math, os, random, struct, wave
import numpy as np

BLOCK_SIGHT = {"mountain", "peak", "house"}
THICK = {"forest": 8, "jungle": 6, "fungal": 7, "taiga": 9, "swamp": 10}     # max sight inside these

DAY = 1000                       # turns in a day


def daytime(turn):
    t = (turn + 150) % DAY        # start the game in the morning
    day = (turn + 150) // DAY + 1
    if t < 100:
        return day, "Dawn", 10, (90, 45, 20, 50)
    if t < 560:
        return day, "Day", 15, (0, 0, 0, 0)
    if t < 660:
        return day, "Dusk", 10, (45, 12, 55, 80)
    return day, "Night", 6, (0, 4, 22, 105)


def fov(ox, oy, radius, cell):
    """set of (x, y) visible from (ox, oy); cell(x, y) -> biome code"""
    vis = {(ox, oy)}
    def cast(row, start, end, xx, xy, yx, yy):
        if start < end:
            return
        for j in range(row, radius + 1):
            dx, dy = -j - 1, -j
            blocked, new_start = False, start
            while dx <= 0:
                dx += 1
                X, Y = ox + dx * xx + dy * xy, oy + dx * yx + dy * yy
                l_slope, r_slope = (dx - 0.5) / (dy + 0.5), (dx + 0.5) / (dy - 0.5)
                if start < r_slope:
                    continue
                if end > l_slope:
                    break
                if dx * dx + dy * dy <= radius * radius:
                    vis.add((X, Y))
                opaque = cell(X, Y) in BLOCK_SIGHT
                if blocked:
                    if opaque:
                        new_start = r_slope
                        continue
                    blocked = False
                    start = new_start
                elif opaque and j < radius:
                    blocked = True
                    cast(j + 1, start, l_slope, xx, xy, yx, yy)
                    new_start = r_slope
            if blocked:
                break
    for xx, xy, yx, yy in ((1, 0, 0, 1), (0, 1, 1, 0), (0, -1, 1, 0), (-1, 0, 0, 1),
                           (-1, 0, 0, -1), (0, -1, -1, 0), (0, 1, -1, 0), (1, 0, 0, -1)):
        cast(1, 1.0, 0.0, xx, xy, yx, yy)
    return vis


# ── descriptions: sight / sound / smell pools per biome ──
D = {
    "grass": (["Pale grass bends the wrong way, against the wind.", "Seed-heads tick against each other like tiny clocks.",
               "The grass here grows in slow spirals."], ["Something chirps in a rhythm you almost recognise.", "Wind hisses through the stalks."],
              ["It smells of cut stems and old rain.", "The air tastes faintly of pennies."]),
    "meadow": (["Pink blooms turn to follow you.", "Petals drift upward instead of down.", "The flowers here have small, careful mouths."],
               ["A low hum comes from the petals.", "Bees, or something like bees, drone nearby."], ["The air is thick with sweet, heavy pollen.", "It smells like candied rot."]),
    "savanna": (["Amber grass runs to the horizon.", "Lone trees stand like signposts to nowhere."], ["Dry stalks rattle in the heat.", "Far off, something laughs."],
                ["Dust and sun-baked straw.", "The heat smells of hot stone."]),
    "forest": (["Drippy trees lean over the path, watching.", "Bark eyes blink shut as you pass.", "Sap glistens in long threads between branches."],
               ["Leaves whisper in no wind.", "Something knocks on wood, three times, then stops."], ["Damp earth and something sweetly spoiled.", "Moss, resin and wet fur."]),
    "jungle": (["Coral trees glow a soft, sick teal.", "Bulbs hang from arching stems, pulsing gently.", "The undergrowth breathes in and out."],
               ["Clicks and drips and wet little pops.", "A chorus of tiny voices falls silent as you step in."], ["Warm, wet and green.", "Rotting fruit and ozone."]),
    "swamp": (["Yellow-green slime glows on black water.", "Stalks rise from the bog like fingers."], ["Bubbles burst with soft sighs.", "Something large shifts under the mud."],
              ["Sulphur and sour weeds.", "The bog smells like an old wound."]),
    "taiga": (["Blue-frosted spires crowd the snow.", "Rime grows on every needle."], ["Snow creaks under your feet.", "Branches crack in the cold."],
              ["Clean, freezing air.", "Pine sap and ice."]),
    "tundra": (["Flat white, forever.", "Shards of ice jut from the snow like teeth."], ["The wind never stops here.", "Silence, apart from your breathing."],
               ["The cold has no smell at all.", "Frost bites the inside of your nose."]),
    "icesheet": (["Ice stretches out, cracked into blue plates.", "Deep under the ice, something glows."], ["The ice groans like a ship.", "A crack runs past with a sound like a gunshot."],
                 ["Cold, metallic air.", "Nothing, just cold."]),
    "drift": (["Snow drifts in frozen waves.", "Pale mounds hide shapes you'd rather not dig up."], ["Snow hisses across the drifts."], ["Clean, stinging cold."]),
    "seaice": (["Pack ice grinds against itself.", "Black water shows between the floes."], ["The ice moans and pops.", "Water slaps against the floes."], ["Salt and frozen weed."]),
    "desert": (["Orange dunes ripple in the heat haze.", "Ribs of something huge stick out of the sand."], ["Sand sings softly as it slides.", "Nothing. Absolutely nothing."],
               ["Hot dust in your throat.", "Baked sand and old bone."]),
    "salt": (["A white crust cracks into perfect hexagons.", "Salt crystals spike up like frozen flames."], ["Your steps crunch loudly.", "The silence rings."],
             ["The air is bitter with salt.", "Brine and chalk."]),
    "badlands": (["Rust-red rock, gouged and folded.", "Dead spires lean in the wind."], ["Loose stones skitter down slopes.", "Wind howls through hollow rock."],
                 ["Iron and dust.", "It smells like a struck match."]),
    "hills": (["Rolling hills, boulders scattered like dice.", "Tufted slopes rise and fall."], ["A distant bell, or a bird that sounds like one.", "Wind over the crests."],
              ["Grass and stone.", "Fresh, open air."]),
    "ash": (["Grey ash lies thick, printed with strange tracks.", "Charred bones poke from the cinders."], ["Ash whispers under your boots.", "Far off, the ground rumbles."],
            ["Smoke and burnt hair.", "Every breath tastes of soot."]),
    "crust": (["Black crust, still glowing in the cracks.", "Heat shimmers off the cooling rock."], ["The rock ticks and pings as it cools.", "A deep, slow bubbling."],
              ["Sulphur and hot metal.", "The air burns your nose."]),
    "fungal": (["Violet caps tower overhead, dripping slow threads.", "Spores drift past like slow snow.", "Orbs of light float between the stalks."],
               ["Something breathes in the gills overhead.", "A soft, wet thrum, like a heartbeat.", "Puffballs pop softly in the dark."],
               ["Earthy, sweet and wrong.", "The spores taste of mushrooms and metal."]),
    "crystal": (["Crystal shards ring with shifting colours.", "Light bends strangely here; your shadow has two heads."],
                ["The crystals chime in the wind.", "A high, pure note hangs in the air."], ["The air is dry and electric.", "Ozone and cold glass."]),
    "beach": (["Pale sand meets dark water.", "Shells crunch underfoot."], ["Waves hush against the shore.", "Gulls, or something gull-shaped."], ["Salt and seaweed."]),
    "road": (["A worn road, rutted by wheels.", "Old stones mark the way."], ["Your footsteps sound loud on the packed earth."], ["Dust and dung."]),
    "plaza": (["Domed huts crowd round a dusty square.", "Lanterns glow in round windows."], ["Murmured voices, a door creaking.", "Someone is hammering something."],
              ["Woodsmoke and cooking.", "Bread, smoke and animals."]),
}
WATERY = {"shallow": "You wade into cold water.", "lake": "You wade into the lake; things brush your legs.", "river": "The river tugs at your knees."}


def describe(biome, rng=random):
    if biome in WATERY:
        return WATERY[biome]
    if biome not in D:
        return None
    sight, sound, smell = D[biome]
    parts = [rng.choice(sight), rng.choice(sound)]
    if rng.random() < 0.6:
        parts.append(rng.choice(smell))
    return " ".join(parts)


# ── sound: made once with numpy, played quietly with pygame.mixer ──
RATE = 22050
SND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
AMB_OF = {"forest": "forest", "jungle": "jungle", "swamp": "water", "lake": "water", "river": "water", "shallow": "water",
          "beach": "water", "fungal": "fungal", "crystal": "crystal", "ash": "lava", "crust": "lava", "lava": "lava",
          "plaza": "town", "road": "wind", "grass": "wind", "meadow": "forest", "savanna": "wind", "desert": "wind",
          "salt": "wind", "badlands": "wind", "hills": "wind", "tundra": "cold", "taiga": "cold", "icesheet": "cold",
          "drift": "cold", "seaice": "cold"}


def _noise(n, rng):
    return rng.uniform(-1, 1, n)


def _lp(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc); y[i] = acc
    return y


def _write(name, x):
    os.makedirs(SND_DIR, exist_ok=True)
    x = np.clip(x / (np.abs(x).max() + 1e-9) * 0.9, -1, 1)
    with wave.open(os.path.join(SND_DIR, name + ".wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes((x * 32000).astype("<i2").tobytes())


def _loopfade(x, f=2000):
    """make a loop seamless by crossfading its tail into its head"""
    head, tail = x[:f].copy(), x[-f:]
    r = np.linspace(0, 1, f)
    x = x[:-f].copy()
    x[:f] = head * r + tail * (1 - r)
    return x


def make_sounds():
    rng = np.random.default_rng(7)
    n = RATE * 8
    t = np.arange(n) / RATE
    wind = _lp(_noise(n, rng), 0.02) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 8 * 2) ** 2)
    _write("amb_wind", _loopfade(wind))
    cold = _lp(_noise(n, rng), 0.05) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 4) ** 2) + 0.15 * np.sin(2 * np.pi * 880 * t) * (np.sin(2 * np.pi * t / 8) > 0.95)
    _write("amb_cold", _loopfade(cold))
    forest = _lp(_noise(n, rng), 0.03) * 0.7
    for _ in range(14):                               # odd little chirps
        s = rng.integers(0, n - 4000); f0 = rng.uniform(1800, 3600)
        k = np.arange(3000)
        forest[s:s + 3000] += 0.35 * np.sin(2 * np.pi * (f0 + 900 * np.sin(k / 300)) * k / RATE) * np.exp(-k / 700)
    _write("amb_forest", _loopfade(forest))
    jungle = _lp(_noise(n, rng), 0.05) * 0.5
    for _ in range(40):                               # wet clicks and pops
        s = rng.integers(0, n - 800); k = np.arange(800)
        jungle[s:s + 800] += 0.5 * np.sin(2 * np.pi * rng.uniform(300, 1400) * k / RATE) * np.exp(-k / 120)
    _write("amb_jungle", _loopfade(jungle))
    water = _lp(_noise(n, rng), 0.12) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * t * 0.5)))
    for _ in range(60):                               # bubbles
        s = rng.integers(0, n - 1200); k = np.arange(1200); f0 = rng.uniform(400, 900)
        water[s:s + 1200] += 0.25 * np.sin(2 * np.pi * (f0 + k * 0.4) * k / RATE) * np.exp(-k / 250)
    _write("amb_water", _loopfade(water))
    lava = _lp(_noise(n, rng), 0.004) * 3 + 0.4 * np.sin(2 * np.pi * 38 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 4))
    for _ in range(50):                               # crackles
        s = rng.integers(0, n - 200)
        lava[s:s + 200] += _noise(200, rng) * np.exp(-np.arange(200) / 40)
    _write("amb_lava", _loopfade(lava))
    drone = sum(np.sin(2 * np.pi * f * t + p) for f, p in ((55, 0), (55.7, 1), (82.4, 2), (110.9, 3)))
    drone *= 0.6 + 0.4 * np.sin(2 * np.pi * t / 8)
    drone += _lp(_noise(n, rng), 0.01) * 2
    _write("amb_fungal", _loopfade(drone))
    chime = _lp(_noise(n, rng), 0.01) * 0.3
    for _ in range(12):
        s = rng.integers(0, n - 20000); k = np.arange(20000); f0 = rng.choice([1046, 1318, 1568, 2093, 2637])
        chime[s:s + 20000] += 0.4 * np.sin(2 * np.pi * f0 * k / RATE) * np.exp(-k / 6000)
    _write("amb_crystal", _loopfade(chime))
    town = _lp(_noise(n, rng), 0.015) * 1.2
    for _ in range(10):                               # distant knocks
        s = rng.integers(0, n - 1500); k = np.arange(1500)
        town[s:s + 1500] += 0.5 * np.sin(2 * np.pi * 180 * k / RATE) * np.exp(-k / 200)
    _write("amb_town", _loopfade(town))
    night = _lp(_noise(n, rng), 0.01) * 0.5
    for s in range(0, n - 3000, RATE // 3):           # crickets
        if rng.random() < 0.6:
            k = np.arange(2000)
            night[s:s + 2000] += 0.3 * np.sin(2 * np.pi * 4200 * k / RATE) * (np.sin(2 * np.pi * 30 * k / RATE) > 0) * np.exp(-k / 900)
    _write("amb_night", _loopfade(night))
    # effects
    k = np.arange(int(RATE * 0.12))
    _write("fx_hit", _noise(len(k), rng) * np.exp(-k / 400) + np.sin(2 * np.pi * 120 * k / RATE) * np.exp(-k / 600))
    _write("fx_hurt", np.sin(2 * np.pi * (220 - k * 0.03) * k / RATE) * np.exp(-k / 800) + 0.3 * _noise(len(k), rng) * np.exp(-k / 300))
    k = np.arange(int(RATE * 0.5))
    _write("fx_kill", np.sin(2 * np.pi * 660 * k / RATE) * np.exp(-k / 3000) + 0.6 * np.sin(2 * np.pi * 990 * k / RATE) * np.exp(-k / 2500))
    k = np.arange(int(RATE * 0.9))
    lvl = sum(np.sin(2 * np.pi * f * k / RATE) * (k > i * 3000) * np.exp(-np.maximum(0, k - i * 3000) / 5000)
              for i, f in enumerate((523, 659, 784, 1046)))
    _write("fx_level", lvl)
    k = np.arange(int(RATE * 0.06))
    _write("fx_miss", _lp(_noise(len(k), rng), 0.3) * np.exp(-k / 300))


class Ambience:
    """quiet ambient loops that crossfade as you move between areas; N toggles"""

    def __init__(self, volume=0.22):
        self.ok = False
        self.on = True
        self.vol = volume
        try:
            import pygame
            self.pg = pygame
            if not os.path.exists(os.path.join(SND_DIR, "amb_night.wav")):
                make_sounds()
            pygame.mixer.init(RATE, -16, 1, 1024)
            pygame.mixer.set_num_channels(8)
            self.snd = {f[:-4]: pygame.mixer.Sound(os.path.join(SND_DIR, f)) for f in os.listdir(SND_DIR) if f.endswith(".wav")}
            self.ch = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
            self.night_ch = pygame.mixer.Channel(2)
            pygame.mixer.set_reserved(3)
            self.cur = None
            self.ok = True
        except Exception:
            pass

    def area(self, biome, night):
        if not self.ok:
            return
        name = "amb_" + AMB_OF.get(biome, "wind")
        if name != self.cur:
            self.cur = name
            self.ch[0].fadeout(1500)
            self.ch.reverse()
            if self.on:
                self.ch[0].set_volume(self.vol)
                self.ch[0].play(self.snd[name], loops=-1, fade_ms=1500)
        want = night and self.on
        if want and not self.night_ch.get_busy():
            self.night_ch.set_volume(self.vol * 0.6)
            self.night_ch.play(self.snd["amb_night"], loops=-1, fade_ms=3000)
        elif not want and self.night_ch.get_busy():
            self.night_ch.fadeout(3000)

    def fx(self, name, vol=1.0):
        if self.ok and self.on:
            s = self.snd.get("fx_" + name)
            if s:
                s.set_volume(self.vol * 1.6 * vol)
                s.play()

    def toggle(self):
        if not self.ok:
            return False
        self.on = not self.on
        if not self.on:
            self.pg.mixer.stop()
            self.cur = None
        return self.on
