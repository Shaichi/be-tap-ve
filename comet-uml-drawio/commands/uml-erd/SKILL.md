---
name: uml-erd
description: Vẽ ERD (sơ đồ thực thể – quan hệ) ký pháp Chen ra draw.io – thực thể là ô chữ nhật chỉ ghi tên, quan hệ là hình thoi có tên, bản số 1 / N / M ở đầu nối phía thực thể, quan hệ đệ quy và bậc 3 – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-erd hoặc cần mô hình dữ liệu mức khái niệm.
argument-hint: "<miền nghiệp vụ / danh sách thực thể cần mô hình hoá>"
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

**Ngôn ngữ trên sơ đồ: mặc định tiếng Anh.** Mọi chữ hiện trên sơ đồ (`title`, tên phần tử, thuộc tính, thao
tác, nhãn quan hệ, message, guard, câu hỏi decision…) viết bằng tiếng Anh, kể cả khi người dùng mô tả bằng tiếng
Việt – tự dịch sang thuật ngữ tiếng Anh chuẩn. Chỉ dùng ngôn ngữ khác khi người dùng yêu cầu rõ (vd "vẽ bằng
tiếng Việt") → đặt `"lang": "vi"` trong spec (không đặt thì `comet_check` báo L1). Trả lời người dùng vẫn
bằng ngôn ngữ của họ.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/elearn_erd.json` — khuôn chuẩn (23 thực thể, quan hệ 1–1 / 1–N / M–N, quan hệ đệ quy
  Comment –replies– Comment).
- `<ENGINE>/references/spec-format.md` — mục *ERD*; `<ENGINE>/references/uml-notation.md` — mục *ERD – ký pháp
  Chen*.
- Class diagram «entity» đã có (vd `./uml/*class*.json`) → dùng lại tên lớp làm tên thực thể.

## 2. Quy tắc
- `"diagram": "erd"`, `"title"`. Thực thể: `{"id", "type": "entity", "name"}` → ô chữ nhật tên in đậm, **không
  liệt kê thuộc tính** (có `attributes` sẽ bị bỏ qua kèm cảnh báo); thực thể yếu thêm `"weak": true` (viền kép).
- Quan hệ: `{"from", "to", "name": "has_role", "fromCard": "M", "toCard": "N"}` → script tự đặt **hình thoi** ghi
  `name` giữa 2 thực thể, nối bằng đường liền không mũi tên; `fromCard` ghi cạnh `from`, `toCard` cạnh `to`.
  - Bản số: `1`, `N`, `M` (1–1, 1–N, M–N) — **đủ cả 2 đầu** (E2).
  - `name`: động từ / `has_xxx` đọc từ `from` sang `to` — **bắt buộc** vì là chữ trong hình thoi (E3).
  - Hình thoi viền kép (quan hệ xác định của thực thể yếu): thêm `"identifying": true`.
- Quan hệ đệ quy: `from` = `to` (vd Comment `replies` Comment, `1`–`N`).
- Quan hệ bậc 3+: khai báo hình thoi là phần tử `{"id": "r", "type": "relationship", "name": "enrolls"}` rồi nối
  từng thực thể `{"from": "student", "to": "r", "card": "N"}`.
- Không khung, không tiêu đề (bật lại bằng `"frame": true`).

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/erd_<ten>.json -o ./uml/erd_<ten>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/erd_<ten>.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/erd_<ten>.drawio -o ./uml/erd_<ten>.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** (E1–E3) trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó
   không đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng.
3. **Mở ảnh** `./uml/erd_<ten>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: mỗi quan hệ có hình thoi ghi tên,
   bản số đúng phía thực thể, không hình/nhãn chồng nhau.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/erd_<ten>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do.
