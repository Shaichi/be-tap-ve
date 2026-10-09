---
name: uml-screenflow
description: Vẽ screen flow theo vai trò ra draw.io – cột trái màn hình công khai (Login, Password Reset, User Profile), nhóm "Post-Login" nét đứt chứa các dashboard theo vai trò xếp dọc, mỗi dashboard toả một dải màn hình sang phải (List → Detail thẳng hàng, popup hình ellipse), màu theo vai trò, mũi tên đặc góc vuông không nhãn, không khung – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-screenflow hoặc cần sơ đồ luồng màn hình / điều hướng giao diện.
argument-hint: "<hệ thống / các vai trò + chức năng cần vẽ sơ đồ màn hình>"
user-invocable: true
---

# Vẽ screen flow theo vai trò (`/uml-screenflow`)

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
- `<ENGINE>/examples/lms_screenflow_roles.json` — **khuôn chuẩn**: Login → nhóm `Post-Login` chứa Admin /
  Manager / Class Dashboard; dải Admin treo lên trên trục, dải Manager treo xuống dưới, Class Dashboard có màn
  ghép nhiều tab, nhánh học sinh màu hồng, liên kết chéo tự đi đường vòng.
- `<ENGINE>/references/spec-format.md` — mục *Screen flow*; `<ENGINE>/references/uml-notation.md` — mục *Screen
  flow*.
- Hệ thống không có đăng nhập / vai trò → dạng cây site map cũ: `<ENGINE>/examples/lms_screenflow_sitemap.json`
  (không khai `group`).

## 2. Bố cục được vẽ
```
 [Password Change]◄─┐
 [User Profile] ◄───┤ (cạnh trên nhóm)          hàng "up":  [Detail]  [Detail]
                    │                                         ▲         ▲
 [User Login] ──►┌──┴── Post-Login ──┐                     [List]    [List]   [Audit Log]
 [Password Reset]│ [Admin Dashboard] ├──────────────────────┴─────────┴──────────┘   ← trục ngang
                 │                   │
                 │ [Manager Dashb.]  ├────────┬──────────┬────  ← hàng "down": con treo xuống
                 │                   │     [List]──►[Detail]   [List]
 [Public ...] ◄──┤ [Class Dashboard] │                         [Detail]
                 └───────────────────┘
```
- **Cột trái:** màn hình công khai (gốc `root`, vd User Login; con của nó xếp dọc), con của nhóm (User Profile,
  Password Change…) và con `"side": "left"` của dashboard (vd Public Credit Packages – đặt ngang dashboard).
- **Nhóm** (`"type": "group"`, vd `Post-Login`): khung nét đứt nền xám, các dashboard khai `"in": "<id nhóm>"`
  xếp dọc bên trong theo thứ tự spec. Mũi tên Login → nhóm vào cạnh trái nhóm.
- **Dải của mỗi dashboard:** trục ngang đi ra từ cạnh phải dashboard; con `"side": "up"` treo phía trên trục,
  `"down"` phía dưới (không ghi → tự chia đều hai hàng). Từ mỗi con đi tiếp ra xa trục: 1 con → thẳng hàng
  (List → Detail), nhiều con → lược, `"side": "right"` / `"left"` → cùng hàng bên cạnh.

## 3. Quy tắc spec
- `"diagram": "screenflow"`, `"title"`, `"root": "login"`, `"roles": {"admin": "orange", "manager": "purple",
  "teacher": "green", "student": "pink"}` (bảng màu: orange, purple, green, pink, blue, yellow, red, grey; hoặc
  `"#rrggbb"`, hoặc `{"fill", "stroke"}`; role chưa khai → tự cấp màu).
- Nút: `screen` (chữ nhật) và `popup` (ellipse – tạo mới, xác nhận, đổi mật khẩu, xem nhanh…), mỗi nút **chỉ có
  `name`** + tuỳ chọn:
  - `"role"` – màu theo vai trò; **luôn ghi trên mỗi dashboard** (Admin cam, Manager tím, Teacher xanh lá,
    Student hồng như hình mẫu; quên ghi thì mỗi dashboard vẫn tự nhận một màu riêng). Màn khác không ghi → kế
    thừa màn cha trên cây điều hướng; ghi role khác khi màn đổi vai trò (vd nhánh học sinh trong Class
    Dashboard → `"student"`). Màn công khai / `"public"` → ô trắng viền đen (Login, Password Reset, User Profile…).
  - `"in": "<nhóm>"` – chỉ cho các dashboard sau đăng nhập.
  - `"highlight": true` – chữ đỏ (màn hình cần lưu ý / mới / thuộc phạm vi sprint).
  - `"tabs": ["Class Detail", "Students", ...]` – màn hình ghép: tên ở trên, các tab ô trắng bên trong.
- Relation chỉ `{"from", "to"}` (+ `"side"`, `"tree": false`). Cây lấy theo **thứ tự relations**: lần đầu một
  màn hình được trỏ tới là cạnh cây (quyết định vị trí); các cạnh còn lại là liên kết chéo, tự đi đường vòng tránh
  hình. `"tree": false` ép một relation thành liên kết chéo (vd Learning Material → Quiz Taking khi Quiz Taking
  thuộc chuỗi Quiz Practice Detail → Quiz Taking).
- Điều hướng tới một dashboard trong nhóm = vào nhóm; **không** cần relation nhóm → dashboard.
- **Không** dùng `initial` / `final` / `decision`, **không** `items`, mũi tên **không** `trigger` / `guard` /
  `label` (F2). Không khung, không tiêu đề trên hình (bật bằng `"frame": true` nếu người dùng muốn).
- Mọi màn hình phải tới được từ gốc (F1); chỉ 1 nhóm, `"in"` phải trỏ tới nhóm (F3). Dashboard / màn quản trị
  chỉ tới được qua Login (`--profile sep490` báo P10).

## 4. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/sf_<ten>.json -o ./uml/sf_<ten>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/sf_<ten>.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/sf_<ten>.drawio -o ./uml/sf_<ten>.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** và **0 WARN** (mã thoát 2 = còn lỗi: sửa spec,
   chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** (F1, F2, F3) trong spec rồi chạy lại.
3. **Mở ảnh** `./uml/sf_<ten>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: Detail thẳng hàng List, dải
  đặt đúng phía (chỉnh `side`), màu đúng vai trò, không hình/đường chồng nhau.

## 5. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/sf_<ten>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do.
