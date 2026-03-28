# Contributing to forgetted

Thanks for your interest in contributing!

## Getting Started

```bash
git clone https://github.com/roli-lpci/forgetted.git
cd forgetted
pip install -e ".[dev]"
pytest tests/ -v
```

## Making Changes

1. Fork the repo and create a branch from `main`
2. Write tests for your changes
3. Ensure all tests pass: `pytest tests/ -v`
4. Submit a pull request

## Code Style

- Python 3.9+ compatible
- Google-style docstrings
- Use `logging` instead of `print()` in library code

## Reporting Bugs

Use the [bug report template](https://github.com/roli-lpci/forgetted/issues/new?template=bug_report.yml).
