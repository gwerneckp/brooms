# Changelog

## 0.1.0

First version, built and tested against the University of Bath's LibCal site.

- `Brooms(username, password)` client. Looking needs no login; booking logs in through LibAuth and Bath's single sign-on, and `LoginError` carries the site's message on a wrong password
- `spaces(location, type, zone)`: every room, table and booth, on campus or in the city
- `availability(day, type, zone, space)`: every slot of every space, from one request
- `book(slot, hours, name)` for 1 or 2 hours. It checks the cart and the checkout form before submitting, refuses anything paid, and checks the confirmation afterwards
- `cancel(link)` with the cancel link from the confirmation email
- Offline tests against real pages from the site, scrubbed of personal details, plus read-only live tests
- `tests/capture_fixtures.py` to refresh those pages when the site changes
- `examples/book_room.py`
