import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.benchmark import convert_day6_question, hit, validate

EVID = "Thời giờ làm việc bình thường không quá 08 giờ trong 01 ngày và không quá 48 giờ trong 01 tuần"


def chunk(i, text, page=44, page_end=44, src="blld-2019"):
    return {"id": i, "text": text, "source_id": src, "source": "x", "page": page,
            "metadata": {"page_end": page_end, "version": src[-4:]}}


def ans(i, split="dev", evidence=EVID, page=44):
    return {"id": i, "split": split, "question": "q?", "expected_answer": "a",
            "gold": [{"source_id": "blld-2019", "page": page, "evidence": evidence}], "filter": None}


def unans(i, split="dev"):
    return {"id": i, "split": split, "question": "q?", "answerable": False,
            "expected_behavior": "search_and_abstain", "absence_reason": "r"}


class HitTests(unittest.TestCase):
    def test_hit_ignores_whitespace_and_case(self):
        c = chunk("c", EVID.upper().replace(" ", "  "))
        self.assertTrue(hit(c, ans("q")["gold"]))

    def test_hit_accepts_page_inside_chunk_range(self):
        c = chunk("c", EVID, page=43, page_end=45)
        self.assertTrue(hit(c, ans("q")["gold"]))

    def test_no_hit_wrong_source_or_page(self):
        self.assertFalse(hit(chunk("c", EVID, src="blld-2012"), ans("q")["gold"]))
        self.assertFalse(hit(chunk("c", EVID, page=10, page_end=10), ans("q")["gold"]))


class ConvertTests(unittest.TestCase):
    def test_alt_gold_becomes_extra_gold_entries(self):
        q = convert_day6_question({
            "id": "q01", "split": "dev", "question": "?", "expected_answer": "a", "gold_source_id": "blld-2019",
            "gold_page": 44, "evidence_quote": "E1", "filter": None,
            "alt_gold": [{"source_id": "blld-2012", "page": 36, "dieu": 104, "evidence_quote": "E2"}]})
        self.assertEqual(q["gold"], [{"source_id": "blld-2019", "page": 44, "evidence": "E1"},
                                     {"source_id": "blld-2012", "page": 36, "evidence": "E2"}])
        self.assertIsNone(q["filter"])


class ValidateTests(unittest.TestCase):
    def good_set(self):
        qs = [ans(f"d{i}") for i in range(15)] + [unans("u1"), unans("u2")]
        qs += [ans(f"t{i}", "test") for i in range(5)] + [unans("u3", "test"), unans("u4", "test")]
        return qs

    def test_good_set_has_no_problems(self):
        self.assertEqual(validate(self.good_set(), [chunk("c", EVID)]), [])

    def test_duplicate_id_detected(self):
        qs = self.good_set() + [ans("d0")]
        self.assertTrue(any("duplicate" in p for p in validate(qs, [chunk("c", EVID)])))

    def test_missing_evidence_detected(self):
        qs = self.good_set()
        qs[0] = ans("d0", evidence="một đoạn không hề tồn tại trong bất kỳ chunk nào của kho dữ liệu")
        self.assertTrue(any("evidence" in p and "d0" in p for p in validate(qs, [chunk("c", EVID)])))

    def test_too_few_unanswerable_detected(self):
        qs = [q for q in self.good_set() if q["id"] != "u4"]
        self.assertTrue(any("unanswerable" in p and "test" in p for p in validate(qs, [chunk("c", EVID)])))

    def test_unanswerable_key_phrase_present_in_corpus_detected(self):
        qs = self.good_set()
        qs[15] = {**unans("u1"), "key_phrases": ["không quá 48 giờ trong 01 tuần"]}
        self.assertTrue(any("u1" in p and "phrase" in p for p in validate(qs, [chunk("c", EVID)])))


if __name__ == "__main__":
    unittest.main()


class FreezeTests(unittest.TestCase):
    def test_freeze_detects_modified_questions(self):
        import tempfile
        from src.benchmark import check_freeze, write_freeze
        with tempfile.TemporaryDirectory() as d:
            qp, fp = Path(d) / "q.json", Path(d) / "freeze.json"
            qp.write_text("[1]", encoding="utf-8")
            write_freeze(qp, fp)
            self.assertTrue(check_freeze(qp, fp))
            qp.write_text("[1, 2]", encoding="utf-8")
            self.assertFalse(check_freeze(qp, fp))
            self.assertFalse(check_freeze(qp, Path(d) / "missing.json"))
