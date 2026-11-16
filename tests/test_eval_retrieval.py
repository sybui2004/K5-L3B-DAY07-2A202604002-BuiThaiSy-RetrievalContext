import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.benchmark import write_freeze
from src.eval_retrieval import ensure_split_allowed, run_retrieval_eval

EV = "Thời giờ làm việc bình thường không quá 08 giờ trong 01 ngày"


def chunk(i, text="khác", page=1):
    return {"id": i, "text": text, "source_id": "s", "source": "s", "page": page, "metadata": {}, "score": 1.0}


def q(i, split="dev", ev=EV):
    return {"id": i, "split": split, "question": "hỏi " + i, "gold": [{"source_id": "s", "page": 1, "evidence": ev}],
            "filter": None}


UNANS = {"id": "u1", "split": "dev", "question": "x", "answerable": False}


class Fake:
    def __init__(self, table):
        self.table, self.calls = table, []

    def search(self, query, *, filters, top_k):
        self.calls.append((query, filters, top_k))
        return self.table[query][:top_k]


class EvalTests(unittest.TestCase):
    def test_unanswerable_excluded_from_denominator(self):
        r = Fake({"hỏi a": [chunk("1", EV)], "x": [chunk("9")]})
        res = run_retrieval_eval(r, [q("a"), UNANS], top_k=3, split="dev")
        self.assertEqual((res["n"], res["hit1"], res["hit3"]), (1, 1, 1))
        self.assertEqual(len(res["rows"]), 2)
        self.assertEqual(res["rows"][1]["id"], "u1")

    def test_hit1_vs_hit3_counts(self):
        r = Fake({"hỏi a": [chunk("1"), chunk("2", EV), chunk("3")],
                  "hỏi b": [chunk("1", EV), chunk("2"), chunk("3")],
                  "hỏi c": [chunk("1"), chunk("2"), chunk("3")]})
        res = run_retrieval_eval(r, [q("a"), q("b"), q("c")], top_k=3, split="dev")
        self.assertEqual((res["hit1"], res["hit3"], res["n"]), (1, 2, 3))
        self.assertEqual([x["rank_of_first_hit"] for x in res["rows"]], [2, 1, None])

    def test_original_query_and_filter_passed_through(self):
        r = Fake({"hỏi a": [chunk("1")]})
        qq = {**q("a"), "filter": {"version": "2019"}}
        run_retrieval_eval(r, [qq], top_k=3, split="dev")
        self.assertEqual(r.calls, [("hỏi a", {"version": "2019"}, 3)])

    def test_only_requested_split_is_run(self):
        r = Fake({"hỏi a": [chunk("1")]})
        res = run_retrieval_eval(r, [q("a"), q("t", "test")], top_k=3, split="dev")
        self.assertEqual(len(res["rows"]), 1)

    def test_test_split_refused_without_final_or_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            qp, fp = Path(d) / "q.json", Path(d) / "f.json"
            qp.write_text("[]", encoding="utf-8")
            with self.assertRaises(PermissionError):
                ensure_split_allowed("test", False, qp, fp)       # no --final
            with self.assertRaises(PermissionError):
                ensure_split_allowed("test", True, qp, fp)        # no freeze file
            write_freeze(qp, fp)
            ensure_split_allowed("test", True, qp, fp)            # ok
            ensure_split_allowed("dev", False, qp, fp)            # dev always ok
            qp.write_text("[1]", encoding="utf-8")
            with self.assertRaises(PermissionError):
                ensure_split_allowed("test", True, qp, fp)        # modified after freeze


if __name__ == "__main__":
    unittest.main()
