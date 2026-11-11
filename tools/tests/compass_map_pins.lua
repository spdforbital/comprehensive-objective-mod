-- drives skyrim_compass/map_markers.lua with a fake Advanced World Map widget that copies the real
-- createMarker rule: an existing id is left untouched unless params.update is set
local SRC = os.getenv('SRC')
local handlers = {}
package.preload['openmw.ui'] = function() return { texture = function(t) return t end, content = function(t) return t end,
  TYPE = { Text = 1 }, ALIGNMENT = { Center = 1 } } end
package.preload['openmw.util'] = function() return { vector2 = function(x, y) return { x = x, y = y } end,
  vector3 = function(x, y, z) return { x = x, y = y, z = z } end, color = { rgb = function() return {} end } } end
package.preload['openmw.interfaces'] = function() return { AdvancedWorldMap = { events = {
  registerHandler = function(name, fn) handlers[name] = fn end } } } end
local function newWidget()
  local w = { LAYER = { nonInteractive = 1, marker = 2 }, pins = {} }
  function w:createImageMarker(p)
    if self.pins[p.id] and not p.update then return p.id end
    self.pins[p.id] = { x = p.pos.x, y = p.pos.y, name = p.tooltipContent and p.tooltipContent[1].props.text }
    return p.id
  end
  function w:removeMarker(id) local had = self.pins[id] ~= nil; self.pins[id] = nil; return had end
  return w
end
local script = assert(loadfile(SRC))()
script.engineHandlers.onFrame()
local set = script.eventHandlers['SkyrimCompass:setMarkers']
local fails = 0
local function quest(widget)
  local out = {}
  for id, p in pairs(widget.pins) do if id:find('skyrim_compass_quest_', 1, true) then out[#out + 1] = p end end
  table.sort(out, function(a, b) return (a.name or '') < (b.name or '') end)
  return out
end
local function expect(label, ok) if not ok then fails = fails + 1 end print((ok and 'PASS ' or 'FAIL ') .. label) end
local w = newWidget()
handlers.onMapShown({ mapWidget = w, isNew = true })
set({ { x = 100, y = 100, name = 'Quest A target' }, { x = 200, y = 200, name = 'Quest B target' }, { x = 300, y = 300, name = 'Quest C target' } })
expect('3 pins for 3 targets', #quest(w) == 3)
-- quest A and B finish: only C remains
set({ { x = 300, y = 300, name = 'Quest C target' } })
local q = quest(w)
expect('finished quests disappear (1 pin left, got ' .. #q .. ')', #q == 1)
expect('remaining pin is Quest C at its spot', q[1] and q[1].name == 'Quest C target' and q[1].x == 300)
-- map closed and opened again later with a new list
handlers.onMapClosed({}); handlers.onMapShown({ mapWidget = w, isNew = false })
set({ { x = 900, y = 900, name = 'Quest D target' } })
q = quest(w)
expect('reopened map shows only the new target', #q == 1 and q[1].name == 'Quest D target' and q[1].x == 900)
set({})
expect('empty list clears all quest pins', #quest(w) == 0)
print(fails == 0 and 'ALL PASS' or (fails .. ' FAILED'))
