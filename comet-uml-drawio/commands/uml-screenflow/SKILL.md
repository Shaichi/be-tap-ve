---
name: uml-screenflow
description: Vẽ screen flow (luồng màn hình / điều hướng giao diện) ra draw.io – mỗi màn hình là khung có tiêu đề + danh sách thành phần, dialog/popup nét đứt, mũi tên điều hướng ghi thao tác kích hoạt [điều kiện], decision có câu hỏi – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-screenflow hoặc cần thiết kế luồng giao diện cho use case.
argument-hint: "<use case / chức năng cần thiết kế luồng màn hình>"
user-invocable: true
---

# Vẽ screen flow – luồng màn hình (`/uml-screenflow`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; chưa rõ
chức năng nào thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/atm_screenflow.json` — khuôn chuẩn (màn hình, dialog lỗi, quay lại, decision "Đủ số dư?").
- `<ENGINE>/references/spec-format.md` — mục *Screen flow*; `<ENGINE>/references/uml-notation.md` — mục *Screen
  flow*.
- Use case / activity diagram đã có → mỗi bước tương tác của actor thường là một màn hình hoặc một nút bấm.

## 2. Quy tắc
- `"diagram": "screenflow"`, `"title"`, tuỳ chọn `"useCase"`, `"direction": "LR"` (mặc định) hoặc `"TB"`.
- Nút: `initial` (điểm vào), `screen` / `page` (màn hình), `dialog` / `popup` (hộp thoại: nền vàng, nét đứt,
  «dialog»), `decision` với `"question": "Đủ số dư?"` (điều kiện hệ thống quyết định màn tiếp theo), `final`.
- Màn hình: `"name"` + `"items": ["Ô nhập PIN", "[Xác nhận]  [Huỷ]"]` — liệt kê thành phần chính; nút bấm viết
  trong `[ ]`. Không vẽ chi tiết pixel (đó là wireframe, không phải screen flow).
- Điều hướng `{"type": "navigate", "from", "to", "trigger": "Nhấn Xác nhận", "guard": "PIN đúng"}` → nhãn
  `trigger [guard]`. Mỗi điều hướng từ màn hình **nên có** trigger (F2); nhánh ra khỏi decision có guard ("Có" /
  "Không").
- Mọi màn hình phải tới được từ điểm bắt đầu (F1); có đường quay lại / thoát cho dialog lỗi.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/sf_<ten>.json -o ./uml/sf_<ten>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/sf_<ten>.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/sf_<ten>.drawio -o ./uml/sf_<ten>.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** (F1) trong spec rồi chạy lại; INFO F2 nên sửa nếu thiếu trigger.
3. **Mở ảnh** `./uml/sf_<ten>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: nhãn điều hướng đọc được,
   không hình/nhãn chồng nhau.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/sf_<ten>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do.
