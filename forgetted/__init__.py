"""
forgetted — Selective memory governance for AI agents.

Branch the timeline, but never merge back.

When triggered, forgetted:
1. Checkpoints the current session context into a resumption file
2. Blocks all persistence layers via registered adapters
3. Self-cleans on exit (session logs, leaked memories)
4. Enables seamless resume from the checkpoint in the next session

This is not incognito mode. This is a fork without consequence —
a memory architecture primitive that gives users control over
what becomes part of their agent's memory.

Author: Hermes Labs
License: Apache-2.0
"""

from .adapters.base import PersistenceAdapter
from .adapters.file_write import FileWriteAdapter
from .checkpoint import create_checkpoint, load_checkpoint
from .cleaner import delete_session_log, find_session_log
from .guard import ForgetGuard
from .session import ForgetSession
from .trigger import TRIGGERS, is_forget_trigger

__version__ = "0.2.0"
__author__ = "Hermes Labs"
__all__ = [
    "create_checkpoint",
    "delete_session_log",
    "FileWriteAdapter",
    "find_session_log",
    "ForgetGuard",
    "ForgetSession",
    "is_forget_trigger",
    "load_checkpoint",
    "PersistenceAdapter",
    "TRIGGERS",
]
