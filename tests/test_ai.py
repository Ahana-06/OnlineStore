"""Tests for the AI functions in app/ai/ (pure Python, no database)."""
import pytest

from app.ai.nlsearch import parse_query
from app.ai.recommend import recommend
from app.ai.restock import days_left, restock_status
from app.ai.risk import FLAG_THRESHOLD, is_flagged, risk_score
from app.ai.sentiment import analyze


# ------------------------------------------------------------ sentiment
@pytest.mark.parametrize("text, label", [
    ("Excellent quality, totally worth it!", "positive"),
    ("Terrible, waste of money.", "negative"),
    ("It is okay, nothing special.", "neutral"),
    ("not good", "negative"),                 # negation flips
    ("paisa vasool", "positive"),             # phrase
    ("value for money", "positive"),          # phrase
    ("not value for money", "negative"),      # negated phrase
    ("not worth it", "negative"),
])
def test_sentiment_labels(text, label):
    assert analyze(text)[0] == label


def test_intensifier_doubles_weight():
    # without the intensifier the two words cancel out
    assert analyze("good, slow")[1] == 0
    assert analyze("very good, slow")[0] == "positive"
    assert analyze("good, extremely slow")[0] == "negative"


def test_negated_intensifier_is_not_doubled():
    # "not very good" counts as a normal negative word, not a doubled one
    assert analyze("not very good, fast")[1] == 0


def test_clause_after_but_weighs_more():
    assert analyze("nice design but stopped working")[0] == "negative"
    assert analyze("slow delivery but really good")[0] == "positive"
    assert analyze("good but bad")[0] == "negative"
    assert analyze("bad but good")[0] == "positive"


def test_sentiment_falls_back_to_rating():
    assert analyze("arrived on Tuesday", rating=5) == ("positive", 1.0)
    assert analyze("arrived on Tuesday", rating=1) == ("negative", -1.0)
    assert analyze("", rating=None) == ("neutral", 0.0)


def test_sentiment_score_stays_in_range():
    for text in ["very very good", "extremely bad but really really good", "paisa vasool must buy"]:
        assert -1 <= analyze(text)[1] <= 1


# ------------------------------------------------------------ risk
def test_normal_order_is_not_risky():
    assert risk_score(1, 1500, 1, 0) == (0, "")


def test_large_quantity_alone_is_flagged():
    score, reason = risk_score(12, 3000, 1, 0)
    assert score == 40 and is_flagged(score)
    assert "12 units" in reason


def test_new_account_big_order_adds_25():
    score, reason = risk_score(1, 6000, 1, 0, account_age_hours=3)
    assert score == 25
    assert "New account" in reason


@pytest.mark.parametrize("age, total", [(30, 6000), (3, 4999), (None, 6000)])
def test_new_account_rule_needs_young_account_and_big_order(age, total):
    assert risk_score(1, total, 1, 0, account_age_hours=age)[0] == 0


def test_new_account_rule_combines_with_others():
    score, reason = risk_score(1, 25000, 1, 0, account_age_hours=1)   # 20 + 25
    assert score == 45 and score >= FLAG_THRESHOLD
    assert "High order value" in reason and "New account" in reason


def test_risk_score_old_call_style_still_works():
    # seed.py calls it with 4 positional arguments
    assert risk_score(25, 8725, 0, 0)[0] == 40


# ------------------------------------------------------------ the other AI helpers
def test_recommend_counts_baskets():
    baskets = [{1, 2}, {1, 2, 3}, {1, 3}, {2, 4}]
    assert recommend(baskets, 1) == [(2, 2), (3, 2)]


def test_restock():
    assert days_left(10, 28, 28) == 10
    assert days_left(10, 0) is None
    assert restock_status(5) == "Restock now"
    assert restock_status(10) == "Restock soon"
    assert restock_status(30) == "OK"
    assert restock_status(None) == "No recent sales"


def test_nl_search():
    assert parse_query("wireless earbuds under 2000") == (["wireless", "earbuds"], None, 2000.0)
    assert parse_query("shoes between 500 and 1500") == (["shoes"], 500.0, 1500.0)
