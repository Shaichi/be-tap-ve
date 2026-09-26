# System consistency manifest

Be Tap Ve co the xuat ba artifact dong bo tu cung mot bo source spec:

```text
system.model.json
system.consistency.json
system.repair.json
```

Chay:

```bash
python scripts/comet_manifest.py "./uml/*.json" -o "./uml/system"
```

## `system.model.json`

Canonical semantic model schema v2. Day la semantic source snapshot: canonical concepts, diagram-local representations, semantic relationships, provenance, constraints, dependency graph va impact map.

## `system.consistency.json`

Manifest cua lan validation tuong ung voi dung `modelFingerprint`:

```json
{
  "schemaVersion": 1,
  "kind": "comet-consistency-manifest",
  "modelSchemaVersion": 2,
  "modelFingerprint": "sha256...",
  "summary": {
    "errors": 0,
    "warnings": 0,
    "infos": 0,
    "violations": 0
  },
  "violations": []
}
```

Moi violation lien ket toi `affectedConceptIds`, `impactedConceptIds`, `affectedDiagramKinds` va `regenerateSources`.

## `system.repair.json`

Repair plan machine-readable v2. Khong tu sua business semantics. Agent dung canonical concept + provenance de chon source spec, sau do regenerate draw.io tu source.

## Fingerprint

Ba artifact phai dung cung `modelFingerprint`. Neu fingerprint thay doi, consistency/repair manifest cu khong duoc xem la snapshot cua model moi.

## Luong agent

```text
Requirement / source specs
        ↓
system.model.json
        ↓
system.consistency.json
        ↓
system.repair.json
        ↓
source-spec repair
        ↓
regenerate diagrams
        ↓
validate again
```

Khong chinh semantic truc tiep trong `.drawio`; `.drawio` la derived artifact.
