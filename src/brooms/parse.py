"""Reading the site's pages. Everything that depends on the markup lives here."""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from .models import Booking, Space


class Parse:
    GRID_TIME = "%Y-%m-%d %H:%M:%S"  # availability grid JSON: "2026-10-05 14:15:00"
    CANCEL_TIME = "%I:%M%p %A, %B %d, %Y"  # cancel page: "2:15pm Monday, October 5, 2026"
    DAY = "%A, %B %d, %Y"  # confirmation: "Monday, October 5, 2026"

    @staticmethod
    def text(el: Tag | None) -> str:
        return " ".join(el.get_text(" ", strip=True).split()) if el else ""

    @staticmethod
    def grid_time(value: str) -> datetime:
        return datetime.strptime(value, Parse.GRID_TIME)

    # ---------------------------------------------------------------- spaces

    @staticmethod
    def spaces(soup: BeautifulSoup, location: str) -> list[Space]:
        """The cards of a "search by space" results page."""
        lid = int(soup.select_one("input[name=lid]")["value"])
        type_ids = {Parse.text(o).lower(): int(o["value"])
                    for o in soup.select("#s-lc-by-space-search-filters select[name=gid] option")}
        spaces = []
        for card in soup.select(".s-lc-booking-suggestion"):
            link = card.select_one(".s-lc-suggestion-heading a[href^='/space/']")
            if link is None:
                continue
            type_, _, zone = Parse.text(card.select_one(".s-lc-booking-group")).partition(" | ")
            capacity = re.search(r"\d+", Parse.text(card.select_one(".s-lc-booking-icons")) or "0")
            spaces.append(Space(
                id=int(re.search(r"/space/(\d+)", link["href"])[1]),
                name=Parse.text(link),
                type=type_,
                zone=zone,
                capacity=int(capacity[0]) if capacity else 0,
                location=location,
                type_id=type_ids.get(type_.lower(), 0),
                location_id=lid,
            ))
        return spaces

    # ----------------------------------------------------------------- login

    @staticmethod
    def is_login(soup: BeautifulSoup) -> bool:
        """Bath's single sign-on form."""
        return soup.select_one("form input[name=password]") is not None

    @staticmethod
    def login_error(soup: BeautifulSoup) -> str:
        return Parse.text(soup.select_one("#msg"))

    # -------------------------------------------------------------- checkout

    @staticmethod
    def cart(soup: BeautifulSoup) -> list[int]:
        """The space ids in the checkout page's cart."""
        return [int(b["data-eid"]) for b in soup.select(".s-lc-eq-remove-single[data-eid]")]

    @staticmethod
    def checkout_fields(soup: BeautifulSoup) -> set[str]:
        """The names of the checkout form's fields."""
        form = soup.select_one("#s-lc-eq-bform")
        if form is None:
            return set()
        return {i["name"] for i in form.select("input[name], select[name], textarea[name]")}

    @staticmethod
    def confirmation(soup: BeautifulSoup) -> Booking | None:
        """The booking on the "Booking Confirmed" page, or None if it isn't one."""
        if "Booking Confirmed" not in Parse.text(soup.select_one(".s-lc-eq-success-title")):
            return None
        fields = {Parse.text(dt).rstrip(":"): Parse.text(dt.find_next_sibling("dd"))
                  for dt in soup.select(".s-lc-eq-success-resource dt")}
        day = datetime.strptime(fields["Date"], Parse.DAY).date()
        start, end = (datetime.combine(day, datetime.strptime(t.strip(), "%I:%M%p").time())
                      for t in fields["Time"].split("-"))
        return Booking(space=fields["Space"], start=start, end=end)

    # ---------------------------------------------------------------- cancel

    @staticmethod
    def cancel_rows(soup: BeautifulSoup) -> list[tuple[int, Booking, bool]]:
        """(booking id, booking, can still be cancelled) for each row of a cancel page."""
        rows = []
        for tr in soup.select("tr[id^=booking_]"):
            cells = [Parse.text(td) for td in tr.find_all("td")]
            texts = [c for c in cells if c]
            if len(texts) < 4:
                continue
            space, _type, start, end = texts[:4]
            rows.append((int(tr["id"].removeprefix("booking_")),
                         Booking(space=space, start=datetime.strptime(start, Parse.CANCEL_TIME),
                                 end=datetime.strptime(end, Parse.CANCEL_TIME)),
                         tr.select_one(".s-lc-cancel-single[data-id]") is not None))
        return rows
