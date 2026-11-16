import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.audit_sheets import write_audit_sheets
from src.score_run import score_run

QA = {"id": "q1", "split": "dev", "question": "Q?", "expected_answer": "12", "filter": None,
      "gold": [{"source_id": "s", "page": 1, "evidence": "e"}]}
QU = {"id": "u1", "split": "dev", "question": "U?", "answerable": False, "absence_reason": "r"}


def tr(qid, status, cites):
    return {"query_id": qid, "split": "dev", "status": status, "answer": "a", "citations": cites,
            "events": [{"event": "search"}], "context": "c", "context_ids": cites, "searches": 1, "seconds": 1,
            "tokens_in": 1, "tokens_out": 1}


class ScoreRunTests(unittest.TestCase):
    def test_score_run_applies_labels_and_status_override(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            traces = [tr("q1", "answered", ["c1"]), tr("u1", "answered", ["c2"])]
            (run / "traces.json").write_text(json.dumps(traces), encoding="utf-8")
            write_audit_sheets(traces, [QA, QU], run / "audit")
            p = run / "audit" / "answer_audit.csv"
            with open(p, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            rows[0].update(answer_grade_0_2="2", citation_support="true")
            rows[1].update(abstention_correct="true", effective_status="abstain", citation_support="false")
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            out = score_run(run, [QA, QU], "dev")
        self.assertEqual(out["grounded_answer"]["2"], 1)
        self.assertEqual(out["abstention"], {"n": 1, "N": 1})
        self.assertEqual(out["citation_validity"], {"n": 1, "N": 2})


if __name__ == "__main__":
    unittest.main()
