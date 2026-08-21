# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A single-file Python tool that pulls 13F-HR institutional holdings from SEC
EDGAR, computes summary analytics, and renders an HTML email digest.

All logic lives in `tracker.py` (~530 lines). There is no package, no
framework, and no database. Keep it that way unless there's a concrete reason
not to — the value of this project is that one file is readable end to end.

## Layout

| Path | Purpose |
|---|---|
| `tracker.py` | Everything: config, fetch, parse, analytics, render, send |
| `tests/` | pytest suite, fully offline |
| `tests/fixtures/` | Saved EDGAR responses — the contract with SEC's format |
| `KNOWN-ISSUES.md` | Confirmed bugs with xfail tests, not yet fixed |
| `.claude/skills/` | Vendored skills (see `.claude/skills/README.md`) |
| `.github/workflows/weekly.yml` | Digest runner — **manual dispatch only** |
| `.github/workflows/tests.yml` | CI: runs the test suite |

`tracker.py` is organised in labelled sections (CONFIGURATION, SEC EDGAR
HELPERS, PRICE LOOKUP, ANALYTICS, EMAIL FORMATTING, EMAIL SENDER, MAIN).
Add new code to the section it belongs to and keep the banner comments.

## Commands

```bash
pip install -r requirements.txt -r requirements-dev.txt   # setup
python3 -m pytest                                         # full suite (<1s)
python3 -m pytest tests/test_parsing.py -q                # one file
python3 -m pytest -k consensus                            # one topic
python3 tracker.py                                        # real run — SENDS EMAIL
```

**`python3 tracker.py` hits the live SEC API and sends a real email.** Never
run it to "check if something works" — write or run a test instead.

## Testing rules

- **Never let a test touch the network.** `tests/conftest.py` installs an
  autouse guard that raises on any unmocked `requests.get`. If you see that
  assertion, mock the call — do not disable the guard.
- **Parsing changes need a fixture.** Add a saved response to
  `tests/fixtures/` rather than inventing XML inline in a test, unless the
  case is a one-line malformation.
- **Test behaviour, not implementation.** Assert on parsed holdings and
  rendered output, not on internal call sequences — except where the test is
  specifically about URL construction, which is where the real bugs are.
- **`xfail` must be `strict=True`.** A bug that gets fixed should make its
  xfail test fail loudly so the marker gets removed.

## Domain notes that have already caused bugs

- **Values are whole dollars, not thousands.** SEC changed this effective
  2023-01-03. `tracker.py` still multiplies by 1000. See KNOWN-ISSUES.md #1.
- **EDGAR archive URLs use the unpadded CIK**
  (`/Archives/edgar/data/1067983/`) while the submissions API uses the
  10-digit zero-padded form (`CIK0001067983.json`). Mixing them up 404s.
- **Accession numbers appear in two forms**: dashed in the API
  (`0000950123-26-000222`), dashless in archive paths.
- **13F XML is namespaced**, sometimes with a prefix (`ns1:infoTable`).
  Only the `lxml-xml` parser handles both; `lxml` and `html.parser` silently
  return zero holdings. Do not change the parser argument.
- **SEC requires a contact address in the User-Agent** or it returns 403.
- **SEC rate-limits.** `main()` sleeps 0.5s between managers. Keep it.
- Filings report `putCall` for derivative positions; these are *not* long
  equity stakes and are carried through to the digest as-is.

## Conventions

- Python 3.11+. Standard library plus `requests`, `beautifulsoup4`, `lxml`,
  `yfinance` — check with the user before adding a dependency.
- Network calls get an explicit `timeout=`, wrapped in `try/except`, and
  degrade to an empty result with a printed warning rather than raising. A
  single bad manager must never abort the whole run.
- Type hints on function signatures, docstrings on every function.
- Money is formatted through `fmt_usd()`, never interpolated raw.

## Before saying a change works

Run `python3 -m pytest` and quote the result. The suite is under a second —
there is no excuse for claiming green without running it. If you changed
parsing, say which fixture covers the change.
