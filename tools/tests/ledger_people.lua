-- drives ledger.lua's People tab with a stubbed OpenMW API: search, track, marker, tick on talking
local MOD = os.getenv('MODDIR')
package.path = MOD .. '/?.lua;' .. package.path
local function stub()
  local s
  s = setmetatable({}, { __index = function() return s end, __call = function() return nil end,
    __concat = function() return '' end, __len = function() return 0 end })
  return s
end
local function vec(x, y, z) return { x = x or 0, y = y or 0, z = z or 0 } end
local state = { pos = vec(-14000, 197000, 300), cell = { isExterior = true, name = '', id = 'solstheim' }, mode = nil, now = 0 }
local events, created, messages = {}, {}, {}
local function withStub(t) return setmetatable(t, { __index = function() return stub() end }) end
package.preload['openmw.core'] = function() return withStub {
  getSimulationTime = function() return state.now end, getRealTime = function() return state.now end,
  contentFiles = { list = {} }, getGMST = function() return nil end, API_REVISION = 90,
  magic = stub(), stats = stub(), dialogue = stub() } end
package.preload['openmw.self'] = function() return setmetatable({ sendEvent = function(_, name, data) events[#events + 1] = { name, data } end },
  { __index = function(_, k) if k == 'cell' then return state.cell elseif k == 'position' then return state.pos end return stub() end }) end
package.preload['openmw.types'] = function() return withStub {
  Actor = withStub { inventory = function() return { countOf = function() return 0 end, getAll = function() return {} end } end,
                     getEquipment = function() return {} end, stats = stub(), spells = function() return {} end },
  Weapon = withStub { TYPE = withStub {}, records = {} }, Armor = withStub { TYPE = withStub {}, records = {} },
  Clothing = withStub { TYPE = withStub {}, records = {} },
  Door = { isTeleport = function() return false end }, NPC = stub(), Player = stub(),
  -- records with real (empty) lists so loops over them end
  Ingredient = { records = setmetatable({}, { __index = function(_, id)
    local name = id:gsub('^ingred_', ''):gsub('_%d+$', ''):gsub('_', ' '):gsub('^%l', string.upper)
    return { name = name, effects = {} } end }) },
  Book = { records = {} } } end
package.preload['openmw.ui'] = function() return withStub {
  TYPE = withStub {}, ALIGNMENT = withStub {}, content = function(t) return t end, texture = function(t) return t end,
  create = function(l) local e = { layout = l, update = function() end, destroy = function(self) self.dead = true end }
    created[#created + 1] = e; return e end,
  showMessage = function(m) messages[#messages + 1] = m end } end
package.preload['openmw.util'] = function() return withStub { vector2 = vec, vector3 = vec,
  color = { rgb = function(r, g, b) return { r, g, b } end } } end
package.preload['openmw.input'] = function() return withStub { KEY = { L = 'L', K = 'K' }, CONTROLLER_BUTTON = {},
  triggers = {}, registerTrigger = function() end, registerTriggerHandler = function() end } end
package.preload['openmw.nearby'] = function() return withStub { doors = {}, actors = {}, items = {}, containers = {} } end
package.preload['openmw.async'] = function() return withStub { callback = function(_, f) return f end } end
package.preload['openmw.storage'] = function() return withStub { playerSection = function() return withStub { get = function() return nil end, set = function() end } end } end
package.preload['openmw.interfaces'] = function() return withStub {
  UI = withStub { getMode = function() return state.mode end, addMode = function(m) state.mode = m end,
                  removeMode = function() state.mode = nil end, setMode = function(m) state.mode = m end },
  MWUI = withStub { templates = withStub {} }, Settings = stub() } end

local script = assert(loadfile(MOD .. '/scripts/comprehensive_objectives/ledger.lua'))()
local fails = 0
local function expect(label, ok) if not ok then fails = fails + 1 end print((ok and 'PASS ' or 'FAIL ') .. label) end
if script.engineHandlers.onInit then script.engineHandlers.onInit() end

-- the ledger window is the largest created element; collect its texts and clickable callbacks
local function window()
  for i = #created, 1, -1 do
    local e = created[i]
    if not e.dead and e.layout and e.layout.layer == 'Windows' and e.layout.content and e.layout.content[1]
       and e.layout.content[1].content and #e.layout.content[1].content > 5 then return e end
  end
end
local function texts()
  local out = {}
  local w = window(); if not w then return out end
  for _, t in ipairs(w.layout.content[1].content) do
    if t.props and t.props.text then out[#out + 1] = { text = t.props.text, click = t.events and t.events.mouseClick } end
  end
  return out
end
local function find(s) for _, t in ipairs(texts()) do if t.text:find(s, 1, true) then return t end end end
local function click(s) local t = find(s); assert(t and t.click, 'no clickable: ' .. s); t.click() end
local function search(q)
  -- the search box is its own element; its textChanged handler sets the query
  for i = #created, 1, -1 do
    local e = created[i]
    local c = e.layout and e.layout.content and e.layout.content[1]
    if c and c.events and c.events.textChanged then c.events.textChanged(q); return end
  end
  error('no search box')
end

script.engineHandlers.onKeyPress({ code = nil })
-- open the ledger the way the L key does (fallback path when triggers are unavailable)
local KEY = require('openmw.input').KEY
script.engineHandlers.onKeyPress({ code = KEY.L })
expect('ledger window opens', window() ~= nil)
click('People')
expect('People tab shows nearest people with a hint', find('Nearest:') ~= nil)
search('falx carius')
expect('search finds Falx Carius', find('Falx Carius') ~= nil)
local row = find('Falx Carius')
print('   row: ' .. (row and row.text or '?'))
local where
for _, t in ipairs(texts()) do if t.text:find('Fort Frostmoth', 1, true) then where = t.text end end
expect('his location is shown (' .. tostring(where) .. ')', where ~= nil)
click('[Track]')
expect('tracking message shown', messages[#messages] and messages[#messages]:find('tracking Captain Falx Carius', 1, true) ~= nil)
script.engineHandlers.onUpdate(1.1)
local block
for i = #events, 1, -1 do if events[i][1] == 'CO_SetCustomBlock' then block = events[i][2]; break end end
local item = block and block.items and block.items[1]
expect('panel line "Find Captain Falx Carius"', item and item.text:find('Find Captain Falx Carius', 1, true) ~= nil)
expect('marker follows the live person (objectIds)', item and item.marker and item.marker.objectIds and item.marker.objectIds[1] == 'falx carius')
local doors = 0
for _, p in ipairs(item and item.marker.positions or {}) do if p.door then doors = doors + 1 end end
expect('marker has his spot plus ' .. doors .. ' route door(s)', item and #item.marker.positions >= 1)
-- class / faction / service search
search('trainer')
expect('searching "trainer" lists trainers', find('trainer') ~= nil)
search('zzqqxx')
expect('no match message', find('Nobody matches') ~= nil)
-- talking to him ticks the tracked line
script.eventHandlers.UiModeChanged({ newMode = 'Dialogue', arg = { recordId = 'falx carius' } })
state.now = 5; script.engineHandlers.onUpdate(1.1)
for i = #events, 1, -1 do if events[i][1] == 'CO_SetCustomBlock' then block = events[i][2]; break end end
expect('talking to him ticks the line', block.items[1].done == true)
-- save / load keeps a tracked person
local saved = script.engineHandlers.onSave()
local kept
for _, e in ipairs(saved.tracked) do if e.kind == 'npc' and e.marker then kept = true end end
expect('tracked person is saved with marker', kept)
print(fails == 0 and 'ALL PASS' or (fails .. ' FAILED'))
