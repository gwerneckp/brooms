<p align="center">
  <img src="https://raw.githubusercontent.com/gwerneckp/brooms/main/assets/logo.svg" alt="brooms logo" width="128">
</p>

<h1 align="center">brooms</h1>

<p align="center">
  <a href="https://pypi.org/project/brooms/"><img src="https://img.shields.io/pypi/v/brooms" alt="PyPI"></a>
  <a href="https://pypi.org/project/brooms/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="https://github.com/gwerneckp/brooms/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/brooms" alt="License"></a>
</p>

<p align="center"><b>Book a study room at the University of Bath from Python.</b></p>

[Froom](https://froom.bathcs.com) finds free rooms; brooms **b**ooks **rooms**. It drives [bath.libcal.com](https://bath.libcal.com), where Bath students book group study rooms, tables and meeting booths in the Library, 1 West, 8 West, East Building, Norwood House and the Virgil Building. No browser needed, so it works in scripts, cron jobs and agents.

## Install

```bash
pip install brooms
```

Requires Python 3.11+.

## Quick start

```python
from datetime import date, timedelta
from brooms import Brooms

b = Brooms("ab123", "password")                 # your Bath username and password
monday = date.today() + timedelta(days=3)

free = [s for s in b.availability(monday, type="group study room", zone="library")
        if s.available and s.start.hour == 14]
print(free[0].space.name, free[0].start)        # Library 1.12 2026-10-05 14:15:00

booking = b.book(free[0], hours=2)              # 14:15-16:15
b.cancel("https://bath.libcal.com/equipment/cancel?id=...")  # the link from the email
```

`b.spaces()` lists every room, table and booth (`b.spaces("city")` for the Virgil Building), and looking needs no login at all. There's a fuller script in [`examples/`](https://github.com/gwerneckp/brooms/blob/main/examples/).

## Good to know

- **Bookings open 7 days ahead**, in 1-hour slots starting at quarter past. A booking can be 1 or 2 hours.
- **Cancelling needs the link from the confirmation email** the site sends to your university address. It's the only handle the site gives on a booking, so brooms can't list your bookings either. To automate cancelling, have whatever reads your email (e.g. an agent with a Microsoft 365 connector) pass the link to `cancel()`.
- **Logging in** goes through Bath's single sign-on with your username and password, like a browser. Keep them out of your code, e.g. in your OS keychain or environment variables.
- **Rooms, tables and booths only.** Study desks are booked a different way and aren't supported yet. Bath's spaces are free; if one ever costs money, `book()` refuses it.
- If a booking attempt fails halfway, its slot stays held for about 5 minutes and shows as unavailable until then.

## Development

```bash
uv sync
uv run pytest              # offline, no account needed
uv run pytest -m live      # read-only checks against the real site, no account needed
```

See [CONTRIBUTING.md](https://github.com/gwerneckp/brooms/blob/main/CONTRIBUTING.md) and the [roadmap](https://github.com/gwerneckp/brooms/blob/main/ROADMAP.md).

## License

[MIT](https://github.com/gwerneckp/brooms/blob/main/LICENSE)
