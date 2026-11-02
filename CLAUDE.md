# Roguelike (working title)

User: EndeavourOS + KDE Plasma (Wayland), fish shell, kitty. Short plain answers, one command at a time.
Direction (Nov 2026): RimWorld x Cowboy Bebop x Project Zomboid. Start stranded on a planet, scavenge/survive,
build a ship to get to space, then the game opens up. Still in the graphics/feel phase.
Original goal: standalone 2D roguelike, Caves of Qud-inspired *look* (own art, never copied), Stone Soup-style depth:
huge generated world, thousands of spells/items, towns, shops, roads; places are random until visited, then permanent.

## Run
`rl` (launcher `~/.local/bin/rl` -> `python3 game/rl.py`), `rl --new`, `rl --seed N`. Needs `python-pygame`.
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
biome colour. Zomboid-style vision cone (rl.update_view: far ahead, 2.3 cells round you), soft darkness edges
(smoothscale). Sound minimal and quiet (immersion.SOUND_VERSION; one bed per zone, not per step).
User wants: minimal but immersive, sparse dim trees, no wading through rivers/lakes.

## Content (Nov 2026)
- structures.py: 33 abandoned-place layouts (ASCII plans + props, rotated/mirrored, ~1 in 4 zones, by biome);
  cultures.py adds a culture per region gone dystopian (forest/jungle Aztec, desert Egyptian, tundra Soviet,
  grass rural decay, fungal/crystal/ash alien tech): 19 more props (stepped pyramid, pyramid, sphinx, pylons,
  neon, mechs...), 13 more layouts, and relics scattered through the land (BIOMES kinds starting "p_").
  "p_solid" = invisible blocked footprint for big monuments.
- weird.py: 12 "insane" plant designs (WEIRD, per-species neon accent). Ground is painted per pixel
  (ground_pass) so nothing shows the grid; proto.gen_cells blends biomes with jittered re-classification.
- Showcases: rl --showcase (21 biomes, alternating busy/barren via World.density), rl --structures (all layouts).
- T = optional screen "trip" effects, OFF by default (user wanted the art insane, not the screen).

## Done so far
World + biomes + rivers/towns/roads, weird look (user: "sparse and dim" flora), walking, permanence, creatures + combat.
## Next ideas
Items/loot, spells (shape x element x twist), shops in towns, character creation, better hero sprite, more immersion
(sound, field of view/darkness, day/night, flavour text).
