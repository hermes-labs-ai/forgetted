"""
forgetted.adapters — Persistence layer adapters.

Built-in adapters:
    - FileWriteAdapter: blocks file writes via builtins.open patch
    - CrewAIAdapter: flips CrewAI memory ``read_only`` for the window
    - HindsightAdapter: flips Hindsight client ``retain_suspended`` for the window
    - Mem0Adapter: blocks mem0 add/update (requires mem0ai)

Custom adapters: subclass ``PersistenceAdapter`` from ``forgetted.adapters.base``.
"""

from .base import PersistenceAdapter
from .file_write import FileWriteAdapter
from .native import CrewAIAdapter, HindsightAdapter

__all__ = [
    "PersistenceAdapter",
    "CrewAIAdapter",
    "FileWriteAdapter",
    "HindsightAdapter",
]

# Optional adapters — import only if deps are available.
try:
    from .mem0 import Mem0Adapter  # noqa: F401

    __all__.append("Mem0Adapter")
except ImportError:
    pass
