# Panel tests (no game needed)

These run `scripts/comprehensive_objectives/player.lua` against a small fake of the OpenMW Lua API.

```bash
MODDIR=/path/to/comprehensive-objective-mod texlua panel_ticks.lua   # arrival / talked-to / count / kill tick-offs
MODDIR=/path/to/comprehensive-objective-mod texlua panel_smoke.lua   # every quest at every stage builds without errors
```

Any Lua 5.3 interpreter works in place of `texlua`. Run both after rebuilding the objective data.
