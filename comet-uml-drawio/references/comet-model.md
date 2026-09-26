# Semantic model của Bé Tập Vẽ

`scripts/comet_model.py` tạo một **semantic index** trung gian từ các spec JSON. Đây chưa phải file nguồn thay thế spec;
nó là projection ổn định để validator, tooling và repair loop dùng chung.

## Chạy

```bash
python scripts/comet_model.py "./uml/*.json" -o ./uml/<He_thong>.model.json
```

Hoặc in JSON:

```bash
python scripts/comet_model.py "./uml/*.json"
```

`comet_check.py --json` cũng nhúng cùng model vào trường `model`.

## Schema

```json
{
  "schemaVersion": 1,
  "kind": "comet-semantic-model",
  "fingerprint": "sha256...",
  "bundles": {},
  "nodes": {},
  "links": {},
  "coverage": {},
  "impactMap": {},
  "stats": {}
}
```

### Canonical ID

Mỗi node/link có ID ổn định dựa trên:

`bundle + kind + tên đã chuẩn hóa`

Vì vậy cùng một concept được lặp lại giữa communication/sequence/state/class/ERD có thể hội tụ về cùng canonical ID
khi chúng có cùng bundle và semantic kind.

### Nodes

Ví dụ:

- `usecase`: use case
- `actor`: actor
- `boundary`, `control`, `entity`, `application-logic`
- `class`, `interface`
- `system`, `external`
- `component`, `subsystem`, `node`, `device`, `artifact`
- `state-machine`, `erd-relationship`

Mỗi node có `sources` và `diagramKinds` để truy về diagram tạo ra nó.

### Links

Các link semantic chính:

- `actor-uses`
- `context-flow`
- `class-relation`
- `erd-relation`
- `interaction-member`
- `message`
- `state-machine-of`
- `state-event`
- `state-action`
- `component-relation`
- `deployment-contained`
- `actor-external-alias`: nối semantic identity giữa actor của use case và external cùng tên trong context.

### Coverage

`coverage.<bundle>.useCases` cho biết use case nào có actor, interaction source và activity source.
`coverage.<bundle>.entities` và `components` cho biết concept xuất hiện ở những loại diagram nào.

### Impact map

`impactMap.<canonicalId>` trả về:

- `diagramKinds`: các loại diagram chứa concept
- `sources`: file spec liên quan
- `relatedLinkIds`: các liên kết semantic bị ảnh hưởng

Đây là nền cho phase repair: khi một concept đổi, agent có thể xác định trước những diagram/spec cần regenerate.

## Nguyên tắc

`bundle` là namespace. Hai hệ thống có cùng tên `Login` vẫn là hai canonical node khác nhau nếu bundle khác nhau.
Spec không có `bundle` dùng namespace `default` để giữ tương thích ngược.

## Schema v2 — canonical model là source of truth

Từ phase mới, `scripts/comet_model.py` xuất schema v2 theo mặc định. Schema v2 **giữ nguyên**
các trường v1 (`bundles`, `nodes`, `links`, `coverage`, `impactMap`, `stats`) để tool cũ vẫn đọc được,
đồng thời bổ sung:

- `concepts`: canonical concepts của system. ID ổn định theo `bundle + conceptId` nếu spec khai báo
  `conceptId`/`semanticId`/`modelId`; nếu không, fallback theo `bundle + tên đã chuẩn hoá`.
- `representations`: biểu diễn diagram-local của concept, gồm `source`, `diagram`, `localId`, `localKind`,
  `role`, `conceptId`.
- `aliases`: alias tên hoặc alias representation explicit (`aliases`, `aliasOf`) và alias actor↔external
  suy ra từ model cũ.
- `relationships`: quan hệ semantic giữa canonical concepts, không còn phụ thuộc ID local của diagram.
- `constraints`: các invariant của canonical layer và các ambiguity machine-readable.
- `dependencyGraph`: graph giữa spec → representation → concept → relationship → concept và artifact
  regeneration.
- `derivedArtifacts`: các projection artifact có thể regenerate từ source spec; không chỉnh semantic
  trực tiếp trong `.drawio`.
- `compatibility`: xác nhận legacy node/link IDs được giữ nguyên và schema v1/v2 có thể chuyển đổi.
- `impactMap`: phân biệt concept tự thân, concept ảnh hưởng trực tiếp và toàn bộ semantic closure;
  `regenerateSources` chỉ chứa source trực tiếp của concept để tránh regenerate mù.

### Canonical identity và alias

Tên giống nhau trong cùng bundle mặc định hội tụ về một canonical concept. Khi hai semantic concepts
cùng tên nhưng thực sự khác nhau, spec nên khai báo `conceptId` khác nhau; khi một representation chỉ
là tên/role thay thế, dùng `aliasOf` hoặc `aliases`.

Ví dụ:

```json
{
  "type": "external",
  "name": "Customer",
  "conceptId": "party.customer",
  "aliases": ["Client"]
}
```

Actor `Client`, external `Customer` và entity `Customer` có thể cùng trỏ vào một canonical concept
nếu chúng dùng cùng `conceptId`. Các representation vẫn giữ `localKind`/`role` riêng để X6 và các
validator không mất thông tin diagram-local.

### Backward compatibility

API Python mới:

```python
M.build_model_v1(specs)     # model schema v1
M.build_model(specs)        # model schema v2
M.model_for_schema(model, 1)
M.upgrade_v1_model(v1_model)
```

CLI:

```bash
python scripts/comet_model.py ... --schema-version 1
python scripts/comet_model.py ... --legacy
```

Fingerprint được tính trên canonical JSON, không có trường `fingerprint` trong payload đầu vào; vì vậy
thứ tự spec đầu vào không làm thay đổi fingerprint.
\n