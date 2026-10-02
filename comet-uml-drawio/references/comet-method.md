# COMET (Collaborative Object Modeling and architectural design mEThod) – Gomaa

Tóm tắt những gì cần để vẽ sơ đồ "đúng COMET". Nguồn: H. Gomaa, *Software Modeling and Design:
UML, Use Cases, Patterns, and Software Architectures* (2011); *Real-Time Software Design for
Embedded Systems* (2016).

## 1. Các pha và sơ đồ tương ứng (thứ tự nên vẽ)

| Pha | Sản phẩm | `diagram` trong spec |
|---|---|---|
| Requirements modeling | Use case diagram (+ đặc tả use case dạng văn bản) | `usecase` |
| Analysis – static | Software system **context** class diagram | `context` |
| Analysis – static | **Entity** class model (lớp «entity», thuộc tính, quan hệ) | `class` |
| Analysis – object structuring | Phân loại đối tượng theo stereotype (bảng mục 2) | – |
| Analysis – dynamic interaction | Mỗi use case → 1 communication diagram (và/hoặc sequence diagram) | `communication`, `sequence` |
| Analysis – dynamic state machine | Statechart cho mỗi lớp «state dependent control» | `state` |
| Design | Integrated communication diagram, subsystem architecture | `communication`, `package` |
| Design | Component-based / concurrent task architecture | `component` |
| Design | Deployment diagram | `deployment` |

Activity diagram (`activity`) dùng tuỳ chọn để mô tả luồng của use case hoặc thuật toán.

## 2. Stereotype cấu trúc đối tượng (object structuring criteria)

| Nhóm | Stereotype | Ý nghĩa |
|---|---|---|
| **Boundary** | «user interaction» | giao tiếp với actor người |
| | «input» / «output» / «I/O» (device I/O) | giao tiếp với thiết bị ngoài |
| | «proxy» | giao tiếp với hệ thống ngoài |
| | «timer» (thường xếp nhóm control) | nhận sự kiện từ đồng hồ ngoài |
| **Control** | «coordinator» | điều phối, không phụ thuộc trạng thái |
| | «state dependent control» | hành vi phụ thuộc trạng thái → **bắt buộc có statechart** |
| | «timer» | điều khiển theo chu kỳ thời gian |
| **Application logic** | «business logic», «algorithm», «service» | quy tắc nghiệp vụ, thuật toán, dịch vụ |
| **Entity** | «entity» | dữ liệu dài hạn, **thụ động** (chỉ được gọi, trả dữ liệu) |
| | «database wrapper», «data abstraction» | (thiết kế) bao gói truy cập dữ liệu |

Communication diagram được bố cục theo cột trái→phải đúng thứ tự COMET:
actor chính | boundary | control | application logic | entity | actor/hệ thống phụ (`"side": "right"`).

## 3. Actor và context diagram

- Actor loại: **primary** (khởi tạo use case), **secondary**; theo bản chất: human user, external
  system, input device, output device, I/O device, timer.
- Software system context diagram là class diagram gồm **đúng 1** lớp «software system» và các lớp
  ngoài với stereotype: «external input device», «external output device», «external I/O device»,
  «external user», «external system», «external timer». Quan hệ association có tên (thường "Inputs to",
  "Outputs to", "Interacts with", "Awakens" cho timer) và multiplicity (vd `1..*` ATM – `1` hệ thống).
- Mỗi actor của use case model có lớp ngoài cùng tên trong context diagram (R14) — trừ actor người chỉ
  tương tác qua thiết bị đã có trên sơ đồ (vd ATM Customer dùng Card Reader, Cash Dispenser).

## 4. Use case model

- Mỗi use case có tên dạng động từ + danh từ ("Withdraw Funds").
- «include»: use case cơ sở → use case được bao gồm (mũi tên hướng về use case được include).
- «extend»: use case mở rộng → use case cơ sở (mũi tên hướng về use case cơ sở), có thể kèm
  extension point / điều kiện `[condition]`.
- Có thể nhóm use case vào package (vd theo actor/chức năng).

## 5. Quy tắc nhất quán (kiểm bằng `scripts/comet_check.py`)

| Mã | Quy tắc | Mức |
|---|---|---|
| R1 | Mỗi use case có ≥1 sơ đồ tương tác (`"useCase"` trùng tên) | WARN (`--partial`: INFO) |
| R2 | Actor trong sơ đồ tương tác có trong use case model | WARN |
| R3 | Actor chỉ trao đổi message với đối tượng boundary | WARN |
| R4 | Đối tượng dùng stereotype COMET hợp lệ | WARN |
| R5 | Đối tượng «entity» có lớp «entity» cùng tên trong entity class model | WARN |
| R6 | Entity thụ động – không chủ động gửi message (chỉ trả dữ liệu) | INFO |
| R7 | Mỗi «state dependent control» có statechart (`"stateMachineOf"`) | WARN (`--partial`: INFO) |
| R8 | Event trên statechart = message **đến** đối tượng control; action = message **đi**; và ngược lại: message đến/đi control phải là event/action (trừ reply) | WARN/INFO |
| R9 | Số thứ tự message không trùng; message có tên; tham chiếu hợp lệ | ERROR |
| R10 | Lớp «entity» ở pha phân tích chỉ có thuộc tính | WARN |
| R11 | Context diagram có đúng 1 «software system», các lớp khác «external …»; association có tên + multiplicity | ERROR/WARN/INFO |
| R12 | Communication và sequence của cùng use case có cùng tập message (tên, bên gửi/nhận); khác `seq` → INFO | WARN/INFO |
| R13 | Mỗi đối tượng boundary trao đổi message với ≥ 1 actor (proxy ↔ hệ thống ngoài nó đại diện) | WARN |
| R14 | Actor của use case model có lớp ngoài cùng tên trong context diagram | INFO |
| R15 | Sequence mức thiết kế: mỗi lời gọi đồng bộ (sync, mặc định) A → B có reply B → A phía sau; không chờ kết quả → `"type": "async"` | WARN |
| S1–S5 | Statechart hợp lệ: initial không event/guard; final không có transition ra; guard của choice; tới được / có đường ra; tất định | ERROR/WARN |
| A1–A6 | Activity hợp lệ: guard của decision; fork/join; initial/final; merge; ngõ cụt; không join/fork ngầm trên action | ERROR/WARN |
| C1–C2 | Class diagram: thuộc tính có kiểu; multiplicity ở hai đầu association/aggregation/composition (WARN), association có tên/role (INFO) | WARN/INFO |
| E1–E3 | ERD: quan hệ tham chiếu đúng thực thể (ERROR); đủ bản số 2 đầu – Chen `1`/`N`/`M`/`P` hoặc `(min,max)` như `(0,N)`, crow's foot `1`/`0..1`/`1..N`/`0..N` (WARN); quan hệ có tên – Chen: hình thoi, crow's foot khái niệm: động từ -ing trên đường nối (WARN) | ERROR/WARN |
| E4 | ERD crow's foot vật lý: bảng (`"type": "table"`) có `columns` phải có cột `"pk": true` | WARN |
| E5 | ERD (Chen): thực thể yếu (`weak`) phải nối với ít nhất một quan hệ xác định (`identifying`, hình thoi viền kép) | WARN |
| F1–F2 | Screen flow (site map): mọi màn hình tới được từ màn hình gốc; không initial/decision, không `items`, mũi tên không nhãn | WARN |
| B1–B3 | Context nghiệp vụ: đúng 1 hệ thống trung tâm (ERROR); luồng có tên và nối trung tâm ↔ bên ngoài; thực thể ngoài có luồng | ERROR/WARN |
| L1 | Mọi sơ đồ: chữ trên sơ đồ mặc định tiếng Anh – có chữ có dấu (tiếng Việt…) mà spec chưa đặt `"lang"` khác `"en"` | WARN |
| X1 | Interaction/activity tham chiếu `useCase` không tồn tại trong use case model cùng `bundle` | WARN (bundle chưa có use case model + `--partial`: INFO) |
| X2 | Actor được gán cho use case phải xuất hiện trong interaction của use case đó, cùng `bundle` | WARN (`--partial`: INFO) |
| X3 | Statechart phải truy vết được về `state dependent control` cùng tên trong interaction, cùng `bundle` (statechart vòng đời entity – `stateMachineOf` là entity/bảng của ERD hoặc lớp «entity» cùng bundle – bỏ qua) | WARN (`--partial`: INFO) |
| X4 | ERD và entity class model phải khớp thực thể khi có cùng bundle (không có bundle: cùng tiền tố title hoặc ≥2 tên chung; cặp duy nhất không ghép được → INFO) | WARN/INFO |
| X5 | Component và deployment phải khớp tên khi có cùng bundle (cùng quy tắc ghép như X4) | WARN/INFO |
| X6 | Cùng một tên structural không được đổi vai trò entity ↔ boundary/control/application logic | WARN |
| X7 | Bảng vật lý (`"entity": "..."`) phải trỏ tới entity của ERD khái niệm cùng `bundle`; entity khái niệm chưa có bảng nào trỏ tới → INFO | WARN/INFO |
| X8 | Sequence/communication mức thiết kế (`"level": "design"`): lifeline là lớp có trong class diagram mức thiết kế cùng `bundle` + `useCase` (use case không có class diagram riêng → so với mọi lớp thiết kế của bundle, chỉ INFO; `"external": true` bỏ qua) | WARN/INFO |
| X11 | Message trong sequence mức thiết kế tới lớp X phải là operation của X (tính cả lớp cha/interface qua generalization/realization; lớp kế thừa `JpaRepository<…>` có sẵn `save`/`findById`/`findAll`/`deleteById`…; getter/setter của thuộc tính; `"type": "create"` bỏ qua) – chặn bịa method | WARN (use case có class diagram riêng) / INFO |
| X9 | Lớp entity trong class diagram mức thiết kế (tên = `"entity"` của bảng vật lý cùng `bundle`): mỗi thuộc tính có cột tương ứng (camelCase ↔ snake_case, `doctor: Doctor` ~ `doctor_id`; bỏ qua `List<…>`/`Set<…>`/`[]`) | WARN |
| X10 | Package diagram cùng `bundle` có đặt lớp vào package (`"in"`) → mọi lớp của class diagram mức thiết kế phải có trong package diagram (bỏ qua kiểu framework `JpaRepository<User, Long>`) | WARN |
| X12 | Ngược với X9: mỗi cột FK (`"fk": true`) của bảng có thuộc tính quan hệ trong lớp entity thiết kế tương ứng (`job_id` ~ `job: JobPosting` / `jobId: Long`); bỏ qua lớp entity không vẽ thuộc tính nào | WARN |
| P1 | `--profile sep490`: SRS đủ sơ đồ – context (bizcontext), business flow (activity), ERD khái niệm (có `entity`), use case, screen flow | WARN (`--partial`: INFO) |
| P2 | `--profile sep490`: SDS đủ sơ đồ – architecture (component), package, database design (ERD có `table`), class + sequence `"level": "design"` | WARN (`--partial`: INFO) |
| P3 | `--profile sep490`: mỗi actor chính có sơ đồ use case riêng ("UCs for <Actor>": actor chính duy nhất hoặc tên actor trong `title`); actor phụ (chỉ ở đầu "to" của association use case → actor) không cần | WARN (`--partial`: INFO) |
| P4 | `--profile sep490`: business flow là swimlane – `partitions` có làn `"System"` | WARN (`--partial`: INFO) |
| P5 | `--profile sep490`: SDS II ≥ 2 use case có đủ cặp class + sequence thiết kế cùng `useCase`; class thiết kế có sequence cùng `useCase`; `useCase` của class thiết kế có trong use case model | WARN (`--partial`: INFO) |
| P6 | `--profile sep490`: có sequence thiết kế cho luồng xác thực (`useCase`/`title` chứa Login / Sign in / Auth…) | WARN (`--partial`: INFO) |
| P7 | `--profile sep490`: mọi entity của ERD khái niệm có bảng vật lý trỏ tới (`"entity"`); thay ghi chú X7 tương ứng | WARN (`--partial`: INFO) |
| P8 | `--profile sep490`: bảng/entity có cột trạng thái (`status`, `*_status`, `state`) → có ít nhất 1 statechart cho entity đó (`"stateMachineOf": "<Entity>"`) | WARN (`--partial`: INFO) |
| P9 | `--profile sep490`: Software Architecture (component) không dùng stereotype đối tượng COMET (`control`, `entity`, `database wrapper`, `proxy`, `user interaction`…) – kiến trúc phân tầng chỉ đặt `subsystem` cho tầng | WARN (`--partial`: INFO) |
| P10 | `--profile sep490`: screen flow – màn hình quản trị (Dashboard / Admin / Management) chỉ tới được qua màn Login | WARN (`--partial`: INFO) |
| P12 | `--profile sep490`: trạng thái nhất quán với statechart entity – bước BF / message sequence thiết kế nhắc status (CHỮ_HOA hoặc tên state, chỉ khi có chữ status/state) phải là state có thật; bước BF đưa entity sang X phải có bước trước đó ứng với event của transition vào X (trừ state tạo từ initial; bước "Verify Confirmed X" không tính là use case Confirm X); sequence thiết kế đặt X phải là use case/operation = event vào X (tính use case «include») và kiểm trạng thái nguồn trước (fragment có status/tên state nguồn, hoặc message `getStatus`/`validate…`/`check…`/`is…`/`can…`) | WARN (cả `--partial`) |
| P12 | INFO: event của statechart entity không trùng use case nào; use case đổi trạng thái (event) chưa xuất hiện trong business flow nào | INFO |
| P13 | `--profile sep490`: sequence thiết kế đủ – use case «include» có bước/lifeline (từ riêng của use case include, so khớp tiền tố: Pay ~ Payment) hoặc sequence riêng; sequence tạo entity cha (`save…`/`create…` tới `<Entity>Repository`, `"type": "create"`) có quan hệ ERD `1..N` bắt buộc thì phải nhắc entity con (lifeline/message: `addItem`, `PrescriptionItem`) | WARN (cả `--partial`) |
| P14 | `--profile sep490`: hệ thống ngoài của context (không phải actor use case) có lớp/lifeline tích hợp trong SDS (class/sequence thiết kế, package); package diagram có lớp cho mọi entity ERD khái niệm | INFO |
| P15 | `--profile sep490`: mỗi lớp ngoài của context (SRS I.1) là actor trong sơ đồ use case – hệ thống ngoài (VNPay, Email) vẽ làm actor phụ (use case → actor, `"side": "right"`) | WARN (cả `--partial`) |
| P11 | `--profile sep490`: statechart của entity (P8) khớp tập giá trị cột status – khai báo `"values"` cho cột (hoặc enumeration trong class diagram mà thuộc tính `status` trỏ tới); mỗi state lá là 1 giá trị, mỗi giá trị là 1 state (`PENDING_PAYMENT` ~ `Pending Payment`) | WARN (`--partial`: INFO) |

Tên message/event được so khớp sau khi bỏ danh sách tham số (`placeOrder(cart)` ~ `placeOrder`).

**Bundle isolation:** nếu spec có `"bundle"`, validator coi đó là namespace consistency. Hai diagram cùng tên nhưng khác bundle không được dùng để thỏa R1/R7/R8/R12 hoặc X1–X6 cho nhau; R2/R5/R14 chỉ áp dụng khi chính bundle đó có use case model / entity class model / context diagram; spec không có bundle vẫn giữ hành vi cũ.
**Mức thiết kế (`"level": "design"`)** – class/sequence kiểu SDS (Controller, Service, Repository, DTO – mặc định Spring Boot) không
dùng stereotype COMET: bỏ R3/R4/R10; C2 thiếu multiplicity chỉ INFO; R1/X2 chỉ INFO khi bundle không có sơ đồ
tương tác mức phân tích cho use case đó (SDS chỉ cần 2–3 bộ thiết kế tiêu biểu). Lifeline thiết kế không
stereotype được model gộp với lớp cùng tên của class diagram (đổi tên lan sang cả hai).
`--partial` dùng khi mới vẽ một phần bộ sơ đồ; lần kiểm cuối cho cả bộ chạy **không** `--partial`.

## 6. Quy ước message trong COMET

- Đánh số theo thứ tự trong use case: `1`, `2`, `3`...; nhánh thay thế dùng hậu tố chữ `10a`, `11a`;
  lồng nhau `1.1`, `1.2`.
- Tên message là **danh từ/sự kiện** mô tả dữ liệu/sự kiện ("Card Inserted", "PIN Entered", "Valid PIN").
- Message từ actor tới boundary là input thô ("Card Reader Input"); boundary chuyển thành sự kiện cho
  control ("Card Inserted").
- Cùng một tên message phải giữ nguyên ở communication diagram, sequence diagram và statechart
  (event/action) – đây là cách COMET liên kết mô hình tương tác với mô hình trạng thái.

## 7. Statechart (state machine) theo COMET

- Nhãn transition: `Event [guard] / action1, action2`. Event = message đến control object;
  action = message control gửi đi.
- Transition từ initial không có event/guard: initial → trạng thái chờ ban đầu ("Idle"), rồi
  `Idle --Event / action--> …` (S1).
- Activity trong state: `entry / X`, `exit / Y`, `do / Z`.
- Có thể dùng composite state (`"in"`), history `H`, choice.
- `"stateMachineOf"` phải bằng tên lớp control ("ATM Control").

## 8. Thiết kế (tóm tắt)

- Integrated communication diagram: hợp nhất các communication diagram của mọi use case.
- Subsystem: package/component có stereotype «client subsystem», «service subsystem»,
  «control subsystem», «coordinator subsystem», «user interaction subsystem», «input subsystem»...
- Kiểu message giữa task/component: asynchronous (mũi tên mở) hoặc synchronous (mũi tên đặc) –
  đặt `"type": "async"|"sync"` trong sequence.
- Deployment: node «device»/«execution environment», communication path có stereotype mạng («LAN», «WAN»).
