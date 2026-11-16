# Luồng làm việc Day 7 và file xử lý từng bước

Day 7 là agent RAG trên kho vector của Day 6 (Bộ luật Lao động 2012 và 2019). Mỗi bước dưới đây ghi rõ lệnh chạy, file code xử lý, đầu vào, đầu ra và người làm.

Ký hiệu: 🤖 = chạy bằng code; 👤 = tác giả tự làm (không thể thay).

## Tổng quan

```text
[0] Chuẩn bị ─► [1] Benchmark ─► [2] Retrieval ─► [3] Agent dev ─► [4] Chấm nhãn dev
                                                                         │
[8] Nộp ◄─ [7] Báo cáo ◄─ [6] Chấm nhãn test ◄─ [5] Chốt cấu hình + chạy test ◄┘
```

Quy tắc xuyên suốt ([RULES.md](../RULES.md)): chọn và chỉnh trên **dev**; test chỉ chạy **một lần** sau khi freeze benchmark và chốt cấu hình.

---

## Bước 0. Chuẩn bị hạ tầng 🤖

| Việc | File |
|---|---|
| Dựng Postgres + pgvector (cổng 15433) | [infra/docker-compose.yml](../infra/docker-compose.yml), [infra/init.sql](../infra/init.sql) |
| Nguồn dữ liệu, giấy phép | [data/raw/](../data/raw/) (2 PDF), [data/manifest.csv](../data/manifest.csv) |
| Biến môi trường (DeepSeek, DB, Ollama) | [.env.example](../.env.example) → `.env` |
| Đọc env, không in giá trị | [src/config.py](../src/config.py) |
| Embedding câu hỏi bằng bge-m3 qua Ollama | [src/embed.py](../src/embed.py) |
| Đọc chunk Day 6 (`chunks_a/b/c`), đổi sang schema Day 7 | [src/store_day6.py](../src/store_day6.py) |

Hướng dẫn dựng lại DB: cuối [README.md](../README.md). Nạp dữ liệu (ingest) vẫn do repo Day 6 làm.

## Bước 1. Benchmark 🤖 + 👤

Đầu vào: câu hỏi Day 6 (20 câu) cộng 4 câu thiếu bằng chứng u01–u04. Đầu ra: `benchmark/questions.json`, `benchmark/freeze.json`.

| Việc | Lệnh | File |
|---|---|---|
| Chuyển câu Day 6, so khớp evidence, kiểm tra hợp lệ | `python -m src.benchmark validate` (phải in `0 problems`) | [src/benchmark.py](../src/benchmark.py) |
| 👤 Mở 2 PDF, xác nhận u01–u04 không có đáp án, điền nhật ký | sửa tay | [benchmark/README.md](../benchmark/README.md), [benchmark/questions.json](../benchmark/questions.json) (`verified_by_author`) |
| 👤 Đóng băng benchmark (ghi SHA-256) | `python -m src.benchmark freeze` | [src/benchmark.py](../src/benchmark.py) → `benchmark/freeze.json` |

Chưa freeze thì test bị chặn (`ensure_split_allowed` trong [src/eval_retrieval.py](../src/eval_retrieval.py)).

## Bước 2. So sánh các phương pháp retrieval 🤖

Yêu cầu: ít nhất 3 phương pháp, gồm dense. Dùng query gốc, top-3, chỉ số Hit@1 và Evidence Hit@3.

| Phương pháp | Lệnh | File |
|---|---|---|
| dense, bm25, bm25-bigram, hybrid, dense-rerank, hybrid-rerank | `python -m src.eval_retrieval --method <m> --split dev --out results/retrieval/<m>-dev` | [src/eval_retrieval.py](../src/eval_retrieval.py) |
| Cài đặt các retriever (`search(query, filters, top_k)`), gồm `RerankRetriever` | | [src/retrievers.py](../src/retrievers.py) |
| Tách từ tiếng Việt cho BM25 | | [src/tokenize_vi.py](../src/tokenize_vi.py) |
| Kiểm tra evidence khớp | | [src/benchmark.py](../src/benchmark.py) (`hit`) |

Kết quả dev đã có (Hit@1 và Hit@3): dense 13/15 và 14/15, bm25 11/15 và 13/15, bm25-bigram 13/15 và 13/15, hybrid 14/15 và 14/15, dense-rerank 15/15 và 15/15, hybrid-rerank 15/15 và 15/15. Bảng ở [results/retrieval/compare-dev.md](../results/retrieval/compare-dev.md).

Rerank lấy 20 ứng viên, chấm lại bằng cross-encoder `BAAI/bge-reranker-v2-m3` (cần `sentence-transformers`, chạy CPU khoảng 21 giây/câu), giữ top-k. Giải thích tiêu chí ở [results/retrieval/rerank-notes.md](../results/retrieval/rerank-notes.md).

## Bước 3. Chạy agent trên dev 🤖

Agent dùng DeepSeek thật: gọi `search` rồi trả lời kèm citation, hoặc từ chối khi thiếu bằng chứng.

```bash
python -m src.run_agent --config configs/<cấu_hình>.json --split dev --out results/agent/<cấu_hình>-dev
```

| Thành phần | File |
|---|---|
| CLI: nạp config, chạy batch, ghi tóm tắt | [src/run_agent.py](../src/run_agent.py) |
| Vòng lặp agent: tìm, ghép context theo ngân sách, trả lời, ghi trace | [src/agent.py](../src/agent.py) |
| Gọi DeepSeek, chọn giữa `search` và câu trả lời cuối | [src/llm.py](../src/llm.py) |
| System prompt và schema tool (không chứa thông tin benchmark) | [src/prompts.py](../src/prompts.py) |
| Retriever dùng trong agent | [src/retrievers.py](../src/retrievers.py) |

Cấu hình trong [configs/](../configs/):

| File | Ý nghĩa |
|---|---|
| `baseline.json` | dense, top-3, 1 lượt tìm, ngân sách 3000 ký tự |
| `improve-a.json` | 4 lượt tìm, viết lại truy vấn |
| `improve-b.json` | top-5, ngân sách 6000 ký tự, thêm Điều liền kề (đã chọn) |
| `improve-c.json` | hybrid |
| `improve-d.json` | hybrid-rerank, top-5, ngân sách 6000, không thêm Điều kề |
| `improve-e.json` | dense-rerank, các tham số còn lại như improve-d |
| `final.json` | cấu hình đã chốt, lý do ở [configs/selection.md](../configs/selection.md) |

Đầu ra mỗi lần chạy: `traces.json`, `summary.json`, `metrics_inputs/`, `audit/*.csv` (bảng chấm trống).

## Bước 4. Chấm nhãn dev 👤 rồi tính điểm 🤖

| Việc | File |
|---|---|
| Tạo bảng chấm trống | [src/audit_sheets.py](../src/audit_sheets.py) (`write_audit_sheets`, tự gọi khi chạy agent) |
| 👤 Điền điểm câu trả lời, citation, abstention | `results/agent/<cấu_hình>-dev/audit/*.csv` |
| Đọc CSV đã điền, tính metrics | `python -m src.score_run --run results/agent/<cấu_hình>-dev --split dev` → [src/score_run.py](../src/score_run.py) |
| Metrics tự động (CER, Hit@k lượt tìm đầu, tool use); tính lại cho run cũ: `python -m src.eval_agent --run ... --split dev` | [src/eval_agent.py](../src/eval_agent.py) |
| Chi phí USD (mức trần) | `python -m src.cost <run...>` → [src/cost.py](../src/cost.py) |
| Công thức metrics chung | [starter/agent_metrics.py](../starter/agent_metrics.py) |

Lưu ý: cột `effective_status` dùng để gán lại các câu "không đủ bằng chứng" nhưng vẫn có citation thành từ chối.

## Bước 5. Chốt cấu hình, chạy test một lần 🤖

Điều kiện: đã freeze, cấu hình đã chọn trên dev, tiêu chí chọn ghi trước trong [configs/selection.md](../configs/selection.md).

```bash
python -m src.run_agent --config configs/baseline.json --split test --final --out results/agent/baseline-test
python -m src.run_agent --config configs/final.json    --split test --final --out results/agent/final-test
```

Cờ `--final` và `ensure_split_allowed` ([src/eval_retrieval.py](../src/eval_retrieval.py)) chặn test nếu benchmark chưa freeze hoặc bị sửa sau freeze. Nếu đã xem test để chỉnh, phải tạo test mới và ghi rõ.

## Bước 6. Chấm nhãn test 👤

Giống bước 4, với `results/agent/<cấu_hình>-test/audit/*.csv`, rồi `python -m src.score_run --run ... --split test`.

## Bước 7. Báo cáo 👤 (🤖 hỗ trợ điền số)

| Việc | File |
|---|---|
| Mẫu báo cáo | [REPORT_TEMPLATE.md](../REPORT_TEMPLATE.md) |
| Báo cáo | [report/individual/2A202604002_BuiThaiSy.md](../report/individual/2A202604002_BuiThaiSy.md) |
| Bảng dev đầy đủ | `results/dev-summary.md` |
| Chi phí | `python -m src.cost <run...>` quy token ra USD (mức trần) theo giá DeepSeek Flash |

## Bước 8. Nộp bài

Theo [SUBMISSION.md](../SUBMISSION.md): repo cá nhân (tên theo lớp, MSSV), người chấm có quyền xem, không nộp `.env`, API key hay token. Chấm điểm theo [RUBRIC.md](../RUBRIC.md); tiến độ gợi ý ở [CHECKPOINTS.md](../CHECKPOINTS.md).

## Bonus (tùy chọn, +15 điểm)

Tài liệu từ 100 trang có bảng, ảnh, biểu đồ; cần đạt ít nhất 90% test. Yêu cầu ở [ADVANCED.md](../ADVANCED.md). Đã chọn HELM (arXiv 2211.09110v2, 162 trang); code, benchmark, kết quả và cách chạy ở [bonus/README.md](../bonus/README.md). Hiện **chưa đạt** ngưỡng (xem "Trạng thái hiện tại").

---

## Kiểm thử code

```bash
python -m unittest discover -s tests -v
```

Test mock chỉ kiểm tra code, không thay cho benchmark agent thật. Các file test nằm trong [tests/](../tests/), mỗi file ứng với một module `src/` cùng tên.

## Trạng thái hiện tại (cập nhật 2026-11-16)

Cách dựng lại môi trường và cảnh báo về volume Docker của Day 6: [README.md](../README.md) mục "Tái tạo kho vector Day 6".

### Phần cơ bản: đã xong

- Dữ liệu nguồn, `infra/`, đọc kho vector Day 6 (`chunks_a/b/c` 501/505/505 chunk). Day 7 không tự ingest.
- Benchmark đã xác nhận u01–u04 và freeze (`benchmark/freeze.json`, SHA-256 `fb253f0a…a592e8`).
- Retrieval trên dev: 6 phương pháp (bước 2), gồm rerank.
- Agent trên dev: baseline, improve-a/b/c đã chạy và **đã chấm nhãn** (bảng ở [results/dev-summary.md](../results/dev-summary.md)); improve-b là `final.json`.
- Rerank: improve-d (hybrid-rerank) và improve-e (dense-rerank) đã chạy trên dev, CER 15/15 như improve-b, chậm hơn 4–5 lần. Nhãn (tác giả đã duyệt): điểm câu trả lời 1,73 do từ chối nhầm q08, q13, thấp hơn improve-b 2,00, nên improve-b vẫn chốt.
- Test (`--final`) cho baseline và improve-b, **đã chấm nhãn**. Test đã chạy hai lần với cùng cấu hình: lần 1 ở `results/prev-test-old-freeze/` (freeze cũ), lần 2 sau khi bỏ trường `draft_by` và freeze lại; số liệu dưới đây là lần 2, giải thích ở `configs/selection.md`:

| Cấu hình | CER | Câu trả lời (TB) | Citation hợp lệ | Từ chối đúng | Từ chối nhầm |
|---|---|---|---|---|---|
| baseline | 5/5 | 2,00 | 9/14 | 2/2 | 0/5 |
| improve-b (final) | 5/5 | 2,00 | 9/9 | 2/2 | 0/5 |

  Test đã dùng nên improve-d/e chỉ được so trên dev; nếu một trong hai thành cấu hình chốt thì phải tạo test mới.
- Giao diện demo có 4 tab: Trace, Live, So sánh & rerank, Bản đồ chunk (`streamlit run demo/app.py`).
- Báo cáo đã điền từ `results/` và được tác giả đọc lại.

### Bonus (HELM)

- Bộ test thứ ba M01–M33 đã đối chiếu với PDF (tác giả đã xác nhận), gộp vào benchmark, freeze, chạy một lần.
- **improve-f đạt 31/33 = 93,94%**, vượt ngưỡng 90%; baseline 23/33. Nhãn đã duyệt. Hai bộ test cũ (T, N) nay là `retired`.
- Cấu hình chọn theo tiêu chí ghi trước trên dev + retired (87 câu): improve-e và improve-f cùng 85/87, improve-f ít token hơn. Chi tiết ở [bonus/README.md](../bonus/README.md) và `bonus/configs/selection.md`.

### Nộp bài

Toàn bộ code, cấu hình, benchmark, trace, nhãn và báo cáo đã commit và merge vào `main` (repo public). `.env` được git-ignore; đã quét toàn bộ lịch sử git, không có khóa API.

## Danh sách việc (đã xong)

- [x] Xác nhận u01–u04 và điền [benchmark/README.md](../benchmark/README.md).
- [x] `python -m src.benchmark freeze`.
- [x] Chấm nhãn audit dev cho baseline, improve-a/b/c/d/e.
- [x] Chấm nhãn audit test (`baseline-test`, `final-test`) và chạy `score_run`.
- [x] Báo cáo [report/individual/2A202604002_BuiThaiSy.md](../report/individual/2A202604002_BuiThaiSy.md).
- [x] (Bonus) Đối chiếu M01–M33 với PDF, chạy test một lần, chấm nhãn `pass_fail`.
- [x] Commit, push, repo public cho người chấm xem.
