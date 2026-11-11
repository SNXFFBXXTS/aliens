# Roadmap

The big picture lives in DIRECTION.md. This file is the to-do list: what we're fixing and building, in order.

## How we work
1. **One thing at a time.** Take the top item from "Now", finish it, play it, tick it off.
2. **Every item has "Done when".** If we can't say when it's done, it's still too vague: split it up first.
3. **Bugs are written like this:**
   - *Where:* what you were doing (zone/biome, menu, key pressed)
   - *Saw:* what happened · *Expected:* what should have happened
   - *Seed:* top-right of the HUD, so it can be reproduced
4. **New ideas go in "Ideas" first.** They move up into "Next" only once we agree they fit, so they don't derail the current item.
5. Test after each item: play it for a few minutes, then commit.

---

## Now: fix what's there

### ✅ B1. The world map lets you roam
Pressing the arrows on the map (M) moved you a whole square, so you could fast-travel across the world.
- **Fixed (Nov 10):** the arrows now move a yellow look cursor that shows "Looking at: Grassland (5 squares away)".
  You never move while the map is open.

### ✅ B1b. Restricted view
You could only see a small circle round you.
- **Fixed (Nov 10):** Caves of Qud style, the whole screen is visible so you can spot danger. Night is a darker tint, not blindness.

### ✅ B2. Load times / freezes when walking into new areas
**Measured before:** each zone took 0.6–1.3 s to draw, in a thread that fought the game for the CPU. Walking fast,
the game froze for about **1.2 s on entering each new zone**, and once 40 zones were loaded it threw all of them away.
**Fixed (Nov 10):**
- Zones are painted in **2 worker processes** (`game/zonepaint.py`), so drawing them no longer slows the game down.
- The zone you're walking toward is always drawn first (picked by where you'll be in about 1.5 s).
- Ground and road drawing is about 30% faster (wild zones skip road/town work; ground shades done in one pass).
  The pixels are identical to before.
- A full cache drops only the furthest zones; road tracing moved into the workers.
- Fixed a crash on save while zones were still loading.

**Result:** at 3x walking speed, fully zoomed out, across 7 new zones: **no freezes** (was three of about 1.2 s).
Normal play: about 8 ms a frame.
Left over: startup's first frame is about 0.5 s slower (the workers start up alongside it). If revisits ever feel
slow, the next step is caching zone pictures on disk.

### B3. (your next bug goes here)
Use the bug format above.

---

## Next: features, in order (from DIRECTION.md)

Each one is small enough to finish in a session or two.

### F1. Decay and "what happened" in shacks (milestone 1.3–1.4)
- Collapsed walls, caved floors, overturned furniture, stains, growth through floors; "how far gone" varies by settlement.
- Barricaded doors, tally marks, bed pushed against the door, a chair facing the wall.
- **Notes:** short, unsettling, found in containers; read with E; kept in a journal (J).
- **Done when:** every settlement has at least one shack that tells a little story without words, plus 20+ notes in the pool.

### F2. Landing-era prefab blocks (1.5)
- **Done when:** rotting colony prefab units appear at the edges of shanties, with their own loot table.

### F3. Sound pass (1.6)
- Creaks, a detuned drone layer that swells with danger, and a warped radio in some shacks.
- **Done when:** walking into a settlement sounds different from the wilds, and a hunt sounds different from quiet.

### F4. Rings: outskirts to the heart (milestone 2)
- **Done when:** the danger tier rises toward the centre, it shows on the HUD, and there are more hunts deeper in.

### F5. Sanity meter (milestone 3)
- A meter on the HUD; dark, the eye and corpses drain it; fire, rest and food restore it.
- Low sanity: phantom creatures, whispers in the log, wrong map markers.
- **Done when:** you can watch sanity fall, see at least 3 kinds of lie, and get it back by resting at camp.

### F6. The eye (milestone 4) → F7. Changed colonists who talk/trade (5) → F8. Ship parts + endings (6) → F9. Permadeath, graves of past characters (7)

---

## Ideas (parking lot)
Write anything here: one line each, no need to be sure.
-

## Done
- B1 World map no longer moves you (Nov 10, 2026)
- B1b Whole screen visible, no line of sight (Nov 10, 2026)
- B2 No more freezes entering new zones: worker processes + nearest-first (Nov 10, 2026)
