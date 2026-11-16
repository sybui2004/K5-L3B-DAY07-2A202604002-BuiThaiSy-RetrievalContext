# So sánh retrieval — dev (query gốc, top-3, chunks_b)

| Phương pháp | Hit@1 | Evidence Hit@3 | Giây (15 câu) | Câu trượt top-3 |
|---|---|---|---|---|
| dense | 13/15 | 14/15 | 37.58 | q14 |
| bm25 | 11/15 | 13/15 | 0.03 | q08, q14 |
| bm25-bigram | 13/15 | 13/15 | 0.06 | q08, q14 |
| hybrid | 14/15 | 14/15 | 37.74 | q14 |
| dense-rerank | 15/15 | 15/15 | 320.85 | không |
| hybrid-rerank | 15/15 | 15/15 | 1230.09 | không |

Hai dòng rerank: 20 ứng viên từ dense (hoặc hybrid), chấm lại bằng cross-encoder `bge-reranker-v2-m3` (CPU), giữ top-3. Cột giây của `hybrid-rerank` gồm cả lần tải model về máy (~2GB); `dense-rerank` chạy sau, model đã có trong cache.
