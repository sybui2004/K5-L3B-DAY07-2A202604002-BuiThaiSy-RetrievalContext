# Bonus: HELM (162 trang) — kết quả và cách chạy lại

**Kết quả: đạt ngưỡng trên bộ test thứ ba (M01–M33): improve-f 31/33 = 93,94%** (cần ít nhất 30/33 = 90,9%). Cấu hình chọn: `improve-f` (`configs/final.json`), chọn theo tiêu chí ghi trước trong `configs/selection.md` (vòng 5).
Nhãn đạt/không đạt ghi ở `results/*/audit/pass_fail.csv` (cột `pass_fail`, `reason`); nhãn của test thứ ba và các lượt vòng 5 đã được tác giả duyệt và đối chiếu với PDF.
Các bộ test trước (T01–T33, N01–N33) đã bị dùng để soi lỗi nên nay là `retired`; kết quả cũ trên chúng (T01–T33: improve-d 27/33, baseline 25/33; N01–N33: improve-e 27/33, baseline 23/33) vẫn giữ trong các mục bên dưới.

### Test thứ ba M01–M33 (2026-11-16, chạy một lần với `--final`)

| Cấu hình | Đạt | Bảng | Ảnh/sơ đồ | Biểu đồ | Multi-hop | Text | Thiếu bằng chứng | Token vào+ra | Giây |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 23/33 (69,7%) | 6/7 | 3/6 | 4/6 | 0/4 | 4/4 | 6/6 | 104.593 | 220 |
| improve-f (final) | **31/33 (93,9%)** | 7/7 | 5/6 | 5/6 | 4/4 | 4/4 | 6/6 | 276.268 | 885 |

Hai câu improve-f trượt đều là từ chối dù phần đọc hình đã có câu trả lời: M11 (tên mục "Recipe creator" trong Figure 9, chữ trong ảnh raster không trích được) và M17 (đường đứt ngang ở 0,5 trong Figure 24; model không tin mô tả tự động). M12 chấm đạt ở mức biên (dùng cách gọi trong caption thay cho tiêu đề in trên hình); nếu tính trượt thì còn 30/33 = 90,9%, vẫn đạt.
Trước khi gộp, M01–M33 được đối chiếu với PDF (tác giả đã xác nhận): đáp án khớp; sửa vị trí ghi chú của M11 (mục cuối cột 3) và ghi chú kiểm tra của M28 ("Falcon" chỉ xuất hiện trong họ tác giả "Saad-Falcon", trang 108).
Freeze: `benchmark/freeze.json` SHA `09012e2d…bddba000` (120 câu: dev 21, retired 66, test 33), ghi trước khi chạy.
Chi phí (mức trần, coi mọi token vào là cache miss, giá DeepSeek Flash xem 2026-11-16; `python -m src.cost bonus/results/final-test3 bonus/results/baseline-test3`): improve-f 0,054 USD ngoài giờ cao điểm / 0,108 USD giờ cao điểm; baseline 0,025 / 0,051 USD. Embedding, mô tả hình và đọc hình chạy cục bộ: 0 USD.
Các file sửa sau khi chạy test (chỉ ghi chú, docstring, nhãn) được liệt kê ở cuối `configs/selection.md`.

### Vòng 2 (2026-11-16)
- Bộ test cũ T01–T33 đã bị dùng để soi lỗi nên chuyển sang split `retired`. Bộ test mới N01–N33 (cùng cơ cấu nhóm, dùng hình/bảng/đoạn khác) được kiểm bằng `validate` (0 lỗi) và freeze **trước** khi chạy.
- Sửa nguyên nhân gốc của lỗi multi-hop: `pack_context` xếp chunk theo thứ tự xuất hiện nên lượt tìm đầu chiếm hết ngân sách; `pack: "round_robin"` xen kẽ kết quả các lượt theo hạng (`src/agent.py`).
- Dev: improve-e 21/21 (151.995 token) so với improve-d 21/21 (161.260 token) → chọn improve-e (`configs/selection.md`).

| Cấu hình (test mới, 1 lần) | Đạt | Bảng | Ảnh/sơ đồ | Biểu đồ | Multi-hop | Text | Thiếu bằng chứng | Token vào+ra | Giây |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 23/33 (69,7%) | 5/7 | 6/6 | 2/6 | 1/4 | 3/4 | 6/6 | 97.708 | 203 |
| improve-e (final) | 27/33 (81,8%) | 7/7 | 6/6 | 2/6 | 2/4 | 4/4 | 6/6 | 312.213 | 381 |

Lỗi còn lại của improve-e: 3 câu (N18, N19, N22) model trả về nội dung **rỗng** dù context đã có đúng hình/bảng → bị ép thành từ chối;
3 câu đọc biểu đồ sai (N14 nhầm tập panel, N17 lấy điểm ngoại lai thay trung vị, N20 nhầm đáy/đỉnh panel BBQ).
Chạy chẩn đoán trên `retired` (`results/final-retired`, không tính điểm): 30/33. T20, T22, T23 đã đúng nhờ round-robin; T01 (dòng Anthropic-LM không được truy xuất), T10 (đưa ví dụ trong caption thay vì Natural Questions, IMDB) và T19 (mô tả hình sai) vẫn hỏng.
Nếu sửa tiếp (ví dụ xử lý câu trả lời rỗng), cần một bộ test mới nữa vì N01–N33 nay cũng đã bị soi lỗi.

### Vòng 5 (2026-11-16) — chunk theo dòng bảng (kết quả test sạch ở mục "Test thứ ba" phía trên)
- **Một chunk cho mỗi dòng bảng** ở Table 5, 6, 13 (danh sách mô hình, phần cứng, nhiễm dữ liệu): `ROW_TABLES` trong `src/ingest.py`,
  `split_table(per_row=True)` và `short_caption` trong `src/extract.py` (có test). Nạp lại trang 43, 44, 157 vào `helm_chunks`.
  Mục tiêu: sửa lỗi dòng cần dùng đứng hạng ~8 nên không lọt vào ngân sách context (D13, T01, T23, N20 ở vòng 4).
- Chạy chẩn đoán improve-f (`results/v5-improve-f-*`, không tính điểm): context đủ evidence ở dev 18/18, `retired` 27/27, N01–N33 26/27 (trượt N24).
  D13, T01, T23, N20 đã có đủ evidence. T33 lỗi hệ thống do DeepSeek timeout. Token vào+ra: dev 157.879, N 242.983, `retired` 243.630; thời gian 798 s / 1.059 s / 1.181 s.
  Nhãn `pass_fail` của ba lượt này **chưa điền**.
- **Bộ test thứ ba:** `benchmark/build_test3.py` sinh M01–M33 (7 bảng, 6 ảnh, 6 biểu đồ, 4 multi-hop, 4 text, 6 thiếu bằng chứng);
  `python -m bonus.benchmark.build_questions --with-test3` gộp vào `questions.json` (N01–N33 sang `retired`), rồi freeze.
- **Chọn cấu hình:** dev bão hòa nên tập chọn mở rộng thành dev + retired (87 câu), cùng index v5, tiêu chí ghi trước.
  improve-e 85/87 (663.797 token), improve-f 85/87 (644.492 token) → improve-f (ít token hơn). Chi tiết: `configs/selection.md`.

### Vòng 4 (2026-11-16) — đọc biểu đồ, CHƯA có test sạch
- **Trung vị box plot đo từ vector PDF** (`extract.boxplot_medians`): khung mỗi panel = nền trắng của trục, trung vị = đoạn ngang màu cam,
  giá trị = hồi quy tuyến tính theo nhãn trục y (khôi phục dấu trừ bị mất), danh mục = nhãn trục x gần nhất (ghép nhãn nhiều dòng).
  Ghi vào chunk hình: "Box-plot medians measured from the PDF vector graphics", kèm trung vị cao/thấp nhất mỗi panel (Figure 25, 34, 36–39).
- **Đọc hình theo câu hỏi lúc trả lời** (`vlm.FigureReader`, cấu hình `improve-f`, `figure_reader: true`): với tối đa 2 hình hạng cao mỗi lượt tìm
  (tối đa 3 hình/câu), hỏi `qwen2.5vl:7b` chính câu hỏi trên ảnh crop; kết quả gắn vào bản sao chunk, ghi rõ "may contain errors".
  Hook chung `enrich(question, results)` trong `src/agent.py`. Chi phí: chạy chậm ~3,5 lần (dev 677 s so với ~185 s).
- Đo trên các bộ **đã bị soi lỗi** (chẩn đoán): dev 20/21, `retired` 30/33, N01–N33 32/33 (so với improve-e v3: 21/21, 30/33, 29/33).
  Đã cứu: N14, N17, N19 (biểu đồ), N09, T10, T16. Lỗi còn lại chủ yếu là **truy xuất dòng bảng** (D13, T01, T23, N20): dòng cần dùng đứng hạng ~8
  nên không vào được ngân sách 12.000 ký tự, tùy cách model viết truy vấn. T19 (BLiMP) model vẫn từ chối.

### Vòng 3 (2026-11-16) — sửa 2 lỗi, CHƯA có test sạch
- **Câu trả lời rỗng:** `deepseek-v4-flash` là model có suy luận; phần suy luận dùng hết `max_tokens` (1.800) → `finish_reason=length`, nội dung rỗng → bị ép thành từ chối (N18, N19, N22).
  Sửa: `DeepSeekController.decide` gọi lại với ngân sách gấp đôi (tối đa 8.192) khi bị cắt mà không có nội dung (`src/llm.py`).
- **Chữ trong hình mất bố cục:** trước đây nối thành một chuỗi phẳng và cắt ở 900 ký tự, nên không biết nhãn nào ở trên/dưới hay thuộc panel nào.
  Sửa: XY-cut theo khoảng trắng chia chữ thành vùng (panel, chú giải, trục), ghi vị trí (% khung hình), liệt kê trên→dưới; bỏ caption;
  giải mã font lệch theo từng dòng; giới hạn 2.400 ký tự (`extract.region_layout`, `ingest.figure_text`). Index ingest lại (`logs/ingest_v3b.log`).
- Đo trên các bộ **đã bị soi lỗi** (chỉ để chẩn đoán, không phải điểm báo cáo): dev 21/21; `retired` 30/33 (trước 27/33);
  N01–N33 29/33 (trước 27/33; lượt này dùng giới hạn 1.600 nên N09 bị cắt chữ — đã nâng lên 2.400).
- Lỗi còn lại cần nhìn ảnh (trung vị, tập panel: N14, N17, N19, T19) hoặc truy xuất dòng bảng (T01).
- Muốn báo điểm hợp lệ cần bộ test thứ ba, soạn và freeze trước khi chạy.

### Vòng 1 (bộ test cũ, nay là `retired`)

## Tài liệu
- *Holistic Evaluation of Language Models* (Liang et al.), arXiv 2211.09110v2, 162 trang, giấy phép CC BY 4.0 (theo trang arXiv).
  Nguồn: https://arxiv.org/abs/2211.09110 · PDF: https://arxiv.org/pdf/2211.09110v2
- Bản đã dùng: `data/raw/helm_2211.09110v2.pdf`, SHA-256 `30970bda8958a1a8adf6a0a82feef9728331840288b7d2b49368bac87fd25f18`.
- Có 40 hình (sơ đồ, bản đồ, biểu đồ cột/đường/phân tán/hộp), 14 bảng, văn bản dài.

## Pipeline index (`src/`)
| Bước | File | Ghi chú |
|---|---|---|
| Trích văn bản, bảng, vùng hình (PyMuPDF) | `src/extract.py` | Bảng dựng lại theo hàng từ tọa độ chữ (`find_tables` làm nát ô gộp). Hình: cắt theo caption, rộng hết khổ chữ. |
| Mô tả hình | `src/vlm.py` | Ollama `qwen2.5vl:7b` chạy local; chữ in trong hình (PDF vector) + caption + mô tả của model. |
| Index | `src/ingest.py` | Embedding `bge-m3` (1024 chiều), bảng `helm_chunks` trong Postgres Day 6. Chunk có trang, bbox, ảnh crop (`data/figures/`). |
| Kho đọc + retriever | `src/store.py` | dense, bm25, hybrid (RRF). |
| Agent | `src/run_bonus.py` (dùng lại `src/agent.py` của phần cơ bản) | DeepSeek, prompt ở `src/prompts.py`. |
| Chấm | `src/eval_bonus.py` | Context evidence (cần đủ mọi evidence), bảng chấm, `score` theo nhóm. |
| Kiểm benchmark với PDF | `src/validate.py` | Chuỗi evidence có trên trang đã ghi; từ khóa câu thiếu bằng chứng không có trong tài liệu. |

Thống kê index hiện tại (khớp bảng `helm_chunks` trong DB): 863 chunk (654 văn bản, 169 bảng, 40 hình), 162/162 trang có nội dung, 0 lỗi mô tả hình. Từ vòng 4, Table 5, 6 và 13 (danh sách mô hình, phần cứng, nhiễm dữ liệu) tách mỗi dòng một chunk nên bảng tăng từ 74 lên 169 chunk; `data/index_stats.json` đã được đếm lại từ `helm_chunks` (863 chunk) và ghi lại số của lần ingest đầy đủ trước đó (768 chunk) trong trường `note`.
Hình có vùng cắt dự phòng (không tìm thấy vùng vẽ): 3, 6, 11–16, 22.

## Chạy lại
```bash
ollama pull qwen2.5vl:7b && ollama pull bge-m3
python -m bonus.src.ingest --vlm qwen2.5vl:7b --table-limit 700      # ~35 phút lần đầu; mô tả hình được cache
python -m bonus.src.validate                                          # phải in 0 problems (có thể truyền đường dẫn file câu hỏi)
python -m bonus.src.run_bonus --config bonus/configs/final.json --split dev --out bonus/results/final-dev
python -m bonus.src.eval_bonus sheets --run bonus/results/final-dev   # sinh bảng chấm; điền pass_fail rồi:
python -m bonus.src.eval_bonus score  --run bonus/results/final-dev
```
Test: thêm `--split test --final` (chỉ chạy được khi `benchmark/freeze.json` khớp `questions.json`).

## Benchmark (`benchmark/`)
120 câu, soạn dựa trên bản gốc và kiểm bằng `validate`; freeze SHA `benchmark/freeze.json`.
| Split | Có đáp án | Thiếu bằng chứng | Nhóm (bảng / ảnh / biểu đồ / multi-hop / text) |
|---|---:|---:|---|
| dev | 18 | 3 | 4 / 3 / 4 / 3 / 4 |
| retired (T01–T33 và N01–N33, hai bộ test cũ) | 54 | 12 | 14 / 12 / 12 / 8 / 8 |
| test (M01–M33) | 27 | 6 | 7 / 6 / 6 / 4 / 4 |

## Kết quả vòng 1 (test cũ T01–T33, nay là `retired`)

Các thư mục `results/_history*` là lượt chạy dev của các phiên bản index cũ, không chấm nhãn và không được trích dẫn.

Dev (cấu hình chọn theo `configs/selection.md`, ghi trước khi chạy test): baseline 19/21, improve-a 19/21, improve-b 20/21, improve-c 20/21, **improve-d 21/21**.

Test (một lần, `--final`, 33 câu, 0 lỗi hệ thống):
| Cấu hình | Đạt | Bảng | Ảnh/sơ đồ | Biểu đồ | Multi-hop | Text | Thiếu bằng chứng | Token vào+ra | Giây |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 25/33 (75,8%) | 6/7 | 5/6 | 5/6 | 0/4 | 3/4 | 6/6 | 96.346 | 189 |
| improve-d (final) | 27/33 (81,8%) | 6/7 | 5/6 | 5/6 | 1/4 | 4/4 | 6/6 | 311.555 | 335 |

Chi phí vòng 1 chỉ ghi token; cách quy ra tiền xem mục test thứ ba (`python -m src.cost`).

## Lỗi và giới hạn
- **Multi-hop là điểm yếu chính** (1/4): hàng cần tra trong Table 5 thường không lọt vào context, nên agent trả lời "không đủ bằng chứng" cho phần thứ hai (T01, T20, T22, T23).
- **Mô tả hình của model vision có thể sai:** T19 (biểu đồ Figure 33) bị sai vì tin mô tả tự động; T10 lấy ví dụ từ caption thay vì nhãn trong sơ đồ. Giá trị số trong biểu đồ không đọc được chính xác; câu biểu đồ trong benchmark chủ yếu hỏi trục, chú giải, thứ hạng.
- **Lỗi tìm được khi chỉnh trên dev:** (1) mô hình hay bỏ tiền tố `H:` khi trích dẫn nên code ép thành từ chối → đổi ID chunk sang `helm-pNNN-...` không có dấu hai chấm; (2) bảng cắt khúc lớn làm hàng bị chìm → cắt khúc 700 ký tự, lặp dòng tiêu đề; (3) một câu thiếu bằng chứng ở dev (giá mỗi 1.000 token) tính ra được từ tổng chi phí nên thay bằng câu khác và freeze lại trước khi chạy test.
- Dev chỉ 21 câu, chênh 1–2 câu; model không tất định.
- Một số câu trả lời của baseline bị cắt do giới hạn token đầu ra (T22).
- Nhãn của mọi vòng đã được tác giả đọc lại và duyệt (ADVANCED yêu cầu tác giả đối chiếu từng câu với bản gốc).
