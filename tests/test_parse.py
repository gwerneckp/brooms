"""The parsers against real (scrubbed) pages."""

import json
from collections import Counter
from datetime import datetime

from bs4 import BeautifulSoup

from brooms import Booking, Space
from brooms.parse import Parse

BOOKED = Booking(space="Norwood House 2.17f", start=datetime(2026, 10, 5, 14, 15),
                 end=datetime(2026, 10, 5, 15, 15))


def test_campus_spaces(pages):
    spaces = Parse.spaces(pages.soup("spaces_campus.html"), "campus")
    assert len(spaces) == 47
    assert spaces[0] == Space(id=18581, name="1 West 2.103 Table 1", type="Group study table",
                              zone="1 West", capacity=6, location="campus", type_id=7473,
                              location_id=3323)
    assert Counter(s.type for s in spaces) == {"Group study table": 27, "Group study room": 9,
                                               "Individual meeting booth": 7,
                                               "Individual study room": 4}
    norwood = next(s for s in spaces if s.name == "Norwood House 2.17f")
    assert (norwood.id, norwood.type_id, norwood.zone, norwood.capacity) == \
        (10614, 7472, "Norwood House Study Spaces", 6)


def test_city_spaces(pages):
    spaces = Parse.spaces(pages.soup("spaces_city.html"), "city")
    assert len(spaces) == 26
    assert {s.zone for s in spaces} == {"Virgil Building"}
    assert {s.location_id for s in spaces} == {1642}
    assert all(s.type_id for s in spaces)


def test_login_pages(pages):
    assert Parse.is_login(pages.soup("login.html"))
    assert Parse.login_error(pages.soup("login.html")) == ""
    assert Parse.login_error(pages.soup("login_failed.html")) == "Invalid credentials."
    assert not Parse.is_login(pages.soup("checkout.html"))


def test_checkout_page(pages):
    soup = pages.soup("checkout.html")
    assert Parse.cart(soup) == [10614]
    assert Parse.checkout_fields(soup) == {"session", "nick"}


def test_confirmation(pages):
    assert Parse.confirmation(BeautifulSoup(json.loads(pages.text("booked.json")),
                                            "html.parser")) == BOOKED
    assert Parse.confirmation(pages.soup("checkout.html")) is None


def test_cancel_pages(pages):
    assert Parse.cancel_rows(pages.soup("cancel.html")) == [(40000001, BOOKED, True)]
    assert Parse.cancel_rows(pages.soup("cancel_done.html")) == [(40000001, BOOKED, False)]
