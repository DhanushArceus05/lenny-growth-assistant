from app.rag.chunking import timestamp_to_seconds


def test_hms_format():
    assert timestamp_to_seconds("00:07:08") == 428


def test_ms_format():
    assert timestamp_to_seconds("07:08") == 428


def test_hours_component():
    assert timestamp_to_seconds("01:02:03") == 3723


def test_invalid_formats_return_none():
    assert timestamp_to_seconds("") is None
    assert timestamp_to_seconds("not-a-timestamp") is None
    assert timestamp_to_seconds("1:2:3:4") is None
