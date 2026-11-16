# Thiết kế — Day 7 Agentic RAG (cơ bản + bonus)

Ngày: 2026-11-15 · Trạng thái: chờ duyệt

## 1. Mục đích

Hoàn thành lab Day 7 và **cả thử thách nâng cao (+15 điểm)**: xây agent dùng model thật để tìm bằng chứng trong kho Day 6, trả lời có citation, từ chối khi thiếu bằng chứng; so sánh ≥3 phương pháp retrieval trên dev, chốt cấu hình, đánh giá test. Phần bonus lặp lại pipeline trên một tài liệu ≥100 trang có bảng/ảnh/biểu đồ và phải đạt ≥90% test. Điểm dựa trên bằng chứng kiểm chứng được và báo cáo trung thực, không dựa vào số cao.

## 2. Mục tiêu / Không làm / Thất bại dù chạy được

**Mục tiêu**
- Phần cơ bản trên corpus Day 6 (Bộ luật Lao động 2012 và 2019), nối thẳng vào Postgres + pgvector của Day 6.
- Một khung agent chung, retriever cắm vào được, dùng lại cho bonus.
- Bonus: index toàn bộ tài liệu mới, benchmark ≥30 câu test (≥24 có đáp án, ≥6 thiếu bằng chứng), chấm đạt/không đạt từng câu.

**Không làm**
- Không thay corpus phần cơ bản (rubric chấm việc kết nối Day 6).
- Không dùng LLM judge thay việc đọc đối chiếu nguồn.
- Không fine-tune model.

**Thất bại dù chạy được**
- Đưa gold (đáp án, trang, evidence) vào agent, query hoặc filter.
- Xem test rồi chỉnh cấu hình mà vẫn báo là đánh giá độc lập.
- Fallback âm thầm sang kết quả giả khi API/DB lỗi.
- Tin mô tả ảnh/biểu đồ do model sinh mà không đối chiếu bản gốc.
- Commit `.env` hoặc API key.

## 3. Ràng buộc

- Windows 11, Python 3.11. Docker Desktop phải bật; Postgres Day 6 ở `127.0.0.1:15433` (cổng 55433 bị Windows giữ, đã đổi trong Day 6).
- Embedding: `bge-m3` qua Ollama, 1024 chiều, giống Day 6 (query phải cùng model với index).
- Agent LLM: `deepseek-v4-flash` qua API DeepSeek (OpenAI-compatible, đã kiểm tra key và gọi được; nhận được cả ảnh). Cấu hình trong `.env`, mẫu ở `.env.example`.
- Quy tắc repo của người dùng: không tự commit; tên nhánh tiếng Anh kebab-case có tiền tố.
- Dữ liệu tài liệu nâng cao phải có quyền sử dụng rõ ràng.

## 4. Các phương án đã cân nhắc

**Tổ chức corpus.** Chọn: hai corpus tách nhau, chung khung agent (phần cơ bản trước, bonus sau). Loại: một corpus mới thay Day 6 cho cả hai (mất điểm kết nối Day 6; luật chỉ có text nên cũng không đáp ứng bonus).

**Đọc nội dung trực quan (bonus).**
1. *Chọn:* PyMuPDF tách text/bảng; DeepSeek mô tả ảnh, biểu đồ, bảng phức tạp; lưu mô tả kèm trang và vùng crop vào pgvector, embed bằng bge-m3.
2. Multimodal embedding local (ColPali/CLIP): nặng GPU/RAM, cần store khác.
3. Như 1 nhưng trích bảng thành dữ liệu có cấu trúc: không làm ngay; chỉ thêm nếu dev cho thấy bảng là điểm yếu.

## 5. Thiết kế đã chốt (phần người dùng quyết định)

- Dùng DeepSeek V4 Flash làm model agent.
- Làm cả bonus.
- Đọc nội dung trực quan theo cách 1 ở trên.

## 6. Các lựa chọn Claude tự đưa ra (cần kiểm tra)

### 6.1 Phần cơ bản
- **Kho dữ liệu:** đọc bảng `chunks_b` (chunk theo Điều) của Day 6 làm kho chính; không ingest lại. Cần xem schema thật khi hiện thực. Embedding không tính lại.
- **Ba phương pháp retrieval** (cùng corpus, cùng câu hỏi, cùng nhãn):
  1. Dense: bge-m3 trên pgvector, cosine, có/không filter `version` (filter chỉ khi câu hỏi nêu năm, như Day 6).
  2. Lexical: BM25 trên cùng chunk; thử tách từ tiếng Việt đơn giản và so với tách theo khoảng trắng.
  3. Hybrid: dense + BM25 hợp nhất bằng RRF.
  Mỗi phương pháp xuất top-3 để so sánh Hit@1 và Evidence Hit@3.
- **Hai cấu hình cải thiện** (giả thuyết ghi trước khi chạy): (a) agent nhiều lượt + viết lại query; (b) tăng top-k/context budget có giữ đoạn lân cận. Có thể thêm rerank nếu còn thời gian.
- **Agent:** vòng lặp tool-calling với DeepSeek; tool `search(query)` (backend là phương pháp đang thử), dừng khi trả lời hoặc đạt giới hạn lượt; citation dạng `[chunk-id]`; thiếu bằng chứng thì từ chối. Lưu trace đầy đủ. Tái dùng và sửa `starter/agentic.py`.
- **Benchmark:** dùng lại 20 câu Day 6 (15 dev / 5 test, test Day 6 chưa chạy nên còn sạch) và thêm 2 câu thiếu bằng chứng cho dev, 2 cho test, gần chủ đề luật lao động nhưng không có trong hai bộ luật. Claude soạn nháp, **người dùng tự kiểm tra trong PDF** rằng không có đáp án rồi chốt split trước khi chạy.
- **Chọn cấu hình:** tiêu chí công bố trước: Context Evidence Rate trên dev → grounded answer → chi phí/thời gian. Chốt rồi mới chạy test.
- **Chấm thủ công:** Claude sinh bảng nhãn có cột điểm để trống; người dùng tự chấm (context 0/1/2, answer 0/1/2, citation, abstention).

### 6.2 Bonus
- **Tài liệu:** Claude đề xuất 2–3 ứng viên (≥100 trang, có bảng/ảnh/biểu đồ thông tin thật, giấy phép rõ, ưu tiên báo cáo CC BY như World Bank/OECD/WHO, PDF có lớp text); **người dùng chọn**. Ghi nguồn, phiên bản, số trang, quyền.
- **Index:** mỗi trang → text (PyMuPDF), bảng (`find_tables`), ảnh/biểu đồ (crop theo bbox). Mô tả bằng DeepSeek (ảnh) được lưu cùng `page`, `bbox`, đường dẫn ảnh crop, loại (`text|table|figure|chart`). Bảng mới `adv_chunks` trong cùng Postgres, embed bge-m3. Phần không xử lý được ghi log.
- **Agent bonus:** như phần cơ bản, thêm tool `view_region(page, bbox)` để gửi ảnh crop gốc cho model đọc lại số liệu thay vì tin mô tả (giảm lỗi biểu đồ/bảng). Citation phải xác định được trang và vùng.
- **Benchmark bonus:** dev ≥15 có đáp án + ≥3 thiếu bằng chứng; test ≥24 có đáp án + ≥6 thiếu bằng chứng, phủ bảng ≥6, ảnh ≥5, biểu đồ ≥5, multi-hop ≥4, text ≥4. Claude soạn nháp; người dùng đối chiếu bản gốc từng câu, chốt split trước khi chạy. Chấm đạt/không đạt từng câu test, báo `n/N` toàn bộ và theo nhóm; cần ≥90% (30 câu → 27).
- **Chi phí:** ước tính trước khi chạy index mô tả hình (số ảnh × giá), ghi chi phí thật.

## 7. Để người hiện thực quyết định

Schema thật của `chunks_b`; thư viện BM25 và cách tách từ; prompt và giới hạn lượt của agent; định dạng trace; cách đo thời gian/chi phí DeepSeek; độ phân giải ảnh crop; cấu trúc thư mục `src/`, `tests/`.

## 8. Thứ tự làm

1. Kết nối Day 6 (đọc `chunks_b`), dense retriever, kiểm tra Hit@3 dev khớp số Day 6 (14/15).
2. BM25, hybrid; agent DeepSeek; benchmark mở rộng; chạy dev, thử cải thiện, chốt, chạy test; báo cáo.
3. Chọn tài liệu bonus, index đa phương thức, benchmark bonus, chạy dev, chốt, chạy test.
