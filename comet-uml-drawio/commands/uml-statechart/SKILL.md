---
name: uml-statechart
description: Vẽ statechart (state machine diagram) cho lớp «state dependent control» theo COMET (Gomaa) ra draw.io – event/action khớp message của sơ đồ tương tác, composite state, choice, history – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-statechart hoặc cần sơ đồ trạng thái.
argument-hint: "<lớp control + các trạng thái/sự kiện chính>"
user-invocable: true
---

# Vẽ statechart cho đối tượng state dependent control (`/uml-statechart`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; chưa rõ
statechart của lớp nào thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/atm_statechart.json` — khuôn chuẩn (statechart của ATM Control).
- `<ENGINE>/examples/atm_comm_validate_pin.json` — thấy message đến/đi từ `ATM Control` trở thành event/action.
- `<ENGINE>/references/comet-method.md` — mục 7 (statechart theo COMET); `<ENGINE>/references/spec-format.md` —
  mục *Phần tử* (`state`, `initial`, `final`, `choice`, `history`), *Quan hệ* (`transition`).
- Communication/sequence đã có (vd `./uml/*.json`) → lấy **đúng** tên lớp control và tên message.

## 2. Quy tắc (UML 2.5 + COMET)
- Một statechart cho **mỗi** lớp `state dependent control` (R7): `"diagram": "state"`, `"stateMachineOf"` = tên lớp
  **y hệt** thuộc tính `"class"` của đối tượng đó trong sơ đồ tương tác, `"title"`.
- Phần tử: `initial` (đúng 1 ở cấp ngoài cùng; 1 trong mỗi composite state có state con), `state` (tên = trạng
  thái chờ có ý nghĩa: "Idle", "Waiting for PIN", "Processing Payment"; `"activities": ["entry / X", "do / Y",
  "exit / Z"]`), composite state = state con khai báo `"in": "<id cha>"`, `final`, `choice`, `junction`,
  `history` / `deephistory`.
- Transition `{"type": "transition", "from", "to", "event", "guard", "action"}` (`action` là chuỗi hoặc mảng):
  - **event = message ĐẾN** đối tượng control trong sơ đồ tương tác; **action = message control GỬI ĐI** — tên y hệt
    (danh sách tham số được bỏ khi so khớp) (R8). Mỗi message control gửi đi phải là action trên một transition
    (hoặc entry/exit/do) — statechart không có action nào gần như chắc chắn thiếu.
  - Transition từ `initial` **không có event, không có guard** (chỉ có thể có action) — S1. Hệ thống chờ sự kiện
    đầu tiên → initial → state chờ ("Idle"), rồi `Idle --event / action--> …`.
  - `final` không có transition ra (S2). `choice`/`junction` có ≥ 2 nhánh ra: mọi nhánh có `guard`, tối đa một
    `"else"` (S3).
  - Mọi state tới được từ initial và có đường ra, trừ trạng thái kết thúc có chủ đích (S4).
  - Cùng state, cùng event mà nhiều transition → guard phải phân biệt (S5). Self-transition (`from == to`) được phép.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/stm_<lop-control>.json -o ./uml/stm_<lop-control>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/stm_<lop-control>.json [comm/seq liên quan…]
python "<ENGINE>/scripts/preview_svg.py" ./uml/stm_<lop-control>.drawio -o ./uml/stm_<lop-control>.html --png
```
Chạy comet_check **cùng** các spec communication/sequence có đối tượng control này để kiểm R8 hai chiều (event ⇄
message đến, action ⇄ message đi). Glob kiểu `"./uml/*.json"` được script tự mở rộng (cả trên PowerShell).
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR (S1/S2 là lỗi) và **sửa hết WARN** (R8, S3–S5…) trong spec rồi chạy lại. Chỉ giữ một
   WARN khi chắc chắn nó không đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng. INFO R8 "event chưa có
   message đến" chấp nhận được khi event thuộc use case chưa vẽ — liệt kê chúng cho người dùng.
3. **Mở ảnh** `./uml/stm_<lop-control>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: nhãn
   `Event [guard] / action` đọc được, không chồng nhau, initial chỉ có một mũi tên ra không nhãn event.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/stm_<lop-control>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
