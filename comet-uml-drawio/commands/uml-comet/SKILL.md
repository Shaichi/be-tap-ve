---
name: uml-comet
description: Vẽ trọn bộ sơ đồ UML theo phương pháp COMET (Gomaa) cho một hệ thống ra một file draw.io nhiều trang – use case, context, entity class, communication + sequence cho từng use case, statechart, (tuỳ chọn) activity, package, component, deployment – nhất quán tên giữa các sơ đồ, bố cục tự động không chồng hình. Dùng khi người dùng gọi /uml-comet hoặc cần cả mô hình COMET chứ không chỉ một sơ đồ.
argument-hint: "<mô tả hệ thống / đề bài; ghi 'đủ 10 bước' nếu cần cả phần thiết kế>"
user-invocable: true
---

# Vẽ trọn bộ mô hình COMET (`/uml-comet`)

**Yêu cầu:** $ARGUMENTS

Dòng trên trống hoặc chưa được thay bằng yêu cầu thật → dùng mô tả người dùng đã đưa trong hội thoại; thiếu hẳn
thông tin cốt lõi (hệ thống làm gì, ai dùng) thì hỏi lại một câu ngắn rồi mới vẽ.

**ENGINE** = `<ENGINE>` — skill gốc [comet-uml-drawio](../comet-uml-drawio/SKILL.md) cài cạnh thư mục lệnh này
(`../comet-uml-drawio`), chứa `scripts/`, `examples/`, `references/`. Không viết XML hay toạ độ bằng tay: chỉ viết
**spec JSON**, script tự bố cục (không chồng/dính hình) và kiểm tra. Lưu spec + kết quả vào `./uml/` của thư mục
làm việc (tạo nếu chưa có) trừ khi người dùng chỉ định chỗ khác.

**Ngôn ngữ trên sơ đồ: mặc định tiếng Anh.** Mọi chữ hiện trên sơ đồ (`title`, tên phần tử, thuộc tính, thao
tác, nhãn quan hệ, message, guard, câu hỏi decision…) viết bằng tiếng Anh, kể cả khi người dùng mô tả bằng tiếng
Việt – tự dịch sang thuật ngữ tiếng Anh chuẩn. Chỉ dùng ngôn ngữ khác khi người dùng yêu cầu rõ (vd "vẽ bằng
tiếng Việt") → đặt `"lang": "vi"` trong spec (không đặt thì `comet_check` báo L1). Trả lời người dùng vẫn
bằng ngôn ngữ của họ.

- **Gán cùng một `"bundle"` cho toàn bộ spec của cùng hệ thống** (ví dụ `"bundle": "atm-banking"`). Validator dùng khoá này để cô lập namespace consistency giữa các diagram; nên giữ nguyên `"bundle"` cho toàn bộ 14 bước. Các luật R1/R2/R5/R7/R8/R12/R14 và X1–X6 sẽ không mượn dữ liệu từ bundle khác.

## 1. Đọc bắt buộc
- Trước khi bắt đầu: `<ENGINE>/references/comet-method.md` (toàn bộ) và `<ENGINE>/SKILL.md`.
- Trước **mỗi** bước ở bảng dưới: đọc file lệnh của bước đó (`../uml-<loại>/SKILL.md`, mục 1–2) và ví dụ nó chỉ tới
  — chưa đọc thì chưa viết spec của bước đó.

## 2. Thứ tự (mỗi bước = 1 spec, tên file đánh số để trang xếp đúng thứ tự)

| Bước | Sơ đồ | Lệnh (đọc quy tắc tại đây) | File spec trong `./uml/` |
|---|---|---|---|
| 1 | Use case model | [/uml-usecase](../uml-usecase/SKILL.md) | `01_usecase.json` |
| 2 | Software system context diagram | [/uml-context](../uml-context/SKILL.md) | `02_context.json` |
| 3 | Entity class model | [/uml-class](../uml-class/SKILL.md) | `03_class.json` |
| 4 | Communication – mỗi use case 1 sơ đồ | [/uml-communication](../uml-communication/SKILL.md) | `04_comm_<use-case>.json` |
| 5 | Sequence – mỗi use case 1 sơ đồ | [/uml-sequence](../uml-sequence/SKILL.md) | `05_seq_<use-case>.json` |
| 6 | Statechart – mỗi lớp «state dependent control» | [/uml-statechart](../uml-statechart/SKILL.md) | `06_stm_<lop-control>.json` |
| 7 | Activity (luồng use case phức tạp) | [/uml-activity](../uml-activity/SKILL.md) | `07_act_<use-case>.json` |
| 8 | Package – kiến trúc subsystem | [/uml-package](../uml-package/SKILL.md) | `08_package.json` |
| 9 | Component | [/uml-component](../uml-component/SKILL.md) | `09_component.json` |
| 10 | Deployment | [/uml-deployment](../uml-deployment/SKILL.md) | `10_deployment.json` |
| + | ERD – thiết kế CSDL từ lớp «entity» | [/uml-erd](../uml-erd/SKILL.md) | `11_erd.json` |
| + | Screen flow – lớp «user interaction» / màn hình | [/uml-screenflow](../uml-screenflow/SKILL.md) | `12_sf_<use-case>.json` |
| + | Context nghiệp vụ (cho người dùng nghiệp vụ) | [/uml-bizcontext](../uml-bizcontext/SKILL.md) | `00_bizcontext.json` |

- Mặc định làm **bước 1–6** (mô hình yêu cầu + phân tích). Bước 7–10 khi người dùng yêu cầu thiết kế / "đủ bộ". Các dòng `+` (ERD, screen flow, context nghiệp vụ) ngoài COMET gốc – chỉ vẽ khi người dùng yêu cầu.
- `./uml/` đã có spec từ lệnh lẻ (vd `usecase.json`, `comm_<use-case>.json`) → dùng lại và **đổi tên** theo cột
  cuối (không viết lại từ đầu, không để hai file cùng một sơ đồ: glob `./uml/*.json` sẽ gộp cả hai). File JSON
  không phải spec thì để ngoài `./uml/`.
- Bước 4–5: làm cho **mọi** use case. Hệ thống quá nhiều use case → vẽ các use case chính, rồi **liệt kê rõ** use case
  nào chưa có sơ đồ tương tác (đó là WARN R1 còn lại, phải nêu cho người dùng).
- Tên là khoá liên kết: actor/use case (bước 1) → lớp ngoài context (bước 2) và `"useCase"` (bước 4–5); lớp entity
  (bước 3) → đối tượng «entity» (bước 4–5); message (bước 4) = message (bước 5) = event/action (bước 6). Viết
  **y hệt** (hoa/thường, khoảng trắng).
- Mỗi spec có `"title"` **khác nhau** (thành tên trang draw.io), vd "Place Order – Communication",
  "Place Order – Sequence".

## 3. Chạy – sửa đến sạch
Sau mỗi bước: chạy 3 lệnh của lệnh con (có `--partial`) cho spec vừa viết. Xong tất cả:
```bash
python "<ENGINE>/scripts/uml2drawio.py" "./uml/*.json" -o ./uml/<He_thong>.drawio
python "<ENGINE>/scripts/comet_model.py" "./uml/*.json" -o ./uml/<He_thong>.model.json
python "<ENGINE>/scripts/comet_check.py" --strict "./uml/*.json"
python "<ENGINE>/scripts/comet_plan.py" "./uml/*.json" -o ./uml/<He_thong>.repair.json
python "<ENGINE>/scripts/preview_svg.py" ./uml/<He_thong>.drawio -o ./uml/<He_thong>.html --png
```
(Glob trong ngoặc kép được script tự mở rộng — chạy được cả trên PowerShell/cmd.)
0. `comet_model.py` gom semantic model thành một index ổn định (`<He_thong>.model.json`) gồm canonical ID, nodes, links, coverage, impact map và provenance; file này là output trung gian cho tooling/repair loop, không chứa tọa độ.
0a. `comet_plan.py` tạo repair plan (`<He_thong>.repair.json`) gồm rule, severity, source và hành động sửa/regenerate; plan là advisory, không tự sửa semantics.
1. `uml2drawio.py` gộp mọi spec thành **một** file nhiều trang, tự chạy validator → phải **0 ERROR** (mã thoát 2 =
   còn lỗi).
2. `comet_check.py` lần cuối **không** `--partial` (kiểm đủ R1–R14 + X1–X6 giữa các sơ đồ, S1–S5, A1–A6, C1–C2; nếu cần tích hợp CI/tooling có thể chạy thêm `--json` để lấy report máy-đọc) → 0 ERROR
   và **sửa hết WARN** trong spec rồi chạy lại. Chỉ giữ một WARN khi chắc chắn nó không đúng ngữ cảnh — nêu mã luật +
   lý do. Không biện minh kiểu "chỉ là cảnh báo nhỏ".
2a. Khi cả bộ đã sạch, chốt nguồn sự thật: `python "<ENGINE>/scripts/comet_project.py" bootstrap "./uml/*.json" -o
   ./uml/<He_thong>.canonical.json` (phải báo `"roundTrip": "exact"`), rồi `compile` một lần để spec mang `conceptId`. Từ lần sửa sau (đổi tên, thêm actor/use case…):
   sửa file canonical → `comet_project.py validate` → `comet_project.py compile ./uml/<He_thong>.canonical.json -o ./uml/`
   → chạy lại các lệnh trên; KHÔNG sửa tay spec đã compile (`compile --check` phát hiện). Xem
   `<ENGINE>/references/comet-project.md`.
3. **Mở từng ảnh** `./uml/<He_thong>_p<N>.png` (mỗi trang một ảnh) bằng công cụ đọc file và tự soát: chữ đọc được,
   không hình/nhãn chồng nhau, ký hiệu đúng.

## 4. Giao
- Có tool draw.io MCP `open_drawio_xml` → đọc file `./uml/<He_thong>.drawio`, truyền **nguyên văn** vào `content`;
  không bật `postLayout`/auto-layout (phá bố cục).
- Không có MCP → đưa đường dẫn `./uml/<He_thong>.drawio` (+ các `.png`).
- Tóm tắt cho người dùng: danh sách trang (sơ đồ) đã vẽ; bảng object structuring (đối tượng → stereotype COMET);
  use case chưa có sơ đồ tương tác (nếu có); số ERROR/WARN/INFO còn lại và lý do. Không tuyên bố "chuẩn UML/COMET"
  khi chưa chạy đủ 3 lệnh trên.
- Người dùng cần đặc tả use case → viết trong câu trả lời theo template Gomaa (Summary, Actors, Precondition, Main
  sequence, Alternative sequences, Postcondition).
