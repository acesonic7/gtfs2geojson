"""list_modes / list_agencies + bug #4 (sole-agency fallback) — v0.4."""
from __future__ import annotations

from gtfs2geojson import convert, list_agencies, list_modes


def test_list_modes_demo(demo_zip):
    counts = list_modes(demo_zip)
    assert counts == {"Bus": 1, "Metro": 1, "Tram": 1}


def test_list_modes_empty_routes(demo_files, feed_factory):
    files = dict(demo_files)
    files["routes.txt"] = "route_id,agency_id,route_short_name,route_long_name,route_type\n"
    assert list_modes(feed_factory(files)) == {}


def test_list_agencies_demo(demo_zip):
    rows = list_agencies(demo_zip)
    assert rows == [{"agency_id": "DEMO", "agency_name": "Demo Transit", "n_routes": 3}]


def test_list_agencies_attributes_blank_to_sole_agency(demo_files, feed_factory):
    """Bug #4: if a feed has exactly one agency, routes with empty agency_id
    should be attributed to it — not bucketed under the empty string."""
    files = dict(demo_files)
    # All three routes lose their explicit agency_id.
    files["routes.txt"] = (
        "route_id,agency_id,route_short_name,route_long_name,route_type,route_color\n"
        "B1,,1,Centre - Airport,3,1976D2\n"
        "M1,,M1,Red Line,1,D32F2F\n"
        "T1,,T,Coastal Tram,0,\n"
    )
    rows = list_agencies(feed_factory(files))
    assert rows == [{"agency_id": "DEMO", "agency_name": "Demo Transit", "n_routes": 3}]


def test_list_agencies_multiple(demo_files, feed_factory):
    files = dict(demo_files)
    files["agency.txt"] = (
        "agency_id,agency_name,agency_url,agency_timezone\n"
        "A,Agency A,http://a,UTC\n"
        "B,Agency B,http://b,UTC\n"
    )
    files["routes.txt"] = (
        "route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "R1,A,1,One,3\n"
        "R2,A,2,Two,3\n"
        "R3,B,3,Three,1\n"
    )
    rows = list_agencies(feed_factory(files))
    by_id = {r["agency_id"]: r for r in rows}
    assert by_id["A"]["n_routes"] == 2
    assert by_id["B"]["n_routes"] == 1


def test_convert_agency_filter_uses_sole_agency_fallback(demo_files, feed_factory):
    """Bug #4 in convert(): --agency DEMO should match routes with empty agency_id
    when DEMO is the sole agency."""
    files = dict(demo_files)
    files["routes.txt"] = (
        "route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "B1,,1,Bus Route,3\n"
    )
    geo = convert(feed_factory(files), agencies=["DEMO"])
    rids = {f["properties"]["route_id"]
            for f in geo["features"] if f["geometry"]["type"] != "Point"}
    assert "B1" in rids
    # And the route's agency_id property should now reflect the resolved agency.
    b1 = next(f for f in geo["features"] if f["properties"].get("route_id") == "B1")
    assert b1["properties"]["agency_id"] == "DEMO"
    assert b1["properties"]["agency_name"] == "Demo Transit"


def test_convert_no_sole_agency_fallback_with_multiple_agencies(feed_factory):
    """If the feed has more than one agency, blank agency_id stays blank."""
    files = {
        "agency.txt":
            "agency_id,agency_name,agency_url,agency_timezone\n"
            "A,A,http://a,UTC\nB,B,http://b,UTC\n",
        "routes.txt":
            "route_id,agency_id,route_short_name,route_long_name,route_type\n"
            "R1,,1,Mystery,3\n",
        "stops.txt":
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "p,P,10.0,10.0\nq,Q,10.1,10.1\n",
        "trips.txt": "route_id,service_id,trip_id\nR1,WK,t1\n",
        "stop_times.txt":
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "t1,08:00:00,08:00:00,p,1\nt1,08:30:00,08:30:00,q,2\n",
    }
    geo = convert(feed_factory(files))
    r1 = next(f for f in geo["features"] if f["properties"].get("route_id") == "R1")
    assert r1["properties"]["agency_id"] == ""
