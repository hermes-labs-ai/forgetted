"""
forgetted.adapters.base — Abstract base for persistence adapters.

Every persistence layer that forgetted can control implements this interface.
Adapters are registered with a ForgetSession, which calls disable/enable/cleanup
at the appropriate times.

To write a custom adapter::

    from forgetted.adapters.base import PersistenceAdapter

    class MyVectorDBAdapter(PersistenceAdapter):
        name = "my-vector-db"

        def disable(self):
            self._client.pause_writes()
            self._active = False

        def enable(self):
            self._client.resume_writes()
            self._active = True

        def cleanup(self):
            self._client.delete_since(self._window_start)
"""

from abc import ABC, abstractmethod


class PersistenceAdapter(ABC):
    """Interface for a persistence layer that forgetted can control.

    Subclasses must implement ``disable``, ``enable``, ``cleanup``,
    and the ``name`` and ``is_active`` properties.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier for this adapter (e.g., 'mem0', 'file-write')."""

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """True when writes are being blocked (adapter is in disabled/forgetted state)."""

    @abstractmethod
    def disable(self) -> None:
        """Block writes through this persistence layer.

        Called when a forgetted window starts. Must be idempotent —
        calling disable() twice should not error.
        """

    @abstractmethod
    def enable(self) -> None:
        """Restore normal write behavior.

        Called when a forgetted window ends. Must be idempotent —
        calling enable() twice should not error.
        """

    @abstractmethod
    def cleanup(self) -> None:
        """Remove any data that leaked through during the forgetted window.

        Called after enable(). This is the post-window sweep — delete
        any memories, embeddings, or logs that were written despite
        the disable() call (e.g., by framework-level code).

        Must be safe to call even if nothing leaked (no-op in that case).
        """
