"""Money cost of saved runs from their token counts (no API call).

Prices: DeepSeek "Models & Pricing" page, read 2026-11-16, flash tier (the legacy name deepseek-v4-flash used in the
runs is billed at the flash price). USD per 1M tokens. Traces store only total input/output tokens, not cache hits,
so every input token is priced as a cache miss: the result is an upper bound for each time band.
Embedding (Ollama bge-m3), rerank (bge-reranker-v2-m3) and figure reading (qwen2.5vl:7b) run locally: 0 USD.

    python -m src.cost results/agent/*-dev results/agent/*-test bonus/results/final-test3
"""
import json
import sys
from pathlib import Path

PRICES = {  # USD / 1M tokens
    "deepseek-flash": {"peak": {"in_miss": 0.30, "in_hit": 0.006, "out": 1.20},
                       "off_peak": {"in_miss": 0.15, "in_hit": 0.003, "out": 0.60}},
}
ALIASES = {"deepseek-v4-flash": "deepseek-flash", "deepseek-flash": "deepseek-flash"}


def run_cost(tokens_in: int, tokens_out: int, model: str = "deepseek-v4-flash") -> dict:
    """Upper-bound USD cost (all input as cache miss) at peak and off-peak prices."""
    if model not in ALIASES:
        raise ValueError(f"no price for model {model!r}")
    table = PRICES[ALIASES[model]]
    return {band: round((tokens_in * p["in_miss"] + tokens_out * p["out"]) / 1e6, 4) for band, p in table.items()}


def main(argv=None) -> int:
    rows = []
    for d in (argv if argv is not None else sys.argv[1:]):
        s = json.loads((Path(d) / "summary.json").read_text(encoding="utf-8"))
        c = run_cost(s["tokens_in"], s["tokens_out"], s.get("model", "deepseek-v4-flash"))
        rows.append((d, s["tokens_in"], s["tokens_out"], c["off_peak"], c["peak"]))
    print("| Run | Token vào | Token ra | USD ngoài giờ cao điểm (trần) | USD giờ cao điểm (trần) |")
    print("|---|---:|---:|---:|---:|")
    for d, ti, to, off, peak in rows:
        print(f"| {Path(d).as_posix()} | {ti:,} | {to:,} | {off:.4f} | {peak:.4f} |")
    print(f"| **Tổng** | {sum(r[1] for r in rows):,} | {sum(r[2] for r in rows):,} | "
          f"{sum(r[3] for r in rows):.4f} | {sum(r[4] for r in rows):.4f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
