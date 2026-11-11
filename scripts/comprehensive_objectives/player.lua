-- Comprehensive Objective Mod: hand-checked quest objectives and markers.
-- Objective HUD
-- * Curated quests (objectives/*.json -> objectives_data.lua): shows what to do for the
--   current journal stage as a checklist and puts proximityTool / HUD markers on the targets.
-- * Other quests: shows the "what to do" sentence picked from the latest journal entry.
-- K toggles the panel. Markers are temporary (never written into saves).
local core = require('openmw.core')
local self = require('openmw.self')
local types = require('openmw.types')
local ui = require('openmw.ui')
local util = require('openmw.util')
local input = require('openmw.input')
local nearby = require('openmw.nearby')
local camera = require('openmw.camera')
local I = require('openmw.interfaces')

local MAX_CURATED = 3      -- curated quest blocks in the panel
local MAX_OTHER = 2        -- non-curated quests (heuristic line)
local MAX_ITEMS = 8        -- objective lines in the newest curated block
local MAX_ITEMS_OTHER = 3  -- objective lines in the older curated blocks (no 'where' line)
local WIDTH = 560
local UPDATE_EVERY = 1.0   -- full refresh (journal, markers)
local LIVE_EVERY = 0.1     -- distances and arrows
local GROUP_SUFFIX = ' (objectives)'
local MOD_NAME = 'comprehensive_objectives'
local HUDM_ICON = 'textures/icons/quest_guider/HUDMarker.dds'
local MARKER_RANGE = 1000000  -- game units; show objective markers from anywhere
local DOOR_ICON = 'textures/icons/quest_guider/toDoorIcon.dds'

local titleColor = util.color.rgb(0.87, 0.72, 0.42)
local textColor = util.color.rgb(0.93, 0.91, 0.86)
local doneColor = util.color.rgb(0.55, 0.55, 0.52)
local nearestColor = util.color.rgb(1.0, 0.93, 0.62)  -- the objective you're closest to
local whereColor = util.color.rgb(0.66, 0.74, 0.80)

---------------------------------------------------------------------------
-- curated data
---------------------------------------------------------------------------
local okData, DATA = pcall(require, 'scripts.comprehensive_objectives.objectives_data')
if not okData or type(DATA) ~= 'table' then
    print('[Comprehensive Objectives] no curated objective data: ' .. tostring(DATA))
    DATA = { quests = {} }
end
local CQ = DATA.quests or {}

local CHILDREN = {}
local DEADWATCH = {}
local function watchDead(c)
    if not c then return end
    if c.kind == 'dead' then DEADWATCH[c.id] = true end
    if c.list then
        for _, x in ipairs(c.list) do watchDead(x) end
    end
end
local function scanLists(q)
    for _, l in pairs({ q.start or {}, q.after or {} }) do
        for _, o in ipairs(l) do watchDead(o.done) end
    end
    for _, l in pairs(q.stages or {}) do
        for _, o in ipairs(l) do watchDead(o.done) end
    end
end
for id, q in pairs(CQ) do
    if q.parent then
        CHILDREN[q.parent] = CHILDREN[q.parent] or {}
        table.insert(CHILDREN[q.parent], id)
    end
    scanLists(q)
end
for _, l in pairs(CHILDREN) do table.sort(l) end

---------------------------------------------------------------------------
-- saved state: actors we saw dead (for "kill X" objectives)
---------------------------------------------------------------------------
local killed = {}

---------------------------------------------------------------------------
-- heuristic objective line for non-curated quests (unchanged behaviour)
---------------------------------------------------------------------------
local cues = {
    "i should", "i must", "i need", "i'm to", "i am to", "i'll have to", "i have to",
    "told me to", "wants me to", "asked me to", "sent me", "my orders", "i'm supposed",
    "return to", "report", "bring", "go to", "find ", "speak with", "talk to", "meet ",
    "deliver", "take it", "take the", "retrieve", "kill", "will follow", "will answer",
    "wait for", "ask ", "look for",
}

local abbreviations = { "St", "Mt", "Gro", "Gra" }

local function splitSentences(text)
    local out = {}
    text = text:gsub("%s+", " ")
    -- keep "St. Olms" and similar in one sentence
    for _, a in ipairs(abbreviations) do
        text = text:gsub("(%f[%a]" .. a .. ")%. ", "%1\1 ")
    end
    for s in text:gmatch("[^%.!%?]+[%.!%?]*") do
        s = s:gsub("^%s+", ""):gsub("%s+$", ""):gsub("\1", ".")
        if #s > 0 then out[#out + 1] = s end
    end
    return out
end

-- Score a sentence: instructions and names of people/places count most.
local function score(sentence)
    local low = sentence:lower()
    local sc = 0
    for _, c in ipairs(cues) do
        if low:find(c, 1, true) then sc = sc + 3 end
    end
    local first = true
    for word in sentence:gmatch("%S+") do
        if not first and word:match("^%u%l") and word ~= "I" then sc = sc + 1 end
        first = false
    end
    return sc
end

-- Pick the sentence(s) that say what to do; fall back to the whole entry.
local function objectiveFrom(text)
    local sentences = splitSentences(text or "")
    if #sentences <= 2 then return table.concat(sentences, " ") end
    local best, bestScore = #sentences, -1
    for i, s in ipairs(sentences) do
        local sc = score(s)
        if sc > bestScore then best, bestScore = i, sc end
    end
    local s = sentences[best]
    -- add a short follow-up sentence, which usually gives the place or reason
    local nxt = sentences[best + 1]
    if nxt and #s + #nxt < 240 and score(nxt) > 0 then
        s = s .. " " .. nxt
    end
    return s
end

---------------------------------------------------------------------------
-- quest state / conditions
---------------------------------------------------------------------------
local questsObj
local inventory

local function qstate(id)
    if not questsObj or not id then return 0, false end
    local ok, q = pcall(function() return questsObj[id] end)
    if not ok or not q then return 0, false end
    local okS, stage = pcall(function() return q.stage end)
    local okF, fin = pcall(function() return q.finished end)
    return (okS and stage) or 0, (okF and fin) and true or false
end

local function has(id)
    if not inventory then return false end
    local ok, n = pcall(function() return inventory:countOf(id) end)
    return ok and (n or 0) > 0
end

local function cond(c)
    if not c then return false end
    local k = c.kind
    if k == 'stage' then
        local s = qstate(c.quest)
        return s >= c.n
    elseif k == 'finished' then
        local _, f = qstate(c.quest)
        return f
    elseif k == 'has' then
        return has(c.id)
    elseif k == 'dead' then
        return killed[c.id] == true
    elseif k == 'any' then
        for _, x in ipairs(c.list or {}) do
            if cond(x) then return true end
        end
        return false
    elseif k == 'all' then
        local list = c.list or {}
        for _, x in ipairs(list) do
            if not cond(x) then return false end
        end
        return #list > 0
    end
    return false
end

-- remember watched actors that are dead in the loaded cells
local function scanDead()
    if next(DEADWATCH) == nil then return end
    for _, a in ipairs(nearby.actors) do
        local rid = a.recordId
        if DEADWATCH[rid] and not killed[rid] then
            local ok, dead = pcall(function() return types.Actor.isDead(a) end)
            if ok and dead then killed[rid] = true end
        end
    end
end

-- which plugins are loaded (lowercase), for mod variants
local LOADED = {}
pcall(function()
    for _, f in ipairs(core.contentFiles.list) do LOADED[f:lower()] = true end
end)

-- same hash as tools/build_objectives.py (djb2 mod 2^31-1)
local function textHash(t)
    local h = 5381
    for i = 1, #t do h = (h * 33 + t:byte(i)) % 2147483647 end
    return h
end

-- the journal text the game has for a quest stage right now (cached)
local liveTextCache = {}
local function liveText(qid, stage)
    local key = qid .. '#' .. stage
    if liveTextCache[key] ~= nil then return liveTextCache[key] or nil end
    local text = false
    pcall(function()
        local rec = core.dialogue.journal.records[qid]
        for _, info in pairs(rec and rec.infos or {}) do
            if info.questStage == stage then text = info.text break end
        end
    end)
    liveTextCache[key] = text
    return text or nil
end

-- Returns the objective list for a stage, or nil plus 'changed' when a mod we
-- don't have data for has rewritten this step (then the journal line is shown instead).
local function stageList(q, stage)
    for plug, v in pairs(q.variants or {}) do
        if LOADED[plug] and v.stages and v.stages[stage] then return v.stages[stage] end
    end
    if q.fp and q.fp[stage] and q.id then
        local t = liveText(q.id:lower(), stage)
        if t and textHash(t) ~= q.fp[stage] then return nil, 'changed' end
    end
    local stages = q.stages or {}
    if stages[stage] then return stages[stage] end
    -- stage index not in the data (e.g. added by a later mod): nearest lower authored stage
    local best
    for s in pairs(stages) do
        if s < stage and (not best or s > best) then best = s end
    end
    return best and stages[best] or nil
end

local function questName(id)
    local rec = core.dialogue.journal.records[id]
    local n = rec and rec.questName
    if n and n ~= '' then return n end
    return (CQ[id] and CQ[id].name) or id
end

-- builds the checklist for a curated top-level quest (plus its active sub-quests)
local function buildBlock(top)
    local q = CQ[top]
    if not q then return nil end
    local items = {}
    local function addList(list, keyPrefix)
        for i, o in ipairs(list or {}) do
            items[#items + 1] = {
                o = o,
                done = o.done and cond(o.done) or false,
                key = keyPrefix .. '|' .. i .. '|' .. (o.text or ''),
            }
        end
    end
    local stage, fin = qstate(top)
    local mode = 'stage'
    if not q.hide then
        if fin then
            mode = 'after'
            addList(q.after, top .. '#after')
        elseif stage <= 0 then
            mode = 'start'
            addList(q.start, top .. '#start')
        else
            local list, why = stageList(q, stage)
            if why == 'changed' then return nil, 'changed' end
            addList(list, top .. '#' .. stage)
        end
    end
    for _, cid in ipairs(CHILDREN[top] or {}) do
        local cq = CQ[cid]
        if not cq.hide then
            local cs, cf = qstate(cid)
            if cs > 0 and not cf then
                addList(stageList(cq, cs), cid .. '#' .. cs)
            end
        end
    end
    if #items == 0 then return nil end
    local open = 0
    for _, it in ipairs(items) do
        if not it.done and not it.o.optional then open = open + 1 end
    end
    if open == 0 and mode ~= 'stage' then return nil end
    local c = q.color or { 1, 1, 1 }
    local name = questName(top)
    return {
        id = top,
        name = name,
        group = name .. GROUP_SUFFIX,
        color = c,
        uiColor = util.color.rgb(c[1], c[2], c[3]),
        items = items,
    }
end

---------------------------------------------------------------------------
-- collect what to show
---------------------------------------------------------------------------
local function collect()
    questsObj = types.Player.quests(self)
    inventory = types.Actor.inventory(self)
    scanDead()
    local entries = types.Player.journal(self).journalTextEntries
    local blocks, others = {}, {}
    local seenTop, seenName = {}, {}
    for i = #entries, 1, -1 do
        if #blocks >= MAX_CURATED and #others >= MAX_OTHER then break end
        local e = entries[i]
        local qid = e.questId and e.questId:lower()
        if qid then
            local cq = CQ[qid]
            if cq then
                local top = cq.parent or qid
                if not CQ[top] then top = qid end
                if not seenTop[top] and #blocks < MAX_CURATED then
                    seenTop[top] = true
                    local b, why = buildBlock(top)
                    if b then
                        blocks[#blocks + 1] = b
                        seenName[b.name] = true
                    elseif why == 'changed' and #others < MAX_OTHER then
                        -- a mod rewrote this step: show the game's own journal line
                        local name = questName(top)
                        if not seenName[name] then
                            seenName[name] = true
                            others[#others + 1] = { name = name, text = objectiveFrom(e.text) }
                        end
                    end
                end
            elseif #others < MAX_OTHER then
                local rec = core.dialogue.journal.records[qid]
                local _, fin = qstate(qid)
                if rec and not fin then
                    local name = rec.questName or qid
                    if name ~= '' and not seenName[name] then
                        seenName[name] = true
                        others[#others + 1] = { name = name, text = objectiveFrom(e.text) }
                    end
                end
            end
        end
    end
    return blocks, others, #entries
end

---------------------------------------------------------------------------
-- markers (proximityTool + HUD markers)
---------------------------------------------------------------------------
local activeMarkers = {}   -- key -> handle

-- Blocks sent by other scripts (Collector's Ledger etc.) through the
-- 'CO_SetCustomBlock' / 'CO_RemoveCustomBlock' events. Format:
--   { id=, name=, color={r,g,b}, items={ { text=, where=, done=bool,
--       marker={ objectIds={..}?, itemId=?, positions={ {cell={isExterior=,id=}, position={x,y,z}, door=bool?} }? } } } }
local customBlocks = {}
local customOrder = {}
local function customList()
    local out = {}
    for _, id in ipairs(customOrder) do
        local cb = customBlocks[id]
        if cb then
            local items = {}
            for i, it in ipairs(cb.items or {}) do
                items[#items + 1] = { o = { text = it.text, where = it.where, marker = it.marker },
                                      done = it.done and true or false, key = id .. '|' .. i .. '|' .. (it.text or '') }
            end
            local c = cb.color or { 0.85, 0.75, 0.45 }
            out[#out + 1] = { id = 'custom:' .. id, name = cb.name or id, group = (cb.name or id) .. GROUP_SUFFIX,
                              color = c, uiColor = util.color.rgb(c[1], c[2], c[3]), items = items }
        end
    end
    return out
end
local cellIdMode = 'lower' -- how this engine spells interior cell ids (checked at runtime)
local markersDirty = true

local function cellId(name)
    if not name then return nil end
    if cellIdMode == 'lower' then return name:lower() end
    return name
end

local function detectCellIdMode()
    local cell = self.cell
    if not cell or cell.isExterior then return end
    local ok, id, name = pcall(function() return cell.id, cell.name end)
    if not ok or not id or not name or name == '' then return end
    local mode
    if id == name:lower() then
        mode = 'lower'
    elseif id == name then
        mode = 'asis'
    end
    if mode and mode ~= cellIdMode then
        cellIdMode = mode
        markersDirty = true
    end
end

local function proximity()
    local pt = I.proximityTool
    if pt and (pt.version or 0) >= 3 then return pt end
    return nil
end

local function hudScale()
    local ok, size = pcall(function() return ui.screenSize() end)
    if ok and size then return 1.5 * size.y / 1080 end
    return 1.5
end

local function removeHandle(pt, h)
    if not pt or not h then return end
    for _, m in ipairs(h.markers or {}) do pcall(pt.removeMarker, m[1], m[2]) end
    for _, r in ipairs(h.records or {}) do pcall(pt.removeRecord, r) end
    if h.hudm and pt.removeHUDM then pcall(pt.removeHUDM, h.hudm) end
end

local function convPositions(list)
    local out = {}
    for _, p in ipairs(list) do
        local cell
        if p.cell.isExterior then
            cell = { isExterior = true }
        else
            cell = { isExterior = false, id = cellId(p.cell.id) }
        end
        out[#out + 1] = { cell = cell, position = { x = p.position.x, y = p.position.y, z = p.position.z } }
    end
    return out
end

local function addHandle(pt, block, it)
    local o, m = it.o, it.o.marker
    local h = { markers = {}, records = {} }
    local ok, err = pcall(function()
        local targetPos, doorPos = {}, {}
        for _, p in ipairs(m.positions or {}) do
            if p.door then doorPos[#doorPos + 1] = p else targetPos[#targetPos + 1] = p end
        end
        local hasObjects = m.objectIds ~= nil and #m.objectIds > 0
        local rec = pt.addRecord {
            name = o.text,
            note = o.where,
            description = block.name,
            nameColor = block.color,
            priority = 15,
            proximity = MARKER_RANGE,
            -- the Quest Markers Plus compass only draws records tagged as tracking
            userData = { type = 'tracking', questName = block.name },
            temporary = true,
        }
        if rec then
            h.records[#h.records + 1] = rec
            if hasObjects then
                local id, gid = pt.addMarker {
                    record = rec,
                    groupName = block.group,
                    objectIds = m.objectIds,
                    positions = (#targetPos > 0) and convPositions(targetPos) or nil,
                    itemId = m.itemId,
                    temporary = true,
                }
                if id then h.markers[#h.markers + 1] = { id, gid } end
            elseif #targetPos > 0 then
                local id, gid = pt.addMarker {
                    record = rec,
                    groupName = block.group,
                    positions = convPositions(targetPos),
                    temporary = true,
                }
                if id then h.markers[#h.markers + 1] = { id, gid } end
            end
        end
        -- doors on the route from outdoors to the target (direction from far away)
        if #doorPos > 0 then
            local drec = pt.addRecord {
                name = o.text,
                note = o.where,
                description = block.name,
                nameColor = block.color,
                icon = DOOR_ICON,
                iconRatio = 1.6,
                priority = 14,
                proximity = MARKER_RANGE,
                userData = { type = 'tracking', questName = block.name },
                temporary = true,
            }
            if drec then
                h.records[#h.records + 1] = drec
                local id, gid = pt.addMarker {
                    record = drec,
                    groupName = block.group,
                    positions = convPositions(doorPos),
                    temporary = true,
                }
                if id then h.markers[#h.markers + 1] = { id, gid } end
            end
        end
        if hasObjects and pt.addHUDM then
            h.hudm = pt.addHUDM {
                modName = MOD_NAME,
                version = 6,
                temporary = true,
                objectIds = m.objectIds,
                itemId = m.itemId,
                hideDead = (o.done ~= nil and o.done.kind == 'dead') or nil,
                params = {
                    icon = HUDM_ICON,
                    color = block.color,
                    scale = hudScale(),
                    opacity = 0.9,
                    range = 500,
                    offsetMult = 1.0,
                    offset = util.vector3(0, 0, 15),
                },
            }
        end
    end)
    if not ok then
        print('[Comprehensive Objectives] marker error for "' .. tostring(o.text) .. '": ' .. tostring(err))
    end
    return h
end

local function markerSignature(m)
    local s = table.concat(m.objectIds or {}, ',')
    local p = m.positions and m.positions[1]
    if p then
        s = s .. '@' .. tostring(p.cell.id) .. ':' .. math.floor(p.position.x) .. ',' .. math.floor(p.position.y)
    end
    return s
end

local function syncMarkers(blocks)
    local pt = proximity()
    if not pt then return end
    if markersDirty then
        for _, h in pairs(activeMarkers) do removeHandle(pt, h) end
        activeMarkers = {}
        markersDirty = false
    end
    local wanted, sigs = {}, {}
    for _, b in ipairs(blocks) do
        for _, it in ipairs(b.shown or b.items) do
            local m = it.o.marker
            if m and not it.done then
                local sig = markerSignature(m)
                if not sigs[sig] then
                    sigs[sig] = true
                    wanted[b.id .. '|' .. it.key] = { b = b, it = it }
                end
            end
        end
    end
    local changed = false
    for k, h in pairs(activeMarkers) do
        if not wanted[k] then
            removeHandle(pt, h)
            activeMarkers[k] = nil
            changed = true
        end
    end
    for k, w in pairs(wanted) do
        if not activeMarkers[k] then
            activeMarkers[k] = addHandle(pt, w.b, w.it)
            changed = true
        end
    end
    if changed then
        pcall(pt.update)
        if pt.updateHUDM then pcall(pt.updateHUDM) end
    end
end

---------------------------------------------------------------------------
-- panel
---------------------------------------------------------------------------
local element
local lastKey
local lastError
local timer = 0
local liveTimer = 0
local visible = true

-- rough line count so each text box gets a fixed height
local function lineCount(text, size, width)
    local perLine = math.floor(width / (size * 0.43))
    local lines, len = 1, 0
    for word in text:gmatch("%S+") do
        if len > 0 and len + 1 + #word > perLine then
            lines = lines + 1
            len = #word
        else
            len = len + (len > 0 and 1 or 0) + #word
        end
    end
    return lines
end

local function textWidget(text, size, color, x, y, width)
    width = width or WIDTH
    local h = lineCount(text, size, width) * math.floor(size * 1.18)
    return {
        type = ui.TYPE.Text,
        props = {
            text = text,
            textSize = size,
            textColor = color,
            textShadow = true,
            textShadowColor = util.color.rgb(0, 0, 0),
            multiline = true,
            wordWrap = true,
            autoSize = false,
            position = util.vector2(x, y),
            size = util.vector2(width, h),
        },
    }, h
end

-- choose which lines of a block to show: keep order, drop finished lines first
local function shownItems(b, maxItems)
    local items = b.items
    if #items <= maxItems then return items, 0 end
    local doneCount = 0
    for _, it in ipairs(items) do
        if it.done then doneCount = doneCount + 1 end
    end
    local out, hidden = {}, 0
    local dropDone = math.min(doneCount, #items - maxItems)
    for _, it in ipairs(items) do
        if it.done and hidden < dropDone then
            hidden = hidden + 1
        elseif #out < maxItems then
            out[#out + 1] = it
        end
    end
    return out, hidden
end

-- short form of an objective line: drop "(...)" notes and tidy spaces
local function shortText(t)
    t = t:gsub("%s*%b()", ""):gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", "")
    return t
end

-- distance from the player to an objective, in game units (nil if unknown here)
local UNITS_PER_METER = 69.99
local function objectiveDistance(o)
    local m = o and o.marker
    if not m then return nil end
    local pos = self.position
    local cell = self.cell
    local best, bestP
    local function consider(p)
        local d = (p - pos):length()
        if not best or d < best then best, bestP = d, p end
    end
    -- the target itself, if it's loaded near the player (catches NPCs that walk around)
    if m.objectIds and #m.objectIds > 0 then
        local want = {}
        for _, id in ipairs(m.objectIds) do want[id:lower()] = true end
        for _, list in ipairs({ nearby.actors, nearby.items, nearby.containers, nearby.activators }) do
            for _, obj in ipairs(list or {}) do
                if want[obj.recordId] then consider(obj.position) end
            end
        end
        if best then return best, bestP end
    end
    -- otherwise the stored target / route-door positions in the player's current cell
    local here = (not cell.isExterior) and cell.name and cell.name:lower() or nil
    for _, p in ipairs(m.positions or {}) do
        local same = (p.cell.isExterior and cell.isExterior) or
                     ((not p.cell.isExterior) and here and p.cell.id and p.cell.id:lower() == here)
        if same then consider(util.vector3(p.position.x, p.position.y, p.position.z)) end
    end
    return best, bestP
end

-- direction arrow (the old tracker's images): turns as you turn; _A = target above, _B = below
local ARROW_DIR = { [0] = 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW' }
local arrowTex = {}
local function arrowTexture(name)
    if not arrowTex[name] then
        arrowTex[name] = ui.texture { path = 'textures/icons/proximityTool/arrow_' .. name .. '.dds' }
    end
    return arrowTex[name]
end
local function viewYaw()
    local ok, fwd = pcall(camera.viewportToWorldVector, util.vector2(0.5, 0.5))
    if ok and fwd then return math.atan2(fwd.x, fwd.y) end
    return self.rotation:getYaw()
end
local function arrowName(p, yaw)
    if not p then return nil end
    local pos = self.position
    local dx, dy, dz = p.x - pos.x, p.y - pos.y, p.z - pos.z
    local suffix = (dz > 200 and '_A') or (dz < -200 and '_B') or ''
    if dx * dx + dy * dy < 200 * 200 then return 'P' .. suffix end
    local rel = util.normalizeAngle(math.atan2(dx, dy) - yaw)
    return ARROW_DIR[math.floor(rel / (math.pi / 4) + 0.5) % 8] .. suffix
end

local function formatDistance(d)
    if not d then return nil end
    local meters = d / UNITS_PER_METER
    if meters >= 1000 then return string.format('%.1fkm', meters / 1000) end
    if meters >= 100 then return string.format('%dm', math.floor(meters / 10 + 0.5) * 10) end
    return string.format('%dm', math.floor(meters + 0.5))
end

-- Skyrim-style: one quest (the newest), only open objectives, small text,
-- right-aligned under the compass, no box.
local PANEL_W = 430
CUSTOM_RENDER = {}
-- open objectives use the quest's colour (same as its markers); the nearest one is brighter
local function tint(c, k)
    c = c or { 1, 1, 1 }
    return util.color.rgb(c[1] + (1 - c[1]) * k, c[2] + (1 - c[2]) * k, c[3] + (1 - c[3]) * k)
end

local ARROW = 18      -- arrow image size
local TEXT_W = PANEL_W - ARROW - 6
local lastSig
local lastBlocks, lastOthers = {}, {}

-- one objective line: text (+ distance) and the arrow towards its target
local function liveLine(o, yaw)
    local d, p = objectiveDistance(o)
    local txt = shortText(o.text)
    if d then txt = txt .. '   ' .. formatDistance(d) end
    return txt, d, arrowName(p, yaw)
end

local function render(blocks, others, force)
    local yaw = viewYaw()
    local b = blocks[1]
    local title, lines = nil, {}
    if b then
        title = b.name
        -- finished objectives stay listed with an X, dimmed; open ones in the quest colour
        local nearestLine, nearestD
        for _, it in ipairs(b.items) do
            if it.done then
                lines[#lines + 1] = { text = 'X  ' .. shortText(it.o.text), done = true }
            else
                local txt, d, arrow = liveLine(it.o, yaw)
                lines[#lines + 1] = { text = txt, arrow = arrow }
                if d and (not nearestD or d < nearestD) then nearestD, nearestLine = d, #lines end
            end
            if #lines >= 7 then break end
        end
        if nearestLine then lines[nearestLine].nearest = true end
    elseif others[1] then
        title = others[1].name
        lines[1] = { text = shortText(others[1].text) }
    end
    local customs = CUSTOM_RENDER or {}
    local customLines = {}
    for ci, cb in ipairs(customs) do
        local cl = {}
        for _, it in ipairs(cb.items) do
            if #cl >= 4 then break end
            if it.done then
                cl[#cl + 1] = { text = 'X  ' .. shortText(it.o.text), done = true }
            else
                local txt, _, arrow = liveLine(it.o, yaw)
                cl[#cl + 1] = { text = txt, arrow = arrow }
            end
        end
        customLines[ci] = cl
    end

    -- skip the redraw when nothing on screen changed
    local visibleNow = visible and (title ~= nil or #customs > 0) and (I.UI.getMode() == nil)
    local sig = { tostring(visibleNow), title or '' }
    for _, l in ipairs(lines) do sig[#sig + 1] = l.text .. (l.arrow or '') .. (l.nearest and '*' or '') end
    for ci, cb in ipairs(customs) do
        sig[#sig + 1] = '#' .. cb.name
        for _, l in ipairs(customLines[ci]) do sig[#sig + 1] = l.text .. (l.arrow or '') end
    end
    sig = table.concat(sig, '\n')
    if not force and element and sig == lastSig then return end
    lastSig = sig

    local content = {}
    local y = 0
    local function addLine(line, col)
        local w, h = textWidget(line.text, 15, col, 0, y, TEXT_W)
        w.props.textAlignH = ui.ALIGNMENT.End
        content[#content + 1] = w
        if line.arrow then
            content[#content + 1] = {
                type = ui.TYPE.Image,
                props = {
                    resource = arrowTexture(line.arrow),
                    color = col,
                    position = util.vector2(PANEL_W - ARROW, y),
                    size = util.vector2(ARROW, ARROW),
                },
            }
        end
        y = y + h + 1
    end
    if title then
        local w, h = textWidget(title, 17, b and b.uiColor or titleColor, 0, y, TEXT_W)
        w.props.textAlignH = ui.ALIGNMENT.End
        content[#content + 1] = w
        y = y + h + 2
        for _, line in ipairs(lines) do
            local col = line.done and doneColor
                or (b and (line.nearest and tint(b.color, 0.55) or tint(b.color, 0.2)))
                or (line.nearest and nearestColor or textColor)
            addLine(line, col)
        end
    end
    for ci, cb in ipairs(customs) do
        y = y + (y > 0 and 8 or 0)
        local w, h = textWidget(cb.name, 17, cb.uiColor, 0, y, TEXT_W)
        w.props.textAlignH = ui.ALIGNMENT.End
        content[#content + 1] = w
        y = y + h + 2
        for _, line in ipairs(customLines[ci]) do
            addLine(line, line.done and doneColor or tint(cb.color, 0.2))
        end
    end
    local layout = {
        layer = 'HUD',
        props = {
            relativePosition = util.vector2(1, 0),
            anchor = util.vector2(1, 0),
            position = util.vector2(-20, 58),
            size = util.vector2(PANEL_W, math.max(y, 1)),
            -- hide while any menu (journal, inventory, dialogue...) is open
            visible = visibleNow,
        },
        content = ui.content(content),
    }
    if element then
        element.layout = layout
        element:update()
    else
        element = ui.create(layout)
    end
end

local function refresh(force)
    local ok, blocks, others, count = pcall(collect)
    if not ok then
        if not lastError then print('[Comprehensive Objectives] ' .. tostring(blocks)) end
        lastError = true
        return
    end
    pcall(detectCellIdMode)
    local key = tostring(count) .. (visible and 'v' or 'h') .. tostring(I.UI.getMode())
    for i, b in ipairs(blocks) do
        b.showWhere = (i == 1)
        b.shown, b.hiddenDone = shownItems(b, i == 1 and MAX_ITEMS or MAX_ITEMS_OTHER)
        key = key .. '#' .. b.id
        for _, it in ipairs(b.shown) do key = key .. (it.done and '+' or '-') .. it.key end
    end
    for _, q in ipairs(others) do key = key .. q.name .. q.text end
    local customs = customList()
    CUSTOM_RENDER = customs
    for _, cb in ipairs(customs) do
        key = key .. '#' .. cb.id
        for _, it in ipairs(cb.items) do key = key .. (it.done and '+' or '-') .. it.key end
    end
    local markerBlocks = { blocks[1] }
    for _, cb in ipairs(customs) do markerBlocks[#markerBlocks + 1] = cb end
    local okM, errM = pcall(syncMarkers, markerBlocks)
    if not okM and not lastError then
        print('[Comprehensive Objectives] markers: ' .. tostring(errM))
        lastError = true
    end
    if force or key ~= lastKey then
        lastKey = key
        for _, b in ipairs(blocks) do
            print('[Comprehensive Objectives] ' .. b.name .. ' :: ' .. #b.items .. ' objectives')
        end
        for _, q in ipairs(others) do print('[Comprehensive Objectives] ' .. q.name .. ' :: ' .. q.text) end
    end
    lastBlocks, lastOthers = blocks, others
    local okR, errR = pcall(render, blocks, others, force)
    if not okR and not lastError then
        print('[Comprehensive Objectives] render: ' .. tostring(errR))
        lastError = true
    end
end

return {
    eventHandlers = {
        -- tell the phone overlay helper which menu is open (it reads this line from openmw.log)
        UiModeChanged = function(data)
            print('[CO-UI] ' .. tostring((data and data.newMode) or 'none'))
        end,
        CO_SetCustomBlock = function(b)
            if not b or not b.id then return end
            if not customBlocks[b.id] then customOrder[#customOrder + 1] = b.id end
            customBlocks[b.id] = b
            lastKey = nil
        end,
        CO_RemoveCustomBlock = function(d)
            local id = d and d.id
            if not id or not customBlocks[id] then return end
            customBlocks[id] = nil
            for i, v in ipairs(customOrder) do if v == id then table.remove(customOrder, i) break end end
            lastKey = nil
        end,
    },
    engineHandlers = {
        onFrame = function(dt)
            timer = timer + dt
            liveTimer = liveTimer + dt
            if timer >= UPDATE_EVERY then
                timer = 0
                liveTimer = 0
                refresh(false)
            elseif liveTimer >= LIVE_EVERY then
                liveTimer = 0
                local ok, err = pcall(render, lastBlocks, lastOthers, false)
                if not ok and not lastError then
                    print('[Comprehensive Objectives] live: ' .. tostring(err))
                    lastError = true
                end
            end
        end,
        onKeyPress = function(key)
            -- K toggles the objective panel
            if key.code == input.KEY.K and I.UI.getMode() == nil then
                visible = not visible
                refresh(true)
            end
        end,
        onControllerButtonPress = function(id)
            -- D-pad up toggles the objective panel (for controllers / phone streaming)
            if id == input.CONTROLLER_BUTTON.DPadUp and I.UI.getMode() == nil then
                visible = not visible
                refresh(true)
            end
        end,
        onSave = function()
            return { killed = killed }
        end,
        onLoad = function(data)
            killed = (data and data.killed) or {}
            -- temporary markers are not in the save: they are re-added on the next refresh
            activeMarkers = {}
            markersDirty = true
            lastKey = nil
            timer = UPDATE_EVERY
        end,
        onInit = function()
            killed = {}
            timer = UPDATE_EVERY
        end,
    },
}
