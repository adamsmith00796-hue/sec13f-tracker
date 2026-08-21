"""Shared fixtures and a hard no-network guard for the test suite."""
import json
import sys
from pathlib import Path

import pytest

# Make tracker.py importable without installing the project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture
def submissions_json() -> dict:
    return json.loads(load("submissions_berkshire.json"))


@pytest.fixture
def folder_html() -> str:
    return load("folder_listing.html")


@pytest.fixture
def infotable_xml() -> str:
    return load("infotable_namespaced.xml")


@pytest.fixture
def infotable_prefixed_xml() -> str:
    return load("infotable_prefixed.xml")


class UnmockedNetworkCall(BaseException):
    """Raised when a test reaches for the real network.

    Deliberately a BaseException, not an Exception. tracker.py wraps its
    fetches in broad ``except Exception`` handlers that degrade to an empty
    result — which would swallow this guard and let a test with a forgotten
    mock pass silently against live SEC data. BaseException escapes those
    handlers and fails the test.
    """


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if a test reaches for the real network.

    Every outbound call must be mocked. A test that quietly hits SEC EDGAR or
    Yahoo is slow, flaky, and rate-limited in CI — and stops being a test.
    """
    import requests

    def blocked(*args, **kwargs):
        raise UnmockedNetworkCall(
            f"Unmocked network call to {args[0] if args else '?'} — "
            "mock it in the test."
        )

    monkeypatch.setattr(requests, "get", blocked)
    monkeypatch.setattr(requests, "post", blocked)


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, text="", json_data=None, status=200):
        self.text = text
        self._json = json_data
        self.status_code = status

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code}")


@pytest.fixture
def fake_response():
    return FakeResponse
