"""Run with:  pytest -q   (from the project root)"""
import json, sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
import hbase_schema as H
import mongo_transform as M

SESSION = {
    "session_id": "sess_a", "user_id": "user_000042", "start_time": "2026-10-05T14:37:22",
    "end_time": "2026-10-05T14:52:41", "duration_seconds": 919,
    "geo_data": {"city": "X", "state": "WY", "country": "US", "ip_address": "1.2.3.4"},
    "device_profile": {"type": "mobile", "os": "iOS", "browser": "Safari"},
    "viewed_products": ["prod_00123"],
    "page_views": [
        {"timestamp": "2026-10-05T14:37:22", "page_type": "home", "product_id": None,
         "category_id": None, "view_duration": 42},
        {"timestamp": "2026-10-05T14:39:11", "page_type": "product_detail",
         "product_id": "prod_00123", "category_id": "cat_007", "view_duration": 124}],
    "cart_contents": {"prod_00123": {"quantity": 2, "price": 129.99}},
    "conversion_status": "converted", "referrer": "search_engine"}


def test_hbase_roundtrip():
    key = H.user_session_rowkey("user_000042", SESSION["start_time"], "sess_a")
    back = H.cells_to_session(key, H.session_to_cells(SESSION))
    assert back["page_views"][1]["product_id"] == "prod_00123"
    assert back["page_views"][0]["product_id"] is None
    assert back["cart"]["prod_00123"]["quantity"] == 2


def test_newest_first_ordering():
    k_old = H.user_session_rowkey("u", "2026-10-01T00:00:00", "a")
    k_new = H.user_session_rowkey("u", "2026-10-09T00:00:00", "b")
    assert k_new < k_old                      # newer sorts first


def test_time_range_bounds_include_and_exclude():
    start, stop = H.user_time_range_bounds("u", "2026-10-02T00:00:00", "2026-10-08T00:00:00")
    inside = H.user_session_rowkey("u", "2026-10-05T12:00:00", "s")
    edge_lo = H.user_session_rowkey("u", "2026-10-02T00:00:00", "s")
    before = H.user_session_rowkey("u", "2026-10-01T23:59:59", "s")
    after = H.user_session_rowkey("u", "2026-10-08T00:00:01", "s")
    assert start <= inside < stop and start <= edge_lo < stop
    assert not (start <= before < stop) and not (start <= after < stop)


def test_product_range_bounds():
    a, b = H.product_range_bounds("p", "20261001", "20261031")
    assert a <= H.product_metric_rowkey("p", "20261031") < b
    assert not (a <= H.product_metric_rowkey("p", "20261101") < b)


def test_mongo_session_cart_becomes_array():
    d = M.transform_session(SESSION)
    assert d["cart_items"] == [{"product_id": "prod_00123", "quantity": 2, "price": 129.99}]
    assert d["cart_value"] == 259.98 and d["n_page_views"] == 2
