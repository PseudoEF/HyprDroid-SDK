local function render()
    local format24 = state.get("format24", true)
    local time = system.get("device.time")
    hypr.ui.render({
        type = "column",
        children = {
            {type = "text", value = "Clock"},
            {type = "text", value = time and time.date or "Date unavailable"},
            {type = "text", value = time and
                (format24 and time.time24 or time.time12) or "Time unavailable"},
            {type = "row", children = {
                {type = "text", value = "24-hour"},
                {type = "switch", id = "format24", value = format24}
            }}
        }
    })
end

hypr.ui.on("onChange", "format24", function(event)
    state.set("format24", event.value)
    render()
end)
hypr.ui.on("onTimer", "clock", render)
timer.every("clock", 1000)
render()
