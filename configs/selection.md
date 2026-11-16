# Giả thuyết và tiêu chí chọn cấu hình (chốt TRƯỚC khi chạy agent trên dev)

Ngày: 2026-11-15. Chọn chỉ bằng **dev**. Chốt `configs/final.json` rồi mới chạy test.

| Cấu hình | Thay đổi so với baseline | Giả thuyết |
|---|---|---|
| baseline | dense (bge-m3 / chunks_b), top-3, tối đa 1 lượt tìm, budget 3000 ký tự | Mốc so sánh. |
| improve-a | tối đa 4 lượt tìm + gợi ý viết lại truy vấn theo thuật ngữ luật | Câu dev bị trượt top-3 (vd. q14, câu nhiều ý) sẽ được cứu bởi truy vấn viết lại/tìm lần hai; đổi lại tốn thêm token và thời gian. |
| improve-b | top-5, budget 6000, thêm các chunk thuộc Điều liền kề | Evidence/điều kiện nằm ở khoản hoặc Điều kề bên sẽ vào context, tăng Context Evidence Rate; rủi ro nhiễu làm giảm grounding và tăng token. |
| improve-c | thay backend dense bằng hybrid RRF (dense + BM25) | Hybrid có Hit@1 dev cao nhất (14/15) nên context đầu tiên tốt hơn; không cứu được q14 nếu cả hai retriever trượt. |

## Tiêu chí chọn (theo thứ tự, áp dụng trên dev)

1. **Context Evidence Rate** cao nhất (n/N câu có đáp án).
2. Hòa → **điểm grounded answer trung bình /2** do tác giả tự chấm trên các cấu hình hòa.
3. Hòa → ít **chi phí/thời gian** hơn (tổng token, giây).

Câu thiếu bằng chứng (u01, u02) là ràng buộc cứng: cấu hình nào trả lời suy đoán (không từ chối) cả hai câu bị loại, trừ khi mọi cấu hình đều như vậy.

Không dùng test để chọn. Nếu test bị dùng để chỉnh, tạo test mới và ghi rõ.

## Bổ sung (2026-11-16) — rerank, ghi TRƯỚC khi chạy agent

Retrieval trên dev: dense-rerank và hybrid-rerank cùng đạt Hit@1 15/15, Hit@3 15/15 (dense 13/15 và 14/15, hybrid 14/15 và 14/15; xem `results/retrieval/compare-dev.md`). Dev không phân biệt được hai bản rerank, nên chạy cả hai qua agent.

| Cấu hình | Thay đổi | Giả thuyết |
|---|---|---|
| improve-d | hybrid-rerank (20 ứng viên → cross-encoder `bge-reranker-v2-m3` → top-5), 1 lượt tìm, budget 6000, không thêm Điều liền kề | Top-5 đã được xếp theo độ liên quan thật sự nên đủ evidence mà không cần ghép Điều kề; ít nhiễu hơn improve-b, token ít hơn. |
| improve-e | như improve-d nhưng ứng viên lấy từ dense | Tách riêng đóng góp của BM25 trong tầng một. |

Tiêu chí chọn giữ nguyên thứ tự ở trên (CER cao nhất → điểm grounded answer → token/thời gian), áp dụng trên dev cho tất cả cấu hình gồm cả improve-d/e. Hiện improve-b (`final.json`) có CER 15/15 trên dev, nên rerank chỉ thay được nó nếu CER bằng 15/15 và hơn ở tiêu chí 2 hoặc 3.

Lưu ý quan trọng: split test của phần cơ bản đã được dùng (baseline, improve-b; chạy hai lần do freeze lại, xem mục cuối file). Vì vậy improve-d/e chỉ được so sánh trên **dev**; nếu một trong hai thành cấu hình chốt thì không được chạy lại trên test hiện tại mà phải tạo test mới và ghi rõ.

### Kết quả áp dụng tiêu chí cho improve-d/e (2026-11-16)

Tiêu chí 1: improve-b, improve-d, improve-e cùng CER 15/15. Tiêu chí 2 (điểm grounded answer): improve-b 2,00; improve-d 1,73; improve-e 1,73 (cả hai từ chối nhầm q08, q13). improve-b thắng ở tiêu chí 2 nên giữ nguyên `final.json`; không xét tiêu chí 3. Nhãn chi tiết ở `results/agent/improve-d-dev/audit/` và `results/agent/improve-e-dev/audit/`.

### Hai lần chạy test phần cơ bản (ghi bổ sung 2026-11-16)

Split test của phần cơ bản đã được chạy **hai lần** với cùng hai cấu hình (baseline, improve-b; `config.json` giống hệt nhau). Lần 1 (`results/prev-test-old-freeze/`) chạy với freeze đầu tiên. Sau đó tôi bỏ trường siêu dữ liệu `draft_by` khỏi `benchmark/questions.json` (không đổi câu hỏi, đáp án hay evidence), freeze lại và chạy lần 2 (`results/agent/baseline-test`, `results/agent/final-test`); số liệu báo cáo là của lần 2. Giữa hai lần không chỉnh cấu hình, prompt hay code agent, nên test không được dùng để chọn hoặc chỉnh. Hai lần cho kết quả gần như trùng: CER 5/5, grounded 2,00, abstention 2/2, từ chối nhầm 0/5 ở cả hai cấu hình; khác ở citation hợp lệ của baseline (lần 1: 12/12, lần 2: 9/14) và số câu `answered`/`abstain` tự động của baseline (6/1 so với 7/0), do model không tất định.
