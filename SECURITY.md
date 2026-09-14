# Security Policy

## Scope

forgetted intercepts writes made through `builtins.open` to protected
workspace paths, and (with the `Mem0Adapter` registered) `mem0`
`add`/`update` calls, for the duration of a `ForgetSession` window. As
documented in [README.md's Threat Model](README.md#threat-model), it is a
software convenience layer, not a security or containment boundary: writes
that bypass `builtins.open` (`Path.write_text`, `Path.write_bytes`,
`os.open`, C-extension writes, subprocesses), LLM-provider logs, network
telemetry, and OS-level forensics are out of scope by design.

## Reporting a Vulnerability

If you find a way to leak a protected write within the scope above — for
example, a bypass of the `builtins.open` guard, an adapter that fails to
restore its prior state on exit, or a cleanup step that misses a file it
should delete — please report it responsibly.

**Do not open a public issue for security-relevant reports.**

Instead, email: **roli@hermes-labs.ai**

Include:
- A description of the issue and why it falls inside the scope above.
- Steps to reproduce the issue.
- Any relevant logs or output.

## Response Timeline

forgetted is maintained by a single maintainer, on a best-effort basis:

- **Acknowledgment**: within 48 hours of your report.
- **Assessment**: within 7 days we will confirm the issue and outline next steps.
- **Fix**: we aim to release a patch within 30 days of confirmation. This is
  a best-effort target, not a guaranteed SLA.

## Supported Versions

Security fixes are applied to the latest release only.

Thank you for helping keep forgetted's stated scope honest.
