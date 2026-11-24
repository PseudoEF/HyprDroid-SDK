"""Serve a single generated preview from memory on IPv4 loopback."""

import shutil
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer


def preview_server(markup, port):
    class PreviewHandler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(5)
            super().setup()

        def respond(self, include_body):
            # BaseHTTPRequestHandler normalizes leading slashes. Check the raw target too.
            target = self.requestline.split()[1]
            if target not in ("/", "/preview.html"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(markup)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if include_body:
                self.wfile.write(markup)

        def do_GET(self):
            self.respond(True)

        def do_HEAD(self):
            self.respond(False)

        def log_message(self, format, *args):
            pass

    class PreviewHTTPServer(HTTPServer):
        # Windows SO_REUSEADDR can allow a second server to steal this port.
        allow_reuse_address = sys.platform != "win32"

    try:
        return PreviewHTTPServer(("127.0.0.1", port), PreviewHandler)
    except OSError as exc:
        raise ValueError(f"Cannot listen on 127.0.0.1:{port} ({exc}). Try another --port.") from exc


def open_browser(url):
    try:
        if sys.platform == "android" or shutil.which("termux-info"):
            command = shutil.which("termux-open")
            return bool(command and subprocess.run([command, url], timeout=5, check=False).returncode == 0)
        return webbrowser.open(url, new=2)
    except (OSError, webbrowser.Error, subprocess.TimeoutExpired):
        return False


def serve_preview(markup, port, launch_browser):
    with preview_server(markup, port) as server:
        url = f"http://127.0.0.1:{server.server_port}/preview.html"
        print(f"Preview: {url} (Ctrl+C to stop)", flush=True)
        try:
            if launch_browser and not open_browser(url):
                print(f"Could not open a browser. Open {url} manually.", file=sys.stderr)
            server.serve_forever()
        except KeyboardInterrupt:
            return
