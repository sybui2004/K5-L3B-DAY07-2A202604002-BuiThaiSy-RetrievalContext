"""Giao diện demo Day 7: tab Trace (phát lại kết quả đã lưu) và tab Live (gọi agent thật).
Chạy từ thư mục gốc repo: streamlit run demo/app.py"""
import dataclasses
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from demo.chunk_map import KIND_HUE, KIND_LABEL, chunk_rows, kind_stats, length_histogram, map_html  # noqa: E402
from demo.live import METHODS, compare_methods, dev_questions, list_configs, rerank_breakdown, rrf_breakdown, run_live  # noqa: E402
from demo.traces import (DATASETS, RERANK_CRITERION_TEXT, Dataset, agent_compare_rows, retrieval_compare_rows, cited_images, context_blocks, describe_config,  # noqa: E402
                         describe_retrieval, list_runs, load_questions_by_id, load_run, run_label, run_meta,
                         search_rounds, trace_filter, trace_overview)

STATUS_ICON = {"answered": "✅", "abstain": "🚫", "error": "⚠️"}
STATUS_NOTE = "✅ answered: có câu trả lời kèm citation hợp lệ · 🚫 abstain: từ chối vì không đủ bằng chứng · ⚠️ error: lỗi hệ thống"
DATASET_NOTES = {
    "basic": "Hai Bộ luật Lao động 2012 và 2019 (PDF công báo), đã chia chunk theo Điều ở Day 6 (bảng `chunks_b`). "
             "Câu hỏi gồm tra cứu trực tiếp, so sánh hai bộ luật, và câu thiếu bằng chứng để kiểm tra từ chối.",
    "bonus": "Bài báo HELM (162 trang), 863 chunk: 654 `text`, 169 `table` và 40 `figure`. "
             "Trích xuất bằng PyMuPDF (văn bản, bảng, chữ vector trong hình); mô tả hình bằng `qwen2.5vl:7b` (Ollama, chạy local); "
             "embedding `bge-m3` (1024 chiều) lưu ở pgvector. Văn bản chia đoạn ≤1100 ký tự; bảng chuyển markdown, "
             "gom dòng ≤700 ký tự lặp dòng tiêu đề (Table 5, 6, 13: mỗi dòng một chunk); mỗi hình là một chunk gồm "
             "caption + chữ trong hình + mô tả của vision model. Chunk bảng và hình giữ `page`, `bbox` và ảnh crop để "
             "đối chiếu lại với PDF.",
}
SPLIT_NOTES = {
    "dev": "dev: bộ để thử cấu hình và chọn cấu hình tốt nhất.",
    "test": "test: bộ chấm điểm, chỉ chạy một lần sau khi đã chốt cấu hình.",
    "retired": "retired: bộ test cũ, đã bị dùng để soi lỗi nên không còn báo điểm (chỉ để chẩn đoán).",
}


def render_trace(trace: dict, question: dict | None, ds: Dataset, root: Path, label: dict | None = None) -> None:
    status = trace.get("status", "")
    tokens = (trace.get("tokens_in") or 0) + (trace.get("tokens_out") or 0)
    st.markdown(f"**Trạng thái:** {STATUS_ICON.get(status, '')} `{status}` · {trace.get('searches', 0)} lượt search · "
                f"{trace.get('seconds', 0)} giây · {tokens} token")
    if trace.get("error"):
        st.error(trace["error"])
    if trace.get("answer"):
        st.markdown("##### Câu trả lời")
        st.markdown(trace["answer"])
    if trace.get("citations"):
        st.markdown("**Citation:** " + ", ".join(f"`{c}`" for c in trace["citations"]))
    if label and label.get("label"):
        st.info(f"Nhãn đã lưu: **{label['label']}**" + (f" — {label['reason']}" if label.get("reason") else ""))
    for img in cited_images(trace, ds, root):
        st.image(str(img), caption=img.name)

    st.markdown("##### Các lượt search")
    flt = trace_filter(trace)
    if ds.key == "basic":
        st.caption("Lọc metadata: " + (", ".join(f"`{k} = {v}`" for k, v in flt.items()) if flt
                                       else "không lọc (tìm trên cả Luật 2012 và 2019)"))
    rounds = search_rounds(trace)
    if not rounds:
        st.caption("Không có lượt search nào.")
    for i, r in enumerate(rounds, start=1):
        with st.expander(f"Lượt {i}: {r['query']}", expanded=(i == 1)):
            df = pd.DataFrame([{"rank": x["rank"], "chunk": x["id"], "score": x["score"], "trang": x["page"],
                                "vào context": "✅" if x["in_context"] else ""} for x in r["results"]])
            st.dataframe(df, hide_index=True, width="stretch")

    blocks = context_blocks(trace)
    with st.expander(f"Context đã ghép ({len(blocks)} chunk)"):
        cited = set(trace.get("citations") or [])
        for b in blocks:
            mark = "📌 " if b["id"] in cited else ""
            st.markdown(f"**{mark}[{b['header']}]**" + (" — được trích dẫn" if mark else ""))
            st.text(b["text"])

    if question is not None:
        st.markdown("##### Đáp án và evidence chuẩn")
        st.write(question.get("expected_answer") or "—")
        gold = question.get("gold") or []
        if question.get("answerable") is False or not gold:
            st.caption("Không có evidence chuẩn (câu thiếu bằng chứng: agent nên từ chối).")
        for g in gold:
            st.markdown(f"- `{g.get('source_id')}` trang {g.get('page')}: {g.get('evidence', '')}")


def _metrics(summary: dict) -> None:
    if not summary:
        return
    cols = st.columns(7)
    counts = summary.get("status_counts") or {}
    cols[0].metric("Số câu", summary.get("n_questions", "—"))
    cols[1].metric("✅ Trả lời", counts.get("answered", 0))
    cols[2].metric("🚫 Từ chối", counts.get("abstain", 0))
    cols[3].metric("⚠️ Lỗi", counts.get("error", 0))
    cer = summary.get("context_evidence_rate")
    cols[4].metric("Context có evidence", f"{cer['n']}/{cer['N']}" if isinstance(cer, dict) else "—")
    cols[5].metric("Token", (summary.get("tokens_in") or 0) + (summary.get("tokens_out") or 0))
    cols[6].metric("Giây", summary.get("seconds_total", "—"))


@st.cache_data(show_spinner=False)
def _run_options(ds_key: str) -> dict[str, tuple[str, dict]]:
    """label -> (đường dẫn run, meta); chỉ các run trực tiếp, bỏ `_history*` và `metrics_inputs`."""
    ds = DATASETS[ds_key]
    base = ROOT / ds.results_dirs[0]
    items = [(run_label(p, base, (m := run_meta(p))), str(p), m) for p in list_runs(ds, ROOT) if p.parent == base]
    items.sort(key=lambda x: x[0])
    return {label: (path, meta) for label, path, meta in items}


def _describe_run(meta: dict, ds: Dataset) -> None:
    lines = [f"**Cấu hình:** {describe_config(meta['config'])}"]
    if meta["split"]:
        lines.append(f"**Bộ câu hỏi:** {SPLIT_NOTES.get(meta['split'], meta['split'])}")
    if meta["labeled"]:
        lines.append(f"**Kết quả theo nhãn đã lưu:** đạt {meta['passed']}/{meta['labeled']} câu "
                     "(nhãn do tác giả chấm, lý do ở cột reason)")
    st.info("\n\n".join(lines))


def trace_tab(ds: Dataset) -> None:
    options = _run_options(ds.key)
    if not options:
        st.warning("Chưa có kết quả đã lưu cho bộ dữ liệu này.")
        return
    st.caption("Mỗi \"lần chạy\" là một lần agent trả lời cả bộ câu hỏi với một cấu hình. "
               "Tên có dạng `cấu hình-bộ câu hỏi`.")
    choice = st.selectbox("Lần chạy", list(options), key="trace_run")
    run_dir = Path(options[choice][0])
    _describe_run(options[choice][1], ds)
    run = load_run(run_dir)
    questions = load_questions_by_id(ds, ROOT)
    _metrics(run["summary"])
    desc = describe_retrieval(run["config"], ds.key)
    if desc:
        st.info("**Cách retrieval của lần chạy này**\n\n" + "\n\n".join(f"- {d}" for d in desc))
        if str(run["config"].get("method", "")).endswith("-rerank"):
            with st.expander("Rerank theo tiêu chí gì, cross-encoder hoạt động thế nào?"):
                st.markdown(RERANK_CRITERION_TEXT)
    traces = run["traces"]
    if not traces:
        st.warning("File traces.json rỗng.")
        return
    st.markdown("##### Bảng câu hỏi")
    st.caption(STATUS_NOTE + " · searches: số lượt tìm · label: nhãn đã lưu (Bonus: pass/fail, Cơ bản: điểm 0–2)")
    st.dataframe(pd.DataFrame(trace_overview(traces, run["labels"], questions)), hide_index=True,
                 width="stretch")
    by_id = {t.get("query_id"): t for t in traces}
    labels_by_id = {i: f"{i} · {(questions.get(i) or {}).get('question', '')[:90]}" for i in by_id}
    chosen = st.selectbox("Mở câu hỏi", list(labels_by_id.values()), key="trace_question")
    qid = next(i for i, lab in labels_by_id.items() if lab == chosen)
    q = questions.get(qid)
    if q:
        st.markdown(f"**Câu hỏi:** {q.get('question', '')}")
    render_trace(by_id[qid], q, ds, ROOT, run["labels"].get(qid))


def _pick_dev_question() -> None:
    chosen = st.session_state.get("live_pick")
    if chosen and chosen != "Tự nhập":
        st.session_state["live_question"] = chosen.split(" · ", 1)[1]


def live_tab(ds: Dataset) -> None:
    st.caption("Gọi thật: Postgres, Ollama (bge-m3) và DeepSeek. Chỉ dùng câu dev hoặc câu tự nhập, không có split test.")
    try:
        dev = dev_questions(ds, ROOT)
    except (OSError, ValueError):
        dev = []
    st.selectbox("Chọn nhanh câu dev", ["Tự nhập"] + [f"{q['id']} · {q['question']}" for q in dev],
                 key="live_pick", on_change=_pick_dev_question)
    question = st.text_area("Câu hỏi", key="live_question")
    configs = list_configs(ds, ROOT)
    if not configs:
        st.warning("Không tìm thấy cấu hình nào.")
        return
    c1, c2 = st.columns(2)
    cfg_name = c1.selectbox("Cấu hình", list(configs), key="live_config")
    override = c2.selectbox("Phương pháp retrieval", ["(theo cấu hình)", *METHODS[ds.key]], key="live_method")
    cfg = configs[cfg_name]
    if override != "(theo cấu hình)":
        cfg = dataclasses.replace(cfg, method=override)
    filters = None
    if ds.key == "basic":
        version = st.selectbox("Lọc metadata: phiên bản luật", ["(không lọc)", "2012", "2019"], key="live_version")
        filters = None if version == "(không lọc)" else {"version": version}
    for line in describe_retrieval(dataclasses.asdict(cfg), ds.key):
        st.caption(line)
    b1, b2 = st.columns(2)
    run_clicked = b1.button("Chạy agent", key="run_live", type="primary", disabled=not question.strip())
    cmp_clicked = b2.button("So sánh các phương pháp", key="compare_live", disabled=not question.strip())
    if run_clicked:
        with st.spinner("Đang chạy agent..."):
            st.session_state["live_trace"] = (ds.key, question, run_live(ds.key, question, cfg, filters=filters))
    if cmp_clicked:
        with st.spinner("Đang truy xuất..."):
            st.session_state["live_compare"] = (ds.key, question, compare_methods(ds.key, question, top_k=cfg.top_k,
                                                                                  filters=filters))
            st.session_state["live_rerank"] = (ds.key, question, rerank_breakdown(
                ds.key, question, top_k=cfg.top_k, filters=filters) if "hybrid-rerank" in METHODS[ds.key] else None)
            st.session_state["live_rrf"] = (ds.key, question, rrf_breakdown(ds.key, question, top_k=cfg.top_k,
                                                                          filters=filters))
    cmp = st.session_state.get("live_compare")
    if cmp and cmp[0] == ds.key:
        st.markdown("##### So sánh retrieval (không gọi LLM)")
        cols = st.columns(len(cmp[2]))
        for col, (method, res) in zip(cols, cmp[2].items()):
            col.markdown(f"**{method}**")
            if isinstance(res, str):
                col.error(res)
            else:
                col.dataframe(pd.DataFrame(res), hide_index=True, width="stretch")
        rrf = st.session_state.get("live_rrf")
        if rrf and rrf[0] == ds.key and "hybrid" in cmp[2]:
            st.markdown("##### Điểm RRF của hybrid")
            st.caption("Mỗi phía (dense, từ khóa) xếp hạng top-20 riêng; chunk ở hạng r được cộng 1/(60 + r). "
                       "Điểm hybrid = điểm dense + điểm từ khóa, nên chunk có mặt ở cả hai phía lên cao. "
                       "Ô trống = chunk không nằm trong top-20 của phía đó.")
            if isinstance(rrf[2], str):
                st.error(rrf[2])
            else:
                st.dataframe(pd.DataFrame(rrf[2]).rename(columns={
                    "id": "chunk", "page": "trang", "dense_rank": "hạng dense", "lexical_rank": "hạng từ khóa",
                    "rrf_dense": "điểm dense", "rrf_lexical": "điểm từ khóa", "score": "tổng RRF"}),
                    hide_index=True, width="stretch")
        rer = st.session_state.get("live_rerank")
        if rer and rer[0] == ds.key and rer[2] is not None and "hybrid-rerank" in cmp[2]:
            st.markdown("##### Rerank bằng cross-encoder")
            st.caption("Hạng trước = hạng trong top-20 của hybrid; hạng sau = hạng theo điểm cross-encoder. "
                       "Bảng chỉ hiện các chunk còn lại trong top-k sau rerank.")
            if isinstance(rer[2], str):
                st.error(rer[2])
            else:
                st.dataframe(pd.DataFrame(rer[2]).rename(columns={
                    "id": "chunk", "page": "trang", "rank_before": "hạng trước (hybrid)",
                    "rank_after": "hạng sau rerank", "score": "điểm cross-encoder"}),
                    hide_index=True, width="stretch")
            with st.expander("Rerank theo tiêu chí gì, cross-encoder hoạt động thế nào?"):
                st.markdown(RERANK_CRITERION_TEXT)
    tr = st.session_state.get("live_trace")
    if tr and tr[0] == ds.key:
        st.markdown("##### Kết quả agent")
        match = next((q for q in dev if q["question"] == tr[1]), None)
        render_trace(tr[2], match, ds, ROOT)


@st.cache_data(show_spinner="Đang đọc chunk từ Postgres...")
def _map_rows(ds_key: str) -> list[dict]:
    from demo.live import _load_chunks, _load_config
    return chunk_rows(_load_chunks(ds_key, _load_config()))


def chunk_map_tab(ds: Dataset) -> None:
    st.caption("Mỗi cột là một trang của tài liệu; mỗi ô vuông là một chunk bắt đầu ở trang đó. "
               "Màu đậm hơn = chunk dài hơn. Di chuột lên ô để xem id, loại, độ dài và trang.")
    try:
        rows = _map_rows(ds.key)
    except Exception as e:  # noqa: BLE001 - không in thông báo gốc vì có thể chứa chuỗi kết nối DB
        st.warning(f"Không đọc được chunk từ Postgres ({type(e).__name__}). Kiểm tra Docker/DB đã chạy chưa "
                   "(xem README, mục dựng lại DB).")
        return
    if not rows:
        st.info("Chưa có chunk nào trong kho vector.")
        return
    docs = len({r["doc"] for r in rows})
    lengths = [r["char_count"] for r in rows]
    c = st.columns(4)
    c[0].metric("Số chunk", len(rows))
    c[1].metric("Số tài liệu", docs)
    c[2].metric("Độ dài trung bình (ký tự)", round(sum(lengths) / len(lengths)))
    c[3].metric("Ngắn nhất / dài nhất", f"{min(lengths)} / {max(lengths)}")
    if ds.key == "bonus":
        st.markdown("Màu theo loại: " + " · ".join(
            f"<span style='color:hsl({hue},70%,45%)'>■</span> {KIND_LABEL[k]}" for k, hue in KIND_HUE.items()),
            unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(kind_stats(rows)), hide_index=True, width="stretch")
    st.markdown(map_html(rows), unsafe_allow_html=True)
    hist = length_histogram(rows)
    if hist:
        st.markdown("##### Phân bố độ dài chunk (ký tự)")
        st.bar_chart(pd.DataFrame({"số chunk": [n for _, n in hist]}, index=[str(b) for b, _ in hist]))


GLOSSARY = (
    "- **q** (q01, q02, ...): câu *có đáp án* trong tài liệu; agent phải trả lời đúng kèm citation.\n"
    "- **u** (u01, ...): câu *thiếu bằng chứng*; hành vi đúng là tìm rồi từ chối, không bịa.\n"
    "- **Evidence**: đoạn gốc trong PDF chứa đáp án (ghi trong benchmark, agent không thấy), dùng để chấm.\n"
    "- **Citation**: `[chunk-id]` do agent tự gắn vào câu trả lời để nói nó dựa vào chunk nào.\n"
    "- **CER (Context Evidence Rate)**: số câu có đáp án mà context cuối cùng của agent chứa đủ evidence.\n"
    "- **Hit@1 / Hit@3**: chunk đầu tiên / trong top-3 có chứa evidence (chỉ đo retrieval, chưa gọi LLM).\n"
    "- **Rerank**: lấy 20 ứng viên rồi chấm lại bằng cross-encoder và giữ top-k.")


def compare_tab(ds: Dataset) -> None:
    if ds.key == "basic":
        st.markdown("##### Retrieval trên dev (query gốc, top-3, không gọi LLM)")
        rows = retrieval_compare_rows(ROOT)
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption("dense-rerank và hybrid-rerank: lấy 20 ứng viên rồi cross-encoder chấm lại. Dev chỉ 15 câu nên "
                       "hai bản rerank cùng đạt trần 15/15, chưa phân biệt được.")
        else:
            st.info("Chưa có kết quả retrieval trong results/retrieval.")
    st.markdown("##### Agent trên dev")
    arows = agent_compare_rows(ROOT, ds)
    if arows:
        st.dataframe(pd.DataFrame(arows), hide_index=True, width="stretch")
        st.caption("Từ chối nhiều hơn mức cần thiết (chỉ các câu u được từ chối đúng) là dấu hiệu từ chối nhầm; "
                   "cần đối chiếu với nhãn trong tab Trace. Token chỉ gồm token vào và ra của DeepSeek, "
                   "chưa gồm chi phí rerank cục bộ (CPU).")
    else:
        st.info("Chưa có lần chạy dev nào.")
    with st.expander("Rerank theo tiêu chí gì, cross-encoder hoạt động thế nào?", expanded=ds.key == "basic"):
        st.markdown(RERANK_CRITERION_TEXT)
    with st.expander("Thuật ngữ: q/u, evidence, citation, CER, Hit@k"):
        st.markdown(GLOSSARY)


def main() -> None:
    st.set_page_config(layout="wide", page_title="Day 7 · Agentic RAG")
    st.title("Day 7 · Agentic RAG")
    key = st.sidebar.radio("Bộ dữ liệu", list(DATASETS), key="dataset", format_func=lambda k: DATASETS[k].label)
    ds = DATASETS[key]
    st.sidebar.caption(DATASET_NOTES[key])
    st.caption("Agent tự quyết định khi nào gọi công cụ `search`, ghép kết quả thành context, rồi trả lời kèm citation "
               "`[chunk-id]` hoặc từ chối khi thiếu bằng chứng. **Trace**: xem lại kết quả đã lưu. "
               "**Live**: gọi thật Postgres + Ollama + DeepSeek.")
    tab_trace, tab_live, tab_cmp, tab_map = st.tabs(["Trace", "Live", "So sánh & rerank", "Bản đồ chunk"])
    with tab_trace:
        trace_tab(ds)
    with tab_live:
        live_tab(ds)
    with tab_cmp:
        compare_tab(ds)
    with tab_map:
        chunk_map_tab(ds)


main()
