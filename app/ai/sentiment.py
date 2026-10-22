"""Feature 3: review sentiment.

How it works (a small lexicon-based model, no external library):
  - Count positive words (+1) and negative words (-1) in the review.
  - A negation word right before a sentiment word flips it ("not good" -> negative).
  - score = (sum of word values) / (number of sentiment words), from -1 to +1.
  - > 0.2 positive, < -0.2 negative, otherwise neutral.
  - If the text has no sentiment words, fall back to the star rating.
(To upgrade later, swap analyze() for VADER: same inputs and outputs.)
"""
import re

POSITIVE = {
    "good", "great", "excellent", "amazing", "awesome", "love", "loved", "perfect", "best",
    "worth", "nice", "fast", "comfortable", "happy", "recommend", "superb", "fantastic",
    "wonderful", "quality", "durable", "satisfied", "value",
}
NEGATIVE = {
    "bad", "poor", "terrible", "worst", "waste", "broke", "broken", "stopped", "slow", "cheap",
    "disappointed", "disappointing", "awful", "horrible", "useless", "defective", "damaged",
    "late", "fake", "hate", "refund", "uncomfortable",
}
NEGATORS = {"not", "no", "never", "hardly", "isn't", "wasn't", "don't", "didn't", "cannot", "can't", "without"}


def analyze(text, rating=None):
    """Returns (label, score) where label is 'positive' / 'neutral' / 'negative'."""
    words = re.findall(r"[a-z']+", (text or "").lower())
    total, hits = 0, 0
    for i, word in enumerate(words):
        value = 1 if word in POSITIVE else -1 if word in NEGATIVE else 0
        if value:
            if i > 0 and words[i - 1] in NEGATORS:
                value = -value
            total += value
            hits += 1

    if hits:
        score = total / hits
    elif rating is not None:
        score = {5: 1.0, 4: 1.0, 3: 0.0, 2: -1.0, 1: -1.0}.get(rating, 0.0)
    else:
        score = 0.0

    label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
    return label, round(score, 2)
