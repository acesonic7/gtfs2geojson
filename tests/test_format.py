"""Output format support: geojson + geojsonseq (v0.4)."""
from __future__ import annotations

import json

import pytest

from gtfs2geojson import convert, write


_RS = "\x1e"


def test_default_format_is_geojson(demo_zip, tmp_path):
    out = tmp_path / "out.geojson"
    geo = convert(demo_zip)
    write(geo, out)
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["type"] == "FeatureCollection"
    assert len(parsed["features"]) == len(geo["features"])


def test_geojsonseq_writes_one_record_per_feature(demo_zip, tmp_path):
    out = tmp_path / "out.geojsonseq"
    geo = convert(demo_zip)
    write(geo, out, format="geojsonseq")
    raw = out.read_text(encoding="utf-8")

    # Every record starts with the ASCII Record Separator and ends with \n.
    records = [r for r in raw.split(_RS) if r]
    assert len(records) == len(geo["features"])
    for r in records:
        assert r.endswith("\n")
        parsed = json.loads(r)
        assert parsed["type"] == "Feature"


def test_geojsonseq_record_decodes_to_same_features(demo_zip, tmp_path):
    out = tmp_path / "out.geojsonseq"
    geo = convert(demo_zip)
    write(geo, out, format="geojsonseq")
    raw = out.read_text(encoding="utf-8")
    seq = [json.loads(r) for r in raw.split(_RS) if r]
    expected_ids = [f["properties"].get("route_id") or f["properties"].get("stop_id")
                    for f in geo["features"]]
    actual_ids = [f["properties"].get("route_id") or f["properties"].get("stop_id")
                  for f in seq]
    assert expected_ids == actual_ids


def test_unknown_format_raises():
    with pytest.raises(ValueError, match="unknown format"):
        write({"type": "FeatureCollection", "features": []}, "/tmp/x", format="kml")
