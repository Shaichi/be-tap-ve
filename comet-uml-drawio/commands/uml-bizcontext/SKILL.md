---
name: uml-bizcontext
description: Vẽ sơ đồ ngữ cảnh nghiệp vụ (business context diagram / DFD mức 0) ra draw.io – hình tròn trung tâm là hệ thống / doanh nghiệp, các thực thể bên ngoài xếp vòng quanh, mũi tên thẳng ghi luồng dữ liệu / thông tin trao đổi 2 chiều – bố cục tự động không chồng hình, nhãn không đè đường. Dùng khi người dùng gọi /uml-bizcontext hoặc cần mô tả phạm vi nghiệp vụ cho người không làm kỹ thuật.
argument-hint: "<hệ thống / doanh nghiệp + các bên liên quan>"
user-invocable: true
---

# Vẽ sơ đồ ngữ cảnh nghiệp vụ (`/uml-bizcontext`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; chưa rõ
hệ thống nào thì hỏi lại một câu ngắn rồi mới vẽ.

Khác `/uml-context` (context diagram COMET dạng class «software system» – «external …», dùng cho thiết kế phần
mềm): sơ đồ này dành cho **nghiệp vụ** – hình tròn ở giữa, ngôn ngữ của người dùng cuối, không có stereotype kỹ
thuật.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/shop_bizcontext.json` — khuôn chuẩn (1 hệ thống trung tâm, 6 bên ngoài, 13 luồng).
- `<ENGINE>/references/spec-format.md` — mục *Context diagram nghiệp vụ*; `<ENGINE>/references/uml-notation.md` —
  mục *Context diagram nghiệp vụ*.

## 2. Quy tắc
- `"diagram": "bizcontext"`, `"title"`.
- **Đúng 1** phần tử trung tâm `{"id", "type": "system", "name": "Hệ thống bán hàng trực tuyến"}` (B1) — vẽ thành
  hình tròn ở giữa.
- Thực thể ngoài `{"id", "type": "external", "name": "Khách hàng"}`: người, tổ chức, bộ phận, hệ thống khác trao đổi
  thông tin với hệ thống. Thứ tự trong `elements` = thứ tự xếp vòng theo chiều kim đồng hồ từ đỉnh.
- Luồng `{"from", "to", "label": "Đơn đặt hàng"}` — **danh từ** chỉ dữ liệu / chứng từ / thông tin (không phải
  hành động), mỗi luồng **có tên** và **một đầu là hệ thống trung tâm** (B2). Nhiều luồng cùng chiều giữa một cặp
  được gộp vào 1 mũi tên nhiều dòng; hai chiều → 2 mũi tên song song.
- Mỗi thực thể ngoài có ít nhất 1 luồng (B3). Luồng giữa hai thực thể ngoài nằm ngoài phạm vi – bỏ.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/bctx_<ten>.json -o ./uml/bctx_<ten>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/bctx_<ten>.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/bctx_<ten>.drawio -o ./uml/bctx_<ten>.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** (B1–B3) trong spec rồi chạy lại.
3. **Mở ảnh** `./uml/bctx_<ten>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: nhãn đọc được, không đè đường
   hay hình.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/bctx_<ten>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do.
