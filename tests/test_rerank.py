import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrievers import RerankRetriever


def c(i):
    return {"id": i, "text": f"text {i}", "source_id": "s", "source": "s", "page": 1, "metadata": {}}


class Base:
    def __init__(self, ids):
        self.ids, self.calls = ids, []

    def search(self, query, *, filters, top_k):
        self.calls.append((query, filters, top_k))
        return [{**c(i), "score": 1.0 / (n + 1)} for n, i in enumerate(self.ids[:top_k])]


class RerankTests(unittest.TestCase):
    def test_reorders_by_scorer_and_keeps_top_k(self):
        scores = {"text a": 0.1, "text b": 0.9, "text c": 0.5}
        r = RerankRetriever(Base(["a", "b", "c"]), scorer=lambda q, texts: [scores[t] for t in texts], pool=3)
        out = r.search("q", filters=None, top_k=2)
        self.assertEqual([x["id"] for x in out], ["b", "c"])
        self.assertEqual(out[0]["score"], 0.9)

    def test_fetches_pool_not_top_k_and_passes_filters(self):
        base = Base(list("abcdef"))
        r = RerankRetriever(base, scorer=lambda q, t: [0.0] * len(t), pool=5)
        r.search("q", filters={"version": "2019"}, top_k=2)
        self.assertEqual(base.calls, [("q", {"version": "2019"}, 5)])

    def test_pool_never_smaller_than_top_k(self):
        base = Base(list("abcdef"))
        r = RerankRetriever(base, scorer=lambda q, t: [0.0] * len(t), pool=2)
        self.assertEqual(len(r.search("q", filters=None, top_k=4)), 4)
        self.assertEqual(base.calls[0][2], 4)

    def test_empty_candidates(self):
        r = RerankRetriever(Base([]), scorer=lambda q, t: [])
        self.assertEqual(r.search("q", filters=None, top_k=3), [])

    def test_rejects_bad_top_k(self):
        with self.assertRaises(ValueError):
            RerankRetriever(Base(["a"]), scorer=lambda q, t: [0.0]).search("q", filters=None, top_k=0)


if __name__ == "__main__":
    unittest.main()
