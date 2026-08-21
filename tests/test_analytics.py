"""Tests for the pure analytics and formatting functions."""
import pytest

import tracker


def h(name, value, put_call=""):
    """Build a holding dict the way fetch_13f_holdings does."""
    return {"name": name, "cusip": "0" * 9, "value": value,
            "shares": "100", "put_call": put_call}


class TestFmtUsd:
    @pytest.mark.parametrize("val,expected", [
        (2_500_000_000_000, "$2.50T"),
        (1_000_000_000_000, "$1.00T"),
        (3_400_000_000, "$3.4B"),
        (1_000_000_000, "$1.0B"),
        (7_600_000, "$7.6M"),
        (1_000_000, "$1.0M"),
        (999_999, "$999,999"),
        (0, "$0"),
    ])
    def test_scales_at_each_boundary(self, val, expected):
        assert tracker.fmt_usd(val) == expected


class TestSummariseManager:
    def test_empty_holdings_returns_empty_dict(self):
        assert tracker.summarise_manager("Nobody", []) == {}

    def test_totals_and_concentration(self):
        holdings = [h(f"S{i}", 10) for i in range(20)]
        out = tracker.summarise_manager("Test Capital", holdings)
        assert out["total"] == 200
        assert out["count"] == 20
        # top 10 of 20 equal positions = exactly half the book
        assert out["top10_pct"] == 50.0
        assert len(out["top5"]) == 5

    def test_top5_is_sorted_by_value_descending(self):
        holdings = [h("SMALL", 1), h("BIG", 100), h("MID", 50)]
        out = tracker.summarise_manager("Test", holdings)
        assert [x["name"] for x in out["top5"]] == ["BIG", "MID", "SMALL"]

    def test_single_holding_is_full_concentration(self):
        out = tracker.summarise_manager("Solo", [h("ONLY", 42)])
        assert out["top10_pct"] == 100.0
        assert out["total"] == 42

    def test_zero_value_book_does_not_divide_by_zero(self):
        out = tracker.summarise_manager("Zeroes", [h("A", 0), h("B", 0)])
        assert out["total"] == 0
        assert out["top10_pct"] == 0


class TestConsensusStocks:
    def test_counts_each_manager_once_per_stock(self):
        managers = [
            {"name": "A", "all_holdings": [h("APPLE INC", 10), h("APPLE INC", 5)]},
            {"name": "B", "all_holdings": [h("APPLE INC", 20)]},
        ]
        out = tracker.consensus_stocks(managers)
        apple = next(x for x in out if x["stock"] == "APPLE INC")
        # A holds two Apple lines but must only be counted as one manager
        assert apple["managers"] == ["A", "B"]
        # ...and only the first line's value is accumulated for A
        assert apple["total_value"] == 30

    def test_normalises_name_case_and_whitespace(self):
        managers = [
            {"name": "A", "all_holdings": [h("apple inc", 10)]},
            {"name": "B", "all_holdings": [h("  APPLE INC  ", 20)]},
        ]
        out = tracker.consensus_stocks(managers)
        assert len(out) == 1
        assert out[0]["stock"] == "APPLE INC"
        assert len(out[0]["managers"]) == 2

    def test_ranked_by_manager_count_and_capped_at_15(self):
        managers = [
            {"name": f"M{i}", "all_holdings": [h(f"STOCK{j}", 1)
                                               for j in range(20 - i)]}
            for i in range(5)
        ]
        out = tracker.consensus_stocks(managers)
        assert len(out) == 15
        counts = [len(x["managers"]) for x in out]
        assert counts == sorted(counts, reverse=True)

    def test_skips_blank_names(self):
        managers = [{"name": "A", "all_holdings": [h("", 10), h("REAL", 5)]}]
        out = tracker.consensus_stocks(managers)
        assert [x["stock"] for x in out] == ["REAL"]


class TestMegaPositions:
    def test_returns_ten_largest_across_all_managers(self):
        managers = [
            {"name": "A", "all_holdings": [h(f"S{i}", i) for i in range(10)]},
            {"name": "B", "all_holdings": [h(f"T{i}", i * 100) for i in range(10)]},
        ]
        out = tracker.mega_positions(managers)
        assert len(out) == 10
        assert out[0]["manager"] == "B"
        assert out[0]["value"] == 900
        assert [x["value"] for x in out] == sorted(
            [x["value"] for x in out], reverse=True)

    def test_carries_put_call_flag(self):
        managers = [{"name": "A", "all_holdings": [h("PUTS", 999, "Put")]}]
        assert tracker.mega_positions(managers)[0]["put_call"] == "Put"

    def test_handles_fewer_than_ten_positions(self):
        managers = [{"name": "A", "all_holdings": [h("ONLY", 1)]}]
        assert len(tracker.mega_positions(managers)) == 1
