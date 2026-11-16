# Dev — agent DeepSeek (17 câu: 15 có đáp án + 2 thiếu bằng chứng)

Kết quả được trích dẫn nằm ở `results/agent/` và `results/retrieval/`. Các thư mục `results/rerun/`, `results/agent-v1-dev-before-final-turn/`, `results/check-*` là lượt chạy kiểm chứng hoặc phiên bản cũ, không chấm nhãn đầy đủ; `results/prev-test-old-freeze/` là lần chạy test đầu (xem `configs/selection.md`).

CER = Context Evidence Rate (n/N câu có đáp án mà context cuối chứa evidence). Nhãn answer/citation/abstention **do tác giả chấm** trong `results/agent/<cfg>-dev/audit/*.csv` (đã chấm, xem bảng bên dưới).

| Cấu hình | CER v1 | abstain v1 | CER sau fix | abstain sau fix | tokens | giây | phân bố số lượt tìm |
|---|---|---|---|---|---|---|---|
| baseline | 14/15 | 5 | 14/15 | 2 | 44741 | 94.94 | {'1': 17} |
| improve-a | 14/15 | 4 | 14/15 | 1 | 75576 | 140.09 | {'1': 14, '4': 3} |
| improve-b | 15/15 | 3 | 15/15 | 1 | 70523 | 97.56 | {'1': 17} |
| improve-c | 14/15 | 4 | 14/15 | 2 | 46958 | 103.91 | {'1': 17} |

Lưu ý nguồn số liệu: `results/agent/improve-a-dev` và `results/agent/improve-c-dev` hiện chứa **lần chạy lại** (mục "Chạy lại để kiểm chứng" bên dưới: improve-a 76.304 token, 139,2 s; improve-c 46.874 token, 99,7 s); nhãn trong `audit/` của hai thư mục này được chấm trên chính lần chạy lại (câu trả lời trong CSV khớp `traces.json`). Lần chạy cũ (75.576 và 46.958 token ở bảng này) nằm ở `results/rerun/improve-a-dev-previous` và `results/rerun/improve-c-dev-previous`. Báo cáo dùng số của lần chạy lại.

v1 = trước khi sửa lỗi "hết lượt tìm kiếm thì bỏ cuộc"; sau fix = lượt cuối không còn công cụ, model phải trả lời từ context.

## Chọn cấu hình (tiêu chí 1: CER cao nhất — chốt trong configs/selection.md trước khi chạy)
improve-b (top-5, budget 6000, thêm Điều liền kề) có CER 15/15, các cấu hình còn lại 14/15 → chọn improve-b (`configs/final.json`), chưa chạy test.
Giới hạn: dev chỉ 15 câu có đáp án; chênh 1 câu (q14) giữa các cấu hình; tốn token hơn baseline ~58%.


## Nhãn đã chấm (answer, citation, abstention) — dev

Bảng sinh từ `python -m src.score_run --run results/agent/<cfg>-dev --split dev` sau khi điền `results/agent/<cfg>-dev/audit/*.csv`. Citation chấm chặt: chỉ citation trỏ tới chunk chứa evidence chuẩn mới tính là hợp lệ; citation phụ (điều luật khác, nêu để so sánh hoặc để giải thích vì sao thiếu bằng chứng) tính là không hợp lệ. Các câu viết "không đủ bằng chứng" nhưng vẫn kèm citation được gán `effective_status = abstain` trong file audit (trace gốc giữ nguyên `answered`).

| Cấu hình | Câu trả lời (trung bình) | Citation hợp lệ | Từ chối đúng (câu thiếu bằng chứng) | Từ chối nhầm (câu có đáp án) |
|---|---|---|---|---|
| baseline | 1.87/2 (14 câu mức 2, 1 câu mức 0) | 22/24 | 2/2 | 1/15 |
| improve-a | 1.87/2 (14 câu mức 2, 1 câu mức 0) | 22/33 | 2/2 | 1/15 |
| improve-b | 2.00/2 (15 câu mức 2, 0 câu mức 0) | 24/32 | 2/2 | 0/15 |
| improve-c | 1.87/2 (14 câu mức 2, 1 câu mức 0) | 22/26 | 2/2 | 1/15 |

## Chạy lại để kiểm chứng (2026-11-16)

Chạy lại bm25-bigram (retrieval) và bốn cấu hình agent trên dev. improve-b chạy ra `results/rerun/improve-b-dev` để không đè nhãn đã chấm.

| Hạng mục | Bảng cũ | Chạy lại |
|---|---|---|
| bm25-bigram Hit@1 / Hit@3 | 13/15, 13/15 | 13/15, 13/15 |
| improve-a CER, token | 14/15, 75.576 | 14/15, 76.304 |
| improve-b CER, token | 15/15, 70.523 | 15/15, 70.896 |
| improve-c CER, token | 14/15, 46.958 | 14/15, 46.874 |

CER khớp bảng cũ ở cả ba cấu hình. Token và thời gian lệch nhẹ do model không tất định. Số câu `answered`/`abstain` có thể khác giữa các lần chạy (ví dụ improve-b: 16/1 ở lần đã chấm, 15/2 ở lần chạy lại), vì vậy kết luận nên dựa vào CER và nhãn chứ không dựa vào số câu từ chối tự động.

## Rerank (2026-11-16)

Retrieval dev (top-3): dense-rerank và hybrid-rerank đều Hit@1 15/15, Hit@3 15/15 (dense 13/15 và 14/15; hybrid 14/15 và 14/15). Chi tiết ở `results/retrieval/compare-dev.md`, giải thích tiêu chí ở `results/retrieval/rerank-notes.md`.

Agent trên dev, cấu hình ghi trước ở `configs/selection.md` (top-5, budget 6000, 1 lượt tìm, không thêm Điều kề):

| Cấu hình | Retrieval | CER | trả lời / từ chối | token (vào + ra) | giây |
|---|---|---|---|---|---|
| improve-b (đang chọn) | dense + Điều kề | 15/15 | 16 / 1 | 70.523 | 97,6 |
| improve-d | hybrid-rerank | 15/15 | 13 / 4 | 59.712 | 376,6 |
| improve-e | dense-rerank | 15/15 | 14 / 3 | 65.366 | 471,3 |

Cả ba hòa ở tiêu chí 1 (CER 15/15). Rerank dùng ít token hơn nhưng chậm hơn 4-5 lần (rerank chạy CPU) và từ chối nhiều hơn: cả improve-d và improve-e đều từ chối thêm q08 và q13 (hai câu có đáp án) so với improve-b; các từ chối ở u01, u02 là đúng. Nhãn đã chấm ở mục bên dưới: q08, q13 là từ chối nhầm.

### Nhãn improve-d / improve-e (2026-11-16)

Chấm theo cùng quy ước với bảng trên (citation chặt: citation phụ tính không hợp lệ). Bảng từ `python -m src.score_run --run results/agent/<cfg>-dev --split dev`.

| Cấu hình | Câu trả lời (trung bình) | Citation hợp lệ | Từ chối đúng (câu thiếu bằng chứng) | Từ chối nhầm (câu có đáp án) |
|---|---|---|---|---|
| improve-b (đang chọn) | 2.00/2 (15 câu mức 2) | 24/32 | 2/2 | 0/15 |
| improve-d | 1.73/2 (13 câu mức 2, 2 câu mức 0) | 22/23 | 2/2 | 2/15 |
| improve-e | 1.73/2 (13 câu mức 2, 2 câu mức 0) | 22/27 | 2/2 | 2/15 |

Hai câu mức 0 ở cả d và e là q08 và q13: context đã chứa evidence chuẩn (context score 2) nhưng model vẫn từ chối, nên đây là từ chối nhầm chứ không phải lỗi retrieval. improve-e u02 viết "không quy định mức thưởng Tết tối thiểu" kèm citation nên được gán `effective_status = abstain` (từ chối đúng). Theo tiêu chí 2 trong `configs/selection.md`, improve-b vẫn là cấu hình chốt.
