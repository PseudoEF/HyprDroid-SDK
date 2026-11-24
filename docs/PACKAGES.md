# Manifest, package format, signing and publishing

manifest.json requires id, version, apiVersion, runtime, entry, permissions and dependencies.
Use a lowercase ID, numeric MAJOR.MINOR.PATCH, runtime lua, a Lua root entrypoint
and an object mapping dependency IDs to minimum versions. Unknown keys and capabilities
are rejected. The SDK implements the two-file layout used by all three official modules.
Core can parse a broader archive format, but this SDK does not pack additional assets.

build writes canonical UTF-8 JSON and the exact entrypoint bytes as stored ZIP members.
File order and timestamps match the official packer. Only the manifest and entrypoint
are included. ZIP inspection validates bounded regular entries without extraction.

## Developer signing example

    mkdir -p "$HOME/.hyprdroid-keys"
    chmod 700 "$HOME/.hyprdroid-keys"
    hyp keygen --private "$HOME/.hyprdroid-keys/dev.pem" --public "$HOME/.hyprdroid-keys/dev-public.pem"
    hyp sign dist/my-tile-1.0.0.hyp --private "$HOME/.hyprdroid-keys/dev.pem" --url https://example.org/my-tile-1.0.0.hyp --output dist/record.json
    hyp verify dist/my-tile-1.0.0.hyp --signature dist/record.json --public "$HOME/.hyprdroid-keys/dev-public.pem"

The Ed25519 signature covers the complete ZIP. The detached JSON object has the
same fields as a catalogue record. It is not a signed catalogue envelope.
Verification checks signature validity and optionally a caller-supplied SHA-256 pin
of the public SubjectPublicKeyInfo DER. Explicit trust is separate from execution admission.
On Windows use a private user directory with protected ACLs. Unix private keys are
created with mode 0600.

The SDK does not publish packages or alter the public catalogue. Publishing the official
catalogue requires the Packages release process and the offline publisher key.
