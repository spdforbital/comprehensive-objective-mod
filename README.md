# Comprehensive Objective Mod (OpenMW)

Skyrim-style quest objectives for **OpenMW 0.51**. For every journal stage it shows what to actually do:
who to talk to, which key or item to get, who to kill and where to go. Each objective has a live distance,
a direction arrow (proximityTool's arrow images; it turns as you turn) and a compass/HUD marker. When the target is a few rooms away,
the distance and arrow point to the next door on the way there.
The panel shows your newest quest, or the one you track with Quest Markers Plus's journal **track** button. Quest Guider's automatic re-tracking after journal updates doesn't take the panel away from the quest you picked.

Each line is one step, and steps tick off as you do them: items when you have them (with a count such as 3/5),
kills when the target is dead, "go to" lines when you arrive and "ask" lines once you have talked to that person.

![Objective panel](docs/final.jpg)

- A small panel at the top right. Finished steps stay listed with an **X**, and the nearest open step is highlighted.
- Objective lines and markers use the quest's colour.
- Markers go through proximityTool, so they show on its HUD and on a
  Skyrim-style compass (Quest Markers Plus).
- Hand-written objectives for **3,161 quest ids**:
  - Morrowind, Tribunal and Bloodmoon.
  - Tamriel Rebuilt (25.08.12).
  - Project Cyrodiil and Skyrim: Home of the Nords.
  - About 70 quest mods, among them Tel Eurus, Greymarch Dawn, Vivec Expansion, Uvirith's Legacy,
    Rise of House Telvanni, Sotha Sil Expanded and Astrologians Guild.
- **Mod-aware:**
  - When a plugin that rewrites a vanilla quest is loaded, the objectives switch to that version.
  - If a quest's journal text changed in a way we don't know about, the panel falls back to showing the journal
    text, so it never shows wrong steps.
- Runs **alongside** other quest trackers; it does not replace them.

## Collector's Ledger (included)

A permanent "quest" for the best items you can find in the world, either lying loose or in containers. It covers:
weapons by type, armor by slot and full sets, artifacts, rings and amulets, scrolls, spell books and ingredients.
Items are coloured green, yellow or red against your current gear. Enchantments are scored with the game's
formula and weighted by your class. Tracking an item puts the nearest copy on the compass.
The search box at the top filters the current tab by name or effect (e.g. "restore fatigue" lists every
ingredient with it) and searches the whole category, not just the top entries.
Plants count too (marshmerrow, wickwheat...), and so do chests. On the Ingredients tab, **Regrowing plants only**
limits it to plants that grow back, so you can farm them. If the nearest copy can't be reached (a locked door, say), press
**[Skip]** on the Tracked tab: that place is never picked again and tracking moves to the next-nearest copy.

![Collector's Ledger](docs/ledger-menu.jpg)

## Town rest (included)

Where sleeping is illegal (towns, shops, guild halls), **Wait** heals you like real rest: 0.1 x Endurance health
and the game's rest rate of magicka per hour (none with the Atronach sign). The game still refuses to let you wait
with enemies nearby.

## Controls

| Keyboard | Controller | Action |
|---|---|---|
| K | D-pad up | Show/hide the objective panel |
| L | D-pad down | Open/close the Collector's Ledger (D-pad moves, A selects, LB/RB switch tabs, B closes) |

## Install

1. Copy this folder somewhere and add it as a `data=` line in `openmw.cfg`.
2. Add `content=comprehensive_objective_mod.omwscripts`.
3. Requires **proximityTool**. Quest Markers Plus is optional, for the compass.

The shipped `objectives_data.lua` and `ledger_data.lua` were built from the author's load order (about 200
plugins). Quests from plugins you don't have are simply never shown.

## Rebuilding the data for your own load order

`tools/` reads your `openmw.cfg` and the plugins in it:

```bash
cd tools
python3 world.py build            # index every plugin (writes world.pickle, a few minutes)
python3 build_objectives.py       # validate objectives/*.json and write the Lua data
python3 build_ledger.py           # rebuild the Collector's Ledger data
```

Other `world.py` helpers that are useful when writing objectives: `journal <QuestId>`, `talk <QuestId>`,
`where <id>`, `find <text>`, `cell "<cell>"`, `mods <QuestId>`.

## Writing objectives

Objectives live in `objectives/*.json`, one entry per quest id and journal stage. See `objectives/main_quest.json`
for the format. `build_objectives.py` checks every target against the real load order and writes
`objectives/VALIDATION.md`.

A line can carry a `doneIf` so it ticks off: `has` (with `count`), `dead` (with `count`), `stage`, `finished`,
`at` (the player has been to the cell or place), `met` (the player has talked to the npc), `any`, `all`.
A `target` id may be a list when any of several people will do. The full format is at the top of
`tools/build_objectives.py`.

### Checking the data against the game files
- `tools/questgraph.py build` reads every dialogue line and script that changes a quest's journal, with its
  conditions (required stage, items, kills, speaker). `questgraph.py show <QuestId>` prints them.
- `tools/worklist.py` lists stages whose markers or sub-objectives look incomplete (a name in the text with no
  marker, a requirement no line mentions, a marker on something that does not move the quest), each with what
  the game files say about that stage. The flags are hints, not verdicts.
- Reviews are written as stage-level patches (`objectives/REVIEW_BRIEF.md` has the rules), checked with
  `build_objectives.py --check <patch>` and merged with `tools/apply_patches.py`.
- `tools/tests/` runs the panel code without the game: tick-off behaviour, and every quest at every stage.

Wiki-based objectives were written in our own words from the UESP walkthroughs. Quests from mods without a
wiki were written from the mods' own dialogue and scripts.
