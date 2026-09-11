# AGENTS.md — forgetted

## Role
You are working on forgetted, a selective memory governance library for AI agents.
Stack: Python 3.9+, zero required dependencies.

## Commands
```bash
pip install -e ".[dev]"          # Install with dev deps
python -m pytest tests/ -v       # Run tests (116 tests: 113 pass, 3 xfail)
```

## Project Structure
```
forgetted/
  __init__.py      — Package exports, version
  trigger.py       — Detect forgetted activation in user messages
  guard.py         — ForgetGuard (builtins.open monkey-patch)
  checkpoint.py    — Save/load resumption files
  cleaner.py       — Find and delete session logs
  session.py       — ForgetSession orchestrator
  adapters/
    base.py        — PersistenceAdapter ABC
    file_write.py  — Wraps ForgetGuard as adapter
    mem0.py        — mem0 semantic memory adapter
    native.py      — HindsightAdapter / CrewAIAdapter (framework-native read-only flags)
```

## Testing
- 116 tests (113 pass, 3 xfail) — the xfail cases document known bypass paths (Path.write_text/write_bytes, out-of-order stop of overlapping sessions)
- Run full suite before any PR that touches core logic

## Boundaries
- Always: run tests before committing
- Ask first: new dependencies, adapter changes
- Never: commit API keys, modify test fixtures without re-running full suite
