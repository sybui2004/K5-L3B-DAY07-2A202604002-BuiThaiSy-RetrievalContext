import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agent import AgentConfig
from demo.live import LiveDeps, METHODS, compare_methods, dev_questions, list_configs, rerank_breakdown, rrf_breakdown, run_live
from demo.traces import DATASETS

SECRET = "sk-SECRET-123"
CHUNKS = [{"id": "c1", "text": "alpha", "source_id": "s", "source": "s.pdf", "page": 1,
           "metadata": {"kind": "table", "bbox": [1, 2, 3, 4], "image_path": None}},
          {"id": "c2", "text": "beta", "source_id": "s", "source": "s.pdf", "page": 2,
           "metadata": {"kind": "text", "bbox": None, "image_path": None}}]


class FakeCfg:
    deepseek_api_key = SECRET
    database_url = "postgresql://u:p@h/db"


class FakeRetriever:
    def __init__(self, fail=False):
        self.fail = fail

    def search(self, query, *, filters, top_k):
        if self.fail:
            raise OSError(f"cannot connect with {SECRET}")
        return [{**c, "score": 0.9 - i / 10} for i, c in enumerate(CHUNKS[:top_k])]


class FakeController:
    def __init__(self):
        self.calls = 0

    def pop_usage(self):
        return {"tokens_in": 7, "tokens_out": 3, "calls": 2, "seconds": 0.0}

    def decide(self, question, history, allow_search=True):
        self.calls += 1
        if not history:
            return {"action": "search", "query": question}
        return {"action": "answer", "answer": "alpha [c1]", "citations": ["c1"]}


def make_deps(**over):
    base = dict(load_config=lambda: FakeCfg(), build_retriever=lambda ds, m, cfg: FakeRetriever(),
                load_chunks=lambda ds, cfg: CHUNKS, make_controller=lambda ds, cfg, acfg: FakeController(),
                secrets=lambda: [SECRET])
    base.update(over)
    return LiveDeps(**base)


ACFG = AgentConfig(name="t", method="dense", top_k=2, max_searches=1, budget_chars=3000, neighbors=False, rewrite=False)


class DemoLiveTests(unittest.TestCase):
    def test_run_live_returns_answered_trace_with_citation(self):
        t = run_live("bonus", "alpha?", ACFG, deps=make_deps())
        self.assertEqual((t["status"], t["citations"], t["tokens_in"]), ("answered", ["c1"], 7))
        self.assertEqual(t["citation_regions"][0]["kind"], "table")
        self.assertEqual(t["split"], "live")

    def test_run_live_missing_env_returns_error_trace_without_secret(self):
        def boom():
            raise ValueError(f"missing environment variables: DATABASE_URL ({SECRET})")
        t = run_live("basic", "x", ACFG, deps=make_deps(load_config=boom))
        self.assertEqual(t["status"], "error")
        self.assertNotIn(SECRET, t["error"])

    def test_run_live_db_down_returns_error_trace(self):
        def down(ds, m, cfg):
            raise OSError(f"connection refused {SECRET}")
        t = run_live("basic", "x", ACFG, deps=make_deps(build_retriever=down))
        self.assertEqual(t["status"], "error")
        self.assertIn("OSError", t["error"])
        self.assertNotIn(SECRET, t["error"])

    def test_compare_methods_isolates_failure_per_method(self):
        def build(ds, m, cfg):
            return FakeRetriever(fail=(m == "bm25"))
        out = compare_methods("basic", "q", top_k=2, deps=make_deps(build_retriever=build))
        self.assertEqual(list(out), list(METHODS["basic"]))
        self.assertIsInstance(out["bm25"], str)
        self.assertNotIn(SECRET, out["bm25"])
        self.assertEqual([r["rank"] for r in out["dense"]], [1, 2])
        self.assertEqual(out["hybrid"][0]["id"], "c1")

    def test_list_configs_reads_json_files(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "configs").mkdir()
            (Path(d) / "configs" / "a.json").write_text(json.dumps(
                {"name": "a", "method": "hybrid", "top_k": 3, "max_searches": 2, "budget_chars": 100,
                 "neighbors": False, "rewrite": True}), encoding="utf-8")
            (Path(d) / "configs" / "notes.md").write_text("x", encoding="utf-8")
            cfgs = list_configs(DATASETS["basic"], Path(d))
            self.assertEqual(list(cfgs), ["a"])
            self.assertEqual(cfgs["a"].method, "hybrid")

    def test_dev_questions_never_returns_test_split(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "benchmark").mkdir()
            qs = [{"id": "a", "split": "dev"}, {"id": "b", "split": "test"}, {"id": "c", "split": "retired"}]
            (Path(d) / "benchmark" / "questions.json").write_text(json.dumps(qs), encoding="utf-8")
            self.assertEqual([q["id"] for q in dev_questions(DATASETS["basic"], Path(d))], ["a"])

    def test_rrf_breakdown_shows_rank_and_score_from_each_side(self):
        def chunk(i):
            return {"id": i, "page": 1, "text": i, "metadata": {}}

        class Side:
            def __init__(self, ids):
                self.ids = ids

            def search(self, query, *, filters, top_k):
                return [chunk(i) for i in self.ids[:top_k]]

        class Hybrid:
            dense, lexical, k, pool = Side(["c1", "c2"]), Side(["c2", "c3"]), 60, 20

        rows = rrf_breakdown("basic", "q", top_k=3, deps=make_deps(build_retriever=lambda ds, m, cfg: Hybrid()))
        self.assertEqual([r["id"] for r in rows], ["c2", "c1", "c3"])
        c2 = rows[0]
        self.assertEqual((c2["dense_rank"], c2["lexical_rank"]), (2, 1))
        self.assertAlmostEqual(c2["score"], 1 / 62 + 1 / 61)
        self.assertAlmostEqual(c2["rrf_dense"] + c2["rrf_lexical"], c2["score"])
        self.assertIsNone(rows[1]["lexical_rank"])
        self.assertEqual(rows[1]["rrf_lexical"], 0.0)

    def test_rrf_breakdown_returns_scrubbed_error_string(self):
        def down(ds, m, cfg):
            raise OSError(f"refused {SECRET}")
        out = rrf_breakdown("basic", "q", deps=make_deps(build_retriever=down))
        self.assertIsInstance(out, str)
        self.assertNotIn(SECRET, out)

    def test_rerank_breakdown_shows_rank_before_and_after(self):
        def chunk(i):
            return {"id": i, "page": 1, "text": f"t{i}", "metadata": {}}

        class Base:
            def search(self, query, *, filters, top_k):
                return [chunk(i) for i in ["c1", "c2", "c3"][:top_k]]

        class Rerank:
            base, pool = Base(), 20
            scorer = staticmethod(lambda q, texts: [{"tc1": 0.1, "tc2": 0.9, "tc3": 0.5}[t] for t in texts])

        rows = rerank_breakdown("basic", "q", top_k=2, deps=make_deps(build_retriever=lambda ds, m, cfg: Rerank()))
        self.assertEqual([r["id"] for r in rows], ["c2", "c3"])
        self.assertEqual((rows[0]["rank_before"], rows[0]["rank_after"]), (2, 1))
        self.assertEqual((rows[1]["rank_before"], rows[1]["rank_after"]), (3, 2))
        self.assertAlmostEqual(rows[0]["score"], 0.9)

    def test_rerank_breakdown_returns_scrubbed_error_string(self):
        def down(ds, m, cfg):
            raise OSError(f"refused {SECRET}")
        out = rerank_breakdown("basic", "q", deps=make_deps(build_retriever=down))
        self.assertIsInstance(out, str)
        self.assertNotIn(SECRET, out)

    def test_basic_methods_include_rerank(self):
        self.assertIn("hybrid-rerank", METHODS["basic"])
        self.assertNotIn("hybrid-rerank", METHODS["bonus"])


if __name__ == "__main__":
    unittest.main()
