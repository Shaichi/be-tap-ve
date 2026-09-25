---
name: uml-package
description: Vẽ package diagram UML / kiến trúc subsystem theo COMET (Gomaa) ra draw.io – package/subsystem chứa lớp, phụ thuộc «use»/«import» giữa package – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-package hoặc cần sơ đồ gói / phân rã subsystem.
argument-hint: "<hệ thống + các package/subsystem và lớp bên trong>"
user-invocable: true
---

# Vẽ package diagram – kiến trúc subsystem (`/uml-package`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; thiếu hẳn
thông tin cốt lõi thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/banking_package.json` — khuôn chuẩn (package «subsystem» chứa lớp COMET, dependency có
  stereotype, generalization giữa lớp).
- `<ENGINE>/references/spec-format.md` — mục *Phần tử* (`package`, `subsystem`, `in`), *Quan hệ* (`dependency`);
  `<ENGINE>/references/comet-method.md` — mục 8 (subsystem).
- Spec đã có của cùng hệ thống (vd `./uml/*.json`) → tên lớp/subsystem dùng y hệt.

## 2. Quy tắc (UML 2.5 + thiết kế COMET)
- `"diagram": "package"`, `"title"`.
- Package / subsystem: `{"type": "package", "stereotype": "subsystem"}` (hoặc stereotype COMET cụ thể:
  `client subsystem`, `service subsystem`, `control subsystem`, `coordinator subsystem`,
  `user interaction subsystem`, `input subsystem`, `output subsystem`, `I/O subsystem`); phần tử con (lớp, package
  con) khai báo `"in": "<id package>"`.
- Lớp trong package giữ stereotype COMET (`entity`, `state dependent control`, `coordinator`, `input`…) và **đúng
  tên** ở các sơ đồ khác.
- Phụ thuộc giữa package: `{"type": "dependency", "from": "<package dùng>", "to": "<package được dùng>",
  "stereotype": "use" | "import" | "access"}`; không tạo phụ thuộc vòng (phân tầng rõ ràng).
- Quan hệ giữa lớp ở hai package khác nhau (generalization, association…) được phép; script tự định tuyến qua biên
  package.

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/package.json -o ./uml/package.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/package.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/package.drawio -o ./uml/package.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó không
   đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng.
3. **Mở ảnh** `./uml/package.png` bằng công cụ đọc file (xem như ảnh) và tự soát: lớp nằm trọn trong package, tab tên
   package đọc được, mũi tên phụ thuộc đúng chiều.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/package.drawio` (+ `package.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
