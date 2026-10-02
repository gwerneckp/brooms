"""Book the smallest free group study room from a time (default: tomorrow 14:00, 1 hour).

    BATH_USERNAME=... BATH_PASSWORD=... uv run python examples/book_room.py
    ... book_room.py --date 2026-10-05 --at 10:00 --hours 2 --zone library --people 6 --dry-run

The confirmation email, with the link to cancel, goes to your university address.
"""

import argparse
import os
from datetime import date, datetime, timedelta

from brooms import Brooms, BroomsError

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--date", type=date.fromisoformat, default=date.today() + timedelta(days=1))
parser.add_argument("--at", default="14:00", help="start time, HH:MM")
parser.add_argument("--hours", type=int, default=1, choices=[1, 2])
parser.add_argument("--zone", help='e.g. "library", "8 west"')
parser.add_argument("--people", type=int, default=1, help="smallest room size")
parser.add_argument("--dry-run", action="store_true", help="show what it would book")
args = parser.parse_args()

b = Brooms(os.environ.get("BATH_USERNAME"), os.environ.get("BATH_PASSWORD"))
at = datetime.combine(args.date, datetime.strptime(args.at, "%H:%M").time())
slots = b.availability(args.date, type="group study room", zone=args.zone)
# The first slot starting from then (Bath's slots start at quarter past, e.g. 14:15).
free = {(s.space.id, s.start): s for s in slots if s.available}
candidates = [s for s in free.values() if at <= s.start < at + timedelta(hours=1)
              and s.space.capacity >= args.people
              and all((s.space.id, s.start + timedelta(hours=h)) in free
                      for h in range(1, args.hours))]
candidates.sort(key=lambda s: (s.space.capacity, s.space.name))  # smallest room that fits
if not candidates:
    raise SystemExit(f"No group study room free at {at:%a %d %b %H:%M} for {args.hours}h.")

for slot in candidates:
    if args.dry_run:
        print(f"Would book {slot.space.name} ({slot.space.zone}, {slot.space.capacity} people) "
              f"from {slot.start:%a %d %b %H:%M} for {args.hours}h.")
        raise SystemExit(0)
    try:
        booking = b.book(slot, hours=args.hours)
    except BroomsError as e:
        print(f"Skipping {slot.space.name}: {e}")
        continue
    print(f"Booked {booking.space}, {booking.start:%a %d %b %H:%M}-{booking.end:%H:%M}. "
          "The cancel link is in your university email.")
    break
else:
    raise SystemExit("Tried every free room; none could be booked.")
