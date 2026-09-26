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