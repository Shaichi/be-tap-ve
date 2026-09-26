---
name: uml-communication
description: Vẽ communication diagram (collaboration) cho một use case theo COMET (Gomaa) ra draw.io – đối tượng «boundary»/«control»/«entity», message đánh số – bố cục cột tự động không chồng hình. Dùng khi người dùng gọi /uml-communication hoặc cần sơ đồ giao tiếp/cộng tác của một use case.
argument-hint: "<tên use case + mô tả luồng chính/thay thế>"
user-invocable: true
---

# Vẽ communication diagram cho một use case (`/uml-communication`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; chưa rõ
use case nào hoặc luồng chính của nó thì hỏi lại một câu ngắn rồi mới vẽ.

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
- `<ENGINE>/examples/atm_comm_validate_pin.json` — khuôn chuẩn: chép cấu trúc, thay nội dung.
- `<ENGINE>/references/comet-method.md` — mục 2 (stereotype), 5 (R1–R14), 6 (quy ước message).
- `<ENGINE>/references/spec-format.md` — mục *Phần tử* (`actor`, `object`), *Message*.
- Spec đã có của cùng hệ thống (use case model, entity class model, sequence/statechart; vd `./uml/*.json`) → dùng
  lại **đúng** tên use case, actor, lớp, message.

## 2. Quy tắc (COMET – dynamic interaction modeling)
- **Một** communication diagram cho **một** use case: `"diagram": "communication"`, `"useCase"` = tên use case
  **y hệt** use case model (R1), `"title"`.
- Phần tử:
  - Actor chính `{"type": "actor", "name": …}` — cùng tên use case model (R2). Actor phụ / hệ thống ngoài: thêm
    `"side": "right"` (cột cuối).
  - Đối tượng `{"type": "object", "class": "Tên Lớp", "stereotype": …}` — ẩn danh `:Tên Lớp` (chỉ thêm `"name"`
    khi cần phân biệt 2 thể hiện cùng lớp). Đối tượng «entity» dùng **đúng tên lớp** của entity class model (R5).
  - Stereotype (R4): boundary `user interaction` (actor người), `input` / `output` / `I/O` (thiết bị), `proxy`
    (hệ thống ngoài); control `state dependent control` / `coordinator` / `timer`; application logic
    `business logic` / `algorithm` / `service`; `entity`.
- Luật tương tác:
  - Actor **chỉ** trao đổi message với đối tượng boundary (R3); mỗi boundary nói chuyện với ≥ 1 actor (R13) —
    `proxy` ↔ actor hệ thống ngoài mà nó đại diện (khai báo actor đó, `"side": "right"`).
  - Entity **thụ động**: chỉ nhận yêu cầu và trả dữ liệu, không tự khởi phát message (R6).
  - Có đối tượng `state dependent control` → bắt buộc có statechart ([/uml-statechart](../uml-statechart/SKILL.md),
    R7): message **đến** nó = event, message **đi** từ nó = action, tên y hệt (R8).
- Message `{"seq": "1", "from": …, "to": …, "name": …}`:
  - đánh số theo luồng chính `1, 2, 3…`; luồng thay thế thêm hậu tố chữ `13a, 14a…`; lồng nhau `1.1, 1.2`;
  - tên là sự kiện/dữ liệu ("Card Inserted", "PIN Entered", "Valid PIN") — actor → boundary là input thô ("Card
    Reader Input"), boundary → control là sự kiện ("Card Inserted");
  - truy cập entity = 2 message: yêu cầu ("Card Request") + dữ liệu trả về ("Card Data");
  - cùng use case đã/sẽ có sequence diagram → **cùng tập message**: cùng tên, cùng cặp gửi/nhận, cùng `seq` (R12).
- Không khai báo `relations`: link tự sinh từ messages, message cùng cặp đối tượng gộp trên 1 link.
- Cột tự xếp theo COMET: actor chính | boundary | control | application logic | entity | actor phụ.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/comm_<use-case>.json -o ./uml/comm_<use-case>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/comm_<use-case>.json [spec liên quan…]
python "<ENGINE>/scripts/preview_svg.py" ./uml/comm_<use-case>.drawio -o ./uml/comm_<use-case>.html --png
```
`[spec liên quan…]` = các spec đã có: use case model (R1/R2), entity class model (R5), sequence cùng use case (R12),
statechart của lớp control (R8). Glob kiểu `"./uml/*.json"` được script tự mở rộng (cả trên PowerShell).
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó không
   đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng. Không biện minh kiểu "chỉ là cảnh báo nhỏ".
3. **Mở ảnh** `./uml/comm_<use-case>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: chữ đọc được, không
   hình/nhãn chồng nhau, số thứ tự message liên tục, mũi tên message đúng chiều.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/comm_<use-case>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
