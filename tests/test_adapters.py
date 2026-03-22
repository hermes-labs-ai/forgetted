"""Tests for persistence adapters."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from forgetted.adapters.file_write import FileWriteAdapter

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
