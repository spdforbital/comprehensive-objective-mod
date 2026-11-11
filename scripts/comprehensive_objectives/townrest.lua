-- Town rest: waiting where sleeping is illegal (towns, shops, guild halls) heals you like real rest.
-- The game already refuses to let you wait with enemies nearby, so this only applies when it's safe.
local core = require('openmw.core')
local self = require('openmw.self')
local types = require('openmw.types')
local ui = require('openmw.ui')
local I = require('openmw.interfaces')

local Actor = types.Actor
local dyn, attr = Actor.stats.dynamic, Actor.stats.attributes

local waiting, startTime, startCell = false, nil, nil

local function noSleepHere()
    local c = self.cell
    return c and c.hasTag and c:hasTag('NoSleep') or false
end

local function restore(stat, amount)
    local s = stat(self)
    local max = s.base + s.modifier
    if s.current < max and amount > 0 then
        s.current = math.min(max, s.current + amount)
        return true
    end
    return false
end

-- same rates the game uses for sleeping: 0.1 x Endurance health and fRestMagicMult x Intelligence magicka per hour
local function heal(hours)
    local endurance = attr.endurance(self).modified
    local intelligence = attr.intelligence(self).modified
    local healed = restore(dyn.health, 0.1 * endurance * hours)
    local stunted = false
    pcall(function()
        local e = Actor.activeEffects(self):getEffect(core.magic.EFFECT_TYPE.StuntedMagicka)
        stunted = e and (e.magnitude or 0) > 0
    end)
    if not stunted then
        local mult = core.getGMST('fRestMagicMult') or 0.15
        healed = restore(dyn.magicka, mult * intelligence * hours) or healed
    end
    if healed then ui.showMessage('You rest quietly. (Town rest)') end
end

local function onFrame()
    local inRest = I.UI.getMode() == 'Rest'
    if inRest and not waiting then
        waiting = true
        startTime = core.getGameTime()
        startCell = self.cell
    elseif not inRest and waiting then
        waiting = false
        local hours = (core.getGameTime() - (startTime or core.getGameTime())) / 3600
        if hours >= 0.99 and self.cell == startCell and noSleepHere() then
            pcall(heal, math.min(hours, 24))
        end
    end
end

return { engineHandlers = { onFrame = onFrame } }
