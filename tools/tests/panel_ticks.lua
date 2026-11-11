-- fake OpenMW API, just enough to drive player.lua
local MOD = os.getenv('MODDIR')
package.path = MOD .. '/?.lua;' .. package.path
local state = { cell = { name = 'Balmora', isExterior = true, id = 'balmora' }, inv = {}, quests = {}, entries = {}, mode = nil, actors = {} }
local function vec(x, y, z)
  local v = { x = x or 0, y = y or 0, z = z or 0 }
  return setmetatable(v, { __sub = function(a, b) return vec(a.x - b.x, a.y - b.y, a.z - b.z) end,
    __index = { length = function(s) return math.sqrt(s.x ^ 2 + s.y ^ 2 + s.z ^ 2) end } })
end
local created = {}
package.preload['openmw.core'] = function() return {
  getGameTime = function() return 0 end, getRealTime = function() return state.now or 0 end, contentFiles = { list = {} }, getGMST = function() return 0 end,
  dialogue = { journal = { records = setmetatable({}, { __index = function(_, id) return { questName = id, infos = {} } end }) } },
  magic = { EFFECT_TYPE = {} } } end
package.preload['openmw.self'] = function() return setmetatable({ sendEvent = function() end },
  { __index = function(_, k) if k == 'cell' then return state.cell elseif k == 'position' then return vec(0, 0, 0)
    elseif k == 'rotation' then return { getYaw = function() return 0 end } end end }) end
package.preload['openmw.types'] = function() return {
  Player = { quests = function() return setmetatable({}, { __index = function(_, id) local q = state.quests[id]; return q and { stage = q.stage, finished = q.fin } or { stage = 0, finished = false } end }) end,
             journal = function() return { journalTextEntries = state.entries } end },
  Actor = { inventory = function() return { countOf = function(_, id) return state.inv[id] or 0 end } end,
            isDead = function(a) return a.dead end, stats = {} },
  Door = { isTeleport = function() return false end } } end
package.preload['openmw.ui'] = function() return { TYPE = { Text = 1, Image = 2 }, ALIGNMENT = { End = 1 },
  content = function(t) return t end, texture = function(t) return t end, screenSize = function() return vec(1920, 1080) end,
  create = function(l) local e = { layout = l, update = function() end, destroy = function() end }; created[#created + 1] = e; return e end,
  showMessage = function() end } end
package.preload['openmw.util'] = function() return { vector2 = function(x, y) return vec(x, y) end, vector3 = vec,
  color = { rgb = function(r, g, b) return { r = r, g = g, b = b } end }, normalizeAngle = function(a) return a end } end
package.preload['openmw.input'] = function() return { KEY = { K = 1 }, CONTROLLER_BUTTON = { DPadUp = 1 } } end
package.preload['openmw.nearby'] = function() return setmetatable({}, { __index = function(_, k) if k == 'actors' then return state.actors end return {} end }) end
package.preload['openmw.camera'] = function() return { viewportToWorldVector = function() return vec(0, 1, 0) end } end
package.preload['openmw.interfaces'] = function() return { UI = { getMode = function() return state.mode end } } end
package.preload['openmw.async'] = function() return {} end
package.preload['openmw.storage'] = function() return {} end

local chunk = assert(loadfile(MOD .. '/scripts/comprehensive_objectives/player.lua'))
local script = chunk()
local function tick() script.engineHandlers.onFrame(1.1) end
local function lines()
  local out = {}
  local e = created[#created]
  for _, w in ipairs(e and e.layout.content or {}) do if w.props and w.props.text then out[#out + 1] = w.props.text end end
  return out
end
local function show(label) print('--- ' .. label); for _, l in ipairs(lines()) do print('   ' .. l) end end
local function setq(id, stage) state.quests[id] = { stage = stage, fin = false }; state.entries[#state.entries + 1] = { questId = id, text = 'x' } end
local fails = 0
local function expect(label, cond) if not cond then fails = fails + 1 end print((cond and 'PASS ' or 'FAIL ') .. label) end
local function has(s) for _, l in ipairs(lines()) do if l:find(s, 1, true) then return l end end end

script.engineHandlers.onInit()
-- 1. arrival tick + item tick (Bonebiter Bow)
setq('a2_1_meetsulmatuul', 40); tick(); show('Sul-Matuul stage 40, in Balmora')
expect('3 lines, none ticked', has('Go to the Urshilaku Burial Caverns') and not has('X  Go to'))
state.cell = { name = 'Urshilaku, Astral Burial', isExterior = false, id = 'urshilaku, astral burial' }; tick()
expect('arrival ticks the go-to line', has('X  Go to the Urshilaku Burial Caverns') ~= nil)
state.cell = { name = 'Urshilaku, Juno Burial', isExterior = false }; tick()
expect('arrival stays ticked after leaving', has('X  Go to the Urshilaku Burial Caverns') ~= nil)
state.inv['bonebiter_bow_unique'] = 1; tick(); show('with the bow')
expect('bow line ticks', has('X  Take the Bonebiter Bow') ~= nil)
-- save / load keeps the arrival tick
local saved = script.engineHandlers.onSave()
script.engineHandlers.onLoad(saved); state.inv['bonebiter_bow_unique'] = nil; tick()
expect('arrival tick survives save/load', has('X  Go to the Urshilaku Burial Caverns') ~= nil)
-- 2. count display (two scrolls) and talked-to tick
setq('a2_4_milogone', 10); tick(); show('Milo stage 10')
expect('count shows 0/2', has('(0/2)') ~= nil)
state.inv['sc_divineintervention'] = 1; tick(); expect('count shows 1/2', has('(1/2)') ~= nil)
state.inv['sc_divineintervention'] = 2; tick(); expect('scroll line ticks at 2', has('X  Get two Scrolls') ~= nil)
state.quests['a2_4_milogone'].stage = 20; tick(); show('Milo stage 20')
expect('Blatta line open', has('Blatta') and not has('X  Tell Blatta'))
script.eventHandlers.UiModeChanged({ newMode = 'Dialogue', arg = { recordId = 'someone else' } }); tick()
expect('talking to someone else does not tick', not has('X  Tell Blatta'))
script.eventHandlers.UiModeChanged({ newMode = 'Dialogue', arg = { recordId = 'blatta hateria' } }); tick(); show('after talking to Blatta')
expect('talking to Blatta ticks her line', has('X  Tell Blatta') ~= nil)
-- 3. plain kill tick still works
setq('fg_telvanni_agents', 1); tick(); show('Telvanni agents')
state.actors = { { recordId = 'alveleg', id = 'obj1', dead = true, position = vec(1, 1, 1) } }; tick()
expect('kill line ticks', has('X  Kill Alveleg') ~= nil)
-- 4. tracked quest keeps the panel; Quest Guider's automatic re-track after a journal update does not steal it
local function title() return lines()[1] end
state.now = 100
script.eventHandlers.CO_FocusQuest({ questId = 'MG_NchuleftBook' })   -- player pressed Track
setq('mg_nchuleftbook', 10); tick()
expect('tracked quest shown first (' .. tostring(title()) .. ')', title() == 'mg_nchuleftbook')
state.now = 200
setq('mv_victimromance', 40)
if script.engineHandlers.onQuestUpdate then script.engineHandlers.onQuestUpdate('MV_VictimRomance', 40) end            -- another quest updates ...
state.now = 200.5
script.eventHandlers.CO_FocusQuest({ questId = 'MV_VictimRomance' })  -- ... and Quest Guider auto-tracks it
tick()
expect('automatic re-track ignored (' .. tostring(title()) .. ')', title() == 'mg_nchuleftbook')
state.now = 300
script.eventHandlers.CO_FocusQuest({ questId = 'FG_Telvanni_agents' }) -- player tracks a different quest
tick()
expect('pressing Track switches the panel (' .. tostring(title()) .. ')', title() == 'fg_telvanni_agents')
print(fails == 0 and 'ALL PASS' or (fails .. ' FAILED'))
