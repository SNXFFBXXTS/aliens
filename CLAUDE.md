# Roguelike (working title)

User: EndeavourOS + KDE Plasma (Wayland), fish shell, kitty. Short plain answers, one command at a time.
Direction (Nov 2026): RimWorld x Cowboy Bebop x Project Zomboid. Start stranded on a planet, scavenge/survive,
build a ship to get to space, then the game opens up. Still in the graphics/feel phase.
Original goal: standalone 2D roguelike, Caves of Qud-inspired *look* (own art, never copied), Stone Soup-style depth:
huge generated world, thousands of spells/items, towns, shops, roads; places are random until visited, then permanent.

## Run
`rl` opens character creation (charcreate.py: 30 archetypes + make-your-own builder, spar with a dummy);
Enter makes a NEW world and plays as that character (symbol + gear glyphs, stats drive HP/hit/dodge/damage,
moves animate on attack). `rl --play` continues the current world with ~/.local/share/roguelike/character.json.
Launcher: `rl` (launcher `~/.local/bin/rl` -> `python3 game/rl.py`), `rl --new`, `rl --seed N`. Needs `python-pygame`.
Saves: `~/.local/share/roguelike/world-<seed>/` (chunks/*.json = cells + creatures, player.json). `RL_HOME` overrides (testing).
Headless test: `RL_HOME=/tmp/x SDL_VIDEODRIVER=dummy python3 game/rl.py --seed 1337 --shot out.png --moves RRDDW`.

## Files (all in game/)
- `proto.py` world generator: noise fields (height/temp/moisture/volcanic/weird) -> biomes, priority-flood rivers + lakes,
  towns, A* roads. `gen_cells(wd, ox, oy, w, h)` = local terrain for any area (12 cells per world tile), deterministic.
  (Its `paint`/`render_*` are the first, rejected "plain" style; still used for nothing but reference.)
- `weird.py` the chosen style: black bg, one colour family per biome, 8-bit palette indices + palette cycling
  (sea/lava rotate, spore/prism hue drift, lumen/bog breathe), procedural flora generators + mutations, per-world species.
- `weird_proto.py` preview images into `game/out/` (w_world, w_tiles, w_zone_*, w_cycle.gif).
- `mobs.py` creatures: species per biome from the seed (sprite, name, stats, temper), spawning, movement.
- `rl.py` the game: chunks loaded/saved, turn loop, bump combat, XP/levels, death/respawn, HUD, world map (M).
- `art.py` old palette/bitmaps (hero sprite still comes from here).

## Look (current)
Zones: 1 world square = 40x40 cells (proto.ZS), world map = travel screen (M, arrows, M/Enter zooms in).
Art drawn at 2x (weird.RES, 32px cells); trees/huts/peaks/shards are BIG (weird.BIG, up to 64px) and drawn after
the ground: all shadows first (weird.SHADE darkens, never blackens), then bodies back to front; trees from
neighbouring zones that lean over the border are drawn too (weird.pick_big). Ground = dark grainy tint of the
biome colour. All-round vision (rl.update_view, line of sight; the Zomboid cone was removed at the user's request), soft darkness edges
(smoothscale). Sound minimal and quiet (immersion.SOUND_VERSION; one bed per zone, not per step).
User wants: minimal but immersive, sparse dim trees, no wading through rivers/lakes.

## Movement (real time)
Not tied to squares: hold arrows/WASD/numpad to move smoothly (rl.SPEED cells/s, ACCEL), let go and you glide a little
(FRICTION; ~0.45 cell). Game.update(dt) each frame: fx/fy = smooth position, px/py = the cell you're in (everything else
still uses cells). Body is a small box (BODY); walls stop one axis so you slide along them; corner help eases you into
1-wide gaps. Walking into a creature attacks it (ATTACK_S cooldown). The world takes a turn every TICK_S seconds
whether you move or not. Creatures glide between squares when drawn (Game.mob_pos). `act()` is only used by --shot.

## Buildings and size
- Towns are 70s Essex estates (user asked for 1970s Essex house designs, not square boxes, NO ROOFS so you see in):
  proto.gen_cells lays out straight "street" (tarmac) roads from the square plus closes (cul-de-sacs) with turning heads,
  reach 34 cells so a town spreads over the 3x3 zones round its square. buildings.town puts houses facing the streets
  with front gardens; each candidate has its own rng ([base, street, side, step]) so fits never ripple.
- buildings.py PLANS (rooms as shared-wall rects + doors D/B/+/G, front = south): L-plan bungalow, T-plan chalet
  bungalow, link-detached house + garage, U courtyard bungalow, semi-detached pair (mirrored, garages at the ends),
  staggered terrace of 3. oriented() turns/mirrors so the front door faces the street; houses are slid wholly inside
  one zone. stamp(): windows on outside walls of lived-in rooms, then _furnish per room (b bed/l lounge/k kitchen/
  d dining/w bathroom/g garage/h hall) via _House.put (door can always reach all free floor).
  Floors: hcarpet (orange lounge), hcarpetb (avocado bedroom), hlino (check), hbath, hconc (garage), hfloor (hall);
  gdoor = open up-and-over garage door. Furniture f_*: bed, sofa, telly, coffee table, armchair, lamp, plant, cooker,
  sink, fridge, cupboard, dining table + chairs, wardrobe, dresser, avocado bath + toilet, workbench, boxes, oil drum.
- Houses have no roofs and house walls don't block sight (immersion.BLOCK_SIGHT). Game.draw_doors marks front doors.
  World.houses() finds houses by their joined walls; World.house_bits() caches furniture + outside doors.
  Creatures don't spawn in zones with houses, can't walk through walls/furniture (mobs.NO_WALK). Old saves keep huts.
- No face-like props (user): serpent heads, stelae, skull racks and idols were removed from scatter and layouts.
- Character size slider: Z (or [ ]) -> Game.size (0.3..1.2, default 0.55), saved in ROOT/settings.json. Hero and
  creatures scale from their feet; collision body scales a bit too.

## Scavenging and survival
- items.py: ITEMS (food, drink, medical, weapons, parts for later building) and LOOT tables per container code
  (house furniture f_stove/f_shelf/f_dress/f_end/f_crate/f_sink, ruin props p_crate/p_barrel/p_rack/p_car/...).
  Contents come from seed + square (items.loot), so nothing is stored until searched; World.searched_set() is saved in
  the world dir (searched.json).
- E (or Space) searches the container within reach (Game.container_near; label + outline drawn over it, 1 s progress
  bar, moving cancels). I/Tab opens the inventory (pauses): Enter uses/eats/holds a weapon, D drops.
- Food and water drain each world tick (~14 / ~9 min from full); warnings at 25 and 0; at 0 you lose HP; no healing
  unless both > 20. Held weapon adds damage. Inventory, food, water, weapon saved in player.json.

## Performance notes
Line of sight only recomputed when position/light changes (update_view vkey); darkness overlay keyed on what it shows
and built with numpy; palette rebuilt ~12x/s; animated plants skipped in never-seen places. Walking ~7 ms/frame median.

## Content (Nov 2026)
- structures.py: 33 abandoned-place layouts (ASCII plans + props, rotated/mirrored, ~1 in 4 zones, by biome);
  cultures.py adds a culture per region gone dystopian (forest/jungle Aztec, desert Egyptian, tundra Soviet,
  grass rural decay, hills/meadow/beach Roman ruins with mosaic floors, fungal/crystal/ash alien tech): 19 more props (stepped pyramid, pyramid, sphinx, pylons,
  neon, mechs...), 13 more layouts, and relics scattered through the land (BIOMES kinds starting "p_").
  "p_solid" = invisible blocked footprint for big monuments.
- weird.py: "insane" plant designs (WEIRD, per-species neon accent). NO FACES on plants (user: monsters will have faces). Ground is painted per pixel
  (ground_pass) so nothing shows the grid; proto.gen_cells blends biomes with jittered re-classification.
- Showcases: rl --showcase (21 biomes, alternating busy/barren via World.density), rl --structures (all layouts).
- T = optional screen "trip" effects, OFF by default (user wanted the art insane, not the screen).

## Done so far
World + biomes + rivers/towns/roads, weird look (user: "sparse and dim" flora), walking, permanence, creatures + combat.
## Next ideas
Items/loot, spells (shape x element x twist), shops in towns, character creation, better hero sprite, more immersion
(sound, field of view/darkness, day/night, flavour text).
