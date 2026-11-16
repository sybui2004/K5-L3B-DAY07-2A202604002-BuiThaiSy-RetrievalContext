import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.audit_sheets import reviews_from_csv, write_audit_sheets
from src.eval_agent import agent_hit_at_k, context_evidence_rate, to_agent_metrics_inputs, tool_use_stats

EV = "nghỉ hằng năm 12 ngày làm việc"


def chunk(i, text):
    return {"id": i, "text": text, "source_id": "s", "source": "s", "page": 1, "metadata": {}}


CHUNKS = {"c1": chunk("c1", "Người lao động được " + EV + " hưởng lương"), "c2": chunk("c2", "không liên quan")}
QA = {"id": "q1", "split": "dev", "question": "Q1?", "expected_answer": "12", "filter": None,
      "gold": [{"source_id": "s", "page": 1, "evidence": EV}]}
QB = {**QA, "id": "q2"}
QU = {"id": "u1", "split": "dev", "question": "U?", "answerable": False}


def _read(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def trace(qid, ids, status="answered", searches=1, cites=None):
    return {"query_id": qid, "split": "dev", "status": status, "answer": "a", "citations": cites or [],
            "events": [{"event": "search"}] * searches, "context": "ctx " + qid, "context_ids": ids,
            "searches": searches, "seconds": 1, "tokens_in": 1, "tokens_out": 1}


class MetricTests(unittest.TestCase):
    def test_agent_hit_at_k_uses_first_search_ranking(self):
        def search(ids):
            return {"event": "search", "results": [{"id": i} for i in ids]}
        t1 = {**trace("q1", ["c1"]), "events": [search(["c2", "c1"]), search(["c1"])]}   # first search: hit at rank 2
        t2 = {**trace("q2", ["c2"]), "events": [search(["c2"])]}                        # miss
        t3 = {**trace("u1", []), "events": [search(["c1"])]}                            # unanswerable: ignored
        out = agent_hit_at_k([t1, t2, t3], [QA, QB, QU], CHUNKS, ks=(1, 3))
        self.assertEqual(out, {"hit@1": {"n": 0, "N": 2}, "hit@3": {"n": 1, "N": 2}})

    def test_agent_hit_at_k_counts_question_without_search_as_miss(self):
        out = agent_hit_at_k([{**trace("q1", ["c1"]), "events": [{"event": "answer"}]}], [QA], CHUNKS, ks=(1,))
        self.assertEqual(out, {"hit@1": {"n": 0, "N": 1}})

    def test_cer_counts_only_answerable(self):
        traces = [trace("q1", ["c1"]), trace("q2", ["c2"]), trace("u1", ["c1"], "abstain")]
        self.assertEqual(context_evidence_rate(traces, [QA, QB, QU], CHUNKS), {"n": 1, "N": 2})

    def test_cer_ignores_error_traces_as_misses_but_keeps_denominator(self):
        traces = [trace("q1", ["c1"]), {**trace("q2", []), "status": "error"}]
        self.assertEqual(context_evidence_rate(traces, [QA, QB], CHUNKS), {"n": 1, "N": 2})

    def test_tool_use_stats(self):
        traces = [trace("q1", [], searches=0), trace("q2", [], searches=2), {**trace("q3", []), "status": "error"}]
        s = tool_use_stats(traces)
        self.assertEqual((s["n"], s["N"], s["errors"]), (1, 2, 1))
        self.assertEqual(s["distribution"], {0: 1, 2: 1})

    def test_metrics_inputs_written(self):
        with tempfile.TemporaryDirectory() as d:
            to_agent_metrics_inputs([trace("q1", ["c1"]), trace("u1", [], "abstain")], [QA, QU], d)
            cases = json.loads((Path(d) / "cases.json").read_text(encoding="utf-8"))
            self.assertEqual(cases, [{"id": "q1", "split": "dev", "answerable": True},
                                     {"id": "u1", "split": "dev", "answerable": False}])
            self.assertTrue((Path(d) / "traces.json").exists())


class AuditTests(unittest.TestCase):
    def test_audit_sheet_score_columns_blank_and_no_gold_leak(self):
        with tempfile.TemporaryDirectory() as d:
            write_audit_sheets([trace("q1", ["c1"], cites=["c1"]), trace("u1", [], "abstain")], [QA, QU], d)
            for name, blank in (("context_audit.csv", ["context_score_0_2", "reason"]),
                                ("answer_audit.csv", ["answer_grade_0_2", "citation_support", "abstention_correct", "reason"])):
                rows = _read(Path(d) / name)
                self.assertEqual(len(rows), 2 if name == "answer_audit.csv" else 1)
                for r in rows:
                    for col in blank:
                        self.assertEqual(r[col], "")
            ans = _read(Path(d) / "answer_audit.csv")
            self.assertEqual(ans[0]["expected_answer"], "12")   # for the human grader

    def test_reviews_from_csv_parses_labels(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "answer_audit.csv"
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["query_id", "answer_grade_0_2", "citation_support", "abstention_correct", "reason"])
                w.writerow(["q1", "2", "true;false", "", "ok"])
                w.writerow(["u1", "", "", "true", "ok"])
            rev = reviews_from_csv(p)
            self.assertEqual(rev[0], {"query_id": "q1", "answer_grade": 2, "citation_support": [True, False]})
            self.assertEqual(rev[1], {"query_id": "u1", "citation_support": [], "abstention_correct": True})

    def test_effective_status_override_flows_to_metrics_inputs(self):
        # model "answered" with a statement that evidence is insufficient: the author labels it as an abstention
        with tempfile.TemporaryDirectory() as d:
            to_agent_metrics_inputs([trace("u1", ["c1"], "answered", cites=["c1"])], [QU], d,
                                    status_overrides={"u1": "abstain"})
            t = json.loads((Path(d) / "traces.json").read_text(encoding="utf-8"))
            self.assertEqual(t[0]["status"], "abstain")
            self.assertEqual(t[0]["trace_status"], "answered")

    def test_reviews_from_csv_reads_effective_status(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.csv"
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["query_id", "answer_grade_0_2", "citation_support", "abstention_correct",
                            "effective_status", "reason"])
                w.writerow(["u1", "", "true", "true", "abstain", "ok"])
            self.assertEqual(reviews_from_csv(p)[0]["effective_status"], "abstain")

    def test_reviews_from_csv_rejects_unlabelled_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.csv"
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["query_id", "answer_grade_0_2", "citation_support", "abstention_correct", "reason"])
                w.writerow(["q1", "", "", "", ""])
            with self.assertRaises(ValueError):
                reviews_from_csv(p)


if __name__ == "__main__":
    unittest.main()
