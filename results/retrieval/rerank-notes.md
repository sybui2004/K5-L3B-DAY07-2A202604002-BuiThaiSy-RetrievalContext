# Rerank bằng cross-encoder — tiêu chí và cách hoạt động

## Rerank theo tiêu chí gì

Tiêu chí duy nhất: **mức độ liên quan giữa câu hỏi và đoạn văn**, do model `BAAI/bge-reranker-v2-m3` ước lượng.
Mỗi cặp (câu hỏi, đoạn) nhận một điểm số thực; cao hơn nghĩa là đoạn đó nhiều khả năng trả lời được câu hỏi hơn.
Không dùng thông tin nào khác: không dùng điểm cũ của dense/BM25, không dùng số trang, loại luật hay năm.
Điểm cũ chỉ dùng để quyết định 20 đoạn nào vào danh sách ứng viên.

## Quy trình (`RerankRetriever` trong `src/retrievers.py`)

1. Retriever gốc (dense hoặc hybrid) trả về **20 ứng viên** (`pool=20`).
2. Cross-encoder chấm từng cặp (câu hỏi, đoạn ứng viên): 20 lần chấm cho mỗi truy vấn.
3. Sắp xếp giảm dần theo điểm mới, giữ `top_k` đoạn đầu (3 khi so sánh retrieval).
4. Nếu đoạn đúng không nằm trong 20 ứng viên thì rerank không cứu được: nó chỉ **xếp lại**, không **tìm thêm**.

## Cross-encoder khác dense (bi-encoder) ở đâu

| | Dense (bge-m3) | Cross-encoder (bge-reranker-v2-m3) |
|---|---|---|
| Cách đọc | Câu hỏi và đoạn được mã hóa **riêng**, mỗi bên thành một vector | Câu hỏi và đoạn được **ghép chung** thành một chuỗi và đưa vào model cùng lúc |
| Điểm số | Độ giống nhau (cosine) của hai vector | Đầu ra của model, ước lượng "đoạn này có trả lời câu hỏi không" |
| Chi phí | Rẻ: vector của đoạn tính sẵn một lần, lúc truy vấn chỉ mã hóa câu hỏi | Đắt: phải chạy model cho từng cặp, không tính sẵn được |
| Chất lượng | Nhanh nhưng thô: một vector phải nén cả ý nghĩa của đoạn | Chính xác hơn: từng từ trong câu hỏi "nhìn" được từng từ trong đoạn (attention chéo) |

Vì vậy cách dùng chuẩn là hai tầng: tầng 1 (dense/hybrid) lọc nhanh từ hàng trăm đoạn xuống 20, tầng 2 (cross-encoder) chấm kỹ 20 đoạn đó.

Cách huấn luyện: model được tinh chỉnh trên rất nhiều cặp (câu hỏi, đoạn) có nhãn đúng/sai, để dự đoán nhãn từ chuỗi ghép chung.
Nó dùng nền XLM-RoBERTa nên hỗ trợ đa ngôn ngữ, trong đó có tiếng Việt, nhưng **không được tinh chỉnh riêng cho văn bản luật**.

## Giới hạn cần nhớ

- Cắt ở 512 token mỗi cặp. Chunk dài hơn bị cắt phần cuối khi chấm.
- Điểm của cross-encoder không có thang cố định, chỉ so sánh được trong cùng một truy vấn.
- Chạy trên CPU nên chậm; không tất định hoàn toàn về thời gian nhưng điểm số thì ổn định.

## Nhật ký chạy



Chạy 2026-11-16, `python -m src.eval_retrieval --method <m> --split dev`, query gốc, top-3, chunks_b, 15 câu có đáp án.

| Phương pháp | Hit@1 | Evidence Hit@3 | Giây | Ghi chú |
|---|---|---|---|---|
| dense (mốc) | 13/15 | 14/15 | 37.58 | trượt q14 |
| hybrid (mốc) | 14/15 | 14/15 | 37.74 | trượt q14 |
| dense-rerank | 15/15 | 15/15 | 320.85 | |
| hybrid-rerank | 15/15 | 15/15 | 1230.09 | gồm thời gian tải model lần đầu |

- Câu q14 (câu nhiều ý, mọi phương pháp trước đều trượt top-3) giờ có chunk đúng ở hạng 1 và hạng 2 (Điều 125 luật 2012, Điều 124 luật 2019).
- Chi phí: chậm hơn dense/hybrid khoảng 9 lần (dense-rerank 321 giây so với 38 giây cho 15 câu, khoảng 21 giây mỗi câu trên CPU).
- Giới hạn: dev chỉ 15 câu và hai phương pháp rerank cùng đạt trần 15/15, nên **dev không phân biệt được** dense-rerank với hybrid-rerank. Muốn chọn giữa hai cái cần số liệu từ agent (Context Evidence Rate, token, thời gian), hoặc đánh giá trên tập lớn hơn.
- Mới đánh giá retrieval, chưa chạy agent với rerank.
