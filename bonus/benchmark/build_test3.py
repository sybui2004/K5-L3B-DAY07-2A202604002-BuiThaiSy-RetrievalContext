"""Third test set (M01-M33, split "test") -> bonus/benchmark/test3_draft.json (file name kept for history).

STATUS: checked against the PDF (bonus/data/raw/helm_2211.09110v2.pdf) and approved by the author on 2026-11-16,
merged into questions.json, frozen, and run once (bonus/results/final-test3). Do not edit: the test has been used.
Content differs from dev (D), retired (T) and the second test (N): other table rows, other figures, or other
questions about them. Same group mix as before: 7 table / 6 image / 6 chart / 4 multi-hop / 4 text / 6 absent.

    python -m bonus.benchmark.build_test3      # writes test3_draft.json
    python bonus/benchmark/build_questions.py --with-test3   # retires N01-N33, appends M01-M33 (after the check)
"""
import json
from pathlib import Path

from bonus.benchmark.build_questions import g, q, u

NOT_IN_DOC = "full-text search of the PDF (all 162 pages) for the model name returns no match"
S = "test"

TEST3 = [
    # ---- tables (7)
    q("M01", S, "table", "How many GPU hours did it take to run OPT (66B), according to the table of evaluated models?",
      "2,000 GPU hours (Table 5, OPT (66B) row, column 'Total Cost').", [g(43, "2,000 GPU hours", "Table 5, OPT (66B) row")]),
    q("M02", S, "table", "Who created TNLG v2 (6.7B), and what is its access level, according to the table of evaluated models?",
      "Microsoft/NVIDIA; closed access (Table 5, TNLG v2 (6.7B) row).", [g(43, "TNLG v2 (6.7B)", "Table 5, TNLG v2 (6.7B) row")]),
    q("M03", S, "table", "On which hardware configurations, and with what shares of GPU hours, was T0++ (11B) inference run?",
      "2×A100 (1.1%) and 8×2080 Ti (98.9%) (Table 6, T0++ (11B) row).", [g(44, "98.9%", "Table 6, T0++ (11B) row")]),
    q("M04", S, "table", "In the table of computation estimates, how much energy (MWh) and how many mtCO2 are estimated for babbage (1.3B)?",
      "9.8 MWh and 4.2 mtCO2 (Table 9, babbage (1.3B) row).", [g(138, "babbage (1.3B)", "Table 9, babbage (1.3B) row")]),
    q("M05", S, "table", "In the summary of language model evaluations, how many datasets does the PaLM evaluation use?",
      "262 (Table 12, row PaLM, column '# datasets').", [g(156, "Chowdhery et al. (2022)", "Table 12, PaLM row")]),
    q("M06", S, "table", "In the table of Wikidata relations used for WikiFact, which manual prompt probes the 'currency' relation (P38)?",
      "'The currency of [X] is' (Table 11, row P38 currency, Economics).", [g(146, "P38", "Table 11, P38 row")]),
    q("M07", S, "table", "Which scenarios use the 'multiple choice (joint)' adaptation method by default?",
      "MMLU, TruthfulQA, LegalSupport, LSAT and BBQ (Table 14).",
      [g(162, "MMLU, TruthfulQA, LegalSupport, LSAT, BBQ", "Table 14, 'Multiple choice (joint)' row")]),
    # ---- images / diagrams (6)
    q("M08", S, "image", "In the sentiment analysis example from IMDB, which reference is marked as correct?",
      "Negative (Figure 14: the review says the movie 'should have been destroyed').", [g(23, "Figure 14", "Figure 14, references list")]),
    q("M09", S, "image", "In the RAFT (Banking77) example for miscellaneous text classification, which reference label is marked as correct?",
      "Declined_transfer (Figure 16).", [g(25, "Figure 16", "Figure 16, references list")]),
    q("M10", S, "image", "In the prompt formatting example, how many times is the block of training input, references and output repeated, and which answer does the training example give?",
      "5 times (the '5x' brace); the training example's answer is C (Figure 23).",
      [g(46, "Figure 23", "Figure 23, '5x' brace and '{train output} Answer: C'")]),
    q("M11", S, "image", "In the figure of modern use cases for language models, which use case is described as 'Create a recipe from a list of ingredients'?",
      "'Recipe creator (eat at your own risk)' (Figure 9, third column).", [g(17, "Figure 9", "Figure 9, third column, bottom entry")]),
    q("M12", S, "image", "In the figure on standardizing language model evaluation, what are the two parts that are compared, and which two scenarios does the caption name as having many models evaluated before this work?",
      "Previous work (top) versus HELM (bottom); BoolQ and HellaSwag (Figure 4).", [g(5, "Figure 4", "Figure 4 caption and the two grids")]),
    q("M13", S, "image", "In the bias metrics demonstration, what value does the gender association bias for 'mathematician' take when the co-occurrence is 3 with male terms and 1 with female terms?",
      "0.25 (Figure 20, right panel 'Stereotypical association').", [g(31, "Figure 20", "Figure 20, right panel")]),
    # ---- charts (6)
    q("M14", S, "chart", "In the head-to-head win rate figure, which model is at the top of the Toxicity panel?",
      "T0pp (11B) (Figure 26, bottom-right panel).", [g(51, "Figure 26", "Figure 26, Toxicity panel, top bar")]),
    q("M15", S, "chart", "In the head-to-head win rate figure, which model is at the top of the Bias panel?",
      "GPT-J (6B) (Figure 26, bottom-middle panel).", [g(51, "Figure 26", "Figure 26, Bias panel, top bar")]),
    q("M16", S, "chart", "In the robustness-equivariance plots with contrast sets, for which of the two scenarios do the points lie closer to the dashed diagonal line?",
      "IMDB (Figure 35, left plot: most points cluster near the diagonal; BoolQ points sit well below it).",
      [g(61, "Figure 35", "Figure 35, both plots")]),
    q("M17", S, "chart", "In the 'Accuracy vs. X' scatter plots, at what value does the dashed horizontal line appear in the bias (gender representation) panel?",
      "0.5 (Figure 24, bottom-left panel).", [g(48, "Figure 24", "Figure 24, bottom-left panel")]),
    q("M18", S, "chart", "In the cumulative scale versus accuracy chart, which scenario has the lowest accuracy at the smallest model size?",
      "XSUM (Figure 29, lowest line at the left edge, about 0.03).", [g(54, "Figure 29", "Figure 29, lowest line at the left edge")]),
    q("M19", S, "chart", "In the multiple-choice adaptation chart, which three adaptation methods are in the legend and which six models are compared on the x-axis?",
      "Legend: joint, separate, separate calibrated. Models: Anthropic-LM v4-s3 (52B), BLOOM (176B), GPT-J (6B), GPT-NeoX (20B), OPT (175B), OPT (66B) (Figure 33).",
      [g(58, "Figure 33", "Figure 33, legend and x-axis labels")]),
    # ---- multi-hop (4)
    q("M20", S, "multihop", "What is the context window size of the model that the summary of findings says reaches 62.0% accuracy on TruthfulQA?",
      "4000 tokens: text-davinci-002 (62.0% on TruthfulQA, p. 8) has window size 4000 (Table 5).",
      [g(8, "62.0%", "Finding 15, Knowledge"), g(43, "text-davinci-002", "Table 5, text-davinci-002 row")]),
    q("M21", S, "multihop", "How many GPU hours did it cost to run the model that heads the Toxicity panel of the head-to-head win rate figure?",
      "1,250 GPU hours: T0pp (11B) is on top (Figure 26) and the models table lists 1,250 GPU hours for T0++ (11B).",
      [g(51, "Figure 26", "Figure 26, Toxicity panel, top bar"), g(43, "T0++ (11B)", "Table 5, T0++ (11B) row")]),
    q("M22", S, "multihop", "How many total queries were made to the model that ran 73.9% of its inference on 2×A100 GPUs?",
      "849,830: GPT-NeoX (20B) (Table 6) has 849,830 total queries (Table 5).",
      [g(44, "73.9%", "Table 6, GPT-NeoX (20B) row"), g(43, "GPT-NeoX (20B)", "Table 5, GPT-NeoX (20B) row")]),
    q("M23", S, "multihop", "What context window size does the model have that is the most accurate on TwitterAAE according to the summary of findings?",
      "2048 tokens: OPT (175B) is the most accurate on TwitterAAE (p. 7) and its window size is 2048 (Table 5).",
      [g(7, "most accurate model on TwitterAAE", "Finding 5, Performance disparities"), g(43, "OPT (175B)", "Table 5, OPT (175B) row")]),
    # ---- text (4)
    q("M24", S, "text", "Which models does the paper give as examples of open, limited-API-access and closed models?",
      "Open: GPT-NeoX (20B), OPT (175B), BLOOM (176B). Limited: davinci (175B), J1-Jumbo v1 (178B), Cohere xlarge v20220609 (52.4B). Closed: Anthropic-LM v4-s3 (52B), TNLG v2 (530B).",
      [g(44, "Model selection.", "paragraph 'Model selection.'")]),
    q("M25", S, "text", "On NarrativeQA, how far does the accuracy of TNLG v2 (530B) fall under robustness perturbations?",
      "From 72.6% standard accuracy to 38.9% (finding 4).", [g(7, "38.9%", "Finding 4, Robustness and fairness perturbations")]),
    q("M26", S, "text", "How does text-davinci-002 perform on the Systematic Review Inclusion split of RAFT compared with other models?",
      "Very poorly: 40.8% accuracy, compared with 97.5% from several models such as GLM (130B) (finding 13).",
      [g(8, "40.8%", "Finding 13, Miscellaneous text classification")]),
    q("M27", S, "text", "How are the in-context examples chosen, and do they change between evaluation instances?",
      "Sampled to ensure class coverage (the 5 most frequent classes represented); fixed across all evaluation instances.",
      [g(46, "fix the in-context examples across all evaluation instances", "paragraph 'In-context examples.'")]),
    # ---- absent (6)
    u("M28", S, "What accuracy does Falcon-40B reach on TruthfulQA in the HELM evaluation?", "Falcon is not evaluated in the paper.",
      "full-text search of the PDF (all 162 pages) finds no model named Falcon; 'Falcon' occurs once, only inside the author surname 'Saad-Falcon' (p. 108 references)."),
    u("M29", S, "What is the total number of queries made to Yi-34B in the models table?", "Yi-34B is not evaluated in the paper.",
      NOT_IN_DOC + " ('Yi-34B' appears 0 times)."),
    u("M30", S, "What toxicity score does Grok-1 get on BOLD in the HELM evaluation?", "Grok is not evaluated in the paper.",
      NOT_IN_DOC + " ('Grok' appears 0 times)."),
    u("M31", S, "On which hardware was Baichuan-13B run for inference?", "Baichuan is not evaluated in the paper.",
      NOT_IN_DOC + " ('Baichuan' appears 0 times)."),
    u("M32", S, "What is the context window size of Phi-2 in the table of evaluated models?", "Phi-2 is not evaluated in the paper.",
      NOT_IN_DOC + " ('Phi-2' appears 0 times)."),
    u("M33", S, "How much energy in MWh is estimated for Nemotron-4 in the computation estimates table?", "Nemotron is not evaluated in the paper.",
      NOT_IN_DOC + " ('Nemotron' appears 0 times)."),
]

if __name__ == "__main__":
    out = Path("bonus/benchmark/test3_draft.json")
    out.write_text(json.dumps(TEST3, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(TEST3)} questions -> {out}")
