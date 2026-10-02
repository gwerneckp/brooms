"""University of Bath study-space bookings (bath.libcal.com, a Springshare LibCal site).

There's no public API: we use the same requests the site's pages make. Looking needs no
login. Booking puts the slot in a cart, logs in through LibAuth and Bath's single sign-on
with your username and password like a browser would, and submits the checkout form.
Each public method starts from scratch, so calls never depend on each other.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import Booking, Slot, Space
from .parse import Parse

USER_AGENT = "Mozilla/5.0 (compatible; brooms)"


class BroomsError(Exception):
    """The site didn't do what we expected, or refused (e.g. a booking limit)."""


class LoginError(BroomsError):
    """Wrong username or password, or no login given."""


class Brooms:
    """University of Bath study-space bookings.

    >>> b = Brooms("ab123", "password")             # your Bath login, only used to book
    >>> free = [s for s in b.availability(date(2026, 10, 5), type="group study room")
    ...         if s.available]
    >>> b.book(free[0])

    Looking (spaces, availability) works without a login. Cancelling needs the cancel link
    from the confirmation email, which is the only handle the site gives on a booking.
    """

    URL = "https://bath.libcal.com"
    LOCATIONS = {"campus": "campus", "city": "virgil-building"}  # name -> /r/search/<page>
    MAX_PAGES = 20  # of the availability grid; one is plenty at Bath

    def __init__(self, username: str | None = None, password: str | None = None, *,
                 timeout: float = 30):
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def __repr__(self) -> str:
        return f"Brooms({self.username!r})"

    # ------------------------------------------------------------- low level

    def request(self, method: str, url: str, **kw) -> requests.Response:
        r = self.session.request(method, urljoin(self.URL, url), timeout=self.timeout, **kw)
        if r.status_code >= 400:
            raise BroomsError(f"{method} {urlparse(r.url).path}: HTTP {r.status_code} "
                              f"{r.text[:200].strip()}")
        return r

    def ajax(self, path: str, data: dict | None = None, referer: str = "/spaces", **kw
             ) -> requests.Response:
        """POST like the site's JavaScript does. It checks the Referer."""
        headers = {"X-Requested-With": "XMLHttpRequest", "Referer": urljoin(self.URL, referer),
                   "Origin": self.URL}
        return self.request("POST", path, data=data, headers=headers, **kw)

    # ------------------------------------------------------------ high level

    def spaces(self, location: str = "campus", *, type: str | None = None,
               zone: str | None = None) -> list[Space]:
        """Every bookable room, table and booth at a location ("campus" or "city"),
        optionally only one type (e.g. "group study room") or zone (e.g. "library")."""
        page = self.LOCATIONS.get(location)
        if page is None:
            raise BroomsError(f"No location {location!r}. Known: {', '.join(self.LOCATIONS)}")
        r = self.request("GET", f"/r/search/{page}",
                         params={"m": "s", "search": "", "gid": 0, "capacity": 0, "zone": 0})
        spaces = Parse.spaces(BeautifulSoup(r.text, "html.parser"), location)
        return [s for s in spaces if self.matches(s.type, type, spaces, "type")
                and self.matches(s.zone, zone, spaces, "zone")]

    def availability(self, day: date | None = None, *, type: str | None = None,
                     zone: str | None = None, space: Space | int | str | None = None,
                     location: str = "campus") -> list[Slot]:
        """Every slot on `day` (default today) of every space at a location, optionally only
        one type, zone or space (a Space, its id or its name), sorted by time then space.

        Bookings open 7 days ahead; further out there are no slots.
        """
        day = day or date.today()
        spaces = {s.id: s for s in self.spaces(location, type=type, zone=zone)}
        if space is not None:
            wanted = self.find_space(space, list(spaces.values()))
            spaces = {wanted.id: wanted}
        if not spaces:
            return []
        lid = next(iter(spaces.values())).location_id
        slots, seen = [], set()
        for index in range(self.MAX_PAGES):
            grid = self.ajax("/spaces/availability/grid", {
                "lid": lid, "gid": 0, "eid": -1, "seat": 0, "seatId": 0, "zone": 0,
                "start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat(),
                "pageIndex": index, "pageSize": 100,
            }).json()
            items = {x["itemId"] for x in grid["slots"]}
            if not items - seen:
                break
            seen |= items
            # Ids not in spaces() are study desks (booked as seats, not supported) or filtered out.
            slots += [Slot(space=spaces[x["itemId"]], start=Parse.grid_time(x["start"]),
                           end=Parse.grid_time(x["end"]), available=not x.get("className"),
                           checksum=x.get("checksum", ""))
                      for x in grid["slots"] if x["itemId"] in spaces]
        return sorted(slots, key=lambda s: (s.start, s.space.name))

    def book(self, slot: Slot, hours: int = 1, name: str = "") -> Booking:
        """Book a free slot from availability(), for `hours` from its start (1 or 2 at Bath).

        Logs in with the username and password. `name` is what the site shows for the
        booking (optional). The site emails a confirmation with the cancel link to your
        university address. Anything that costs money, or a checkout that asks for more
        than a name, is refused before booking; the site's own refusals (booking limits...)
        raise BroomsError with its message.
        """
        if not (self.username and self.password):
            raise LoginError("Booking needs your Bath username and password: "
                             "Brooms(username, password).")
        if not slot.available:
            raise BroomsError(f"{self.describe(slot)} isn't available.")
        self.clear_cart()
        sp, referer = slot.space, f"/space/{slot.space.id}"
        self.request("GET", referer)  # starts the site's session, as a browser would
        window = {"lid": sp.location_id, "gid": sp.type_id, "start": slot.start.date().isoformat(),
                  "end": (slot.start.date() + timedelta(days=1)).isoformat()}
        added = self.cart_update({"add[eid]": sp.id, "add[gid]": sp.type_id,
                                  "add[lid]": sp.location_id,
                                  "add[start]": f"{slot.start:%Y-%m-%d %H:%M}",
                                  "add[checksum]": slot.checksum, **window}, [], referer, slot)
        end = slot.start + timedelta(hours=hours)
        if Parse.grid_time(added["end"]) != end:
            options = [Parse.grid_time(o) for o in added["options"]]
            if end not in options:
                longest = (max(options) - slot.start) if options else timedelta(hours=1)
                raise BroomsError(f"{self.describe(slot)} can be booked for at most "
                                  f"{longest.seconds // 3600} hour(s) from then.")
            i = options.index(end)
            added = self.cart_update({"update[id]": added["id"],
                                      "update[checksum]": added["optionChecksums"][i],
                                      "update[end]": added["options"][i], **window},
                                     [added], referer, slot)
            if Parse.grid_time(added["end"]) != end:
                raise BroomsError(f"{self.describe(slot)}: couldn't extend it to {end:%H:%M}.")
        if added.get("cost"):
            raise BroomsError(f"{self.describe(slot)} costs {added['cost']}. "
                              "Paid bookings aren't supported.")
        times = self.ajax("/ajax/space/times", {
            "patron": "", "patronHash": "", "returnUrl": referer, "method": 12,
            **self.cart_payload([added]),
        }, referer=referer).json()
        if not times.get("redirect"):
            raise BroomsError(f"{self.describe(slot)}: no checkout page ({times}).")
        checkout = self.log_in(self.request("GET", times["redirect"]))
        soup = BeautifulSoup(checkout.text, "html.parser")
        if Parse.cart(soup) != [sp.id]:
            raise BroomsError(f"The checkout cart holds {Parse.cart(soup)}, not just {sp.name}. "
                              "Nothing was booked.")
        unknown = Parse.checkout_fields(soup) - {"session", "nick"}
        if unknown:
            raise BroomsError(f"The checkout asks for {', '.join(sorted(unknown))}, which brooms "
                              "doesn't know how to fill in. Nothing was booked.")
        session = soup.select_one("#s-lc-eq-bform input[name=session]")["value"]
        fields = {"session": session, "nick": name, "returnUrl": referer, "logoutUrl": "logout"}
        r = self.ajax("/ajax/equipment/checkout", referer=checkout.url,
                      files={k: (None, str(v)) for k, v in fields.items()})
        html = json.loads(r.text)
        booking = Parse.confirmation(BeautifulSoup(html, "html.parser")) \
            if isinstance(html, str) else None
        if booking is None:
            raise BroomsError(f"{self.describe(slot)}: no booking confirmation ({r.text[:200]}).")
        if (booking.space, booking.start, booking.end) != (sp.name, slot.start, end):
            raise BroomsError(f"Booked {booking}, which isn't what was asked for: "
                              f"{self.describe(slot)} until {end:%H:%M}. Cancel it from the email.")
        return booking

    def cancel(self, link: str) -> list[Booking]:
        """Cancel the bookings behind a cancel link from a confirmation email
        (https://bath.libcal.com/equipment/cancel?id=..., or just its id). No login needed.
        Returns what was cancelled."""
        code = parse_qs(urlparse(link).query).get("id", [link])[0].strip()
        page = f"/equipment/cancel?id={code}"
        rows = Parse.cancel_rows(BeautifulSoup(self.request("GET", page).text, "html.parser"))
        if not rows:
            raise BroomsError(f"No bookings behind cancel link {code!r}.")
        todo = [(i, b) for i, b, cancellable in rows if cancellable]
        if not todo:
            raise BroomsError("Those bookings are already cancelled (or over).")
        for booking_id, booking in todo:
            result = self.ajax(f"/ajax/equipment/cancel/{code}/{booking_id}", referer=page).json()
            if not result.get("success"):
                raise BroomsError(f"Couldn't cancel {booking.space} at "
                                  f"{booking.start:%a %d %b %H:%M}: {result.get('error', result)}")
        return [b for _, b in todo]

    # --------------------------------------------------------------- helpers

    def log_in(self, r: requests.Response) -> requests.Response:
        """Follow the checkout's login redirects (LibAuth, Bath single sign-on, SAML) back to
        the site, entering the username and password if asked."""
        tried = False
        for _ in range(10):
            soup = BeautifulSoup(r.text, "html.parser")
            if r.url.startswith(self.URL) and soup.select_one("#s-lc-eq-bform"):
                return r
            form = soup.find("form")
            if form is None:
                raise BroomsError(f"Lost on the way to the checkout, at {r.url.split('?')[0]}.")
            data = {i["name"]: i.get("value", "") for i in form.find_all("input") if i.get("name")}
            if Parse.is_login(soup):
                if tried:
                    raise LoginError(Parse.login_error(soup) or "Login failed.")
                data.update(username=self.username, password=self.password)
                tried = True
            elif r.url.startswith(self.URL):
                raise BroomsError(f"Unexpected page on the way to the checkout: {r.url}")
            r = self.request(form.get("method", "get").upper(),
                             urljoin(r.url, form.get("action") or r.url), data=data)
        raise BroomsError("Too many redirects on the way to the checkout.")

    def cart_update(self, data: dict, cart: list[dict], referer: str, slot: Slot) -> dict:
        """Add a slot to the cart or change its end time; returns the cart's booking."""
        result = self.ajax("/spaces/availability/booking/add",
                           {**data, **self.cart_payload(cart)}, referer=referer).json()
        if result.get("error"):
            raise BroomsError(f"{self.describe(slot)}: {result['error']}")
        if result.get("limitIssues"):
            raise BroomsError(f"{self.describe(slot)}: over a booking limit "
                              f"({result['limitIssues']}).")
        if len(result.get("bookings") or []) != 1:
            raise BroomsError(f"{self.describe(slot)}: the cart didn't take it.")
        return result["bookings"][0]

    def clear_cart(self) -> None:
        """Forget the site's cookies (and so any cart) but keep the single sign-on login."""
        for cookie in list(self.session.cookies):
            if "libcal" in cookie.domain:
                self.session.cookies.clear(cookie.domain, cookie.path, cookie.name)

    @staticmethod
    def cart_payload(cart: list[dict]) -> dict:
        payload = {}
        for n, b in enumerate(cart):
            for k in ("id", "eid", "seat_id", "gid", "lid", "checksum"):
                payload[f"bookings[{n}][{k}]"] = b[k]
            payload[f"bookings[{n}][start]"] = b["start"][:16]
            payload[f"bookings[{n}][end]"] = b["end"][:16]
        return payload

    @staticmethod
    def find_space(space: Space | int | str, spaces: list[Space]) -> Space:
        if isinstance(space, Space):
            return space
        for s in spaces:
            if space in (s.id, str(s.id)) or str(space).strip().lower() == s.name.lower():
                return s
        raise BroomsError(f"No space {space!r} among the {len(spaces)} listed.")

    @staticmethod
    def matches(value: str, wanted: str | None, spaces: list[Space], what: str) -> bool:
        """Whether a space's type or zone is `wanted` (case-insensitive). Raises for a name
        no space has, listing the known ones."""
        if wanted is None:
            return True
        known = sorted({getattr(s, what) for s in spaces})
        if wanted.strip().lower() not in (k.lower() for k in known):
            raise BroomsError(f"No {what} {wanted!r}. Known: {', '.join(known)}")
        return value.lower() == wanted.strip().lower()

    @staticmethod
    def describe(slot: Slot) -> str:
        return f"{slot.space.name} at {slot.start:%a %d %b %H:%M}"
