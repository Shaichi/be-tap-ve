# Ký hiệu UML 2.5 và style draw.io tương ứng

Script `uml2drawio.py` đã sinh sẵn các style này. Bảng dùng để (a) chọn đúng `type` trong spec,
(b) kiểm tra/sửa file draw.io có sẵn.

## Quan hệ (edge)

| UML | Ký hiệu | spec `type` | style draw.io |
|---|---|---|---|
| Association | nét liền, không mũi tên (hoặc mũi tên mở nếu navigable) | `association` (+`navigable`) | `endArrow=none` / `endArrow=open;endFill=0` |
| Aggregation | thoi rỗng ở phía **toàn thể** (`from`) | `aggregation` | `startArrow=diamondThin;startFill=0` |
| Composition | thoi đặc ở phía toàn thể (`from`) | `composition` | `startArrow=diamondThin;startFill=1` |
| Generalization | tam giác rỗng chỉ vào lớp **cha** (`from` con → `to` cha) | `generalization` | `endArrow=block;endFill=0` |
| Realization | nét đứt + tam giác rỗng chỉ vào interface | `realization` | `endArrow=block;endFill=0;dashed=1` |
| Dependency | nét đứt + mũi tên mở | `dependency` (+`stereotype`) | `endArrow=open;endFill=0;dashed=1` |
| «include» | nét đứt, mũi tên mở, base → included | `include` | như dependency + nhãn «include» |
| «extend» | nét đứt, mũi tên mở, extension → base | `extend` (+`condition`) | như dependency + nhãn «extend» |
| Actor – use case | nét liền, không mũi tên | `association` | `endArrow=none` |
| Transition / control flow | nét liền, mũi tên mở | `transition` / `flow` | `endArrow=open;endFill=0` |
| Note anchor | nét đứt không mũi tên | `anchor` | `endArrow=none;dashed=1` |
| Link (communication) | nét liền, không mũi tên; message là mũi tên nhỏ kèm nhãn | tự sinh từ `messages` | `endArrow=none` |
| Communication path (deployment) | nét liền, có thể có «stereotype» | `communicationpath` | `endArrow=none` |
| «use» / required interface | nét đứt mũi tên mở + «use», trỏ tới interface/supplier | `usage`, `requires` | như dependency |
| Provided interface | nét liền **không mũi tên** từ component tới ball (lollipop) | `provides` (hoặc `realization` tới interface lollipop) | `endArrow=none` |
| Guard (activity) | `[điều kiện]` trên luồng ra khỏi decision | `flow` + `guard` | nhãn giữa đường |

Multiplicity/role đặt sát đầu mút: `fromMult`, `toMult`, `fromRole`, `toRole` (vd `"1"`, `"0..*"`, `"1..*"`).

## Message trong sequence diagram

| Loại | Ký hiệu | `type` | style |
|---|---|---|---|
| Synchronous call | nét liền, **tam giác đặc** | `sync` | `endArrow=block;endFill=1` |
| Asynchronous | nét liền, mũi tên mở | `async` | `endArrow=open;endFill=0` |
| Reply / return | nét đứt, mũi tên mở | `reply` | `dashed=1;endArrow=open` |
| Create | nét đứt, mũi tên mở tới header đối tượng mới | `create` | lifeline mới bắt đầu thấp hơn |

- Lifeline: header `name:Class` hoặc `:Class`, **không gạch chân** (UML 2; gạch chân là instance
  specification của object diagram / UML 1.x); actor dùng hình người.
- Execution specification (thanh kích hoạt) là tuỳ chọn trong UML; script không vẽ để tránh chồng hình
  (COMET cũng thường bỏ qua ở mức phân tích).
- Combined fragment: khung `umlFrame` với toán tử `alt`, `opt`, `loop`, `par`, `break`, `critical`,
  `ref`...; operand phân tách bằng nét đứt, guard `[điều kiện]`.
- Message luôn **nằm ngang**; không vẽ chéo.

## Phần tử (vertex)

| UML | Ký hiệu | spec `type` |
|---|---|---|
| Actor | hình người, tên bên dưới | `actor` |
| Use case | ellipse | `usecase` |
| System boundary | hình chữ nhật chứa use case, tên ở trên | tự sinh (`"system"` ở top-level) |
| Class | 3 ngăn: tên (in đậm, căn giữa; *nghiêng* nếu abstract) / thuộc tính / thao tác | `class` |
| Interface | «interface» + tên | `interface` |
| Interface dạng ball (lollipop) | vòng tròn nhỏ, tên bên cạnh | `interface` + `notation: "lollipop"` |
| Enumeration | «enumeration» + literals | `enumeration` |
| Object / lifeline (communication, sequence) | `name:Class` hoặc `:Class`, không gạch chân (UML 2) | `object` |
| State | chữ nhật bo góc; ngăn activity `entry/`, `do/`, `exit/` | `state` |
| Composite state | state chứa state con | `state` + con có `"in"` |
| Initial | chấm tròn đặc | `initial` |
| Final | chấm tròn đặc trong vòng tròn | `final` |
| Flow final | vòng tròn có dấu X | `flowFinal` |
| Choice / decision / merge | hình thoi; decision ghi câu hỏi điều kiện bên trong (`question`) | `choice`, `decision`, `merge` |
| Junction | chấm đặc nhỏ | `junction` |
| Fork / join | thanh đen dày | `fork`, `join` |
| History | vòng tròn H / H* | `history`, `deephistory` |
| Action (activity) | chữ nhật bo góc (góc nhỏ, khác state bo tròn nhiều) | `action` |
| Activity partition (swimlane) | làn dọc (TB) / ngang (LR) có tiêu đề, xếp sát nhau | `partitions` + `partition` |
| Note | tờ giấy gập góc | `note` |
| Component | chữ nhật + biểu tượng component, «component» | `component` |
| Node / device / execution env. | khối hộp 3D | `node`, `device`, `executionEnvironment` |
| Artifact | chữ nhật + «artifact» | `artifact` |
| Package / subsystem | thư mục có tab | `package`, `subsystem` |

## Khung sơ đồ (diagram frame)

UML 2 khuyến nghị khung ngoài với nhãn ngũ giác ở góc trái trên: `uc`, `class`, `sd`, `stm`, `act`,
`cmp`, `deployment`, `pkg` + tên. Script tự thêm (tắt bằng `"frame": false`).

## Quy tắc trình bày

- Stereotype dùng dấu «guillemet», không dùng `<<…>>`.
- Tên lớp: danh từ số ít, viết hoa chữ cái đầu; thuộc tính `tên: Kiểu` (comet_check C1); thao tác
  `tên(tham số): Kiểu`.
- Association/aggregation/composition ghi multiplicity ở **cả hai đầu** (C2); association có tên (động từ,
  đọc theo chiều `from → to`) hoặc role.
- Visibility: `+` public, `-` private, `#` protected, `~` package.
- Không đặt nhãn đè lên hình hay đường khác; không để hai đường chồng khít nhau
  (validator báo lỗi).
- Chỗ hai đường cắt nhau dùng `jumpStyle=arc` để hiện "cầu nhảy".

## Activity diagram – quy tắc hợp lệ (comet_check A1–A6)

- Decision: 1 luồng vào, ≥ 2 luồng ra, **mỗi luồng ra có guard**, tối đa một `[else]` (A1). Câu hỏi điều kiện
  ghi trong hình thoi (`"question": "Đủ số dư?"`), guard là câu trả lời (`[Có]` / `[Không]`).
- Merge: ≥ 2 luồng vào, 1 luồng ra (không dùng để rẽ nhánh) (A4). Fork: 1 vào/≥ 2 ra; join: ≥ 2 vào/1 ra (A2).
- Initial: không có luồng vào, đúng 1 luồng ra. Activity final / flow final: không có luồng ra (A3).
- Mỗi action có luồng vào và luồng ra (không ngõ cụt) (A5).
- Action có **≥ 2 luồng vào** = join ngầm (UML 2.5: action chờ token trên *mọi* luồng vào → nhánh rẽ từ
  decision bị kẹt); **≥ 2 luồng ra** = fork ngầm. Gộp nhánh bằng `merge`, rẽ nhánh bằng `decision`, song song
  bằng `fork`/`join` (A6). Vòng lặp quay về một `merge` đặt trước action cần lặp.
- Swimlane: mỗi action nằm trong làn của tác nhân/đối tượng thực hiện nó (vd actor, hệ thống, hệ thống ngoài).
- Hình thoi có nhiều luồng cùng phía: script tự đưa luồng xa nhất ra/vào góc trái/phải.

## Statechart – quy tắc hợp lệ (comet_check S1–S5)

- Initial pseudostate: không có transition vào, đúng 1 transition ra, transition đó **không có event/guard**
  (chỉ được có action); mỗi region tối đa 1 initial (S1).
- Final state không có transition ra (S2).
- Choice/junction có ≥ 2 transition ra: mọi transition có guard, tối đa một `[else]` (S3).
- Mọi state tới được từ initial và có đường ra, trừ trạng thái kết thúc có chủ đích (S4).
- Cùng state, cùng event → guard phải phân biệt, nếu không state machine không tất định (S5).
- Nhãn transition: `Event [guard] / action1, action2`; self-transition (`from == to`) hợp lệ.

## ERD – ký pháp chân chim (comet_check E1–E3)

| Cardinality (`fromCard`/`toCard`) | Ký hiệu ở đầu đường nối | draw.io |
|---|---|---|
| `1` (đúng một) | hai gạch ‖ | `ERmandOne` |
| `0..1` (không hoặc một) | vòng + gạch | `ERzeroToOne` |
| `1..*` (một hoặc nhiều) | gạch + chân chim | `ERoneToMany` |
| `0..*` (không hoặc nhiều) | vòng + chân chim | `ERzeroToMany` |
| `many` / `n` | chân chim | `ERmany` |

- Entity: hộp tiêu đề xanh + 2 cột (khoá | tên: kiểu); cột PK gạch chân. Weak entity viền đậm.
- Identifying relationship nét liền; non-identifying (`identifying: false`) nét đứt.
- Mỗi entity có khoá chính (E1); mỗi relationship đủ cardinality 2 đầu và có tên động từ (E2); nhiều–nhiều nên
  tách bảng trung gian ở mức logic (E3). Bảng phía "nhiều" giữ FK.

## Screen flow (comet_check F1–F2)

- Màn hình (`screen`/`page`): khung bo góc, tiêu đề xanh, thân liệt kê thành phần; dialog/popup nền vàng, nét
  đứt, «dialog».
- Điều hướng: mũi tên liền, nhãn `thao tác [điều kiện]`. Decision (hình thoi có câu hỏi) khi hệ thống quyết định
  màn hình tiếp theo; nhánh ra có guard.
- Mọi màn hình tới được từ điểm bắt đầu (F1); điều hướng từ màn hình ghi thao tác kích hoạt (F2).

## Context diagram nghiệp vụ (comet_check B1–B3)

- Dạng DFD mức 0 / business context: **hình tròn** ở giữa = hệ thống / doanh nghiệp / quy trình nghiệp vụ; hình
  chữ nhật xung quanh = thực thể ngoài (người, tổ chức, bộ phận, hệ thống khác).
- Mũi tên thẳng, đầu tam giác đặc, ghi **tên dữ liệu** (danh từ: "Đơn đặt hàng", "Hoá đơn"), không ghi hành động.
- Đúng 1 hình tròn trung tâm (B1); mọi luồng có tên và nối trung tâm với bên ngoài (B2); thực thể ngoài không có
  luồng thì bỏ (B3). Không vẽ luồng giữa hai thực thể ngoài, không vẽ kho dữ liệu hay tiến trình con.
- Khác context diagram COMET (`context`): cái đó là class diagram «software system» / «external …» cho kỹ sư.
