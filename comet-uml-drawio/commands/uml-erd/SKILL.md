---
name: uml-erd
description: Vẽ ERD (sơ đồ thực thể – quan hệ, ký pháp chân chim / crow's foot) ra draw.io – entity có cột khoá PK/FK, relationship có cardinality 2 đầu (1, 0..1, 1..*, 0..*), identifying / non-identifying – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-erd hoặc cần thiết kế cơ sở dữ liệu / mô hình dữ liệu.
argument-hint: "<miền nghiệp vụ / danh sách bảng cần mô hình hoá>"
user-invocable: true
---

# Vẽ ERD – sơ đồ thực thể quan hệ (`/uml-erd`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; chưa rõ
miền dữ liệu nào thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/banking_erd.json` — khuôn chuẩn (khoá chính, khoá ngoại, khoá kép PK,FK ở bảng trung gian,
  quan hệ non-identifying).
- `<ENGINE>/references/spec-format.md` — mục *ERD*; `<ENGINE>/references/uml-notation.md` — mục *ERD – ký pháp
  chân chim*.
- Class diagram «entity» đã có (vd `./uml/*class*.json`) → dùng lại tên lớp làm tên bảng, thuộc tính làm cột.

## 2. Quy tắc
- `"diagram": "erd"`, `"title"`. Mỗi bảng: `{"id", "type": "entity", "name", "attributes": [...]}`; bảng yếu
  (weak entity) thêm `"weak": true`.
- Thuộc tính: chuỗi `"PK maKH: INT"`, `"FK maTK: CHAR(12)"`, `"PK,FK x: INT"`, `"ten: VARCHAR(80)"` — hoặc object
  `{"name", "type", "key": "PK" | "FK" | "PK,FK" | "UK"}`. **Mỗi entity có khoá chính** (E1).
- Quan hệ `{"type": "relationship", "from", "to", "fromCard", "toCard", "label"}`:
  - cardinality mỗi đầu: `"1"` (đúng một), `"0..1"`, `"1..*"` (một hoặc nhiều), `"0..*"` (không hoặc nhiều) —
    **đủ cả 2 đầu** (E2); `label` là động từ đọc từ `from` sang `to` ("places", "đặt").
  - `"identifying": false` → nét đứt (khoá ngoại không nằm trong khoá chính của bảng con).
  - `"showCard": true` → ghi thêm chữ cardinality cạnh chân chim.
- Bảng con (phía "nhiều") giữ **FK** trỏ về khoá chính bảng cha.
- Nhiều–nhiều (`0..*` ↔ `0..*`) chỉ để ở mức khái niệm; mức logic/vật lý tách thành bảng trung gian có khoá kép
  `PK,FK` + 2 quan hệ 1–nhiều (E3).

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/erd_<ten>.json -o ./uml/erd_<ten>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/erd_<ten>.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/erd_<ten>.drawio -o ./uml/erd_<ten>.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** (E1–E3) trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó
   không đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng.
3. **Mở ảnh** `./uml/erd_<ten>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: chân chim đúng đầu "nhiều",
   cột PK gạch chân, không hình/nhãn chồng nhau.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/erd_<ten>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do.
