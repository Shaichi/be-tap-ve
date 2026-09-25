---
name: uml-context
description: Vẽ software system context diagram theo COMET (Gomaa) ra draw.io – 1 lớp «software system» và các lớp «external …» với association có tên + multiplicity – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-context hoặc cần sơ đồ ngữ cảnh hệ thống.
argument-hint: "<hệ thống + các actor/thiết bị/hệ thống ngoài>"
user-invocable: true
---

# Vẽ software system context diagram (`/uml-context`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; thiếu hẳn
thông tin cốt lõi thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/atm_context.json` — khuôn chuẩn: chép cấu trúc, thay nội dung.
- `<ENGINE>/references/comet-method.md` — mục 3 (actor và context diagram).
- `<ENGINE>/references/spec-format.md` — mục *Phần tử* (`system`, `external`), *Quan hệ* (`association`).
- Use case model đã có (vd `./uml/usecase.json`, `./uml/01_usecase.json`) → mỗi actor phải có mặt ở đây.

## 2. Quy tắc (COMET – software system context class diagram)
- `"diagram": "context"`, `"title"`.
- **Đúng 1** phần tử `{"type": "system", "stereotype": "software system"}` = hệ thống đang xây (R11).
- Mỗi thực thể ngoài: `{"type": "external", "stereotype": ...}`, rút ra từ actor của use case model:

| Thực thể ngoài | `stereotype` | `label` association (chiều `from → to`) |
|---|---|---|
| Thiết bị chỉ đưa dữ liệu vào (cảm biến, bàn phím riêng) | `external input device` | "Inputs to" (thiết bị → hệ thống) |
| Thiết bị chỉ nhận dữ liệu ra (máy in, cash dispenser, đèn) | `external output device` | "Outputs to" (hệ thống → thiết bị) |
| Thiết bị vào/ra (card reader) | `external I/O device` | "Inputs to" / "Outputs to" theo chiều chính, hoặc "Interacts with" |
| Người dùng qua màn hình/bàn phím chuẩn | `external user` | "Interacts with" (người → hệ thống) |
| Hệ thống ngoài (cổng thanh toán, bank server, dịch vụ bên thứ ba) | `external system` | "Interacts with" |
| Đồng hồ / bộ định thời | `external timer` | "Awakens" (timer → hệ thống) |

- **Mọi association có `label`** (bảng trên) **và multiplicity ở cả hai đầu** (`"fromMult"`, `"toMult"`,
  vd `"1..*"` Customer – `"1"` hệ thống) (R11).
- Mọi actor của use case model xuất hiện với **cùng tên** (R14) — trừ người dùng chỉ tương tác qua thiết bị đã vẽ
  (vd ATM Customer dùng Card Reader, Cash Dispenser). Actor hệ thống ngoài → `external system`; actor timer →
  `external timer`.
- Không đưa lớp nội bộ (entity/boundary/control), use case, hay quan hệ giữa hai lớp ngoài vào context diagram.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/context.json -o ./uml/context.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/context.json ./uml/usecase.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/context.drawio -o ./uml/context.html --png
```
(Chưa có use case model thì bỏ `./uml/usecase.json` khỏi lệnh 2.)
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** trong spec rồi chạy lại; INFO R11/R14 (thiếu tên quan hệ,
   multiplicity, actor chưa có lớp ngoài) cũng sửa nốt. Chỉ giữ một WARN khi chắc chắn nó không đúng ngữ cảnh —
   khi đó nêu mã luật + lý do cho người dùng.
3. **Mở ảnh** `./uml/context.png` bằng công cụ đọc file (xem như ảnh) và tự soát: chữ đọc được, không hình/nhãn
   chồng nhau, nhãn quan hệ + multiplicity đủ. Không có Chrome/Edge thì soát bằng `context.html`.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/context.drawio` (+ `context.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
