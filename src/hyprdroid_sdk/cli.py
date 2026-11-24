"""Command line entrypoint."""

import argparse
import json
import platform
import sys
import tempfile
import zipfile
from pathlib import Path

from . import __version__
from .packer import bounded_read, build, inspect, project, read_json
from .preview import page
from .preview_server import serve_preview
from .project import SOURCES, create
from .runtime import check_syntax, lua_executable, scenario
from .signing import exclusive, keygen, load_record, openssl, raw_sign, raw_verify, sign, verify


def parser():
    root = argparse.ArgumentParser(prog="hyp", description="HyprDroid Plugin SDK")
    root.add_argument("--version", action="version", version=f"HyprDroid SDK {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    new = commands.add_parser("create")
    new.add_argument("destination", type=Path)
    new.add_argument("--template", choices=SOURCES, default="basic")
    new.add_argument("--api", type=int, choices=(1, 2), default=2)
    for name in ("validate", "test", "build", "preview"):
        sub = commands.add_parser(name)
        sub.add_argument("project", type=Path, nargs="?", default=Path("."))
        if name in ("test", "preview"):
            sub.add_argument("--suite", type=Path)
        if name == "test":
            sub.add_argument("--json", action="store_true")
        if name == "build":
            sub.add_argument("--output", type=Path, default=Path("dist"))
        if name == "preview":
            sub.add_argument("--output", type=Path)
            sub.add_argument("--serve", action="store_true", help="serve the generated page on 127.0.0.1")
            sub.add_argument("--open", action="store_true", help="open the served URL in a browser")
            sub.add_argument("--port", type=int, help="loopback port (default: 8765)")
    for name in ("inspect", "sign", "verify"):
        sub = commands.add_parser(name)
        sub.add_argument("artifact", type=Path)
        if name == "inspect":
            sub.add_argument("--signature", type=Path)
        elif name == "verify":
            sub.add_argument("--signature", type=Path, required=True)
            sub.add_argument("--public", type=Path, required=True)
            sub.add_argument("--publisher-fingerprint")
        else:
            sub.add_argument("--private", type=Path, required=True)
            sub.add_argument("--url", required=True)
            sub.add_argument("--output", type=Path, required=True)
    keys = commands.add_parser("keygen")
    keys.add_argument("--private", type=Path, required=True)
    keys.add_argument("--public", type=Path, required=True)
    return root


def report(value):
    print(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2))


def doctor():
    print(f"Python {platform.python_version()}; Plugin API 1 and 2")
    failed = False
    try:
        print("Lua 5.4:", lua_executable())
        check_syntax(b"return 1")
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        failed = True
    try:
        print(openssl(["version"]).decode().strip())
        with tempfile.TemporaryDirectory() as tmp:
            private, public = Path(tmp) / "private.pem", Path(tmp) / "public.pem"
            keygen(private, public)
            raw_verify(b"SDK self-test", raw_sign(b"SDK self-test", private), public)
        print("Ed25519 self-test passed")
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        failed = True
    return int(failed)


def run(args):
    cmd = args.command
    if cmd == "preview":
        if args.serve and args.output is not None:
            raise ValueError("--output is only available for static preview")
        if not args.serve and (args.open or args.port is not None):
            raise ValueError("--open and --port require --serve")
        if args.port is not None and not 1 <= args.port <= 65535:
            raise ValueError("--port must be between 1 and 65535")
    if cmd == "doctor":
        return doctor()
    if cmd == "create":
        create(args.destination, args.template, args.api)
        print(args.destination)
    elif cmd == "keygen":
        keygen(args.private, args.public)
        print(f"Public key: {args.public}")
    elif cmd == "inspect":
        info, _ = inspect(args.artifact)
        if args.signature:
            signature = load_record(args.signature)
            info["detached_signature"] = {"present": True, "verified": False, "url": signature["url"]}
        report(info)
    elif cmd == "sign":
        report(sign(args.artifact, args.private, args.url, args.output))
    elif cmd == "verify":
        report(verify(args.artifact, load_record(args.signature), args.public, args.publisher_fingerprint))
    else:
        manifest, source = project(args.project)
        if cmd in ("validate", "build"):
            try:
                check_syntax(source)
            except ValueError as exc:
                raise ValueError(f"{args.project / manifest['entry']}: {exc}") from exc
        if cmd == "validate":
            for member in args.project.iterdir():
                if member.is_symlink() and member.name not in ("manifest.json", manifest["entry"]):
                    print(f"warning: {member}: ignored symlink; keep assets out of the .hyp", file=sys.stderr)
            print(f"Valid: {manifest['id']} · API {manifest['apiVersion']}")
        elif cmd == "build":
            artifact = build(args.project, args.output)
            info, _ = inspect(artifact)
            print(f"{info['sha256']}  {artifact}")
        else:
            suite_path = args.suite or args.project / "hyp-tests.json"
            suite = read_json(bounded_read(suite_path, 65536)) if cmd == "test" or args.suite else {"steps": [{}]}
            if not isinstance(suite, dict):
                raise ValueError("Contract suite must be a JSON object")
            frames = scenario(manifest, source, suite)
            if cmd == "preview":
                markup = page(frames[-1]["ui"], manifest["apiVersion"]).encode("utf-8")
                if args.serve:
                    serve_preview(markup, args.port or 8765, args.open)
                else:
                    output = args.output or Path("preview.html")
                    exclusive(output, markup)
                    print(output.resolve())
            elif args.json:
                report({"ok": True, "steps": len(frames), "frames": frames})
            else:
                print(f"Passed {len(frames)} contract steps")
    return 0


def main():
    args = parser().parse_args()
    try:
        return run(args)
    except (ValueError, OSError, zipfile.BadZipFile, KeyError, TypeError, IndexError, OverflowError) as exc:
        if args.command == "test" and args.json:
            report({"ok": False, "error": str(exc)})
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
