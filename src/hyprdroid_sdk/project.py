"""Project scaffolds and deterministic test vectors."""

import json
from pathlib import Path

from .packer import check_id

CLOCK = {"date": "2026-11-24", "time24": "14:30:00", "time12": "2:30:00 PM"}
SYSTEM = {"device.time": CLOCK, "battery.level": 78, "battery.charging": False}
SOURCES = {
    "basic": 'hypr.ui.render({type="text", value="Hello from HyprDroid"})\n',
    "counter": '''local count = state.get("count", 0)
local function render()
    ui.render({type="column", children={
        {type="text", value="Count: " .. count},
        {type="button", id="increment", text="Increment"}
    }})
end
ui.on("onClick", "increment", function()
    count = count + 1
    state.set("count", count)
    render()
end)
render()
''',
    "clock": '''local function render()
    local time = system.get("device.time")
    ui.render({type="text", value=time and time.time24 or "Time unavailable"})
end
ui.on("onTimer", "clock", render)
timer.every("clock", 1000)
render()
''',
    "battery": '''local function render()
    local level = system.get("battery.level")
    ui.render({type="column", children={
        {type="text", value=level and ("Battery: " .. level .. "%") or "Battery unavailable"},
        {type="progress", value=level and level / 100 or 0}
    }})
end
render()
''',
}
CAPABILITIES = {"basic": [], "counter": ["state.local"], "clock": ["system.time"], "battery": ["system.battery"]}
SUITES = {
    "basic": {"steps": [{"text": "Hello from HyprDroid"}]},
    "counter": {"steps": [{"text": "Count: 0"},
                          {"event": {"kind": "onClick", "id": "increment"}, "text": "Count: 1",
                           "expect": {"state": {"count": 1}}},
                          {"text": "Count: 1"}, {"fresh_instance": True, "text": "Count: 0"}]},
    "clock": {"system": SYSTEM, "steps": [{"text": "14:30:00"},
              {"system": {"device.time": {**CLOCK, "time24": "14:30:01"}},
               "event": {"kind": "onTimer", "id": "clock"}, "text": "14:30:01"}]},
    "battery": {"system": SYSTEM, "steps": [{"text": "Battery: 78%"}]},
}


def create(dest: Path, template: str, api: int):
    package_id = dest.name
    check_id(package_id)
    if api == 1 and template != "basic":
        raise ValueError("Use the basic template for API v1 or select API 2")
    # Atomic directory creation prevents replacing an existing project or alias.
    dest.mkdir()
    manifest = {"id": package_id, "version": "1.0.0", "apiVersion": api, "runtime": "lua", "entry": "main.lua",
                "permissions": ["ui.tile", *CAPABILITIES[template]], "dependencies": {}}
    files = {"manifest.json": json.dumps(manifest, indent=2) + "\n",
             "main.lua": SOURCES[template],
             "hyp-tests.json": json.dumps(SUITES[template], indent=2) + "\n",
             "README.md": f"# {package_id}\n\nRun `hyp validate .`, `hyp test .` and `hyp build .`.\n",
             "LICENSE": "Choose a license and replace this template before distributing your module.\n"}
    for name, content in files.items():
        with (dest / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
