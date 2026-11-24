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
    hyp preview .

Open preview.html in a browser. On Android you can copy it to Downloads after granting
Termux storage access, or use the command below from the project directory and open
http://127.0.0.1:8765/preview.html. Run this command in a directory containing only files
you want the local server to expose. Keep private keys elsewhere.

    python -m http.server 8765 --bind 127.0.0.1

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
