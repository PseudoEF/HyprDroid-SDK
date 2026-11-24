import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from hyprdroid_sdk.packer import build, inspect, project, validate_manifest
from hyprdroid_sdk.project import create, SOURCES
from hyprdroid_sdk.runtime import execute, scenario, validate_tree
from hyprdroid_sdk.preview import page
from hyprdroid_sdk.signing import keygen, public_der, raw_verify, sign, verify

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "tests/vectors"


class SDKTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def tile(self, template="basic"):
        path = self.root / template
        create(path, template, 2)
        return path

    def test_templates_and_deterministic_build(self):
        for template in SOURCES:
            with self.subTest(template=template):
                path = self.tile(template)
                manifest, source = project(path)
                scenario(manifest, source, json.loads((path / "hyp-tests.json").read_text()))
                one, two = (build(path, self.root / dirname) for dirname in ("one", "two"))
                self.assertEqual(one.read_bytes(), two.read_bytes())
                self.assertEqual(inspect(one)[0]["manifest"], manifest)

    def test_no_overwrite(self):
        self.tile()
        with self.assertRaises(FileExistsError):
            self.tile()

    def test_api_v1_template(self):
        path = self.root / "old-api"
        create(path, "basic", 1)
        manifest, source = project(path)
        self.assertEqual(execute(manifest, source, {})["ui"]["type"], "text")

    def test_official_signatures_and_exact_archive_bytes(self):
        public = VECTORS / "publisher.pem"
        envelope = json.loads((VECTORS / "catalog.json").read_text())
        self.assertEqual(public_der(public)[-32:].hex(),
                         "6c8604bfb78dcadbd20554d47c686b04d3ea98f6339eaa3a4b54ef5f2839c093")
        payload = base64.b64decode(envelope["payload"], validate=True)
        raw_verify(b"HyprDroid catalog v1\n" + payload, envelope["signature"], public)
        catalog = json.loads(payload)
        self.assertEqual(catalog["revision"], 2)
        self.assertEqual({record["manifest"]["id"] for record in catalog["packages"]},
                         {"hello-tile", "clock-tile", "battery-tile"})
        for record in catalog["packages"]:
            source = ROOT / "examples" / record["manifest"]["id"]
            manifest, script = project(source)
            scenario(manifest, script, json.loads((source / "hyp-tests.json").read_text()))
            artifact = build(source, self.root / "official")
            published = VECTORS / artifact.name
            self.assertEqual(published.read_bytes(), artifact.read_bytes())
            self.assertTrue(verify(published, record, public)["signature_valid"])

    def signed_fixture(self):
        artifact = build(self.tile(), self.root / "dist")
        private, public = self.root / "private.pem", self.root / "public.pem"
        keygen(private, public)
        record = sign(artifact, private, f"https://example.org/{artifact.name}", self.root / "record.json")
        return artifact, record, private, public

    def test_signature_and_trust_are_distinct(self):
        artifact, record, private, public = self.signed_fixture()
        pin = hashlib.sha256(public_der(public)).hexdigest()
        self.assertEqual(verify(artifact, record, public, pin)["publisher_trust"], "explicit caller pin")
        with self.assertRaises(ValueError):
            verify(artifact, record, public, "00" * 32)
        if os.name == "posix":
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            keygen(private, public)

    def test_wrong_signature_and_archive_tampering(self):
        artifact, record, _, public = self.signed_fixture()
        with self.assertRaises(ValueError):
            verify(artifact, {**record, "signature": "00" * 64}, public)
        artifact.write_bytes(artifact.read_bytes() + b"changed")
        with self.assertRaises(ValueError):
            verify(artifact, record, public)

    def test_bad_zip(self):
        path = self.root / "bad.hyp"
        path.write_text("not zip")
        with self.assertRaises(zipfile.BadZipFile):
            inspect(path)

    def test_zip_traversal(self):
        path = self.root / "bad.hyp"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("../outside.lua", b"return")
        with self.assertRaisesRegex(ValueError, "Unsafe ZIP member"):
            inspect(path)

    def test_expanded_size_limit(self):
        path = self.root / "large.hyp"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("main.lua", b"a" * 16385)
        with self.assertRaisesRegex(ValueError, "exceeds bounds"):
            inspect(path)

    def test_unknown_capability(self):
        manifest, _ = project(self.tile())
        with self.assertRaises(ValueError):
            validate_manifest({**manifest, "permissions": ["ui.tile", "system.contacts"]})

    def test_loop_terminates(self):
        manifest, _ = project(self.tile())
        with self.assertRaisesRegex(ValueError, "instruction limit|wall-time"):
            execute(manifest, b"while true do end", {})

    def test_capability_filters(self):
        manifest, _ = project(self.tile())
        result = execute(manifest, b'ui.render({type="text", value=system.get("battery.level") or "nil"})',
                         {"battery.level": 78})
        self.assertEqual(result["ui"]["value"], "nil")
        with self.assertRaisesRegex(ValueError, "state.local denied"):
            execute(manifest, b'state.set("flag", true)', {})

    def test_no_standard_libraries(self):
        manifest, _ = project(self.tile())
        result = execute(manifest, b'''
          local safe = io == nil and os == nil and debug == nil and require == nil
          ui.render({type="text", value=safe and "safe" or "failed"})
        ''', {})
        self.assertEqual(result["ui"]["value"], "safe")
        with self.assertRaises(ValueError):
            execute(manifest, b'local method = ("x").rep; ui.render({type="text", value=method("x", 1)})', {})

    def test_bad_timer_and_duplicate_ui_id(self):
        manifest, _ = project(self.tile())
        with self.assertRaisesRegex(ValueError, "invalid interval"):
            execute(manifest, b'timer.every("tick", 999)', {})
        node = {"type": "button", "id": "same", "text": "Click"}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_tree({"type": "row", "children": [node, node]}, 2)

    def test_preview_escapes_html(self):
        markup = page({"type": "textInput", "id": "safe", "value": '<script>" onfocus="alert(1)'}, 2)
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertIn("&quot; onfocus=&quot;", markup)

    def test_cli_smoke(self):
        path = self.root / "my-module"
        def cli(*args):
            return subprocess.run(["hyp", *map(str, args)], check=True, capture_output=True, text=True).stdout
        self.assertIn("0.1.0", cli("--version"))
        cli("create", path, "--template", "counter")
        cli("validate", path)
        self.assertTrue(json.loads(cli("test", path, "--json"))["ok"])
        cli("build", path, "--output", self.root / "dist")
        cli("inspect", self.root / "dist" / "my-module-1.0.0.hyp")
        cli("preview", path, "--output", self.root / "preview.html")
