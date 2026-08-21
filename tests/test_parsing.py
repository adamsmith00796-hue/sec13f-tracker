"""Tests for the SEC EDGAR fetch/parse layer.

Every network call is mocked against saved EDGAR fixtures. If SEC changes
their response shape, these fail loudly here instead of silently producing
an empty or wrong digest.
"""
import requests

import tracker


class TestGetLatest13F:
    def test_picks_most_recent_13f_skipping_other_forms(
            self, monkeypatch, submissions_json, fake_response):
        monkeypatch.setattr(
            requests, "get",
            lambda *a, **k: fake_response(json_data=submissions_json))

        meta = tracker.get_latest_13f("0001067983")

        # The 8-K is newer but must be skipped; the first 13F-HR wins.
        assert meta["accessionNumber"] == "0000950123-26-000222"
        assert meta["filingDate"] == "2026-05-15"
        assert meta["primaryDocument"] == "primary_doc.xml"

    def test_pads_cik_to_ten_digits_in_url(
            self, monkeypatch, submissions_json, fake_response):
        seen = {}

        def capture(url, **kwargs):
            seen["url"] = url
            return fake_response(json_data=submissions_json)

        monkeypatch.setattr(requests, "get", capture)
        tracker.get_latest_13f("1067983")
        assert seen["url"].endswith("/submissions/CIK0001067983.json")

    def test_sends_contact_user_agent_sec_requires(
            self, monkeypatch, submissions_json, fake_response):
        seen = {}

        def capture(url, **kwargs):
            seen["headers"] = kwargs.get("headers", {})
            return fake_response(json_data=submissions_json)

        monkeypatch.setattr(requests, "get", capture)
        tracker.get_latest_13f("1067983")
        # SEC rejects requests without a contact address in the UA.
        assert "@" in seen["headers"].get("User-Agent", "")

    def test_returns_none_when_no_13f_present(
            self, monkeypatch, fake_response):
        payload = {"filings": {"recent": {
            "form": ["8-K"], "filingDate": ["2026-01-01"],
            "accessionNumber": ["x"], "primaryDocument": ["y"]}}}
        monkeypatch.setattr(
            requests, "get", lambda *a, **k: fake_response(json_data=payload))
        assert tracker.get_latest_13f("1") is None

    def test_returns_none_on_http_error(self, monkeypatch, fake_response):
        monkeypatch.setattr(
            requests, "get", lambda *a, **k: fake_response(status=403))
        assert tracker.get_latest_13f("1") is None

    def test_returns_none_on_network_exception(self, monkeypatch):
        def boom(*a, **k):
            raise requests.ConnectionError("down")
        monkeypatch.setattr(requests, "get", boom)
        assert tracker.get_latest_13f("1") is None


META = {
    "accessionNumber": "0000950123-26-000222",
    "filingDate": "2026-05-15",
    "primaryDocument": "primary_doc.xml",
    "cik": "0001067983",
}


def route(monkeypatch, fake_response, folder_html, xml_text, calls=None):
    """Serve the folder listing first, then the XML document."""
    def _get(url, **kwargs):
        if calls is not None:
            calls.append(url)
        if url.endswith("/"):
            return fake_response(text=folder_html)
        return fake_response(text=xml_text)
    monkeypatch.setattr(requests, "get", _get)


class TestFetch13FHoldings:
    def test_parses_namespaced_infotable(
            self, monkeypatch, fake_response, folder_html, infotable_xml):
        route(monkeypatch, fake_response, folder_html, infotable_xml)

        holdings = tracker.fetch_13f_holdings(META)

        assert len(holdings) == 2
        apple = holdings[0]
        assert apple["name"] == "APPLE INC"
        assert apple["cusip"] == "037833100"
        assert apple["shares"] == "5000000"
        assert apple["put_call"] == ""

    def test_parses_prefixed_namespace_infotable(
            self, monkeypatch, fake_response, folder_html,
            infotable_prefixed_xml):
        # Some filers emit ns1:-prefixed tags; both forms appear on EDGAR.
        route(monkeypatch, fake_response, folder_html, infotable_prefixed_xml)

        holdings = tracker.fetch_13f_holdings(META)

        assert len(holdings) == 1
        assert holdings[0]["name"] == "MICROSOFT CORP"

    def test_captures_put_call_flag(
            self, monkeypatch, fake_response, folder_html, infotable_xml):
        route(monkeypatch, fake_response, folder_html, infotable_xml)
        holdings = tracker.fetch_13f_holdings(META)
        assert holdings[1]["put_call"] == "Put"

    def test_prefers_the_infotable_file_over_primary_doc(
            self, monkeypatch, fake_response, folder_html, infotable_xml):
        calls = []
        route(monkeypatch, fake_response, folder_html, infotable_xml, calls)

        tracker.fetch_13f_holdings(META)

        assert calls[1].endswith("form13fInfoTable.xml"), (
            f"should fetch the infotable, got {calls[1]}")

    def test_builds_folder_url_without_leading_zeros_on_cik(
            self, monkeypatch, fake_response, folder_html, infotable_xml):
        calls = []
        route(monkeypatch, fake_response, folder_html, infotable_xml, calls)

        tracker.fetch_13f_holdings(META)

        # EDGAR archive paths use the unpadded CIK and a dashless accession.
        assert calls[0] == (
            "https://www.sec.gov/Archives/edgar/data/1067983/"
            "000095012326000222/")

    def test_value_is_read_as_whole_dollars(
            self, monkeypatch, fake_response, folder_html, infotable_xml):
        route(monkeypatch, fake_response, folder_html, infotable_xml)

        holdings = tracker.fetch_13f_holdings(META)

        # SEC Form 13F amendments (compliance date 2023-01-03) require values
        # rounded to the nearest whole dollar. Scaling by 1000 here — as this
        # code used to — overstates every figure in the digest by 1000x.
        assert holdings[0]["value"] == 1234567
        assert holdings[1]["value"] == 800000

    def test_non_numeric_value_becomes_zero_not_a_crash(
            self, monkeypatch, fake_response, folder_html):
        xml = ('<informationTable><infoTable>'
               '<nameOfIssuer>WEIRD CO</nameOfIssuer>'
               '<value>N/A</value></infoTable></informationTable>')
        route(monkeypatch, fake_response, folder_html, xml)

        holdings = tracker.fetch_13f_holdings(META)

        assert holdings[0]["value"] == 0

    def test_missing_tags_yield_empty_strings(
            self, monkeypatch, fake_response, folder_html):
        xml = ('<informationTable><infoTable>'
               '<nameOfIssuer>SPARSE CO</nameOfIssuer>'
               '</infoTable></informationTable>')
        route(monkeypatch, fake_response, folder_html, xml)

        holdings = tracker.fetch_13f_holdings(META)

        assert holdings[0] == {"name": "SPARSE CO", "cusip": "", "value": 0,
                               "shares": "", "put_call": ""}

    def test_empty_infotable_returns_empty_list(
            self, monkeypatch, fake_response, folder_html):
        route(monkeypatch, fake_response, folder_html,
              "<informationTable></informationTable>")
        assert tracker.fetch_13f_holdings(META) == []

    def test_folder_fetch_failure_returns_empty_list(self, monkeypatch):
        def boom(*a, **k):
            raise requests.ConnectionError("down")
        monkeypatch.setattr(requests, "get", boom)
        assert tracker.fetch_13f_holdings(META) == []

    def test_xml_fetch_failure_returns_empty_list(
            self, monkeypatch, fake_response, folder_html):
        def _get(url, **kwargs):
            if url.endswith("/"):
                return fake_response(text=folder_html)
            return fake_response(status=404)
        monkeypatch.setattr(requests, "get", _get)
        assert tracker.fetch_13f_holdings(META) == []

    def test_fallback_to_primary_doc_builds_a_valid_url(
            self, monkeypatch, fake_response):
        calls = []
        # A folder listing with no infotable file forces the fallback path.
        bare = '<html><body><a href="/some/other/file.txt">x</a></body></html>'

        def _get(url, **kwargs):
            calls.append(url)
            if url.endswith("/"):
                return fake_response(text=bare)
            return fake_response(text="<informationTable/>")

        monkeypatch.setattr(requests, "get", _get)
        tracker.fetch_13f_holdings(META)

        assert calls[1].startswith(
            "https://www.sec.gov/Archives/edgar/data/1067983/"), (
            f"fallback built an unreachable URL: {calls[1]}")
