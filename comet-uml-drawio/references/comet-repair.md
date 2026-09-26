# Repair plan của Bé Tập Vẽ

`scripts/comet_plan.py` biến kết quả `comet_check.py` thành một plan có cấu trúc. Nó **không tự sửa spec**;
agent dùng plan để quyết định sửa file nguồn nào và regenerate diagram nào.

## Chạy

```bash
python scripts/comet_plan.py "./uml/*.json" -o ./uml/<He_thong>.repair.json
```

## Schema

```json
{
  "schemaVersion": 1,
  "kind": "comet-repair-plan",
  "modelFingerprint": "...",
  "summary": {"errors": 0, "warnings": 0, "infos": 0, "steps": 0},
  "steps": []
}
```

Mỗi `step` gồm:

- `rule`: mã R/X/S/A/C/E/F/B/L
- `severity`: `error` / `warning` / `info`
- `message`: thông báo gốc từ validator
- `action`: hướng sửa theo luật
- `sources`: spec được xác định từ thông báo
- `affectedNodeIds`: canonical concepts liên quan nếu model truy được
- `regenerateSources`: danh sách source nên xem xét regenerate

## Repair loop

1. Chạy `comet_plan.py`.
2. Ưu tiên ERROR, sau đó WARN.
3. Sửa **spec nguồn**, không sửa `.drawio` trực tiếp.
4. Dựa vào `affectedNodeIds`/`regenerateSources` để xác định diagram bị ảnh hưởng.
5. Sinh lại `.drawio`, chạy `validate_drawio.py`.
6. Chạy lại `comet_check.py --strict`.
7. Lặp tới khi plan sạch.

`comet_plan.py` hiện là advisory; chưa tự chỉnh file để tránh sửa sai semantics nghiệp vụ.

## Repair plan v2 và impact propagation

Repair plan v2 giữ các trường v1 (`rule`, `severity`, `message`, `sources`, `affectedNodeIds`) nhưng bổ sung:

- `affectedConceptIds`: canonical concepts trực tiếp liên quan đến violation — concept trong spec vi phạm có tên (khớp nguyên từ, ưu tiên tên dài nhất) được nhắc trong message; message không nêu tên concept nào thì lấy cả spec.
- `directlyImpactedConceptIds`: concept kề trực tiếp (1 bước quan hệ) — nên xem trước khi sửa.
- `impactedConceptIds`: semantic dependency closure bị ảnh hưởng (thường gần hết bundle; dùng để tra cứu, không phải danh sách phải sửa).
- `affectedDiagramKinds`: loại diagram nên xem xét regenerate.
- `regenerateSources`: source specs cần regenerate trực tiếp.

Repair engine không tự kết luận business semantics. Agent nên dùng canonical concept + provenance để trả lời:

```
violation
  ↓
affectedConceptIds
  ↓
impactMap / dependencyGraph
  ↓
diagram-local representations
  ↓
source specs
  ↓
regenerate từ spec
```

Trong trường hợp ambiguity, giữ violation dưới dạng advisory và yêu cầu source khai báo
`conceptId`/`aliasOf`; không sửa tên hay quan hệ nghiệp vụ một cách mù quáng.
\n

## Canonical reconciliation rules

Khi có authoritative schema-v2 model, `comet_plan.py --canonical-model <model.json>`
có thể thêm các semantic drift steps:

- **M1** — canonical concept chưa có projection.
- **M2** — projection chứa concept chưa khai báo canonical.
- **M3** — identity/name của concept bị drift.
- **M4** — canonical relationship không xuất hiện trong projection.
- **M5** — projection chứa relationship chưa khai báo canonical.
- **M6** — canonical alias bị thiếu trong projection (WARN, không phải lỗi identity).

Các bước M1–M6 là advisory về business semantics: agent chỉ sửa source spec/model khi có
đủ provenance; không patch trực tiếp `.drawio`. `regenerateSources` và
`affectedDiagramKinds` được tính từ canonical impact graph.
\n