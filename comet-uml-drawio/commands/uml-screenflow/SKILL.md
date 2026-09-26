---
name: uml-screenflow
description: Vẽ screen flow dạng sơ đồ trang (site map) ra draw.io – cây điều hướng toàn hệ thống từ Home, ô chữ nhật chỉ ghi tên màn hình, popup/modal bo góc, mũi tên mở không nhãn bẻ góc bo tròn, không khung – bố cục cây tự động không chồng hình. Dùng khi người dùng gọi /uml-screenflow hoặc cần sơ đồ luồng màn hình / điều hướng giao diện.
argument-hint: "<hệ thống / nhóm chức năng cần vẽ sơ đồ màn hình>"
user-invocable: true
---

# Vẽ screen flow – sơ đồ trang / site map (`/uml-screenflow`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; chưa rõ
hệ thống nào thì hỏi lại một câu ngắn rồi mới vẽ.

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
- `<ENGINE>/examples/lms_screenflow_sitemap.json` — khuôn chuẩn duy nhất: cây điều hướng từ Home, List → Details
  → Edit, Add ở hàng dưới, popup đăng nhập bên trái, nhánh toả từ cạnh phải.
- `<ENGINE>/references/spec-format.md` — mục *Screen flow*; `<ENGINE>/references/uml-notation.md` — mục *Screen
  flow*.
- Có use case / danh sách chức năng → mỗi chức năng thường là một màn hình danh sách (List) + chi tiết (Details)
  + thêm/sửa (Add / Edit).

## 2. Quy tắc
- `"diagram": "screenflow"`, `"title"`, `"root": "home"` (gốc cây; mặc định nút đầu tiên không có mũi tên vào).
- Chỉ có 2 loại nút: `screen` (ô chữ nhật) và `popup` (ô bo góc – đăng nhập, đăng ký, xác nhận, import...). Mỗi
  nút **chỉ có `name`** – tên màn hình ngắn, kiểu `Course Lists`, `Course Details`, `Add Post`.
- **Không** dùng `initial` / `final` / `decision`, **không** `items`, mũi tên **không** `trigger` / `guard` /
  `label` (F2 – nếu có sẽ bị bỏ qua kèm cảnh báo). Không khung, không tiêu đề trên hình (bật lại bằng
  `"frame": true` nếu người dùng muốn).
- Relation chỉ `{"from", "to"}` (+ `side`). Cây lấy theo **thứ tự relations**: lần đầu một màn hình được trỏ tới
  là cạnh cây, các cạnh còn lại (vd. Course Details → Course Register) tự đi đường vòng tránh hình.
- Vị trí con so với cha – `"side"` trên relation (hoặc trên element con):
  `same` (cùng hàng, mũi tên ngang – mặc định cho con đầu tiên, vd. List → Details),
  `down` (hàng dưới, đi ra từ đáy cha – mặc định cho các con sau, vd. List → Add),
  `up` (hàng trên), `top` (ngay trên đầu cha, cùng cột, vd. Home → User Profile), `left` (cột bên trái; ghép được
  `left-up`, `left-down`, vd. Home → User Login). Các con `down` của gốc đi chung **một trục dọc** từ đáy Home.
- `"branch": "side"` trên element cha → các con toả ra từ **cạnh phải** (up/same/down) thay vì từ đáy
  (vd. Subject Details → Dimension / Price / Lessons).
- Mọi màn hình phải tới được từ gốc (F1).

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/sf_<ten>.json -o ./uml/sf_<ten>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/sf_<ten>.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/sf_<ten>.drawio -o ./uml/sf_<ten>.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** và **0 WARN** (mã thoát 2 = còn lỗi: sửa spec,
   chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** (F1, F2) trong spec rồi chạy lại.
3. **Mở ảnh** `./uml/sf_<ten>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: List–Details cùng hàng, nhánh
   đặt đúng phía (chỉnh `side` / `branch`), không hình/đường chồng nhau.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/sf_<ten>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do.
