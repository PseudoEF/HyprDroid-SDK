local function render()
    local level = system.get("battery.level")
    local charging = system.get("battery.charging")
    local children = {
        {type = "text", value = "Battery"},
        {type = "text", value = level and (level .. "%") or "Level unavailable"},
        {type = "text", value = charging == nil and "Charging status unavailable"
            or (charging and "Charging" or "Not charging")}
    }
    if level ~= nil then
        children[4] = {type = "progress", value = level / 100}
    end
    children[#children + 1] = {type = "button", id = "refresh", text = "Refresh"}
    hypr.ui.render({type = "column", children = children})
end

hypr.ui.on("onClick", "refresh", render)
render()
