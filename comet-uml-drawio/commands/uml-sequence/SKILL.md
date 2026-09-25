---
name: uml-sequence
description: Vẽ sequence diagram cho một use case theo COMET (Gomaa) ra draw.io – lifeline «boundary»/«control»/«entity», message sync/async/reply, fragment alt/opt/loop – bố cục tự động, message luôn nằm ngang, không chồng hình. Dùng khi người dùng gọi /uml-sequence hoặc cần sơ đồ tuần tự của một use case.
argument-hint: "<tên use case + luồng chính/thay thế>"
user-invocable: true
---

# Vẽ sequence diagram cho một use case (`/uml-sequence`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; chưa rõ
use case nào hoặc luồng chính của nó thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/atm_seq_validate_pin.json` — khuôn chuẩn (message sync/async/reply + fragment `alt`).
- `<ENGINE>/examples/atm_comm_validate_pin.json` — cùng use case ở dạng communication: thấy hai sơ đồ khớp nhau
  từng message (R12).
- `<ENGINE>/references/spec-format.md` — mục *Message*, *Fragment*; `<ENGINE>/references/uml-notation.md` — mục
  *Message trong sequence diagram*.
- Spec đã có của cùng hệ thống (vd `./uml/*.json`) → dùng lại **đúng** tên use case, actor, lớp, message.

## 2. Quy tắc (UML 2.5 + COMET)
- `"diagram": "sequence"`, `"useCase"` = tên use case **y hệt** use case model (R1), `"title"`.
- Phần tử như communication: actor (`"side": "right"` cho actor phụ / hệ thống ngoài), đối tượng
  `{"type": "object", "class": …, "stereotype": …}` (boundary `user interaction`/`input`/`output`/`proxy`, control
  `state dependent control`/`coordinator`, `business logic`, `entity`).
- **Khai báo mọi bên tham gia**, kể cả hệ thống ngoài phía sau `proxy` (vd Payment Gateway, Bank Server) — thiếu
  thì proxy không nói chuyện với ai (R13).
- `messages[]`: thứ tự trong mảng = thứ tự từ trên xuống. Mỗi message có `"id"` (vd `"m1"`), `"seq"`, `"name"`,
  `"type"`:
  - `async` (mũi tên mở) — sự kiện giữa actor/đối tượng chạy đồng thời (mặc định COMET cho message sự kiện);
  - `sync` (tam giác đặc) — gọi và chờ: tới entity, tới proxy / hệ thống ngoài;
  - `reply` (nét đứt) — kết quả của một `sync` (ghi tên dữ liệu trả về, vd "Valid PIN");
  - `create` — tạo đối tượng mới.
- Luật COMET: actor ↔ boundary (R3), mỗi boundary ↔ ≥ 1 actor (R13), entity thụ động (R6), có
  `state dependent control` → có statechart và event/action khớp message (R7/R8).
- Cùng use case có communication diagram → **cùng tập message**: cùng tên, cùng cặp gửi/nhận, cùng `seq` (R12).
- **Nhánh thay thế / lặp / tuỳ chọn** dùng `"fragments"` tham chiếu `id` message:
  `{"type": "alt", "operands": [{"guard": "PIN valid", "from": "m13", "to": "m16"}, {"guard": "else", "from": "m13a", "to": "m16a"}]}`;
  cũng có `opt`, `loop` (`"guard"` hoặc `"label": "loop [1..3]"`), `par`, `break`. Mọi nhánh lỗi chính của use case
  (thanh toán thất bại, PIN sai, hết hàng…) phải có operand riêng; message nhánh thay thế đánh số hậu tố chữ
  (`13a`) và đặt **sau** các message nhánh chính trong mảng.
- Lifeline không gạch chân (UML 2.x) và message luôn nằm ngang — script tự vẽ; không khai báo `relations`.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/seq_<use-case>.json -o ./uml/seq_<use-case>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/seq_<use-case>.json [spec liên quan…]
python "<ENGINE>/scripts/preview_svg.py" ./uml/seq_<use-case>.drawio -o ./uml/seq_<use-case>.html --png
```
`[spec liên quan…]` = các spec đã có: communication cùng use case (R12), use case model (R1/R2), entity class model
(R5), statechart của lớp control (R8). Glob kiểu `"./uml/*.json"` được script tự mở rộng (cả trên PowerShell).
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó không
   đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng. Không biện minh kiểu "chỉ là cảnh báo nhỏ".
3. **Mở ảnh** `./uml/seq_<use-case>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: chữ đọc được, fragment bao
   đúng message, đầu mũi tên đúng loại (sync đặc, async mở, reply nét đứt).

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/seq_<use-case>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
