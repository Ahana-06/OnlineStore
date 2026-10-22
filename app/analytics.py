"""Turns raw order rows into the numbers the seller dashboard charts need.

No Flask or database code in here, so it is easy to test.
rows = list of (qty, price_at_purchase, order_id, order_status, created_at, product_name)
"""
from datetime import timedelta

STATUSES = ["Placed", "Packed", "Shipped", "Delivered"]


def build_chart_data(rows, now, weeks=8):
    revenue = [0.0] * weeks
    units = {}
    order_status = {}      # order_id -> status (an order is counted once)
    total_units = 0

    for qty, price, order_id, status, created_at, name in rows:
        week_idx = weeks - 1 - int((now - created_at).days // 7)   # last slot = this week
        if 0 <= week_idx < weeks:
            revenue[week_idx] += qty * price
        units[name] = units.get(name, 0) + qty
        total_units += qty
        order_status[order_id] = status

    top = sorted(units.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    status_counts = [sum(1 for s in order_status.values() if s == label) for label in STATUSES]
    week_labels = [(now - timedelta(days=7 * (weeks - 1 - i))).strftime("%d %b") for i in range(weeks)]

    return {
        "week_labels": week_labels,
        "revenue": [round(r, 2) for r in revenue],
        "top_names": [name for name, _ in top],
        "top_units": [u for _, u in top],
        "status_labels": STATUSES,
        "status_counts": status_counts,
        "total_revenue": round(sum(revenue), 2),
        "total_units": total_units,
        "total_orders": len(order_status),
    }
