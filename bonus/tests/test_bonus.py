import csv
import json
import tempfile
import unittest
from pathlib import Path

from bonus.src.eval_bonus import COLS, context_evidence_rate, score
from bonus.src.extract import layout_lines, short_caption, split_table, table_to_markdown
from bonus.src.ingest import fix_text, page_range
from bonus.src.validate import norm


def chunk(i, page, text):
    return {"id": i, "page": page, "source_id": "helm", "source": "x.pdf", "text": text, "metadata": {"page_end": page}}


class EvalTests(unittest.TestCase):
    def test_context_needs_all_evidence_of_multihop(self):
        q = {"id": "T1", "group": "multihop", "answerable": True,
             "gold": [{"source_id": "helm", "page": 44, "evidence": "16×2080 Ti"},
                      {"source_id": "helm", "page": 43, "evidence": "UL2 (20B)"}]}
        chunks = {"a": chunk("a", 44, "UL2 (20B) | 2×A100 (3.5%); 16×2080 Ti (96.5%)"), "b": chunk("b", 43, "UL2 (20B) | Google | 512")}
        both = [{"query_id": "T1", "context_ids": ["a", "b"]}]
        one = [{"query_id": "T1", "context_ids": ["a"]}]
        self.assertEqual(context_evidence_rate(both, [q], chunks)["all"], {"n": 1, "N": 1})
        self.assertEqual(context_evidence_rate(one, [q], chunks)["multihop"], {"n": 0, "N": 1})

    def test_score_counts_errors_and_refusals_in_denominator(self):
        qs = [{"id": f"X{i}", "group": "table", "answerable": True} for i in range(10)]
        traces = [{"query_id": q["id"], "status": "answered", "tokens_in": 1, "tokens_out": 1, "seconds": 1.0} for q in qs]
        traces[0]["status"] = "error"
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "audit").mkdir()
            (run / "traces.json").write_text(json.dumps(traces), encoding="utf-8")
            with open(run / "audit" / "pass_fail.csv", "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COLS)
                w.writeheader()
                for q in qs:
                    w.writerow({"query_id": q["id"], "pass_fail": "pass"})
            res = score(run, qs)
        self.assertEqual(res["pass"], "9/10")
        self.assertTrue(res["meets_90_percent"])
        self.assertEqual(res["errors"], 1)

    def test_score_rejects_unlabelled(self):
        qs = [{"id": "X1", "group": "text", "answerable": True}]
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "audit").mkdir()
            (run / "traces.json").write_text(json.dumps([{"query_id": "X1", "status": "answered", "tokens_in": 0,
                                                          "tokens_out": 0, "seconds": 0}]), encoding="utf-8")
            with open(run / "audit" / "pass_fail.csv", "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COLS)
                w.writeheader()
                w.writerow({"query_id": "X1", "pass_fail": ""})
            with self.assertRaises(ValueError):
                score(run, qs)


class ExtractTests(unittest.TestCase):
    def test_fix_text_decodes_shifted_font_codes(self):
        self.assertEqual(fix_text(",QSXW :KLFK"), "Input Which")
        self.assertEqual(fix_text("Input which of the following"), "Input which of the following")

    def test_split_table_repeats_header(self):
        md = "Model | Cost\n" + "\n".join(f"m{i} | {i}" for i in range(200))
        parts = split_table(md, limit=300)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(p.startswith("Model | Cost") for p in parts))

    def test_row_chunks_one_row_each_with_header(self):
        md = "Model | Cost\nA (1B) | $1\nB (2B) | $2\nC (3B) | $3"
        self.assertEqual(split_table(md, per_row=True),
                         ["Model | Cost\nA (1B) | $1", "Model | Cost\nB (2B) | $2", "Model | Cost\nC (3B) | $3"])

    def test_short_caption_keeps_first_sentence(self):
        self.assertEqual(short_caption("Table 5: Models. Description of the 30 models. More."), "Table 5: Models.")
        self.assertEqual(short_caption("No period here"), "No period here")

    def test_table_to_markdown_pads_rows(self):
        md = table_to_markdown([["a", "b"], ["c"]])
        self.assertIn("| c |  |", md)

    def test_layout_splits_side_by_side_panels_and_keeps_top_to_bottom_order(self):
        import pymupdf
        frame = pymupdf.Rect(0, 0, 200, 100)
        left = [(pymupdf.Rect(10, 10 + 10 * i, 60, 18 + 10 * i), f"L{i}") for i in range(3)]
        right = [(pymupdf.Rect(120, 10 + 10 * i, 170, 18 + 10 * i), f"R{i}") for i in range(3)]
        out = layout_lines(right[::-1] + left, frame)  # input order must not matter
        self.assertIn("top to bottom", out)
        regions = [ln for ln in out.splitlines() if ln.startswith("[")]
        self.assertEqual(len(regions), 2)
        self.assertTrue(regions[0].endswith("L0 | L1 | L2"))
        self.assertTrue(regions[1].endswith("R0 | R1 | R2"))
        self.assertIn("x 5-30%", regions[0])

    def test_layout_merges_axis_tick_regions(self):
        import pymupdf
        frame = pymupdf.Rect(0, 0, 200, 100)
        ticks = [(pymupdf.Rect(5, 10 + 20 * i, 12, 15 + 20 * i), f"0.{8 - 2 * i}") for i in range(4)]
        out = layout_lines(ticks + [(pymupdf.Rect(60, 10, 120, 18), "Panel A")], frame)
        regions = [ln for ln in out.splitlines() if ln.startswith("[")]
        self.assertEqual(len(regions), 2)
        self.assertTrue(regions[0].endswith("0.8 | 0.6 | 0.4 | 0.2"))

    def _fig_medians(self, page, number):
        import pymupdf
        from bonus.src.extract import PDF, boxplot_medians, figure_regions
        p = pymupdf.open(PDF)[page - 1]
        f = next(f for f in figure_regions(p) if f["number"] == number)
        return boxplot_medians(p, f["bbox"])

    def test_boxplot_medians_read_from_vector_graphics(self):
        panels = dict(self._fig_medians(70, 39))
        (title, meds), = panels.items()
        self.assertTrue(title.startswith("Copyright"))
        top = max(meds, key=lambda m: m[1])
        self.assertEqual(top[0], "Copyright (code) LCS")  # the ↓ glyph is not in the PDF text layer
        self.assertAlmostEqual(top[1], 0.15, delta=0.01)

    def test_boxplot_medians_multi_panel_and_two_line_labels(self):
        panels = dict(self._fig_medians(60, 34))
        tox = dict(next(m for t, m in panels.items() if t.startswith("Toxicity")))
        self.assertEqual(max(tox, key=tox.get), "NarrativeQA")
        know = dict(dict(self._fig_medians(68, 37))["Knowledge"])
        self.assertIn("NaturalQuestions (closed-book)", know)

    def test_boxplot_ticks_without_minus_glyph_are_restored(self):
        panels = dict(self._fig_medians(49, 25))
        self.assertTrue(any(v < 0 for meds in panels.values() for _, v in meds))

    def test_layout_of_empty_figure_is_empty(self):
        import pymupdf
        self.assertEqual(layout_lines([], pymupdf.Rect(0, 0, 10, 10)), "")

    def test_figure_reader_reads_top_figures_once_per_question(self):
        from bonus.src.vlm import FigureReader
        calls = []

        def ask(image, question):
            calls.append((image, question))
            return f"answer about {image}"
        fig = lambda i: {"id": f"f{i}", "text": f"Figure {i}", "metadata": {"kind": "figure", "image_path": f"img{i}.png"}}  # noqa: E731
        txt = {"id": "t1", "text": "plain", "metadata": {"kind": "text", "image_path": None}}
        r = FigureReader(ask, max_per_round=2, max_per_question=3, model="m")
        out = r("Q?", [txt, fig(1), fig(2), fig(3)])
        self.assertEqual([c[0] for c in calls], ["img1.png", "img2.png"])
        self.assertIn("answer about img1.png", out[1]["text"])
        self.assertEqual(out[0]["text"], "plain")
        self.assertEqual(out[3]["text"], "Figure 3")      # beyond max_per_round
        r("Q?", [fig(1), fig(3)])                         # f1 cached, f3 read (3rd call)
        r("Q?", [fig(4)])                                 # over max_per_question
        self.assertEqual([c[0] for c in calls], ["img1.png", "img2.png", "img3.png"])
        self.assertNotIn("answer", fig(1)["text"])        # input chunks are not mutated
        r("Other?", [fig(1)])
        self.assertEqual(calls[-1], ("img1.png", "Other?"))

    def test_page_range(self):
        self.assertEqual(page_range("3-5", 10), [3, 4, 5])
        self.assertEqual(page_range(None, 3), [1, 2, 3])
        self.assertEqual(norm("A  B­ c"), "abc")


if __name__ == "__main__":
    unittest.main()
