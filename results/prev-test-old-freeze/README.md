# Lần chạy test đầu tiên (freeze cũ)

Split test của phần cơ bản đã được chạy **hai lần** với cùng hai cấu hình (baseline, improve-b; `config.json` giống hệt nhau). Lần 1 (`results/prev-test-old-freeze/`) chạy với freeze đầu tiên. Sau đó tôi bỏ trường siêu dữ liệu `draft_by` khỏi `benchmark/questions.json` (không đổi câu hỏi, đáp án hay evidence), freeze lại và chạy lần 2 (`results/agent/baseline-test`, `results/agent/final-test`); số liệu báo cáo là của lần 2. Giữa hai lần không chỉnh cấu hình, prompt hay code agent, nên test không được dùng để chọn hoặc chỉnh. Hai lần cho kết quả gần như trùng: CER 5/5, grounded 2,00, abstention 2/2, từ chối nhầm 0/5 ở cả hai cấu hình; khác ở citation hợp lệ của baseline (lần 1: 12/12, lần 2: 9/14) và số câu `answered`/`abstain` tự động của baseline (6/1 so với 7/0), do model không tất định.

Thư mục này giữ lại để minh bạch; không dùng làm số liệu báo cáo.
