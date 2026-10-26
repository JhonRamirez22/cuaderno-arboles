"""API HTTP del cuaderno.

La API no guarda nada: cada petición trae el árbol completo, lo valida, aplica
una operación y devuelve el árbol resultante. El navegador es quien conserva
los datos. Así funciona igual en un servidor local que en Vercel.
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from cuaderno.tree import Notebook, NotebookError, NotFoundError, sample_notebook

MAX_BODY = 4_000_000


def _tree(notebook, **extra):
    return 200, {"tree": notebook.to_dict(), **extra}


def _load(notebook, body):
    return _tree(notebook)


def _create(notebook, body):
    node = notebook.create(body.get("parent_id"), body.get("kind"), body.get("name"), body.get("content", ""))
    return _tree(notebook, id=node.id)


def _rename(notebook, body):
    notebook.rename(body.get("id"), body.get("name"))
    return _tree(notebook)


def _move(notebook, body):
    notebook.move(body.get("id"), body.get("parent_id"))
    return _tree(notebook)


def _delete(notebook, body):
    removed = notebook.delete(body.get("id"))
    return _tree(notebook, removed=removed)


def _save(notebook, body):
    notebook.save(body.get("id"), body.get("content"))
    return 200, {"saved": True}


def _search(notebook, body):
    return 200, {"results": notebook.search(body.get("q", ""))}


ACTIONS = {
    "load": _load,
    "create": _create,
    "rename": _rename,
    "move": _move,
    "delete": _delete,
    "save": _save,
    "search": _search,
}


def handle(method, path, body):
    """Devuelve (código HTTP, diccionario JSON)."""
    try:
        action = path.rstrip("/").split("/")[-1]
        if method == "GET" and action == "seed":
            return 200, {"tree": sample_notebook().to_dict()}
        if method != "POST" or action not in ACTIONS:
            return 404, {"error": "Ruta no encontrada"}
        if not isinstance(body, dict):
            raise NotebookError("Petición inválida")
        notebook = Notebook.from_dict(body.get("tree"))
        return ACTIONS[action](notebook, body)
    except NotFoundError as error:
        return 404, {"error": str(error)}
    except NotebookError as error:
        return 400, {"error": str(error)}


class ApiHandler(BaseHTTPRequestHandler):
    """Atiende únicamente /api/*. server.py lo extiende para servir los archivos."""

    def do_GET(self):
        self._respond("GET")

    def do_POST(self):
        self._respond("POST")

    def _respond(self, method):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY:
            return self._send(413, {"error": "El cuaderno es demasiado grande"})
        body = None
        if length:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._send(400, {"error": "La petición no es JSON válido"})
        status, payload = handle(method, path, body)
        self._send(status, payload)

    def _send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass
