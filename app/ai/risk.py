"""Feature 4: risky-order flags.

How it works: a rule-based risk score. Each suspicious signal adds points.
An order with score >= FLAG_THRESHOLD goes to the admin review queue, with the reasons listed.
"""

FLAG_THRESHOLD = 40


def risk_score(max_line_qty, total_amount, orders_last_hour, failed_payments_24h):
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
    return score, "; ".join(reasons)


def is_flagged(score):
    return score >= FLAG_THRESHOLD
