<div align="center">
  <h1 align="center">🫥 forgetted</h1>
  <p>A small Python library that gives AI agents selective memory governance: keep full read access while writes to protected persistence layers vanish inside a context-managed window.</p>
  <p>forgetted is developed by <a href="https://hermes-labs.ai">Hermes Labs</a>.</p>
  <p>Hermes Labs is an agentic infrastructure company building the reliability layer for autonomous systems.</p>
  <p align="center">
    <a href="https://pypi.org/project/forgetted/"><img src="https://img.shields.io/pypi/v/forgetted" alt="PyPI"></a>
    <a href="https://pypi.org/project/forgetted/"><img src="https://img.shields.io/pypi/dm/forgetted" alt="Downloads"></a>
    <a href="https://github.com/hermes-labs-ai/forgetted"><img src="https://img.shields.io/github/stars/hermes-labs-ai/forgetted" alt="Stars"></a>
    <a href="https://github.com/hermes-labs-ai/forgetted/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/forgetted" alt="License"></a>
    <a href="https://pypi.org/project/forgetted/"><img src="https://img.shields.io/pypi/pyversions/forgetted" alt="Python"></a>
    <a href="https://github.com/hermes-labs-ai/forgetted/actions/workflows/ci.yml"><img src="https://github.com/hermes-labs-ai/forgetted/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  </p>
</div>

---

**Your AI agent remembers everything. Now it doesn't have to.**

**forgetted** is a small Python library that gives AI agents selective memory governance: inside a context-managed window the agent keeps full read access but its writes to memory files, session logs, deliverables, and (optionally) a vector store silently vanish and are cleaned up on exit. One `with` block, and your agent keeps full context but persists nothing.

> Traditional incognito is all-or-nothing: no past, no future, fully isolated.
> **forgetted** keeps full read continuity while making the write side non-persistent for the duration of a window.

```python
from forgetted import ForgetSession

with ForgetSession("/path/to/workspace"):
    agent.chat("this conversation never happened")
# ↑ Writes through `builtins.open` to protected workspace paths do not persist.
#    Add an adapter for mem0 or another persistence layer; reads still work.
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
import tempfile
from pathlib import Path

from forgetted import ForgetSession

with tempfile.TemporaryDirectory() as workspace_str:
    workspace = Path(workspace_str)
    (workspace / "memory").mkdir()
    notes = workspace / "memory" / "notes.md"

    # Inside the window, writes through `open()` to protected paths
    # (memory/, DELIVERABLES.md, *.jsonl) silently vanish. Reads are never blocked.
    with ForgetSession(str(workspace)):
        with open(notes, "w") as f:
            f.write("this conversation never happened")

    print(notes.exists())  # False — the write was intercepted

    # After the window, writes persist normally again.
    with open(notes, "w") as f:
        f.write("this one is remembered")

    print(notes.read_text())  # this one is remembered
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

### With framework-native read-only switches

`HindsightAdapter` and `CrewAIAdapter` don't patch framework methods. Hindsight
uses the client's task-local `suspend_retains()` context manager; CrewAI's adapter
sets and restores its `read_only` flag.

```python
from forgetted import ForgetSession
from forgetted.adapters import CrewAIAdapter, HindsightAdapter

session = ForgetSession(
    workspace="/path/to/workspace",
    adapters=[
        HindsightAdapter(hindsight_client),
        CrewAIAdapter(crew_memory),
    ],
)
session.start()
# ... conversation happens with full context, zero persistence ...
session.stop()  # restores each layer's prior setting
```

`HindsightAdapter` requires a Hindsight client exposing `suspend_retains()`;
`CrewAIAdapter` requires a CrewAI memory exposing `read_only`. Each raises
`AttributeError` at construction if its API is missing, so an unsupported
version fails loudly instead of silently not blocking.

CrewAI status (verified 2026-09-11): `crewai` 1.15.21 on PyPI exposes
`Memory.read_only`, so `CrewAIAdapter` blocks `remember()`/`remember_many()` with a
released CrewAI; that release still writes access times on `recall()` and allows
`update()` under `read_only` (fixed upstream in the still-open
[crewAIInc/crewAI#7367](https://github.com/crewAIInc/crewAI/pull/7367)).
`hindsight-client` 0.10.1 includes the task-local `suspend_retains()` context
manager added in [vectorize-io/hindsight#4285](https://github.com/vectorize-io/hindsight/pull/4285)
(merged upstream Sep 15, 2026 and released to PyPI Sep 21, 2026).

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
| Hindsight | Task-local `suspend_retains()` context manager | ✅ Available in `hindsight-client` 0.10.1+ |
| CrewAI memory | Framework-native `read_only` flag | ✅ Blocked |
| Any custom persistence | Write your own adapter | 🔌 Extensible |

## How It Works

**forgetted** uses a layered defense:

1. **`FileWriteAdapter`** (always on) — patches `builtins.open` to intercept writes to protected paths. Returns no-op file handles instead of raising — agent code doesn't crash, writes just vanish.

2. **`Mem0Adapter`** (opt-in) — patches `memory.add()` and `memory.update()` during the window. Post-window cleanup deletes any memories that leaked through.

3. **`HindsightAdapter`** / **`CrewAIAdapter`** (opt-in) — enter the client's task-local `suspend_retains()` scope or set CrewAI's `read_only` flag for the window, then exit the scope or restore the flag. No patching or cleanup sweep is needed.

4. **`ForgetSession`** orchestrates everything: checkpoint → disable adapters → run conversation → enable adapters → cleanup → delete session log.

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

Like git: you branch, but you never merge back. The conversation exists in context, and the writes it would normally make to the agent's persistent state are intercepted instead. After the window closes, a normal read of the agent's memory and logs shows no trace of it — within the scope described in [Limitations](#limitations).

> *"I want context… but I don't want consequences."*

## Tested

116 tests (113 pass, 3 xfail) including an adversarial suite:
- ✅ Write blocking via `builtins.open` (modes `w`/`a`/`x`/`wb`/`r+`, symlinks resolved, binary)
- ✅ Trigger detection (no false positive on "I'm so forgetful today", etc.)
- ✅ Adapter error isolation (one failing adapter doesn't break others)
- ✅ Exception safety (cleanup runs even if the conversation crashes)
- ✅ Idempotency (double-start, stop-before-start, double-stop all safe)

Known bypasses (writes that do **not** go through `builtins.open`, such as `Path.write_text`/`write_bytes` and `os.open`) are documented as [xfail tests](tests/test_adversarial.py) rather than hidden. See [Limitations](#limitations) below.

## Threat Model

**What forgetted blocks:** Writes that go through `builtins.open` to protected workspace paths (`memory/`, `DELIVERABLES.md`, `*.jsonl`), plus mem0 `add`/`update` when the Mem0Adapter is registered.

**What forgetted does NOT block:** LLM API provider logs, network telemetry, OS-level forensics, and writes that bypass `builtins.open` (see [Limitations](#limitations)). It is a convenience layer for agent-controlled persistence, not a security or containment boundary.

**What you can rely on, within that scope:** writes routed through `builtins.open` to protected paths are intercepted and return no-op handles, so a normal read of the agent's memory and logs afterward does not surface what happened inside the window. This is enforcement by effect (no-op handles + post-window cleanup), not a prompt instruction.

## Limitations

forgetted is a software convenience layer, not a security boundary. Grounded in the code and the [xfail test suite](tests/test_adversarial.py), it does **not**:

- **Catch writes that bypass `builtins.open`.** `Path.write_text`, `Path.write_bytes`, `os.open`, C-extension writes, and subprocesses write directly and are not intercepted. These are documented as xfail tests.
- **Erase data written before the window opened.** It governs writes during the window only; pre-existing memory is untouched.
- **Block reads.** By design — the agent keeps full read context.
- **Intercept writes outside the declared workspace path.**
- **Block network calls, API calls, or external tool use.**
- **Support overlapping forgetted sessions stopped out of order.** Properly nested (LIFO) sessions work, but stopping an outer session before an inner one restores the real `open` underneath the still-active inner window (xfail test).
- **Defend against an adversary inspecting LLM-provider logs, network traffic, or raw disk forensics.**

For the full machine-readable behavior contract, see [`INTENT.md`](INTENT.md).

If forgetted is useful to you, please [star the repo](https://github.com/hermes-labs-ai/forgetted) — it helps others find it.

## More from Hermes Labs
- [lintlang](https://github.com/hermes-labs-ai/lintlang) — Static analysis for AI agent tool descriptions and workflows.
- [little-canary](https://github.com/hermes-labs-ai/little-canary) — Prompt injection detection through a powerless sacrificial model.
- [fidelis](https://github.com/hermes-labs-ai/fidelis) — Semantic memory for long-running agents with local retrieval.
- [hermeneutic](https://github.com/hermes-labs-ai/hermeneutic) — Detect recurring AI drift from correction history.
- [zer0dex](https://github.com/hermes-labs-ai/zer0dex) — Local agent recall without burdening the context window.
- [claude-plugins marketplace](https://github.com/hermes-labs-ai/claude-plugins) — Plugin system for Claude Code extensibility.

Browse the [open-source catalog](https://hermes-labs.ai/open-source) or contact [roli@hermes-labs.ai](mailto:roli@hermes-labs.ai).

## License

[Apache-2.0](LICENSE) — Hermes Labs
