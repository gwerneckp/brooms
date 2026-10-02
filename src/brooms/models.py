"""What the library returns: plain dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Space:
    """A bookable room, table or booth, e.g. "Norwood House 2.17f"."""

    id: int  # the site's item id, as in bath.libcal.com/space/<id>
    name: str
    type: str  # e.g. "Group study room", "Group study table", "Individual meeting booth"
    zone: str  # e.g. "Library", "Norwood House Study Spaces", "Virgil Building"
    capacity: int  # people
    location: str  # "campus" | "city"
    type_id: int = field(repr=False)  # the site's category id
    location_id: int = field(repr=False)  # the site's location id


@dataclass
class Slot:
    """One bookable hour of one space."""

    space: Space
    start: datetime
    end: datetime
    available: bool
    checksum: str = field(default="", repr=False)  # the site's token for booking this slot


@dataclass
class Booking:
    """A booking you made (from book()) or cancelled (from cancel())."""

    space: str  # the space's name, e.g. "Norwood House 2.17f"
    start: datetime
    end: datetime
