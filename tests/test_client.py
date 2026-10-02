"""The client's flows against mocked HTTP, answered with the real (scrubbed) pages."""

import json
from datetime import date, datetime
from urllib.parse import parse_qs

import pytest
import responses

from brooms import Booking, Brooms, BroomsError, LoginError, Slot
from brooms.parse import Parse

URL = "https://bath.libcal.com"
SSO = "https://auth.bath.ac.uk/login"
LIBAUTH = "https://eu.libauth.com/saml/acs"
MONDAY = date(2026, 10, 5)
BOOKED = Booking(space="Norwood House 2.17f", start=datetime(2026, 10, 5, 14, 15),
                 end=datetime(2026, 10, 5, 15, 15))
# What Bath's single sign-on and LibAuth answer with: forms the browser posts on by itself.
SAML = f'<form method="post" action="{LIBAUTH}"><input name="SAMLResponse" value="x"></form>'
LIBAUTH_BACK = f'<form method="post" action="{URL}/spaces/auth"><input name="t" value="y"></form>'


def sent(call) -> dict[str, str]:
    """The form fields of a recorded urlencoded POST."""
    return {k: v[0] for k, v in parse_qs(call.request.body, keep_blank_values=True).items()}


def calls(rsps, path: str) -> list:
    return [c for c in rsps.calls if path in c.request.url]


@pytest.fixture
def rsps():
    with responses.RequestsMock() as r:
        yield r


@pytest.fixture
def b():
    return Brooms("ab123", "secret")


def listed(rsps, pages, location="campus"):
    page = {"campus": "campus", "city": "virgil-building"}[location]
    rsps.get(f"{URL}/r/search/{page}", body=pages.text(f"spaces_{location}.html"))


def gridded(rsps, pages, grid=None):
    """The grid's first page, then the same again (as the site does past the last page)."""
    body = json.dumps(grid if grid is not None else pages.json("grid.json"))
    rsps.post(f"{URL}/spaces/availability/grid", body=body)
    rsps.post(f"{URL}/spaces/availability/grid", body=body)


# ------------------------------------------------------------------ looking


def test_spaces(rsps, pages, b):
    listed(rsps, pages)
    assert len(b.spaces()) == 47
    assert {s.type for s in b.spaces(type="Group Study Room")} == {"Group study room"}
    assert {s.zone for s in b.spaces(zone="library")} == {"Library"}
    query = parse_qs(rsps.calls[0].request.url.split("?")[1])
    assert query["m"] == ["s"]


def test_unknown_names(rsps, pages, b):
    listed(rsps, pages)
    with pytest.raises(BroomsError, match="No type 'sauna'. Known: Group study room"):
        b.spaces(type="sauna")
    with pytest.raises(BroomsError, match="No location 'moon'"):
        b.spaces("moon")


def test_city(rsps, pages, b):
    listed(rsps, pages, "city")
    assert {s.location for s in b.spaces("city")} == {"city"}


def test_availability(rsps, pages, b):
    listed(rsps, pages)
    gridded(rsps, pages)
    slots = b.availability(MONDAY)
    grid = pages.json("grid.json")["slots"]
    assert 0 < len(slots) < len(grid)  # study desks (booked as seats) are left out
    assert slots == sorted(slots, key=lambda s: (s.start, s.space.name))
    first = slots[0]
    assert first.start.date() == MONDAY and first.end > first.start
    assert {s.available for s in slots} == {True, False}
    sent_grid = sent(calls(rsps, "/grid")[0])
    assert (sent_grid["lid"], sent_grid["gid"], sent_grid["start"], sent_grid["end"]) == \
        ("3323", "0", "2026-10-05", "2026-10-06")
    assert len(calls(rsps, "/grid")) == 2  # stopped when the second page had nothing new


def test_availability_of_one_space(rsps, pages, b):
    listed(rsps, pages)
    gridded(rsps, pages)
    slots = b.availability(MONDAY, space="norwood house 2.17f")
    assert {s.space.id for s in slots} == {10614}
    assert [s.start.hour for s in slots][:3] == [8, 9, 10]


def test_availability_past_the_booking_window(rsps, pages, b):
    listed(rsps, pages)
    rsps.post(f"{URL}/spaces/availability/grid",
              json={"slots": [], "bookings": [], "isPreCreatedBooking": False, "windowEnd": True})
    assert b.availability(date(2026, 10, 30)) == []


# ------------------------------------------------------------------ booking


def norwood_slot(pages) -> Slot:
    """Norwood House 2.17f on Mon 5 Oct 14:15, the slot the booking pages are for."""
    space = next(s for s in Parse.spaces(pages.soup("spaces_campus.html"), "campus")
                 if s.name == "Norwood House 2.17f")
    return Slot(space=space, start=datetime(2026, 10, 5, 14, 15),
                end=datetime(2026, 10, 5, 15, 15), available=True, checksum="abc")


def cart(pages, name: str) -> str:
    """A cart answer moved to 14:15, the time of the booking pages (it was captured at 08:15)."""
    text = pages.text(name)
    for old, new in (("10:15", "16:15"), ("09:15", "15:15"), ("08:15", "14:15")):
        text = text.replace(old, new)
    return text


def checkout_flow(rsps, pages, *, checkout=None, login=None, update=False):
    rsps.get(f"{URL}/space/10614", body="<html></html>")
    rsps.post(f"{URL}/spaces/availability/booking/add", body=cart(pages, "cart_add.json"))
    if update:
        rsps.post(f"{URL}/spaces/availability/booking/add", body=cart(pages, "cart_update.json"))
    rsps.post(f"{URL}/ajax/space/times", body=pages.text("times.json"))
    rsps.get(f"{URL}/spaces/auth", status=302, headers={"Location": SSO + "?service=x"})
    rsps.get(SSO, body=pages.text("login.html"))
    rsps.post(SSO, body=login or SAML)
    if login is None:
        rsps.post(LIBAUTH, body=LIBAUTH_BACK)
        rsps.post(f"{URL}/spaces/auth", body=checkout or pages.text("checkout.html"))


def test_book(rsps, pages, b):
    checkout_flow(rsps, pages)
    rsps.post(f"{URL}/ajax/equipment/checkout", body=pages.text("booked.json"))
    assert b.book(norwood_slot(pages), name="revision") == BOOKED

    add = sent(calls(rsps, "/booking/add")[0])
    assert (add["add[eid]"], add["add[start]"], add["add[checksum]"]) == \
        ("10614", "2026-10-05 14:15", "abc")
    login = sent(calls(rsps, SSO)[-1])
    assert (login["username"], login["password"]) == ("ab123", "secret")
    body = calls(rsps, "/ajax/equipment/checkout")[0].request.body.decode()
    assert 'name="nick"\r\n\r\nrevision' in body
    assert 'name="session"' in body


def test_book_two_hours(rsps, pages, b):
    checkout_flow(rsps, pages, update=True)
    rsps.post(f"{URL}/ajax/equipment/checkout", body=json.dumps(
        json.loads(pages.text("booked.json")).replace("3:15pm", "4:15pm")))
    booking = b.book(norwood_slot(pages), hours=2)
    assert booking.end == datetime(2026, 10, 5, 16, 15)
    update = sent(calls(rsps, "/booking/add")[1])
    assert update["update[end]"] == "2026-10-05 16:15:00"
    assert update["bookings[0][start]"] == "2026-10-05 14:15"


def test_book_too_long(rsps, pages, b):
    rsps.get(f"{URL}/space/10614", body="<html></html>")
    rsps.post(f"{URL}/spaces/availability/booking/add", body=cart(pages, "cart_add.json"))
    with pytest.raises(BroomsError, match="at most 2 hour"):
        b.book(norwood_slot(pages), hours=3)


def test_book_wrong_password(rsps, pages, b):
    checkout_flow(rsps, pages, login=pages.text("login_failed.html"))
    with pytest.raises(LoginError, match="Invalid credentials."):
        b.book(norwood_slot(pages))
    assert not calls(rsps, "/ajax/equipment/checkout")


def test_book_refusal(rsps, pages, b):
    rsps.get(f"{URL}/space/10614", body="<html></html>")
    rsps.post(f"{URL}/spaces/availability/booking/add",
              json={"error": "Sorry, the selected times have become unavailable."})
    with pytest.raises(BroomsError, match="become unavailable"):
        b.book(norwood_slot(pages))


def test_book_refuses_paid(rsps, pages, b):
    rsps.get(f"{URL}/space/10614", body="<html></html>")
    rsps.post(f"{URL}/spaces/availability/booking/add",
              body=cart(pages, "cart_add.json").replace('"cost": 0', '"cost": 5'))
    with pytest.raises(BroomsError, match="Paid bookings aren't supported"):
        b.book(norwood_slot(pages))
    assert not calls(rsps, "/ajax/space/times")


def test_book_refuses_unknown_checkout_questions(rsps, pages, b):
    page = pages.text("checkout.html").replace(
        'name="nick"', 'name="nick"/><input name="q1234" required')
    checkout_flow(rsps, pages, checkout=page)
    with pytest.raises(BroomsError, match="asks for q1234"):
        b.book(norwood_slot(pages))
    assert not calls(rsps, "/ajax/equipment/checkout")


def test_book_refuses_a_cart_with_something_else(rsps, pages, b):
    checkout_flow(rsps, pages, checkout=pages.text("checkout.html").replace(
        'data-eid="10614"', 'data-eid="99999"'))
    with pytest.raises(BroomsError, match="Nothing was booked"):
        b.book(norwood_slot(pages))
    assert not calls(rsps, "/ajax/equipment/checkout")


def test_book_needs_a_login(rsps, pages):
    with pytest.raises(LoginError, match="username and password"):
        Brooms().book(norwood_slot(pages))


def test_book_unavailable(rsps, pages, b):
    slot = norwood_slot(pages)
    slot.available = False
    with pytest.raises(BroomsError, match="isn't available"):
        b.book(slot)


# ------------------------------------------------------------------ cancelling


def test_cancel(rsps, pages, b):
    rsps.get(f"{URL}/equipment/cancel", body=pages.text("cancel.html"))
    rsps.post(f"{URL}/ajax/equipment/cancel/0123456789ab/40000001",
              json={"success": True, "moreRemaining": False, "refundAmount": 0})
    assert b.cancel(f"{URL}/equipment/cancel?id=0123456789ab") == [BOOKED]
    assert rsps.calls[0].request.url.endswith("?id=0123456789ab")


def test_cancel_takes_just_the_code(rsps, pages):
    rsps.get(f"{URL}/equipment/cancel", body=pages.text("cancel.html"))
    rsps.post(f"{URL}/ajax/equipment/cancel/0123456789ab/40000001", json={"success": True})
    assert Brooms().cancel("0123456789ab") == [BOOKED]  # no login needed


def test_cancel_already_cancelled(rsps, pages, b):
    rsps.get(f"{URL}/equipment/cancel", body=pages.text("cancel_done.html"))
    with pytest.raises(BroomsError, match="already cancelled"):
        b.cancel("0123456789ab")


def test_cancel_refused(rsps, pages, b):
    rsps.get(f"{URL}/equipment/cancel", body=pages.text("cancel.html"))
    rsps.post(f"{URL}/ajax/equipment/cancel/0123456789ab/40000001",
              json={"success": False, "error": "Too late to cancel."})
    with pytest.raises(BroomsError, match="Too late to cancel."):
        b.cancel("0123456789ab")
