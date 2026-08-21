# Known issues

Bugs found by the test suite and confirmed, but **not yet fixed** — each
changes program output, so fixing them is a deliberate decision rather than a
drive-by edit. Each has a `strict=True` xfail test that will start failing
(as XPASS) the moment the bug is fixed, prompting removal of the marker.

---

## 1. Every dollar figure is overstated by 1000x

**Severity: high — the digest reports wrong numbers.**

`fetch_13f_holdings()` scales the filing's `<value>` field by 1000:

```python
value = int(txt("value") or 0) * 1000   # SEC reports in $thousands
```

That comment was true before 2023. The SEC's June 2022 Form 13F amendments
changed the rounding convention, with a compliance date of **3 January 2023**:

> "Simplifies the rounding conventions of Form 13F to require that the dollar
> values reported be rounded to the nearest dollar (rather than to the nearest
> one thousand dollars)."
> — [SEC Form 13F FAQ](https://www.sec.gov/divisions/investment/13ffaq), FAQ 36

Every 13F filed on or after that date — which is every filing this tracker
fetches, since it always takes the most recent — reports whole dollars. The
`* 1000` therefore inflates every figure by three orders of magnitude:
a manager holding $300B is rendered as `$300.0T`.

This affects manager totals, consensus values, mega positions, and every
`fmt_usd()` output in the email.

**Fix:** drop the `* 1000`. Note this makes historical digests
non-comparable with new ones.

- Test documenting current behaviour: `test_value_is_scaled_by_one_thousand`
- Test encoding correct behaviour: `test_value_should_be_whole_dollars_for_modern_filings` (xfail)

---

## 2. The XML fallback path builds an unreachable URL

**Severity: medium — silent data loss for affected filers.**

When a filing folder contains no file with `infotable` in its name,
`fetch_13f_holdings()` falls back to the primary document:

```python
xml_link = f"/{acc}/{meta['primaryDocument']}"
...
xml_url = f"https://www.sec.gov{xml_link}"
```

This omits the `/Archives/edgar/data/<cik>/` prefix that EDGAR archive paths
require:

```
built:   https://www.sec.gov/000095012326000222/primary_doc.xml
correct: https://www.sec.gov/Archives/edgar/data/1067983/000095012326000222/primary_doc.xml
```

The built URL always 404s. The exception is caught and `[]` returned, so the
manager is silently dropped from the digest with only a console warning —
no failure, no alert, just a shorter report.

**Fix:** build the fallback from the same `folder_url` already computed a few
lines above.

- Test: `test_fallback_to_primary_doc_builds_a_valid_url` (xfail)

---

## 3. Dead code in `fetch_13f_holdings()`

**Severity: low — cosmetic.**

`idx_url` and `index_url` are constructed and never used. `idx_url` also
hardcodes the filer prefix `0001193125`, which is wrong for most managers.
Both should be deleted.
