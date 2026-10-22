"""Feature 5: natural-language search.

"wireless earbuds under 2000"  ->  keywords ['wireless', 'earbuds'], max price 2000
How it works: regular expressions pull out price phrases ("under 2000", "above 500",
"between 500 and 1500"); the remaining words are keywords that must each match the
product name, description or category.
"""
import re

STOPWORDS = {"a", "an", "the", "for", "me", "show", "find", "i", "want", "need", "best", "good", "with", "and", "of", "to", "in"}
NUM = r"(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)"


def parse_query(q):
    """Returns (keywords, min_price, max_price)."""
    text = (q or "").lower()
    min_price = max_price = None

    m = re.search(r"between\s*" + NUM + r"\s*(?:and|to|-)\s*" + NUM, text)
    if m:
        min_price, max_price = float(m.group(1)), float(m.group(2))
        text = text.replace(m.group(0), " ")

    m = re.search(r"(?:under|below|less than|cheaper than|upto|up to|within|max)\s*" + NUM, text)
    if m:
        max_price = float(m.group(1))
        text = text.replace(m.group(0), " ")

    m = re.search(r"(?:above|over|more than|at least|min)\s*" + NUM, text)
    if m:
        min_price = float(m.group(1))
        text = text.replace(m.group(0), " ")

    words = re.findall(r"[a-z0-9]+", text)
    keywords = [w for w in words if w not in STOPWORDS]
    return keywords, min_price, max_price


def stem(word):
    """Very small plural fix so 'shoes' matches 'Shoe' and 'socks' matches 'Sock'."""
    return word[:-1] if len(word) > 3 and word.endswith("s") else word
