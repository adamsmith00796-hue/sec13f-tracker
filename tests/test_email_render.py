"""End-to-end render test for the digest HTML.

This is the last gate before an email reaches a recipient: it proves the
whole pipeline composes and that real numbers land in the output.
"""
import pytest

import tracker


@pytest.fixture(autouse=True)
def stub_prices(monkeypatch):
    """Price lookups are yfinance calls; pin them so the render is offline."""
    monkeypatch.setattr(
        tracker, "get_price_info",
        lambda name: {"current": "$100.00", "target": "$90.00"})


@pytest.fixture
def digest():
    holdings = [
        {"name": "APPLE INC", "cusip": "037833100", "value": 5_000_000_000,
         "shares": "100", "put_call": ""},
        {"name": "BANK OF AMERICA CORP", "cusip": "060505104",
         "value": 2_000_000_000, "shares": "50", "put_call": "Put"},
    ]
    summary = tracker.summarise_manager("Berkshire Hathaway", holdings)
    summary["filed"] = "2026-05-15"
    summaries = [summary]
    return (summaries,
            tracker.consensus_stocks(summaries),
            tracker.mega_positions(summaries))


class TestBuildEmailHtml:
    def test_renders_without_error_and_returns_html(self, digest):
        summaries, consensus, mega = digest
        html = tracker.build_email_html(summaries, consensus, mega, "2026-05-15")
        assert isinstance(html, str) and len(html) > 500
        assert "<html" in html.lower()

    def test_includes_manager_and_holdings(self, digest):
        summaries, consensus, mega = digest
        html = tracker.build_email_html(summaries, consensus, mega, "2026-05-15")
        assert "Berkshire Hathaway" in html
        assert "APPLE INC" in html
        assert "BANK OF AMERICA CORP" in html

    def test_formats_values_rather_than_dumping_raw_integers(self, digest):
        summaries, consensus, mega = digest
        html = tracker.build_email_html(summaries, consensus, mega, "2026-05-15")
        assert "$5.0B" in html
        assert "5000000000" not in html

    def test_shows_the_run_date(self, digest):
        summaries, consensus, mega = digest
        html = tracker.build_email_html(summaries, consensus, mega, "2026-05-15")
        assert "2026-05-15" in html

    def test_empty_digest_still_renders(self):
        # A week where every fetch failed must not raise on the way out.
        html = tracker.build_email_html([], [], [], "2026-05-15")
        assert isinstance(html, str)
        assert "2026-05-15" in html
