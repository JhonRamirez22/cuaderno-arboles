"""Árbol de carpetas y notas.

Cada elemento es un nodo: las carpetas pueden tener hijos (otras carpetas o
notas) y las notas son hojas. La raíz es una carpeta que nunca se elimina.
"""

import uuid

KINDS = ("folder", "note")
MAX_NODES = 500
MAX_NAME = 80
MAX_CONTENT = 10_000
MAX_TOTAL_CONTENT = 1_000_000
MAX_DEPTH = 10


class NotebookError(ValueError):
    """Operación inválida. El mensaje está pensado para mostrarse al usuario."""


class NotFoundError(NotebookError):
    """El elemento pedido no existe."""


class Node:
    """Nodo del árbol: una carpeta o una nota."""

    def __init__(self, id, name, kind, content=""):
        self.id = id
        self.name = name
        self.kind = kind
        self.content = content
        self.parent = None
        self.children = []

    @property
    def is_folder(self):
        return self.kind == "folder"


def clean_name(name):
    if not isinstance(name, str) or not name.strip():
        raise NotebookError("El nombre no puede estar vacío")
    name = " ".join(name.split())
    if len(name) > MAX_NAME:
        raise NotebookError(f"El nombre es demasiado largo (máximo {MAX_NAME} caracteres)")
    if "/" in name:
        raise NotebookError("El nombre no puede contener «/»")
    return name


def check_content(text):
    if not isinstance(text, str):
        raise NotebookError("El contenido de la nota no es válido")
    if len(text) > MAX_CONTENT:
        raise NotebookError(f"La nota es demasiado larga (máximo {MAX_CONTENT} caracteres)")


def _sort_children(folder):
    """Carpetas primero y luego notas, cada grupo por nombre."""
    folder.children.sort(key=lambda child: (not child.is_folder, child.name.casefold()))


class Notebook:
    """Árbol completo con sus operaciones.

    `_index` (id -> Node) permite llegar a un nodo sin recorrer el árbol. La
    jerarquía real vive en los punteros `parent` y `children`.
    """

    def __init__(self, root=None):
        self.root = root or Node("root", "Mi cuaderno", "folder")
        self._index = {node.id: node for node in self.walk()}

    def __len__(self):
        return len(self._index)

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def get(self, id):
        node = self._index.get(id)
        if node is None:
            raise NotFoundError("Ese elemento ya no existe")
        return node

    def walk(self, start=None):
        """Recorrido en profundidad (preorden), sin recursión."""
        stack = [start or self.root]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    def path(self, id):
        """Nodos desde la raíz hasta el elemento."""
        nodes = []
        current = self.get(id)
        while current is not None:
            nodes.append(current)
            current = current.parent
        return nodes[::-1]

    def depth(self, id):
        return len(self.path(id)) - 1

    def note_count(self, node):
        return sum(1 for n in self.walk(node) if not n.is_folder)

    def stats(self):
        folders = sum(1 for n in self.walk() if n.is_folder) - 1
        return {"folders": folders, "notes": self.note_count(self.root)}

    def search(self, text, limit=30):
        """Elementos cuyo nombre o contenido contiene `text`."""
        needle = text.strip().casefold() if isinstance(text, str) else ""
        if not needle:
            return []
        results = []
        for node in self.walk():
            if node is self.root:
                continue
            in_name = needle in node.name.casefold()
            position = node.content.casefold().find(needle) if not node.is_folder else -1
            if not in_name and position < 0:
                continue
            location = " / ".join(n.name for n in self.path(node.id)[:-1])
            snippet = ""
            if position >= 0:
                start = max(0, position - 30)
                snippet = " ".join(node.content[start:start + 90].split())
                snippet = ("…" if start > 0 else "") + snippet + ("…" if start + 90 < len(node.content) else "")
            results.append({
                "id": node.id,
                "name": node.name,
                "kind": node.kind,
                "location": location,
                "snippet": snippet,
            })
            if len(results) >= limit:
                break
        return results

    # ------------------------------------------------------------------
    # Modificación
    # ------------------------------------------------------------------

    def create(self, parent_id, kind, name, content=""):
        parent = self.get(parent_id)
        if not parent.is_folder:
            raise NotebookError("Solo las carpetas pueden contener elementos")
        if kind not in KINDS:
            raise NotebookError("Tipo de elemento inválido")
        name = clean_name(name)
        if kind == "folder":
            content = ""
        else:
            check_content(content)
        self._check_free_name(parent, name)
        if len(self) >= MAX_NODES:
            raise NotebookError(f"Se alcanzó el máximo de {MAX_NODES} elementos")
        if self.depth(parent_id) + 1 > MAX_DEPTH:
            raise NotebookError(f"Demasiados niveles de carpetas (máximo {MAX_DEPTH})")

        node = Node(uuid.uuid4().hex[:10], name, kind, content)
        node.parent = parent
        parent.children.append(node)
        self._index[node.id] = node
        _sort_children(parent)
        return node

    def rename(self, id, name):
        node = self.get(id)
        name = clean_name(name)
        if node.parent is not None:
            self._check_free_name(node.parent, name, ignore=node)
        node.name = name
        if node.parent is not None:
            _sort_children(node.parent)
        return node

    def move(self, id, new_parent_id):
        """Mueve un elemento (con todo lo que contiene) a otra carpeta."""
        node = self.get(id)
        if node is self.root:
            raise NotebookError("La carpeta principal no se puede mover")
        target = self.get(new_parent_id)
        if not target.is_folder:
            raise NotebookError("Solo se puede mover a una carpeta")

        # Evita ciclos: el destino no puede estar dentro de lo que se mueve.
        current = target
        while current is not None:
            if current is node:
                raise NotebookError("No puedes mover una carpeta dentro de sí misma")
            current = current.parent

        if target is node.parent:
            return node
        self._check_free_name(target, node.name)
        if self.depth(new_parent_id) + 1 + self._height(node) > MAX_DEPTH:
            raise NotebookError(f"Demasiados niveles de carpetas (máximo {MAX_DEPTH})")

        node.parent.children.remove(node)
        node.parent = target
        target.children.append(node)
        _sort_children(target)
        return node

    def delete(self, id):
        """Elimina el elemento y todo su subárbol. Devuelve cuántos nodos se borraron."""
        node = self.get(id)
        if node is self.root:
            raise NotebookError("La carpeta principal no se puede eliminar")
        removed = [n.id for n in self.walk(node)]
        for removed_id in removed:
            del self._index[removed_id]
        node.parent.children.remove(node)
        node.parent = None
        return len(removed)

    def save(self, id, content):
        node = self.get(id)
        if node.is_folder:
            raise NotebookError("Las carpetas no tienen contenido")
        check_content(content)
        self._check_total_content(len(content) - len(node.content))
        node.content = content
        return node

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self, node=None):
        node = node or self.root
        data = {"id": node.id, "name": node.name, "kind": node.kind}
        if node.is_folder:
            data["children"] = [self.to_dict(child) for child in node.children]
        else:
            data["content"] = node.content
        return data

    @classmethod
    def from_dict(cls, data):
        """Reconstruye y valida un árbol recibido del cliente."""
        root = _load(data, depth=0, seen=set())
        if not root.is_folder:
            raise NotebookError("La raíz debe ser una carpeta")
        notebook = cls(root)
        notebook._check_total_content(0)
        return notebook

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    def _check_free_name(self, parent, name, ignore=None):
        for child in parent.children:
            if child is not ignore and child.name.casefold() == name.casefold():
                raise NotebookError(f"Ya existe «{name}» en «{parent.name}»")

    def _check_total_content(self, extra):
        total = sum(len(n.content) for n in self.walk()) + extra
        if total > MAX_TOTAL_CONTENT:
            raise NotebookError("El cuaderno es demasiado grande; elimina algunas notas")

    @staticmethod
    def _height(node):
        """Niveles que hay por debajo de `node`."""
        best = 0
        stack = [(node, 0)]
        while stack:
            current, level = stack.pop()
            best = max(best, level)
            stack.extend((child, level + 1) for child in current.children)
        return best


def _load(data, depth, seen):
    if depth > MAX_DEPTH:
        raise NotebookError("El cuaderno tiene demasiados niveles")
    if not isinstance(data, dict):
        raise NotebookError("El cuaderno no es válido")
    if len(seen) >= MAX_NODES:
        raise NotebookError(f"Se alcanzó el máximo de {MAX_NODES} elementos")

    id = data.get("id")
    if not isinstance(id, str) or not 0 < len(id) <= 40 or id in seen:
        raise NotebookError("El cuaderno tiene identificadores inválidos")
    kind = data.get("kind")
    if kind not in KINDS:
        raise NotebookError("El cuaderno tiene un tipo de elemento inválido")
    seen.add(id)

    node = Node(id, clean_name(data.get("name")), kind)
    if kind == "note":
        content = data.get("content", "")
        check_content(content)
        node.content = content
        if data.get("children"):
            raise NotebookError("Una nota no puede contener elementos")
        return node

    names = set()
    for child_data in data.get("children") or []:
        child = _load(child_data, depth + 1, seen)
        key = child.name.casefold()
        if key in names:
            raise NotebookError(f"Hay dos elementos llamados «{child.name}» en «{node.name}»")
        names.add(key)
        child.parent = node
        node.children.append(child)
    _sort_children(node)
    return node


WELCOME = """Bienvenido a tu cuaderno.

- A la izquierda ves tus carpetas y notas. Haz clic en una carpeta para abrirla.
- «Nueva nota» y «Nueva carpeta» crean dentro de la carpeta que tengas abierta.
- Arrastra cualquier elemento sobre una carpeta para moverlo.
- Lo que escribas se guarda solo, en este navegador.
- El buscador mira nombres y también el texto de las notas.

Curiosidad: tu cuaderno es un árbol. Cada carpeta es un nodo y sus hijos son lo que contiene. Las notas son las hojas.
"""


def sample_notebook():
    """Cuaderno de ejemplo para la primera vez."""
    notebook = Notebook()
    notebook.create("root", "note", "Bienvenida", WELCOME)

    university = notebook.create("root", "folder", "Universidad")
    structures = notebook.create(university.id, "folder", "Estructuras de datos")
    notebook.create(structures.id, "note", "Árboles", (
        "Un árbol es una estructura jerárquica de nodos.\n\n"
        "- Raíz: el nodo de arriba, sin padre.\n"
        "- Hoja: un nodo sin hijos.\n"
        "- Altura: niveles desde la raíz hasta la hoja más lejana.\n\n"
        "Recorridos: preorden, inorden, postorden y por niveles."
    ))
    notebook.create(structures.id, "note", "Pendientes", "- Entregar el proyecto de árboles\n- Repasar recorridos\n")
    calculus = notebook.create(university.id, "folder", "Cálculo")
    notebook.create(calculus.id, "note", "Derivadas", "(x^n)' = n·x^(n-1)\n(sen x)' = cos x\n(e^x)' = e^x\n")

    personal = notebook.create("root", "folder", "Personal")
    notebook.create(personal.id, "note", "Ideas de proyectos", "- App para repartir gastos\n- Recetario con lista de compras\n")
    notebook.create(personal.id, "note", "Lista de compras", "Café\nPan\nFrutas\n")
    return notebook
