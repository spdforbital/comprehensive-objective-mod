-- Comprehensive Objective Mod (global): when Quest Markers Plus tracks a quest (its journal
-- "track" button, or auto-tracking), tell the player script so the objective panel shows it.
-- Returns nothing, so Quest Markers Plus still gets the event.
local world = require('openmw.world')

return {
    eventHandlers = {
        ['QGL:trackQuest'] = function(data)
            if not data or not data.questId or data.finished then return end
            local p = data.player or world.players[1]
            if p then p:sendEvent('CO_FocusQuest', { questId = data.questId }) end
        end,
    },
}
