# Roguelike (working title)

User: EndeavourOS + KDE Plasma (Wayland), fish shell, kitty. Short plain answers, one command at a time.
Goal: standalone 2D roguelike, Caves of Qud-inspired *look* (own art, never copied), Stone Soup-style depth:
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

## Done so far
World + biomes + rivers/towns/roads, weird look (user: "sparse and dim" flora), walking, permanence, creatures + combat.
## Next ideas
Items/loot, spells (shape x element x twist), shops in towns, character creation, better hero sprite, more immersion
(sound, field of view/darkness, day/night, flavour text).
