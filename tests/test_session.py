"""Tests for ForgetSession orchestrator."""

import shutil
from pathlib import Path

import pytest

from forgetted.adapters.base import PersistenceAdapter
from forgetted.session import ForgetSession

SCRATCH_ROOT = Path("/tmp/incognito-test/scratch")


@pytest.fixture(autouse=True)
def clean_scratch():
    if SCRATCH_ROOT.exists():
        shutil.rmtree(SCRATCH_ROOT)
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    (SCRATCH_ROOT / "memory").mkdir()
    yield


class MockAdapter(PersistenceAdapter):
    """Test adapter that tracks calls."""

    def __init__(self, adapter_name: str = "mock"):
        self._name = adapter_name
        self._active = False
        self.disable_count = 0
        self.enable_count = 0
        self.cleanup_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_active(self) -> bool:
        return self._active

    def disable(self) -> None:
        self._active = True
        self.disable_count += 1

    def enable(self) -> None:
        self._active = False
        self.enable_count += 1

    def cleanup(self) -> None:
        self.cleanup_count += 1


class FailingAdapter(PersistenceAdapter):
    """Adapter that raises on every method."""

    @property
    def name(self) -> str:
        return "failing"

    @property
    def is_active(self) -> bool:
        return False

    def disable(self) -> None:
        raise RuntimeError("disable exploded")

    def enable(self) -> None:
        raise RuntimeError("enable exploded")

    def cleanup(self) -> None:
        raise RuntimeError("cleanup exploded")


class TestForgetSessionBasics:
    def test_session_starts_and_stops(self):
        session = ForgetSession(str(SCRATCH_ROOT))
        session.start()
        assert session.is_active
        session.stop()
        assert not session.is_active

    def test_file_write_adapter_always_included(self):
        session = ForgetSession(str(SCRATCH_ROOT))
        names = [a.name for a in session.adapters]
        assert "file-write" in names

    def test_blocks_writes_during_session(self):
        target = SCRATCH_ROOT / "memory" / "secret.md"

        with ForgetSession(str(SCRATCH_ROOT)), open(target, "w") as f:
            f.write("should not persist")

        assert not target.exists()

    def test_writes_work_after_session(self):
        target = SCRATCH_ROOT / "memory" / "normal.md"

        with ForgetSession(str(SCRATCH_ROOT)):
            pass

        with open(target, "w") as f:
            f.write("this should persist")

        assert target.exists()
        assert target.read_text() == "this should persist"


class TestForgetSessionWithAdapters:
    def test_custom_adapter_registered(self):
        mock = MockAdapter("custom-db")
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock])
        names = [a.name for a in session.adapters]
        assert "file-write" in names
        assert "custom-db" in names

    def test_adapter_disable_enable_called(self):
        mock = MockAdapter()
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock])

        session.start()
        assert mock.disable_count == 1
        assert mock.is_active

        session.stop()
        assert mock.enable_count == 1
        assert not mock.is_active

    def test_adapter_cleanup_called_on_stop(self):
        mock = MockAdapter()
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock])

        session.start()
        session.stop(clean=True)
        assert mock.cleanup_count == 1

    def test_adapter_cleanup_skipped_when_clean_false(self):
        mock = MockAdapter()
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock])

        session.start()
        session.stop(clean=False)
        assert mock.cleanup_count == 0

    def test_multiple_adapters(self):
        mock1 = MockAdapter("db-1")
        mock2 = MockAdapter("db-2")
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock1, mock2])

        session.start()
        assert mock1.is_active
        assert mock2.is_active

        session.stop()
        assert mock1.enable_count == 1
        assert mock2.enable_count == 1
        assert mock1.cleanup_count == 1
        assert mock2.cleanup_count == 1

    def test_add_adapter_before_start(self):
        session = ForgetSession(str(SCRATCH_ROOT))
        mock = MockAdapter("late-add")
        session.add_adapter(mock)
        assert len(session.adapters) == 2

    def test_add_adapter_during_session_raises(self):
        session = ForgetSession(str(SCRATCH_ROOT))
        session.start()
        with pytest.raises(RuntimeError, match="Cannot add adapters"):
            session.add_adapter(MockAdapter())
        session.stop()


class TestForgetSessionErrorHandling:
    def test_failing_adapter_doesnt_block_others(self):
        """A failing adapter should not prevent other adapters from working."""
        mock = MockAdapter("healthy")
        failing = FailingAdapter()
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[failing, mock])

        session.start()
        assert mock.disable_count == 1  # healthy adapter still disabled

        session.stop()
        assert mock.enable_count == 1  # healthy adapter still enabled
        assert mock.cleanup_count == 1  # healthy adapter still cleaned

    def test_failing_cleanup_doesnt_block_others(self):
        mock = MockAdapter("healthy")
        failing = FailingAdapter()
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock, failing])

        session.start()
        session.stop(clean=True)
        assert mock.cleanup_count == 1  # ran despite failing sibling


class TestForgetSessionIdempotency:
    def test_double_start_is_noop(self):
        mock = MockAdapter()
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock])

        session.start()
        session.start()  # second start should be no-op

        assert mock.disable_count == 1  # only called once
        session.stop()

    def test_stop_before_start_is_noop(self):
        mock = MockAdapter()
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock])

        session.stop()  # should not error
        assert mock.enable_count == 0
        assert mock.cleanup_count == 0

    def test_double_stop_is_noop(self):
        mock = MockAdapter()
        session = ForgetSession(str(SCRATCH_ROOT), adapters=[mock])

        session.start()
        session.stop()
        session.stop()  # second stop should be no-op

        assert mock.enable_count == 1  # only called once


class TestForgetSessionContextManager:
    def test_context_manager_starts_and_stops(self):
        mock = MockAdapter()
        with ForgetSession(str(SCRATCH_ROOT), adapters=[mock]) as session:
            assert session.is_active
            assert mock.is_active

        assert not mock.is_active
        assert mock.cleanup_count == 1

    def test_context_manager_cleans_up_on_exception(self):
        """Even if an exception occurs inside the with block,
        adapters must be re-enabled and cleaned up."""
        mock = MockAdapter()

        with pytest.raises(ValueError, match="boom"), ForgetSession(str(SCRATCH_ROOT), adapters=[mock]):
            raise ValueError("boom")

        # Adapter must be re-enabled and cleaned up despite the exception.
        assert not mock.is_active
        assert mock.enable_count == 1
        assert mock.cleanup_count == 1


class TestForgetSessionCheckpoint:
    def test_start_with_checkpoint(self):
        session = ForgetSession(str(SCRATCH_ROOT))
        session.start(checkpoint_summary="Discussing secret project X")

        checkpoint = SCRATCH_ROOT / "memory" / "forgetted-checkpoint.md"
        assert checkpoint.exists()
        assert "secret project X" in checkpoint.read_text()
        session.stop()

    def test_start_without_checkpoint(self):
        session = ForgetSession(str(SCRATCH_ROOT))
        session.start()

        checkpoint = SCRATCH_ROOT / "memory" / "forgetted-checkpoint.md"
        assert not checkpoint.exists()
        session.stop()
