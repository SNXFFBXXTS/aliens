# Roguelike (working title)

User: EndeavourOS + KDE Plasma (Wayland), fish shell, kitty. Short plain answers, one command at a time.
Direction (Nov 2026): RimWorld x Cowboy Bebop x Project Zomboid. Start stranded on a planet, scavenge/survive,
build a ship to get to space, then the game opens up. Still in the graphics/feel phase.
Original goal: standalone 2D roguelike, Caves of Qud-inspired *look* (own art, never copied), Stone Soup-style depth:
huge generated world, thousands of spells/items, towns, shops, roads; places are random until visited, then permanent.

## Direction
See DIRECTION.md (Nov 2026): creepy derelict colony planet, changed colonists, the planet's eye, sanity that
lies, shanties + decay, permadeath. Work order: look first (milestone 1), then systems. 70s Essex estates are being dropped.

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
- Milestone 1.2 (DIRECTION.md): towns are now SHANTY SETTLEMENTS (the 70s estates are dropped; old saves still draw
  their h* codes). proto.gen_cells: ragged "mud" clearing round a bonfire, 4-6 wandering mud paths out (same in every
  zone, so they join), buildings.settlement() scatters shacks (own rng per shack, wholly inside one zone) facing the fire,
  each door gets a short mud spur. buildings.shack(): walls per side from iron/wood/tarp/hull (patched 22%), sgap holes,
  sometimes a lean-to (tarp/wood) and a caved-in stretch ("debris", walkable); floors sdirt/spallet. _furnish: floor
  mattress f_matt0/1, oil-drum stove f_drum (glows), crate table + stool, scrap shelf, bucket, rags, water barrel,
  crate, sometimes a shrine (candles, twig effigy, the eye daubed in red). Zone mood "shanty" (immersion text).
- Milestone 1.1: weird.sicken() drains the whole palette at load (blood/lava/eye stay vivid), darker days, night
  near-black with a carried light (darkness carve + warm glow), drifting fog (Game.draw_fog), screen vignette.
- No face-like props (user): serpent heads, stelae, skull racks and idols were removed from scatter and layouts.
- Character size slider: Z (or [ ]) -> Game.size (0.3..1.2, default 0.55), saved in ROOT/settings.json. Hero and
  creatures scale from their feet; collision body scales a bit too.

## Scavenging and survival
- items.py: ITEMS (food, drink, medical, weapons, parts for later building) and LOOT tables per container code
  (house furniture f_stove/f_shelf/f_dress/f_end/f_crate/f_sink, ruin props p_crate/p_barrel/p_rack/p_car/...).
  Contents come from seed + square (items.loot), so nothing is stored until searched; World.searched_set() is saved in
  the world dir (searched.json).
- Menus are Dungeon Crawl Stone Soup-style on an MS-DOS text screen (dosui.Dos: 80x25 cells of 8x16 at 640x400,
  16 VGA colours, ProggyClean pixel font for ASCII, DejaVu for symbols, box lines drawn as exact pixels, scaled up hard).
  E on a container: "Pick up what?" (letters mark -/+, ',' all, '-' none, Enter take, Tab = "Put what in?").
  I: inventory grouped by category (items.CATEGORY) with symbols/colours (items.GLYPH), letter opens a boxed
  description (items.DESC) with [e]at/[q]uaff/[a]pply/[w]ield/[d]rop. Game.draw_menu / bag_input / menu_rows.
  Containers keep what's left (World.containers(), containers.json). Carry weight vs Game.cap = 12 + 1.5*STR kg.
  (The earlier Zomboid two-pane window with drag and drop was replaced at the user's request.)
- Sounds (user HATED the FM/chip blips): sfx.py makes everything from noise + sines. beds(): grainy gusting wind
  (band-limited noise, gust envelopes, crackle grains) + sine whistles (pitch drift, vibrato, breath, sometimes a
  semitone dyad), per-biome mixes, faint detuned drones, tin rattles for settlements. sounds(): foley (creak, thud,
  scrape, rustle, crunch, glug, rip). SOUND_VERSION "5-wind" regenerates (~5 s). Game.METAL picks clunk vs creak.
- Window glass uses the "ice" family: "sea" shades cycle and made windows flash.
- Food and water drain each world tick (~14 / ~9 min from full); warnings at 25 and 0; at 0 you lose HP; no healing
  unless both > 20. Held weapon adds damage. Inventory, food, water, weapon saved in player.json.

## Maps, crew, cold open (Nov 2026)
- Minimap top-right (Game.minimap: 64x64 squares round you from World.seen + codes, coloured by Game.code_colour; V
  toggles). World map on M (Game.draw_map): explored clear, unexplored dimmed, towns as houses, you pulsing.
- Bag window supports mouse drag and drop (whole stack; Shift = one). Searching is instant (no wait).
- Pipes prop redrawn (round shaded pipeline, flanges, saddles, valve wheel or broken end) and ~5x rarer.
- "Drift" crew archetypes (old late-night anime vibe, NOT copies; the old "Bebop" tag was renamed Drift): Lounge Singer,
  Bounty Clerk, Noodle Mechanic, Rock Wrangler, Lapsed Monk, Undertaker (+ the earlier Bounty Hunter etc.).
  Restore point before them: git tag before-anime-characters (branch backup/before-anime-characters).
- New story opens on a title card (Game.draw_cold_open): eyecatch-style diagonal colour field, film grain, letterbox,
  "REEL nn" + generated title (REEL_WORDS + REEL_FORMS), the character big and flat, FM jazz sting (sfx "sting").
  main() sets it only for brand-new worlds with a character (not in --shot).

## Heads (Nov 2026)
Every character's head is a kanji drawn on top of their body glyph (charcreate.draw_head / draw_char(head=...)), and it
comes off. heads.POWERS: boomerang (thrown, arcs back, hits on the way out and back), fire/frost/storm/rot (spits a
kanji: burn / freeze-stun / chain lightning / poison), shield (orbits, 70% of blows land on it, clips), spin (wide fast
chain orbit), nova (scream: hits + stuns within ~4 cells), scout (send it off; you see from it). While a boomerang or
scout head is out you see from the head (Game.update_head swaps self.vis). F = toward facing, right-click = at mouse
(Game._cam maps screen->cells). Game.damage_mob is the one place creatures get hurt/killed; Game.mob_fx holds stun/poison.
10 "Severed" classes (Head Thrower, Ember Saint, Frost Widow, Storm Oracle, Rot Priest, Gate Warden, Chain Monk,
Bell Ringer, Watcher, Bone Twin); older archetypes each get a fitting power + kanji from heads.ARCH_HEADS (spread over all nine powers,
4-7 each; heads.default_head(look) is only a fallback for the custom builder). character.json stores "head".
The head ALWAYS comes off (user): spit powers pop it forward to spit then it flies back (head_out kind
"spit"), the scream lifts it off and shakes it (kind "scream"); hats go with the head. Selection screen: H demos the
head on the dummy, and a TUTORIAL box plays real footage of the power (assets/tutorials/<power>.jpg filmstrips, made by
game/tools/make_tutorials.py: re-run it whenever powers change) with heads.TUTORIAL steps. Creatures got a light rim + lifted colours (they vanished in the
sickly palette). Demo recorder: game/out/demo/record.py -> heads.mp4.

## Performance notes
Zoom levels 0.6-2.0 (0.5 was too slow). Fog drawn at quarter res and only in a box round your sight; zoomed view
resized with a fast scale; darkness built at half size. ~12 ms/frame at 100%, ~25 ms at 60%.
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
