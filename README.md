# forgetted 🫥

> *Branch the timeline, but never merge back.*

Selective memory governance for AI agents.

**forgetted** is not incognito mode. It's a memory architecture primitive — a fork without consequence. Your agent keeps full context from the past, but nothing from the forgetted window persists into the future.

Traditional incognito is dumb: no past, no future, fully isolated.
**forgetted** gives you: full continuity + selective non-persistence.

> "I want context… but I don't want consequences."

## Installation

```bash
pip install forgetted
```

With optional adapters:

```bash
pip install forgetted[trash]   # recoverable file deletion
```

## Quick Start (30 seconds)

```python
from forgetted import ForgetSession

# Everything inside the session is forgetted
with ForgetSession("/path/to/workspace"):
    # Agent runs with full context
    # But writes to memory, logs, and deliverables silently vanish
    agent.chat("tell me about the secret project")

# Back to normal — no trace remains
```

## With Custom Adapters

```python
from forgetted import ForgetSession
from forgetted.adapters.mem0 import Mem0Adapter

# Register your persistence layers
session = ForgetSession(
    workspace="/path/to/workspace",
    adapters=[Mem0Adapter(memory_instance, user_id="roli")],
    session_id="abc-123",
    agents_dir="~/.openclaw/agents/",
)

# Checkpoint before going dark (optional)
session.start(checkpoint_summary="Discussing API design for v2")

# ... forgetted conversation happens ...

# Re-enable all layers, run cleanup sweep, delete session log
session.stop(clean=True)
```

## What Gets Blocked

| Layer | Adapter | Status |
|---|---|---|
| Memory files (`memory/*.md`) | `FileWriteAdapter` (built-in) | ✅ Blocked |
| Deliverables log | `FileWriteAdapter` (built-in) | ✅ Blocked |
| Session logs (`*.jsonl`) | `FileWriteAdapter` + cleaner | ✅ Blocked + cleaned |
| mem0 (semantic memory) | `Mem0Adapter` | ✅ Blocked + cleaned |
| Your custom DB | Write your own adapter | 🔌 Extensible |

## Architecture

### ForgetSession (orchestrator)

Coordinates multiple persistence adapters. Always includes `FileWriteAdapter` as the safety net.

**Ordering contract for `stop()`:**
1. Re-enable all adapters (restore normal writes)
2. Run cleanup on each adapter (post-window sweep)
3. Delete session log

This ordering ensures cleanup code can write freely (e.g., `mem0.delete()`) because adapters are re-enabled first.

### Adapter Pattern

Every persistence layer implements a simple interface:

```python
from forgetted.adapters.base import PersistenceAdapter

class MyAdapter(PersistenceAdapter):
    name = "my-db"
    is_active = False

    def disable(self):   # Block writes
    def enable(self):    # Restore writes
    def cleanup(self):   # Post-window sweep
```

Built-in adapters:
- **FileWriteAdapter** — patches `builtins.open` to block file writes (safety net)
- **Mem0Adapter** — blocks `memory.add()` / `memory.update()`, cleans by timestamp

### Threat Model

**What forgetted blocks:** Everything the agent controls — memory files, vector DB writes, session logs, deliverables.

**What forgetted does NOT block:** LLM API provider logs, network telemetry, OS-level forensics. That's not our scope.

**The guarantee:** "If someone looks through the agent's memory and logs, they won't find what you didn't want them to find."

## The Test

If I use forgetted like this:
1. I ask something sensitive in a forgetted window
2. I exit
3. Later I ask something related in normal mode

Can the agent infer anything from that prior interaction?

**If yes → we failed. If no → we built something real.**

## Write Your Own Adapter

```python
from forgetted.adapters.base import PersistenceAdapter

class RedisAdapter(PersistenceAdapter):
    def __init__(self, client):
        self._client = client
        self._active = False
        self._blocked_keys = []

    @property
    def name(self): return "redis"

    @property
    def is_active(self): return self._active

    def disable(self):
        self._client.config_set("save", "")  # disable persistence
        self._active = True

    def enable(self):
        self._client.config_set("save", "3600 1")  # restore
        self._active = False

    def cleanup(self):
        for key in self._blocked_keys:
            self._client.delete(key)
```

## What This Really Is

This is not a UX feature. It's:

- **A memory governance primitive** — user-controlled memory architecture for AI systems
- **A fork without consequence** — like git: you branch, but you never merge back
- **A standard, not just a library** — frameworks can implement the adapter interface natively

## License

Apache-2.0
