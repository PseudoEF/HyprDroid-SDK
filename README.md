# HyprDroid Plugin SDK

Develop, test, package and sign HyprDroid Lua tiles with Python 3.11+, Lua 5.4 and OpenSSL 3.

    pip install .
    hyp doctor
    hyp create my-tile --template counter --api 2
    cd my-tile
    hyp validate .
    hyp test . --json
    hyp build .
    hyp inspect dist/my-tile-1.0.0.hyp
    hyp preview .

Open preview.html in any browser. The static preview approximates the Android UI.

- [Getting started and platform installation](docs/GETTING_STARTED.md)
- [Plugin API v1/v2, UI, events and capabilities](docs/API.md)
- [Package format, signing and publishing](docs/PACKAGES.md)
- [Testing and security limitations](docs/TESTING.md)

SDK 0.1.0 targets Core d22bf7c. Local testing is for developer-controlled code.
Signing a package does not grant permission to execute it in Android HyprDroid.
