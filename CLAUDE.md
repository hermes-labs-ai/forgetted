# CLAUDE.md — Agent Instructions for forgetted

## What this project is

`forgetted` is a Python package that gives AI agents selective memory governance.
It blocks writes to persistence layers during a "forgetted window" while keeping
reads working normally. The agent has full context but can't write new context.

## Architecture

```
forgetted/
├── __init__.py          # Package exports, version
├── trigger.py           # Detect forgetted activation in user messages
├── guard.py             # ForgetGuard — builtins.open monkey-patch
├── checkpoint.py        # Save/load resumption files
├── cleaner.py           # Find and delete session logs
├── session.py           # ForgetSession — orchestrator (main entry point)
└── adapters/
    ├── base.py          # PersistenceAdapter ABC
    ├── file_write.py    # Wraps ForgetGuard as adapter
    ├── mem0.py          # mem0 semantic memory adapter (method patch on add/update)
    └── native.py        # HindsightAdapter / CrewAIAdapter — flip the framework's own read-only flag
```

## Key design decisions

1. **builtins.open patch** is the safety net — catches writes from any layer
2. **Adapter pattern** for extensibility — each persistence layer registers separately
3. **No-op returns** instead of raising — agent code doesn't crash, writes silently vanish
4. **ForgetSession.stop() ordering**: enable first → cleanup → delete log (so cleanup code can write)
5. **Idempotent** — double-start, stop-before-start, double-stop are all safe no-ops

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

116 tests (113 pass, 3 xfail). Test files:
- `test_forgetted.py` — core module tests (triggers, guard, checkpoint, cleaner)
- `test_session.py` — ForgetSession orchestrator tests
- `test_adapters.py` — FileWriteAdapter, Mem0Adapter, HindsightAdapter and CrewAIAdapter tests (fake objects, no framework installed)
- `test_adversarial.py` — bypass vectors, false positives, edge cases

## Known limitations (documented in `test_adversarial.py`)

- `Path.write_text()` / `Path.write_bytes()` bypass builtins.open (uses os.open internally) — xfail
- `os.open()` + `os.write()` bypass (low-level file descriptors) — asserted as a bypass
- `subprocess` / shell commands bypass (outside Python) — asserted as a bypass
- `rename()` into protected paths bypass (filesystem operation) — asserted as a bypass
- Overlapping ForgetSessions stopped out of order (outer stopped before inner) break the
  guard chain — xfail. Properly nested (LIFO) sessions work: the inner guard hands
  `builtins.open` back to the outer guard, not to the real open.

These are acceptable for the threat model:
"Don't let this shape my agent's memory" — not "prevent all possible file I/O."

## Style

- Logging: `logging.getLogger(__name__)`
- Docstrings: Google style
- Tests: pytest fixtures, class grouping, descriptive names
- Emoji: 🫥 for log messages
- Target: Python 3.9+, zero required dependencies
