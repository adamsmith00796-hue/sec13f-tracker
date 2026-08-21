# Project skills

Vendored Claude Code skills, checked into the repo so every session — local,
web, or CI — starts with the same guidance. No marketplace or plugin install
is required; Claude picks these up automatically from `.claude/skills/`.

## Process skills

| Skill | Purpose |
|---|---|
| `test-driven-development` | Write the failing test before the implementation |
| `systematic-debugging` | Find root cause before proposing a fix |
| `verification-before-completion` | Run the check and show output before claiming done |

## Python skills

| Skill | Purpose |
|---|---|
| `python-testing-patterns` | pytest structure, fixtures, mocking network calls |
| `python-resilience` | Retries, timeouts, backoff — relevant to the SEC/yfinance fetches |
| `python-anti-patterns` | Common Python mistakes to avoid |

## Provenance

Both upstreams are MIT licensed. Vendored deliberately rather than installed
from a marketplace, so the content is version-controlled, reviewable in diffs,
and cannot change underneath a client build.

- Process skills — [obra/superpowers](https://github.com/obra/superpowers), MIT, © Jesse Vincent
- Python skills — `python-development` plugin, MIT

To update, re-copy from upstream and review the diff before committing.
