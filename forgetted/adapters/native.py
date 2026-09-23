"""Adapters for frameworks with a native read-only boolean flag."""

from threading import RLock
from typing import Any

from .base import PersistenceAdapter

_leases: dict[tuple[int, str], tuple[Any, Any, int]] = {}
_leases_lock = RLock()


class _NativeFlagAdapter(PersistenceAdapter):
    """Toggle one framework-owned flag while a forgetted window is active."""

    flag: str
    adapter_name: str

    def __init__(self, target: Any):
        if not hasattr(target, self.flag):
            raise AttributeError(
                f"{type(self).__name__} requires {type(target).__name__}.{self.flag}; "
                "upgrade to a version that exposes this native read-only flag"
            )
        self._target = target
        self._lease_key = (id(target), self.flag)
        self._active = False

    @property
    def name(self) -> str:
        return self.adapter_name

    @property
    def is_active(self) -> bool:
        return self._active

    def disable(self) -> None:
        with _leases_lock:
            if self._active:
                return
            lease = _leases.get(self._lease_key)
            if lease is None:
                previous = getattr(self._target, self.flag)
                setattr(self._target, self.flag, True)
                _leases[self._lease_key] = (self._target, previous, 1)
            else:
                target, previous, owners = lease
                _leases[self._lease_key] = (target, previous, owners + 1)
            self._active = True

    def enable(self) -> None:
        with _leases_lock:
            if not self._active:
                return
            target, previous, owners = _leases[self._lease_key]
            if owners == 1:
                setattr(target, self.flag, previous)
                del _leases[self._lease_key]
            else:
                _leases[self._lease_key] = (target, previous, owners - 1)
            self._active = False

    def cleanup(self) -> None:
        """No sweep is needed because the framework refused writes."""


class HindsightAdapter(_NativeFlagAdapter):
    """Enter Hindsight's task-local retain suspension for the active window.

    ``Hindsight.suspend_retains()`` is a synchronous context manager. Keeping
    its manager instance lets ``enable()`` exit the exact scope entered by
    ``disable()``, which is required for ContextVar token cleanup.
    """

    adapter_name = "hindsight"

    def __init__(self, target: Any):
        suspend_retains = getattr(target, "suspend_retains", None)
        if not callable(suspend_retains):
            raise AttributeError(
                f"{type(self).__name__} requires {type(target).__name__}.suspend_retains(); "
                "upgrade to hindsight-client 0.10.1 or newer"
            )
        self._target = target
        self._suspension = None
        self._active = False
        self._lock = RLock()

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def disable(self) -> None:
        with self._lock:
            if self._active:
                return
            suspension = self._target.suspend_retains()
            suspension.__enter__()
            self._suspension = suspension
            self._active = True

    def enable(self) -> None:
        with self._lock:
            if not self._active:
                return
            suspension = self._suspension
            try:
                # ForgetSession calls enable() from its finally/stop path; the
                # Hindsight context manager only needs exit to reset its token.
                suspension.__exit__(None, None, None)
            finally:
                self._suspension = None
                self._active = False

    def cleanup(self) -> None:
        """No sweep is needed because Hindsight suppressed retains in-scope."""


class CrewAIAdapter(_NativeFlagAdapter):
    """Make a CrewAI Memory read-only for the forgetted window."""

    flag = "read_only"
    adapter_name = "crewai"
