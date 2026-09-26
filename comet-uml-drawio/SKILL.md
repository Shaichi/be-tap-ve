---
name: comet-uml-drawio
description: Vẽ sơ đồ UML chuẩn cú pháp theo phương pháp COMET (Gomaa) và xuất ra draw.io (qua draw.io MCP hoặc file .drawio) với bố cục tự động KHÔNG chồng/dính hình. Dùng khi người dùng muốn vẽ use case, context, class/entity, communication (collaboration), sequence, statechart, activity, component, deployment, package diagram, ERD (sơ đồ thực thể quan hệ, ký pháp Chen – hình thoi), screen flow (sơ đồ trang / site map – cây điều hướng màn hình), context diagram nghiệp vụ (hình tròn trung tâm); khi nhắc tới COMET, Gomaa, «entity»/«boundary»/«control», draw.io, drawio, diagrams.net, hoặc "vẽ sơ đồ UML".
---

# Bé tập vẽ – COMET UML → draw.io

Bộ skill này tách việc vẽ sơ đồ thành 3 bước để AI **không bao giờ tự đoán toạ độ**:

1. **Mô hình hoá** (việc của AI): viết *spec JSON* mô tả phần tử + quan hệ/message theo UML & COMET.
2. **Bố cục + sinh XML** (việc của script): `scripts/uml2drawio.py` tự tính vị trí (Sugiyama layered layout),
   định tuyến đường nối vuông góc theo làn riêng, chừa chỗ cho nhãn → không hình nào chồng/dính nhau,
   không đường nào đi xuyên hình hoặc đè khít lên đường khác.
3. **Lập semantic model + kiểm tra**: `scripts/comet_model.py` tạo semantic graph ổn định (canonical ID + provenance), sau đó `scripts/validate_drawio.py` (hình học + UML lint) và `scripts/comet_check.py`
   (nhất quán COMET giữa các sơ đồ) → mở bằng draw.io MCP hoặc giao file `.drawio`.

> Quy tắc vàng: KHÔNG viết mxGraph XML bằng tay, KHÔNG dùng `postLayout`/ELK/auto-layout của MCP
> lên XML đã sinh (sẽ phá bố cục và kiểu đường UML). Muốn sửa → sửa spec rồi sinh lại.

Mọi đường dẫn bên dưới tương đối so với thư mục chứa file SKILL.md này (`<skill>`).

## Lệnh vẽ từng loại sơ đồ
Mỗi loại sơ đồ có một lệnh (skill anh em, cài cạnh thư mục này) gói sẵn: ví dụ bắt buộc đọc, quy tắc UML/COMET
của loại đó, 3 lệnh chạy – kiểm – chụp ảnh. Người dùng gọi lệnh → làm theo file lệnh; yêu cầu tự do ("vẽ class
diagram cho…") → đọc file lệnh tương ứng trước khi viết spec.

| Sơ đồ | Lệnh | Sơ đồ | Lệnh |
|---|---|---|---|
| Use case | [/uml-usecase](../uml-usecase/SKILL.md) | Statechart | [/uml-statechart](../uml-statechart/SKILL.md) |
| Context | [/uml-context](../uml-context/SKILL.md) | Activity (swimlane) | [/uml-activity](../uml-activity/SKILL.md) |
| Class / entity | [/uml-class](../uml-class/SKILL.md) | Package / subsystem | [/uml-package](../uml-package/SKILL.md) |
| Communication | [/uml-communication](../uml-communication/SKILL.md) | Component | [/uml-component](../uml-component/SKILL.md) |
| Sequence | [/uml-sequence](../uml-sequence/SKILL.md) | Deployment | [/uml-deployment](../uml-deployment/SKILL.md) |
| ERD (Chen) | [/uml-erd](../uml-erd/SKILL.md) | Screen flow | [/uml-screenflow](../uml-screenflow/SKILL.md) |
| Context nghiệp vụ (hình tròn) | [/uml-bizcontext](../uml-bizcontext/SKILL.md) | | |

Cả bộ theo thứ tự COMET, ra 1 file nhiều trang: [/uml-comet](../uml-comet/SKILL.md).
Trong bản nguồn các lệnh nằm ở `commands/uml-*/SKILL.md` (placeholder `<ENGINE>`); cài bằng
`python <skill>/scripts/install.py` → chép engine + mỗi lệnh thành `<thư mục skills>/uml-*/SKILL.md` với
`<ENGINE>` thay bằng đường dẫn tuyệt đối (mặc định `~/.claude/skills` và `~/.gemini/config/skills` nếu có;
`--dest DIR`, `--dry-run`, `--uninstall`).

## Quy trình

### Bước 0 – Xác định sơ đồ cần vẽ (theo COMET)
Đọc `references/comet-method.md` nếu người dùng yêu cầu "theo COMET" hoặc cần cả bộ sơ đồ. Thứ tự chuẩn:
use case model → software system context diagram → entity class model → (mỗi use case) communication
và/hoặc sequence diagram → statechart cho mỗi đối tượng «state dependent control» → (thiết kế)
integrated communication diagram, subsystem/component/deployment.

### Bước 1 – Viết spec
- Định dạng đầy đủ: `references/spec-format.md`. Ví dụ mẫu (hệ ATM/Banking của Gomaa): `examples/*.json`
- Semantic model: `references/comet-model.md` mô tả canonical ID, coverage, impact map và schema JSON.
  – mỗi loại sơ đồ có 1 file; **bắt buộc** mở file cùng loại làm khuôn trước khi viết spec mới.
- Activity: chia làn bằng `partitions` (cấp spec) + `partition` (mỗi phần tử); luồng ra khỏi decision
  luôn có `guard`. Component: interface cung cấp/yêu cầu dùng `notation: "lollipop"` + `provides`/`requires`.
- Ký hiệu UML (mũi tên, nét đứt, multiplicity, guard...): `references/uml-notation.md`.
- Chỉ khai báo *ngữ nghĩa* (type, name, stereotype, from/to, multiplicity, seq...). Không khai báo toạ độ.
- Stereotype viết tên trần (`"entity"`, `"state dependent control"`); script tự thêm « ».
- Mỗi sơ đồ 1 spec. Tên use case / lớp / message phải **viết giống hệt nhau** giữa các sơ đồ
  (comet_check so khớp theo tên).
- **Ngôn ngữ trên sơ đồ mặc định là tiếng Anh** (title, tên, thuộc tính, nhãn, message, guard, câu hỏi decision…),
  kể cả khi người dùng mô tả bằng tiếng Việt → tự dịch sang thuật ngữ tiếng Anh chuẩn. Người dùng yêu cầu rõ ngôn
  ngữ khác → đặt `"lang": "vi"` (…) trong spec; không đặt mà có chữ có dấu thì `comet_check` báo L1.
  Trả lời người dùng vẫn bằng ngôn ngữ của họ.

### Bước 2 – Sinh file
```bash
python <skill>/scripts/uml2drawio.py spec1.json [spec2.json ...] -o diagram.drawio
```
- Nhiều spec → nhiều trang (page) trong một file (tên trang = `title`; trùng thì tự thêm loại sơ đồ/số).
  Script tự chạy validator; mã thoát 2 nếu còn lỗi.
- Glob `"uml/*.json"` (để trong ngoặc kép) được script tự mở rộng – chạy được cả trên PowerShell/cmd.
- `--xml-only` in `<mxGraphModel>` của trang đầu ra stdout (để truyền thẳng vào MCP).
- Có WARN về quan hệ vượt biên container/phần tử không tồn tại → sửa spec.

### Bước 3 – Kiểm tra
```bash
python <skill>/scripts/validate_drawio.py diagram.drawio        # 0 ERROR mới được giao
python <skill>/scripts/comet_check.py spec1.json spec2.json ...  # khi làm theo COMET (--partial: mới vẽ 1 phần)
python <skill>/scripts/preview_svg.py diagram.drawio -o preview.html --png   # ảnh PNG mỗi trang để tự soát
```
- **ERROR** (bắt buộc sửa): hình chồng nhau, đường xuyên hình, 2 đường đè khít, message sequence
  không nằm ngang, «include»/«extend» sai nét, id trùng/treo; COMET R9/R11, statechart S1–S2…
- **WARN**: nhãn đè hình/nhãn, hình sát < 8px, dùng `<<>>` thay «», vi phạm quy tắc COMET (R1–R14),
  statechart (S1–S5), activity (A1–A6), class (C1–C2), chữ không phải tiếng Anh khi chưa đặt `lang` (L1). **Sửa hết WARN trong spec** rồi chạy lại; chỉ giữ một WARN
  khi chắc chắn nó không đúng ngữ cảnh, và nêu mã luật + lý do cho người dùng (không biện minh "chỉ là cảnh báo").
- **INFO**: stereotype lạ, event/action chưa khớp message (có thể do use case chưa vẽ), thiếu tên quan hệ.
- `comet_check.py --partial`: khi mới vẽ một phần bộ sơ đồ, "thiếu sơ đồ đối ứng" (R1 use case chưa có sơ đồ
  tương tác, R7 control chưa có statechart) chỉ là INFO. Lần kiểm cuối cho cả bộ: không `--partial`.
- Validator cũng dùng được cho file draw.io bất kỳ (kể cả file nén) → dùng để kiểm tra sơ đồ người dùng đưa.
- `--png`: chụp mỗi trang thành `preview.png` / `preview_p<N>.png` bằng Chrome/Edge headless → **mở ảnh xem**
  trước khi giao (không có trình duyệt thì script báo và bỏ qua; xem `preview.html`).
- Kiểm thử hồi quy của chính skill: `python <skill>/tests/run_tests.py` (chạy sau khi sửa script).

### Bước 4 – Giao cho người dùng qua draw.io MCP
Xem chi tiết `references/drawio-mcp.md`. Tóm tắt:
- Có tool `open_drawio_xml` (server `@drawio/mcp`): đọc nội dung file `.drawio` vừa sinh và truyền
  nguyên văn vào `content` (không truyền `postLayout`) → draw.io mở đúng bố cục.
- Sửa 1 trang trong file nhiều trang: `--xml-only` → tool `set_page`; đọc sơ đồ người dùng: `get_page`.
- Tool MCP chưa hiện trong phiên? Kiểm tra server bằng `python <skill>/scripts/mcp_smoke.py --list`.
- Có tool `create_diagram` (MCP App draw.io): truyền XML; **không** bật `postLayout`, không yêu cầu
  routing lại.
- MCP chỉ có thao tác từng hình (add vertex/edge): dùng đúng toạ độ, kích thước, style lấy từ XML đã sinh.
- Không có MCP: giao file `.drawio` (mở bằng app draw.io hoặc app.diagrams.net → File › Open).

## Khi người dùng đưa sơ đồ có sẵn / yêu cầu sửa
1. Chạy validator lên file của họ để liệt kê lỗi chồng hình / sai ký hiệu.
2. Dựng lại spec từ nội dung sơ đồ (tên phần tử, quan hệ), sinh lại → validator sạch.
3. Nếu buộc phải sửa tay XML: tuân thủ mục "Sửa XML an toàn" trong `references/drawio-mcp.md`
   và chạy lại validator.

## Checklist trước khi trả lời
- [ ] Đúng loại sơ đồ & ký hiệu UML (bảng trong `uml-notation.md`).
- [ ] Chữ trên sơ đồ bằng tiếng Anh (trừ khi người dùng yêu cầu ngôn ngữ khác và spec có `"lang"`).
- [ ] Stereotype COMET đúng nhóm; actor chỉ nói chuyện với đối tượng boundary; entity thụ động.
- [ ] Message đánh số, tên message trong communication = sequence; event/action statechart khớp message.
- [ ] `uml2drawio.py`/`validate_drawio.py` 0 ERROR; `comet_check.py` 0 ERROR, WARN đã sửa (WARN nào còn lại:
      nêu mã luật + lý do).
- [ ] Đã mở ảnh `--png` từng trang và tự soát (chữ đọc được, không chồng hình/nhãn).
- [ ] Đã mở qua MCP hoặc đưa đường dẫn file `.drawio`.

- Traceability chéo mở rộng: **X1–X6** (use case, actor, statechart, ERD/entity, component/deployment, role consistency).
- [ ] Nếu bộ sơ đồ có nhiều hệ thống: tất cả spec của cùng hệ thống đã đặt cùng `"bundle"`; không trộn namespace giữa các bundle.
- [ ] Semantic model đã được sinh (khi làm full COMET) để làm canonical index cho tooling/repair loop.
