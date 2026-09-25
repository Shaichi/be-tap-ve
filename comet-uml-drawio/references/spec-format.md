# Định dạng spec JSON cho `uml2drawio.py`

Một file có thể chứa: 1 spec (object), một mảng spec, hoặc `{"diagrams": [spec, ...]}`.
Mỗi spec → 1 trang draw.io. **Không có trường toạ độ** – bố cục hoàn toàn tự động. Thứ tự khai báo
phần tử/quan hệ được dùng để phá thế hoà khi xếp tầng/cột → khai báo theo thứ tự đọc mong muốn (vd lớp
trung tâm trước, quan hệ theo luồng chính trước).

## Trường cấp cao

| Trường | Bắt buộc | Ý nghĩa |
|---|---|---|
| `diagram` | ✔ | `usecase` · `context` · `class` · `communication` · `sequence` · `state` · `activity` · `component` · `deployment` · `package` |
| `title` | | Tên hiển thị trên khung (`uc Title`, `sd Title`...) |
| `useCase` | tương tác | Tên use case mà communication/sequence hiện thực (khớp R1) |
| `stateMachineOf` | state | Tên lớp «state dependent control» (khớp R7/R8) |
| `system` | usecase | Tên hệ thống trên system boundary (mặc định = `title`) |
| `direction` | | `TB` (trên→dưới) hoặc `LR` (trái→phải). Mặc định `LR` cho usecase/communication, `TB` còn lại |
| `frame` | | `false` để bỏ khung UML ngoài |
| `autonumber` | | communication: tự đánh số message nếu thiếu `seq` (mặc định true); sequence: mặc định false |
| `elements` | ✔ | Danh sách phần tử |
| `relations` | | Danh sách quan hệ (không dùng cho sequence) |
| `messages` | tương tác | Message (communication, sequence) |
| `fragments` | | Combined fragment (sequence) |
| `partitions` | | activity: danh sách làn (swimlane), chuỗi `"ATM"` hoặc `{"id": "atm", "name": "ATM"}`; thứ tự = thứ tự làn (TB: trái→phải, LR: trên→dưới) |

## Phần tử (`elements[]`)

Trường chung: `id` (mặc định = `name`; dùng trong `from`/`to`/`in`), `type`, `name`, `stereotype`
(chuỗi hoặc mảng; viết trần, không « »), `in` (id phần tử cha – lồng vào container),
`partition` (activity có `partitions`: id hoặc tên làn; phần tử không ghi sẽ theo làn của nút kề).

| `type` | Trường riêng |
|---|---|
| `actor` | `side`: `"left"`/`"right"` (usecase: mặc định trái nếu là đầu `from` của association; communication: `"right"` = cột cuối, dùng cho hệ thống ngoài/actor phụ), `primary`: true; `stereotype` tuỳ chọn: `human actor`, `system actor`, `input device actor`, `output device actor`, `I/O device actor`, `timer actor` |
| `usecase` | – (tự nằm trong system boundary) |
| `class`, `entity`, `external`, `system`, `datatype`, `box` | `attributes[]`, `operations[]`, `abstract`: true (tên in nghiêng), `compartments`: true (luôn vẽ ngăn rỗng) |
| `interface` | như class (tự thêm «interface»); `notation: "lollipop"` → vẽ dạng ball (vòng tròn nhỏ + tên), dùng trong component diagram |
| `enumeration` | `literals[]` |
| `object` | `class`: tên lớp → hiển thị `name:Class` (không có `name` → `:Class`); lifeline UML 2 không gạch chân |
| `state` | `activities[]` (vd `"entry / Display Welcome"`); con lồng qua `in` → composite state |
| `action` | (activity diagram) |
| `initial`, `final`, `activityFinal`, `flowFinal` | – |
| `choice`, `decision`, `merge` | `showName`: true để in `name` trong thoi |
| `junction` | – |
| `fork`, `join` | `length` (mặc định 120) |
| `history`, `deephistory` | – |
| `note` | `text` |
| `component` | stereotype mặc định «component»; có thể chứa phần tử con |
| `node`, `device`, `executionEnvironment` | stereotype mặc định «node»/«device»/«execution environment»; chứa component/artifact |
| `artifact` | – |
| `package`, `subsystem` | chứa phần tử con qua `in` |

Context diagram: đúng 1 `{"type": "system", "stereotype": "software system"}` và các lớp ngoài
`{"type": "external", "stereotype": ...}` với `"external input device"` / `"external output device"` /
`"external I/O device"` / `"external user"` / `"external system"` / `"external timer"` (`type: "class"`
cũng được chấp nhận). Association có `label` ("Inputs to", "Outputs to", "Interacts with", "Awakens")
và `fromMult`/`toMult`; xem `examples/atm_context.json`.

Communication/sequence: đối tượng `type: "object"`, `class`, `stereotype` theo COMET
(`user interaction`, `input`, `output`, `proxy`, `state dependent control`, `coordinator`,
`business logic`, `entity`...). Cột được xếp tự động theo nhóm stereotype.

## Quan hệ (`relations[]`)

Trường chung: `type`, `from`, `to`, `label`/`name`, `id`.

| `type` | Trường riêng | Hướng `from → to` |
|---|---|---|
| `association` | `fromMult`, `toMult`, `fromRole`, `toRole`, `navigable` | bất kỳ; usecase: actor → use case |
| `aggregation`, `composition` | như association | **toàn thể → bộ phận** |
| `generalization` | – | **con → cha** |
| `realization` | – | lớp → interface (tới interface dạng lollipop = `provides`) |
| `provides` | – | component → interface lollipop: nét liền không mũi tên (provided interface) |
| `requires`, `usage` | – | component/lớp → interface hoặc supplier: nét đứt mũi tên mở + «use» (required interface) |
| `dependency` | `stereotype` | client → supplier |
| `include` | – | base → included |
| `extend` | `condition` | extension → base |
| `transition`, `flow` | `event`, `guard`, `action` (chuỗi hoặc mảng), hoặc `label` viết sẵn `"Ev [g] / a"` | nguồn → đích (cho phép `from == to`: self-transition) |
| `anchor` | – | note → phần tử |
| `communicationpath`, `connector` | `stereotype`, mult | node ↔ node |
| `link` | – | (communication – thường tự sinh từ messages) |

Quan hệ có thể nối phần tử ở các cấp lồng khác nhau (vd component trong node A → artifact trong node B).

## Message (`messages[]`)

| Trường | Ý nghĩa |
|---|---|
| `from`, `to` | id phần tử (sequence: nếu id chưa khai báo sẽ tự tạo object `:id`) |
| `name` | tên message (bắt buộc trừ reply) |
| `seq` | số thứ tự: `"1"`, `"2"`, `"10a"`, `"1.2"`... |
| `type` | sequence: `sync` (mặc định) · `async` · `reply` · `create` |
| `id` | sequence: dùng để tham chiếu trong fragment |

- Communication: các message giữa cùng một cặp đối tượng gộp trên 1 link; mũi tên nhỏ →/←/↑/↓
  được chọn theo hướng thật sau bố cục.
- Sequence: thứ tự dọc = thứ tự trong mảng. `from == to` → self message.

## Fragment (`fragments[]`, chỉ sequence)

```json
{"type": "alt", "operands": [
  {"guard": "PIN valid", "from": "m10", "to": "m11"},
  {"guard": "else",      "from": "m12", "to": "m13"}]}
```
- `type`: `alt`, `opt`, `loop`, `par`, `break`, `critical`, `neg`, `ref`...; `label` để ghi đè
  (vd `"loop [1..3]"`).
- Dạng 1 operand rút gọn: `{"type": "loop", "guard": "more items", "from": "m3", "to": "m6"}`.
- Fragment lồng nhau được tự phát hiện nếu khoảng message nằm trọn trong fragment khác.

## Ví dụ ngắn

```json
{
  "diagram": "usecase", "title": "ATM", "system": "Banking System",
  "elements": [
    {"id": "cust", "type": "actor", "name": "ATM Customer"},
    {"id": "bank", "type": "actor", "name": "Bank Server", "side": "right"},
    {"id": "wd", "type": "usecase", "name": "Withdraw Funds"},
    {"id": "vp", "type": "usecase", "name": "Validate PIN"}
  ],
  "relations": [
    {"type": "association", "from": "cust", "to": "wd"},
    {"type": "association", "from": "wd", "to": "bank"},
    {"type": "include", "from": "wd", "to": "vp"}
  ]
}
```

### Activity diagram có swimlane

```json
{
  "diagram": "activity", "title": "Withdraw Funds",
  "partitions": ["ATM Customer", "ATM", "Bank Server"],
  "elements": [
    {"id": "start", "type": "initial", "partition": "ATM Customer"},
    {"id": "insert", "type": "action", "name": "Insert Card", "partition": "ATM Customer"},
    {"id": "validate", "type": "action", "name": "Validate PIN", "partition": "Bank Server"},
    {"id": "d1", "type": "decision", "partition": "Bank Server"},
    {"id": "menu", "type": "action", "name": "Display Menu", "partition": "ATM"},
    {"id": "invalid", "type": "action", "name": "Display Invalid PIN", "partition": "ATM"},
    {"id": "m1", "type": "merge", "partition": "ATM"},
    {"id": "eject", "type": "action", "name": "Eject Card", "partition": "ATM"},
    {"id": "end", "type": "activityFinal", "partition": "ATM Customer"}
  ],
  "relations": [
    {"type": "flow", "from": "start", "to": "insert"},
    {"type": "flow", "from": "insert", "to": "validate"},
    {"type": "flow", "from": "validate", "to": "d1"},
    {"type": "flow", "from": "d1", "to": "menu", "guard": "PIN valid"},
    {"type": "flow", "from": "d1", "to": "invalid", "guard": "PIN invalid"},
    {"type": "flow", "from": "menu", "to": "m1"},
    {"type": "flow", "from": "invalid", "to": "m1"},
    {"type": "flow", "from": "m1", "to": "eject"},
    {"type": "flow", "from": "eject", "to": "end"}
  ]
}
```
- Mọi luồng ra khỏi `decision` phải có `guard` (tối đa một `"else"`); song song dùng `fork` … `join`.
- Hai nhánh gặp lại nhau → **gộp bằng `merge`** rồi mới vào action: action có ≥ 2 luồng vào là join ngầm
  (chờ đủ mọi luồng → nhánh rẽ từ decision bị kẹt), comet_check báo A6. comet_check A1–A6 kiểm tra các luật này.
- Vòng lặp (luồng quay lui) được phép — quay về một `merge` đặt trước action cần lặp; script tự vẽ vào góc hình
  thoi, không đè luồng khác.

### Component diagram với provided/required interface

```json
{"id": "ibank", "type": "interface", "name": "IBankService", "notation": "lollipop"}
{"type": "provides", "from": "bankService", "to": "ibank"}
{"type": "requires", "from": "atmClient", "to": "ibank"}
```

Ví dụ đầy đủ cho mọi loại COMET: thư mục `examples/` (hệ ATM/Banking của Gomaa), gồm cả
`atm_activity_withdraw.json` (swimlane), `banking_component.json`, `banking_package.json`.
