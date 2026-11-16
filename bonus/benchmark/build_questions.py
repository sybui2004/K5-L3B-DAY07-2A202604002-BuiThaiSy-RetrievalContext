"""Builds bonus/benchmark/questions.json (run: python bonus/benchmark/build_questions.py).

Every answer was checked against the original PDF (bonus/data/raw/helm_2211.09110v2.pdf); `gold` lists the
evidence items that must ALL be present in the context (PDF page + a string printed on that page). `region` says
where to look in the page. Nothing in this file is ever sent to the agent: only `question` is.
"""
import json
from pathlib import Path

SRC = "helm"


def g(page, evidence, region):
    return {"source_id": SRC, "page": page, "evidence": evidence, "region": region}


def q(id, split, group, question, answer, gold, note="", tags=None):
    return {"id": id, "split": split, "group": group, "tags": tags or [], "answerable": True, "question": question,
            "expected_answer": answer, "gold": gold, "note": note}


def u(id, split, question, reason, how):
    return {"id": id, "split": split, "group": "abstain", "tags": [], "answerable": False, "question": question,
            "expected_behavior": "search_and_abstain", "absence_reason": reason, "how_checked": how, "gold": []}


NOT_IN_DOC = "full-text search of the PDF (all 162 pages) for the model name returns no match"

DEV = [
    # ---- tables (4)
    q("D01", "dev", "table", "How many parameters does the Cohere xlarge v20220609 model have, according to the table of evaluated models?",
      "52.4B (Table 5, row 'Cohere xlarge v20220609 (52.4B)', column '# Parameters').",
      [g(43, "Cohere xlarge v20220609 (52.4B)", "Table 5, Cohere xlarge row")]),
    q("D02", "dev", "table", "Which hardware was used to run inference for YaLM (100B)?",
      "8×A100 (Table 6, row YaLM (100B)).", [g(44, "YaLM (100B)", "Table 6, YaLM row")]),
    q("D03", "dev", "table", "In the summary of prominent language model evaluations, how many datasets does the BLOOM evaluation use?",
      "17 (Table 12, row BLOOM, column '# datasets').", [g(156, "BLOOM", "Table 12, BLOOM row")]),
    q("D04", "dev", "table", "In the table of Wikidata relations used for WikiFact, what manual prompt probes the 'author' relation (P50)?",
      "'The author of [X] is' (Table 11, row P50 author).", [g(146, "P50", "Table 11, P50 row")]),
    # ---- images / diagrams (3)
    q("D05", "dev", "image", "In the figure that demonstrates how toxicity of model predictions is measured, what toxicity value results from the three examples and how is it computed?",
      "1/3: only the first generation is judged Toxic by the Perspective API, so Toxic / (Toxic + Non-Toxic) = 1/3 (Figure 21).",
      [g(32, "Figure 21", "Figure 21, bottom formula 'Toxicity = Toxic / (Toxic + Non-Toxic) = 1/3'")]),
    q("D06", "dev", "image", "In the bias metrics demonstration, which gender representation bias value is obtained when male terms occur 5 times and female terms 2 times?",
      "0.214 (Figure 20, left panel: 0.5*[|2/7-0.5| + |5/7-0.5|]).", [g(31, "Figure 20", "Figure 20, left panel 'Demographic representation'")]),
    q("D07", "dev", "image", "In the fairness perturbation example with the campfire text, which substitution is applied to the original input, and does the model's prediction change?",
      "A gender substitution (He becomes She); the prediction stays 'then starts quickly.', so it is invariant (Figure 19).",
      [g(30, "Figure 19", "Figure 19, original vs perturbed input and the 'Invariant?' arrow")]),
    # ---- charts (4)
    q("D08", "dev", "chart", "In the chart of accuracy by model access, which three access categories appear in the legend, and which scenario has the highest accuracy for all of them?",
      "Legend: open, limited, closed; IMDB has the highest accuracy (about 0.95) for all three (Figure 28).",
      [g(53, "Figure 28", "Figure 28, legend (top right) and tallest bars at IMDB")]),
    q("D09", "dev", "chart", "In the figure on the number of in-context examples, which metric is plotted on the y-axis for the CNN/DailyMail panel?",
      "ROUGE-2 (Figure 32, CNN/DailyMail panel; the x-axis is '#in-context examples').", [g(57, "Figure 32", "Figure 32, second panel y-axis label")]),
    q("D10", "dev", "chart", "In the box plots of variance across random seeds, which scenario shows the widest spread of the accuracy range?",
      "NaturalQuestions (open-book) - F1 (Figure 31, left plot: widest box and whiskers).", [g(56, "Figure 31", "Figure 31, left box plot")]),
    q("D11", "dev", "chart", "In the figure relating The Pile loss to accuracy, what is on the x-axis and which scenario is at the top of the chart?",
      "x-axis: log(The Pile BPB); the top line is IMDB (Figure 30).", [g(54, "Figure 30", "Figure 30, x-axis label and top line")]),
    # ---- multi-hop (3)
    q("D12", "dev", "multihop", "Which model is shown in the evaluation-components example diagram, and how many parameters does that model have in the table of evaluated models?",
      "GPT-3 davinci v1 (Figure 5); davinci has 175B parameters (Table 5).",
      [g(14, "Figure 5", "Figure 5, the 'Model' box"), g(43, "davinci (175B)", "Table 5, davinci row")]),
    q("D13", "dev", "multihop", "Which tokenizer is used by the model for which 40.9% of the inference was run on 8×2080 Ti GPUs?",
      "The T5 tokenizer: T5 (11B) ran 40.9% on 8×2080 Ti (Table 6) and its tokenizer is T5 (Table 5).",
      [g(44, "40.9%", "Table 6, T5 (11B) row"), g(43, "T5 (11B)", "Table 5, T5 row, column Tokenizer")]),
    q("D14", "dev", "multihop", "According to the table of evaluated models, which access category of the accuracy-by-access chart does BLOOM (176B) belong to?",
      "open (Table 5 lists BLOOM (176B) with access 'open'; Figure 28 groups models as open, limited, closed).",
      [g(53, "Figure 28", "Figure 28 legend"), g(43, "BLOOM (176B)", "Table 5, BLOOM row, column Access")]),
    # ---- text (4)
    q("D15", "dev", "text", "What three elements does the paper say holistic evaluation involves?",
      "Broad coverage and recognition of incompleteness; multi-metric measurement; standardization (Section 1).",
      [g(2, "Multi-metric measurement", "Section 1, numbered list of three elements")]),
    q("D16", "dev", "text", "About how many GPU hours of compute did the open models require for all runs?",
      "About 19,500 GPU hours (Section 1.2).", [g(6, "19,500 GPU hours", "Section 1.2 Empirical findings, first paragraph")]),
    q("D17", "dev", "text", "How many queries were made in total across all models?",
      "17,431,479 queries (Section 1.2).", [g(6, "17,431,479", "Section 1.2 Empirical findings, first paragraph")]),
    q("D18", "dev", "text", "Which models report no public results prior to this work, according to the introduction?",
      "J1-Grande v1 (17B), Cohere xlarge v20220609 (52.4B) and YaLM (100B).",
      [g(5, "YaLM (100B)", "Section 1, paragraph below Figure 4")]),
    # ---- abstention (3)
    u("D19", "dev", "What accuracy does GPT-4 reach on MMLU in the HELM evaluation?",
      "GPT-4 is not among the 30 evaluated models.", NOT_IN_DOC + " ('GPT-4' appears 0 times); Table 5 lists the 30 models."),
    u("D20", "dev", "What is the robustness score of the Alpaca model on IMDB?",
      "Alpaca is not evaluated in the paper.", NOT_IN_DOC + " ('Alpaca' appears 0 times)."),
    u("D21", "dev", "What accuracy does Pythia-12B reach on QuAC in the HELM evaluation?",
      "Pythia is not evaluated in the paper.", NOT_IN_DOC + " ('Pythia' appears 0 times)."),
]

TEST = [
    # ---- tables (7)
    q("T01", "test", "table", "What is the context window size, in tokens, of Anthropic-LM v4-s3 (52B)?",
      "8192 (Table 5, column 'Window Size').", [g(43, "Anthropic-LM v4-s3 (52B)", "Table 5, Anthropic-LM row")]),
    q("T02", "test", "table", "How much did it cost to run the davinci (175B) model, according to the models table?",
      "$8,440 (Table 5, column 'Total Cost').", [g(43, "$8,440", "Table 5, davinci (175B) row")]),
    q("T03", "test", "table", "Which hardware, and in what shares, was used for GPT-NeoX (20B) inference?",
      "2×A100 (73.9%) and 11×2080 Ti (26.1%) (Table 6).", [g(44, "GPT-NeoX (20B)", "Table 6, GPT-NeoX row")]),
    q("T04", "test", "table", "In the example adaptation parameters, which temperature and maximum number of output tokens are used for CNN/DailyMail?",
      "Temperature 0.3 and max tokens 128 (Table 7, CNN/DailyMail column).", [g(46, "CNN/DailyMail", "Table 7, last column, rows Temperature and Max tokens")]),
    q("T05", "test", "table", "In the table of computation estimates, how much energy (MWh) and how many mtCO2 are estimated for davinci (175B)?",
      "1287.1 MWh and 552.2 mtCO2 (Table 9).", [g(138, "1287.1", "Table 9, davinci (175B) row")]),
    q("T06", "test", "table", "How many more datasets does the HELM evaluation use than the OPT evaluation, according to the summary of language model evaluations?",
      "15: HELM uses 42 datasets and OPT 27 (Table 12).", [g(156, "Zhang et al. (2022)", "Table 12, rows HELM (42) and OPT (27)")]),
    q("T07", "test", "table", "Which default adaptation method is used for the MS MARCO scenarios?",
      "Ranking (Table 14).", [g(162, "MS MARCO (regular)", "Table 14, row 'Ranking'")]),
    # ---- images / diagrams (6)
    q("T08", "test", "image", "In the calibration demonstration, what error does Bin 1 have and what expected calibration error (ECE) results?",
      "Bin-1 error is 0.35 and ECE = (4/8)*0.35 + (4/8)*0.1 = 0.225 (Figure 17).", [g(28, "Figure 17", "Figure 17, upper part")]),
    q("T09", "test", "image", "In the inference efficiency diagram, how is the total time computed from the numbers of prompt and output tokens?",
      "Total time = F(num_prompt_tokens) + g * num_output_tokens (Figure 22).", [g(34, "Figure 22", "Figure 22, formula under the diagram")]),
    q("T10", "test", "image", "In the scenario structure diagram, which columns break a scenario down, and which two example scenarios are shown at the end of the arrows?",
      "Columns: Task, What, Who, When, Language; the example scenarios are Natural Questions and IMDB (Figure 8).",
      [g(16, "Figure 8", "Figure 8, column headings and right-hand labels")]),
    q("T11", "test", "image", "In the adaptation example for the multiple choice question about homeostasis, what is the max tokens setting in the joint strategy and which answer letter does the model give?",
      "max tokens = 1 and the answer is D (Figure 7, left; the separate strategy on the right uses max tokens = 0).",
      [g(15, "Figure 7", "Figure 7, left panel")]),
    q("T12", "test", "image", "What does each dot on the world map of languages represent, and what does its colour indicate?",
      "Each dot is one language and its colour is the top-level language family; the map is from Glottolog data (Figure 10).",
      [g(18, "Figure 10", "Figure 10, map and caption")]),
    q("T13", "test", "image", "In the robustness perturbation example, which kinds of perturbation are applied to the question and what does the model predict for the original and perturbed inputs?",
      "Typos and synonyms; the prediction is (A) for both, so it is invariant (Figure 18).", [g(29, "Figure 18", "Figure 18, both input boxes and prediction boxes")]),
    # ---- charts (6)
    q("T14", "test", "chart", "In the scatter plots of accuracy versus other metrics, which six metrics are on the y-axes and which one is measured in seconds?",
      "Calibration error, robustness, fairness, bias (gender representation), toxicity and inference time; inference time is in seconds (Figure 24).",
      [g(48, "Figure 24", "Figure 24, y-axis labels of the six panels")]),
    q("T15", "test", "chart", "In the robustness-equivariance plots with contrast sets, what is on each axis, which scenarios are shown, and do the points lie above or below the dashed diagonal?",
      "x-axis Accuracy (EM), y-axis Robustness (EM), for IMDB and BoolQ; the points lie below the diagonal (Figure 35).",
      [g(61, "Figure 35", "Figure 35, both panels")]),
    q("T16", "test", "chart", "In the targeted evaluation of language, which of the four scenarios has the highest median value?",
      "TwitterAAE (BPB, lower is better), median about 2.3 (Figure 36).", [g(67, "Figure 36", "Figure 36, box plots")]),
    q("T17", "test", "chart", "In the chart of the best accuracy up to a given model scale, what is on the x-axis and which scenario has the highest accuracy at the largest scales?",
      "x-axis: # Parameters on a logarithmic scale; IMDB is highest (about 0.95) (Figure 29).", [g(54, "Figure 29", "Figure 29, axes and top line")]),
    q("T18", "test", "chart", "In the cumulative accuracy over time chart, what does the x-axis show and which date range do its tick labels cover?",
      "Release date, with ticks from 2019-09 to 2022-09 (Figure 27).", [g(52, "Figure 27", "Figure 27, x-axis")]),
    q("T19", "test", "chart", "In the multiple-choice adaptation chart, which adaptation method gives the highest exact-match accuracy in the BLiMP panel, and what are the three methods in the legend?",
      "Multiple Choice Separate is highest (about 0.8); the legend lists Multiple Choice Joint, Separate and Separate Calibrated (Figure 33).",
      [g(58, "Figure 33", "Figure 33, BLiMP panel and legend")]),
    # ---- multi-hop (4)
    q("T20", "test", "multihop", "What is the context window size of the model that ran 96.5% of its inference on 16×2080 Ti GPUs?",
      "512 tokens: UL2 (20B) (Table 6) has window size 512 (Table 5).",
      [g(44, "16×2080 Ti", "Table 6, UL2 (20B) row"), g(43, "UL2 (20B)", "Table 5, UL2 row")]),
    q("T21", "test", "multihop", "What is the access level, in the models table, of the model that the summary of findings calls the second most accurate and fair?",
      "closed: the second most accurate and fair model is TNLG v2 (530B) (Section 1.2), listed as closed in Table 5.",
      [g(6, "TNLG v2 (530B)", "Section 1.2, finding 1"), g(43, "TNLG v2 (530B)", "Table 5, TNLG v2 (530B) row")]),
    q("T22", "test", "multihop", "What is the total cost listed in the models table for the model with the highest accuracy head-to-head win rate in the win-rate chart?",
      "$9,337: text-davinci-002 tops the accuracy panel (Figure 26) and costs $9,337 (Table 5).",
      [g(51, "Figure 26", "Figure 26, 'Accuracy' panel, top bar"), g(43, "text-davinci-002", "Table 5, text-davinci-002 row")]),
    q("T23", "test", "multihop", "What is the context window size of the only model with strong train-test contamination evidence on HellaSwag?",
      "1024 tokens: T0++ (11B) is the only model rated Strong on HellaSwag (Table 13) and its window is 1024 (Table 5).",
      [g(157, "HellaSwag", "Table 13, T0++ (11B) row"), g(43, "T0++ (11B)", "Table 5, T0++ row")]),
    # ---- text (4)
    q("T24", "test", "text", "How many runs (a specific model on a specific scenario) did the authors perform in total?",
      "4,939 runs (Section 1.2).", [g(6, "4,939 runs", "Section 1.2, first paragraph")]),
    q("T25", "test", "text", "What was the total cost for the commercial APIs?",
      "$38,001 (Section 1.2).", [g(6, "$38,001", "Section 1.2, first paragraph")]),
    q("T26", "test", "text", "Which three considerations do the authors highlight before presenting the empirical findings?",
      "(1) models may be more suitable for particular scenarios, metrics or prompts; (2) the computational resources used to train models differ; (3) possible train-test contamination (Section 1.1, caveats).",
      [g(6, "Caveats and considerations", "Section 1.1, paragraph 'Caveats and considerations'")]),
    q("T27", "test", "text", "Across how many datasets evaluated in major language modeling works do the authors find that evaluation conditions vary greatly?",
      "405 datasets (Section 1.1).", [g(5, "405 datasets", "Section 1.1, paragraph below Figure 4")]),
    # ---- abstention (6)
    u("T28", "test", "What accuracy does LLaMA-65B reach on BoolQ in the HELM evaluation?",
      "LLaMA is not evaluated in the paper.", NOT_IN_DOC + " ('LLaMA' and 'Llama' appear 0 times)."),
    u("T29", "test", "What score does Gemini obtain on HellaSwag in the HELM evaluation?",
      "Gemini is not evaluated in the paper.", NOT_IN_DOC + " ('Gemini' appears 0 times)."),
    u("T30", "test", "What toxicity score does ChatGPT get on CivilComments in the HELM evaluation?",
      "ChatGPT is not evaluated in the paper.", NOT_IN_DOC + " ('ChatGPT' appears 0 times)."),
    u("T31", "test", "How does Mistral 7B score on RAFT in the HELM evaluation?",
      "Mistral is not evaluated in the paper.", NOT_IN_DOC + " ('Mistral' appears 0 times)."),
    u("T32", "test", "What F1 does Bard obtain on NarrativeQA in the HELM evaluation?",
      "Bard is not evaluated in the paper.", NOT_IN_DOC + " ('Bard' appears 0 times)."),
    u("T33", "test", "What context window size does Vicuna have in the table of evaluated models?",
      "Vicuna is not listed among the 30 models of Table 5.", NOT_IN_DOC + " ('Vicuna' appears 0 times); Table 5 lists 30 models."),
]

# The first test set (T01-T33) was used to diagnose failures after its run, so it is no longer a clean test.
# It is kept as split "retired"; TEST2 (N01-N33) is the new held-out test set, written from figures, tables and
# passages that no dev or retired question uses (same group mix), and is frozen before any run on it.
TEST2 = [
    # ---- tables (7)
    q("N01", "test", "table", "Which tokenizer does GLM (130B) use, and who created the model, according to the table of evaluated models?",
      "The ICE tokenizer; created by Tsinghua University (Table 5, GLM (130B) row).", [g(43, "Tsinghua University", "Table 5, GLM (130B) row")]),
    q("N02", "test", "table", "How many total queries were made to code-davinci-002 in the evaluation, according to the models table?",
      "57,051 queries (Table 5, code-davinci-002 row, column 'Total Queries').", [g(43, "57,051", "Table 5, code-davinci-002 row")]),
    q("N03", "test", "table", "On which hardware configurations was GPT-J (6B) inference run, and with what shares of GPU hours?",
      "2×A100 (10.4%) and 4×2080 Ti (89.6%) (Table 6).", [g(44, "4×2080 Ti (89.6%)", "Table 6, GPT-J (6B) row")]),
    q("N04", "test", "table", "In the human evaluation for disinformation, what reiteration style score did GLM (130B) receive?",
      "1.270 (standard deviation 0.499) (Table 8, Reiteration / Style column).", [g(74, "1.270 (0.499)", "Table 8, GLM (130B) row")]),
    q("N05", "test", "table", "In the train-test contamination table, how strong is the contamination evidence for davinci (175B) on QuAC, and what is the source?",
      "Weak; source Brown et al. (2020) (Table 13).", [g(157, "Contamination strength", "Table 13, davinci (175B) / QuAC row")]),
    q("N06", "test", "table", "In the enumeration of desiderata by venue, which single venue (not the union row) lists both 'oversight' and 'participatory design'?",
      "FAccT (Table 2).", [g(26, "participatory design", "Table 2, FAccT row")]),
    q("N07", "test", "table", "In the taxonomy of tasks, which tasks are listed for the Information Extraction track?",
      "Named entity recognition, entity linking, entity extraction, relation extraction, event extraction, open information extraction (Table 1).",
      [g(16, "open information extraction", "Table 1, Information Extraction row")]),
    # ---- images / diagrams (6)
    q("N08", "test", "image", "In the figure that illustrates what a language model does, what is the input text and what completion is shown?",
      "Input 'A helm is a', completion 'wheel for steering a ship...' (Figure 1).", [g(2, "Figure 1", "Figure 1, the diagram at the top of the page")]),
    q("N09", "test", "image", "In the figure on the importance of the taxonomy to HELM, which input perturbations are listed under Robustness and under Fairness?",
      "Robustness: Typo; Fairness: Gender and Dialect (Figure 2, 'Input perturbation' column; 'None' is also listed).",
      [g(3, "Figure 2", "Figure 2, Metrics part, 'Input perturbation' column")]),
    q("N10", "test", "image", "In the 'many metrics for each use case' figure, which single metric does previous work use for AdversarialQA and which for BBQ?",
      "AdversarialQA: Robustness; BBQ: Bias (Figure 3, left 'Previous work' panel).", [g(4, "Figure 3", "Figure 3, left panel")]),
    q("N11", "test", "image", "In the passage-ranking example from MS MARCO, what is the query, and what weight range does the rank-1 reference give for male spectacled bears?",
      "Query 'how much does a spectacled bear weigh'; the rank-1 passage says males weigh from 120 to 340 pounds (Figure 12).",
      [g(21, "Figure 12", "Figure 12, Input and first reference")]),
    q("N12", "test", "image", "In the toxicity detection example from CivilComments, which reference is marked as correct?",
      "'True' (the comment is labelled toxic); 'False' is the other reference (Figure 15).", [g(24, "Figure 15", "Figure 15, References list")]),
    q("N13", "test", "image", "In the CNN/DailyMail summarization example, what is the reference summary?",
      "'Citizens gather to honor victims on One Boston Day, two years after the marathon bombings.' (Figure 13).",
      [g(22, "Figure 13", "Figure 13, Reference line")]),
    # ---- charts (6)
    q("N14", "test", "chart", "In the figure showing correlation between metrics, which six metrics have their own panel and what is on the y-axis?",
      "Accuracy, Calibration error, Robustness, Fairness, Bias (gender repr.), Toxicity; the y-axis is Pearson correlation (Figure 25).",
      [g(49, "Figure 25", "Figure 25, panel titles and y-axis label")]),
    q("N15", "test", "chart", "In the targeted evaluation of knowledge chart, which scenario has the highest median accuracy?",
      "HellaSwag, median about 0.7 (Figure 37).", [g(68, "Figure 37", "Figure 37, box plots")]),
    q("N16", "test", "chart", "In the targeted evaluation of reasoning chart, which scenario has the highest median accuracy?",
      "Entity matching (median about 0.78), just above Data imputation (about 0.72) (Figure 38).", [g(69, "Figure 38", "Figure 38, rightmost box plots")]),
    q("N17", "test", "chart", "In the copyright and memorization chart, which of the four measures has the highest median value?",
      "Copyright (code) LCS, about 0.15 (Figure 39; the other three are near 0).", [g(70, "Figure 39", "Figure 39, third box plot")]),
    q("N18", "test", "chart", "In the BBQ (ambiguous) panel of the social bias chart, which model is at the top and which is at the bottom?",
      "Top: text-davinci-002 (the only clearly positive bar); bottom: YaLM (100B) (about -0.2) (Figure 40, left panel).",
      [g(70, "Figure 40", "Figure 40, left panel")]),
    q("N19", "test", "chart", "In the metric spread figure for core scenarios, which scenario has the highest median in the toxicity panel?",
      "NarrativeQA (median about 0.019, far above the others) (Figure 34, Toxicity panel).", [g(60, "Figure 34", "Figure 34, bottom-right Toxicity panel")]),
    # ---- multi-hop (4)
    q("N20", "test", "multihop", "What is the context window size of the model at the bottom of the BBQ (unambiguous) panel of the social bias chart?",
      "512 tokens: T5 (11B) is at the bottom of the unambiguous panel (Figure 40) and has window size 512 (Table 5).",
      [g(70, "Figure 40", "Figure 40, right panel, bottom bar"), g(43, "T5 (11B)", "Table 5, T5 (11B) row")]),
    q("N21", "test", "multihop", "Which organization created the second most accurate model on WikiFact, and how many parameters does it have?",
      "Microsoft/NVIDIA; TNLG v2 (530B) is second on WikiFact at 34.3% (Knowledge paragraph, p. 68) and has 530B parameters (Table 5).",
      [g(68, "34.3%", "Knowledge paragraph, WikiFact sentence"), g(43, "Microsoft/NVIDIA", "Table 5, TNLG v2 (530B) row")]),
    q("N22", "test", "multihop", "For the dataset used in the toxicity detection example figure, which robustness measure is not computed according to the scenarios-metrics matrix?",
      "Equivariance: the example is from CivilComments (Figure 15), whose row in Table 4 has Robustness Inv = Y and Equiv = N.",
      [g(24, "Figure 15", "Figure 15 caption"), g(27, "CivilComments", "Table 4, CivilComments row, Robustness columns")]),
    q("N23", "test", "multihop", "How much energy (MWh) is estimated for the OpenAI model whose evaluation cost $846 in the models table?",
      "49.2 MWh (21.1 mtCO2): the model is curie (6.7B), $846 in Table 5, and Table 9 lists 49.2 MWh.",
      [g(43, "$846", "Table 5, curie (6.7B) row"), g(138, "49.2", "Table 9, curie (6.7B) row")]),
    # ---- text (4)
    q("N24", "test", "text", "On average, what percentage of the core scenarios were models evaluated on before HELM, and what does HELM raise this to?",
      "17.9% before, 96.0% with HELM (Section 1.1).", [g(5, "17.9%", "paragraph 'In Figure 4, we make explicit...'")]),
    q("N25", "test", "text", "How many queries does the TREC track of MS MARCO contain, and about how many judged query-passage pairs?",
      "43 queries with over 9,000 query-passage pairs (Section 3.4).", [g(21, "43 queries", "Datasets and selection process paragraph")]),
    q("N26", "test", "text", "How much were crowd workers paid per task in the disinformation human evaluation, and how was that amount chosen?",
      "$5.50 per task: the authors took about 11 minutes per task themselves, doubled it, and paid at the California minimum wage of $15.00/hr.",
      [g(74, "$5.50", "paragraph on recruiting annotators")]),
    q("N27", "test", "text", "Which models achieve more than 75% accuracy on Dyck, and what are their accuracies?",
      "Only code-davinci-002 (80.2%) and TNLG v2 (530B) (78.4%); text-davinci-002 reaches 59.4% (Reasoning paragraph, p. 69).",
      [g(69, "78.4%", "Reasoning paragraph on Dyck")]),
    # ---- abstention (6)
    u("N28", "test", "What accuracy does Qwen-7B reach on MMLU in the HELM evaluation?",
      "Qwen is not evaluated in the paper.", NOT_IN_DOC + " ('Qwen' appears 0 times)."),
    u("N29", "test", "What calibration error does Mixtral 8x7B have on HellaSwag in the HELM evaluation?",
      "Mixtral is not evaluated in the paper.", NOT_IN_DOC + " ('Mixtral' appears 0 times)."),
    u("N30", "test", "What is the total evaluation cost of Gemma 7B in the models table?",
      "Gemma is not listed among the 30 models of Table 5.", NOT_IN_DOC + " ('Gemma' appears 0 times)."),
    u("N31", "test", "How robust is DeepSeek LLM on IMDB in the HELM evaluation?",
      "DeepSeek is not evaluated in the paper.", NOT_IN_DOC + " ('DeepSeek' appears 0 times)."),
    u("N32", "test", "Which hardware was used to run inference for StableLM in the HELM evaluation?",
      "StableLM is not among the public models of Table 6.", NOT_IN_DOC + " ('StableLM' appears 0 times)."),
    u("N33", "test", "What toxicity does Dolly 2.0 produce on RealToxicityPrompts in the HELM evaluation?",
      "Dolly is not evaluated in the paper.", NOT_IN_DOC + " ('Dolly' appears 0 times)."),
]


def main(argv=None) -> None:
    """--with-test3: retire N01-N33 and add M01-M33 as the new test. Done on 2026-11-16 after the author checked
    M01-M33 (bonus/benchmark/test3_draft.json) against the PDF; the result was frozen before the single test run."""
    import sys
    with_test3 = "--with-test3" in (sys.argv[1:] if argv is None else argv)
    if with_test3:
        from bonus.benchmark.build_test3 import TEST3
        qs = DEV + [dict(x, split="retired") for x in TEST + TEST2] + TEST3
    else:
        qs = DEV + [dict(x, split="retired") for x in TEST] + TEST2
    ids = [x["id"] for x in qs]
    assert len(ids) == len(set(ids))
    from collections import Counter
    for split in ("dev", "retired", "test"):
        c = Counter((x["group"]) for x in qs if x["split"] == split)
        print(split, dict(c), "answerable:", sum(1 for x in qs if x["split"] == split and x["answerable"]))
    Path("bonus/benchmark/questions.json").write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
