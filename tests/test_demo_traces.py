import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo.traces import (DATASETS, cited_images, context_blocks, agent_compare_rows, describe_config, list_runs, retrieval_compare_rows, load_questions_by_id,
                         load_run, run_label, run_meta, search_rounds, trace_overview)

ANSWERED = {
    "query_id": "q01", "split": "dev", "config": "c", "status": "answered", "answer": "A [x1]", "citations": ["x1"],
    "events": [
        {"event": "search", "query": "q a", "filter": None,
         "results": [{"id": "x1", "score": 0.9, "page": 3}, {"id": "x2", "score": 0.5, "page": 4}],
         "context_ids": ["x1"]},
        {"event": "search", "query": "q b", "filter": None,
         "results": [{"id": "x3", "score": None, "page": 5}], "context_ids": ["x1", "x3"]},
        {"event": "answer"}],
    "searches": 2, "context": "[x1 | s | page 3]\ntext one\n\n[x3 | s | page 5]\ntext three", "context_ids": ["x1", "x3"],
    "error": None, "seconds": 1.5, "tokens_in": 10, "tokens_out": 5, "llm_calls": 3,
}
ERRORED = {"query_id": "q02", "split": "dev", "config": "c", "status": "error", "answer": None, "citations": [],
           "events": [], "searches": 0, "context": "", "context_ids": [], "error": "LlmError: boom", "seconds": 0.2}


def make_run(root: Path, name: str, *, audit: str | None = None, summary: bool = True, nested: str = "") -> Path:
    run = root / "results" / "agent" / nested / name if nested else root / "results" / "agent" / name
    run.mkdir(parents=True)
    (run / "traces.json").write_text(json.dumps([ANSWERED, ERRORED]), encoding="utf-8")
    if summary:
        (run / "summary.json").write_text(json.dumps({"n_questions": 2}), encoding="utf-8")
    (run / "config.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    if audit is not None:
        (run / "audit").mkdir()
        (run / "audit" / ("pass_fail.csv" if "pass_fail" in audit.split("\n")[0] else "answer_audit.csv")).write_bytes(
            audit.encode("utf-8-sig"))
    return run


class DemoTracesTests(unittest.TestCase):
    def test_list_runs_finds_nested_run_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_run(root, "a")
            make_run(root, "b", nested="_history")
            (root / "results" / "agent" / "empty").mkdir()
            names = [p.name for p in list_runs(DATASETS["basic"], root)]
            self.assertEqual(names, ["a", "b"])

    def test_load_run_without_audit_or_summary_returns_empty_labels(self):
        with tempfile.TemporaryDirectory() as d:
            run = make_run(Path(d), "a", summary=False)
            loaded = load_run(run)
            self.assertEqual((loaded["labels"], loaded["summary"], len(loaded["traces"])), ({}, {}, 2))

    def test_load_run_reads_basic_and_bonus_label_columns(self):
        with tempfile.TemporaryDirectory() as d:
            basic = make_run(Path(d), "a", audit="query_id,answer_grade_0_2,reason\nq01,2,tốt\n")
            bonus = make_run(Path(d), "b", audit="query_id,pass_fail,reason\nq01,pass,ok\n")
            self.assertEqual(load_run(basic)["labels"], {"q01": {"label": "2", "reason": "tốt"}})
            self.assertEqual(load_run(bonus)["labels"], {"q01": {"label": "pass", "reason": "ok"}})

    def test_search_rounds_marks_in_context_and_rank_starts_at_1(self):
        rounds = search_rounds(ANSWERED)
        self.assertEqual([(r["rank"], r["id"], r["in_context"]) for r in rounds[0]["results"]],
                         [(1, "x1", True), (2, "x2", False)])
        self.assertEqual(rounds[1]["query"], "q b")

    def test_trace_overview_handles_error_trace(self):
        rows = trace_overview([ANSWERED, ERRORED], {"q01": {"label": "2", "reason": ""}},
                              {"q01": {"type": "truc_tiep"}, "q02": {"group": "table"}})
        self.assertEqual((rows[1]["status"], rows[1]["tokens"], rows[1]["type"]), ("error", 0, "table"))
        self.assertEqual((rows[0]["tokens"], rows[0]["label"], rows[0]["type"]), (15, "2", "truc_tiep"))

    def test_context_blocks_splits_on_chunk_headers(self):
        blocks = context_blocks(ANSWERED)
        self.assertEqual([(b["id"], b["text"]) for b in blocks], [("x1", "text one"), ("x3", "text three")])
        self.assertEqual(blocks[0]["header"], "x1 | s | page 3")
        self.assertEqual(context_blocks(ERRORED), [])

    def test_cited_images_skips_none_and_missing_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bonus" / "data" / "figures").mkdir(parents=True)
            (root / "bonus" / "data" / "figures" / "f.png").write_bytes(b"x")
            t = {"citation_regions": [{"id": "a", "image": None},
                                      {"id": "b", "image": "bonus/data/figures/missing.png"},
                                      {"id": "c", "image": "bonus/data/figures/f.png"}]}
            self.assertEqual(cited_images(t, DATASETS["bonus"], root), [root / "bonus" / "data" / "figures" / "f.png"])
            self.assertEqual(cited_images(t, DATASETS["basic"], root), [])
            self.assertEqual(cited_images({}, DATASETS["bonus"], root), [])

    def test_load_questions_by_id_indexes_by_id(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "benchmark"
            p.mkdir()
            (p / "questions.json").write_text(json.dumps([{"id": "q01", "split": "dev"}]), encoding="utf-8")
            self.assertEqual(list(load_questions_by_id(DATASETS["basic"], Path(d))), ["q01"])

    def test_describe_config_in_vietnamese(self):
        text = describe_config({"method": "hybrid", "top_k": 8, "max_searches": 4, "budget_chars": 12000,
                                "neighbors": False, "rewrite": True, "pack": "round_robin", "figure_reader": True})
        for part in ("hybrid", "top-8", "tối đa 4 lượt tìm", "12000", "round-robin", "đọc hình"):
            self.assertIn(part, text)
        self.assertEqual(describe_config({}), "chưa có config.json")

    def test_run_meta_and_label_show_split_and_pass_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = make_run(root, "x-dev", audit="query_id,pass_fail,reason\nq01,pass,ok\nq02,fail,no\n")
            (run / "summary.json").write_text(json.dumps({"split": "dev", "n_questions": 2}), encoding="utf-8")
            meta = run_meta(run)
            self.assertEqual((meta["split"], meta["n"], meta["passed"], meta["labeled"]), ("dev", 2, 1, 2))
            self.assertEqual(run_label(run, root / "results" / "agent", meta), "x-dev · dev · 2 câu · đạt 1/2")
            bare = make_run(root, "y", summary=False, nested="_history")
            self.assertEqual(run_label(bare, root / "results" / "agent", run_meta(bare)), "[lịch sử] _history/y")


class RetrievalDescriptionTests(unittest.TestCase):
    def test_dense_basic_mentions_semantic_and_metadata(self):
        from demo.traces import describe_retrieval
        text = "\n".join(describe_retrieval({"method": "dense", "top_k": 5, "max_searches": 1, "budget_chars": 6000,
                                              "neighbors": True}, "basic"))
        self.assertIn("Ngữ nghĩa", text)
        self.assertIn("top-5", text)
        self.assertIn("Điều liền kề", text)
        self.assertIn("Metadata", text)

    def test_bonus_has_no_version_metadata_line_and_empty_config_is_empty(self):
        from demo.traces import describe_retrieval
        self.assertNotIn("Metadata", "\n".join(describe_retrieval({"method": "hybrid"}, "bonus")))
        self.assertEqual(describe_retrieval({}, "basic"), [])

    def test_trace_filter_reads_first_search_event(self):
        from demo.traces import trace_filter
        self.assertIsNone(trace_filter(ANSWERED))
        with_filter = {"events": [{"event": "search", "filter": {"version": "2012"}}]}
        self.assertEqual(trace_filter(with_filter), {"version": "2012"})


class CompareTests(unittest.TestCase):
    def test_retrieval_rows_read_summaries_and_order_by_method(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "results" / "retrieval"
            for name, h1, h3 in (("hybrid-dev", 14, 14), ("dense-dev", 13, 14), ("hybrid-rerank-dev", 15, 15)):
                (base / name).mkdir(parents=True)
                (base / name / "summary.json").write_text(json.dumps(
                    {"method": name[:-4], "hit1": h1, "hit3": h3, "n": 15, "seconds_total": 1.5}), encoding="utf-8")
            (base / "junk-dev").mkdir()
            rows = retrieval_compare_rows(Path(d))
            self.assertEqual([r["method"] for r in rows], ["dense", "hybrid", "hybrid-rerank"])
            self.assertEqual(rows[2]["Hit@1"], "15/15")
            self.assertEqual(rows[0]["Hit@3"], "14/15")

    def test_retrieval_rows_empty_without_results(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(retrieval_compare_rows(Path(d)), [])

    def test_agent_rows_summarise_dev_runs_only(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "results" / "agent"
            for name, split in (("improve-b-dev", "dev"), ("final-test", "test")):
                (base / name).mkdir(parents=True)
                (base / name / "summary.json").write_text(json.dumps(
                    {"config": name[:-4 if name.endswith("-dev") else -5], "split": split, "n_questions": 17,
                     "status_counts": {"answered": 16, "abstain": 1}, "context_evidence_rate": {"n": 15, "N": 15},
                     "tokens_in": 100, "tokens_out": 20, "seconds_total": 9.5}), encoding="utf-8")
            rows = agent_compare_rows(Path(d), DATASETS["basic"])
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["CER"], rows[0]["trả lời / từ chối"], rows[0]["token"]), ("15/15", "16 / 1", 120))


if __name__ == "__main__":
    unittest.main()
