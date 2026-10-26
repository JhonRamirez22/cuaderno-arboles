# Cuaderno: notas organizadas en carpetas (árboles en Python)


# Link Vercel: https://cuaderno-arboles.vercel.app

Un cuaderno de notas con carpetas dentro de carpetas, como el explorador de archivos pero para apuntes. Sirve para organizar apuntes de clase, ideas o listas, y encontrarlos rápido.

La estructura de datos central es un **árbol**: cada carpeta es un nodo, sus hijos son lo que contiene (otras carpetas o notas) y las notas son las hojas.

## Qué se puede hacer

- Crear carpetas y notas, renombrarlas y eliminarlas.
- Mover cualquier elemento a otra carpeta, con el diálogo «Mover a…» o **arrastrándolo** sobre una carpeta.
- Escribir en las notas con **autoguardado**.
- Buscar por nombre y por el **texto dentro de las notas**.
- Ver siempre dónde estás (migas de pan) y cuántas notas hay en cada carpeta.
- Usarlo desde el móvil.

Tus notas se guardan en tu navegador (`localStorage`), así que siguen ahí al volver. La primera vez aparece un cuaderno de ejemplo con una nota de bienvenida.

## Ejecutar

Requiere Python 3.10 o superior. No necesita instalar nada.

```bash
python3 server.py
```

Abrir <http://localhost:8000>. Para otro puerto: `python3 server.py 5000`.

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

## Operaciones del árbol

Implementadas en `cuaderno/tree.py` (clases `Node` y `Notebook`).

| Operación | Método | Complejidad |
|---|---|---|
| Llegar a un elemento por id | `get` (índice `dict`) | O(1) |
| Crear en una carpeta | `create` | O(h + k) |
| Renombrar | `rename` | O(k) |
| Mover (valida ciclos subiendo por los padres) | `move` | O(h + n) |
| Eliminar un subárbol | `delete` | O(n) |
| Ruta desde la raíz (migas de pan) | `path` | O(h) |
| Recorrido en profundidad, preorden | `walk` | O(n) |
| Notas dentro de una carpeta | `note_count` | O(n) |
| Búsqueda por nombre y contenido | `search` | O(n) |

n = elementos, h = altura del árbol, k = hijos de la carpeta.

Reglas que protege el árbol: solo las carpetas tienen hijos; no hay dos elementos con el mismo nombre en una carpeta (sin distinguir mayúsculas); una carpeta no puede moverse dentro de sí misma ni de sus descendientes; la carpeta principal no se mueve ni se elimina; hay límites de tamaño y de niveles (10).

## Cómo funciona

La API de Python **no guarda nada**: cada petición trae el árbol completo, lo valida, aplica una operación y devuelve el resultado. El navegador conserva los datos. Por eso funciona igual en local y en Vercel, y cada persona tiene su propio cuaderno.

```
cuaderno/
  tree.py        Node y Notebook: el árbol y sus operaciones
  web.py         API HTTP (valida el árbol recibido y ejecuta la acción)
server.py        servidor local: interfaz + API (biblioteca estándar)
api/index.py     entrada serverless para Vercel
public/          interfaz (HTML, CSS y JavaScript sin dependencias)
tests/           pruebas del árbol y de la API
vercel.json      configuración de despliegue
```

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/seed` | Cuaderno de ejemplo |
| POST | `/api/load` | Valida un cuaderno guardado |
| POST | `/api/create` | Crea carpeta o nota (`parent_id`, `kind`, `name`) |
| POST | `/api/rename` | Renombra (`id`, `name`) |
| POST | `/api/move` | Mueve (`id`, `parent_id`) |
| POST | `/api/delete` | Elimina un subárbol (`id`) |
| POST | `/api/save` | Guarda el texto de una nota (`id`, `content`) |
| POST | `/api/search` | Busca (`q`) |

Todas las peticiones POST incluyen `tree`. Los errores devuelven `400` o `404` con `{"error": "..."}`.
