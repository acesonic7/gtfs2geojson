"""Shared pytest fixtures: synthetic GTFS feeds for tests."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

DEMO_GTFS: dict[str, str] = {
    "agency.txt":
        "agency_id,agency_name,agency_url,agency_timezone\n"
        "DEMO,Demo Transit,http://example.com,Europe/Athens\n",
    "routes.txt":
        "route_id,agency_id,route_short_name,route_long_name,route_type,route_color\n"
        "B1,DEMO,1,Centre - Airport,3,1976D2\n"
        "M1,DEMO,M1,Red Line,1,D32F2F\n"
        "T1,DEMO,T,Coastal Tram,0,\n",
    "stops.txt":
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "s1,Centre,37.9755,23.7348\n"
        "s2,Museum,37.9876,23.7338\n"
        "s3,University,37.9981,23.7411\n"
        "s4,Airport,37.9356,23.9468\n"
        "s5,Beach,37.9300,23.7100\n"
        "s6,Marina,37.9250,23.7250\n",
    "trips.txt":
        "route_id,service_id,trip_id,shape_id,trip_headsign\n"
        "B1,WK,t_b1,sh_b1,Airport\n"
        "M1,WK,t_m1,,University\n"
        "T1,WK,t_t1,sh_t1,Marina\n",
    "shapes.txt":
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
        "sh_b1,37.9755,23.7348,1\nsh_b1,37.9700,23.8000,2\n"
        "sh_b1,37.9500,23.8800,3\nsh_b1,37.9356,23.9468,4\n"
        "sh_t1,37.9300,23.7100,1\nsh_t1,37.9250,23.7250,2\n",
    "stop_times.txt":
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "t_b1,08:00:00,08:00:00,s1,1\nt_b1,08:30:00,08:30:00,s4,2\n"
        "t_m1,09:00:00,09:00:00,s1,1\nt_m1,09:05:00,09:05:00,s2,2\n"
        "t_m1,09:10:00,09:10:00,s3,3\n"
        "t_t1,10:00:00,10:00:00,s5,1\nt_t1,10:05:00,10:05:00,s6,2\n",
    "calendar.txt":
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "WK,1,1,1,1,1,0,0,20240101,20251231\n",
}


def _write_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    return tmp_path


def _write_zip(tmp_path: Path, files: dict[str, str], name: str = "demo.zip") -> Path:
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as zf:
        for fname, body in files.items():
            zf.writestr(fname, body)
    return p


@pytest.fixture
def demo_files() -> dict[str, str]:
    """The demo GTFS as a {filename: text} dict — handy for variants."""
    return {k: v for k, v in DEMO_GTFS.items()}


@pytest.fixture
def demo_zip(tmp_path: Path) -> Path:
    return _write_zip(tmp_path, DEMO_GTFS)


@pytest.fixture
def demo_dir(tmp_path: Path) -> Path:
    return _write_dir(tmp_path, DEMO_GTFS)


@pytest.fixture
def feed_factory(tmp_path: Path):
    """Returns a callable that materialises a GTFS dict as a zip in a unique subdir."""
    counter = {"n": 0}

    def _make(files: dict[str, str], *, as_dir: bool = False) -> Path:
        counter["n"] += 1
        sub = tmp_path / f"feed_{counter['n']}"
        sub.mkdir()
        return _write_dir(sub, files) if as_dir else _write_zip(sub, files)

    return _make
