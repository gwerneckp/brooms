"""Against the real site, read-only. Run with:

    uv run pytest -m live

These check the site still looks the way the parsers expect, whatever is on today. They
need no account, and never book or cancel anything.
"""

from datetime import date, timedelta

import pytest

from brooms import Brooms

pytestmark = pytest.mark.live
SOON = date.today() + timedelta(days=2)


@pytest.fixture(scope="module")
def b():
    return Brooms()


@pytest.mark.parametrize("location", ["campus", "city"])
def test_spaces(b, location):
    spaces = b.spaces(location)
    assert len(spaces) > 10
    assert all(s.id and s.name and s.type and s.zone and s.type_id for s in spaces)


def test_availability(b):
    slots = b.availability(SOON, type="group study room")
    assert slots and {s.space.type for s in slots} == {"Group study room"}
    assert all(s.start.date() == SOON and s.end > s.start for s in slots)
    assert all(s.checksum for s in slots if s.available)


def test_nothing_past_the_booking_window(b):
    assert b.availability(date.today() + timedelta(days=30)) == []
