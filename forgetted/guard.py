"""
forgetted.guard — Write-blocking interceptor for forgetted mode.

Patches ``builtins.open`` and ``pathlib.Path.write_text/write_bytes`` while
active so writes to protected workspace paths silently vanish. Reads are never
blocked. Direct ``os.open`` calls remain outside this guard's coverage.

This is the core primitive: "this session can read from memory but cannot
write to it." A fork without consequence — the branch exists in context
but is never merged back into the agent's persistent state.

Protected paths:
    - memory/ directory (daily logs, checkpoints)
    - DELIVERABLES.md
    - Any *.jsonl file (session logs)

Security model:
    - Input: workspace path (trusted, set by caller)
    - Patches common Python file-write entry points at process level
    - Returns no-op StringIO/BytesIO instead of raising — agent code doesn't crash
    - Restores original open on stop() — no permanent side effects
"""

import builtins
import io
import logging
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Modes that involve writing — we block these on protected paths.
_WRITE_MODES = re.compile(r"[wax+]", re.IGNORECASE)

# Default protected path patterns (relative to workspace root).
_DEFAULT_PROTECTED = {
    "memory",           # entire memory/ directory tree
    "DELIVERABLES.md",  # shared deliverables log
}

# File extensions that are always blocked inside the workspace.
_BLOCKED_EXTENSIONS = {".jsonl"}

# pathlib uses io.open directly, so it needs its own shared dispatcher. Keeping
# one dispatcher for all active guards also makes restoration safe when
# overlapping sessions stop out of order.
_ACTIVE_PATH_GUARDS = []
_PATH_ORIGINAL_WRITE_TEXT = None
_PATH_ORIGINAL_WRITE_BYTES = None


def _guarded_path_write_text(path, data, *args, **kwargs):
    for guard in reversed(_ACTIVE_PATH_GUARDS):
        if guard._is_protected(path):
            guard._blocked_count += 1
            logger.debug("🫥 Blocked pathlib text write to %s", path)
            return len(data) if sys.version_info >= (3, 10) else None
    return _PATH_ORIGINAL_WRITE_TEXT(path, data, *args, **kwargs)


def _guarded_path_write_bytes(path, data, *args, **kwargs):
    for guard in reversed(_ACTIVE_PATH_GUARDS):
        if guard._is_protected(path):
            guard._blocked_count += 1
            logger.debug("🫥 Blocked pathlib binary write to %s", path)
            return len(data)
    return _PATH_ORIGINAL_WRITE_BYTES(path, data, *args, **kwargs)


class ForgetGuard:
    """Context manager that blocks file writes to protected workspace paths.

    Parameters
    ----------
    workspace_path : str
        Absolute path to the agent workspace root.
    extra_protected : set[str], optional
        Additional relative paths or directory names to protect.

    Usage
    -----
    ::

        guard = ForgetGuard("/path/to/workspace")
        guard.start()
        # ... agent runs, writes to memory/ silently vanish ...
        guard.stop()

    Or as a context manager::

        with ForgetGuard("/path/to/workspace"):
            ...
    """

    def __init__(self, workspace_path: str, extra_protected: Optional[set[str]] = None):
        self.workspace = Path(workspace_path).resolve()
        self.protected = _DEFAULT_PROTECTED | (extra_protected or set())
        self.active = False
        self._original_open = None
        self._blocked_count = 0

    # -- public API ---------------------------------------------------------

    def start(self):
        """Activate write blocking for open() and pathlib write helpers."""
        if self.active:
            return
        self._original_open = builtins.open
        self._blocked_count = 0
        builtins.open = self._patched_open  # type: ignore[assignment]
        global _PATH_ORIGINAL_WRITE_TEXT, _PATH_ORIGINAL_WRITE_BYTES
        if not _ACTIVE_PATH_GUARDS:
            _PATH_ORIGINAL_WRITE_TEXT = Path.write_text
            _PATH_ORIGINAL_WRITE_BYTES = Path.write_bytes
            Path.write_text = _guarded_path_write_text  # type: ignore[method-assign]
            Path.write_bytes = _guarded_path_write_bytes  # type: ignore[method-assign]
        _ACTIVE_PATH_GUARDS.append(self)
        self.active = True
        logger.info("🫥 Forgetted guard active — writes to protected paths are blocked")

    def stop(self):
        """Deactivate write blocking and restore patched methods."""
        global _PATH_ORIGINAL_WRITE_TEXT, _PATH_ORIGINAL_WRITE_BYTES
        if not self.active:
            return
        builtins.open = self._original_open  # type: ignore[assignment]
        self._original_open = None
        if self in _ACTIVE_PATH_GUARDS:
            _ACTIVE_PATH_GUARDS.remove(self)
        if not _ACTIVE_PATH_GUARDS:
            Path.write_text = _PATH_ORIGINAL_WRITE_TEXT  # type: ignore[method-assign]
            Path.write_bytes = _PATH_ORIGINAL_WRITE_BYTES  # type: ignore[method-assign]
            _PATH_ORIGINAL_WRITE_TEXT = None
            _PATH_ORIGINAL_WRITE_BYTES = None
        self.active = False
        logger.info("🫥 Forgetted guard stopped — %d write(s) blocked", self._blocked_count)

    @property
    def blocked_count(self) -> int:
        """Number of write attempts blocked since guard was started."""
        return self._blocked_count

    # -- context manager ----------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    # -- internal -----------------------------------------------------------

    def _is_protected(self, filepath: Path) -> bool:
        """Check if *filepath* falls under a protected path."""
        try:
            resolved = filepath.resolve()
        except (OSError, ValueError):
            return False

        # Must be inside the workspace to be subject to protection.
        try:
            rel = resolved.relative_to(self.workspace)
        except ValueError:
            return False

        # Check extension blocklist (e.g., .jsonl anywhere in workspace).
        if resolved.suffix in _BLOCKED_EXTENSIONS:
            return True

        # Check protected directories and files.
        rel_parts = rel.parts
        for protected in self.protected:
            # Direct filename match (e.g., "DELIVERABLES.md").
            if rel_parts and rel_parts[-1] == protected:
                return True
            # Directory match (e.g., "memory" matches memory/anything).
            if protected in rel_parts:
                return True

        return False

    def _is_write_mode(self, mode: str) -> bool:
        """Return True if *mode* involves writing."""
        return bool(_WRITE_MODES.search(mode))

    def _patched_open(self, file, mode="r", *args, **kwargs):
        """Replacement for builtins.open that intercepts protected writes."""
        filepath = Path(str(file))

        if self._is_write_mode(mode) and self._is_protected(filepath):
            self._blocked_count += 1
            logger.debug("🫥 Blocked write to %s (mode=%s)", filepath, mode)
            # Return a no-op StringIO/BytesIO depending on mode.
            if "b" in mode:
                return io.BytesIO()
            return io.StringIO()

        return self._original_open(file, mode, *args, **kwargs)
