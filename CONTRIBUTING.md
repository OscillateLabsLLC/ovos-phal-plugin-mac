# Contributing to ovos-phal-plugin-mac

This plugin is in **Security Fixes Only** status. Contributions are accepted for:

- Security vulnerability fixes
- Critical bug fixes that cause crashes or data loss
- Dependency updates required for security reasons

Feature requests and non-critical enhancements may be accepted.

## Development Setup

### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) package manager

### Getting Started

```bash
git clone https://github.com/OscillateLabsLLC/ovos-phal-plugin-mac
cd ovos-phal-plugin-mac

# Install dependencies (including test extras)
uv sync --extra test
```

## Common Commands

```bash
# Run tests
uv run pytest

# Run linter
uv run ruff check .

# Format code
uv run ruff format .
```

## Pull Requests

1. Create a feature branch: `git checkout -b fix/my-fix`
2. Make your changes and add tests where applicable
3. Run `uv run ruff check .` and `uv run pytest` to ensure everything passes
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `fix:`, `security:`)
5. Open a pull request

**PR Guidelines:**

- Keep PRs focused on a single concern
- Include tests for changes where possible
- Ensure all CI checks pass

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
