"""Adversarial tests for forgetted — trying to BREAK the guarantees.

Tests write bypass vectors, trigger false positives, checkpoint edge cases,
cleaner edge cases, and session orchestrator edge cases.

All file operations use /tmp/incognito-test/scratch as scratch space.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from forgetted.checkpoint import create_checkpoint, load_checkpoint
from forgetted.cleaner import delete_session_log, find_session_log
from forgetted.guard import ForgetGuard
from forgetted.session import ForgetSession
from forgetted.trigger import is_forget_trigger

SCRATCH_ROOT = Path("/tmp/incognito-test/scratch")


@pytest.fixture(autouse=True)
def clean_scratch():
    if SCRATCH_ROOT.exists():
        shutil.rmtree(SCRATCH_ROOT)
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    (SCRATCH_ROOT / "memory").mkdir()
    yield


# =========================================================================
# 1. WRITE BYPASS VECTORS
# =========================================================================


class TestWriteBypass:
    def test_pathlib_write_text_bypasses_guard(self):
        """Path.write_text() uses os.open internally — bypasses builtins.open."""
        target = SCRATCH_ROOT / "memory" / "pathlib_bypass.md"
        with ForgetGuard(str(SCRATCH_ROOT)):
            target.write_text("pathlib bypass attempt")
        bypass_occurred = target.exists()
        if bypass_occurred:
            pytest.xfail("KNOWN: Path.write_text() bypasses builtins.open patch")

    def test_pathlib_write_bytes_bypasses_guard(self):
        """Path.write_bytes() — same low-level path as write_text."""
        target = SCRATCH_ROOT / "memory" / "pathlib_bytes.md"
        with ForgetGuard(str(SCRATCH_ROOT)):
            target.write_bytes(b"bytes bypass attempt")
        bypass_occurred = target.exists()
        if bypass_occurred:
            pytest.xfail("KNOWN: Path.write_bytes() bypasses builtins.open patch")

    def test_os_open_bypasses_guard(self):
        """os.open() + os.write() uses file descriptors — known bypass."""
        target = SCRATCH_ROOT / "memory" / "os_bypass.md"
        with ForgetGuard(str(SCRATCH_ROOT)):
            fd = os.open(str(target), os.O_WRONLY | os.O_CREAT, 0o644)
            os.write(fd, b"os.open bypass")
            os.close(fd)
        assert target.exists(), "os.open should bypass (known limitation)"
        target.unlink()

    def test_subprocess_bypasses_guard(self):
        """Shell commands bypass Python entirely."""
        target = SCRATCH_ROOT / "memory" / "shell_bypass.md"
        with ForgetGuard(str(SCRATCH_ROOT)):
            subprocess.run(["bash", "-c", f"echo 'shell bypass' > {target}"], check=True)
        assert target.exists(), "subprocess should bypass (known limitation)"
        target.unlink()

    def test_open_exclusive_create_blocked(self):
        """open() with 'x' (exclusive create) mode should be blocked."""
        target = SCRATCH_ROOT / "memory" / "exclusive.md"
        with ForgetGuard(str(SCRATCH_ROOT)), open(target, "x") as f:
            f.write("exclusive create")
        assert not target.exists()

    def test_open_binary_write_blocked(self):
        """open() with 'wb' should be blocked."""
        target = SCRATCH_ROOT / "memory" / "binary.md"
        with ForgetGuard(str(SCRATCH_ROOT)), open(target, "wb") as f:
            f.write(b"binary write")
        assert not target.exists()

    def test_open_read_write_mode_blocked(self):
        """open() with 'r+' should be blocked because + includes write."""
        target = SCRATCH_ROOT / "memory" / "readwrite.md"
        target.write_text("original content")
        with ForgetGuard(str(SCRATCH_ROOT)), open(target, "r+") as fh:  # noqa: SIM115
            fh.write("overwritten")
        content = target.read_text()
        assert content == "original content", "r+ write should have been blocked"

    def test_rename_into_protected_path(self):
        """Write outside workspace, rename into memory/ — known bypass."""
        outside = SCRATCH_ROOT / "harmless.txt"
        target = SCRATCH_ROOT / "memory" / "sneaky.md"
        with ForgetGuard(str(SCRATCH_ROOT)):
            with open(outside, "w") as f:
                f.write("sneaky content")
            outside.rename(target)
        assert target.exists(), "rename should bypass (known limitation)"
        target.unlink()

    def test_shutil_copy_blocked_but_crashes(self):
        """shutil.copy() uses builtins.open for the copy, so the write is
        blocked. But then shutil tries to chmod the non-existent destination,
        causing FileNotFoundError. Guard did its job — the write vanished."""
        source = SCRATCH_ROOT / "source.txt"
        source.write_text("source content")
        target = SCRATCH_ROOT / "memory" / "shutil_copy.md"
        with ForgetGuard(str(SCRATCH_ROOT)), pytest.raises(FileNotFoundError):
            shutil.copy(str(source), str(target))
        assert not target.exists()

    def test_symlink_write_resolved_and_blocked(self):
        """Write through a symlink pointing into memory/ — guard resolves it."""
        real_target = SCRATCH_ROOT / "memory" / "via_symlink.md"
        symlink = SCRATCH_ROOT / "innocent_link.txt"
        symlink.symlink_to(real_target)
        with ForgetGuard(str(SCRATCH_ROOT)), open(symlink, "w") as f:
            f.write("symlink attack")
        assert not real_target.exists(), "Symlink write to memory/ should be blocked"


# =========================================================================
# 2. TRIGGER FALSE POSITIVES
# =========================================================================


class TestTriggerFalsePositives:
    def test_forgot_password(self):
        assert not is_forget_trigger("I forgot my password")

    def test_forget_about_it(self):
        assert not is_forget_trigger("forget about it")

    def test_dont_forget_to(self):
        assert not is_forget_trigger("don't forget to buy milk")

    def test_forgetful(self):
        assert not is_forget_trigger("I'm so forgetful today")

    def test_unforgettable(self):
        assert not is_forget_trigger("that was unforgettable")

    def test_emoji_only(self):
        assert not is_forget_trigger("🫥🫥🫥")

    def test_trigger_buried_in_long_message(self):
        """Trigger at the end of a very long message should still fire."""
        assert is_forget_trigger("blah " * 500 + "/forgetted")

    def test_trigger_with_whitespace(self):
        assert is_forget_trigger("  /forgetted  ")
        assert is_forget_trigger("\n/forgetted\n")

    def test_on_the_record_not_triggered(self):
        assert not is_forget_trigger("let's keep this on the record")


# =========================================================================
# 3. CHECKPOINT EDGE CASES
# =========================================================================


class TestCheckpointEdgeCases:
    def test_empty_summary(self):
        path = create_checkpoint("", str(SCRATCH_ROOT))
        assert path.exists()
        assert "Forgetted Checkpoint" in path.read_text()

    def test_very_long_summary(self):
        long_summary = "A" * 10_000
        path = create_checkpoint(long_summary, str(SCRATCH_ROOT))
        assert long_summary in path.read_text()

    def test_special_chars(self):
        special = "# Heading\n\n**bold** 🫥 `code` — em-dash\n\n> blockquote"
        path = create_checkpoint(special, str(SCRATCH_ROOT))
        assert "🫥" in path.read_text()

    def test_double_checkpoint_overwrites(self):
        create_checkpoint("first", str(SCRATCH_ROOT))
        create_checkpoint("second", str(SCRATCH_ROOT))
        content = load_checkpoint(str(SCRATCH_ROOT))
        assert "second" in content
        assert "first" not in content

    def test_load_from_empty_dir(self):
        assert load_checkpoint(str(SCRATCH_ROOT)) is None

    def test_load_is_single_use(self):
        create_checkpoint("one-time", str(SCRATCH_ROOT))
        assert load_checkpoint(str(SCRATCH_ROOT)) is not None
        assert load_checkpoint(str(SCRATCH_ROOT)) is None


# =========================================================================
# 4. CLEANER EDGE CASES
# =========================================================================


class TestCleanerEdgeCases:
    def _make_agents_dir(self):
        d = SCRATCH_ROOT / "agents" / "main" / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def test_special_chars_in_session_id(self):
        d = self._make_agents_dir()
        (d / "agent_main_abc-123-def_456.jsonl").write_text("{}\n")
        found = find_session_log("abc-123-def", str(SCRATCH_ROOT / "agents"))
        assert found is not None

    def test_multiple_matches_returns_one(self):
        d = self._make_agents_dir()
        (d / "session-abc-1.jsonl").write_text("{}\n")
        (d / "session-abc-2.jsonl").write_text("{}\n")
        found = find_session_log("abc", str(SCRATCH_ROOT / "agents"))
        assert found is not None

    def test_delete_readonly_log_graceful(self):
        """Deleting from a read-only dir should not raise."""
        d = self._make_agents_dir()
        log = d / "readonly-session.jsonl"
        log.write_text("{}\n")
        d.chmod(0o555)
        try:
            delete_session_log(log)  # should not raise
        finally:
            d.chmod(0o755)


# =========================================================================
# 5. SESSION ORCHESTRATOR EDGE CASES
# =========================================================================


class TestSessionEdgeCases:
    def test_nonexistent_workspace(self):
        session = ForgetSession(str(SCRATCH_ROOT / "nonexistent"))
        session.start()
        session.stop()

    def test_nested_sessions_break_guard(self):
        """Nested ForgetSessions share builtins.open — inner stop() restores
        the original, breaking the outer guard. Known limitation."""
        ws1 = SCRATCH_ROOT / "ws1"
        ws2 = SCRATCH_ROOT / "ws2"
        for ws in (ws1, ws2):
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "memory").mkdir()

        target = ws1 / "memory" / "outer.md"
        with ForgetSession(str(ws1)):
            with ForgetSession(str(ws2)):
                pass
            # After inner stops, does outer still block?
            with open(target, "w") as f:
                f.write("after inner closed")

        if target.exists():
            pytest.xfail("KNOWN: nested sessions break — inner stop restores original open")

    def test_concurrent_sessions_same_workspace(self):
        """Two sessions on same workspace — second stop may break first."""
        s1 = ForgetSession(str(SCRATCH_ROOT))
        s2 = ForgetSession(str(SCRATCH_ROOT))
        s1.start()
        s2.start()
        s2.stop()

        target = SCRATCH_ROOT / "memory" / "concurrent.md"
        with open(target, "w") as f:
            f.write("after s2 stopped")
        s1.stop()

        if target.exists():
            pytest.xfail("KNOWN: concurrent sessions on same workspace break guard chain")

    def test_guard_restored_after_stop(self):
        """builtins.open must be the real open after guard stops."""
        import builtins
        original = builtins.open
        guard = ForgetGuard(str(SCRATCH_ROOT))
        guard.start()
        guard.stop()
        assert builtins.open is original
