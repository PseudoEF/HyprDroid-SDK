"""Compare recorded upstream sources against an explicit Core checkout or pinned GitHub revision."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--core-root", type=Path)
args = parser.parse_args()
contract = json.loads((Path(__file__).resolve().parents[1] / "src/hyprdroid_sdk/contract.json").read_text())
changed = []
for filename, signed_digest in contract["upstream_files"].items():
    if args.core_root:
        content = (args.core_root / filename).read_bytes()
    else:
        url = f"https://raw.githubusercontent.com/PseudoEF/HyprDroid/{contract['core']}/{filename}"
        with urlopen(url, timeout=15) as response:
            content = response.read(1048576)
    if hashlib.sha256(content).hexdigest() != signed_digest:
        changed.append(filename)
if changed:
    raise SystemExit("Core contract sources changed; review these files and refresh shared vectors:\n" + "\n".join(changed))
print("Core contract source fingerprints match")
