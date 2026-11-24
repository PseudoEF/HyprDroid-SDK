"""Static, escaped preview of a validated frame."""

import html

from .runtime import validate_tree


def page(tree, api):
    validate_tree(tree, api)
    icons = {"CLOCK": "◷", "BATTERY": "▰", "REFRESH": "↻", "INFO": "ⓘ"}

    def render(node):
        kind = node["type"]
        if "children" in node:
            return '<div class="' + ("row" if kind == "row" else "column") + '">' + "".join(
                render(child) for child in node["children"]
            ) + "</div>"
        if kind == "text":
            return "<p>" + html.escape(node["value"]) + "</p>"
        if kind == "button":
            return "<button disabled>" + html.escape(node["text"]) + "</button>"
        if kind == "textInput":
            return '<input disabled value="' + html.escape(node["value"], quote=True) + '">'
        if kind == "switch":
            return '<input disabled type="checkbox"' + (" checked" if node["value"] else "") + ">"
        if kind == "divider":
            return "<hr>"
        if kind == "icon":
            return '<span role="img" aria-label="' + node["glyph"] + '">' + icons[node["glyph"]] + "</span>"
        if kind == "progress":
            return f'<progress max="1" value="{node["value"]}"></progress>'
        return f'<div aria-hidden="true" style="height:{int(node["size"])}px"></div>'

    cards = "".join(f'<section><h2>{name} · {width}px</h2><div class="tile {theme}" style="width:{width}px">'
                    + render(tree) + "</div></section>"
                    for theme, name in (("light", "Light"), ("dark", "Dark")) for width in (220, 360))
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>HyprDroid tile preview</title>
<style>body{font:16px system-ui;margin:20px}main{display:flex;flex-wrap:wrap;gap:20px}
.tile{box-sizing:border-box;max-width:calc(100vw - 40px);padding:12px;border-radius:12px;overflow-wrap:anywhere}
.light{background:#e8e6f3;color:#222}.dark{background:#242338;color:#eceafb}
.row{display:flex;gap:6px;align-items:center}.row>*{min-width:0}
.column{display:grid;gap:5px}p{margin:4px 0}input,progress{max-width:100%}</style>
<h1>Tile preview</h1><p>Static approximation of the Android Compose renderer.</p><main>""" + cards + "</main>"
