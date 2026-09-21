"""Unit tests for scripts/ingest.py's real-data parsing helpers — front-matter
dates vary in shape across real vs. synthetic transcripts, and the citation link
should prefer the most specific traceable source available."""
from datetime import date
from pathlib import Path

from scripts.ingest import _build_source_location, _parse_date


def test_parse_date_from_quoted_iso_string():
    assert _parse_date("2026-08-16") == date(2026, 8, 16)


def test_parse_date_passes_through_date_object():
    assert _parse_date(date(2024, 3, 12)) == date(2024, 3, 12)


def test_parse_date_none_for_missing_or_bad_value():
    assert _parse_date(None) is None
    assert _parse_date("not-a-date") is None


def test_source_location_prefers_youtube_deep_link_with_timestamp():
    loc = _build_source_location(
        video_id="kLe-zy5r0Mk",
        youtube_url="https://www.youtube.com/watch?v=kLe-zy5r0Mk",
        post_url="https://www.lennysnewsletter.com/p/example",
        path=Path("data/lennys_podcast/stewart-butterfield.md"),
        timestamp_ref="00:07:08",
    )
    assert loc == "https://www.youtube.com/watch?v=kLe-zy5r0Mk&t=428s"


def test_source_location_falls_back_to_youtube_url_without_timestamp():
    loc = _build_source_location(
        video_id="kLe-zy5r0Mk",
        youtube_url="https://www.youtube.com/watch?v=kLe-zy5r0Mk",
        post_url=None,
        path=Path("f.md"),
        timestamp_ref=None,
    )
    assert loc == "https://www.youtube.com/watch?v=kLe-zy5r0Mk"


def test_source_location_falls_back_to_post_url_without_video_id():
    loc = _build_source_location(
        video_id=None,
        youtube_url=None,
        post_url="https://www.lennysnewsletter.com/p/example",
        path=Path("f.md"),
        timestamp_ref="00:04:24",
    )
    assert loc == "https://www.lennysnewsletter.com/p/example"


def test_source_location_falls_back_to_file_path_for_synthetic_fixtures():
    loc = _build_source_location(
        video_id=None, youtube_url=None, post_url=None, path=Path("sample_transcripts/01-plg-onboarding.md"), timestamp_ref="00:02:10"
    )
    assert loc == "sample_transcripts/01-plg-onboarding.md"
