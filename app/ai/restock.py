"""Feature 2: restock prediction.

How it works:
  daily sales rate = units sold in the last N days / N
  days of stock left = current stock / daily sales rate
A simple moving average: easy to explain and it needs no training data.
"""


def days_left(stock, units_sold, window_days=28):
    """Returns estimated days until stock runs out, or None if there were no recent sales."""
    if units_sold <= 0:
        return None
    daily_rate = units_sold / window_days
    return stock / daily_rate


def restock_status(days):
    if days is None:
        return "No recent sales"
    if days <= 7:
        return "Restock now"
    if days <= 14:
        return "Restock soon"
    return "OK"
