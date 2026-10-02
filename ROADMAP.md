# Roadmap

brooms is built around **the University of Bath's study-space bookings** ([bath.libcal.com](https://bath.libcal.com), Springshare LibCal). [Froom](https://froom.bathcs.com) finds free rooms; brooms books them. New features come from what Bath students actually do on the site, and are tested there. The guiding rule is **stay small**: one `Brooms` class, plain dataclasses, two dependencies.

## How the site works (found 2 Oct 2026)

- **Looking needs no login.** The space list is a server-rendered search page, and availability is one JSON call (`/spaces/availability/grid`) for a whole location and day.
- **Booking logs in with your Bath username and password** (LibCal → LibAuth → Bath single sign-on, a plain username and password form, no MFA), then submits a one-field checkout form. Your name and email come from the login.
- **Bookings open 7 days ahead**, in 1-hour slots, and a booking can be 1 or 2 hours.
- **Cancelling needs the link from the confirmation email** (`/equipment/cancel?id=...`). That link is the only handle on a booking: the site never shows it anywhere else, and its "patron view" logs in by emailed link too. So there's no way to list your own bookings.

## Now (0.1): book and cancel rooms

- [ ] **`spaces()`**: every bookable room, table and booth, on campus or in the city (Virgil Building)
- [ ] **`availability(day, type=..., zone=..., space=...)`**: every 1-hour slot of every space, from one request
- [ ] **`book(slot, hours=1|2, name=...)`**: logs in, books, and checks the confirmation. Refuses anything that costs money, and anything the checkout asks for that brooms doesn't know
- [ ] **`cancel(link)`**: cancels the bookings behind a confirmation email's cancel link
- [ ] Offline tests against real, scrubbed pages from the site, plus opt-in live tests (read-only, no account needed)
- [ ] A capture script to refresh the test pages when the site changes

## Next (0.2): CLI and MCP

- [ ] A `brooms` command, e.g. `brooms free "group study room" mon 14:00`, `brooms book <space> mon 14:00 --hours 2`, `brooms cancel <link>`, with `--json` for scripts and agents
- [ ] An optional MCP server (`[mcp]` extra) with read-only tools first, and booking and cancelling as separate, explicit tools

## Later

- [ ] Study desks. They're booked as seats (`seatId`), a different flow from rooms
- [ ] Check in with the code from the confirmation email, if the site lets a script do it

## 1.0: stable release

- [ ] A stable, documented API
- [ ] Published on PyPI

## Not in scope

- **Reading your email** to find cancel links. That needs access to your Bath (Outlook) inbox, which belongs in your own automations, e.g. an agent with a Microsoft 365 connector that passes the link to `cancel()`.
- **Listing your bookings**, for the same reason: the site only ties bookings to you through email.
- Teaching rooms. Students can't book them; [Froom](https://froom.bathcs.com) shows which are free.
