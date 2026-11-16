import sys
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrievers import Bm25Retriever
from src.tokenize_vi import tokenize_syllable_bigrams, tokenize_whitespace


def chunk(i, text, version="2019"):
    return {"id": i, "text": text, "source_id": f"blld-{version}", "source": "x.pdf", "page": 1,
            "metadata": {"version": version}}


CHUNKS = [
    chunk("a", "Thời giờ làm việc bình thường không quá 08 giờ trong 01 ngày"),
    chunk("b", "Người lao động được nghỉ hằng năm 12 ngày làm việc hưởng nguyên lương"),
    chunk("c", "Hợp đồng lao động xác định thời hạn tối đa 36 tháng", "2012"),
    chunk("d", "Kỷ luật sa thải áp dụng khi tái phạm", "2012"),
]


class TokenizerTests(unittest.TestCase):
    def test_whitespace_lowercases_and_nfc(self):
        self.assertEqual(tokenize_whitespace(unicodedata.normalize("NFD", "Thời Giờ")), ["thời", "giờ"])

    def test_bigrams_include_unigrams_and_pairs(self):
        self.assertEqual(tokenize_syllable_bigrams("thời giờ làm"),
                         ["thời", "giờ", "làm", "thời giờ", "giờ làm"])


class Bm25Tests(unittest.TestCase):
    def test_exact_phrase_ranks_its_chunk_first(self):
        r = Bm25Retriever(CHUNKS)
        res = r.search("nghỉ hằng năm bao nhiêu ngày", filters=None, top_k=3)
        self.assertEqual(res[0]["id"], "b")
        self.assertGreater(res[0]["score"], 0)

    def test_version_filter(self):
        res = Bm25Retriever(CHUNKS).search("hợp đồng thời giờ lao động", filters={"version": "2012"}, top_k=5)
        self.assertTrue(res)
        self.assertTrue(all(x["metadata"]["version"] == "2012" for x in res))

    def test_nfd_query_matches_nfc_text(self):
        q = unicodedata.normalize("NFD", "nghỉ hằng năm")
        self.assertEqual(Bm25Retriever(CHUNKS).search(q, filters=None, top_k=1)[0]["id"], "b")

    def test_zero_score_chunks_not_returned(self):
        res = Bm25Retriever(CHUNKS).search("xyzabc", filters=None, top_k=3)
        self.assertEqual(res, [])

    def test_validation(self):
        r = Bm25Retriever(CHUNKS)
        with self.assertRaises(ValueError):
            r.search(" ", filters=None, top_k=3)
        with self.assertRaises(ValueError):
            r.search("lương", filters={"version": "1999"}, top_k=3)
        with self.assertRaises(ValueError):
            r.search("lương", filters=None, top_k=0)

    def test_bigram_tokenizer_option_works(self):
        r = Bm25Retriever(CHUNKS, tokenizer=tokenize_syllable_bigrams)
        self.assertEqual(r.search("sa thải", filters=None, top_k=1)[0]["id"], "d")


if __name__ == "__main__":
    unittest.main()
