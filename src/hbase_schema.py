"""
HBase schema helpers: row-key design + (de)serialisation of sessions.

TABLE 1  user_sessions        row key = <user_id>#<reverse_ts>#<session_id>
    reverse_ts = 9_999_999_999_999 - epoch_ms  (13 digits, zero padded)
    -> all of a user's sessions are contiguous AND sorted newest-first,
       so "last N sessions" is a prefix scan with limit=N.
    families:  meta | device | geo | pv | cart
       pv   : one column per page view, qualifier = 3-digit sequence ("000","001"...)
              value = ts|page_type|product_id|category_id|view_duration
       cart : one column per product in the cart, qualifier = product_id
              value = quantity|price      (dynamic, sparse columns = wide-column strength)

TABLE 2  product_daily_metrics  row key = <product_id>#<yyyymmdd>
    family m: views | cart_adds | purchases | units | revenue
    -> one product's time series is contiguous: a date-range query is a short range scan.
"""
from datetime import datetime, timezone

MAX_TS_MS = 9_999_999_999_999
USER_SESSIONS = "user_sessions"
PRODUCT_METRICS = "product_daily_metrics"

USER_SESSIONS_FAMILIES = ["meta", "device", "geo", "pv", "cart"]
PRODUCT_METRICS_FAMILIES = ["m"]


def to_epoch_ms(iso: str) -> int:
    """ISO timestamp (naive, treated as UTC) -> epoch milliseconds."""
    dt = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def user_session_rowkey(user_id: str, start_iso: str, session_id: str) -> bytes:
    rev = MAX_TS_MS - to_epoch_ms(start_iso)
    return f"{user_id}#{rev:013d}#{session_id}".encode()


def user_prefix(user_id: str) -> bytes:
    return f"{user_id}#".encode()


def user_time_range_bounds(user_id: str, start_iso: str, end_iso: str):
    """(row_start, row_stop) covering sessions that started in [start_iso, end_iso].
    Newest sessions have SMALLER reverse timestamps, hence the swap."""
    rev_from = MAX_TS_MS - to_epoch_ms(end_iso)
    rev_to = MAX_TS_MS - to_epoch_ms(start_iso) + 1      # stop row is exclusive
    return (f"{user_id}#{rev_from:013d}".encode(), f"{user_id}#{rev_to:013d}".encode())


def product_metric_rowkey(product_id: str, yyyymmdd: str) -> bytes:
    return f"{product_id}#{yyyymmdd}".encode()


def product_range_bounds(product_id: str, first_yyyymmdd: str, last_yyyymmdd: str):
    """Inclusive date range -> (row_start, row_stop exclusive)."""
    last_plus = (datetime.strptime(last_yyyymmdd, "%Y%m%d")
                 .toordinal() + 1)
    stop_day = datetime.fromordinal(last_plus).strftime("%Y%m%d")
    return (product_metric_rowkey(product_id, first_yyyymmdd),
            product_metric_rowkey(product_id, stop_day))


def _s(value) -> bytes:
    return ("" if value is None else str(value)).encode()


def session_to_cells(s: dict) -> dict:
    """One raw session dict -> {b'family:qualifier': b'value'} ready for table.put()."""
    cells = {
        b"meta:session_id": _s(s["session_id"]),
        b"meta:user_id": _s(s["user_id"]),
        b"meta:start": _s(s["start_time"]),
        b"meta:end": _s(s["end_time"]),
        b"meta:duration": _s(s["duration_seconds"]),
        b"meta:referrer": _s(s["referrer"]),
        b"meta:status": _s(s["conversion_status"]),
        b"meta:n_views": _s(len(s["page_views"])),
        b"device:type": _s(s["device_profile"]["type"]),
        b"device:os": _s(s["device_profile"]["os"]),
        b"device:browser": _s(s["device_profile"]["browser"]),
        b"geo:city": _s(s["geo_data"].get("city")),
        b"geo:state": _s(s["geo_data"].get("state")),
        b"geo:country": _s(s["geo_data"].get("country")),
        b"geo:ip": _s(s["geo_data"].get("ip_address")),
    }
    for i, pv in enumerate(s["page_views"]):
        cells[f"pv:{i:03d}".encode()] = "|".join(
            _s(x).decode() for x in (pv["timestamp"], pv["page_type"], pv["product_id"],
                                     pv["category_id"], pv["view_duration"])).encode()
    for pid, v in (s.get("cart_contents") or {}).items():
        cells[f"cart:{pid}".encode()] = f"{v['quantity']}|{v['price']}".encode()
    return cells


def cells_to_session(row_key: bytes, data: dict) -> dict:
    """Inverse of session_to_cells(): rebuild a readable session from an HBase row."""
    g = lambda k: data.get(k, b"").decode()
    page_views = []
    for col in sorted(c for c in data if c.startswith(b"pv:")):
        ts, ptype, pid, cid, dur = data[col].decode().split("|")
        page_views.append({"timestamp": ts, "page_type": ptype, "product_id": pid or None,
                           "category_id": cid or None, "view_duration": int(dur)})
    cart = {}
    for col in (c for c in data if c.startswith(b"cart:")):
        q, p = data[col].decode().split("|")
        cart[col.decode().split(":", 1)[1]] = {"quantity": int(q), "price": float(p)}
    return {
        "row_key": row_key.decode(),
        "session_id": g(b"meta:session_id"), "user_id": g(b"meta:user_id"),
        "start": g(b"meta:start"), "end": g(b"meta:end"),
        "duration": int(g(b"meta:duration") or 0), "referrer": g(b"meta:referrer"),
        "status": g(b"meta:status"),
        "device": {"type": g(b"device:type"), "os": g(b"device:os"),
                   "browser": g(b"device:browser")},
        "geo": {"city": g(b"geo:city"), "state": g(b"geo:state"), "country": g(b"geo:country")},
        "page_views": page_views, "cart": cart,
    }
