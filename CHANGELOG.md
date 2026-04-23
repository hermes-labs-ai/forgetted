# Changelog

## [0.2.0] - 2026-03-22
### Added
- Mem0Adapter for blocking vector DB writes during incognito sessions
- `ForgetSession` context manager with checkpoint/restore lifecycle
- Adapter registry for custom persistence layers
- 99 tests covering all adapters and edge cases

## [0.1.0] - 2026-03-15
### Added
- Initial release
- File-based write interception via `builtins.open` patch
- Memory file and session log blocking
