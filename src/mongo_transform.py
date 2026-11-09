"""
Pure-Python transformations: raw generator JSON  ->  MongoDB documents.
Kept out of the notebook so they can be unit-tested and re-used.

Modelling decisions implemented here (justified in the report):
  * ISO strings  -> real datetime objects (enables date operators / TTL / range queries)
  * product      -> embeds a small copy of its category (denormalisation, read-heavy)
  * transaction  -> items embedded AND each item carries category_id (avoids a $lookup
                    for the most common analytic: revenue by category)
  * session      -> page_views embedded (a journey is always read as a whole);
                    cart_contents {product_id: {...}} becomes an ARRAY cart_items,
                    because dynamic keys cannot be indexed or queried by operators.
"""
from datetime import datetime
from statistics import mean


def parse_dt(value):
    """'2026-08-10T10:38:23.998221' -> datetime (None stays None)."""
    return datetime.fromisoformat(value) if value else None


def build_category_lookup(categories):
    """category_id -> {name, avg_margin, n_subcategories}.
    NOTE: products.json has NO subcategory_id, so profit margin can only be
    estimated at category level (mean of its subcategory margins)."""
    lookup = {}
    for c in categories:
        margins = [s["profit_margin"] for s in c["subcategories"]]
        lookup[c["category_id"]] = {
            "name": c["name"],
            "avg_margin": round(mean(margins), 4) if margins else None,
            "n_subcategories": len(margins),
        }
    return lookup


def transform_category(c, lookup):
    doc = dict(c)
    doc["_id"] = doc["category_id"]
    doc["avg_profit_margin"] = lookup[c["category_id"]]["avg_margin"]
    return doc


def transform_product(p, lookup):
    cat = lookup.get(p["category_id"], {})
    return {
        "_id": p["product_id"],
        "product_id": p["product_id"],
        "name": p["name"],
        "category": {"category_id": p["category_id"], "name": cat.get("name"),
                     "avg_margin": cat.get("avg_margin")},
        "base_price": p["base_price"],
        "current_stock": p["current_stock"],
        "is_active": p["is_active"],
        "price_history": [{"price": h["price"], "date": parse_dt(h["date"])}
                          for h in p.get("price_history", [])],
        "creation_date": parse_dt(p["creation_date"]),
    }


def transform_user(u):
    """purchase_summary / engagement are created with zeros here and filled later by
    server-side aggregation pipelines ($merge), so users with no purchases still
    have a consistent shape."""
    return {
        "_id": u["user_id"],
        "user_id": u["user_id"],
        "geo_data": u["geo_data"],
        "registration_date": parse_dt(u["registration_date"]),
        "last_active": parse_dt(u["last_active"]),
        "purchase_summary": {"orders": 0, "total_spent": 0.0, "avg_order_value": 0.0,
                             "first_purchase": None, "last_purchase": None},
        "preferences": {"top_categories": []},
    }


def transform_transaction(t, product_category):
    items = []
    for it in t["items"]:
        items.append({**it, "category_id": product_category.get(it["product_id"])})
    return {
        "_id": t["transaction_id"],
        "transaction_id": t["transaction_id"],
        "session_id": t["session_id"],
        "user_id": t["user_id"],
        "timestamp": parse_dt(t["timestamp"]),
        "items": items,
        "n_items": sum(i["quantity"] for i in items),
        "subtotal": t["subtotal"],
        "discount": t["discount"],
        "total": t["total"],
        "payment_method": t["payment_method"],
        "status": t["status"],
    }


def transform_session(s):
    cart_items = [{"product_id": pid, "quantity": v["quantity"], "price": v["price"]}
                  for pid, v in (s.get("cart_contents") or {}).items()]
    page_views = [{**pv, "timestamp": parse_dt(pv["timestamp"])} for pv in s["page_views"]]
    return {
        "_id": s["session_id"],
        "session_id": s["session_id"],
        "user_id": s["user_id"],
        "start_time": parse_dt(s["start_time"]),
        "end_time": parse_dt(s["end_time"]),
        "duration_seconds": s["duration_seconds"],
        "geo_data": s["geo_data"],
        "device_profile": s["device_profile"],
        "viewed_products": s["viewed_products"],
        "page_views": page_views,
        "cart_items": cart_items,
        "cart_value": round(sum(c["quantity"] * c["price"] for c in cart_items), 2),
        "n_page_views": len(page_views),
        "conversion_status": s["conversion_status"],
        "referrer": s["referrer"],
    }
