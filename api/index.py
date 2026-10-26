"""Entrada serverless de Vercel: reutiliza la misma API que el servidor local."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cuaderno.web import ApiHandler  # noqa: E402


class handler(ApiHandler):
    """Clase que Vercel busca al ejecutar la función."""
