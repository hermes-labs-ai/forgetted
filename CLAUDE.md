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
    └── mem0.py          # mem0 semantic memory adapter
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

99 tests + 2 xfail. Test files:
- `test_forgetted.py` — core module tests (triggers, guard, checkpoint, cleaner)
- `test_session.py` — ForgetSession orchestrator tests
- `test_adapters.py` — FileWriteAdapter and Mem0Adapter tests
- `test_adversarial.py` — bypass vectors, false positives, edge cases

## Known limitations (documented as xfail tests)

- `Path.write_text()` / `Path.write_bytes()` bypass builtins.open (uses os.open internally)
- `os.open()` + `os.write()` bypass (low-level file descriptors)
- `subprocess` / shell commands bypass (outside Python)
- `rename()` into protected paths bypass (filesystem operation)
- Nested ForgetSessions break (inner stop restores original open)

These are documented in `test_adversarial.py` and are acceptable for the threat model:
"Don't let this shape my agent's memory" — not "prevent all possible file I/O."

## Style

- Logging: `logging.getLogger(__name__)`
- Docstrings: Google style
- Tests: pytest fixtures, class grouping, descriptive names
- Emoji: 🫥 for log messages
- Target: Python 3.9+, zero required dependencies
