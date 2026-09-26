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