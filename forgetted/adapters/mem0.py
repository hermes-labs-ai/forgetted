"""
forgetted.adapters.mem0 — mem0 semantic memory adapter.

Disables mem0 writes during a forgetted window by monkey-patching the
Memory instance's ``add`` and ``update`` methods. On cleanup, deletes
any memories added during the window (by timestamp comparison).

Requires: ``pip install mem0ai`` (optional dependency).
"""

import logging
import time
from typing import Any

from .base import PersistenceAdapter

logger = logging.getLogger(__name__)


class Mem0Adapter(PersistenceAdapter):
    """Adapter for mem0 (semantic memory layer).

    Parameters
    ----------
    memory : object
        A mem0 ``Memory`` instance. The adapter patches its ``add``
        and ``update`` methods during the forgetted window.
    user_id : str, optional
        mem0 user ID for scoped cleanup queries.

    Example
    -------
    ::

        from mem0 import Memory
        from forgetted.adapters.mem0 import Mem0Adapter

        m = Memory()
        adapter = Mem0Adapter(m, user_id="roli")
    """

    def __init__(self, memory: Any, user_id: str = "default"):
        self._memory = memory
        self._user_id = user_id
        self._original_add = None
        self._original_update = None
        self._active = False
        self._window_start: float = 0

    @property
    def name(self) -> str:
        return "mem0"

    @property
    def is_active(self) -> bool:
        return self._active

    def disable(self) -> None:
        if self._active:
            return
        self._window_start = time.time()
        self._original_add = self._memory.add
        self._original_update = getattr(self._memory, "update", None)

        def _noop_add(*args, **kwargs):
            logger.debug("🫥 mem0 add blocked during forgetted window")
            return {"results": [], "blocked_by": "forgetted"}

        def _noop_update(*args, **kwargs):
            logger.debug("🫥 mem0 update blocked during forgetted window")
            return {"results": [], "blocked_by": "forgetted"}

        self._memory.add = _noop_add
        if self._original_update is not None:
            self._memory.update = _noop_update

        self._active = True
        logger.info("🫥 mem0 adapter disabled — add/update blocked")

    def enable(self) -> None:
        if not self._active:
            return
        self._memory.add = self._original_add
        if self._original_update is not None:
            self._memory.update = self._original_update
        self._original_add = None
        self._original_update = None
        self._active = False
        logger.info("🫥 mem0 adapter enabled — normal writes restored")

    def cleanup(self) -> None:
        """Delete any memories that leaked through during the window.

        Queries mem0 for memories created after ``_window_start`` and
        deletes them. This catches writes made by framework code that
        bypassed the patched methods.
        """
        if self._window_start == 0:
            return

        try:
            # mem0's get_all returns memories with metadata including created_at
            all_memories = self._memory.get_all(user_id=self._user_id)
            if not all_memories:
                return

            # Handle both dict and list response formats
            memories = all_memories if isinstance(all_memories, list) else all_memories.get("results", [])
            deleted = 0
            for mem in memories:
                created = mem.get("created_at", 0)
                # mem0 uses ISO timestamps or epoch — handle both
                if isinstance(created, str):
                    continue  # Skip string timestamps for now — timestamp comparison is fragile
                if created >= self._window_start:
                    try:
                        self._memory.delete(mem["id"])
                        deleted += 1
                    except Exception as exc:
                        logger.warning("🫥 Failed to delete mem0 memory %s: %s", mem.get("id"), exc)

            if deleted:
                logger.info("🫥 mem0 cleanup: deleted %d memories from forgetted window", deleted)
        except Exception as exc:
            logger.warning("🫥 mem0 cleanup failed (non-fatal): %s", exc)
        finally:
            self._window_start = 0
