# Panel tests (no game needed)

These run `scripts/comprehensive_objectives/player.lua` against a small fake of the OpenMW Lua API.

```bash
MODDIR=/path/to/comprehensive-objective-mod texlua panel_ticks.lua   # arrival / talked-to / count / kill tick-offs
MODDIR=/path/to/comprehensive-objective-mod texlua panel_smoke.lua   # every quest at every stage builds without errors
```

Any Lua 5.3 interpreter works in place of `texlua`. Run both after rebuilding the objective data.

`compass_map_pins.lua` checks the Quest Markers Plus compass's world-map pins (they must move and disappear
when the quest targets change):

```bash
SRC=/path/to/quest-markers-plus/scripts/skyrim_compass/map_markers.lua texlua compass_map_pins.lua
```
