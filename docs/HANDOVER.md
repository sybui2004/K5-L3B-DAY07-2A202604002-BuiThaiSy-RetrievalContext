# Bàn giao Day 7 (cập nhật 2026-11-16)

Dùng khi mở workspace **chỉ chứa** `K5-L3B-DAY07-2A202604002-BuiThaiSy-RetrievalContext` (không còn `K5-L3-Day07-Retrieval-Context-Engineering`). Repo này là bản nộp: remote `origin` trỏ `sybui2004/K5-L3B-DAY07-2A202604002-BuiThaiSy-RetrievalContext`, nhánh hiện tại `main`. **Chưa có commit nào cho phần Day 7** (xem mục 6).

## 0. Việc bạn phải tự làm (không thể giao cho AI)

Cập nhật lần 2 (2026-11-16): AI làm trước các việc dưới đây, **tác giả đã đọc lại và duyệt** (đuôi nháp trong cột `reason` đã xóa).

- [x] **Duyệt nhãn improve-d/e trên dev** (`results/agent/improve-d-dev/audit/`, `improve-e-dev/audit/`). Kết quả: cả hai đạt điểm câu trả lời 1,73 (q08, q13 từ chối nhầm dù context có evidence) so với improve-b 2,00, nên improve-b vẫn là cấu hình chốt. Đã ghi ở `results/dev-summary.md` và `configs/selection.md`.
- [x] **Duyệt việc đối chiếu M01–M33 với PDF.** AI đã xem từng trang (ảnh render cho M08–M19): đáp án khớp. Chỉ sửa ghi chú vị trí của M11 và ghi chú kiểm tra của M28 ("Falcon" có trong họ tác giả "Saad-Falcon", trang 108; câu vẫn không trả lời được). Test3 **đã gộp, freeze và chạy một lần**, nên nếu bạn phát hiện câu sai thì chỉ được sửa nhãn và ghi rõ, không sửa câu hỏi rồi chạy lại.
- [x] **Duyệt nhãn `pass_fail` bonus**: `bonus/results/final-test3/` (31/33), `baseline-test3/` (23/33), và các lượt chọn cấu hình `v5-improve-f-*`, `v5-improve-e-*`. Cần xem kỹ M11, M17 (trượt) và M12 (đạt ở mức biên; tính trượt thì còn 30/33, vẫn đạt).
- [x] **Đọc lại báo cáo** `report/individual/2A202604002_BuiThaiSy.md` (đã cập nhật phần bonus là đạt, và phần chọn improve-b theo nhãn d/e), đối chiếu số với `results/` và tự viết phần nhận xét.
- [ ] Commit, push, cấp quyền xem cho người chấm.

## 1. Môi trường chạy (đã dựng lại trong repo này)

| Thành phần | Trạng thái | Ghi chú |
|---|---|---|
| Python venv | `.venv/` trong repo, Python 3.11, 84 gói từ `requirements.txt` | Tạo lại: `python -m venv .venv` rồi `.venv\Scripts\python.exe -m pip install -r requirements.txt`. Torch là bản CPU (máy không dùng được GPU cho torch). |
| `.env` | Có sẵn trong repo, git-ignore | Có khóa DeepSeek; **không commit**. Mẫu ở `.env.example`. |
| PostgreSQL + pgvector | Container `day6_student_starter-postgres-1`, cổng `127.0.0.1:15433`, volume Docker `day6_student_starter_pg_data` | Chứa `chunks_a/b/c` (501/505/505 chunk) và `helm_chunks` (863 chunk, cho bonus). |
| Ollama | `bge-m3` (embedding) và `qwen2.5vl:7b` (đọc hình, chỉ bonus) | Model nằm ở thư mục của Ollama, không phụ thuộc repo. |
| Model rerank | `BAAI/bge-reranker-v2-m3` trong cache HuggingFace của user (`~/.cache/huggingface`) | Đã tải sẵn (~2GB); chạy CPU. |

Dùng interpreter của repo này cho mọi lệnh (`.venv\Scripts\python.exe ...`). Đã kiểm tra bằng venv mới: `unittest discover -s tests` 134 test đạt; `bonus/tests` đạt; `python -m src.eval_retrieval --method dense --split dev` cho Hit@1 13/15, Hit@3 14/15; `python -m src.benchmark validate` và `python -m bonus.src.validate` đều `0 problems`.

### Cảnh báo về database (quan trọng)

Container và volume trên được **tạo từ thư mục Day 6** (`D:\Vin\temp\K5-L3-Day06-DataIngestionEngineering\starter`), không phải từ repo này. Điều đó có nghĩa:

- Dữ liệu vẫn còn khi bạn đóng workspace cũ, miễn là **không xóa volume** `day6_student_starter_pg_data`. Không chạy `docker compose down -v` và không `docker volume rm`.
- Nếu khởi động lại bằng `infra/docker-compose.yml` của repo này, phải dùng đúng tên project để gắn lại volume cũ: `docker compose -f infra/docker-compose.yml -p day6_student_starter up -d --wait`.
- Nếu mất volume, phần cơ bản phải nạp lại bằng **code ingest Day 6**, hiện chỉ có ở thư mục Day 6 ngoài repo này (xem README mục "Tái tạo kho vector Day 6"). Riêng bonus có thể nạp lại bằng `python -m bonus.src.ingest --vlm qwen2.5vl:7b --table-limit 700 ` (~35 phút), rồi chạy lại ingest cho trang 43, 44, 157 với chunk theo dòng (mục 4).

## 2. Cấu trúc và nơi tìm mọi thứ

| Việc | Đường dẫn |
|---|---|
| Luồng làm việc từng bước | `docs/WORKFLOW.md` (phần "Trạng thái hiện tại" đã cũ, xem mục 5) |
| Code agent, retriever, đánh giá | `src/` (có `RerankRetriever` trong `src/retrievers.py`) |
| Cấu hình agent cơ bản và tiêu chí chọn | `configs/*.json`, `configs/selection.md` |
| Benchmark cơ bản (dev 15+2, test 5+2, đã freeze) | `benchmark/questions.json`, `benchmark/freeze.json` |
| Kết quả agent cơ bản | `results/agent/<cấu_hình>-dev|test/` (trace, summary, `audit/*.csv`) |
| Kết quả retrieval | `results/retrieval/*-dev/`, bảng `results/retrieval/compare-dev.md`, giải thích rerank `results/retrieval/rerank-notes.md` |
| Bảng tổng hợp dev | `results/dev-summary.md` |
| Giao diện demo | `demo/` (chạy `.venv\Scripts\streamlit.exe run demo/app.py`) |
| Bonus (HELM, 162 trang) | `bonus/` (README riêng, benchmark `bonus/benchmark/`, kết quả `bonus/results/`) |
| Báo cáo | `report/individual/2A202604002_BuiThaiSy.md` (tác giả đã đọc lại) |

## 3. Phần cơ bản: đã xong và còn thiếu

**Retrieval trên dev** (query gốc, top-3, 15 câu có đáp án):

| Phương pháp | Hit@1 | Hit@3 |
|---|---|---|
| dense | 13/15 | 14/15 |
| bm25 | 11/15 | 13/15 |
| bm25-bigram | 13/15 | 13/15 |
| hybrid (RRF) | 14/15 | 14/15 |
| dense-rerank | 15/15 | 15/15 |
| hybrid-rerank | 15/15 | 15/15 |

Rerank = lấy 20 ứng viên, chấm lại từng cặp (câu hỏi, chunk) bằng cross-encoder `bge-reranker-v2-m3`, giữ top-k. Tiêu chí duy nhất là độ liên quan câu hỏi–chunk do model ước lượng. Chậm hơn khoảng 9 lần (≈21 giây/câu trên CPU). Dev chỉ 15 câu nên hai bản rerank cùng đạt trần, chưa phân biệt được.

**Agent trên dev** (17 câu = 15 câu `q` có đáp án + 2 câu `u` thiếu bằng chứng; CER = Context Evidence Rate):

| Cấu hình | Retrieval | CER | Trả lời / từ chối | Token vào+ra | Giây |
|---|---|---|---|---|---|
| baseline | dense top-3, budget 3000 | 14/15 | 15 / 2 | 44.741 | 94,9 |
| improve-a | 4 lượt tìm, viết lại truy vấn | 14/15 | 17 / 0 | 76.304 | 139,2 |
| improve-b (**đang là `final.json`**) | dense top-5, budget 6000, Điều kề | 15/15 | 16 / 1 | 70.523 | 97,6 |
| improve-c | hybrid | 14/15 | 15 / 2 | 46.874 | 99,7 |
| improve-d | hybrid-rerank top-5 | 15/15 | 13 / 4 | 59.712 | 376,6 |
| improve-e | dense-rerank top-5 | 15/15 | 14 / 3 | 65.366 | 471,3 |

d và e hòa CER với b, dùng ít token hơn nhưng chậm hơn 4–5 lần và từ chối thêm q08, q13 (hai câu có đáp án). Chưa biết đó là từ chối nhầm hay vẫn trả lời đủ ý. **Cần bạn chấm nhãn** `results/agent/improve-d-dev/audit/` và `improve-e-dev/audit/` (bảng đang trống). Tiêu chí đã ghi trước trong `configs/selection.md`: CER → điểm câu trả lời → token/thời gian. b chỉ bị thay nếu d/e hơn ở điểm câu trả lời.

**Test cơ bản đã chạy một lần** (baseline và improve-b, `--final`), nhãn answer/citation/abstention và context 0/1/2 đã điền cho cả hai. Vì test đã dùng, `improve-d/e` chỉ được so trên dev; nếu một trong hai thành cấu hình chốt thì phải tạo test mới và ghi rõ.

**Còn thiếu cho phần cơ bản** (theo `RUBRIC.md`, `SUBMISSION.md`, `BENCHMARK.md`):
1. ~~Điền báo cáo~~ Đã điền và tác giả đã đọc lại.
2. Chấm nhãn improve-d/e (nếu muốn đưa vào kết luận).
3. ~~Chi phí chưa quy ra tiền~~: đã thêm `src/cost.py` và bảng USD (mức trần) trong báo cáo.
4. ~~Cập nhật `docs/WORKFLOW.md` và `README.md` (mục 5).~~ Đã làm 2026-11-16.
5. Commit, push, cấp quyền xem cho người chấm.

## 3b. Báo cáo đã soạn (2026-11-16)

File: `report/individual/2A202604002_BuiThaiSy.md`. Nguồn số liệu: `results/**/agent_metrics.json`, `summary.json`, `audit/*.csv`, `results/retrieval/compare-dev.md`, `results/dev-summary.md`, `configs/selection.md`, `data/manifest.csv`, `benchmark/README.md`, `bonus/README.md`, `bonus/results/final-test2/audit/pass_fail.csv`.

Cần bạn kiểm tra/biết:
- Hit@1/Hit@3 của các cấu hình agent tính lại từ trace (lượt tìm đầu, truy vấn do agent viết), nên khác bảng retrieval dùng câu hỏi gốc. Hit trên test cũng tính từ trace, không chạy lại retrieval.
- Test không phân biệt được baseline và improve-b: cùng CER 5/5, grounded 2,00, abstention 2/2; khác ở citation hợp lệ (9/9 so với 9/14). Báo cáo ghi rõ điều này.
- Hai lỗi dev nêu trong báo cáo: q14 trượt retrieval (baseline từ chối nhầm; improve-b cứu được, chunk ở hạng 4) và lỗi vòng lặp "hết lượt tìm thì bỏ cuộc" (số từ chối 5/4/3/4 xuống 2/1/1/2).
- Baseline test: trace gốc ghi `answered` ở u03/u04 dù nội dung là từ chối; báo cáo coi là từ chối theo quy ước chấm trong `results/dev-summary.md`. Hãy xác nhận cách hiểu này.
- Chi phí đã quy ra USD (mức trần, `src/cost.py`). improve-d/e chưa chấm nhãn nên không dùng làm kết luận.
- Phần bonus (cập nhật lần 2) ghi "đạt": test thứ ba M01–M33, improve-f 31/33 = 93,94%; hai bộ test cũ (T 25/33, N 27/33) được nêu như lịch sử, không dùng làm điểm.
- Tôi chưa chạy lại bất kỳ lệnh nào để kiểm chứng số liệu trong báo cáo.

Còn lại sau báo cáo: commit/push (kiểm tra không có `.env`/khóa; `results/` không bị git-ignore), cấp quyền xem repo cho người chấm.

## 4. Bonus (HELM): trạng thái

**Đạt ngưỡng trên bộ test thứ ba M01–M33: improve-f 31/33 = 93,94%** (nhãn đã duyệt). Baseline cùng bộ 23/33.

Đã làm (2026-11-16, lần 2), theo thứ tự:
1. Đối chiếu M01–M33 với PDF; sửa ghi chú M11, M28 trong `bonus/benchmark/build_test3.py`; sinh lại `test3_draft.json`; `validate` 0 problems. Sửa luôn `bonus/src/validate.py` để nhận đường dẫn file câu hỏi từ dòng lệnh (trước đây tham số bị bỏ qua).
2. `python -m bonus.benchmark.build_questions --with-test3` (phải chạy dạng module): 120 câu, N01–N33 sang `retired`, nội dung câu cũ không đổi. Freeze SHA `09012e2d…bddba000`.
3. Ghi tiêu chí chọn vào `bonus/configs/selection.md` **trước** khi có kết quả improve-e trên index mới: dev đã bão hòa nên tập chọn là dev + retired (87 câu). Chạy improve-e trên index v5 (`v5-improve-e-dev`, `v5-improve-e-retired`). Kết quả improve-e 85/87 (663.797 token), improve-f 85/87 (644.492 token), nên chọn improve-f; `final.json` = improve-f.
4. Chạy test một lần: `bonus/results/final-test3` (improve-f) và `bonus/results/baseline-test3`. Trượt: M11, M17 (model từ chối dù phần đọc hình đã có đáp án).

Bản sao `questions.json` và `freeze.json` trước khi gộp nằm ở thư mục scratchpad của phiên (tạm thời); git chưa theo dõi các file này.

## 5. File tài liệu cần cập nhật

- ~~`docs/WORKFLOW.md`~~: đã cập nhật 2026-11-16 (rerank, improve-d/e, nhãn test, 4 tab demo, trạng thái bonus).
- ~~`README.md`~~: đã thêm mục "Rerank (cross-encoder)" và sửa link báo cáo sang `report/individual/2A202604002_BuiThaiSy.md`.
- ~~`bonus/README.md`~~: đã thêm vòng 5 và bộ test thứ ba. Đã cập nhật kết quả test3 ở đầu file.
- ~~`results/dev-summary.md`~~: đã thêm nhãn improve-d/e.

## 6. Git và quy tắc cần nhớ

- Nhánh hiện tại là `main` (theo quy tắc nên tạo nhánh tính năng, ví dụ `feature/agentic-rag-basic`, trước khi commit); gần như toàn bộ Day 7 đang **untracked** (`src/`, `configs/`, `benchmark/`, `bonus/`, `demo/`, `tests/`, `results/`...). `results/` **không** bị git-ignore, nên sẽ được commit cùng toàn bộ trace và `audit/`; kiểm tra trước khi push.
- Theo `CLAUDE.md` của bạn: không tự commit; nếu được yêu cầu commit thì không thêm `Co-Authored-By`; PR không thêm dòng "Generated with Claude Code". Tên nhánh tiếng Anh, kebab-case, có tiền tố loại.
- `RULES.md`: chọn và chỉnh trên dev; test chỉ chạy một lần sau khi chốt; test đã dùng để chỉnh thì phải làm test mới.
- Không commit `.env`, khóa API, token.

## 7. Lệnh hay dùng (từ thư mục gốc repo)

```bash
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe -m src.eval_retrieval --method hybrid-rerank --split dev --out results/retrieval/hybrid-rerank-dev
.venv\Scripts\python.exe -m src.run_agent --config configs/improve-d.json --split dev --out results/agent/improve-d-dev   # thư mục đích phải chưa tồn tại
.venv\Scripts\python.exe -m src.score_run --run results/agent/improve-b-dev --split dev                                   # sau khi điền audit/*.csv
.venv\Scripts\streamlit.exe run demo/app.py
```

Lưu ý: chạy rerank trên toàn bộ câu rất chậm (CPU); lần đầu mất thêm thời gian nạp model. Lệnh `run_agent` và `run_bonus` ghi đè bị chặn nếu thư mục đích đã có `traces.json`, nên mỗi lần chạy dùng thư mục mới.
