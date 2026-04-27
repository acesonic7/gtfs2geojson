"""End-to-end CLI invocations (v0.4)."""
from __future__ import annotations

import json

from gtfs2geojson.__main__ import main


def test_cli_default_writes_geojson_to_stdout(demo_zip, capsys):
    rc = main([str(demo_zip)])
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["type"] == "FeatureCollection"
    assert any(f["properties"].get("route_id") == "B1" for f in parsed["features"])


def test_cli_format_geojsonseq(demo_zip, capsys):
    rc = main([str(demo_zip), "--format", "geojsonseq"])
    assert rc == 0
    raw = capsys.readouterr().out
    records = [r for r in raw.split("\x1e") if r]
    assert len(records) >= 3
    for r in records:
        json.loads(r)  # each record must parse as JSON


def test_cli_list_modes_human(demo_zip, capsys):
    rc = main([str(demo_zip), "--list-modes"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Mode" in out
    for label in ("Bus", "Metro", "Tram"):
        assert label in out


def test_cli_list_modes_json(demo_zip, capsys):
    rc = main([str(demo_zip), "--list-modes", "--json"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    by_mode = {r["mode"]: r["n_routes"] for r in parsed}
    assert by_mode == {"Bus": 1, "Metro": 1, "Tram": 1}


def test_cli_list_agencies_human(demo_zip, capsys):
    rc = main([str(demo_zip), "--list-agencies"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "agency_id" in out
    assert "DEMO" in out
    assert "Demo Transit" in out


def test_cli_list_agencies_json(demo_zip, capsys):
    rc = main([str(demo_zip), "--list-agencies", "--json"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed == [{"agency_id": "DEMO", "agency_name": "Demo Transit", "n_routes": 3}]


def test_cli_list_modes_and_agencies_are_mutually_exclusive(demo_zip, capsys):
    """argparse should reject both flags together."""
    import pytest
    with pytest.raises(SystemExit):
        main([str(demo_zip), "--list-modes", "--list-agencies"])


def test_cli_missing_source_returns_error_code(tmp_path, capsys):
    rc = main([str(tmp_path / "does_not_exist.zip")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err
