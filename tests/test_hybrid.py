import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrievers import HybridRetriever


def c(i):
    return {"id": i, "text": i, "source_id": "s", "source": "s", "page": 1, "metadata": {}}


class Fake:
    def __init__(self, ids):
        self.ids, self.calls = ids, []

    def search(self, query, *, filters, top_k):
        self.calls.append((query, filters, top_k))
        return [{**c(i), "score": 1.0 / (n + 1)} for n, i in enumerate(self.ids[:top_k])]


class HybridTests(unittest.TestCase):
    def test_rrf_ranks_item_in_both_lists_first(self):
        h = HybridRetriever(Fake(["a", "b", "c"]), Fake(["x", "b", "y"]))
        self.assertEqual(h.search("q", filters=None, top_k=3)[0]["id"], "b")

    def test_duplicate_ids_merged(self):
        h = HybridRetriever(Fake(["a", "b"]), Fake(["b", "a"]))
        ids = [r["id"] for r in h.search("q", filters=None, top_k=5)]
        self.assertEqual(sorted(ids), ["a", "b"])

    def test_top_k_respected_and_pool_used(self):
        d, l = Fake(list("abcdef")), Fake(list("uvwxyz"))
        h = HybridRetriever(d, l, pool=4)
        self.assertEqual(len(h.search("q", filters=None, top_k=2)), 2)
        self.assertEqual(d.calls[0][2], 4)
        self.assertEqual(l.calls[0][2], 4)

    def test_rrf_score_matches_formula(self):
        h = HybridRetriever(Fake(["a"]), Fake(["a"]), k=60)
        self.assertAlmostEqual(h.search("q", filters=None, top_k=1)[0]["score"], 2 / 61)

    def test_filters_forwarded_to_both(self):
        d, l = Fake(["a"]), Fake(["a"])
        HybridRetriever(d, l).search("q", filters={"version": "2012"}, top_k=1)
        self.assertEqual(d.calls[0][1], {"version": "2012"})
        self.assertEqual(l.calls[0][1], {"version": "2012"})


if __name__ == "__main__":
    unittest.main()
