---
name: uml-class
description: Vẽ class diagram UML – entity class model theo COMET (Gomaa) hoặc design class diagram – ra draw.io, thuộc tính có kiểu, association có tên + multiplicity, bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-class hoặc chỉ cần vẽ riêng sơ đồ lớp.
argument-hint: "<hệ thống hoặc danh sách lớp/quan hệ cần vẽ>"
user-invocable: true
---

# Vẽ class diagram – entity class model (`/uml-class`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; thiếu hẳn
thông tin cốt lõi thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/atm_entity.json` — khuôn chuẩn: chép cấu trúc, thay nội dung.
- `<ENGINE>/references/spec-format.md` — mục *Phần tử* (`class`, `enumeration`), *Quan hệ*.
- `<ENGINE>/references/uml-notation.md` — bảng *Quan hệ (edge)* và *Quy tắc trình bày*.
- Spec đã có của cùng hệ thống (vd `./uml/*.json`) → lớp entity phải trùng tên đối tượng «entity» trong sơ đồ
  tương tác (R5).

## 2. Quy tắc (entity class model – COMET, pha phân tích)
- `"diagram": "class"`, `"title"` (vd "Food Delivery System - Entity Class Model").
- Lớp: `{"type": "class", "stereotype": "entity", "attributes": [...]}` — dữ liệu lưu lâu dài (khách hàng, đơn hàng,
  tài khoản…). Tên lớp: danh từ số ít, viết hoa chữ đầu mỗi từ.
- **Thuộc tính luôn có kiểu** `"tên: Kiểu"` (camelCase: `"orderId: String"`, `"totalAmount: Real"`,
  `"createdAt: Date"`, `"isActive: Boolean"`) — C1. Tập giá trị cố định → phần tử `enumeration` + `literals`, dùng
  làm kiểu (`"status: OrderStatus"`).
- Pha phân tích: entity **không có operations** (R10). Chỉ khi người dùng yêu cầu *design class diagram* mới thêm
  `operations` dạng `"+ tên(thamSo: Kiểu): Kiểu"` và visibility `+ - # ~`.
- **Association**: `"label"` là động từ đọc theo chiều `from → to` ("Customer Places Order": from Customer, to
  Order, label "Places"); multiplicity **ở cả hai đầu** `"fromMult"`/`"toMult"` (`"1"`, `"0..1"`, `"0..*"`,
  `"1..*"`) — C2.
- **Composition** (bộ phận không tồn tại riêng, vd Order ◆– Order Item) / **aggregation** (bộ phận dùng chung):
  `"from"` = **toàn thể** → `"to"` = bộ phận, có multiplicity.
- **Generalization**: `"from"` lớp **con** → `"to"` lớp **cha**; lớp cha trừu tượng đặt `"abstract": true`; không
  đặt multiplicity/tên trên generalization.
- Không đưa lớp boundary/control (thuộc sơ đồ tương tác) vào entity class model.
- Thứ tự khai báo ảnh hưởng bố cục khi hoà: khai báo lớp trung tâm trước, các lớp liên quan ngay sau.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/class.json -o ./uml/class.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/class.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/class.drawio -o ./uml/class.html --png
```
(Đã có sơ đồ tương tác → thêm các spec đó vào lệnh 2 để kiểm R5.)
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** (C1 thuộc tính thiếu kiểu, C2 thiếu multiplicity, R10…) trong
   spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó không đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người
   dùng. Không biện minh kiểu "chỉ là cảnh báo nhỏ".
3. **Mở ảnh** `./uml/class.png` bằng công cụ đọc file (xem như ảnh) và tự soát: chữ đọc được, không hình/nhãn chồng
   nhau, thoi aggregation/composition ở phía toàn thể, tam giác generalization chỉ vào lớp cha.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/class.drawio` (+ `class.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
