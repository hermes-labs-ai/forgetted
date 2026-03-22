"""
forgetted.adapters.file_write — File write blocking adapter.

Wraps the existing ForgetGuard (builtins.open monkey-patch) as a
PersistenceAdapter. This is the safety-net layer — it catches writes
that slip past higher-level adapters.
"""

import logging
from typing import Optional

from ..guard import ForgetGuard
from .base import PersistenceAdapter

logger = logging.getLogger(__name__)


class FileWriteAdapter(PersistenceAdapter):
    """Adapter that blocks file writes to protected workspace paths.

    Parameters
    ----------
    workspace_path : str
        Absolute path to the agent workspace root.
    extra_protected : set[str], optional
        Additional relative paths or directory names to protect.
    """

    def __init__(self, workspace_path: str, extra_protected: Optional[set[str]] = None):
        self._guard = ForgetGuard(workspace_path, extra_protected)

    @property
    def name(self) -> str:
        return "file-write"

    @property
    def is_active(self) -> bool:
        return self._guard.active

    def disable(self) -> None:
        self._guard.start()

    def enable(self) -> None:
        self._guard.stop()

    def cleanup(self) -> None:
        # No cleanup needed — writes were blocked, not captured.
        pass

    @property
    def blocked_count(self) -> int:
        """Number of write attempts blocked during the current/last window."""
        return self._guard.blocked_count
