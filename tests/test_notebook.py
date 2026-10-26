"""Pruebas del cuaderno. Ejecutar con: python3 -m unittest discover -s tests -v"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from cuaderno import Notebook, NotebookError, sample_notebook  # noqa: E402
from cuaderno.tree import MAX_CONTENT, MAX_DEPTH  # noqa: E402
from cuaderno.web import handle  # noqa: E402


def build():
    """
    Mi cuaderno
    ├── Clases
    │   ├── Árboles (nota)
    │   └── Cálculo (carpeta)
    └── Ideas (nota)
    """
    notebook = Notebook()
    classes = notebook.create("root", "folder", "Clases")
    notebook.create("root", "note", "Ideas", "proyecto de notas")
    trees = notebook.create(classes.id, "note", "Árboles", "raíz, hojas y altura")
    calculus = notebook.create(classes.id, "folder", "Cálculo")
    return notebook, classes, trees, calculus


class CreateTests(unittest.TestCase):

    def test_create_links_parent_and_child(self):
        notebook, classes, trees, _ = build()
        self.assertIs(trees.parent, classes)
        self.assertIn(trees, classes.children)
        self.assertEqual(notebook.depth(trees.id), 2)

    def test_children_are_sorted_folders_first(self):
        notebook, classes, _, _ = build()
        self.assertEqual([c.name for c in classes.children], ["Cálculo", "Árboles"])
        self.assertEqual([c.name for c in notebook.root.children], ["Clases", "Ideas"])

    def test_notes_cannot_contain_items(self):
        notebook, _, trees, _ = build()
        with self.assertRaises(NotebookError):
            notebook.create(trees.id, "note", "Hija")

    def test_duplicate_name_is_rejected_ignoring_case(self):
        notebook, classes, _, _ = build()
        with self.assertRaises(NotebookError):
            notebook.create(classes.id, "note", "árboles")

    def test_invalid_names_are_rejected(self):
        notebook, _, _, _ = build()
        for name in ("", "   ", "a/b", "x" * 200, None):
            with self.assertRaises(NotebookError):
                notebook.create("root", "note", name)

    def test_depth_limit(self):
        notebook = Notebook()
        parent = "root"
        for level in range(MAX_DEPTH):
            parent = notebook.create(parent, "folder", f"n{level}").id
        with self.assertRaises(NotebookError):
            notebook.create(parent, "folder", "demasiado")


class MoveTests(unittest.TestCase):

    def test_move_note_to_another_folder(self):
        notebook, classes, _, calculus = build()
        ideas = notebook.get(notebook.root.children[1].id)
        notebook.move(ideas.id, calculus.id)
        self.assertIs(ideas.parent, calculus)
        self.assertNotIn(ideas, notebook.root.children)

    def test_move_folder_carries_its_contents(self):
        notebook, classes, trees, _ = build()
        other = notebook.create("root", "folder", "Archivo")
        notebook.move(classes.id, other.id)
        self.assertEqual(notebook.depth(trees.id), 3)

    def test_cannot_move_folder_into_itself_or_descendant(self):
        notebook, classes, _, calculus = build()
        with self.assertRaises(NotebookError):
            notebook.move(classes.id, classes.id)
        with self.assertRaises(NotebookError):
            notebook.move(classes.id, calculus.id)

    def test_cannot_move_root_or_into_a_note(self):
        notebook, classes, trees, _ = build()
        with self.assertRaises(NotebookError):
            notebook.move("root", classes.id)
        with self.assertRaises(NotebookError):
            notebook.move(classes.id, trees.id)

    def test_move_with_name_conflict_is_rejected(self):
        notebook, classes, _, _ = build()
        notebook.create("root", "note", "Árboles")
        clash = [n for n in notebook.root.children if n.name == "Árboles"][0]
        with self.assertRaises(NotebookError):
            notebook.move(clash.id, classes.id)


class DeleteAndSaveTests(unittest.TestCase):

    def test_delete_removes_whole_subtree(self):
        notebook, classes, trees, calculus = build()
        removed = notebook.delete(classes.id)
        self.assertEqual(removed, 3)
        for node in (classes, trees, calculus):
            with self.assertRaises(NotebookError):
                notebook.get(node.id)
        self.assertEqual(len(notebook), 2)

    def test_root_cannot_be_deleted(self):
        notebook, _, _, _ = build()
        with self.assertRaises(NotebookError):
            notebook.delete("root")

    def test_save_updates_content_and_limits_size(self):
        notebook, _, trees, _ = build()
        notebook.save(trees.id, "nuevo texto")
        self.assertEqual(trees.content, "nuevo texto")
        with self.assertRaises(NotebookError):
            notebook.save(trees.id, "x" * (MAX_CONTENT + 1))

    def test_folders_have_no_content(self):
        notebook, classes, _, _ = build()
        with self.assertRaises(NotebookError):
            notebook.save(classes.id, "texto")


class QueryTests(unittest.TestCase):

    def test_search_matches_names_and_content(self):
        notebook, _, _, _ = build()
        names = [r["name"] for r in notebook.search("hojas")]
        self.assertEqual(names, ["Árboles"])
        self.assertEqual([r["name"] for r in notebook.search("ideas")], ["Ideas"])
        self.assertEqual(notebook.search("   "), [])

    def test_search_result_has_location(self):
        notebook, _, _, _ = build()
        result = notebook.search("hojas")[0]
        self.assertEqual(result["location"], "Mi cuaderno / Clases")
        self.assertIn("hojas", result["snippet"])

    def test_stats_and_counts(self):
        notebook, classes, _, _ = build()
        self.assertEqual(notebook.stats(), {"folders": 2, "notes": 2})
        self.assertEqual(notebook.note_count(classes), 1)

    def test_walk_is_preorder(self):
        notebook, _, _, _ = build()
        names = [n.name for n in notebook.walk()]
        self.assertEqual(names, ["Mi cuaderno", "Clases", "Cálculo", "Árboles", "Ideas"])


class SerializationTests(unittest.TestCase):

    def test_round_trip(self):
        notebook, _, _, _ = build()
        loaded = Notebook.from_dict(notebook.to_dict())
        self.assertEqual(loaded.to_dict(), notebook.to_dict())

    def test_sample_notebook_is_valid(self):
        data = sample_notebook().to_dict()
        self.assertEqual(Notebook.from_dict(data).to_dict(), data)

    def test_invalid_trees_are_rejected(self):
        notebook, _, _, _ = build()
        base = notebook.to_dict()

        duplicated = {"id": "a", "name": "A", "kind": "folder", "children": [
            {"id": "x", "name": "N", "kind": "note", "content": ""},
            {"id": "x", "name": "M", "kind": "note", "content": ""},
        ]}
        same_name = {"id": "a", "name": "A", "kind": "folder", "children": [
            {"id": "x", "name": "N", "kind": "note", "content": ""},
            {"id": "y", "name": "n", "kind": "note", "content": ""},
        ]}
        note_root = {"id": "a", "name": "A", "kind": "note", "content": ""}
        note_with_children = {"id": "a", "name": "A", "kind": "folder", "children": [
            {"id": "x", "name": "N", "kind": "note", "content": "", "children": [base]},
        ]}
        for bad in (None, [], "texto", duplicated, same_name, note_root, note_with_children):
            with self.assertRaises(NotebookError):
                Notebook.from_dict(bad)


class ApiTests(unittest.TestCase):

    def test_seed_and_create_flow(self):
        status, seed = handle("GET", "/api/seed", None)
        self.assertEqual(status, 200)
        status, created = handle("POST", "/api/create", {
            "tree": seed["tree"], "parent_id": "root", "kind": "folder", "name": "Nueva",
        })
        self.assertEqual(status, 200)
        names = [c["name"] for c in created["tree"]["children"]]
        self.assertIn("Nueva", names)
        self.assertTrue(created["id"])

    def test_errors_use_http_codes(self):
        _, seed = handle("GET", "/api/seed", None)
        status, body = handle("POST", "/api/create", {
            "tree": seed["tree"], "parent_id": "root", "kind": "note", "name": "",
        })
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        status, _ = handle("POST", "/api/delete", {"tree": seed["tree"], "id": "no-existe"})
        self.assertEqual(status, 404)
        status, _ = handle("POST", "/api/nada", {"tree": seed["tree"]})
        self.assertEqual(status, 404)
        status, _ = handle("POST", "/api/load", {"tree": "mal"})
        self.assertEqual(status, 400)

    def test_search_and_save(self):
        _, seed = handle("GET", "/api/seed", None)
        status, found = handle("POST", "/api/search", {"tree": seed["tree"], "q": "recorridos"})
        self.assertEqual(status, 200)
        self.assertTrue(found["results"])
        note_id = found["results"][0]["id"]
        status, saved = handle("POST", "/api/save", {"tree": seed["tree"], "id": note_id, "content": "hola"})
        self.assertEqual((status, saved), (200, {"saved": True}))


if __name__ == "__main__":
    unittest.main()
