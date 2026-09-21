"""
Regression tests for the exact bug found during live Docker verification against
real Postgres:

    asyncpg.exceptions.DataError: invalid input for query argument $3:
    datetime.datetime(..., tzinfo=datetime.timezone.utc) (can't subtract
    offset-naive and offset-aware datetimes)

Root cause: `sessions`/`messages`/`artifacts` columns are plain `DateTime`
(Postgres `TIMESTAMP WITHOUT TIME ZONE`), but the ORM defaults produced
timezone-aware `datetime.now(timezone.utc)` values. asyncpg enforces this
mismatch strictly; sqlite (used by the rest of this test suite) does NOT — it
silently accepts either AND normalizes tzinfo away on read, which is exactly why
this didn't surface until a real Postgres run (confirmed empirically: temporarily
reintroducing the original `datetime.now(timezone.utc)` defaults and re-running
this file, every persistence-based test below still passed). The test that
actually catches this class of bug without a live Postgres connection is
`test_column_defaults_are_wired_to_the_naive_utcnow_helper`, which inspects the
column default callable directly rather than round-tripping through sqlite.
"""
from datetime import datetime

from app.models.db_models import Artifact, Message, Session, _utcnow


def test_utcnow_helper_returns_naive_datetime():
    dt = _utcnow()
    assert dt.tzinfo is None


def test_utcnow_is_actually_current_utc_time():
    # Naive, but should still be close to the real current UTC instant — a bug
    # that e.g. dropped a timezone conversion instead of just stripping tzinfo
    # would produce a naive datetime offset by the local timezone.
    from datetime import timezone

    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = abs((_utcnow() - now_utc_naive).total_seconds())
    assert delta < 2


async def test_session_created_at_is_naive_when_persisted(db_session):
    session = Session(title="test session")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    assert session.created_at.tzinfo is None
    assert session.updated_at.tzinfo is None


async def test_message_and_artifact_created_at_are_naive_when_persisted(db_session):
    session = Session(title="test session")
    db_session.add(session)
    await db_session.flush()

    message = Message(session_id=session.id, role="user", content="hello")
    db_session.add(message)
    await db_session.flush()

    artifact = Artifact(message_id=message.id, artifact_type="markdown", title="doc", content="# hi")
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(message)
    await db_session.refresh(artifact)

    assert message.created_at.tzinfo is None
    assert artifact.created_at.tzinfo is None


def test_column_defaults_are_wired_to_the_naive_utcnow_helper():
    """The actual regression point: sqlite (used above and by the rest of this
    suite) silently normalizes away tzinfo on read, so a persisted-value
    assertion alone would pass even with the original buggy
    `datetime.now(timezone.utc)` default — confirmed empirically by temporarily
    reintroducing that exact bug and re-running the tests above, which still
    passed. The only place this bug is actually visible without a live Postgres
    connection is the column's default callable itself, inspected directly
    here via SQLAlchemy's `ColumnDefault.arg` — this is what asyncpg actually
    calls to produce the value it binds to the query parameter. Checking the
    callable's *behavior* (naive output) rather than its identity against
    `_utcnow` — a duplicate-import edge case can give two distinct-but-identical
    function objects, which would make an `is` check flaky for reasons unrelated
    to this bug."""
    for model, column_name in [
        (Session, "created_at"),
        (Session, "updated_at"),
        (Message, "created_at"),
        (Artifact, "created_at"),
    ]:
        default_fn = model.__table__.columns[column_name].default.arg
        result = default_fn(None)
        assert isinstance(result, datetime)
        assert result.tzinfo is None, f"{model.__name__}.{column_name} default produced a tz-aware datetime"


async def test_new_session_can_be_created_via_api_without_datetime_error(client):
    """Sanity/integration check that the full create-session code path (the
    operation that actually failed against Postgres) still works end-to-end on
    this ORM. Note: sqlite normalizes away tzinfo on read the same way it did
    for the two persistence tests above, so this alone would NOT have caught the
    original bug — `test_column_defaults_are_wired_to_the_naive_utcnow_helper`
    above is the test that actually does that. This one guards against a
    different mistake: e.g. accidentally serializing timestamps in a shape the
    frontend or a future migration wouldn't expect."""
    resp = await client.post("/api/sessions", json={"title": "Pricing questions"})
    assert resp.status_code == 201
    body = resp.json()
    assert "+" not in body["created_at"].split("T")[-1]
    assert not body["created_at"].endswith("Z")
