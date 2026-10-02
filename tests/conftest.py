import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

FIXTURES = Path(__file__).parent / "fixtures"


class Fixtures:
    """Real pages from the site, scrubbed (see capture_fixtures.py). Captured on Fri 2 Oct
    2026; the grid and cart are for Mon 5 Oct, and the booking pages are for Norwood House
    2.17f on Mon 5 Oct, 14:15-15:15."""

    @staticmethod
    def text(name: str) -> str:
        return (FIXTURES / name).read_text()

    @staticmethod
    def json(name: str):
        return json.loads(Fixtures.text(name))

    @staticmethod
    def soup(name: str) -> BeautifulSoup:
        return BeautifulSoup(Fixtures.text(name), "html.parser")


@pytest.fixture
def pages():
    return Fixtures
