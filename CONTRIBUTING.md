# Contributing

Thanks for your interest! brooms is made for **the University of Bath's LibCal site**, and that's the only site it's tested against. Contributions are welcome with that in mind.

## Using it at another university

Many universities book study spaces with Springshare LibCal, so brooms may partly work on yours. The parts specific to Bath are the site address and location pages (`Brooms.URL` and `Brooms.LOCATIONS` in `src/brooms/client.py`) and the login, which follows Bath's single sign-on form (`Brooms.log_in`). You can:

- **Fork it** and adapt it to your site. This is usually the quickest route.
- **Open an issue** saying what worked and what didn't, with anything personal removed.
- **Send a PR** if your change is general and doesn't change behaviour at Bath. I can only test against Bath, so I may not be able to accept changes I can't verify.

## When the site changes

1. Run the live tests to see what broke: `uv run pytest -m live`. They need no account.
2. Refresh the saved pages with `uv run python tests/capture_fixtures.py`. It also needs no account. It holds one slot in a cart for a few minutes, without booking it.
3. Fix `parse.py` or `client.py`, then update the expected values in `tests/test_parse.py` and `tests/test_client.py`. They're specific to the day the pages were captured.
4. **Before committing, check the fixtures by eye** for anything personal.

The booking pages (checkout, confirmation, cancel) can only be captured by really booking. Book a slot in a browser or with brooms, save the pages, cancel straight away, and scrub them with `tests/capture_fixtures.py --booking-pages` (see its docstring). It refuses to save a page if any of your details survive.

## Ground rules

- **Never commit real personal details**: not yours, not anyone else's. Fixtures go through `capture_fixtures.py`.
- **Never commit a password**, not even in a test.
- Keep it simple: no feature bloat. Prefer extending the `Brooms` class over adding layers, and new dependencies need a good reason.
- Helpers go in a class: a private method or staticmethod on the class that uses them. No loose module-level `_functions`.
- Keep calls stateless: each public method starts from scratch.
- Nothing that books, cancels or logs in runs in the default test suite or the live tests.

## Setup

```bash
uv sync
uv run pytest
uv run ruff check src tests examples
```

The default tests are offline: HTTP is mocked with [responses](https://github.com/getsentry/responses) and answered with the saved pages.
