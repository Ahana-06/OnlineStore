"""Feature 3: review sentiment.

How it works (a small lexicon-based model, no external library):
  - Count positive words (+1) and negative words (-1) in the review.
  - Phrases count as one sentiment word ("paisa vasool", "value for money" -> positive).
  - A negation word right before a sentiment word flips it ("not good" -> negative).
  - An intensifier right before a sentiment word doubles its weight ("very good").
    "not very good" is only mildly negative, so a negated intensifier is NOT doubled.
  - Words after "but" count double: "nice design but stopped working" is mainly negative.
  - score = (sum of weighted values) / (sum of weights), from -1 to +1.
  - > 0.2 positive, < -0.2 negative, otherwise neutral.
  - If the text has no sentiment words, fall back to the star rating.
(To upgrade later, swap analyze() for VADER: same inputs and outputs.)
"""
import re

POSITIVE = {
    "good", "great", "excellent", "amazing", "awesome", "love", "loved", "perfect", "best",
    "worth", "nice", "fast", "comfortable", "happy", "recommend", "superb", "fantastic",
    "wonderful", "quality", "durable", "satisfied", "value",
    "sturdy", "reliable", "genuine", "smooth", "beautiful", "impressed",
}
NEGATIVE = {
    "bad", "poor", "terrible", "worst", "waste", "broke", "broken", "stopped", "slow", "cheap",
    "disappointed", "disappointing", "awful", "horrible", "useless", "defective", "damaged",
    "late", "fake", "hate", "refund", "uncomfortable",
    "overpriced", "flimsy", "faulty", "leaking", "leaks",
}
# multi-word phrases, matched before the single words (each counts as ONE sentiment word)
PHRASES = {
    "paisa vasool": 1,
    "value for money": 1,
    "must buy": 1,
    "worth every penny": 1,
    "waste of money": -1,
    "not worth it": -1,
    "stopped working": -1,
}
NEGATORS = {"not", "no", "never", "hardly", "isn't", "wasn't", "don't", "didn't", "cannot", "can't", "without"}
INTENSIFIERS = {"very", "really", "extremely", "highly"}
INTENSIFIER_WEIGHT = 2
CONTRAST_WORD = "but"
CONTRAST_WEIGHT = 2


def _tokens(text):
    """Lower-case words, with each known phrase replaced by a single placeholder token."""
    text = (text or "").lower()
    for i, phrase in enumerate(sorted(PHRASES, key=len, reverse=True)):  # longest first
        text = re.sub(r"\b" + re.escape(phrase) + r"\b", f" phrase{i} ", text)
    return re.findall(r"[a-z0-9']+", text)


def _phrase_values():
    return {f"phrase{i}": PHRASES[p] for i, p in enumerate(sorted(PHRASES, key=len, reverse=True))}


def _word_value(word, phrase_values):
    if word in phrase_values:
        return phrase_values[word]
    return 1 if word in POSITIVE else -1 if word in NEGATIVE else 0


def analyze(text, rating=None):
    """Returns (label, score) where label is 'positive' / 'neutral' / 'negative'."""
    words = _tokens(text)
    phrase_values = _phrase_values()
    # everything after the LAST "but" gets the contrast weight
    contrast_from = max((i for i, w in enumerate(words) if w == CONTRAST_WORD), default=None)

    total, weight_sum = 0.0, 0.0
    for i, word in enumerate(words):
        value = _word_value(word, phrase_values)
        if not value:
            continue
        weight = 1
        j = i - 1
        intensified = j >= 0 and words[j] in INTENSIFIERS
        if intensified:
            j -= 1
        negated = j >= 0 and words[j] in NEGATORS
        if negated:
            value = -value
        elif intensified:
            weight *= INTENSIFIER_WEIGHT
        if contrast_from is not None and i > contrast_from:
            weight *= CONTRAST_WEIGHT
        total += value * weight
        weight_sum += weight

    if weight_sum:
        score = total / weight_sum
    elif rating is not None:
        score = {5: 1.0, 4: 1.0, 3: 0.0, 2: -1.0, 1: -1.0}.get(rating, 0.0)
    else:
        score = 0.0

    label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
    return label, round(score, 2)
