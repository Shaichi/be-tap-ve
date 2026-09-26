# Canonical reconciliation

`scripts/comet_reconcile.py` treats the schema-v2 canonical model as the authoritative semantic contract and the current COMET specs as diagram projections.

## Check

```text
python scripts/comet_reconcile.py --help
```

In normal agent workflows the preferred entry point is:

```text
python scripts/comet_manifest.py "./uml/*.json" --canonical-model "./uml/system.model.json" -o "./uml/system"
```

The manifest then binds the authoritative `modelFingerprint`, the projected-spec fingerprint and the reconciliation report into the same consistency/repair snapshot.

## Drift rules

- M1: canonical concept has no projection.
- M2: projection contains a concept not declared canonically.
- M3: canonical concept identity/name drifted in a projection.
- M4: canonical relationship is missing from the projections.
- M5: projection contains an undeclared relationship.
- M6: canonical alias is missing from a projection (warning, not an identity error).

Each drift item carries canonical concept IDs plus affected diagram kinds/source specs when they can be determined from the projection model.

## Repair policy

Reconciliation is read-only. M1/M4 suggest adding the required projection to the correct source spec; M2/M5 suggest removing or explicitly declaring the semantic addition; M3/M6 suggest updating source representation. No business-semantic change is applied automatically.

## Source-of-truth loop

```text
canonical model
      ↓
reconcile
      ↓
projection drift
      ↓
repair plan
      ↓
source spec change
      ↓
regenerate .drawio
      ↓
reconcile + validate again
```
