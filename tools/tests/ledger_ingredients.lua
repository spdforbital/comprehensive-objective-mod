-- drives ledger.lua's Ingredients tab and tracked-copy arrows with a stubbed OpenMW API: search, track, marker, tick on talking
local MOD = os.getenv('MODDIR')
package.path = MOD .. '/?.lua;' .. package.path
local function stub()
  local s
  s = setmetatable({}, { __index = function() return s end, __call = function() return nil end,
    __concat = function() return '' end, __len = function() return 0 end })
  return s
end
local function vec(x, y, z) return { x = x or 0, y = y or 0, z = z or 0 } end
local state = { pos = vec(tonumber(os.getenv('PX') or -11000), tonumber(os.getenv('PY') or -71000), 300), cell = { isExterior = true, name = '', id = 'seyda neen' }, mode = nil, now = 0 }
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
local function click(s) local t = find(s); assert(t and t.click, 'no clickable: ' .. s); local c0 = os.clock(); t.click(); if os.getenv('VERBOSE') then print(string.format('   click %s (%s): %.2fs', s, t.text, os.clock() - c0)) end end
local function search(q)
  -- the search box is its own element; its textChanged handler sets the query
  for i = #created, 1, -1 do
    local e = created[i]
    local c = e.layout and e.layout.content and e.layout.content[1]
    if c and c.events and c.events.textChanged then c.events.textChanged(q); return end
  end
  error('no search box')
end


local KEY = require('openmw.input').KEY
script.engineHandlers.onKeyPress({ code = KEY.L })
click('Ingredients')
search('marshmerrow')
local row = find('Marshmerrow')
if os.getenv('DUMP') then for _, t in ipairs(texts()) do print('   | ' .. t.text) end end
print('   row: ' .. (row and row.text or '?'))
local nearest = row and tonumber(row.text:match('nearest ([%d%.]+) cells'))
expect('marshmerrow listed with a nearest distance (' .. tostring(nearest) .. ' cells)', nearest ~= nil)
local expected = tonumber(os.getenv('EXPECT') or '-1')
expect(string.format('nearest easy copy matches independent check (%.2f vs %.2f cells)', nearest or -1, expected),
       nearest and math.abs(nearest - expected) < 0.06)
local line
for _, t in ipairs(texts()) do if t.text:find('regrowing plant', 1, true) or t.text:find("plant (doesn't regrow)", 1, true) then line = t.text end end
expect('source type is spelled out (' .. tostring(line) .. ')', line ~= nil)
click('[Track]')
click('Tracked')
local pos = find('/')
for _, t in ipairs(texts()) do if t.text:match('^%d+/%d+$') then pos = t end end
print('   copy: ' .. (pos and pos.text or '?'))
local r1, n = pos.text:match('^(%d+)/(%d+)$')
expect('tracked copy shows its place in the nearest-first order', tonumber(n) and tonumber(n) > 10)
local function dist()
  for _, t in ipairs(texts()) do local d = t.text:match('   ([%d%.]+) cells') if d then return tonumber(d), t.text end end
end
local d1 = dist()
click('[>]')
local r2 = nil; for _, t in ipairs(texts()) do if t.text:match('^%d+/%d+$') then r2 = t.text end end
local d2, l2 = dist()
expect('[>] moves to the next copy (' .. tostring(r2) .. ', ' .. tostring(d2) .. ' cells)', r2 and r2 ~= pos.text and d2 and d2 >= (d1 or 0) - 0.05)
click('[>]'); click('[>]')
local d4 = dist()
expect('copies get farther as you step on (' .. tostring(d4) .. ' >= ' .. tostring(d2) .. ')', d4 and d4 >= d2 - 0.05)
click('[<]'); click('[<]'); click('[<]')
local r0 = nil; for _, t in ipairs(texts()) do if t.text:match('^%d+/%d+$') then r0 = t.text end end
expect('[<] goes back to where it started (' .. tostring(r0) .. ')', r0 == pos.text)
-- lock levels: track an item in the Heran tomb by stepping until its row names it
local found
for i = 1, tonumber(os.getenv('STEPS') or 400) do
  for _, t in ipairs(texts()) do if t.text:find('Heran Ancestral Tomb', 1, true) then found = t.text end end
  if found then break end
  click('[>]')
end
print('   heran row: ' .. tostring(found))
expect('Heran tomb copy shows its inner locked doors', found and found:find('locked doors inside: 10, 80, 100', 1, true) ~= nil)
print(fails == 0 and 'ALL PASS' or (fails .. ' FAILED'))
