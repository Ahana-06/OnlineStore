"""Feature 1: explainable recommendations ("bought together").

How it works (say this in the review):
  1. Every past order is a "basket" = the set of products in it.
  2. For the product being viewed, count how many baskets ALSO contain each other product.
  3. The products with the highest counts are recommended, and the count is shown as the reason.
No black box: the reason is just "bought together in N orders".
"""
from collections import Counter


def recommend(baskets, product_id, top_n=3):
    """baskets: list of sets of product ids. Returns [(other_product_id, times_bought_together), ...]"""
    counts = Counter()
    for basket in baskets:
        if product_id in basket:
            for other in basket:
                if other != product_id:
                    counts[other] += 1
    return counts.most_common(top_n)
