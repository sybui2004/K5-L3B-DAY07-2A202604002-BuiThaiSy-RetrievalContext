"""Đọc và chuẩn hóa kết quả agent đã lưu cho giao diện demo (không import streamlit)."""
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Dataset:
    key: str
    label: str
    results_dirs: tuple[str, ...]
    configs_dir: str
    questions_path: str
    label_file: str
    image_root: str | None


DATASETS: dict[str, Dataset] = {
    "basic": Dataset("basic", "Cơ bản · Luật Lao động 2012/2019", ("results/agent",), "configs",
                     "benchmark/questions.json", "answer_audit.csv", None),
    "bonus": Dataset("bonus", "Bonus · HELM (bảng và ảnh)", ("bonus/results",), "bonus/configs",
                     "bonus/benchmark/questions.json", "pass_fail.csv", "bonus"),
}
_LABEL_COLUMNS = ("answer_grade_0_2", "pass_fail")


METHOD_DESC = {
    "dense": "**Ngữ nghĩa (dense)**: embedding câu hỏi bằng bge-m3 (Ollama), so khớp cosine với vector của chunk "
             "trong Postgres pgvector.",
    "bm25": "**Từ khóa (BM25)**: chấm điểm theo từ trùng khớp giữa câu hỏi và văn bản chunk (tách theo âm tiết).",
    "bm25-bigram": "**Từ khóa (BM25 + bigram)**: như BM25 nhưng thêm cặp âm tiết liền kề làm token.",
    "hybrid": "**Kết hợp ngữ nghĩa + từ khóa (hybrid)**: gộp xếp hạng dense và BM25 bằng Reciprocal Rank Fusion.",
    "dense-rerank": "**Dense + rerank**: dense lấy 20 ứng viên, rồi cross-encoder `bge-reranker-v2-m3` chấm lại từng "
                    "cặp (câu hỏi, chunk) và giữ top-k theo điểm mới (xem mục Tiêu chí rerank).",
    "hybrid-rerank": "**Hybrid + rerank**: hybrid (RRF) lấy 20 ứng viên, rồi cross-encoder `bge-reranker-v2-m3` chấm "
                     "lại từng cặp (câu hỏi, chunk) và giữ top-k theo điểm mới (xem mục Tiêu chí rerank).",
}
RERANK_CRITERION_TEXT = (
    "**Tiêu chí rerank**: chỉ một tiêu chí là mức độ liên quan giữa câu hỏi và chunk, do model ước lượng thành một "
    "điểm số cho mỗi cặp. Không dùng điểm cũ của dense/BM25, trang hay loại luật; điểm cũ chỉ quyết định 20 chunk nào "
    "vào danh sách ứng viên.\n\n"
    "**Cross-encoder khác dense**: dense mã hóa câu hỏi và chunk *riêng* thành hai vector rồi so cosine (nhanh, vector "
    "chunk tính sẵn, nhưng thô). Cross-encoder *ghép* câu hỏi và chunk thành một chuỗi và đưa vào model một lượt, nên "
    "từng từ của câu hỏi đối chiếu trực tiếp với từng từ của chunk (chính xác hơn, nhưng phải chạy model cho từng cặp "
    "nên chỉ dùng chấm lại 20 ứng viên).\n\n"
    "**Giới hạn**: chỉ xếp lại, không tìm thêm (chunk đúng ngoài top-20 thì không cứu được); cắt ở 512 token mỗi "
    "cặp; chạy CPU nên chậm; điểm chỉ so sánh được trong cùng một truy vấn.")
METADATA_DESC = ("**Metadata**: bộ lọc `version` (2012 hoặc 2019) giới hạn tìm kiếm vào đúng bộ luật khi câu hỏi nêu "
                 "rõ; câu không nêu thì tìm trên cả hai. Mỗi chunk cũng mang metadata nguồn, trang, Điều.")


def describe_retrieval(config: dict, ds_key: str) -> list[str]:
    """Các dòng mô tả cách retrieval của một lần chạy (ngữ nghĩa/từ khóa, tham số, metadata)."""
    if not config:
        return []
    lines = [METHOD_DESC.get(config.get("method", ""), f"Phương pháp: `{config.get('method', '?')}`")]
    lines.append(f"Lấy top-{config.get('top_k', '?')} chunk mỗi lượt, tối đa {config.get('max_searches', '?')} lượt "
                 f"search, ngân sách context {config.get('budget_chars', '?')} ký tự"
                 + (", thêm Điều liền kề" if config.get("neighbors") else "")
                 + (", viết lại truy vấn giữa các lượt" if config.get("rewrite") else "") + ".")
    if ds_key == "basic":
        lines.append(METADATA_DESC)
    return lines


def trace_filter(trace: dict) -> dict | None:
    """Bộ lọc metadata đã dùng khi search câu này (None nếu không lọc)."""
    for e in trace.get("events", []):
        if e.get("event") == "search":
            return e.get("filter") or None
    return None


def list_runs(ds: Dataset, root: Path = Path(".")) -> list[Path]:
    found = []
    for rd in ds.results_dirs:
        base = Path(root) / rd
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if not p.is_dir():
                continue
            if (p / "traces.json").is_file():
                found.append(p)
            found += [c for c in p.iterdir() if c.is_dir() and (c / "traces.json").is_file()]
    return sorted(found, key=lambda p: (p.name, str(p)))


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _read_labels(run_dir: Path) -> dict[str, dict]:
    labels: dict[str, dict] = {}
    audit = run_dir / "audit"
    for name in ("answer_audit.csv", "pass_fail.csv"):
        path = audit / name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                col = next((c for c in _LABEL_COLUMNS if c in row), None)
                if col and row.get("query_id"):
                    label = (row[col] or "").strip()
                    if not label and (row.get("abstention_correct") or "").strip():  # câu thiếu bằng chứng: không có điểm 0-2
                        label = "từ chối đúng" if row["abstention_correct"].strip().lower() == "true" else "từ chối sai"
                    labels[row["query_id"]] = {"label": label, "reason": row.get("reason") or ""}
    return labels


def load_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    return {"traces": _read_json(run_dir / "traces.json", []), "summary": _read_json(run_dir / "summary.json", {}),
            "config": _read_json(run_dir / "config.json", {}), "labels": _read_labels(run_dir)}


def load_questions_by_id(ds: Dataset, root: Path = Path(".")) -> dict[str, dict]:
    return {q["id"]: q for q in _read_json(Path(root) / ds.questions_path, [])}


def trace_overview(traces: list[dict], labels: dict, questions: dict) -> list[dict]:
    rows = []
    for t in traces:
        qid = t.get("query_id", "")
        q = questions.get(qid, {})
        rows.append({"id": qid, "type": q.get("type") or q.get("group") or "", "status": t.get("status", ""),
                     "searches": t.get("searches", 0), "seconds": t.get("seconds", 0),
                     "tokens": (t.get("tokens_in") or 0) + (t.get("tokens_out") or 0),
                     "label": labels.get(qid, {}).get("label", "")})
    return rows


def search_rounds(trace: dict) -> list[dict]:
    rounds = []
    for e in trace.get("events", []):
        if e.get("event") != "search":
            continue
        in_ctx = set(e.get("context_ids", []))
        rounds.append({"query": e.get("query", ""), "results": [
            {"rank": i, "id": r["id"], "score": r.get("score"), "page": r.get("page"), "in_context": r["id"] in in_ctx}
            for i, r in enumerate(e.get("results", []), start=1)]})
    return rounds


def context_blocks(trace: dict) -> list[dict]:
    ctx = trace.get("context") or ""
    if not ctx.strip():
        return []
    blocks = []
    for part in re.split(r"\n\n(?=\[)", ctx):
        m = re.match(r"\[([^\]\n]*)\]\n?(.*)", part, re.S)
        if not m:
            blocks.append({"id": "", "header": "", "text": part})
            continue
        header = m.group(1)
        blocks.append({"id": header.split(" | ")[0].strip(), "header": header, "text": m.group(2)})
    return blocks


def cited_images(trace: dict, ds: Dataset, root: Path) -> list[Path]:
    if ds.image_root is None:
        return []
    out = []
    for region in trace.get("citation_regions") or []:
        img = region.get("image")
        if not img:
            continue
        for cand in (Path(root) / img, Path(root) / ds.image_root / img):
            if cand.is_file():
                out.append(cand)
                break
    return out


def describe_config(cfg: dict) -> str:
    """Mô tả một config.json bằng tiếng Việt ngắn gọn, để đọc to khi demo."""
    if not cfg:
        return "chưa có config.json"
    parts = [f"{cfg.get('method', '?')}", f"top-{cfg.get('top_k', '?')}",
             f"tối đa {cfg.get('max_searches', '?')} lượt tìm", f"ngân sách context {cfg.get('budget_chars', '?')} ký tự"]
    if cfg.get("pack") == "round_robin":
        parts.append("đóng gói round-robin (xen kẽ kết quả các lượt tìm)")
    if cfg.get("neighbors"):
        parts.append("thêm điều luật liền kề")
    if cfg.get("rewrite"):
        parts.append("gợi ý viết lại/tách câu hỏi")
    if cfg.get("figure_reader"):
        parts.append("đọc hình bằng vision model")
    return " · ".join(parts)


def run_meta(run_dir: Path) -> dict:
    """Thông tin nhẹ về một run (không đọc traces.json): config, split, số câu, đạt/chấm."""
    run_dir = Path(run_dir)
    summary, labels = _read_json(run_dir / "summary.json", {}), _read_labels(run_dir)
    values = [v["label"] for v in labels.values()]
    pass_fail = [v for v in values if v in ("pass", "fail")]
    return {"config": _read_json(run_dir / "config.json", {}), "split": summary.get("split", ""),
            "n": summary.get("n_questions"), "labeled": len(pass_fail), "passed": pass_fail.count("pass")}


def run_label(run_dir: Path, base: Path, meta: dict) -> str:
    rel = Path(run_dir).relative_to(base).as_posix() if Path(run_dir).is_relative_to(base) else Path(run_dir).name
    if "/" in rel:
        return f"[lịch sử] {rel}"
    parts = [rel]
    if meta.get("split"):
        parts.append(meta["split"])
    if meta.get("n"):
        parts.append(f"{meta['n']} câu")
    if meta.get("labeled"):
        parts.append(f"đạt {meta['passed']}/{meta['labeled']}")
    return " · ".join(parts)


_METHOD_ORDER = ("dense", "bm25", "bm25-bigram", "hybrid", "dense-rerank", "hybrid-rerank")


def retrieval_compare_rows(root: Path = Path(".")) -> list[dict]:
    """Một dòng mỗi phương pháp: Hit@1, Evidence Hit@3, thời gian (từ results/retrieval/*-dev/summary.json)."""
    rows = []
    for p in sorted((Path(root) / "results" / "retrieval").glob("*-dev/summary.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            rows.append({"method": d["method"], "Hit@1": f"{d['hit1']}/{d['n']}", "Hit@3": f"{d['hit3']}/{d['n']}",
                         "giây": round(d["seconds_total"], 1)})
        except (OSError, ValueError, KeyError):
            continue
    rows.sort(key=lambda r: _METHOD_ORDER.index(r["method"]) if r["method"] in _METHOD_ORDER else 99)
    return rows


def agent_compare_rows(root: Path, ds: Dataset) -> list[dict]:
    """Một dòng mỗi lần chạy agent trên dev: CER, số câu trả lời/từ chối, token, thời gian."""
    rows = []
    for rd in ds.results_dirs:
        for p in sorted((Path(root) / rd).glob("*/summary.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if d.get("split") != "dev":
                    continue
                sc, cer = d.get("status_counts", {}), d.get("context_evidence_rate") or {}
                rows.append({"cấu hình": d["config"], "CER": f"{cer.get('n', '?')}/{cer.get('N', '?')}",
                             "trả lời / từ chối": f"{sc.get('answered', 0)} / {sc.get('abstain', 0)}",
                             "lỗi": sc.get("error", 0), "token": d.get("tokens_in", 0) + d.get("tokens_out", 0),
                             "giây": round(d.get("seconds_total", 0), 1)})
            except (OSError, ValueError, KeyError):
                continue
    return rows
