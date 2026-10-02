"""Refresh tests/fixtures/ from the real site.

    uv run python tests/capture_fixtures.py

Run it when the site changes, then update the expectations in the tests. It needs no
account: everything it captures is public. It puts one slot in a cart (held for a few
minutes, never booked), and tries one login with a made-up username to capture the
"Invalid credentials" page. Scripts and styles are dropped to keep the files small.

It never books. The booking pages (checkout.html, booked.json, cancel.html,
cancel_done.html) were captured once, on 2 Oct 2026, by booking a free group study room
and cancelling it straight away, and scrubbed with Capture.scrub: your name, email and
username become fake ones, and the cancel code and booking id are replaced.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

from brooms import Brooms

OUT = Path(__file__).parent / "fixtures"
FAKE_NAME, FAKE_EMAIL, FAKE_USER = "Alex Example", "ab123@bath.ac.uk", "ab123"
FAKE_CODE, FAKE_BOOKING = "0123456789ab", "40000001"


class Capture:
    def __init__(self):
        self.b = Brooms()

    @staticmethod
    def html(text: str) -> str:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return str(soup)

    @staticmethod
    def scrub(text: str, pairs: list[tuple[str, str]]) -> str:
        for real, fake in sorted(pairs, key=lambda p: -len(p[0])):  # full name before parts
            text = text.replace(real, fake)
        return text

    def save(self, name: str, text: str) -> None:
        (OUT / name).write_text(text)
        print("saved", name)

    def public(self) -> None:
        day = date.today() + timedelta(days=3)
        for location, page in Brooms.LOCATIONS.items():
            r = self.b.request("GET", f"/r/search/{page}",
                               params={"m": "s", "search": "", "gid": 0, "capacity": 0, "zone": 0})
            self.save(f"spaces_{location}.html", self.html(r.text))
        space = next(s for s in self.b.spaces() if s.name == "Norwood House 2.17f")
        grid = self.b.ajax("/spaces/availability/grid", {
            "lid": space.location_id, "gid": 0, "eid": -1, "seat": 0, "seatId": 0, "zone": 0,
            "start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat(),
            "pageIndex": 0, "pageSize": 100}).json()
        self.save("grid.json", json.dumps(grid, indent=1))
        self.cart(space, day, grid)
        r = self.b.request("GET", "https://auth.bath.ac.uk/login")
        self.save("login.html", self.html(r.text))
        form = BeautifulSoup(r.text, "html.parser").find("form")
        data = {i["name"]: i.get("value", "") for i in form.find_all("input") if i.get("name")}
        data.update(username="brooms-fixture-capture", password="not-a-real-password")
        r = self.b.request("POST", r.url, data=data)
        self.save("login_failed.html", self.html(r.text))

    def cart(self, space, day, grid) -> None:
        """The cart steps of book(), up to the login redirect. Holds a slot, books nothing."""
        slot = next(x for x in grid["slots"] if x["itemId"] == space.id and not x.get("className"))
        referer = f"/space/{space.id}"
        self.b.request("GET", referer)
        window = {"lid": space.location_id, "gid": space.type_id, "start": day.isoformat(),
                  "end": (day + timedelta(days=1)).isoformat()}
        added = self.b.ajax("/spaces/availability/booking/add", {
            "add[eid]": space.id, "add[gid]": space.type_id, "add[lid]": space.location_id,
            "add[start]": slot["start"][:16], "add[checksum]": slot["checksum"], **window},
            referer=referer).json()
        self.save("cart_add.json", json.dumps(added | {"gridUpdateData": None}, indent=1))
        b = added["bookings"][0]
        updated = self.b.ajax("/spaces/availability/booking/add", {
            "update[id]": b["id"], "update[checksum]": b["optionChecksums"][-1],
            "update[end]": b["options"][-1], **window, **Brooms.cart_payload([b])},
            referer=referer).json()
        self.save("cart_update.json", json.dumps(updated | {"gridUpdateData": None}, indent=1))
        times = self.b.ajax("/ajax/space/times", {
            "patron": "", "patronHash": "", "returnUrl": referer, "method": 12,
            **Brooms.cart_payload(updated["bookings"])}, referer=referer).json()
        self.save("times.json", json.dumps(times, indent=1))

    def booking_pages(self, folder: Path, name: str, email: str, user: str, code: str,
                      booking_id: str) -> None:
        """Scrub pages saved from a real booking: checkout.html, booked.json (the checkout's
        JSON answer), cancel.html and cancel_done.html (the cancel page before and after)."""
        first, *rest = name.split()
        pairs = [(name, FAKE_NAME), (email, FAKE_EMAIL), (user, FAKE_USER), (code, FAKE_CODE),
                 (booking_id, FAKE_BOOKING), (first, FAKE_NAME.split()[0])]
        pairs += [(part, FAKE_NAME.split()[1]) for part in rest]
        for file in ("checkout.html", "cancel.html", "cancel_done.html"):
            text = self.scrub(self.html((folder / file).read_text()), pairs)
            self.check(file, text, [name, email, user, *name.split()])
            self.save(file, text)
        booked = self.scrub(self.html(json.loads((folder / "booked.json").read_text())), pairs)
        self.check("booked.json", booked, [name, email, user, *name.split()])
        self.save("booked.json", json.dumps(booked))

    @staticmethod
    def check(file: str, text: str, personal: list[str]) -> None:
        left = [p for p in personal if p and p.lower() in text.lower()]
        if left:
            raise SystemExit(f"{file} still contains personal details ({len(left)}); not saved.")


if __name__ == "__main__":
    # Scrubbing pages from a real booking (see the docstring):
    #   NAME=... EMAIL=... USERNAME=... CODE=... BOOKING_ID=... \
    #       uv run python tests/capture_fixtures.py --booking-pages <folder>
    OUT.mkdir(exist_ok=True)
    capture = Capture()
    if sys.argv[1:2] == ["--booking-pages"]:
        env = os.environ
        capture.booking_pages(Path(sys.argv[2]), env["NAME"], env["EMAIL"], env["USERNAME"],
                              env["CODE"], env["BOOKING_ID"])
    else:
        capture.public()
