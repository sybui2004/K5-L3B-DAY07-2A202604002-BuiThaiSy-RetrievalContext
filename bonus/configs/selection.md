# Chọn cấu hình bonus (HELM) — ghi TRƯỚC khi chạy test

Tiêu chí: chọn cấu hình có tỷ lệ đạt cao nhất trên **dev** (nhãn trong `bonus/results/<cfg>-dev/audit/pass_fail.csv`);
nếu bằng nhau thì chọn cấu hình dùng ít token hơn. Test chỉ chạy một lần, cho `baseline` và cấu hình được chọn.

Kết quả dev (21 câu: 18 có đáp án, 3 thiếu bằng chứng), index 768 chunk, bảng cắt khúc 700 ký tự:

| Cấu hình | Mô tả | Đạt | Token vào+ra | Giây |
|---|---|---|---|---|
| baseline | dense top-5, 1 lượt tìm, budget 6000 | 19/21 | 59.239 | 108 |
| improve-a | hybrid top-8, 1 lượt tìm, budget 9000 | 19/21 | 75.823 | 106 |
| improve-b | dense top-6, tối đa 3 lượt, budget 9000 | 20/21 | 120.450 | 163 |
| improve-c | dense top-8, tối đa 4 lượt, budget 12000, gợi ý tách câu nhiều phần | 20/21 | 180.114 | 193 |
| improve-d | hybrid top-8, tối đa 4 lượt, budget 12000, gợi ý tách câu nhiều phần | 21/21 | 161.260 | 173 |

Chọn: **improve-d** (`bonus/configs/final.json`).
Giới hạn: dev chỉ 21 câu; chênh lệch 1–2 câu; model không tất định nên kết quả mỗi lần chạy có thể lệch.

## Vòng 2 (2026-11-16) — ghi TRƯỚC khi chạy bộ test mới

Bộ test cũ T01–T33 đã bị dùng để soi lỗi sau khi chạy nên chuyển sang split `retired` (không báo điểm trên nó nữa).
Bộ test mới N01–N33 (cùng cơ cấu nhóm, soạn từ hình/bảng/đoạn mà dev và `retired` không dùng) được freeze trước khi chạy.

Nguyên nhân gốc của các câu multi-hop hỏng: `pack_context` xếp chunk theo thứ tự xuất hiện, nên các kết quả của lượt tìm
đầu tiên chiếm gần hết ngân sách 12.000 ký tự và kết quả của các lượt sau (dòng Table 5) không vào được context.
Sửa: `pack: "round_robin"` lấy hạng 1 của mọi lượt, rồi hạng 2 của mọi lượt, v.v. (`src/agent.py`, mặc định vẫn là `order`).

| Cấu hình | Mô tả | Đạt (dev) | Token vào+ra | Giây |
|---|---|---|---|---|
| improve-d | như trên | 21/21 | 161.260 | 173 |
| improve-e | improve-d + đóng gói round-robin | 21/21 | 151.995 | 166 |

Chọn: **improve-e** (bằng điểm, ít token hơn). `configs/final.json` cập nhật theo.

## Vòng 5 / bộ test thứ ba (2026-11-16) — tiêu chí ghi TRƯỚC khi có kết quả improve-e trên index mới và TRƯỚC khi chạy test M01–M33

Bối cảnh: bộ test thứ ba M01–M33 đã gộp vào `questions.json` (N01–N33 chuyển sang `retired`) và freeze
(`freeze.json` SHA `09012e2d…bddba000`). Index hiện tại là v5 (Table 5, 6, 13 tách một chunk mỗi dòng).

Dev (21 câu) đã bão hòa: improve-e và improve-f đều có thể đạt 21/21, nên dev không còn phân biệt được hai cấu hình.
Vì vậy tập dùng để chọn được mở rộng thành **dev + retired** (21 + 66 = 87 câu; T01–T33 và N01–N33 đều không còn là test).
Hai cấu hình chạy trên **cùng index v5**: improve-f (`v5-improve-f-dev`, `-retired`, `-n-diagnostic`) và
improve-e (`v5-improve-e-dev`, `v5-improve-e-retired`).

Tiêu chí (theo thứ tự): (1) số câu đạt trên 87 câu cao nhất; (2) nếu bằng nhau, ít token hơn.
Lỗi hệ thống (timeout) tính là không đạt. Cấu hình thắng ghi vào `final.json`; test M01–M33 chạy **một lần** với `--final`.
Giới hạn: các câu `retired` đã từng được dùng để soi lỗi trong vòng 2–5, nên đây là tập phát triển, không phải ước lượng
khách quan; chỉ M01–M33 là test sạch.

### Kết quả áp dụng tiêu chí vòng 5 (nhãn đã được tác giả duyệt)

| Cấu hình (index v5) | dev | T01–T33 | N01–N33 | Tổng 87 câu | Token vào+ra | Giây |
|---|---|---|---|---|---|---|
| improve-e | 21/21 | 31/33 (T10, T19 sai) | 33/33 | 85/87 | 663.797 | 751 |
| improve-f | 21/21 | 31/33 (T10 sai, T33 timeout) | 33/33 | 85/87 | 644.492 | 3.037 |

Bằng nhau ở tiêu chí 1 → tiêu chí 2 (ít token hơn): **improve-f**. `final.json` đổi sang improve-f.
Ghi chú: improve-f chậm hơn khoảng 4 lần vì gọi `qwen2.5vl:7b` đọc hình; tiêu chí ghi trước không xét thời gian.

### Mốc thời gian và các sửa đổi sau khi chạy test thứ ba (ghi 2026-11-16)

Thứ tự (giờ máy, 2026-11-16): gộp M01–M33 và freeze `benchmark/freeze.json` (17:03) → bắt đầu chạy improve-e trên index v5 (dev, retired) → trong lúc improve-e đang chạy, chấm nhãn các lượt v5 của improve-f và ghi tiêu chí vòng 5 vào file này, **trước khi xem kết quả improve-e** → chấm improve-e, áp dụng tiêu chí, ghi `final.json` = improve-f (17:17) → chạy test một lần (`final-test3` xong 17:32, rồi `baseline-test3` 17:36). Test M01–M33 không được mở ra xem trước khi chọn cấu hình.
Các file sửa **sau** khi test chạy xong, không thay đổi cấu hình hay câu hỏi:
- `configs/selection.md`: thêm bảng "Kết quả áp dụng tiêu chí vòng 5", đổi tiêu đề bảng khi tác giả duyệt nhãn, và thêm mục này. Phần tiêu chí (mục "Vòng 5 / bộ test thứ ba") giữ nguyên.
- `benchmark/build_test3.py`: chỉ đổi docstring từ "DRAFT" sang "đã duyệt, đã freeze, đã chạy". Danh sách câu M01–M33 không đổi; `questions.json` vẫn khớp SHA trong `freeze.json`.
- `results/*/audit/pass_fail.csv`: điền nhãn và lý do sau khi chạy (đúng quy trình), sau đó tác giả duyệt.
Các file này chưa được commit tại thời điểm chạy, nên mốc thời gian ở trên là thời gian sửa file trên máy, không phải bằng chứng độc lập.
