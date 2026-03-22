"""
forgetted.adapters — Persistence layer adapters.

Built-in adapters:
    - FileWriteAdapter: blocks file writes via builtins.open patch
    - Mem0Adapter: blocks mem0 add/update (requires mem0ai)

Custom adapters: subclass ``PersistenceAdapter`` from ``forgetted.adapters.base``.
"""

from .base import PersistenceAdapter
from .file_write import FileWriteAdapter

__all__ = [
    "PersistenceAdapter",
    "FileWriteAdapter",
]

# Optional adapters — import only if deps are available.
try:
    from .mem0 import Mem0Adapter  # noqa: F401

    __all__.append("Mem0Adapter")
except ImportError:
    pass
