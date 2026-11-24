local count = hypr.ui.getState()
if count == "" then count = "0" end

local function render()
    hypr.ui.render({
        type = "scrollableColumn",
        children = {
            { type = "text", value = "Hello HyprDroid" },
            { type = "text", value = "Count: " .. count },
            { type = "button", id = "increment", text = "Increment" },
            { type = "button", id = "reset", text = "Reset" }
        }
    })
end

hypr.ui.on("increment", function()
    count = "" .. (count + 1)
    hypr.ui.setState(count)
    render()
end)

hypr.ui.on("reset", function()
    count = "0"
    hypr.ui.setState(count)
    render()
end)

render()
