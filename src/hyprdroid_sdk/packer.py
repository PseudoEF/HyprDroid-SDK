"""Validate the official two-file subset and produce reproducible archives."""

import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path

CONTRACT = json.loads(Path(__file__).with_name("contract.json").read_text(encoding="utf-8"))
FIELDS = {"id", "version", "apiVersion", "runtime", "entry", "permissions", "dependencies"}
ENTRY = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}\.lua")
ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*")


def reject_duplicates(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def read_json(data):
    return json.loads(data, object_pairs_hook=reject_duplicates)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def check_id(value):
    if not isinstance(value, str) or len(value) > 80 or not ID.fullmatch(value):
        raise ValueError("Use a lowercase package ID with letters, digits and single dot or hyphen separators")


def check_version(value):
    if not isinstance(value, str) or not re.fullmatch(r"(0|[1-9][0-9]{0,9})(\.(0|[1-9][0-9]{0,9})){2}", value):
        raise ValueError("Use a numeric MAJOR.MINOR.PATCH version")
    if any(int(item) > 2147483647 for item in value.split(".")):
        raise ValueError("Version component exceeds the Core limit")


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != FIELDS:
        raise ValueError("Manifest must contain exactly " + ", ".join(sorted(FIELDS)))
    check_id(manifest["id"])
    check_version(manifest["version"])
    api = manifest["apiVersion"]
    if type(api) is not int or str(api) not in CONTRACT["apis"] or manifest["runtime"] != "lua":
        raise ValueError("Use Plugin API 1 or 2 with runtime lua")
    entry = manifest["entry"]
    if not isinstance(entry, str) or len(entry) > 80 or not ENTRY.fullmatch(entry):
        raise ValueError("Use a root-relative, single-file .lua entrypoint")
    permissions = manifest["permissions"]
    if not isinstance(permissions, list) or not all(isinstance(item, str) and item in CONTRACT["apis"][str(api)] for item in permissions):
        raise ValueError(f"Use only permissions declared for API {api}")
    if len(set(permissions)) != len(permissions) or (api == 2 and "ui.tile" not in permissions):
        raise ValueError("Remove duplicate permissions and include ui.tile for API 2")
    deps = manifest["dependencies"]
    if not isinstance(deps, dict) or len(deps) > 16 or manifest["id"] in deps:
        raise ValueError("Declare up to 16 dependencies and omit the package itself")
    for package, version in deps.items():
        check_id(package)
        check_version(version)
    return manifest


def bounded_read(path, limit):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path}: use a regular file, not a symlink")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{path}: exceeds {limit} bytes")
    return data


def validate_source(source):
    if not source or len(source) > CONTRACT["source_bytes"] or b"\x00" in source or source.startswith(b"\x1b"):
        raise ValueError("Use nonempty UTF-8 Lua text of at most 16 KiB")
    source.decode("utf-8")


def project(path):
    manifest_path = path / "manifest.json"
    try:
        manifest = validate_manifest(read_json(bounded_read(manifest_path, 16384)))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"{manifest_path}: {exc}") from exc
    source_path = path / manifest["entry"]
    source = bounded_read(source_path, CONTRACT["source_bytes"])
    try:
        validate_source(source)
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"{source_path}: {exc}") from exc
    return manifest, source


def build(path, output):
    manifest, source = project(path)
    if output.is_symlink():
        raise ValueError("Choose a regular output directory")
    output.mkdir(parents=True, exist_ok=True)
    dest = output / f"{manifest['id']}-{manifest['version']}.hyp"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in (("manifest.json", canonical(manifest)), (manifest["entry"], source)):
            member = zipfile.ZipInfo(name)
            member.create_system = 3  # The official ZIP uses Unix metadata on every platform.
            archive.writestr(member, data, compress_type=zipfile.ZIP_STORED)
    contents = buffer.getvalue()
    if dest.exists() and not dest.is_symlink() and bounded_read(dest, CONTRACT["archive_bytes"]) == contents:
        return dest
    with dest.open("xb") as stream:
        stream.write(contents)
    return dest


def inspect(path):
    raw = bounded_read(path, CONTRACT["archive_bytes"])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        names = [item.filename for item in entries]
        if len(names) != 2 or len(set(names)) != 2 or "manifest.json" not in names:
            raise ValueError("Expected exactly manifest.json and one Lua entrypoint")
        for item in entries:
            mode = item.external_attr >> 16
            if item.orig_filename != item.filename or (not ENTRY.fullmatch(item.filename) and item.filename != "manifest.json") or item.is_dir() or (
                stat.S_IFMT(mode) not in (0, stat.S_IFREG)
            ) or item.flag_bits & 1 or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError(f"Unsafe ZIP member {item.filename!r}")
            if not 0 <= item.file_size <= 16384:
                raise ValueError(f"ZIP member exceeds bounds: {item.filename}")
        with archive.open("manifest.json") as stream:
            manifest = validate_manifest(read_json(stream.read(16385)))
        if set(names) != {"manifest.json", manifest["entry"]}:
            raise ValueError("ZIP entrypoint differs from manifest")
        with archive.open(manifest["entry"]) as stream:
            validate_source(stream.read(16385))
    return {"manifest": manifest, "sha256": hashlib.sha256(raw).hexdigest(),
            "files": [{"name": item.filename, "bytes": item.file_size} for item in entries], "bytes": len(raw)}, raw
