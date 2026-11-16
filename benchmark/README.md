# Benchmark Day 7 — Bộ luật Lao động 2012 & 2019

`questions.json`: 24 câu = 20 câu Day 6 (chuyển nguyên văn, giữ split) + 4 câu thiếu bằng chứng.
Kiểm tra: `python -m src.benchmark validate` → phải in `0 problems`.

| Split | Có đáp án | Thiếu bằng chứng |
|---|---:|---:|
| dev (q01–q15, u01–u02) | 15 | 2 |
| test (q16–q20, u03–u04) | 5 | 2 |

- Câu có đáp án: `gold` = gold chính + `alt_gold` của Day 6 (điều tương ứng ở bộ luật kia). Hit khi chunk cùng nguồn, khoảng trang chứa trang gold và chứa evidence (so khớp NFC, bỏ khoảng trắng, như Day 6).
- Câu thiếu bằng chứng (u01–u04): `key_phrases` là cụm từ mà `validate` kiểm tra không xuất hiện trong kho chunk.
- `filter`: chỉ có khi chính câu hỏi nêu năm bộ luật (người dùng cung cấp trước), không lấy từ gold.

## Việc tác giả đã làm

- [x] Tự mở cả hai PDF và tìm cho từng câu u01–u04 để xác nhận **thật sự không có đáp án**; sửa/thay câu nếu có. Ghi ngày và cách tìm bên dưới, rồi đổi `verified_by_author` thành `true`.
- [x] Xem lại các câu Day 6 nếu muốn sửa; sau khi chốt, chạy `python -m src.benchmark freeze` để ghi `benchmark/freeze.json`. **Không chạy split test trước bước này.** (Đã freeze. Lần freeze đầu bị thay sau khi bỏ trường `draft_by`; test đã chạy với cả hai bản freeze, xem `configs/selection.md`.)

## Nhật ký duyệt (tác giả điền)

- Ngày: 2026-11-15
- Cách kiểm tra u01–u04: tìm toàn văn trong hai PDF gốc (`data/raw/`, chuẩn hóa NFC và khoảng trắng, không phân biệt hoa thường), đọc ngữ cảnh từng chỗ khớp và đối chiếu lại với PDF. Kết quả:
  - u01 (lương tối thiểu vùng I): không có "vùng I" hay số tiền đồng/tháng. 2012 Điều 91 và 2019 Điều 91 chỉ nêu nguyên tắc; mức cụ thể do Chính phủ công bố. Không có đáp án.
  - u02 (thưởng Tết tối thiểu): không có cụm "thưởng Tết". "Tết" chỉ xuất hiện ở điều nghỉ lễ, tết (2012 Điều 115, 2019 Điều 112) và tiền lương làm thêm giờ. Điều về thưởng (2012 Điều 103, 2019 Điều 104) để người sử dụng lao động quy định theo quy chế, không có mức tối thiểu. Không có đáp án.
  - u03 (hỗ trợ internet, điện thoại khi làm việc từ xa): không có "từ xa", "internet" hay "điện thoại" trong cả hai bản. Chỉ có "làm việc tại nhà" ở 2012 Điều 185 (nhận việc về làm tại nhà theo hình thức gia công, không thuộc đối tượng áp dụng của Bộ luật), không nói gì về hỗ trợ chi phí. Không có đáp án.
  - u04 (mức phạt tiền cụ thể khi dùng lao động chưa thành niên trái quy định): không có "triệu đồng" và không có số tiền đồng nào trong cả hai bản. Điều về xử lý vi phạm (2012 Điều 239, 2019 Điều 217) chỉ nói xử lý theo quy định về xử phạt vi phạm hành chính. "Phạt tiền" còn xuất hiện ở điều cấm xử lý kỷ luật bằng phạt tiền. Không có đáp án.
- Câu đã viết lại / thay: không có. Cả bốn câu giữ nguyên; `verified_by_author` đã đổi thành `true`.
