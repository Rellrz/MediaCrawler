# Repository Guidelines

## Project Structure & Module Organization

`main.py` is the CLI entry point. Platform crawlers live in `media_platform/<platform>/`; shared abstractions are in `base/`. Persistence spans `store/`, `database/`, and `cache/`. Settings are in `config/`, models in `model/`, proxies in `proxy/`, and utilities in `tools/`. The FastAPI app is under `api/`, documentation in `docs/`, and tests in `tests/` and legacy `test/`.

## Build, Test, and Development Commands

- `uv sync && uv run playwright install`: install dependencies and browser binaries (Python 3.11+).
- `uv run main.py --help`: show crawler options.
- `uv run uvicorn api.main:app --port 8080 --reload`: start the development API.
- `uv run pytest tests test`: run all unit and integration tests.
- `uv run pre-commit run --all-files`: run repository checks.
- `npm ci && npm run docs:dev`: install and serve VitePress documentation.

## Coding Style & Naming Conventions

Use four-space indentation, public-interface type hints, and async APIs for I/O. Use `snake_case` for modules/functions/variables, `PascalCase` for classes, and uppercase configuration constants. Keep platform behavior in its package and extract shared logic. New Python files require the project license header. Do not add backward-compatibility code unless explicitly requested.

## Agent Workflow Rules

- Begin every response with “您好”.
- Before writing code, describe the proposed approach and wait for approval.
- Clarify ambiguous requirements before implementation.
- If a change affects more than three files, split it into smaller tasks first.
- After coding, list edge cases and tests.
- After any correction, explain what went wrong and state a prevention plan.
- After every modification, inspect `git status`, `git diff`, and `git diff --check`; do not create a commit unless requested.

## Testing Guidelines

Pytest and `pytest-asyncio` are used. Name files `test_*.py`, classes `Test*`, and functions `test_*`. Prefer fixtures and mocks for platform requests. Isolate tests requiring external services. No coverage threshold is configured; add regression tests for bug fixes and focused tests for new behavior.

## Commit & Pull Request Guidelines

Use focused Conventional Commit-style subjects such as `feat: ...`, `fix: ...`, and `docs: ...`. PRs should explain motivation, list validation commands, link issues, and call out configuration or schema changes. Include screenshots for UI changes and sanitized logs for crawler defects.

## Security, Configuration & Responsible Use

Copy `.env.example` locally; never commit cookies, credentials, proxy keys, or user data. Respect platform terms, `robots.txt`, and rate limits. Review the non-commercial learning and research terms in `LICENSE`.
