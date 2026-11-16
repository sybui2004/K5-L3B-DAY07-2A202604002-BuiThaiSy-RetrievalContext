# Streamlit Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một app Streamlit 2 tab (Trace phát lại, Live gọi thật) để demo agent RAG của Day 7 cho cả bộ Cơ bản và Bonus HELM.

**Architecture:** Logic tách khỏi giao diện: `demo/traces.py` (đọc và chuẩn hóa kết quả đã lưu), `demo/live.py` (dựng retriever/controller và chạy một câu bằng `src.agent.run_question`), `demo/app.py` (chỉ ghép UI). Hai module đầu không import streamlit để test bằng `unittest` với dữ liệu nhỏ và mock.

**Tech Stack:** Python 3.11, streamlit 1.67 (đã cài), pandas (đã cài), unittest (giống `tests/` hiện có), `src/` và `bonus/src/` có sẵn.

**Spec:** `docs/superpowers/specs/2026-11-16-streamlit-demo-design.md`

## Global Constraints

- Không sửa file trong `src/` và `bonus/src/`.
- Không có đường nào chạy split `test`; Live chỉ nhận câu có `split == "dev"` hoặc câu tự gõ.
- Không in hay hiển thị `DEEPSEEK_API_KEY` và `DATABASE_URL`; lỗi hiển thị phải qua `_scrub` kiểu `src.agent` (thay bí mật bằng `<hidden>`).
- Thiếu DB, Ollama hoặc khóa thì chỉ tab Live báo lỗi; tab Trace vẫn chạy.
- Chạy app: `streamlit run demo/app.py` từ thư mục gốc repo. Test: `python -m unittest discover -s tests -v`.
- Giao diện tiếng Việt.

## Review Focus

- Thư mục run không có `audit/` hoặc `summary.json` (vd `_history`, `check-*`): vẫn liệt kê/mở được, nhãn để trống.
- `traces.json` có trace `status == "error"` hoặc `answer == None`: hiển thị lỗi, không crash.
- Run có chunk `image_path` là `None` (bảng) hoặc file ảnh không tồn tại: bỏ qua ảnh, không crash.
- Câu hỏi thiếu bằng chứng (`gold` rỗng / `answerable == False`): hiển thị "không có evidence chuẩn".
- `.env` thiếu biến hoặc DB tắt khi bấm chạy Live: trả về thông báo lỗi, không văng traceback ra UI và không lộ bí mật.

---

## File Structure

- Create `demo/__init__.py`, `demo/traces.py`, `demo/live.py`, `demo/app.py`
- Create `tests/test_demo_traces.py`, `tests/test_demo_live.py`, `tests/test_demo_app.py`
- Modify `requirements.txt` (thêm `streamlit>=1.40`), `README.md` (một đoạn ngắn "Giao diện demo")

### Task 1: Đọc và chuẩn hóa kết quả đã lưu (`demo/traces.py`)

**Files:**
- Create: `demo/__init__.py` (rỗng), `demo/traces.py`
- Test: `tests/test_demo_traces.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Dataset: key: str; label: str; results_dirs: tuple[str, ...]; configs_dir: str; questions_path: str; label_file: str; image_root: str | None`
  - `DATASETS: dict[str, Dataset]` với hai khóa:
    - `"basic"`: results `("results/agent",)`, configs `"configs"`, questions `"benchmark/questions.json"`, label_file `"answer_audit.csv"`, image_root `None`.
    - `"bonus"`: results `("bonus/results",)`, configs `"bonus/configs"`, questions `"bonus/benchmark/questions.json"`, label_file `"pass_fail.csv"`, image_root `"bonus"` (người làm kiểm tra cách `image_path` trong `traces.json` ghép với thư mục này, vd `bonus/data/figures/fig01_p002.png`).
  - `list_runs(ds: Dataset, root: Path = Path(".")) -> list[Path]`: các thư mục chứa `traces.json`, trực tiếp dưới `results_dirs` hoặc sâu thêm một cấp; sắp xếp theo tên.
  - `load_run(run_dir: Path) -> dict` với khóa `traces` (list), `summary` (dict, `{}` nếu thiếu), `config` (dict, `{}` nếu thiếu), `labels` (dict `query_id -> {"label": str, "reason": str}`, `{}` nếu không có audit; Cơ bản dùng cột `answer_grade_0_2` và `reason`, Bonus dùng `pass_fail` và `reason`; đọc CSV bằng `utf-8-sig`).
  - `load_questions_by_id(ds: Dataset, root: Path = Path(".")) -> dict[str, dict]`.
  - `trace_overview(traces: list[dict], labels: dict, questions: dict) -> list[dict]`: mỗi dòng có `id, type` (`type` hoặc `group` của câu hỏi, `""` nếu thiếu), `status, searches, seconds, tokens, label`.
  - `search_rounds(trace: dict) -> list[dict]`: mỗi lượt search `{"query": str, "results": [{"rank": int, "id": str, "score": float | None, "page": int, "in_context": bool}]}` suy ra từ `events` và `context_ids` của lượt đó.
  - `context_blocks(trace: dict) -> list[dict]`: tách `trace["context"]` theo chuỗi `\n\n[` thành `{"id": str, "header": str, "text": str}` (header là phần trong `[...]` đầu khối).
  - `cited_images(trace: dict, ds: Dataset, root: Path) -> list[Path]`: đường dẫn ảnh tồn tại của `citation_regions[*].image`; rỗng nếu `image_root` là `None` hoặc không có file.

- [ ] **Step 1: Viết test thất bại.** Dùng thư mục tạm dựng bằng `tempfile`, ghi `traces.json` với 2 trace (một `answered` có 2 lượt search, một `error` với `answer: None`) và `summary.json`, `audit/answer_audit.csv` có BOM. Các test cần có, mỗi test một assert chính:
  - `test_list_runs_finds_nested_run_dirs`
  - `test_load_run_without_audit_or_summary_returns_empty_labels` (Review Focus 1)
  - `test_load_run_reads_basic_and_bonus_label_columns`
  - `test_search_rounds_marks_in_context_and_rank_starts_at_1`
  - `test_trace_overview_handles_error_trace` (Review Focus 2: `status == "error"`, `tokens` vẫn là số)
  - `test_context_blocks_splits_on_chunk_headers`
  - `test_cited_images_skips_none_and_missing_files` (Review Focus 3)
- [ ] **Step 2: Chạy** `python -m unittest tests.test_demo_traces -v`. Mong đợi: lỗi `ModuleNotFoundError: demo`.
- [ ] **Step 3: Cài đặt** các hàm theo Interfaces; `tokens = tokens_in + tokens_out` với `.get(..., 0)`. Thêm `sys.path.insert` đầu file test giống `tests/test_run_agent.py`.
- [ ] **Step 4: Chạy lại** lệnh trên. Mong đợi: tất cả PASS.
- [ ] **Step 5: Chạy thử trên dữ liệu thật** bằng một lệnh `python -c` in `len(list_runs(DATASETS["basic"]))` và `len(list_runs(DATASETS["bonus"]))`; cả hai phải > 0.
- [ ] **Step 6: Commit** (chỉ khi bạn yêu cầu commit; mặc định để bạn tự commit).

### Task 2: Chạy live và so sánh retrieval (`demo/live.py`)

**Files:**
- Create: `demo/live.py`
- Test: `tests/test_demo_live.py`

**Interfaces:**
- Consumes: `Dataset`, `DATASETS` từ Task 1; `src.agent.AgentConfig`, `src.agent.run_question(q, cfg, retriever, controller, *, all_chunks, secrets)`; `src.config.load_config`; `src.llm.DeepSeekController`; Cơ bản: `src.eval_retrieval.build_retriever(method, cfg)`, `src.store_day6.load_day6_chunks(cfg)`, `src.prompts.build_system_prompt(rewrite)`; Bonus: `bonus.src.store.build_retriever(method, cfg, chunks)`, `bonus.src.store.load_chunks(cfg)`, `bonus.src.prompts.SYSTEM_PROMPT` và `MULTI_PART_HINT`, `max_tokens=1800` cho controller.
- Produces:
  - `METHODS = {"basic": ("dense", "bm25", "bm25-bigram", "hybrid"), "bonus": ("dense", "bm25", "hybrid")}`
  - `list_configs(ds: Dataset, root: Path = Path(".")) -> dict[str, AgentConfig]` (đọc `*.json` trong `configs_dir`).
  - `dev_questions(ds: Dataset, root: Path = Path(".")) -> list[dict]` (chỉ `split == "dev"`).
  - `run_live(ds_key: str, question: str, cfg: AgentConfig, *, filters: dict | None = None, deps: "LiveDeps | None" = None) -> dict`: trả về trace hợp lệ như `run_question`; thêm khóa `citation_regions` cho Bonus giống `bonus/src/run_bonus.py`. Mọi lỗi thiết lập (thiếu biến môi trường, DB tắt) trả về trace `status="error"` với `error` đã `_scrub`, không raise.
  - `compare_methods(ds_key: str, question: str, *, top_k: int = 3, filters: dict | None = None, deps=None) -> dict[str, list[dict] | str]`: với mỗi method trong `METHODS[ds_key]` gọi `retriever.search(question, filters=filters, top_k=top_k)` (không gọi LLM) và trả về danh sách `{"rank", "id", "score", "page"}`; method lỗi thì giá trị là chuỗi lỗi đã scrub.
  - `LiveDeps` (dataclass) gom các hàm dựng phụ thuộc (`load_config`, `build_retriever`, `load_chunks`, `make_controller`) để test thay bằng mock; mặc định trỏ vào các hàm thật ở trên. Chunks và retriever được cache theo `(ds_key, method)` trong một dict ở cấp module để lần chạy thứ hai không nạp lại.

- [ ] **Step 1: Viết test thất bại** với `LiveDeps` giả (retriever trả 2 chunk cố định, controller giả `decide` trả search rồi answer có citation hợp lệ):
  - `test_run_live_returns_answered_trace_with_citation`
  - `test_run_live_missing_env_returns_error_trace_without_secret` (Review Focus 5: `load_config` giả raise `ValueError("missing environment variables: DATABASE_URL")`; assert `status == "error"` và `error` không chứa giá trị khóa giả được đặt trong `secrets`)
  - `test_run_live_db_down_returns_error_trace` (`build_retriever` raise `OSError`)
  - `test_compare_methods_isolates_failure_per_method` (một method raise, các method khác vẫn có kết quả)
  - `test_list_configs_reads_json_files`
  - `test_dev_questions_never_returns_test_split`
- [ ] **Step 2: Chạy** `python -m unittest tests.test_demo_live -v`. Mong đợi: FAIL (module chưa có).
- [ ] **Step 3: Cài đặt** theo Interfaces. Cơ bản và Bonus dựng controller/retriever khác nhau như mô tả ở Consumes; `secrets = [cfg.deepseek_api_key, cfg.database_url]`.
- [ ] **Step 4: Chạy lại.** Mong đợi: PASS.
- [ ] **Step 5: Thử thật (nếu Docker, Ollama đang chạy):** `python -c` gọi `compare_methods("basic", "Thời giờ làm việc bình thường tối đa là bao nhiêu giờ một ngày?")`; mong đợi 4 method có kết quả. Nếu hạ tầng chưa chạy, ghi rõ là chưa kiểm chứng thật.

### Task 3: Giao diện (`demo/app.py`) và tài liệu

**Files:**
- Create: `demo/app.py`
- Test: `tests/test_demo_app.py`
- Modify: `requirements.txt`, `README.md`

**Interfaces:**
- Consumes: mọi hàm ở Task 1 và Task 2.
- Produces: `render_trace(trace: dict, question: dict | None, ds: Dataset, root: Path)` dùng chung cho hai tab; `main()` gọi ở cấp module khi chạy bằng streamlit.

- [ ] **Step 1: Viết test thất bại** bằng `streamlit.testing.v1.AppTest.from_file("demo/app.py")` (chạy từ thư mục gốc, dữ liệu thật trong `results/`):
  - `test_app_runs_without_exception_on_basic_dataset` (`at.run()` rồi `assert not at.exception`)
  - `test_app_runs_without_exception_on_bonus_dataset` (đặt selectbox/radio bộ dữ liệu sang `bonus`)
  - `test_live_tab_without_infrastructure_shows_error_not_exception` (đặt `DATABASE_URL` sai bằng `monkeypatch`/`os.environ`, bấm nút chạy; assert không có `at.exception`)
- [ ] **Step 2: Chạy** `python -m unittest tests.test_demo_app -v`. Mong đợi: FAIL (file chưa có).
- [ ] **Step 3: Cài đặt `demo/app.py`:**
  - Thanh bên: radio chọn bộ dữ liệu từ `DATASETS`, cố định `st.set_page_config(layout="wide", page_title="Day 7 · Agentic RAG")`.
  - `st.tabs(["Trace", "Live"])`.
  - **Tab Trace:** selectbox chọn run từ `list_runs`; `st.metric` cho số câu, từng trạng thái, context evidence rate (`n/N`), token, giây (đọc từ `summary`; thiếu thì bỏ qua); `st.dataframe` từ `trace_overview` (chọn dòng để mở câu; nếu `on_select` bất tiện thì dùng selectbox id câu); gọi `render_trace`.
  - **`render_trace`:** hiện trạng thái và lỗi (nếu có); câu trả lời; citation; mỗi lượt search là một `st.expander` kèm bảng top-k, chunk có `in_context` được đánh dấu; context theo `context_blocks` trong expander, chunk được trích dẫn đánh dấu; khối "Đáp án và evidence chuẩn" từ `question` (câu thiếu bằng chứng ghi "không có evidence chuẩn"); nhãn và lý do từ audit nếu có; ảnh từ `cited_images` bằng `st.image`.
  - **Tab Live:** selectbox chọn nhanh câu dev (kèm lựa chọn "Tự nhập"), `st.text_area` câu hỏi, selectbox cấu hình từ `list_configs`, selectbox ghi đè method (mặc định theo cấu hình), nút "Chạy agent" (spinner, rồi `render_trace`, hiện giây và token) và nút "So sánh các phương pháp" (bảng theo cột cho từng method). Kết quả giữ trong `st.session_state` để không mất khi rerun.
- [ ] **Step 4: Chạy lại** test ở Step 2. Mong đợi: PASS.
- [ ] **Step 5: Thêm `streamlit>=1.40`** vào `requirements.txt` và đoạn "Giao diện demo" (lệnh chạy, hai tab, điều kiện cho tab Live: Docker Postgres, Ollama `bge-m3`, `.env`) vào `README.md`.
- [ ] **Step 6: Chạy toàn bộ test** `python -m unittest discover -s tests -v`. Mong đợi: không có test cũ nào hỏng.
- [ ] **Step 7: Mở app thật** `streamlit run demo/app.py`, kiểm tra bằng mắt tab Trace ở cả hai bộ dữ liệu (một câu có citation, một câu từ chối, một ảnh Bonus nếu có) và tab Live nếu hạ tầng đang chạy. Báo rõ phần nào đã/chưa kiểm chứng.

---

## Self-review

- Phủ spec: 2 tab, chọn bộ dữ liệu, summary + bảng + chi tiết trace, ảnh Bonus, Live với cấu hình và ghi đè method, so sánh retrieval, lỗi hạ tầng chỉ ảnh hưởng tab Live, không test split, không lộ bí mật, `requirements.txt`: đều có task.
- Tên và kiểu thống nhất giữa các task (`Dataset`, `DATASETS`, `run_live`, `compare_methods`, `render_trace`).
- Tỷ lệ: plan chỉ ghi chữ ký, test và giá trị cố định; thân hàm do người làm viết.
