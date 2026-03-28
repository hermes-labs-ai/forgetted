<p align="center">
  <h1 align="center">🫥 forgetted</h1>
  <p align="center"><strong>Your AI agent remembers everything. Now it doesn't have to.</strong></p>
  <p align="center">
    <a href="https://pypi.org/project/forgetted/"><img src="https://img.shields.io/pypi/v/forgetted" alt="PyPI"></a>
    <a href="https://pypi.org/project/forgetted/"><img src="https://img.shields.io/pypi/dm/forgetted" alt="Downloads"></a>
    <a href="https://github.com/roli-lpci/forgetted"><img src="https://img.shields.io/github/stars/roli-lpci/forgetted" alt="Stars"></a>
    <a href="https://github.com/roli-lpci/forgetted/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/forgetted" alt="License"></a>
    <a href="https://pypi.org/project/forgetted/"><img src="https://img.shields.io/pypi/pyversions/forgetted" alt="Python"></a>
    <a href="https://github.com/roli-lpci/forgetted/actions/workflows/ci.yml"><img src="https://github.com/roli-lpci/forgetted/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  </p>
</p>

---

**forgetted** gives AI agents selective memory governance. One line of code, and your agent keeps full context but writes nothing to memory.

> Traditional incognito is dumb: no past, no future, fully isolated.
> **forgetted** gives you: full continuity + selective non-persistence.

```python
from forgetted import ForgetSession

with ForgetSession("/path/to/workspace"):
    agent.chat("this conversation never happened")
# ↑ No trace in memory, logs, or vector DB. Agent resumes normally.
```

## Why?

AI agents write everything: memory files, session logs, vector embeddings, deliverables. Sometimes you need context without consequences:

- 💬 **Sensitive conversations** that shouldn't persist in agent memory
- 🧪 **Experiments** you don't want polluting your agent's knowledge base
- 🔒 **Client data** discussed but not stored
- 🤔 **Brainstorming** that shouldn't bias future responses

**forgetted** is not a prompt. It's software that wraps the agent's persistence layer — writes silently vanish, reads still work, and the agent resumes normally after.

## Install

```bash
pip install forgetted
```

## Quick Start

### Simple (file-level protection)

```python
from forgetted import ForgetSession

# Everything inside is forgetted — writes to memory/, logs, deliverables vanish
with ForgetSession("/path/to/agent/workspace"):
    agent.chat("tell me about the secret project")
```

### With vector DB protection

```python
from forgetted import ForgetSession
from forgetted.adapters.mem0 import Mem0Adapter

session = ForgetSession(
    workspace="/path/to/workspace",
    adapters=[Mem0Adapter(memory_instance, user_id="roli")],
)
session.start(checkpoint_summary="Discussing API design")
# ... conversation happens with full context, zero persistence ...
session.stop()  # re-enables all layers, cleans up
```

### Trigger detection (for chat agents)

```python
from forgetted import is_forget_trigger, ForgetSession

if is_forget_trigger(user_message):  # "/forget", "off the record", etc.
    with ForgetSession(workspace):
        handle_conversation()
```

## What Gets Blocked

| Layer | How | Status |
|---|---|---|
| Memory files (`memory/*.md`) | `builtins.open` patch | ✅ Blocked |
| Deliverables / audit logs | `builtins.open` patch | ✅ Blocked |
| Session logs (`*.jsonl`) | Blocked + deleted on exit | ✅ Blocked |
| mem0 / semantic memory | Method patch on `add`/`update` | ✅ Blocked |
| Any custom persistence | Write your own adapter | 🔌 Extensible |

## How It Works

**forgetted** uses a layered defense:

1. **`FileWriteAdapter`** (always on) — patches `builtins.open` to intercept writes to protected paths. Returns no-op file handles instead of raising — agent code doesn't crash, writes just vanish.

2. **`Mem0Adapter`** (opt-in) — patches `memory.add()` and `memory.update()` during the window. Post-window cleanup deletes any memories that leaked through.

3. **`ForgetSession`** orchestrates everything: checkpoint → disable adapters → run conversation → enable adapters → cleanup → delete session log.

Reads are **never** blocked. The agent has full context — it just can't write new context.

## Write Your Own Adapter

Any persistence layer can be controlled:

```python
from forgetted.adapters.base import PersistenceAdapter

class RedisAdapter(PersistenceAdapter):
    name = "redis"

    def disable(self):
        self._client.config_set("save", "")
        self._active = True

    def enable(self):
        self._client.config_set("save", "3600 1")
        self._active = False

    def cleanup(self):
        for key in self._window_keys:
            self._client.delete(key)

    @property
    def is_active(self): return self._active
```

Register it: `ForgetSession(workspace, adapters=[RedisAdapter(client)])`

## Trigger Phrases

Built-in detection for natural-language triggers:

| Trigger | Example |
|---|---|
| `/forgetted` | "/forgetted" |
| `/forget` | "/forget" |
| `forget this` | "hey, forget this conversation" |
| `off the record` | "let's go off the record" |
| `forgetted mode` | "enable forgetted mode" |
| `don't remember this` | "don't remember this" |

## Architecture

```
┌─────────────────────────────────────────┐
│           ForgetSession                  │
│  (orchestrator — context manager)        │
├─────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐     │
│  │ FileWrite    │  │ Mem0         │     │
│  │ Adapter      │  │ Adapter      │ ... │
│  │ (safety net) │  │ (opt-in)     │     │
│  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────┤
│  checkpoint → disable → conversation    │
│  → enable → cleanup → delete log        │
└─────────────────────────────────────────┘
```

## What This Really Is

This is not a UX toggle. It's a **memory governance primitive**.

Like git: you branch, but you never merge back. The conversation exists in context but is never written to the agent's persistent state. After the window closes, it's as if it never happened.

> *"I want context… but I don't want consequences."*

## Tested

97 tests including an adversarial suite:
- ✅ Write blocking (open w/a/x/wb/r+, symlinks, binary)
- ✅ Trigger detection (zero false positives on "forgot password", "forgetful", etc.)
- ✅ Adapter error isolation (one failing adapter doesn't break others)
- ✅ Exception safety (cleanup runs even if conversation crashes)
- ✅ Idempotency (double-start, stop-before-start, double-stop all safe)

Known limitations are [documented as xfail tests](tests/test_adversarial.py) — not hidden.

## Threat Model

**What forgetted blocks:** Everything the agent controls — memory files, vector DB writes, session logs, deliverables.

**What forgetted does NOT block:** LLM API provider logs, network telemetry, OS-level forensics. That's not the point.

**The guarantee:** *"If someone looks through the agent's memory and logs, they won't find what you forgetted."*

## Hermes Labs Ecosystem

forgetted is part of the [Hermes Labs](https://hermes-labs.ai) open-source suite:

- [**little-canary**](https://github.com/roli-lpci/little-canary) — Prompt injection detection
- [**lintlang**](https://github.com/roli-lpci/lintlang) — Static linter for AI agent configs
- [**zer0dex**](https://github.com/roli-lpci/zer0dex) — Dual-layer memory for AI agents
- [**zer0lint**](https://github.com/roli-lpci/zer0lint) — mem0 extraction diagnostics
- [**suy-sideguy**](https://github.com/roli-lpci/suy-sideguy) — Autonomous agent watchdog
- [**quickthink**](https://github.com/roli-lpci/quickthink) — Planning scaffolding for local LLMs

---

If forgetted is useful to you, please [star the repo](https://github.com/roli-lpci/forgetted) — it helps others find it.

## License

[Apache-2.0](LICENSE) — Hermes Labs
