# Getting started

Use Python 3.11+, PUC Lua 5.4 and OpenSSL 3. The SDK itself has no Python runtime dependencies.

## Termux (ARM64)

    pkg update
    pkg install python git lua54 openssl-tool
    git clone https://github.com/PseudoEF/HyprDroid-SDK
    cd HyprDroid-SDK
    python -m venv .venv
    . .venv/bin/activate
    pip install -e .
    hyp doctor
    hyp create my-tile --template counter --api 2
    cd my-tile
    hyp validate .
    hyp test .
    hyp build .
    hyp inspect dist/my-tile-1.0.0.hyp
    hyp preview . --serve --open

If Android does not open the browser, open the printed HTTP URL manually.
The SDK serves only the generated HTML on 127.0.0.1. Use Ctrl+C to stop it.
For an alternate port, use hyp preview . --serve --port 8765. The original
hyp preview . still writes preview.html without starting a server.

### Generate a developer key and sign a package

Run from my-tile after building it. Choose a new directory outside the project.

    (umask 077; mkdir "$HOME/.hyp-my-tile-keys")
    hyp keygen --private "$HOME/.hyp-my-tile-keys/developer.pem" --public "$HOME/.hyp-my-tile-keys/developer.pub.pem"
    hyp sign dist/my-tile-1.0.0.hyp --private "$HOME/.hyp-my-tile-keys/developer.pem" --url https://example.invalid/my-tile-1.0.0.hyp --output dist/my-tile.signature.json
    hyp verify dist/my-tile-1.0.0.hyp --signature dist/my-tile.signature.json --public "$HOME/.hyp-my-tile-keys/developer.pub.pem"

The URL is signed metadata. This example does not upload anything. Keep
developer.pem private. A verified developer signature does not grant
execution permission in the ordinary HyprDroid app.

### Pixel 9 compatibility record for SDK 0.1.0

The owner verified pip installation, doctor, counter scaffolding, validation,
Lua contract tests, build, inspect, reproducible SHA-256 and HTTP preview on
Android 17 with Termux, Python 3.14.10, Lua 5.4 and OpenSSL 3.6.5. Chrome
could not open the private HTML through the Termux content URI. Manually
serving the generated HTML through localhost worked. The Ed25519 self-test
passed. The owner has yet to complete the manual keygen, sign and verify
sequence on the device.

The generated API 2 counter had ui.tile and state.local capabilities.
Its my-tile-1.0.0.hyp was 698 bytes with SHA-256
fc61de1a6d628f1bc02e2227ba7e90cce33934129ede2b4d4ae471a9a84832ab.

[Termux Lua 5.4 package](https://github.com/termux/termux-packages/blob/master/packages/lua54/build.sh)
· [OpenSSL command-line package](https://github.com/termux/termux-packages/blob/master/packages/openssl/openssl-tool.subpackage.sh)

## Linux

Install Lua 5.4 and OpenSSL through your distribution. Debian and Ubuntu use lua5.4 and
openssl. On Arch, select lua54 rather than the unversioned Lua if it has moved to a newer
major version. Install Python with venv support, create a virtual environment and run
pip install . from the checkout or install the wheel from the release.

## Windows

Install Python 3.11+ and MSYS2. In its UCRT64 shell install these native dependencies:

    pacman -S mingw-w64-ucrt-x86_64-lua54 mingw-w64-ucrt-x86_64-openssl

In PowerShell add the UCRT64 bin directory to PATH for this session, or set HYP_LUA and
HYP_OPENSSL to the full executable paths. For a default installation:

    $env:Path = "C:\msys64\ucrt64\bin;$env:Path"
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install .
    .venv\Scripts\hyp.exe doctor

[MSYS2 Lua 5.4 package](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-lua54)

## macOS

Use a Lua 5.4 and OpenSSL 3 executable from your package manager. Set HYP_LUA and
HYP_OPENSSL if your unversioned executables are different. macOS is not covered by release CI.

## Кратко по-русски

Установите Python, Lua 5.4 и OpenSSL 3 по инструкции для вашей платформы.
Создайте проект командой hyp create my-tile --template counter --api 2.
Внутри проекта выполните hyp validate ., hyp test ., hyp build . и hyp preview .
Подпись разработчика не меняет список модулей, разрешённых в HyprDroid.
