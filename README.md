# Day 7 — Agentic RAG

**Bài cá nhân · Python 3.11+ · tiếp nối Day 6**

Dùng embedding và vector store từ Day 6 để xây một agent biết tìm bằng chứng, trả lời có nguồn và nhận biết khi không đủ thông tin. Bạn tự chọn kiến trúc, số tool và cách tổ chức retrieval.

> **Tùy chọn:** [Gợi ý dùng AI để lập trình](AGENT_SETUP.md) giúp bạn làm lab; phần này không bắt buộc và không tính điểm.

## Bài cần làm

![Agent tìm tài liệu trong kho Day 6 và trả lời có nguồn](assets/retrieval-pipeline.svg)

1. Kết nối dữ liệu, embedding và vector store Day 6.
2. Xây agent dùng model thật và ít nhất một khả năng truy xuất dữ liệu. Agent có thể dùng nhiều tool và nhiều lượt gọi.
3. Thử **ít nhất 3 phương pháp retrieval khác nhau**, trong đó có dense retrieval dùng vector store Day 6. Tự chọn các phương pháp còn lại; xem [gợi ý](GUIDE.md#2-thử-các-phương-pháp-retrieval).
4. Thử nhiều cấu hình, benchmark, phân tích lỗi và chọn cấu hình tốt trên **dev**; sau đó đánh giá trên **test**.

Benchmark tối thiểu có **24 câu**: dev gồm 15 câu có đáp án và 2 câu thiếu bằng chứng; test gồm 5 câu có đáp án và 2 câu thiếu bằng chứng. Xem [benchmark](BENCHMARK.md) và [rubric](RUBRIC.md).

## Thử thách nâng cao · +15 điểm

Index một tài liệu thực tế từ **100 trang** có bảng, ảnh và biểu đồ; xây agent truy xuất và trả lời các câu hỏi về nội dung đó. Hoàn thành [thử thách nâng cao](ADVANCED.md) và đạt **ít nhất 90% benchmark test** để nhận 15 điểm bonus. Phần cơ bản tối đa 85 điểm; toàn bài tối đa 100 điểm.

## Bắt đầu

1. Đọc [hướng dẫn](GUIDE.md), [rubric](RUBRIC.md) và [quy tắc](RULES.md).
2. Tạo repo cá nhân theo [cách nộp bài](SUBMISSION.md), chuẩn bị đầu ra Day 6 và model hỗ trợ tool calling.
3. Dùng hoặc thay thế [starter](starter/README.md); bạn cần kết nối model và vector store thật.
4. Chạy `python -m unittest discover -s tests -v`. Test mock chỉ kiểm tra code, không phải benchmark agent thật.

![Các bước thử nghiệm trên dev và đánh giá trên test](assets/experiment-loop.svg)

Nộp code, cách chạy, cấu hình, benchmark, trace và [báo cáo](report/individual/2A202604002_BuiThaiSy.md). Thời gian ở [checkpoints](CHECKPOINTS.md) là gợi ý, có thể điều chỉnh theo lớp và phạm vi thử nghiệm.

## Tái tạo kho vector Day 6

Day 7 chỉ **đọc** các bảng `chunks_a/b/c` của Day 6 (xem [src/store_day6.py](src/store_day6.py)); repo này không tự ingest. Nguồn dữ liệu nằm trong [data/raw/](data/raw/), nguồn và quyền sử dụng ở [data/manifest.csv](data/manifest.csv) (SHA-256 khớp bản dùng ở Day 6).

1. Dựng PostgreSQL + pgvector bằng file đã sao chép từ Day 6:
   ```bash
   docker compose -f infra/docker-compose.yml -p day6_student_starter up -d --wait
   ```
   Cổng host là `15433` (Windows trên máy này giữ `55433`). Mật khẩu `day6_local_only` chỉ dùng local.
2. Nếu volume Docker của Day 6 còn nguyên (cùng project name `day6_student_starter`, volume `day6_student_starter_pg_data`), dữ liệu đã có sẵn, bỏ qua bước 3. Không chạy `docker compose down -v` hay `docker volume rm` với volume này: dữ liệu (gồm cả `helm_chunks` của phần bonus) sẽ mất và phải ingest lại.
3. Nếu database trống, nạp lại bằng pipeline Day 6 (repo Day 6, thư mục `starter/`), dùng đúng PDF trong `data/raw/` ở đây (copy sang `data/raw/` của Day 6 nếu cần):
   ```bash
   python -m src.run ingest        # tạo chunks_a, chunks_b, chunks_c với bge-m3 (1024 chiều)
   ```
4. Embedding: Ollama `bge-m3`, chạy ở `http://localhost:11434` (`ollama pull bge-m3`).
5. Copy `.env.example` thành `.env`, điền khóa DeepSeek, kiểm tra `DATABASE_URL` trỏ `127.0.0.1:15433`.
6. Kiểm chứng: `python -m src.eval_retrieval --method dense --split dev --out results/check-dense` phải cho Hit@1 13/15 và Hit@3 14/15; lệch thì index không khớp Day 6.

## Rerank (cross-encoder)

Hai phương pháp `dense-rerank` và `hybrid-rerank` lấy 20 ứng viên từ dense hoặc hybrid, chấm lại từng cặp (câu hỏi, chunk) bằng `BAAI/bge-reranker-v2-m3`, rồi giữ top-k (`RerankRetriever` trong [src/retrievers.py](src/retrievers.py)).

- Cần gói `sentence-transformers` (đã có trong [requirements.txt](requirements.txt)). Lần chạy đầu tải model (~2GB) vào cache HuggingFace; chạy trên CPU khoảng 21 giây/câu.
- Retrieval: `python -m src.eval_retrieval --method hybrid-rerank --split dev --out results/retrieval/hybrid-rerank-dev`
- Agent: đặt `"method": "hybrid-rerank"` (hoặc `"dense-rerank"`) trong file config, ví dụ [configs/improve-d.json](configs/improve-d.json), [configs/improve-e.json](configs/improve-e.json), rồi chạy `python -m src.run_agent --config configs/improve-d.json --split dev --out results/agent/<thư_mục_mới>`.

Kết quả so sánh: [results/retrieval/compare-dev.md](results/retrieval/compare-dev.md), [results/dev-summary.md](results/dev-summary.md).

## Tính lại metric và chi phí từ kết quả đã lưu (không gọi API)

- Hit@1/Hit@3 của lượt tìm đầu tiên và Context Evidence Rate của một run agent (cần Postgres để đọc nội dung chunk): `python -m src.eval_agent --run results/agent/improve-b-dev --split dev` (ghi vào `summary.json`, trường `first_search_hits`).
- Điểm từ nhãn tay: `python -m src.score_run --run results/agent/improve-b-dev --split dev`.
- Chi phí bằng USD (mức trần, giá DeepSeek Flash): `python -m src.cost results/agent/*-dev results/agent/*-test`.

## Giao diện demo

Chạy từ thư mục gốc repo: `streamlit run demo/app.py`. Thanh bên chọn bộ dữ liệu (Cơ bản hoặc Bonus HELM).

- **Trace**: xem lại các lần chạy đã lưu (`results/agent/*`, `bonus/results/*`): summary, bảng câu hỏi, từng lượt search, context đã ghép, câu trả lời kèm citation, đáp án và evidence chuẩn, nhãn audit, ảnh crop của Bonus. Không cần DB hay API.
- **Live**: gọi agent thật trên câu dev hoặc câu tự nhập (không có split test), chọn cấu hình và ghi đè phương pháp retrieval, hoặc so sánh các phương pháp mà không gọi LLM. Cần Docker Postgres đang chạy, Ollama có `bge-m3` và `.env` đã điền; thiếu thì chỉ tab Live báo lỗi.
