---
name: uml-component
description: Vẽ component diagram UML theo thiết kế COMET (Gomaa) ra draw.io – component/subsystem lồng nhau, interface cung cấp (lollipop) và yêu cầu («use») – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-component hoặc cần sơ đồ thành phần/kiến trúc component.
argument-hint: "<hệ thống + các component/subsystem và interface>"
user-invocable: true
---

# Vẽ component diagram (`/uml-component`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; thiếu hẳn
thông tin cốt lõi thì hỏi lại một câu ngắn rồi mới vẽ.

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
- `<ENGINE>/examples/banking_component.json` — khuôn chuẩn (subsystem chứa component, interface lollipop,
  provides/requires/usage).
- `<ENGINE>/references/spec-format.md` — mục *Component diagram với provided/required interface*;
  `<ENGINE>/references/comet-method.md` — mục 8 (thiết kế).
- Spec đã có của cùng hệ thống (vd `./uml/*.json`) → tên subsystem/lớp dùng y hệt.

## 2. Quy tắc (UML 2.5 + thiết kế COMET)
- `"diagram": "component"`, `"title"`.
- Component `{"type": "component", "stereotype": …}`, component con lồng bằng `"in": "<id cha>"`.
  - Subsystem: `client subsystem`, `service subsystem`, `coordinator subsystem`, `control subsystem`,
    `user interaction subsystem`, `input subsystem`, `output subsystem`, `I/O subsystem`,
    `system services subsystem`.
  - Component bên trong theo nhóm đối tượng COMET: `state dependent control`, `coordinator`, `business logic`,
    `database wrapper`, `input`, `output`, `user interaction`.
- Interface **cung cấp**: `{"type": "interface", "name": "IOrderService", "notation": "lollipop"}` +
  `{"type": "provides", "from": "<component>", "to": "<interface>"}` (nét liền tới ball).
- Interface **yêu cầu**: `{"type": "requires", "from": "<component dùng>", "to": "<interface>"}` (nét đứt «use»).
  Mỗi interface được `requires` phải có một component `provides`.
- Phụ thuộc trực tiếp component → component: `usage`. Tránh phụ thuộc vòng.
- Tên interface: `I` + danh từ dịch vụ; tên component/subsystem khớp package/deployment diagram.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/component.json -o ./uml/component.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/component.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/component.drawio -o ./uml/component.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại); WARN
   về quan hệ vượt biên container / phần tử không tồn tại → sửa spec.
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó không
   đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng.
3. **Mở ảnh** `./uml/component.png` bằng công cụ đọc file (xem như ảnh) và tự soát: component con nằm trọn trong
   subsystem, ball + nhãn interface đọc được, mũi tên «use» chỉ vào interface.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/component.drawio` (+ `component.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
