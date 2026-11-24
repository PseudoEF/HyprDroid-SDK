-- The executable has standard libraries. The module environment only has these explicit capabilities.
local cfg = assert(load(io.read("*a"), "@request", "t", {}))()
local original_string_metatable = debug.getmetatable("")
local tree, handlers, timers = nil, {}, {}
local state = cfg.state
local function text(value, max)
    assert(type(value) == "string" and #value <= max, "invalid text")
    return value
end
local function render(value) tree = value end
local ui = {render = render}
local environment = {}
environment.hypr = {ui = ui}
if cfg.api == 1 then
    ui.getState = function() return state end
    ui.setState = function(value) state = text(value, 512) end
    ui.on = function(id, fn)
        assert(id == "increment" or id == "reset", "unsupported v1 external event")
        handlers[id] = assert(type(fn) == "function" and fn)
    end
    -- The external v1 Core adapter only adds decimal strings for the pinned Hello Tile.
    debug.setmetatable("", {__add = function(a, b)
        assert(type(a) == "string" and string.match(a, "^%d+$") and math.type(b) == "integer" and b >= 0, "invalid counter")
        local n = math.tointeger(a)
        assert(n and n <= math.maxinteger - b, "counter overflow")
        return n + b
    end})
else
    debug.setmetatable("", {})
    environment.ui = ui
    local kinds = {onClick=true, onChange=true, onSubmit=true, onTimer=true, onResume=true}
    ui.on = function(kind, id, fn)
        assert(kinds[kind] and type(fn) == "function", "invalid handler")
        text(id, 32)
        assert((kind == "onResume") == (id == ""), "invalid handler ID")
        handlers[kind .. ":" .. id] = fn
    end
    environment.state = {
        get = function(key, default)
            text(key, 32)
            if state[key] == nil then return default end
            return state[key]
        end,
        set = function(key, value)
            assert(cfg.permissions["state.local"], "state.local denied")
            text(key, 32)
            assert(string.match(key, "^[a-zA-Z][a-zA-Z0-9_.-]*$"), "invalid state key")
            local kind = type(value)
            assert(kind == "string" or kind == "number" or kind == "boolean", "invalid state type")
            state[key] = value
        end,
    }
    local grants = {["device.time"]="system.time", ["battery.level"]="system.battery", ["battery.charging"]="system.battery"}
    environment.system = {get = function(key)
        assert(grants[key], "unknown system field")
        if cfg.permissions[grants[key]] then return cfg.system[key] end
    end}
    environment.timer = {every = function(id, ms)
        text(id, 32)
        assert(string.match(id, "^[a-zA-Z][a-zA-Z0-9_-]*$"), "invalid timer ID")
        assert(math.type(ms) == "integer" and ms >= 1000 and ms <= 86400000, "invalid interval")
        assert(#timers < 2, "too many timers")
        for _, existing in ipairs(timers) do assert(existing.id ~= id, "duplicate timer") end
        timers[#timers + 1] = {id = id, intervalMs = ms}
    end}
end

local module = assert(load(cfg.source, "@main.lua", "t", environment))
local allowance = 50000
debug.sethook(function()
    allowance = allowance - 250
    if allowance <= 0 then error("Lua instruction limit exceeded") end
end, "", 250)
module()
if cfg.event then
    local event = cfg.event
    local handler = handlers[cfg.api == 1 and event.id or event.kind .. ":" .. event.id]
    if handler then handler(event) end
end
debug.sethook()
debug.setmetatable("", original_string_metatable)

local emitted = 0
local output = {}
local function chunk(value)
    emitted = emitted + #value
    assert(emitted <= 16384, "result exceeds byte limit")
    output[#output + 1] = value
end
local function quoted(s)
    assert(#s <= 1024, "result string too long")
    return '"' .. s:gsub('[%z\1-\31\\"]', function(c)
        return string.format("\\u%04x", c:byte())
    end) .. '"'
end
local active = {}
local function json(value, depth, array)
    assert(depth <= 20, "result nesting exceeds limit")
    local kind = type(value)
    if kind == "nil" then chunk("null")
    elseif kind == "string" then chunk(quoted(value))
    elseif kind == "number" then
        assert(value == value and value ~= math.huge and value ~= -math.huge, "invalid number")
        chunk(string.format("%.17g", value))
    elseif kind == "boolean" then chunk(tostring(value))
    elseif kind == "table" then
        assert(not active[value], "cyclic result")
        active[value] = true
        local n = 0
        chunk(array and "[" or "{")
        if array then
            assert(#value <= 48, "array exceeds limit")
            for key in pairs(value) do
                assert(math.type(key) == "integer" and key >= 1 and key <= #value, "invalid array key")
            end
            for i = 1, #value do
                if i > 1 then chunk(",") end
                json(value[i], depth + 1)
            end
        else
            for key, item in pairs(value) do
                n = n + 1
                assert(n <= 48 and type(key) == "string", "invalid result field")
                if n > 1 then chunk(",") end
                chunk(quoted(key)); chunk(":")
                json(item, depth + 1, key == "children" or key == "timers")
            end
        end
        chunk(array and "]" or "}")
        active[value] = nil
    else error("unsupported result value") end
end
json({ui = tree, state = state, timers = timers}, 1)
io.write(table.concat(output))
