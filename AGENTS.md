# AGENTS.md — forgetted

## Role
You are working on forgetted, a selective memory governance library for AI agents.
Stack: Python 3.9+, zero required dependencies.

## Commands
```bash
pip install -e ".[dev]"          # Install with dev deps
python -m pytest tests/ -v       # Run tests (99 + 2 xfail)
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
```

## Testing
- 99 tests + 2 xfail
- Run full suite before any PR that touches core logic

## Boundaries
- Always: run tests before committing
- Ask first: new dependencies, adapter changes
- Never: commit API keys, modify test fixtures without re-running full suite
