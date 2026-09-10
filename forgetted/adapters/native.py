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
        if self._active:
            return
        with _leases_lock:
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
        if not self._active:
            return
        with _leases_lock:
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
    """Suspend retains while preserving Hindsight recall and reflect."""

    flag = "retain_suspended"
    adapter_name = "hindsight"


class CrewAIAdapter(_NativeFlagAdapter):
    """Make a CrewAI Memory read-only for the forgetted window."""

    flag = "read_only"
    adapter_name = "crewai"
