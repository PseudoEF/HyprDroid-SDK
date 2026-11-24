import http.client
from http.server import HTTPServer
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from threading import Thread
from unittest.mock import patch

from hyprdroid_sdk.preview_server import open_browser, preview_server, serve_preview


class PreviewServerTest(unittest.TestCase):
    def test_only_preview_is_served(self):
        markup = b"<html>generated preview</html>"
        with preview_server(markup, 0) as server:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            thread = Thread(target=server.serve_forever)
            thread.start()
            try:
                for path, status in (
                    ("/", 200), ("/preview.html", 200), ("/keys/", 404),
                    ("/manifest.json", 404), ("/../preview.html", 404),
                    ("/%2e%2e/preview.html", 404), ("//preview.html", 404),
                ):
                    with self.subTest(path=path):
                        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                        try:
                            conn.request("GET", path)
                            response = conn.getresponse()
                            self.assertEqual(response.status, status)
                            if status == 200:
                                self.assertEqual(response.read(), markup)
                        finally:
                            conn.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())

    def test_busy_port(self):
        with preview_server(b"preview", 0) as server:
            with self.assertRaisesRegex(ValueError, "Try another --port"):
                preview_server(b"preview", server.server_port)

    def test_interrupt_closes_socket_and_browser_failure_prints_url(self):
        with patch("hyprdroid_sdk.preview_server.open_browser", return_value=False):
            with patch.object(HTTPServer,
                              "serve_forever", side_effect=KeyboardInterrupt):
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    serve_preview(b"preview", 0, True)
        url = stdout.getvalue().split()[1]
        self.assertIn(url, stderr.getvalue())
        port = int(url.split(":")[2].split("/")[0])
        with preview_server(b"preview", port):
            pass

    def test_termux_opens_http_url(self):
        url = "http://127.0.0.1:8765/preview.html"
        with patch("sys.platform", "android"):
            with patch("shutil.which", return_value="/termux-open"):
                with patch("subprocess.run") as run:
                    run.return_value.returncode = 0
                    self.assertTrue(open_browser(url))
                    run.assert_called_once_with(["/termux-open", url], timeout=5, check=False)

    def test_desktop_browser_error(self):
        with patch("sys.platform", "linux"), patch("shutil.which", return_value=None):
            with patch("webbrowser.open", side_effect=OSError):
                self.assertFalse(open_browser("http://127.0.0.1:8765/preview.html"))
