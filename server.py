"""Servidor local: sirve la interfaz (public/) y la API (/api/*).

    python3 server.py          # http://localhost:8000
    python3 server.py 5000     # otro puerto

Solo usa la biblioteca estándar de Python.
"""

import os
import sys
from http.server import HTTPServer
from urllib.parse import unquote, urlparse

from cuaderno.web import ApiHandler

PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


class LocalHandler(ApiHandler):

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return super().do_GET()
        self._serve_file(path)

    def _serve_file(self, path):
        if path in ("", "/"):
            path = "/index.html"
        file_path = os.path.normpath(os.path.join(PUBLIC, unquote(path).lstrip("/")))
        if not file_path.startswith(PUBLIC + os.sep) or not os.path.isfile(file_path):
            self.send_error(404)
            return
        with open(file_path, "rb") as file:
            content = file.read()
        self.send_response(200)
        self.send_header("Content-Type", TYPES.get(os.path.splitext(file_path)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = HTTPServer(("127.0.0.1", port), LocalHandler)
    print(f"Cuaderno disponible en http://localhost:{port}  (Ctrl+C para salir)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()
