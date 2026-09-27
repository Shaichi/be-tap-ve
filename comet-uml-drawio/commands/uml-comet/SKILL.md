---
name: uml-comet
description: Vẽ trọn bộ sơ đồ UML theo phương pháp COMET (Gomaa) cho một hệ thống ra một file draw.io nhiều trang – use case, context, entity class, communication + sequence cho từng use case, statechart, (tuỳ chọn) activity, package, component, deployment – nhất quán tên giữa các sơ đồ, bố cục tự động không chồng hình. Có hồ sơ SEP490 (FPT capstone) sinh đủ sơ đồ cho Report 3 SRS và Report 4 SDS. Dùng khi người dùng gọi /uml-comet hoặc cần cả mô hình COMET chứ không chỉ một sơ đồ.
argument-hint: "<mô tả hệ thống / đề bài; ghi 'đủ 10 bước' nếu cần cả phần thiết kế; 'SEP490' / 'SRS SDS' cho bộ báo cáo capstone>"
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

**Kỷ luật đọc file (bắt buộc, áp dụng từ đầu phiên):**
- **Cấm mở toàn bộ** file do script sinh ra: `*.model.json` (vài MB ≈ hàng trăm nghìn token), `*.canonical.json`,
  `*.repair.json`, `*.drawio`, `*.html`, `*_DataDictionary.md`. Cần tra một mục → `grep` đúng tên, đọc vài dòng.
- Chỉ đọc: output của lệnh (checker đã in đủ mã luật, file, gợi ý sửa), spec `srs_*/sds_*.json` đang viết/sửa, và
  tài liệu ở mục 1. Spec lớn (ERD vật lý) → đọc phần cần sửa, không đọc lại cả file sau mỗi lần sửa nhỏ.
- Ảnh PNG: mỗi trang xem **một lần** sau khi build; sửa trang nào thì chỉ xem lại trang đó.
- Không dán lại nội dung spec/ảnh vào câu trả lời; báo cáo bằng tên file + output checker.

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

## 2b. Hồ sơ SEP490 – Report 3 (SRS) + Report 4 (SDS)

Dùng **thay** bảng bước 1–10 khi người dùng nhắc SEP490, capstone FPT, "Report 3/Report 4", "SRS + SDS", hoặc đưa
template `Software Requirement Specification` / `Software Design Specification`. Mọi spec cùng một `"bundle"`
(vd `"talenthub"`); tiền tố `srs_`/`sds_` giữ thứ tự trang theo mục của báo cáo.

**Stack mặc định (kiến trúc phân tầng – layered):** backend **Spring Boot** (Controller → Service → Repository,
Spring Data JPA, Spring Security + JWT), web client **React** (SPA gọi REST API), CSDL **PostgreSQL**; hệ thống có
giao diện điện thoại → thêm client **Flutter** (mobile app gọi cùng REST API). Chỉ đổi khi người dùng / SRS nêu
stack khác – khi đó ánh xạ tầng theo bảng cuối mục này và ghi rõ giả định.

| Tầng (Spring Boot) | Lớp / package | Vai trò trong class + sequence thiết kế |
|---|---|---|
| Client | `React Web App` (`"external": true`); `Flutter Mobile App` nếu có mobile | Lifeline đầu tiên, gọi REST endpoint |
| Controller | `XxxController` – package `controller` | `@RestController`: `+createJob(request: JobRequest): ResponseEntity<JobResponse>` |
| Service | `XxxService` (interface) + `XxxServiceImpl` – package `service`, `service.impl` | Nghiệp vụ, `@Transactional` |
| Repository | `XxxRepository` – package `repository` | `«interface»` extends `JpaRepository<Xxx, Long>`: `+findByEmail(email: String): Optional<User>` |
| Entity | `Xxx` – package `entity` | `@Entity` ánh xạ bảng PostgreSQL (SDS I.3) |
| DTO / Mapper | `XxxRequest`, `XxxResponse` – `dto`; `XxxMapper` – `mapper` | Dữ liệu vào/ra API, chuyển Entity ↔ DTO |
| Security / Config / Exception | `SecurityConfig`, `JwtAuthenticationFilter`, `JwtService`, `GlobalExceptionHandler` | Auth flow (SDS III), xử lý lỗi |

| Mục báo cáo | Sơ đồ | Lệnh (đọc quy tắc) | File spec trong `./uml/` | `title` |
|---|---|---|---|---|
| SRS I.1 Context Diagram | Hệ thống (hình tròn) + actor/dịch vụ ngoài, luồng có tên | [/uml-bizcontext](../uml-bizcontext/SKILL.md) | `srs_01_context.json` | `<Sys> - Context Diagram` |
| SRS I.2 Main Business Flows | Activity swimlane **ngang** mỗi BF: `"direction": "LR"`, `partitions` = actor tham gia + `"System"` | [/uml-activity](../uml-activity/SKILL.md) | `srs_02_bf01_<flow>.json`… | `BF-01 <Flow Name>` |
| SRS I.3.1 Entity Relationship Diagram | ERD khái niệm crow's foot: `"notation": "crowfoot"`, `entity` + `attributes` `"+ Full Name"`, quan hệ động từ -ing | [/uml-erd](../uml-erd/SKILL.md) | `srs_03_erd.json` | `<Sys> - Entity Relationship Diagram` |
| SRS I.3 (kèm ERD) State Diagram | Statechart vòng đời **entity chính có cột `status`** (Appointment, Order, Application…): `"stateMachineOf": "<Entity>"` y hệt tên entity ERD, state = giá trị cột `status` – khai báo `"values"` cho cột đó trong SDS I.3 (P8, P11) | [/uml-statechart](../uml-statechart/SKILL.md) | `srs_03_<entity>_state.json` | `<Entity> - State Diagram` |
| SRS I.4.3 Use Case Diagrams | **Mỗi actor 1 sơ đồ** (actor + use case của họ, include/extend) | [/uml-usecase](../uml-usecase/SKILL.md) | `srs_04_uc_<actor>.json` | `UCs for <Actor>` |
| SRS I.5.1a Screen Flow | Site map màn hình; dashboard/màn quản trị theo vai trò **chỉ** đi qua Login: `Home → Login → <Role> Dashboard → …` (P10) | [/uml-screenflow](../uml-screenflow/SKILL.md) | `srs_05_screenflow.json` | `<Sys> - Screen Flow` |
| SDS I.1 Software Architecture | Component lồng tầng (component cha `"stereotype": "subsystem"`, con qua `"in"`): `Client Tier` (`React Web App`, + `Flutter Mobile App`) / `Application Tier` – Spring Boot (`Security Filter (JWT)`, `REST Controllers`, `Service Layer`, `Repository Layer (Spring Data JPA)`) / `Data Tier` (`PostgreSQL Database`) / `External Services`; quan hệ nối **component tầng**, nhãn giao thức (`REST/JSON over HTTPS`, `JDBC`, `SMTP`…). **Không** stereotype COMET (`control`, `database wrapper`, `proxy`…) – P9; view render phía server (JSP/Thymeleaf) thuộc Application Tier, không phải Client Tier | [/uml-component](../uml-component/SKILL.md) | `sds_01_architecture.json` | `<Sys> - Software Architecture` |
| SDS I.2 Package Diagram | Package backend theo tầng: `controller`, `service`, `service.impl`, `repository`, `entity`, `dto`, `mapper`, `security`, `config`, `exception` + dependency (controller → service/dto; service.impl → service/repository/mapper/entity; repository → entity; mapper → entity/dto; security → repository); **mỗi lớp của SDS II** đặt vào package đúng tầng bằng `{"type": "class", "in": "<id package>"}` (X10) | [/uml-package](../uml-package/SKILL.md) | `sds_02_package.json` | `<Sys> - Package Diagram` |
| SDS I.3 Database Design | ERD vật lý crow's foot: `table` + `columns` (kiểu, `pk`/`fk`/`nullable`) + `"entity"` trỏ ERD SRS | [/uml-erd](../uml-erd/SKILL.md) | `sds_03_database.json` | `<Sys> - Database Design` |
| SDS II.x Code Designs (2–3 bộ) | Class diagram `"level": "design"`: Controller → Service (interface) ◁┄ ServiceImpl → Repository («interface» → `JpaRepository<Xxx, Long>`), Entity, Request/Response DTO, Mapper | [/uml-class](../uml-class/SKILL.md) mục 4 | `sds_04_<feature>_class.json` | `<Feature> - Class Diagram` |
| | Sequence `"level": "design"`, `"activations": true`, `"autonumber": true`: `React Web App` (`"external": true`) → Controller → ServiceImpl → Repository (+ Mapper); reply `ResponseEntity`/DTO; nhánh lỗi (`alt`: 400/404/409) | [/uml-sequence](../uml-sequence/SKILL.md) | `sds_04_<feature>_seq.json` | `<Feature> - Sequence Diagram` |
| SDS III.1.1 Authentication Flow | Sequence thiết kế Login JWT: Client → `AuthController.login(LoginRequest)` → `AuthServiceImpl` → `AuthenticationManager` → `UserDetailsServiceImpl`/`UserRepository` → `PasswordEncoder` → `JwtService.generateToken` → `AuthResponse(token)`; `alt` sai mật khẩu → 401; request sau đi qua `JwtAuthenticationFilter` | [/uml-sequence](../uml-sequence/SKILL.md) | `sds_05_auth_seq.json` | `Authentication Flow - Sequence Diagram` |

Khoá liên kết xuyên hai tài liệu (viết **y hệt**; comet_check kiểm):
- Actor: context (SRS I.1) = làn BF (I.2) = actor của `UCs for <Actor>` (I.4.3). Ngoài context chỉ có actor
  người dùng + dịch vụ ngoài; dịch vụ ngoài (Email, Payment…) cũng là component trong `External Services` (SDS I.1).
- Use case (I.4.3) = `"useCase"` của class/sequence thiết kế (SDS II) và auth flow (`"Login"`) – X1. Chọn 2–3 use
  case cốt lõi cho SDS II; các use case còn lại không có sequence là **INFO R1**, không phải lỗi.
- Entity ERD SRS = `"entity"` của bảng SDS I.3 (X7); bảng PostgreSQL snake_case số nhiều (`job_postings`), kiểu
  PostgreSQL: `bigserial`/`bigint`, `varchar(n)`, `text`, `boolean`, `numeric(12,2)`, `timestamptz`, `uuid`.
  Lớp `@Entity` (SDS II) = bảng tương ứng: mỗi thuộc tính có cột (camelCase ↔ snake_case: `createdAt` ↔
  `created_at`, `doctor: Doctor` ↔ `doctor_id`) – X9; thiếu cột thì thêm vào bảng SDS I.3, đừng bịa thuộc tính.
  Ngược lại mỗi cột FK có thuộc tính quan hệ trong lớp (`job_id` → `job: JobPosting`) – X12. Cột `status` của
  entity có statechart: `"values": ["PENDING", "CONFIRMED", …]` = đúng các state (P11).
- Lớp trong class diagram SDS II = lifeline của sequence cùng bộ (X8); message sequence = operation của lớp
  (`createJob(JobRequest)`) – X11: gọi method nào thì method đó phải có trong lớp (hoặc interface lớp đó
  realize / `JpaRepository<…>` lớp đó extends); không có thì thêm operation vào class diagram, không bịa. Lớp có mặt trong package diagram SDS I.2, đúng package theo bảng tầng (X10).
- Sequence thiết kế: mỗi lời gọi `sync` có `reply` (R15, cả `void` → reply `"ok"`); việc không chờ kết quả (gửi
  email, push notification) → `"type": "async"`. Luồng nghiệp vụ trong sequence phải khớp BF (SRS I.2) và
  statechart: trạng thái đặt trong sequence = state trên statechart của entity đó.
- Trạng thái xuyên BF ↔ statechart ↔ sequence (P12): bước BF đổi trạng thái ghi đúng tên state; trước bước đó có
  bước ứng với event của transition vào state (nhánh lỗi/hết hạn → event riêng `paymentFailed`); event = tên use
  case camelCase; **mỗi use case đổi trạng thái xuất hiện trong ít nhất một BF** (thêm BF-03… nếu cần – số BF không
  cố định); sequence đổi trạng thái kiểm trạng thái nguồn trước. Danh từ trong BF (Time Slot…) phải có trên ERD.
- Sequence thiết kế đủ (P13): use case «include» có bước/lifeline; entity cha có con 1..N bắt buộc → tạo con
  (`loop`), DTO có danh sách. Hệ thống ngoài có lớp tích hợp; mọi entity ERD có lớp trong package `entity` (P14).
- Có Flutter: Screen Flow (SRS I.5.1a) tách hai trang `srs_05_screenflow_web.json` / `srs_05_screenflow_mobile.json`
  (`<Sys> - Web Screen Flow` / `<Sys> - Mobile Screen Flow`); lifeline Client của sequence = client thật sự gọi use
  case đó (`React Web App` hoặc `Flutter Mobile App`).
- Framework bean không tự viết (`AuthenticationManager`, `PasswordEncoder`) → `"external": true` trong sequence.
- **Data dictionary** (SDS I.3): **sinh**, không viết tay –
  `python "<ENGINE>/scripts/comet_datadict.py" ./uml/sds_03_database.json -o ./uml/<Sys>_DataDictionary.md`
  (bảng, entity, cột, kiểu, PK/FK → bảng đích, NOT NULL; mô tả cột lấy từ `"description"` của cột). Sửa bảng →
  sửa spec rồi chạy lại. **Không** viết tay một tài liệu đặc tả song song (SPECIFICATION.md…) chứa bảng/cột/luồng
  – nó sẽ lệch sơ đồ; mọi bảng/cột/tên lớp chỉ có một nguồn là spec JSON.
- Mục SRS/SDS không có sơ đồ (bảng use case, đặc tả UC, bảng method…) → viết trong câu trả lời hoặc file `.md`,
  dùng **y hệt** tên trong spec, không vẽ.

Chạy như mục 3 nhưng xuất hai file: `uml2drawio.py "./uml/srs_*.json" -o ./uml/<Sys>_SRS.drawio` và
`"./uml/sds_*.json" -o ./uml/<Sys>_SDS.drawio`; `comet_check.py --strict --profile sep490 "./uml/*.json"` chạy
**trên cả hai** để kiểm liên kết SRS ↔ SDS **và độ đủ theo template** (P1–P14: thiếu mục nào, actor nào chưa có
"UCs for", BF không swimlane, < 2 bộ code design, thiếu auth flow, entity chưa có bảng, entity có `status` chưa có
statechart, kiến trúc dùng stereotype COMET, dashboard vào được không qua Login, state ≠ giá trị status) + X9–X12/R15
(thuộc tính ↔ cột, lớp ↔ package, message ↔ operation, cột FK ↔ thuộc tính, sync ↔ reply) + P12–P14 (trạng thái BF /
sequence ↔ statechart, «include» và entity con 1..N trong sequence, hệ thống ngoài / entity có lớp); cuối cùng sinh data dictionary bằng `comet_datadict.py`. **Không giao khi còn WARN P**:
vẽ bổ sung đúng mục bị báo rồi chạy lại. **INFO không phải "quy ước"**: INFO P12/P14 (và X8/X11) phải được sửa, hoặc
ghi vào NOTES một dòng lý do cụ thể cho từng mục; chỉ INFO R1 (use case ngoài SDS II chưa có sequence) được bỏ qua
không cần giải thích. Thêm tính năng sau này: cập nhật spec SRS + SDS liên quan rồi chạy lại lệnh
này. Canonical (2a) cũng trên `"./uml/*.json"`.

**Chia phiên SRS / SDS (mặc định cho bộ SEP490 đầy đủ; hệ nhỏ < ~12 spec làm một phiên cũng được).** Tính nhất quán
nằm ở **spec JSON + checker**, không ở trí nhớ hội thoại → phiên ngắn, mỗi phiên một báo cáo, ít quên ràng buộc hơn:
1. **Phiên 1 – SRS:** viết `srs_*.json`; kiểm bằng
   `comet_check.py --strict --profile sep490 --partial "./uml/srs_*.json"` (mục SDS chưa có chỉ là INFO P2/P6) → 0
   ERROR, 0 WARN; build `<Sys>_SRS.drawio` + PNG, soát ảnh. Cuối phiên ghi `./uml/NOTES.md` **chỉ gồm quyết định
   không suy ra được từ spec**: stack, 2–3 use case chọn cho SDS II, giả định nghiệp vụ, WARN còn giữ (mã + lý do).
   **Không** chép danh sách actor/use case/entity/cột vào NOTES – spec là nguồn duy nhất. Dừng, báo người dùng mở phiên mới.
2. **Phiên 2 – SDS (phiên mới):** đọc `./uml/NOTES.md` rồi lấy tên từ spec SRS cần dùng (`srs_03_erd.json`,
   `srs_03_*_state.json`, `srs_04_uc_*.json`, `srs_02_*.json` khi viết luồng) – **không** mở `.drawio`/PNG của SRS.
   Viết `sds_*.json`; kiểm trên **cả bộ, không `--partial`**: `comet_check.py --strict --profile sep490 "./uml/*.json"`
   (X1/X7/X9–X12/P5–P14 đối chiếu SDS với SRS). Lệch do SRS thiếu (entity/cột/use case) → sửa spec SRS, build lại
   `<Sys>_SRS.drawio`, ghi một dòng vào NOTES. Xong: build `<Sys>_SDS.drawio` + PNG, sinh data dictionary, canonical (2a).
3. **Phiên sau – thêm/sửa tính năng:** đọc NOTES, sửa đúng spec SRS + SDS liên quan, chạy lại lệnh kiểm cả bộ.
Người dùng muốn làm liền một phiên → vẫn theo đúng thứ tự trên (SRS sạch với `--partial` rồi mới sang SDS).

Stack khác (chỉ khi người dùng nêu) – đổi tên tầng, giữ nguyên cấu trúc:

| Stack | Controller | Service | Truy cập dữ liệu | Client / khác |
|---|---|---|---|---|
| Java Servlet/JSP | `XxxServlet` (`doGet`/`doPost`) | `XxxService` | `XxxDAO` (JDBC) | JSP view, DTO |
| ASP.NET Core | `XxxController` | `IXxxService` / `XxxService` | `XxxRepository` / `AppDbContext` (EF Core) | ViewModel |
| Node.js / Express | `xxxController` + `xxxRouter` | `xxxService` | `xxxModel` (Sequelize/Mongoose) | middleware |
| Laravel | `XxxController` | `XxxService` | Eloquent model `Xxx` | FormRequest, Resource |

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
**Tiết kiệm token:** theo "Kỷ luật đọc file" ở đầu – chỉ đọc output lệnh và spec cần sửa; **không** mở
`*.model.json`/`*.repair.json`/`*.canonical.json`/`*.drawio`/`*.html` (cần tra thì `grep`); xem PNG thay vì XML.
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
