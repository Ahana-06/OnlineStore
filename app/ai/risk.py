"""Feature 4: risky-order flags.

How it works: a rule-based risk score. Each suspicious signal adds points.
An order with score >= FLAG_THRESHOLD goes to the admin review queue, with the reasons listed.

Signals: very large quantity (+40), high order value (+20), many orders in one hour (+30),
failed payments (+30), brand-new account placing a big order (+25).
"""

FLAG_THRESHOLD = 40
NEW_ACCOUNT_HOURS = 24        # an account younger than this counts as "new"
NEW_ACCOUNT_MIN_TOTAL = 5000  # ...but only big orders from new accounts add risk


def risk_score(max_line_qty, total_amount, orders_last_hour, failed_payments_24h,
               account_age_hours=None):
    """account_age_hours is optional (None = unknown, the rule is skipped), so older callers still work."""
    score, reasons = 0, []
    if max_line_qty >= 10:
        score += 40
        reasons.append(f"Very large quantity ({max_line_qty} units of one item)")
    if total_amount >= 20000:
        score += 20
        reasons.append(f"High order value (Rs {total_amount:,.0f})")
    if orders_last_hour >= 3:
        score += 30
        reasons.append(f"{orders_last_hour} orders within one hour")
    if failed_payments_24h >= 2:
        score += 30
        reasons.append(f"{failed_payments_24h} failed payments in 24 hours")
    if (account_age_hours is not None and account_age_hours < NEW_ACCOUNT_HOURS
            and total_amount >= NEW_ACCOUNT_MIN_TOTAL):
        score += 25
        reasons.append(f"New account ({account_age_hours:.0f}h old) placing a Rs {total_amount:,.0f} order")
    return score, "; ".join(reasons)


def is_flagged(score):
    return score >= FLAG_THRESHOLD
