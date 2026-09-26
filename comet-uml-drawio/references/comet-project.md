# Canonical-first projection compiler

`scripts/comet_project.py` makes one canonical document (`kind: "comet-canonical-model"`) the single source of truth and compiles it into the per-diagram source specs. A concept is declared once. Every view references it with `{"ref": key}`. Renaming the concept in the canonical file renames it in every compiled spec and diagram.

```text
system.canonical.json ──compile──▶ specs/*.json ──uml2drawio──▶ *.drawio
        │
        └──model──▶ authoritative model v2 ──reconcile/manifest──▶ drift report
```

## CLI

```text
python scripts/comet_project.py bootstrap "./uml/*.json" -o ./uml/system.canonical.json [--bundle B]
python scripts/comet_project.py validate  ./uml/system.canonical.json
python scripts/comet_project.py compile   ./uml/system.canonical.json -o ./uml/ [--check]
python scripts/comet_project.py model     ./uml/system.canonical.json -o ./uml/system.model.json
```

- `bootstrap` builds the canonical file from the existing specs. It then compiles the result and compares it with the input. It prints `"roundTrip": "exact"` on a match, or `"mismatch"` plus the differing outputs and exit 1 otherwise. Mixed bundles are rejected; pass `--bundle` to pick one.
- `validate` runs the K rules. It exits 1 on any error.
- `compile` writes one spec per view to `OUTDIR/<view.output>`. With `--check` it writes nothing, prints `STALE <path>` for every missing or outdated spec, and exits 1. Use it in CI to catch hand-edited specs.
- `model` writes the authoritative semantic model v2. Its `sourceOfTruth.mode` is `"canonical"` and it carries `canonicalFingerprint`.

`comet_reconcile.py` and `comet_manifest.py --canonical-model` also accept the canonical file directly and convert it to the model v2 internally.

## Document format

```json
{
  "kind": "comet-canonical-model", "schemaVersion": 1, "bundle": "optional",
  "concepts": {
    "atm-customer": {"name": "ATM Customer", "kind": "actor", "conceptId": "concept:fbd1249afbb3"},
    "card-reader-interface": {"name": "Card Reader Interface", "kind": "class",
                              "conceptId": "concept:397428de8ef1", "stereotype": "input"}
  },
  "relationships": {
    "association:card-reader->banking-system": {"type": "association", "from": "card-reader",
      "to": "banking-system", "label": "Inputs to", "fromMult": "1", "toMult": "1"}
  },
  "interactions": {
    "validate-pin": {"messages": [{"seq": "1", "from": "cust", "to": "cri", "name": "Card Reader Input"}]}
  },
  "views": [
    {"id": "atm_usecase", "output": "atm_usecase.json", "diagram": "usecase",
     "system": {"ref": "banking-system"},
     "elements": [{"ref": "atm-customer", "id": "cust", "type": "actor"}],
     "relations": [{"ref": "association:atm-customer->withdraw-funds"}],
     "autoInclude": {"kinds": ["actor", "usecase"], "relationships": true}},
    {"id": "atm_comm_validate_pin", "output": "atm_comm_validate_pin.json", "diagram": "communication",
     "useCase": {"ref": "validate-pin"},
     "elements": [{"ref": "atm-customer", "id": "cust", "type": "actor"}],
     "interaction": "validate-pin", "messageOmit": ["id", "type"]}
  ]
}
```

### Concepts

- The key is a readable slug. It is the reference handle and is never used as semantic identity.
- `conceptId` is the stable identity. At bootstrap it equals the name-based id, so the semantic fingerprint does not change. It also stays the same after a rename. An explicit `conceptId`/`semanticId`/`modelId` in a source spec is kept as-is.
- Shared props are projected only into the diagram groups where they are meaningful:

| Prop | Projected into |
|---|---|
| `stereotype` | class, package, communication, sequence, component, deployment |
| `attributes`, `operations`, `abstract`, `literals` | class, package, context |
| `aliases` | all diagrams |

  At bootstrap each prop takes the majority value across the specs. A tie goes to the first spec in sorted source order.

### View elements

- `{"ref": key, "type", "id"?, ...overrides, "omit": [...], "nameField"?}`: a concept element. Local fields such as `id`, `type`, `partition` and `in` override the canonical props. `omit` drops a canonical prop in this view. `nameField` keeps a non-`name` label field.
- An inline dict without `ref` is a local element. Local elements are all elements of state and activity views, notes, pseudo-states, frames and fragments, and unnamed elements. They never become concepts.
- Local references (`in`, relation `from`/`to`, message `from`/`to`, `root`) may be written as `{"ref": key}` when the element has no explicit id.
- Spec-level fields `useCase`, `stateMachineOf`, `system`, `title`, `partitions` and element `partition` may also be `{"ref": key}`.

### Relationships

- Structural relationships only (every diagram except state, activity, communication and sequence). Behavioural flows and transitions stay local to their view.
- A view relation is `{"ref": rid, "id"?, "side"?, "style"?}`. `from`/`to` are needed only when the concept appears more than once in the view.
- `"relationsKey": "flows"` keeps the original `flows` key in the compiled spec.

### Interactions

A communication view and a sequence view of the same use case share one message list. Each view refers to it with `"interaction": iid`. `messageOmit` drops fields in one view; communication views omit `["id", "type"]` by default. Renaming a message changes both diagrams together, so R12 cannot drift.

### autoInclude

`{"kinds": [...], "relationships": true}` adds every concept of the listed kinds that the view does not already contain. With `"relationships": true` it also adds every relationship between concepts in the view whose type is allowed for that diagram. Relationships already used by a view of another diagram kind are not added. Bootstrap enables it only on usecase views, and only when doing so adds nothing, so round-trip stays exact. After that, a new actor or use case added to the canonical file appears in the use case diagram automatically.

## Compiled spec

- A concept element carries `conceptId`.
- A spec whose `useCase` / `stateMachineOf` is a ref carries `useCaseConceptId` / `stateMachineOfConceptId`. `comet_semantic` uses them so that the R1/R7/R8 anchors keep their identity after a rename.
- The output is deterministic. The same canonical file always compiles byte-identical specs.

## K rules

| Rule | Meaning |
|---|---|
| K1 | Document structure (kind, schemaVersion, field types, interaction without `messages` list) |
| K2 | Concept without `name` |
| K3 | Two concepts with the same semantic identity |
| K4 | Dangling ref (concept, relationship or interaction) |
| K5 | Relationship or message endpoint missing, or ambiguous because the concept appears more than once and there is no `from`/`to` |
| K6 | Duplicate local id in a view |
| K7 | Unsupported diagram, missing `output`, view bundle differs from the document bundle, or two views with the same output |
| K8 | Communication message endpoint has no element in the view |
| K9 | Relationship endpoint is not a concept |

## Workflow

1. Once, run `bootstrap` on the existing specs and check that `roundTrip` is `exact`.
2. From then on, edit only `system.canonical.json`.
3. Run `validate` → `compile -o ./uml/` → `uml2drawio.py` → `comet_check.py --strict`.
4. Run `comet_manifest.py "./uml/*.json" --canonical-model ./uml/system.canonical.json -o ./uml/system`. A clean reconciliation shows the specs are exact projections.
5. In CI, run `compile --check` to fail on a hand-edited spec.

Never repair semantics in the `.drawio` or in a compiled spec. Fix the canonical file and compile again.

## Limitations

- A canonical relationship not used by any view is not reported as M4. Only unprojected concepts are reported (M1).
- The use case `system` boundary is resolved by ref, but the compiled spec does not carry a conceptId for it.
- Bootstrap enables `autoInclude` only on usecase views. Other views can opt in by hand.
