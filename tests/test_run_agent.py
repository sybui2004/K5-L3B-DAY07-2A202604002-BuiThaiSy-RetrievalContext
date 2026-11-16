import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.run_agent import load_agent_config, summarize_run


class RunAgentTests(unittest.TestCase):
    def test_load_agent_config_reads_all_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text(json.dumps({"name": "x", "method": "hybrid", "top_k": 5, "max_searches": 2,
                                     "budget_chars": 100, "neighbors": True, "rewrite": False}), encoding="utf-8")
            c = load_agent_config(p)
        self.assertEqual((c.name, c.method, c.top_k, c.neighbors), ("x", "hybrid", 5, True))

    def test_load_agent_config_rejects_unknown_method(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text(json.dumps({"name": "x", "method": "magic", "top_k": 5, "max_searches": 2,
                                     "budget_chars": 100, "neighbors": True, "rewrite": False}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_agent_config(p)

    def test_summarize_run_has_time_tokens_status_counts(self):
        traces = [{"query_id": "q1", "status": "answered", "searches": 1, "seconds": 2.0, "tokens_in": 100,
                   "tokens_out": 10, "context_ids": [], "citations": ["a"], "events": []},
                  {"query_id": "q2", "status": "error", "searches": 0, "seconds": 1.0, "tokens_in": 0,
                   "tokens_out": 0, "context_ids": [], "citations": [], "events": []}]
        qs = [{"id": "q1", "split": "dev", "question": "?", "gold": [{"source_id": "s", "page": 1, "evidence": "e"}]},
              {"id": "q2", "split": "dev", "question": "?", "gold": [{"source_id": "s", "page": 1, "evidence": "e"}]}]
        s = summarize_run(traces, qs, {})
        self.assertEqual(s["status_counts"], {"answered": 1, "error": 1})
        self.assertEqual((s["tokens_in"], s["tokens_out"], s["seconds_total"]), (100, 10, 3.0))
        self.assertEqual(s["context_evidence_rate"], {"n": 0, "N": 2})


if __name__ == "__main__":
    unittest.main()
