"""Ed25519 through OpenSSL 3. Keys are never part of the package."""

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from .packer import bounded_read, canonical, inspect, read_json
from .runtime import environment


def openssl(args, data=None, env=None):
    program = shutil.which(os.environ.get("HYP_OPENSSL", "openssl"))
    if not program:
        raise ValueError("OpenSSL 3 not found. Install openssl-tool on Termux or set HYP_OPENSSL")
    try:
        result = subprocess.run([program, *map(str, args)], input=data, capture_output=True,
                                timeout=10, env=environment() if env is None else env)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("OpenSSL timed out") from exc
    if result.returncode:
        raise ValueError(f"OpenSSL {args[0]} failed. Check the Ed25519 key and signature")
    return result.stdout


def exclusive(path, data, mode=0o644):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode), "wb") as stream:
        stream.write(data)


def keygen(private_path, public_path):
    if private_path.exists() or public_path.exists() or private_path.absolute() == public_path.absolute():
        raise ValueError("Use two different, unused key paths")
    private = openssl(["genpkey", "-algorithm", "ED25519"])
    public = openssl(["pkey", "-pubout"], private)
    exclusive(private_path, private, mode=0o600)
    try:
        exclusive(public_path, public)
    except OSError:
        private_path.unlink()
        raise


def raw_sign(data, private_key):
    with tempfile.TemporaryDirectory() as tmp:
        message = Path(tmp) / "message"
        message.write_bytes(data)
        signature = openssl(["pkeyutl", "-sign", "-rawin", "-inkey", private_key.resolve(), "-in", message])
        if len(signature) != 64:
            raise ValueError("Expected an Ed25519 signature")
        return signature.hex()


def sign(artifact, private_key, url, output):
    report, raw = inspect(artifact)
    parsed = urlparse(url)
    name = f"{report['manifest']['id']}-{report['manifest']['version']}.hyp"
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.path.endswith("/" + name):
        raise ValueError("Use an HTTPS asset URL ending in the canonical .hyp filename")
    record = {"manifest": report["manifest"], "sha256": report["sha256"], "signature": raw_sign(raw, private_key),
              "url": url, "status": "active"}
    exclusive(output, canonical(record) + b"\n")
    return record


def public_der(key):
    der = openssl(["pkey", "-pubin", "-in", key.resolve(), "-pubout", "-outform", "DER"])
    # RFC 8410 Ed25519 SubjectPublicKeyInfo with a single 32-byte public key.
    if len(der) != 44 or not der.startswith(bytes.fromhex("302a300506032b6570032100")):
        raise ValueError("Expected an Ed25519 public key")
    return der


def raw_verify(data, signature, public_key):
    if not isinstance(signature, str) or len(signature) != 128:
        raise ValueError("Expected a 64-byte hexadecimal Ed25519 signature")
    try:
        decoded = bytes.fromhex(signature)
    except ValueError as exc:
        raise ValueError("Invalid hexadecimal signature") from exc
    if len(decoded) != 64:
        raise ValueError("Invalid Ed25519 signature length")
    with tempfile.TemporaryDirectory() as tmp:
        message, sig = Path(tmp) / "message", Path(tmp) / "signature"
        message.write_bytes(data)
        sig.write_bytes(decoded)
        openssl(["pkeyutl", "-verify", "-pubin", "-inkey", public_key.resolve(), "-rawin",
                 "-in", message, "-sigfile", sig])


def load_record(path):
    record = read_json(bounded_read(path, 65536))
    if not isinstance(record, dict) or set(record) != {"manifest", "sha256", "signature", "url", "status"}:
        raise ValueError("Expected a HyprDroid catalogue record")
    return record


def verify(artifact, record, public_key, trusted_fingerprint=None):
    info, raw = inspect(artifact)
    if record["manifest"] != info["manifest"] or record["sha256"] != info["sha256"]:
        raise ValueError("Archive manifest or SHA-256 differs from the record")
    fingerprint = hashlib.sha256(public_der(public_key)).hexdigest()
    raw_verify(raw, record["signature"], public_key)
    if trusted_fingerprint and fingerprint != trusted_fingerprint.lower():
        raise ValueError("Signature valid; publisher fingerprint differs from your trust pin")
    return {"signature_valid": True, "publisher_fingerprint_sha256": fingerprint,
            "publisher_trust": "explicit caller pin" if trusted_fingerprint else "not established",
            "core_execution_admission": "not asserted", "sha256": info["sha256"]}
