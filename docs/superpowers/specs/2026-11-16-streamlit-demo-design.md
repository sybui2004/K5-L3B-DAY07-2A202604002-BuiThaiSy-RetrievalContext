# Thiết kế: giao diện demo Streamlit cho Day 7

Trạng thái: bạn đã đồng ý hướng làm (2 tab: Trace và Live) và chỉ định làm trong thư mục này.

## Mục đích
Có một giao diện để demo nhanh các phần bài lab chấm: agent truy xuất, trace tool, chọn context, citation hoặc từ chối khi thiếu bằng chứng, so sánh retrieval, và (bonus) trích dẫn ảnh/bảng của HELM. Hiện lab chỉ có CLI ghi ra file.

## Phạm vi
- Một app Streamlit `demo/app.py` có 2 tab: **Trace** (xem lại kết quả đã lưu) và **Live** (gọi agent thật).
- Thanh bên chọn bộ dữ liệu: Cơ bản (Luật Lao động 2012/2019, `results/agent/*`) hoặc Bonus (HELM, `bonus/results/*`).
- Dùng lại `src/` và `bonus/src/`; không sửa code ở đó.

## Không làm
- Không có nút chạy split test (test chỉ chạy một lần, xem RULES.md).
- Không in khóa API hay `DATABASE_URL`.
- Không chạy lại benchmark cả bộ từ giao diện.

## Tab Trace (phát lại, không cần DB hay API)
- Chọn một lần chạy (thư mục có `traces.json`). Phía trên hiện `summary.json`: số câu theo trạng thái, context evidence rate, token, thời gian; nếu có `audit/` thì thêm nhãn.
- Bảng câu hỏi: id, loại, trạng thái, số lượt search, giây, token, nhãn (nếu có). Chọn một câu để xem:
  - từng lượt search: query, top-k kèm score, rank, trang;
  - context đã ghép (chunk nào vào, theo thứ tự);
  - câu trả lời kèm citation, hoặc lý do từ chối/lỗi;
  - đáp án và evidence chuẩn từ benchmark.
- Bonus: hiện thêm ảnh crop của chunk được trích dẫn (`bonus/data/figures/`) nếu có.

## Tab Live (gọi thật)
- Nhập câu hỏi, hoặc chọn nhanh một câu dev trong benchmark. Chỉ dev, không có test.
- Chọn cấu hình trong `configs/*.json` (hoặc `bonus/configs/*.json`) và cho ghi đè `method` (dense, bm25, bm25-bigram, hybrid).
- Bấm chạy: gọi `run_question` thật (Postgres, Ollama bge-m3, DeepSeek), rồi hiển thị bằng cùng bộ hiển thị trace của tab Trace, kèm giây và token.
- Có nút "So sánh các phương pháp": cùng một câu, chỉ chạy retrieval (không gọi LLM) cho từng method, hiện top-k cạnh nhau với score.
- Thiếu DB, Ollama hoặc khóa API thì báo lỗi rõ trong tab Live; tab Trace vẫn dùng được.

## Cấu trúc
- `demo/traces.py`: đọc thư mục run, summary, audit, benchmark; chuẩn hóa dữ liệu hiển thị. Không import streamlit nên test được.
- `demo/live.py`: dựng retriever/controller theo dataset và chạy một câu; không import streamlit.
- `demo/app.py`: giao diện, ghép hai module trên.
- `tests/test_demo_traces.py`, `tests/test_demo_live.py`: test bằng dữ liệu nhỏ và mock, không gọi mạng.
- Thêm `streamlit` vào `requirements.txt`. Chạy: `streamlit run demo/app.py`.

## Các hướng đã cân nhắc
- App Streamlit dùng lại `src/` (chọn): nhanh nhất, đúng mục đích demo.
- Viết lại logic riêng cho UI: trùng lặp, dễ lệch với kết quả đã nộp. Loại.
- FastAPI + React: quá nặng cho một buổi demo. Loại.

## Do người làm quyết
Bố cục chi tiết, màu sắc, cách đánh dấu chunk trong context.
