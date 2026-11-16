import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo.chunk_map import chunk_rows, kind_stats, length_histogram, map_html


def chunk(cid, page, text, doc="blld-2012", **meta):
    return {"id": cid, "source_id": doc, "page": page, "text": text, "metadata": {"page_end": page, **meta}}


CHUNKS = [chunk("b", 2, "x" * 300), chunk("a", 1, "y" * 100, dieu=5),
          chunk("t", 1, "z" * 700, doc="helm", kind="table"), chunk("f", 3, "w" * 50, doc="helm", kind="figure")]


class ChunkMapTests(unittest.TestCase):
    def test_rows_are_sorted_and_default_kind_is_text(self):
        rows = chunk_rows(CHUNKS)
        self.assertEqual([r["id"] for r in rows], ["a", "b", "t", "f"])  # blld-2012 trước helm? sắp theo doc
        self.assertEqual(rows[0]["kind"], "text")
        self.assertEqual(rows[0]["char_count"], 100)

    def test_histogram_counts_every_chunk(self):
        hist = length_histogram(chunk_rows(CHUNKS), bins=4)
        self.assertEqual(sum(n for _, n in hist), 4)
        self.assertEqual(hist[0][0], 50)
        self.assertEqual(length_histogram([]), [])

    def test_kind_stats(self):
        stats = {s["loại"]: s for s in kind_stats(chunk_rows(CHUNKS))}
        self.assertEqual(stats["văn bản"]["số chunk"], 2)
        self.assertEqual(stats["văn bản"]["trung bình"], 200)
        self.assertEqual(stats["bảng"]["dài nhất"], 700)
        self.assertEqual(stats["hình"]["số chunk"], 1)

    def test_map_html_has_one_box_per_chunk_and_escapes_ids(self):
        rows = chunk_rows(CHUNKS + [chunk("<script>", 9, "q")])
        out = map_html(rows)
        self.assertEqual(out.count("border-radius:2px"), 5)
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertEqual(map_html([]), "")


if __name__ == "__main__":
    unittest.main()
