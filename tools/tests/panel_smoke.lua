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
  getGameTime = function() return 0 end, contentFiles = { list = {} }, getGMST = function() return 0 end,
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
local DATA = require('scripts.comprehensive_objectives.objectives_data')
local realprint = print
local problems, n, shown = {}, 0, 0
print = function(...) local t = table.concat({...}, ' ')
  if t:find('error', 1, true) or t:find('render:', 1, true) or t:find('markers:', 1, true) or t:find('live:', 1, true) or (t:find('%[Comprehensive Objectives%] ') and not t:find(' :: ')) then problems[#problems + 1] = t end end
for id, q in pairs(DATA.quests) do
  for stage in pairs(q.stages or {}) do
    state.quests = { [id] = { stage = stage, fin = false } }
    state.entries = { { questId = id, text = 'x' } }
    local before = #problems
    local ok, err = pcall(tick)
    if not ok then problems[#problems + 1] = id .. ' ' .. stage .. ' THREW ' .. tostring(err) end
    if #problems > before then problems[#problems] = id .. '#' .. stage .. ': ' .. problems[#problems] end
    n = n + 1
    if #lines() > 1 then shown = shown + 1 end
  end
end
print = realprint
print(n .. ' quest stages driven, ' .. shown .. ' showed objective lines, ' .. #problems .. ' problems')
for i = 1, math.min(#problems, 15) do print(problems[i]) end
