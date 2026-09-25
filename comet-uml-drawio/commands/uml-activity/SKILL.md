---
name: uml-activity
description: Vẽ activity diagram UML có swimlane (partition) ra draw.io – action, decision/merge có guard, fork/join, initial/final đúng ngữ nghĩa UML 2.5 – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-activity hoặc cần sơ đồ hoạt động cho use case / quy trình nghiệp vụ.
argument-hint: "<use case / quy trình + các bên tham gia (làn)>"
user-invocable: true
---

# Vẽ activity diagram có swimlane (`/uml-activity`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; chưa rõ
quy trình nào thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/atm_activity_withdraw.json` — khuôn chuẩn (3 làn, decision + merge, fork/join, vòng lặp nhập
  lại PIN).
- `<ENGINE>/references/spec-format.md` — mục *Activity diagram có swimlane*; `<ENGINE>/references/uml-notation.md` —
  mục *Activity diagram – quy tắc hợp lệ*.
- Use case model đã có (vd `./uml/*.json`) → tên use case / actor dùng y hệt.

## 2. Quy tắc (UML 2.5)
- `"diagram": "activity"`, `"title"`, tuỳ chọn `"useCase"` (tên use case y hệt use case model).
- Swimlane: `"partitions": ["Customer", "System", "Payment Gateway"]` (thứ tự = thứ tự làn) + mỗi phần tử có
  `"partition"`. Mỗi action nằm trong làn của bên **thực hiện** nó.
- Nút: `initial` (đúng 1, không luồng vào, 1 luồng ra), `action` (động từ + bổ ngữ: "Enter PIN", "Validate Order"),
  `decision` (1 vào, ≥ 2 ra), `merge` (≥ 2 vào, 1 ra), `fork` / `join` (song song), `activityFinal` (kết thúc cả
  activity), `flowFinal` (kết thúc một luồng).
- Luồng `{"type": "flow", "from", "to"}`; luồng ra khỏi `decision` **luôn có** `"guard"` (tối đa một `"else"`) — A1;
  luồng thường không có guard.
- **Action có ≥ 2 luồng vào là sai ngữ nghĩa** (join ngầm: chờ đủ mọi luồng → nhánh rẽ từ decision sẽ kẹt): gộp
  nhánh bằng `merge` rồi mới vào action (A6). Action có ≥ 2 luồng ra = fork ngầm → dùng `decision` + guard, hoặc
  `fork`.
- Vòng lặp (thử lại, nhập lại): luồng quay lui về một `merge` đặt **trước** action cần lặp, không quay thẳng vào
  action.
- Fork/join cân nhau: mỗi nhánh của fork kết thúc ở join (hoặc flowFinal) (A2). Initial/final đúng số luồng (A3);
  không để action ngõ cụt (A5).

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/act_<ten>.json -o ./uml/act_<ten>.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/act_<ten>.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/act_<ten>.drawio -o ./uml/act_<ten>.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** (A1–A6) trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó
   không đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng. Không biện minh kiểu "chỉ là cảnh báo nhỏ".
3. **Mở ảnh** `./uml/act_<ten>.png` bằng công cụ đọc file (xem như ảnh) và tự soát: mỗi phần tử nằm đúng làn, guard
   đọc được, không hình/nhãn chồng nhau.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/act_<ten>.drawio` (+ `.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML" khi chưa chạy đủ 3 lệnh trên.
