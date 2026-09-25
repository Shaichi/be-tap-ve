---
name: uml-deployment
description: Vẽ deployment diagram UML theo thiết kế COMET (Gomaa) ra draw.io – node/device/execution environment chứa component và artifact, communication path có stereotype mạng + multiplicity – bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-deployment hoặc cần sơ đồ triển khai.
argument-hint: "<hệ thống + máy/thiết bị, mạng, thành phần triển khai>"
user-invocable: true
---

# Vẽ deployment diagram (`/uml-deployment`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; thiếu hẳn
thông tin cốt lõi thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

## 1. Đọc bắt buộc (chưa đọc xong thì chưa viết spec)
- `<ENGINE>/examples/atm_deployment.json` — khuôn chuẩn (node «device» + node server, component trong node,
  artifact, communication path «WAN» có multiplicity).
- `<ENGINE>/references/spec-format.md` — mục *Phần tử* (`node`, `device`, `executionEnvironment`, `artifact`),
  *Quan hệ* (`communicationpath`, `dependency`); `<ENGINE>/references/comet-method.md` — mục 8.
- Component/package diagram đã có (vd `./uml/*.json`) → tên subsystem/component dùng y hệt.

## 2. Quy tắc (UML 2.5 + thiết kế COMET)
- `"diagram": "deployment"`, `"title"`.
- Node vật lý: `{"type": "node", "stereotype": "device"}` (máy ATM, điện thoại, kiosk), `{"type": "node"}` (server);
  môi trường thực thi `{"type": "executionEnvironment"}` (vd "JVM", "Docker") lồng trong node. Phần tử con dùng
  `"in": "<id node>"`.
- Component triển khai `{"type": "component", "stereotype": "client subsystem" | "service subsystem" | …, "in": …}`
  — tên khớp component/package diagram.
- Artifact `{"type": "artifact", "name": "orders.db", "in": …}`.
- Kết nối node: `{"type": "communicationpath", "from", "to", "stereotype": "WAN" | "LAN" | "HTTPS" | …,
  "fromMult", "toMult"}` (vd `"1..*"` ATM – `"1"` Bank Server). Chỉ nối **node với node**.
- Component dùng artifact: `{"type": "dependency", "stereotype": "use"}`; artifact hiện thực component:
  `dependency` stereotype `manifest` (artifact → component).

## 3. Chạy – sửa đến sạch
```bash
python "<ENGINE>/scripts/uml2drawio.py" ./uml/deployment.json -o ./uml/deployment.drawio
python "<ENGINE>/scripts/comet_check.py" --partial ./uml/deployment.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/deployment.drawio -o ./uml/deployment.html --png
```
1. `uml2drawio.py` tự chạy validator hình học → phải **0 ERROR** (mã thoát 2 = còn lỗi: sửa spec, chạy lại).
2. `comet_check.py` → 0 ERROR và **sửa hết WARN** trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó không
   đúng ngữ cảnh — khi đó nêu mã luật + lý do cho người dùng.
3. **Mở ảnh** `./uml/deployment.png` bằng công cụ đọc file (xem như ảnh) và tự soát: component/artifact nằm trọn
   trong node, nhãn đường truyền + multiplicity đọc được, không chồng nhau.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `.drawio` vừa sinh, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/deployment.drawio` (+ `deployment.png`).
- Báo trung thực số ERROR/WARN/INFO còn lại và lý do; không tuyên bố "chuẩn UML/COMET" khi chưa chạy đủ 3 lệnh trên.
