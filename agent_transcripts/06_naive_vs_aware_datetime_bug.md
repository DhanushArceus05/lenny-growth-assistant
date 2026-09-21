# Session 6 — Naive vs. aware datetime bug (second live-Postgres-only bug)

**Context:** Immediately after the CORS fix, the user's live Docker Postgres
surfaced a second real bug on the exact same operation (`POST /api/sessions`):

    asyncpg.exceptions.DataError: invalid input for query argument $3:
    datetime.datetime(..., tzinfo=datetime.timezone.utc) (can't subtract
    offset-naive and offset-aware datetimes)

## Root cause

`sessions`/`messages`/`artifacts` columns are plain SQLAlchemy `DateTime` —
Postgres `TIMESTAMP WITHOUT TIME ZONE` — but every default in `db_models.py`
was `datetime.now(timezone.utc)`, timezone-*aware*. asyncpg enforces the
naive/aware distinction strictly at bind time; sqlite (used by the whole test
suite) does not.

## Fix

Added a single `_utcnow()` helper — `datetime.now(timezone.utc).replace(tzinfo=None)`
— and pointed every `default=`/`onupdate=` at it instead of the inline aware
lambda. Deliberately did **not** change the column type to `TIMESTAMPTZ`: the
tables were just created (empty) by the previous session's `init_models()` fix,
so a migration would work, but changing the app to consistently produce naive
UTC is the smaller, lower-risk fix that matches the schema already in place,
per the explicit instruction to avoid unnecessary DB changes.

## A test-writing mistake I caught and fixed before reporting anything

My first attempt at a regression test asserted `session.created_at.tzinfo is None`
after a normal commit+refresh against the test suite's sqlite DB. All the
persistence-based tests passed — which felt like proof, but I didn't trust it and
checked by **temporarily reintroducing the exact original bug** (aware
`datetime.now(timezone.utc)` defaults) and rerunning the same tests. They still
passed. This proved sqlite silently normalizes away tzinfo on read regardless of
what's written — a persistence-based test can never distinguish the fixed
behavior from the bug on this test suite's DB backend.

**Correction:** rewrote the real regression test to inspect
`Column.default.arg` directly — the actual callable SQLAlchemy hands to asyncpg
to produce the bound value — and assert its *output* is naive, bypassing the
ORM/DB round-trip entirely. Verified this test the same way: reintroduced the
bug, confirmed the new test failed (and only that one — the persistence-based
tests still falsely passed), then restored the fix and confirmed all 6 tests in
`test_datetime_handling.py` pass. A second, smaller mistake in that same test —
asserting `default.arg is _utcnow` (identity) — was itself flaky due to an
unrelated duplicate-module-import quirk in this environment; changed it to
assert the callable's *behavior* (naive output) instead of its identity, which
is what actually matters and isn't sensitive to how the module got imported.

## Verified this session
- 54/54 backend tests pass (48 prior + 6 new datetime tests).
- The one meaningful regression test (`test_column_defaults_are_wired_to_the_naive_utcnow_helper`)
  empirically confirmed to fail against the original bug and pass against the fix.
- Also empirically confirmed which of the *other* new tests would NOT have
  caught this bug (documented honestly in the test file's docstrings, not
  hidden) — worth keeping anyway as ordinary persistence/integration checks,
  just not overclaimed as regression coverage for this specific issue.

## Still requires local verification
Rebuilding the backend image and confirming `POST /api/sessions` succeeds
against the real Postgres instance with the 675 existing chunks untouched.
