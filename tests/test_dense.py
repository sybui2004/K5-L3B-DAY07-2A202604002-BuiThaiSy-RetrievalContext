import sys
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import Config, load_config
from src.retrievers import DenseRetriever


def _cfg(db="postgresql://x:y@127.0.0.1:1/none"):
    return Config("k", "http://b", "m", db, "http://127.0.0.1:1", "bge-m3")


def _live_cfg():
    try:
        cfg = load_config()
        import psycopg
        psycopg.connect(cfg.database_url, connect_timeout=3).close()
        import requests
        requests.get(cfg.ollama_url + "/api/tags", timeout=3).raise_for_status()
        return cfg
    except Exception:
        return None


class DenseValidationTests(unittest.TestCase):
    def test_search_rejects_empty_query(self):
        r = DenseRetriever(_cfg(), embed=lambda q, c: self.fail("must not embed"))
        with self.assertRaises(ValueError):
            r.search("   ", filters=None, top_k=3)

    def test_search_rejects_top_k_below_one(self):
        r = DenseRetriever(_cfg(), embed=lambda q, c: self.fail("must not embed"))
        with self.assertRaises(ValueError):
            r.search("lương", filters=None, top_k=0)

    def test_search_rejects_unknown_filter_value(self):
        r = DenseRetriever(_cfg(), embed=lambda q, c: self.fail("must not embed"))
        with self.assertRaises(ValueError):
            r.search("lương", filters={"version": "2020"}, top_k=3)

    def test_query_is_nfc_normalized_before_embedding(self):
        seen = []

        def spy(q, c):
            seen.append(q)
            raise RuntimeError("stop after embed")  # keep the DB out of this unit test

        r = DenseRetriever(_cfg(), embed=spy)
        nfd = unicodedata.normalize("NFD", "tiền lương")
        with self.assertRaisesRegex(RuntimeError, "stop after embed"):
            r.search(nfd, filters=None, top_k=3)
        self.assertEqual(seen, [unicodedata.normalize("NFC", nfd)])


@unittest.skipUnless(_live_cfg(), "Day 6 Postgres + Ollama not reachable (start Docker/Ollama)")
class DenseLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = DenseRetriever(_live_cfg())

    def test_dense_top3_returns_unique_ids_and_scores_desc(self):
        res = self.r.search("Thời giờ làm việc bình thường tối đa bao nhiêu giờ một ngày?", filters=None, top_k=3)
        self.assertEqual(len(res), 3)
        self.assertEqual(len({x["id"] for x in res}), 3)
        scores = [x["score"] for x in res]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for x in res:
            self.assertTrue(x["text"] and x["source_id"] and x["page"])

    def test_version_filter_only_returns_that_version(self):
        res = self.r.search("thời giờ làm việc", filters={"version": "2012"}, top_k=5)
        self.assertTrue(res)
        self.assertTrue(all(x["metadata"]["version"] == "2012" and x["source_id"] == "blld-2012" for x in res))


if __name__ == "__main__":
    unittest.main()
