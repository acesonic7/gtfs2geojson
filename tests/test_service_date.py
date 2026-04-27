"""Service-day filtering via --date / service_date (v0.3)."""
from __future__ import annotations

import datetime as dt

import pytest

from gtfs2geojson import convert
from gtfs2geojson.converter import _active_services_on, _normalise_gtfs_date


# Demo's WK service runs Mon-Fri, 2024-01-01 → 2025-12-31.
WK_MONDAY = "20250106"   # Mon, in range
WK_SATURDAY = "20250104"  # Sat, weekday=0 in calendar.txt
OUT_OF_RANGE = "20300106"


def _routes(geo: dict) -> set[str]:
    return {f["properties"]["route_id"]
            for f in geo["features"] if f["geometry"]["type"] != "Point"}


def test_normalise_accepts_yyyymmdd():
    assert _normalise_gtfs_date("20260427") == "20260427"


def test_normalise_accepts_iso():
    assert _normalise_gtfs_date("2026-04-27") == "20260427"


def test_normalise_accepts_date_object():
    assert _normalise_gtfs_date(dt.date(2026, 4, 27)) == "20260427"


def test_normalise_rejects_garbage():
    with pytest.raises(ValueError):
        _normalise_gtfs_date("yesterday")


def test_active_services_in_range(demo_zip):
    assert _active_services_on(demo_zip, WK_MONDAY) == {"WK"}


def test_active_services_wrong_weekday(demo_zip):
    # WK is Mon-Fri only.
    assert _active_services_on(demo_zip, WK_SATURDAY) == set()


def test_active_services_out_of_range(demo_zip):
    assert _active_services_on(demo_zip, OUT_OF_RANGE) == set()


def test_convert_with_active_date_keeps_routes(demo_zip):
    geo = convert(demo_zip, service_date=WK_MONDAY)
    assert _routes(geo) == {"B1", "M1", "T1"}


def test_convert_with_inactive_date_drops_all_routes(demo_zip, capsys):
    geo = convert(demo_zip, service_date=WK_SATURDAY)
    assert _routes(geo) == set()
    assert "no services active" in capsys.readouterr().err.lower()


def test_calendar_dates_addition(demo_files, feed_factory):
    """exception_type=1 should add a service on the given date even if the weekday is off."""
    files = dict(demo_files)
    files["calendar_dates.txt"] = "service_id,date,exception_type\nWK,20250104,1\n"
    geo = convert(feed_factory(files), service_date=WK_SATURDAY)
    assert _routes(geo) == {"B1", "M1", "T1"}


def test_calendar_dates_removal(demo_files, feed_factory):
    """exception_type=2 should remove a service that would otherwise run."""
    files = dict(demo_files)
    files["calendar_dates.txt"] = "service_id,date,exception_type\nWK,20250106,2\n"
    geo = convert(feed_factory(files), service_date=WK_MONDAY)
    assert _routes(geo) == set()


def test_iso_date_string_works(demo_zip):
    geo = convert(demo_zip, service_date="2025-01-06")
    assert _routes(geo) == {"B1", "M1", "T1"}
