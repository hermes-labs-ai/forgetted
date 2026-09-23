"""Tests for persistence adapters."""

import shutil
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from forgetted.adapters import native
from forgetted.adapters.file_write import FileWriteAdapter
from forgetted.adapters.native import CrewAIAdapter, HindsightAdapter
from forgetted.session import ForgetSession

SCRATCH_ROOT = Path("/tmp/incognito-test/scratch")


@pytest.fixture(autouse=True)
def clean_scratch():
    if SCRATCH_ROOT.exists():
        shutil.rmtree(SCRATCH_ROOT)
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    (SCRATCH_ROOT / "memory").mkdir()
    yield


class TestFileWriteAdapter:
    def test_implements_interface(self):
        adapter = FileWriteAdapter(str(SCRATCH_ROOT))
        assert adapter.name == "file-write"
        assert not adapter.is_active

    def test_disable_enables_guard(self):
        adapter = FileWriteAdapter(str(SCRATCH_ROOT))
        adapter.disable()
        assert adapter.is_active
        adapter.enable()
        assert not adapter.is_active

    def test_blocks_writes_when_disabled(self):
        target = SCRATCH_ROOT / "memory" / "blocked.md"
        adapter = FileWriteAdapter(str(SCRATCH_ROOT))

        adapter.disable()
        with open(target, "w") as f:
            f.write("should vanish")
        adapter.enable()

        assert not target.exists()

    def test_blocked_count(self):
        adapter = FileWriteAdapter(str(SCRATCH_ROOT))
        adapter.disable()

        with open(SCRATCH_ROOT / "memory" / "a.md", "w") as f:
            f.write("1")
        with open(SCRATCH_ROOT / "memory" / "b.md", "w") as f:
            f.write("2")

        adapter.enable()
        assert adapter.blocked_count == 2

    def test_cleanup_is_noop(self):
        adapter = FileWriteAdapter(str(SCRATCH_ROOT))
        adapter.cleanup()  # should not raise

    def test_idempotent_disable(self):
        adapter = FileWriteAdapter(str(SCRATCH_ROOT))
        adapter.disable()
        adapter.disable()  # no error
        adapter.enable()

    def test_idempotent_enable(self):
        adapter = FileWriteAdapter(str(SCRATCH_ROOT))
        adapter.disable()
        adapter.enable()
        adapter.enable()  # no error


class TestMem0Adapter:
    """Test mem0 adapter with mocked Memory instance."""

    def _make_mock_memory(self):
        mock = MagicMock()
        mock.add = MagicMock(return_value={"results": [{"id": "test"}]})
        mock.update = MagicMock(return_value={"results": []})
        mock.get_all = MagicMock(return_value=[])
        mock.delete = MagicMock()
        return mock

    def test_import_and_interface(self):
        from forgetted.adapters.mem0 import Mem0Adapter

        mock_memory = self._make_mock_memory()
        adapter = Mem0Adapter(mock_memory)
        assert adapter.name == "mem0"
        assert not adapter.is_active

    def test_disable_blocks_add(self):
        from forgetted.adapters.mem0 import Mem0Adapter

        mock_memory = self._make_mock_memory()
        original_add = mock_memory.add
        adapter = Mem0Adapter(mock_memory)

        adapter.disable()
        assert adapter.is_active

        # Call add — should be the no-op, not the original
        result = mock_memory.add("secret data")
        assert result.get("blocked_by") == "forgetted"
        original_add.assert_not_called()

        adapter.enable()
        assert not adapter.is_active

    def test_enable_restores_original_methods(self):
        from forgetted.adapters.mem0 import Mem0Adapter

        mock_memory = self._make_mock_memory()
        original_add = mock_memory.add
        adapter = Mem0Adapter(mock_memory)

        adapter.disable()
        adapter.enable()

        # Should be the original method again
        assert mock_memory.add is original_add

    def test_cleanup_with_no_memories(self):
        from forgetted.adapters.mem0 import Mem0Adapter

        mock_memory = self._make_mock_memory()
        adapter = Mem0Adapter(mock_memory)

        adapter.disable()
        adapter.enable()
        adapter.cleanup()  # should not raise

    def test_cleanup_deletes_new_timezone_aware_iso_memories_only(self):
        from forgetted.adapters.mem0 import Mem0Adapter

        boundary = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
        mock_memory = self._make_mock_memory()
        mock_memory.get_all.return_value = {
            "results": [
                {"id": "old", "created_at": (boundary - timedelta(seconds=1)).isoformat()},
                {"id": "new-offset", "created_at": (boundary + timedelta(seconds=1)).isoformat()},
                {"id": "new-z", "created_at": "2026-07-31T12:00:02Z"},
                {"id": "ambiguous", "created_at": "2026-07-31T12:00:03"},
                {"id": "invalid", "created_at": "not-a-timestamp"},
            ]
        }
        adapter = Mem0Adapter(mock_memory)
        adapter._window_start = boundary.timestamp()

        adapter.cleanup()

        assert [call.args[0] for call in mock_memory.delete.call_args_list] == ["new-offset", "new-z"]

    def test_cleanup_keeps_support_for_epoch_timestamps(self):
        from forgetted.adapters.mem0 import Mem0Adapter

        mock_memory = self._make_mock_memory()
        mock_memory.get_all.return_value = [
            {"id": "old", "created_at": 99.0},
            {"id": "new", "created_at": 101.0},
        ]
        adapter = Mem0Adapter(mock_memory)
        adapter._window_start = 100.0

        adapter.cleanup()

        mock_memory.delete.assert_called_once_with("new")

    def test_idempotent_disable(self):
        from forgetted.adapters.mem0 import Mem0Adapter

        mock_memory = self._make_mock_memory()
        adapter = Mem0Adapter(mock_memory)

        adapter.disable()
        adapter.disable()  # no error, should not double-patch
        adapter.enable()

    def test_idempotent_enable(self):
        from forgetted.adapters.mem0 import Mem0Adapter

        mock_memory = self._make_mock_memory()
        adapter = Mem0Adapter(mock_memory)

        adapter.disable()
        adapter.enable()
        adapter.enable()  # no error


@pytest.fixture(params=[(CrewAIAdapter, "read_only", "crewai")])
def native_adapter(request):
    adapter_type, flag, name = request.param
    target = SimpleNamespace(**{flag: False})
    adapter = adapter_type(target)
    yield adapter, target, flag, name
    native._leases.pop(adapter._lease_key, None)


def test_native_adapter_disables_and_restores(native_adapter):
    adapter, target, flag, name = native_adapter
    assert adapter.name == name
    assert not adapter.is_active

    adapter.disable()
    adapter.disable()
    assert getattr(target, flag) is True
    assert adapter.is_active

    adapter.enable()
    adapter.enable()
    assert getattr(target, flag) is False
    assert not adapter.is_active


def test_native_adapter_preserves_preexisting_true(native_adapter):
    adapter, target, flag, _ = native_adapter
    setattr(target, flag, True)

    adapter.disable()
    adapter.enable()

    assert getattr(target, flag) is True


def test_native_adapters_restore_after_last_owner_exits(native_adapter):
    first, target, flag, _ = native_adapter
    second = type(first)(target)

    first.disable()
    second.disable()
    first.enable()
    assert getattr(target, flag) is True

    second.enable()
    assert getattr(target, flag) is False


def test_native_adapter_rejects_unsupported_version(native_adapter):
    adapter, _, flag, _ = native_adapter
    with pytest.raises(AttributeError, match=flag):
        type(adapter)(SimpleNamespace())


class _FakeHindsight:
    def __init__(self):
        self.suspension_depth = 0

    @contextmanager
    def suspend_retains(self):
        self.suspension_depth += 1
        try:
            yield
        finally:
            self.suspension_depth -= 1


def test_hindsight_adapter_enters_and_exits_suspend_retains_idempotently():
    target = _FakeHindsight()
    adapter = HindsightAdapter(target)

    adapter.disable()
    adapter.disable()
    assert adapter.is_active
    assert target.suspension_depth == 1

    adapter.enable()
    adapter.enable()
    assert not adapter.is_active
    assert target.suspension_depth == 0


def test_hindsight_adapters_support_nested_scopes_on_one_client():
    target = _FakeHindsight()
    outer = HindsightAdapter(target)
    inner = HindsightAdapter(target)

    outer.disable()
    inner.disable()
    assert target.suspension_depth == 2

    inner.enable()
    assert target.suspension_depth == 1
    outer.enable()
    assert target.suspension_depth == 0


def test_hindsight_adapter_exits_scope_after_exception_and_can_restart():
    target = _FakeHindsight()
    adapter = HindsightAdapter(target)

    with pytest.raises(RuntimeError, match="stop"), ForgetSession(
        str(SCRATCH_ROOT), adapters=[adapter]
    ):
        assert target.suspension_depth == 1
        raise RuntimeError("stop")
    assert not adapter.is_active
    assert target.suspension_depth == 0

    adapter.disable()
    assert target.suspension_depth == 1
    adapter.enable()
    assert target.suspension_depth == 0


def test_hindsight_adapter_requires_context_manager_api():
    with pytest.raises(AttributeError, match="suspend_retains"):
        HindsightAdapter(SimpleNamespace(retain_suspended=False))


def test_hindsight_adapter_with_released_client_needs_no_server():
    hindsight_client = pytest.importorskip("hindsight_client")
    client = hindsight_client.Hindsight(base_url="http://127.0.0.1:1")
    adapter = HindsightAdapter(client)

    adapter.disable()
    assert adapter.is_active
    adapter.enable()
    assert not adapter.is_active


def test_native_adapter_cleanup_is_noop(native_adapter):
    adapter, target, flag, _ = native_adapter
    adapter.disable()
    adapter.enable()
    adapter.cleanup()
    assert getattr(target, flag) is False


class _BarrierLock:
    """Instrumented stand-in for ``native._leases_lock``.

    The first ``parties`` acquirers are parked at a barrier *before* the real
    lock is taken, so every caller is guaranteed to have entered ``disable`` or
    ``enable`` before any of them commits a state change. That makes a check or
    assignment placed outside the critical section race deterministically,
    without sleeps.
    """

    def __init__(self, parties: int):
        self._lock = threading.RLock()
        self._barrier = threading.Barrier(parties)
        self._gate = threading.Lock()
        self._remaining = parties

    def acquire(self, blocking: bool = True, timeout: float = -1):
        with self._gate:
            park = self._remaining > 0
            if park:
                self._remaining -= 1
        if park:
            self._barrier.wait(timeout=5)
        return self._lock.acquire(blocking, timeout)

    def release(self) -> None:
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()


def _run_concurrently(call, parties):
    """Run ``call`` on ``parties`` threads; return whatever each one raised."""
    errors = []

    def worker():
        try:
            call()
        except Exception as exc:  # the unsynchronized race surfaces as KeyError
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(parties)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in threads), "concurrent lifecycle call deadlocked"
    return errors


def test_native_adapter_concurrent_disable_takes_a_single_lease(native_adapter, monkeypatch):
    adapter, target, flag, _ = native_adapter
    monkeypatch.setattr(native, "_leases_lock", _BarrierLock(2))

    errors = _run_concurrently(adapter.disable, 2)

    assert errors == []
    assert adapter.is_active
    assert getattr(target, flag) is True
    assert native._leases[adapter._lease_key][2] == 1

    adapter.enable()
    assert not adapter.is_active
    assert getattr(target, flag) is False
    assert adapter._lease_key not in native._leases


def test_native_adapter_concurrent_enable_releases_a_single_lease(native_adapter, monkeypatch):
    adapter, target, flag, _ = native_adapter
    adapter.disable()
    monkeypatch.setattr(native, "_leases_lock", _BarrierLock(2))

    errors = _run_concurrently(adapter.enable, 2)

    assert errors == []
    assert not adapter.is_active
    assert getattr(target, flag) is False
    assert adapter._lease_key not in native._leases
