"""
forgetted.trigger — Detect forgetted mode activation in user messages.

Supports exact commands (/forgetted) and natural-language variants
("forget this", "go off the record"). Case-insensitive matching.
"""

# Trigger phrases — checked via substring match against lowercased input.
TRIGGERS: list[str] = [
    "/forgetted",
    "/forget",
    "forget this",
    "go off the record",
    "off the record",
    "forgetted mode",
    "this is off the record",
    "don't remember this",
]


def is_forget_trigger(message: str) -> bool:
    """Check whether a user message contains a forgetted trigger.

    Parameters
    ----------
    message : str
        Raw user message text.

    Returns
    -------
    bool
        True if the message activates forgetted mode.
    """
    lowered = message.lower()
    return any(trigger in lowered for trigger in TRIGGERS)
