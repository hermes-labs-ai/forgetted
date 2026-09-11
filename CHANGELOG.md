# Changelog

## [Unreleased]
### Added
- `HindsightAdapter` and `CrewAIAdapter` (`forgetted.adapters.native`): drive each framework's own read-only flag (`retain_suspended` / `read_only`) for the window and restore the prior value on exit (#30).
### Fixed
- Native adapter `disable()`/`enable()` transitions are atomic under concurrent calls (#31).
### Changed
- Test suite documents that nested (LIFO) sessions work; the remaining known limitation is an out-of-order stop of overlapping sessions.

## [0.2.2] - 2026-08-04
### Fixed
- Bind PyPI publishing to the release tag and validate source and built-package integrity before upload.

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
