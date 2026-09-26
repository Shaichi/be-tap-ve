# Bé Tập Vẽ — Agent Handoff / Development State

> Branch: `feat/diagram-consistency`
>
> Base: `main`
>
> PR: https://github.com/Shaichi/be-tap-ve/pull/1
>
> Scope: describe everything developed on this branch after branching from `main`, the current architecture/contracts, verified regression state, and the next implementation phase for a new coding agent.
>
> **Important:** this branch must **not** be merged into `main` unless the user explicitly asks.

---

## 1. Project goal

Bé Tập Vẽ generates COMET/UML diagram specifications and draw.io diagrams.

The branch started as a cross-diagram consistency effort. It has since evolved toward a system-wide semantic consistency engine whose long-term target is:

```text
requirements / source intent
        ↓
canonical semantic model   ← true system source of truth
        ↓
projection compiler
        ↓
diagram source specs
        ↓
draw.io diagrams
        ↓
R1–R14 + X1–X6 + semantic reconciliation
        ↓
impact-aware repair
        ↓
source-spec repair
        ↓
regenerate
        ↓
validate / reconcile again
```

The current branch has implemented most of the **semantic indexing, authority, reconciliation, impact propagation, repair planning, manifests, and regression infrastructure**.

The major remaining architectural step is a **true canonical-first projection compiler**. See Section 10.

---

## 2. Development completed after branching from main

### Phase A — Cross-diagram consistency X1–X6

Implemented system-level checks in:

- `comet-uml-drawio/scripts/comet_check.py`

The checks cover:

| Rule | Meaning |
|---|---|
| X1 | Interaction/activity references a use case that must exist in the matching use-case model |
| X2 | Actor attached to a use case must appear in the corresponding interaction |
| X3 | Statechart traces its `state dependent control` consistently |
| X4 | ERD entities must reconcile with entity classes |
| X5 | Component ↔ deployment consistency, including nested components with `in` |
| X6 | Structural-role conflicts across diagrams are detected |

These checks operate with the existing R1–R14 validation layer rather than replacing it.

### Phase B — Bundle isolation

A declared:

```json
{
  "bundle": "atm-banking"
}
```

acts as a semantic namespace.

Core checks now respect bundle boundaries for:

- R1
- R2
- R5
- R7
- R8
- R12
- R14
- X1–X6

Important compatibility rule:

- Specs without `bundle` still use the legacy `default` namespace.
- A concept with the same name in another bundle must not borrow evidence from the first bundle.
- Only `bundle` is a scope key. `system` / `project` / `systemName` are display fields and never scope a check.
- Without `bundle`, X4/X5 pair specs by title stem or ≥2 shared names. If exactly one spec exists on each side and they
  cannot be paired, an INFO suggests declaring a shared `bundle` instead of silently skipping.
- `--partial` downgrades "missing counterpart" findings (R1, R7, X2, X3, and X1 when the bundle has no use-case model)
  to INFO. A dangling reference inside a bundle that does have a use-case model stays WARN.

### Phase C — Machine-readable validation

`comet_check.py` now supports:

```bash
python scripts/comet_check.py --json ...
python scripts/comet_check.py --strict ...
```

The JSON output contains machine-readable summary/errors/warnings/infos plus the semantic model.

`--strict` treats warnings as failures.

This is intended for agents and CI, not only human inspection.

### Phase D — Canonical semantic model v1

The model work began with a projection-oriented semantic index in:

- `comet-uml-drawio/scripts/comet_model.py`

The model tracks:

- bundles
- semantic nodes
- semantic links
- coverage
- impact information
- source provenance
- deterministic fingerprints

The v1 implementation remains available for compatibility.

### Phase E — Canonical semantic model v2

The main semantic layer is now:

- `comet-uml-drawio/scripts/comet_semantic.py`

and `comet_model.py` exposes schema v2 by default.

Schema v2 deliberately separates:

1. **Canonical concepts**
2. **Diagram-local representations**
3. **Aliases**
4. **Semantic relationships**
5. **Provenance**
6. **Constraints**
7. **Dependency graph**
8. **Impact propagation**
9. **Derived artifacts**

The intent is to stop treating diagram-local IDs as system identity.

#### Stable identity

Preferred identity fields in source specs:

- `conceptId`
- `semanticId`
- `modelId`

Alias fields:

- `aliases`
- `aliasOf`
- `canonicalName`

Fallback identity is derived from normalized semantic name + bundle.

Canonical identity helper:

```python
canonical_concept_id(bundle, identity_key)
```

Canonical IDs are stable hashes and include the bundle namespace.

#### v1 compatibility

The existing v1 projection is still available:

```python
build_model_v1(specs)
build_model(specs)                 # v2 by default
model_for_schema(model, 1)
upgrade_v1_model(v1_model)
```

CLI compatibility:

```bash
python scripts/comet_model.py ... --schema-version 1
python scripts/comet_model.py ... --legacy
```

The v2 payload retains the legacy `nodes`, `links`, `bundles`, `coverage`, `impactMap`, and `stats` shape so older tooling does not immediately break.

### Phase F — Canonical authority + reconciliation

Added:

- `comet-uml-drawio/scripts/comet_reconcile.py`

This introduces a distinction between:

- an authoritative canonical semantic model
- current diagram specs treated as projections

Drift rules:

| Rule | Drift |
|---|---|
| M1 | Canonical concept has no projection |
| M2 | Projection contains undeclared canonical concept |
| M3 | Canonical identity/name/alias drift |
| M4 | Canonical relationship missing from projections |
| M5 | Projection contains undeclared relationship |
| M6 | Canonical alias missing from projection (warning; M3 covers only name/bundle identity drift) |

Reconciliation is **read-only**.

It must not invent business semantics.

It should point the agent back to the correct source spec / semantic model field.

Example:

```bash
python scripts/comet_reconcile.py \
  canonical.model.json \
  spec1.json spec2.json
```

### Phase G — Impact-aware repair planning

Enhanced:

- `comet-uml-drawio/scripts/comet_plan.py`

The repair planner now accepts an authoritative model:

```bash
python scripts/comet_plan.py ... --canonical-model system.model.json
```

The plan can propagate a violation from:

```text
rule violation
   ↓
affected source / local node
   ↓
canonical concept
   ↓
dependency / impact graph
   ↓
affected diagrams and source specs
```

Repair actions M1–M6 are included.

The plan exposes canonical impact metadata such as:

- `affectedConceptIds`: concepts named in the finding and present in the violating source; if the message names no
  concept (e.g. a count rule), every concept of that source
- `affectedNodeIds`: legacy nodes of those concepts restricted to the violating sources
- `directlyImpactedConceptIds`: one-hop neighbours from the dependency graph
- `impactedConceptIds`: full transitive closure (whole connected component, by design)
- affected diagram kinds and regenerate sources
- canonical reconciliation information

Concept-name matching uses whole-word regexes over `nameKey` + aliases, and keeps only the longest overlapping hit
("Query Account" does not also select "Account").

### Phase H — Machine-readable manifest trio

Added:

- `comet-uml-drawio/scripts/comet_manifest.py`

It emits:

```text
<prefix>.model.json
<prefix>.consistency.json
<prefix>.repair.json
```

Typical usage:

```bash
python scripts/comet_manifest.py "./uml/*.json" -o "./uml/system"
```

With an authoritative model:

```bash
python scripts/comet_manifest.py \
  "./uml/*.json" \
  --canonical-model "./uml/system.model.json" \
  -o "./uml/system"
```

The manifests are bound together with the model fingerprint.

The consistency manifest reports:

- model fingerprint
- projection fingerprint
- whether canonical authority was provided
- violation summary
- reconciliation output
- impacted concepts
- regenerate sources
- dependency graph counts

### Phase I — Documentation

Updated / added:

- `README.md` (repo root)
- `comet-uml-drawio/SKILL.md`
- `comet-uml-drawio/references/comet-model.md`
- `comet-uml-drawio/references/comet-repair.md`
- `comet-uml-drawio/references/comet-manifest.md`
- `comet-uml-drawio/references/comet-reconcile.md`
- `comet-uml-drawio/references/spec-format.md`

`spec-format.md` now documents semantic identity fields.

The docs explicitly distinguish:

```text
diagram-local id
        ≠
canonical semantic identity
```

### Phase J — CI / regression hardening

The CI workflow is:

- `.github/workflows/comet-tests.yml`

The CI compile list includes the new semantic/reconciliation/manifest scripts.

Regression coverage was expanded for:

- canonical identity
- aliases
- provenance
- bundle isolation
- deterministic fingerprinting
- dependency graph
- impact propagation
- v1 compatibility
- repair-plan canonical impact
- authoritative reconciliation
- manifest fingerprinting
- CLI behavior

Status after the review-fix pass (commits `884a1a6`, `95c0f6d`, `1757fd3` and the follow-up docs/R8 commit):

- **106 tests**, 1 skipped (PNG render, needs a browser)
- compile checks passed
- CI on PR #1 green

Review-fix pass summary:

- R8 messages print the original class name (not the `(scope, key)` tuple or the normalized key).
- X1/X3 guard per bundle and respect `--partial`; X4/X5 scope only by `bundle`.
- `coverage.activitySources` works for the default bundle.
- M6 alias drift is reachable (warning); M3 no longer checks aliases.
- Representation IDs use a per-localId occurrence counter, so element order does not change IDs or fingerprints.
- Interaction lifelines and message endpoints share one node kind (no duplicate `object` nodes).
- Default bundle spelled `""`, `default` or `__default__` maps to one namespace in v2 (ATM: 95 → 62 concepts).
- `comet_manifest.py` builds the semantic model once and reuses it for the repair plan.

Do not assume a newer change is green until its own CI run is verified.

### Phase K — Canonical-first projection compiler

Branch `feat/canonical-projection`. New module:

- `comet-uml-drawio/scripts/comet_project.py` (docs: `references/comet-project.md`)

One canonical document (`kind: "comet-canonical-model"`, `schemaVersion: 1`) holds `concepts`, `relationships`, `interactions` and `views`. `compile` turns it into every source spec deterministically.

- `bootstrap` lifts the existing specs into a canonical document and verifies the round-trip. It is exact for all 14 examples: 120 concepts, 141 relationships, 1 shared interaction, 14 views. The `.drawio` files rendered from the compiled specs are byte-identical to the originals.
- Concept `conceptId` = the name-based semantic id at bootstrap, so fingerprints are unchanged. Compiled specs carry `conceptId`, `useCaseConceptId` and `stateMachineOfConceptId`, so identity survives a rename.
- Communication and sequence views share one interaction message list, so R12 cannot drift.
- `autoInclude`, enabled by bootstrap on the single view of each family (usecase: actor/usecase, context/bizcontext: external, erd: entity). A new concept of that kind, plus its relationships, appears automatically.
- K1–K9 validation errors; K10/K11 warnings for declarations no view projects; `compile --check` for stale or hand-edited specs, and `model` exports an authoritative v2 model with `sourceOfTruth.mode = "canonical"`.
- `comet_reconcile.load_model` (and therefore `comet_manifest.py --canonical-model`) accepts the canonical document directly.

Related fixes:

- `comet_semantic`: concepts, relationships and aliases created by the v1 upgrade that no representation uses are pruned. They used to become ghosts when an explicit `conceptId` differed from the name-based id.
- `comet_reconcile` M3: when the canonical model has representations, a projection representation name that is not a canonical one is also drift. This catches a hand-edited compiled spec.

Status: **125 tests** OK locally (new `TestCanonicalProjection`, including a fuzz round-trip). CI compile list includes `comet_project.py`.

Also on PR #1: X2 reports actors missing from an interaction that has no actor lifeline, and R2/R5/R14 apply only when the spec's own bundle has the use case model, entity class model or context diagram.

---

## 3. Important current files

### Validation

```text
comet-uml-drawio/scripts/comet_check.py
```

Responsible for the existing R1–R14 validation layer, JSON/strict modes, and cross-diagram checks X1–X6.

### Semantic model

```text
comet-uml-drawio/scripts/comet_semantic.py
comet-uml-drawio/scripts/comet_model.py
```

Use these for canonical identity, semantic projection, relationships, provenance, impact, compatibility and fingerprints.

### Reconciliation

```text
comet-uml-drawio/scripts/comet_reconcile.py
```

Treat an explicit schema-v2 model as authority and compare current specs against it.

### Repair

```text
comet-uml-drawio/scripts/comet_plan.py
```

Turns validation/reconciliation findings into machine-readable repair steps.

### Manifest

```text
comet-uml-drawio/scripts/comet_manifest.py
```

Produces the model/consistency/repair artifact set.

### Tests

```text
comet-uml-drawio/tests/run_tests.py
```

This is the main regression suite.

---

## 4. Current semantic architecture

Schema v2 conceptually looks like:

```text
                ┌──────────────────────────┐
                │ authoritative concepts   │
                │ aliases / relationships  │
                │ constraints              │
                └────────────┬─────────────┘
                             │
                             ▼
                ┌──────────────────────────┐
                │ representations          │
                │ diagram-local projection │
                └────────────┬─────────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
         usecase          class/ERD        interaction
            │                │                │
            └────────────┬───┴────────────┬───┘
                         ▼                ▼
                   consistency       impact graph
                         │                │
                         └──────┬─────────┘
                                ▼
                         repair / regenerate
```

The important conceptual rule is:

> **Canonical concepts are system identity. Diagram representations are projections.**

A diagram-local ID may identify a local node, but must not be silently promoted to canonical system identity.

---

## 5. Source-of-truth status right now

This is the most important caveat for the next agent.

The current generated v2 model is still capable of being created from existing source specs. Its metadata therefore identifies it as a bootstrap snapshot rather than proof that canonical-first generation is fully implemented.

The model distinguishes authoritative and derived areas through `sourceOfTruth`.

Typical bootstrap state:

```json
{
  "sourceOfTruth": {
    "mode": "projection-bootstrap",
    "authoritativeSections": [
      "concepts",
      "aliases",
      "relationships",
      "constraints"
    ],
    "derivedSections": [
      "nodes",
      "links",
      "representations",
      "coverage",
      "impactMap",
      "conceptImpactMap",
      "dependencyGraph",
      "derivedArtifacts",
      "stats"
    ]
  }
}
```

This means:

- The semantic model can now be edited/treated as authority for reconciliation and repair.
- It is **not yet** a full compiler input from which every source spec can be regenerated.
- Existing specs are still the place from which many diagram-specific details are initially derived.

Update (Phase K): `comet_project.py` now provides the canonical-first path. A project that has a `system.canonical.json` should edit that file and compile. Its `model` output uses `sourceOfTruth.mode = "canonical"`. Projects without a canonical document still use the bootstrap flow above.

---

## 6. Non-negotiable invariants for the next agent

1. Preserve existing R1–R14 behavior.
2. Preserve X1–X6 behavior.
3. Preserve bundle isolation.
4. Preserve v1 compatibility unless the user explicitly requests a breaking change.
5. Preserve deterministic fingerprints.
6. Never use diagram-local `id` as canonical identity by accident.
7. Never edit business semantics directly inside generated `.drawio` output as a repair strategy.
8. Prefer repairing the canonical model or source spec, then regenerate.
9. Keep semantic changes explicit; ambiguous business-semantic changes should remain advisory.
10. Do not use one bundle's evidence to validate another bundle.
11. Every new automated repair must be explainable through provenance/impact data.
12. Keep manifests internally consistent by fingerprint.

---

## 7. Recommended canonical-first target architecture

The next phase should turn the canonical model into an actual source of truth:

```text
requirements / authoring input
          ↓
  authoritative system.model.json
          ↓
  canonical model validator
          ↓
  projection compiler
          ↓
  generated source specs
          ↓
  existing diagram generators
          ↓
  .drawio
```

The projection compiler should be deterministic.

Suggested responsibility split:

```text
comet_semantic.py
    canonical schema / identity / graph primitives

comet_model.py
    compatibility / model serialization

NEW compiler module
    canonical model → diagram source specs

comet_check.py
    R1–R14 + X1–X6 validation

comet_reconcile.py
    authoritative canonical model ↔ projections

comet_plan.py
    repair plan + impact propagation

comet_manifest.py
    reproducible machine-readable snapshot
```

A possible next script name is:

```text
scripts/comet_project.py
```

but the exact name is up to the next agent.

---

## 8. What the projection compiler must eventually solve

The compiler should be able to take canonical concepts and relationships and deterministically produce the source specs required by the existing diagram generator.

At minimum it should define how canonical semantics project into:

- use-case diagram
- context diagram
- class diagram
- communication / sequence diagram
- statechart
- activity diagram
- ERD
- component diagram
- deployment diagram
- screen/site-map style diagrams where supported by the project

The important distinction is:

```text
canonical semantic fact
        ↓
diagram-specific representation
```

not:

```text
diagram-specific representation
        ↓
guessed canonical fact
```

The compiler must preserve enough diagram-local information for existing R rules to remain meaningful.

---

## 9. Recommended canonical model additions before compiling

Before implementing broad generation, inspect whether the canonical model explicitly represents the following instead of reconstructing them indirectly:

- actor ↔ use case participation
- use-case interaction membership
- messages and their endpoints
- message ordering / sequence
- state machine ownership
- states / transitions / events / guards / actions
- class inheritance / association / aggregation / composition
- ERD entities / attributes / relationships / cardinalities
- component hierarchy
- component relationships
- deployment nodes / artifacts / containment
- context system boundary / external parties / flows
- activity control-flow semantics
- screen hierarchy / flow where applicable

If a concept is only represented in a legacy `nodes` or `links` compatibility section, consider promoting it into an explicit canonical structure before relying on it for compilation.

---

## 10. Repair loop expected from the next phase

The intended loop is:

```text
1. Load authoritative canonical model
2. Validate canonical constraints
3. Compile projections into source specs
4. Generate diagrams
5. Run R1–R14
6. Run X1–X6
7. Run reconciliation M1–M6
8. Build impact-aware repair plan
9. Repair canonical/source semantic data
10. Recompile
11. Regenerate
12. Validate again
13. Emit manifest trio
```

A repair should not mutate a generated `.drawio` file as the semantic source.

For ambiguous changes, the engine should say what is inconsistent and what source concept/spec is implicated, rather than inventing a business rule.

---

## 11. CLI compatibility expected by agents

Existing important commands include:

```bash
# Validate
python scripts/comet_check.py ...
python scripts/comet_check.py --json ...
python scripts/comet_check.py --strict ...

# Generate semantic model
python scripts/comet_model.py ...
python scripts/comet_model.py ... --schema-version 1
python scripts/comet_model.py ... --schema-version 2
python scripts/comet_model.py ... --legacy

# Reconcile against authority
python scripts/comet_reconcile.py canonical.model.json spec1.json spec2.json

# Repair plan
python scripts/comet_plan.py ... --canonical-model canonical.model.json

# Full machine-readable snapshot
python scripts/comet_manifest.py \
  "specs/*.json" \
  --canonical-model canonical.model.json \
  -o system
```

---

## 12. How the next agent should start

1. Read this handoff first.
2. Read:
   - `references/comet-model.md`
   - `references/comet-reconcile.md`
   - `references/comet-repair.md`
   - `references/spec-format.md`
3. Inspect:
   - `scripts/comet_semantic.py`
   - `scripts/comet_model.py`
   - `scripts/comet_reconcile.py`
   - `scripts/comet_plan.py`
   - `scripts/comet_check.py`
4. Run the full regression suite before modifying behavior.
5. Treat the current branch as a working feature branch; do not merge to `main`.
6. Implement the canonical-first projection compiler incrementally, preserving the existing validators and compatibility contracts.
7. Add regression tests before changing broad generation behavior.
8. Re-run CI and verify the **new commit's** workflow status before declaring success.

---

## 13. Current stopping point

The branch has successfully moved from:

```text
pairwise diagram checks
```

to:

```text
system-wide semantic indexing
+ canonical identity
+ bundle isolation
+ provenance
+ dependency graph
+ impact propagation
+ authoritative reconciliation
+ repair planning
+ machine-readable manifests
+ CI regression coverage
```

Phase K added the missing step:

```text
system.canonical.json
        ↓  comet_project.py validate / compile
all source specs (round-trip exact on every example)
        ↓  uml2drawio.py
all diagrams
```

Next candidates:

- Authoring helpers (add concept, rename) on top of the canonical document.

---

## 14. Safety / change-control note

This branch is intended to be developed with an agent in the loop.

Before making architectural changes, compare the intended change against:

- R1–R14
- X1–X6
- M1–M6
- bundle isolation
- v1 compatibility
- fingerprint determinism
- source-of-truth boundary

Avoid broad rewrites when an incremental compiler/projection layer can be added around the existing semantic model.

**Do not merge into `main` unless explicitly instructed by the user.**
