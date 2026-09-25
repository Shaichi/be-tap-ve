---
name: uml-usecase
description: Vẽ use case diagram UML theo COMET (Gomaa) ra draw.io – actor, use case, «include»/«extend», system boundary – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-usecase hoặc chỉ cần vẽ riêng sơ đồ use case (mô hình yêu cầu).
argument-hint: "<hệ thống + chức năng/actor chính>"
user-invocable: true
---

# Vẽ use case diagram (`/uml-usecase`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; thiếu hẳn
thông tin cốt lõi (hệ thống làm gì, ai dùng) thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/atm_usecase.json` — khuôn chuẩn: chép cấu trúc, thay nội dung.
- `<ENGINE>/references/spec-format.md` — mục *Trường cấp cao* (`system`), *Phần tử* (`actor`, `usecase`),
  *Quan hệ* (`association`, `include`, `extend`).
- `<ENGINE>/references/comet-method.md` — mục 3–4 (actor, use case model).
- Spec đã có của cùng hệ thống (vd `./uml/*.json`) → dùng lại **đúng** tên actor/use case.

## 2. Quy tắc (UML 2.5 + COMET)
- `"diagram": "usecase"`, `"system"`: tên hệ thống (nhãn khung system boundary), `"title"`.
- **Use case** = một chuỗi tương tác hoàn chỉnh mang lại giá trị cho actor; tên *động từ + danh từ*, viết hoa chữ
  đầu mỗi từ ("Withdraw Funds", "Place Order"). Không tách từng bước / màn hình / thao tác lẻ thành use case
  (phân rã chức năng).
- **Actor** nằm ngoài hệ thống: người dùng, hệ thống ngoài, thiết bị vào/ra, timer (use case chạy định kỳ có actor
  timer, vd "Clock"). Stereotype tuỳ chọn: `human actor`, `system actor`, `input device actor`,
  `output device actor`, `I/O device actor`, `timer actor`.
- **Association** actor – use case (nét liền, không mũi tên):
  - actor chính (khởi tạo use case): `"from"` actor → `"to"` use case (tự xếp bên trái);
  - actor phụ / hệ thống ngoài tham gia: `"from"` use case → `"to"` actor, actor đặt `"side": "right"`.
- **«include»**: `"from"` use case cơ sở → `"to"` use case được bao gồm (đoạn chung dùng lại ở ≥ 2 use case).
  **«extend»**: `"from"` use case mở rộng → `"to"` use case cơ sở, kèm `"condition"`. Không dùng include/extend để
  diễn tả thứ tự các bước.
- Không nối use case – use case bằng association; không nối actor – actor (trừ `generalization` con → cha).
- Mỗi use case nối tới ≥ 1 actor, hoặc là đích của «include» / nguồn của «extend».
- Tên actor và use case ở đây là **tên chuẩn** cho mọi sơ đồ sau: `"useCase"` của communication/sequence và lớp ngoài
  của context diagram phải viết **y hệt**.
- Người dùng cần đặc tả use case → viết trong câu trả lời (không đưa vào spec) theo template Gomaa: Summary, Actors,
  Precondition, Main sequence, Alternative sequences, Postcondition.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/usecase.json -o ./uml/usecase.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/usecase.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/usecase.drawio -o ./uml/usecase.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó không
   đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng. Không biện minh kiểu "chỉ là cảnh báo nhỏ".
   (`--partial`: use case chưa có sơ đồ tương tác (R1) chỉ là INFO khi vẽ riêng sơ đồ này.)
3. **Mở ảnh** `./uml/usecase.png` bằng công cụ đọc file (xem như ảnh) và tự soát: chữ đọc được, không hình/nhãn
   chồng nhau, ký hiệu đúng mục 2. Không có Chrome/Edge thì script báo và bỏ qua ảnh → soát bằng `usecase.html`.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/usecase.drawio` (+ `usecase.png`); mở bằng draw.io desktop hoặc
  app.diagrams.net › File › Open.
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
- Bước tiếp theo theo COMET: [/uml-context](../uml-context/SKILL.md), [/uml-class](../uml-class/SKILL.md), rồi
  [/uml-communication](../uml-communication/SKILL.md) cho từng use case.
