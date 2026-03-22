"""
forgetted.session — ForgetSession orchestrator.

Coordinates multiple persistence adapters during a forgetted window.
This is the main entry point for v0.2 usage.

Ordering contract for stop():
    1. Re-enable all adapters (restore normal writes) — always happens first.
    2. Run cleanup on each adapter (post-window sweep) — runs after enable.
    3. Clean session log if requested.

This ordering ensures that cleanup code can write freely (e.g., mem0.delete)
because adapters are already re-enabled when cleanup runs.

If any adapter raises during disable/enable/cleanup, the error is logged
but other adapters continue. No single adapter failure blocks the rest.

Usage::

    from forgetted.session import ForgetSession

    with ForgetSession("/path/to/workspace") as fs:
        # ... everything here is forgetted ...
        pass
    # adapters re-enabled, cleanup done, session log deleted
"""

import logging
from typing import Optional

from .adapters.base import PersistenceAdapter
from .adapters.file_write import FileWriteAdapter
from .checkpoint import create_checkpoint
from .cleaner import delete_session_log, find_session_log

logger = logging.getLogger(__name__)


class ForgetSession:
    """Orchestrate a forgetted window across multiple persistence adapters.

    Parameters
    ----------
    workspace : str
        Absolute path to the agent workspace root.
    adapters : list[PersistenceAdapter], optional
        Additional adapters to register. ``FileWriteAdapter`` is always
        included as the safety-net layer.
    session_id : str, optional
        Session ID for log cleanup after the window.
    agents_dir : str, optional
        Directory to search for session logs (for cleanup).
    """

    def __init__(
        self,
        workspace: str,
        adapters: Optional[list[PersistenceAdapter]] = None,
        session_id: Optional[str] = None,
        agents_dir: Optional[str] = None,
    ):
        self.workspace = workspace
        self.session_id = session_id
        self.agents_dir = agents_dir
        self._started = False

        # FileWriteAdapter is always the base layer (safety net).
        self._adapters: list[PersistenceAdapter] = [FileWriteAdapter(workspace)]
        if adapters:
            self._adapters.extend(adapters)

    @property
    def is_active(self) -> bool:
        """True if the forgetted window is currently open."""
        return self._started

    @property
    def adapters(self) -> list[PersistenceAdapter]:
        """List of registered adapters (read-only view)."""
        return list(self._adapters)

    def add_adapter(self, adapter: PersistenceAdapter) -> None:
        """Register an additional persistence adapter.

        Must be called before ``start()``. Raises RuntimeError if
        the session is already active.
        """
        if self._started:
            raise RuntimeError("Cannot add adapters while forgetted session is active")
        self._adapters.append(adapter)
        logger.info("🫥 Registered adapter: %s", adapter.name)

    def start(self, checkpoint_summary: Optional[str] = None) -> None:
        """Open the forgetted window.

        Parameters
        ----------
        checkpoint_summary : str, optional
            If provided, saves a resumption checkpoint before disabling.
        """
        if self._started:
            return  # Idempotent — double-start is a no-op.

        # Save checkpoint before going dark.
        if checkpoint_summary:
            create_checkpoint(checkpoint_summary, self.workspace)

        # Disable all adapters. Each adapter is independent — one failure
        # doesn't prevent others from disabling.
        for adapter in self._adapters:
            try:
                adapter.disable()
            except Exception as exc:
                logger.error("🫥 Failed to disable adapter '%s': %s", adapter.name, exc)

        self._started = True
        adapter_names = ", ".join(a.name for a in self._adapters)
        logger.info("🫥 Forgetted session started — %d adapters active (%s)", len(self._adapters), adapter_names)

    def stop(self, clean: bool = True) -> None:
        """Close the forgetted window.

        Ordering contract:
            1. Re-enable all adapters (restore normal writes)
            2. Run cleanup on each adapter (if clean=True)
            3. Delete session log (if session_id and agents_dir provided)

        Parameters
        ----------
        clean : bool
            If True (default), run cleanup sweep on all adapters and
            delete the session log. Set to False to skip cleanup.
        """
        if not self._started:
            return  # Idempotent — stop before start is a no-op.

        # Step 1: Re-enable all adapters first.
        # This ensures cleanup code can write freely (e.g., mem0.delete).
        for adapter in self._adapters:
            try:
                adapter.enable()
            except Exception as exc:
                logger.error("🫥 Failed to enable adapter '%s': %s", adapter.name, exc)

        # Step 2: Run cleanup sweep.
        if clean:
            for adapter in self._adapters:
                try:
                    adapter.cleanup()
                except Exception as exc:
                    logger.error("🫥 Cleanup failed for adapter '%s': %s", adapter.name, exc)

            # Step 3: Delete session log.
            if self.session_id and self.agents_dir:
                log = find_session_log(self.session_id, self.agents_dir)
                if log:
                    delete_session_log(log)

        self._started = False
        logger.info("🫥 Forgetted session stopped (clean=%s)", clean)

    # -- context manager ----------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Always stop and clean up, even if an exception occurred.
        self.stop(clean=True)
        return False  # Don't suppress exceptions.
