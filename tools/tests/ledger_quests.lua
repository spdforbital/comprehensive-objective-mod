-- drives ledger.lua's Quests tab (quest finder) with a stubbed OpenMW API: search, track, marker, tick on talking
local MOD = os.getenv('MODDIR')
package.path = MOD .. '/?.lua;' .. package.path
local function stub()
  local s
  s = setmetatable({}, { __index = function() return s end, __call = function() return nil end,
    __concat = function() return '' end, __len = function() return 0 end })
  return s
end
local function vec(x, y, z) return { x = x or 0, y = y or 0, z = z or 0 } end
local state = { pos = vec(-22000, -15000, 600), cell = { isExterior = true, name = '', id = 'balmora' }, mode = nil, now = 0 }
local events, created, messages = {}, {}, {}
QUESTS, RANKS, TOPICS = {}, {}, {}
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
  Door = { isTeleport = function() return false end },
  NPC = withStub { getFactionRank = function(_, f) return RANKS[f] or 0 end },
  Player = withStub { quests = function() return setmetatable({}, { __index = function(_, id) return QUESTS[id] end }) end,
    journal = function() return { topics = TOPICS } end },
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


local KEY = require('openmw.input').KEY
script.engineHandlers.onKeyPress({ code = KEY.L })
expect('ledger window opens', window() ~= nil)
click('Quests')
local hint = find('you can start now')
expect('Quests tab shows counts (' .. tostring(hint and hint.text) .. ')', hint ~= nil)
search('missing mercenary')
expect('search finds The Missing Mercenary', find('The Missing Mercenary') ~= nil)
expect('mod name shown', find('mod: Balmora Guilds Expanded') ~= nil)
expect('how to start: ask Marsh-Axe about Wuleen-Shei', find('Ask Marsh-Axe about "Wuleen-Shei"') ~= nil)
click('Base game')
expect('base game filter hides the mod quest', find('The Missing Mercenary') == nil)
click('Mods')
expect('mods filter shows it', find('The Missing Mercenary') ~= nil)
click('All')
-- a base-game quest that needs earlier steps
search('code book')
expect('Code Book is not in Can start yet', find('Fighters Guild: The Code Book') == nil)
click('Locked')
local cb = find('Fighters Guild: The Code Book')
expect('Code Book is under Locked', cb ~= nil)
local needs = find('Needs:')
print('   ' .. tostring(needs and needs.text))
expect('reason names the earlier quest and the guild', needs and needs.text:find('Telvanni Agents', 1, true) and needs.text:find('join Fighters Guild', 1, true))
expect('base game quest labelled [Morrowind]', find('[Morrowind]') ~= nil)
QUESTS['fg_telvanni_agents'] = { stage = 100, finished = true }
RANKS['fighters guild'] = 2
click('Can start')
expect('after finishing the earlier quest and joining, Code Book can start', find('Fighters Guild: The Code Book') ~= nil)
local fs = find('to learn "code book"')
print('   ' .. tostring(fs and fs.text))
expect('it says how to learn the topic first', fs and fs.text:find('Eydis Fire-Eye', 1, true) ~= nil)
TOPICS['code book'] = { id = 'code book' }
search('code book ')
search('code book')
expect('once the topic is known the first step goes away', find('to learn "code book"') == nil and find('Fighters Guild: The Code Book') ~= nil)
-- a main quest topic you only learn later
search('hortator and nerevarine')
expect('Hortator is not in Can start', find('Hortator and Nerevarine') == nil)
click('Locked')
local hn = find('Hortator and Nerevarine')
local hw = find('Needs:')
print('   ' .. tostring(hw and hw.text))
expect('Hortator is listed once, under Locked', hn ~= nil)
expect('its reason mentions learning the topic or the earlier quests', hw and (hw.text:find('learn "', 1, true) or hw.text:find('finish', 1, true)))
local n = 0
for _, t in ipairs(texts()) do if t.text:find('Hortator and Nerevarine', 1, true) then n = n + 1 end end
expect('quest split into many journal ids shows as one entry (' .. n .. ')', n == 1)
click('Can start')
-- track how to start a quest
click('All'); search('missing mercenary')
click('[Track]')
script.engineHandlers.onUpdate(1.1)
local block
for i = #events, 1, -1 do if events[i][1] == 'CO_SetCustomBlock' then block = events[i][2]; break end end
local item = block and block.items and block.items[1]
print('   panel: ' .. tostring(item and item.text))
expect('panel line says how to start it', item and item.text:find('Start The Missing Mercenary: Ask Marsh-Axe', 1, true) ~= nil)
expect('marker on Marsh-Axe', item and item.marker and item.marker.objectIds and item.marker.objectIds[1] == 'luce_mio_bfg_marshaxe')
-- the quest starting ticks the line and drops it from the list
QUESTS['luce_miobfg_wuleen'] = { stage = 10, finished = false }
state.now = 3; script.engineHandlers.onUpdate(1.1)
for i = #events, 1, -1 do if events[i][1] == 'CO_SetCustomBlock' then block = events[i][2]; break end end
expect('starting the quest ticks the tracked line', block.items[1].done == true)
search('missing mercenary')
expect('a started quest leaves the list', find('The Missing Mercenary') == nil)
local saved = script.engineHandlers.onSave()
expect('tracked quest start is saved', saved.tracked[1] and saved.tracked[1].quest == 'luce_miobfg_wuleen' and saved.tracked[1].label ~= nil)
-- a script-started quest
search('')
click('All')
local t0 = os.clock()
click('Can start')
print(string.format('   redraw of the full list: %.0f ms', (os.clock() - t0) * 1000))
-- a Mournhold quest: no walking route, so no distance and no fake portal route
search('the warlords')
local wl = find('Ask Felvan Ienith')
print('   ' .. tostring(wl and wl.text))
expect('Mournhold giver says there is no road', wl and wl.text:find('no road there', 1, true) ~= nil)
print(fails == 0 and 'ALL PASS' or (fails .. ' FAILED'))
