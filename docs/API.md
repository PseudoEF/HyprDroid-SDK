# Plugin API v1 and v2

The versioned contract snapshot is in src/hyprdroid_sdk/contract.json.
The supported deployment surface is external tiles, and the three official projects
in examples are pinned to HyprDroid-Packages fa92592.

## v1 external tiles

Use hypr.ui.render(tree), hypr.ui.getState(), hypr.ui.setState(string) and
hypr.ui.on(id, callback). The external worker recognizes increment and reset.
Hello Tile uses a compatibility adapter for adding a bounded decimal string and an
integer. Core also recognizes older manifest capabilities for its other trusted v1
adapters. The SDK external tile harness does not emulate DroidFetch, Android windows,
or terminal access.

## v2

Use ui.render(tree) or hypr.ui.render(tree). Both names refer to the same local interface.
ui.on(kind, id, callback) registers one callback for that pair. The module entrypoint
runs for each request, then Core delivers one event. Event kinds are onClick, onChange,
onSubmit, onTimer and onResume. Switch provides a boolean event.value. TextInput
onChange/onSubmit provide a string. onResume uses an empty ID.

## UI components

| Type | Required fields beyond type |
| --- | --- |
| text | value |
| button | id, text |
| column, row, card, scrollableColumn | children |
| progress | value in 0..1 |
| spacer | integer size in 0..32 |
| divider (v2) | none |
| switch (v2) | id, boolean value |
| textInput (v2) | id, value up to 128 UTF-8 bytes, no control characters |
| list (v2) | children, at most 12 |
| icon (v2) | glyph from CLOCK, BATTERY, REFRESH, INFO |

Limits are six levels, 48 nodes, 256 UTF-16 units per text, 4096 units overall and
unique ID tokens. scrollableColumn is root-only. The SDK rejects undeclared node
fields so values ignored by the native encoder do not become accidental contracts.

## State and timers

state.get(key, default) reads the current snapshot. state.set(key, value) requires
state.local. State values are string, finite number or boolean. Core retains at most
16 keys and 512 bytes per snapshot. v1 uses a single string with a 512-byte limit.
timer.every(id, milliseconds) declares one of up to two timers, with intervals from
1000 to 86400000 ms. Android Core owns the actual scheduler and pauses invisible tiles.
The SDK deterministically supplies explicit timer events from a test vector.

## Capabilities and system data

v2 requires ui.tile. state.local enables local state; system.time grants device.time
with date, time12 and time24; system.battery grants battery.level and battery.charging.
Unknown system fields fail. Known unavailable or ungranted fields return nil.
The SDK uses only synthetic caller-supplied data.
