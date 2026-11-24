"""Deterministic contract harness for local, developer-controlled Lua."""

import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .packer import CONTRACT, canonical

EVENT_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}")
STATE_KEY = re.compile(r"[a-zA-Z][a-zA-Z0-9_.-]{0,31}")
CONTAINERS = {"column", "row", "card", "scrollableColumn", "list"}
TEXT_FIELDS = {"text": "value", "button": "text", "textInput": "value"}
FIELDS = {"switch": {"id", "value"}, "button": {"id", "text"}, "textInput": {"id", "value"},
          "text": {"value"}, "spacer": {"size"}, "progress": {"value"}, "icon": {"glyph"}, "divider": set()}


def environment():
    return {key: os.environ[key] for key in ("SystemRoot", "WINDIR") if key in os.environ}


def lua_executable():
    selected = os.environ.get("HYP_LUA")
    names = (selected,) if selected else ("lua5.4", "lua54", "lua")
    for name in names:
        path = shutil.which(name)
        if path:
            result = subprocess.run([path, "-E", "-v"], capture_output=True, timeout=3, env=environment(), check=False)
            if b"Lua 5.4." in result.stdout + result.stderr:
                return path
    raise ValueError("Lua 5.4 not found. Install lua54/lua5.4 or set HYP_LUA to a Lua 5.4 executable")


def limits():
    import resource
    # Android's linker reserves a large virtual address range before Lua starts.
    if sys.platform != "android":
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))


def run_lua(arguments, data):
    options = {"preexec_fn": limits} if os.name == "posix" else {}
    if len(data) > 100_000:
        raise ValueError("Lua request is too large")
    try:
        result = subprocess.run([lua_executable(), "-E", *arguments], input=data, capture_output=True,
                                timeout=3, env=environment(), **options)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Lua exceeded the wall-time limit") from exc
    if result.returncode:
        detail = result.stderr[:2048].decode("utf-8", errors="replace").strip()
        raise ValueError(f"Lua failed: {detail or result.returncode}")
    if len(result.stdout) > 16384:
        raise ValueError("Lua result exceeds 16 KiB")
    return result.stdout


def check_syntax(data):
    run_lua(["-e", 'assert(load(io.read("*a"),"@entry","t"))'], data)


def literal(value):
    if value is None:
        return "nil"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) in (int, float) and math.isfinite(value):
        return repr(value)
    if isinstance(value, str):
        return '"' + "".join(f"\\{b:03d}" for b in value.encode()) + '"'
    if isinstance(value, dict):
        return "{" + ",".join(f"[{literal(k)}]={literal(v)}" for k, v in value.items()) + "}"
    raise ValueError("Unsupported input value")


def string_ok(value, count):
    return isinstance(value, str) and len(value.encode("utf-16-le")) // 2 <= count and all(
        not (ord(ch) < 32 or 127 <= ord(ch) <= 159) or ch in "\t\n" for ch in value
    )


def validate_tree(tree, api):
    ids = {}
    count = 0
    total = 0
    allowed = CONTRACT["ui_v1"] + (CONTRACT["ui_v2"] if api == 2 else [])

    def walk(node, depth):
        nonlocal count, total
        count += 1
        if count > CONTRACT["ui_nodes"] or depth > CONTRACT["ui_depth"] or not isinstance(node, dict):
            raise ValueError("UI tree exceeds limits or contains an invalid node")
        kind = node.get("type")
        if kind not in allowed:
            raise ValueError(f"Unsupported UI component {kind!r}")
        expected = {"children"} if kind in CONTAINERS else FIELDS[kind]
        if set(node) != {"type"} | expected:
            raise ValueError(f"Invalid fields for {kind}")
        if kind in CONTAINERS:
            children = node["children"]
            if not isinstance(children, list) or kind == "list" and len(children) > 12 or kind == "scrollableColumn" and depth != 1:
                raise ValueError(f"Invalid children for {kind}")
            for child in children:
                walk(child, depth + 1)
            return
        if kind in TEXT_FIELDS:
            text = node[TEXT_FIELDS[kind]]
            if not string_ok(text, 256) or kind == "button" and not text.strip():
                raise ValueError("Invalid UI text")
            total += len(text.encode("utf-16-le")) // 2
            if total > 4096 or kind == "textInput" and not input_ok(text):
                raise ValueError("UI text exceeds limits")
        if "id" in node:
            identifier = node["id"]
            if not isinstance(identifier, str) or not EVENT_ID.fullmatch(identifier) or identifier in ids:
                raise ValueError("Invalid or duplicate interactive ID")
            ids[identifier] = node
        if kind == "switch" and type(node["value"]) is not bool:
            raise ValueError("Switch requires a boolean")
        if kind == "progress" and (type(node["value"]) not in (int, float) or not 0 <= node["value"] <= 1):
            raise ValueError("Progress must be within 0..1")
        if kind == "spacer" and (type(node["size"]) not in (int, float) or not 0 <= node["size"] <= 32 or node["size"] % 1):
            raise ValueError("Spacer must be an integer within 0..32")
        if kind == "icon" and node["glyph"] not in CONTRACT["icons"]:
            raise ValueError("Unknown icon")

    walk(tree, 1)
    return ids


def input_ok(value):
    return string_ok(value, 128) and len(value.encode()) <= 128 and not any(ch in "\t\n" for ch in value)


def validate_event(event, previous, api):
    kind, identifier = event.get("kind"), event.get("id")
    if kind == "onResume" and identifier == "" and api == 2:
        return
    if previous is None:
        raise ValueError("Events require an initial frame")
    if kind == "onTimer" and api == 2 and any(timer["id"] == identifier for timer in previous["timers"]):
        return
    node = validate_tree(previous["ui"], api).get(identifier)
    if not node:
        raise ValueError("Event target is absent from the preceding frame")
    value = event.get("value")
    if kind == "onClick" and node["type"] == "button" and "value" not in event:
        return
    if api == 2 and kind == "onChange" and node["type"] == "switch" and type(value) is bool and value != node["value"]:
        return
    if api == 2 and kind in ("onChange", "onSubmit") and node["type"] == "textInput" and input_ok(value):
        return
    raise ValueError("Event does not match the interactive component")


def execute(manifest, source, system, previous=None, event=None):
    api = manifest["apiVersion"]
    grants = {permission: True for permission in manifest["permissions"]}
    if event:
        validate_event(event, previous, api)
    state = previous["state"] if previous else ({} if api == 2 else "")
    system = {key: system[key] for key in ("device.time", "battery.level", "battery.charging") if key in system}
    level = system.get("battery.level")
    if level is not None and (type(level) is not int or not 0 <= level <= 100):
        raise ValueError("Synthetic battery level must be an integer from 0 to 100")
    charging = system.get("battery.charging")
    if charging is not None and type(charging) is not bool:
        raise ValueError("Synthetic charging status must be boolean")
    clock = system.get("device.time")
    if clock is not None and (not isinstance(clock, dict) or set(clock) != {"date", "time12", "time24"}
                              or not all(string_ok(item, 32) for item in clock.values())):
        raise ValueError("Synthetic time requires date, time12 and time24 strings")
    cfg = dict(api=api, permissions=grants, state=state, system=system, source=source.decode(), event=event)
    frame = json.loads(run_lua([str(Path(__file__).with_name("runner.lua"))], ("return " + literal(cfg)).encode()))
    validate_tree(frame["ui"], api)
    result = frame["state"]
    if api == 1:
        if not string_ok(result, 512) or len(result.encode()) > 512:
            raise ValueError("Invalid v1 state")
    elif not isinstance(result, dict) or len(result) > 16 or len(canonical(result)) > 512 or (
        result and "state.local" not in grants
    ) or any(not STATE_KEY.fullmatch(k) or
             (type(v) not in (bool, int, float) and not string_ok(v, 128)) for k, v in result.items()):
        raise ValueError("Invalid or unauthorized v2 state")
    return frame


def scenario(manifest, source, suite):
    frame = None
    frames = []
    system = suite.get("system", {}).copy()
    for index, step in enumerate(suite.get("steps", [{}])):
        system.update(step.get("system", {}))
        if step.get("fresh_instance"):
            frame = None
        frame = execute(manifest, source, system, frame, step.get("event"))
        for key, value in step.get("expect", {}).items():
            if frame.get(key) != value:
                raise ValueError(f"Step {index + 1}: expected {key} to match")
        text = step.get("text")
        if text is not None:
            def contains(node):
                return node.get("value") == text or node.get("text") == text or any(map(contains, node.get("children", [])))
            if not contains(frame["ui"]):
                raise ValueError(f"Step {index + 1}: expected visible text is absent")
        frames.append(frame)
    return frames
