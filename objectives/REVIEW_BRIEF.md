# Brief: second pass on quest objectives (markers and sub-objectives)

You are improving the data of the **Comprehensive Objective Mod**, an OpenMW Lua mod that shows, for the
player's current journal stage, a short checklist of what to do, with a compass/world marker and a live
distance for each line. The first pass wrote one or two lines per stage. Players found that many lines
bundle several steps into one sentence with a single marker, or have a marker on the wrong thing.

**The owner's request:** keep the text short. Do not add detail to the text. Put the detail into
**separate sub-objectives, each with its own correct marker and its own tick-off condition**.

Root: `~/games/extra-mods/comprehensive-objective-mod/`. Work from `tools/`.

## Your input and output
- Input: one worklist chunk, `tools/worklists/<chunk>.json` (given in your task). It lists quests; each has
  `review` entries (stage groups that a checker flagged) and `other_stages` (the rest, for context only).
- Output: ONE patch file, `tools/patches/<chunk>.json`, holding only the stages you changed:
  ```json
  { "<QuestId>": { "stages": { "<stage key>": [ objective, ... ] } } }
  ```
  A stage key is a stage number or several joined with commas (`"40,42"`), as in the worklist. Give the
  complete new objective list for that key. You may split a key (`"40"` and `"42"` separately) when the
  stages need different lists. Stages you leave out stay exactly as they are.
- Write nothing else. Do not edit `objectives/*.json`, the tools, the mod's Lua, other mods or openmw.cfg.
  Never launch, close or type into the game.

## What each review entry gives you
- `journal`: the journal text of those stages. `objectives`: the current lines (raw JSON).
- `game`: what the game files say can move the quest on from these stages. Dialogue lines show who must be
  talked to, about which topic, which items they require (`needs items`), which actors must be dead
  (`needs dead`), what is taken or given. Script lines show the object the script sits on and its conditions.
  Trust this over the current objectives. It lists everything that can fire from this stage onward, so later
  steps and failure branches show up too: use your judgment about which lines belong to this stage.
- `unmarked`: names found in the text that no marker in the stage covers, with candidate record ids and
  where they are placed.
- `flags`: `missing_item` / `missing_dead` (the game requires them but no line mentions them),
  `no_target` (no marker at all), `unrelated_target` (the marked thing is not what moves the quest).
- **The flags are hints from a noisy checker.** Many are false alarms: a name mentioned only as context
  ("ask about Sul-Matuul"), a requirement of a different branch or a later stage, a failure branch (the
  quest giver dying). When the current lines are already right, leave the stage out of your patch.

## The rules
1. **One step per line.** Each person to talk to, each item to get, each creature or person to kill and each
   place to go to is its own objective with its own `target`, in the order the player does them.
   "Go to the tomb, enter the vaults and take the hammer from the chest; return to X" becomes four lines.
2. **Every line that can tick off gets a `doneIf`:**
   - item to get: `{"has": "<item id>"}`, or `{"has": "<id>", "count": 5}` for "bring 5 of X"
     (the panel then shows 3/5).
   - kill: `{"dead": "<actor id>"}`, or `{"dead": "<id>", "count": 3}` for "kill 3 of them" when several
     share one record id (the panel then shows 1/3).
   - go to a place, when more steps follow: `{"at": true}` with a `cell` or `place` target, or
     `{"at": "<interior cell or named outdoor cell>"}`. It ticks once the player has been there.
   - talk to someone when that talk does NOT change the journal stage (asking around, gathering info):
     `{"met": true}` with an `npc` target. It ticks once the player has opened dialogue with them.
   - a step that ends when this or another quest reaches a stage: `{"stage": {"quest": "<id>", "atLeast": n}}`.
   - combine with `{"any": [...]}` / `{"all": [...]}`.
   The line whose completion changes the journal stage (usually the final "report to X") needs no `doneIf`.
3. **The marker must be on the thing the line is about.** A "talk to X" line targets the npc X, not the
   building. An item line targets the item (the builder also marks a unique container or carrier). Use
   `"in": "<interior cell>"` to pick the right placement when an id is placed in several cells, or to route to
   the cell where a script puts an unplaced actor.
4. **Alternatives.** "Report to any of these four people": one line with a list target,
   `"target": {"npc": ["id a", "id b", "id c"]}`. A genuinely different way to do the step: its own line
   starting with "Or", marked `"optional": true`.
5. **Requirements from `game`.** Items the advancing dialogue needs get their own "Get ..." lines before the
   hand-in line (unless the player already has them from an earlier stage of this quest). Actors that must be
   dead get their own "Kill ..." lines. Don't add requirements that belong to another branch.
6. **Text.** Keep each `do` short (aim for under 50 characters) and in the existing voice: imperative, plain.
   When you split a line, reuse its wording. Move location hints into `where` (a short place name). Don't
   restate the journal. Don't add flavour, tips or spoilers that the current line didn't have.
7. **Exact ids only.** Every id and cell name must exist in this load order: take them from the worklist
   (`candidates`, `game`) or look them up. Never guess an id.
8. Optional steps keep `"optional": true`. Keep existing `where`, `optional`, `note` fields on lines you keep.
   Strings that start with `@` in a list are shared lists: keep them as they are.
9. Don't use the web or the browser. The game files are the authority. If something can't be settled from
   the worklist and the tools, leave that stage as it is and mention it in your report.

## Objective format
```json
{"do": "Take the Dwemer Puzzle Box", "where": "Arkngthand, Cells of Hollow Hand",
 "target": {"item": "misc_dwrv_ark_cube00"}, "doneIf": {"has": "misc_dwrv_ark_cube00"}}
```
`target` has exactly one of `npc`, `creature`, `item`, `object` (activator, container, door), `cell`
(interior cell name), `place` (named outdoor cell such as "Urshilaku Camp"); plus optional `in` and `via`
(an interior cell whose outdoor route is used when the target's own cell has none).

### Example
Before (one line, one marker):
```json
"5,7": [{"do": "Get the puzzle box from Arkngthand (Cells of Hollow Hand) and give it to Hasphat",
         "target": {"npc": "hasphat antabolis"}}]
```
After:
```json
"5,7": [
 {"do": "Go to Arkngthand", "target": {"cell": "Arkngthand, Weepingbell Hall"}, "doneIf": {"at": true}},
 {"do": "Take the Dwemer Puzzle Box", "where": "Cells of Hollow Hand",
  "target": {"item": "misc_dwrv_ark_cube00"}, "doneIf": {"has": "misc_dwrv_ark_cube00"}},
 {"do": "Give the puzzle box to Hasphat Antabolis", "where": "Fighters Guild, Balmora",
  "target": {"npc": "hasphat antabolis"}}
]
```

## Tools (run from `tools/`, plain `python3`)
- `python3 build_objectives.py --check patches/<chunk>.json` : validates your patch against the load order
  in about 3 seconds and writes nothing. **Run it after every batch of edits. Finish with 0 errors**, and
  fix warnings that are about your own lines where you can (for example "placed in N cells": add `in`).
  A warning that a cell has no outdoor route is fine.
- `python3 questgraph.py show <QuestId>` : every dialogue line and script that moves that quest.
- `python3 world.py journal <QuestId>` : full journal text per stage.
- `python3 world.py find <text>` : search record ids and names, with placements.
- `python3 world.py where <id>` : placements, and who carries or contains an item.
- `python3 world.py cell "<interior cell name>"` : the door route into a cell.
Each call takes about 3 seconds, so prefer the worklist data and batch your lookups.

## How to work
Go through the chunk quest by quest. For each review entry decide: already right (skip), or rewrite.
Write the patch file early and extend it as you go, validating in batches, so partial work is never lost.
The patch must be valid JSON.

## Report back (short)
Stages reviewed, stages changed, stages left unchanged, and a list of anything you could not settle or
that looks wrong in the game data (quest id + one line each).
