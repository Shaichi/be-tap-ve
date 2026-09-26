#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcile diagram specs against an authoritative canonical semantic model."""
from __future__ import annotations

import json
from pathlib import Path

from comet_model import build_model


def _rel_key(rel):
    attrs = rel.get("attributes", {})
    return (
        rel.get("kind", ""),
        rel.get("bundle", "default"),
        rel.get("sourceConceptId", ""),
        rel.get("targetConceptId", ""),
        json.dumps(attrs, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def _impact_sources(model, concept_ids):
    sources = set()
    diagrams = set()
    for cid in concept_ids:
        impact = model.get("impactMap", {}).get(cid) or model.get("conceptImpactMap", {}).get(cid, {})
        sources.update(impact.get("regenerateSources", []))
        sources.update(impact.get("impactedSources", []))
        diagrams.update(impact.get("impactedDiagramKinds", []))
    return sorted(sources), sorted(diagrams)


def reconcile(canonical_model, projection_model):
    if canonical_model.get("schemaVersion") != 2:
        raise ValueError("Canonical model must use schemaVersion 2")
    if projection_model.get("schemaVersion") != 2:
        raise ValueError("Projection model must use schemaVersion 2")

    canonical = canonical_model.get("concepts", {})
    projected = projection_model.get("concepts", {})
    errors, warnings, infos = [], [], []
    drift = []

    for cid in sorted(set(canonical) - set(projected)):
        item = {
            "rule": "M1",
            "severity": "error",
            "kind": "missing-projection",
            "message": "Canonical concept '%s' has no diagram projection in current specs." % canonical[cid].get("name", cid),
            "affectedConceptIds": [cid],
            "suggestion": "Add a source-spec representation for the canonical concept; do not invent business semantics in .drawio.",
        }
        errors.append(item["message"]); drift.append(item)

    for cid in sorted(set(projected) - set(canonical)):
        item = {
            "rule": "M2",
            "severity": "error",
            "kind": "undeclared-projection",
            "message": "Projection contains undeclared canonical concept '%s'." % projected[cid].get("name", cid),
            "affectedConceptIds": [cid],
            "suggestion": "Declare the concept in the canonical model or remove the semantic projection from source specs.",
        }
        errors.append(item["message"]); drift.append(item)

    for cid in sorted(set(canonical) & set(projected)):
        left, right = canonical[cid], projected[cid]
        changed = []
        if left.get("nameKey") != right.get("nameKey"):
            changed.append("name")
        if left.get("bundle") != right.get("bundle"):
            changed.append("bundle")
        authoritative_aliases = set(left.get("aliases", []))
        projected_aliases = set(right.get("aliases", []))
        if not authoritative_aliases <= projected_aliases:
            changed.append("aliases")
        if changed:
            item = {
                "rule": "M3",
                "severity": "error",
                "kind": "concept-drift",
                "message": "Canonical concept '%s' drifted in projection fields: %s." % (left.get("name", cid), ", ".join(changed)),
                "affectedConceptIds": [cid],
                "suggestion": "Update the source spec to match canonical identity/name/alias declarations.",
            }
            errors.append(item["message"]); drift.append(item)

    canonical_rels = {_rel_key(r): r for r in canonical_model.get("relationships", {}).values()}
    projected_rels = {_rel_key(r): r for r in projection_model.get("relationships", {}).values()}
    for key in sorted(set(canonical_rels) - set(projected_rels)):
        rel = canonical_rels[key]
        ids = [rel.get("sourceConceptId"), rel.get("targetConceptId")]
        item = {
            "rule": "M4",
            "severity": "error",
            "kind": "missing-relationship-projection",
            "message": "Canonical relationship '%s' is missing from diagram projections." % rel.get("kind", "relationship"),
            "affectedConceptIds": sorted(x for x in ids if x),
            "suggestion": "Add the relationship to the source spec(s) that own the affected concepts, then regenerate.",
        }
        errors.append(item["message"]); drift.append(item)

    for key in sorted(set(projected_rels) - set(canonical_rels)):
        rel = projected_rels[key]
        ids = [rel.get("sourceConceptId"), rel.get("targetConceptId")]
        item = {
            "rule": "M5",
            "severity": "error",
            "kind": "undeclared-relationship-projection",
            "message": "Projection contains an undeclared relationship '%s'." % rel.get("kind", "relationship"),
            "affectedConceptIds": sorted(x for x in ids if x),
            "suggestion": "Declare the relationship in the canonical model or remove it from source specs.",
        }
        errors.append(item["message"]); drift.append(item)

    # Alias direction is authoritative, but extra observed aliases are not a business edit.
    for cid in sorted(set(canonical) & set(projected)):
        expected = set(canonical[cid].get("aliases", []))
        observed = set(projected[cid].get("aliases", []))
        missing = sorted(expected - observed)
        if missing and not any(d.get("rule") == "M3" and cid in d.get("affectedConceptIds", []) for d in drift):
            item = {
                "rule": "M6",
                "severity": "warning",
                "kind": "alias-drift",
                "message": "Canonical concept '%s' is missing aliases in projection: %s." % (canonical[cid].get("name", cid), ", ".join(missing)),
                "affectedConceptIds": [cid],
                "suggestion": "Add the declared alias to the source representation or model the explicit aliasOf relationship.",
            }
            warnings.append(item["message"]); drift.append(item)

    affected = sorted({cid for item in drift for cid in item.get("affectedConceptIds", [])})
    sources, diagrams = _impact_sources(projection_model, affected)
    for item in drift:
        item["regenerateSources"], item["affectedDiagramKinds"] = _impact_sources(projection_model, item.get("affectedConceptIds", []))
    return {
        "schemaVersion": 1,
        "kind": "comet-canonical-reconciliation",
        "status": "clean" if not errors and not warnings else "drift",
        "canonicalModelFingerprint": canonical_model.get("fingerprint"),
        "projectionFingerprint": projection_model.get("fingerprint"),
        "summary": {"errors": len(errors), "warnings": len(warnings), "infos": len(infos), "drift": len(drift)},
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "drift": drift,
        "affectedConceptIds": affected,
        "impactedSources": sources,
        "affectedDiagramKinds": diagrams,
    }


def load_model(path):
    model = json.loads(Path(path).read_text(encoding="utf-8"))
    if model.get("schemaVersion") != 2:
        raise ValueError("Canonical model file must use schemaVersion 2")
    return model


def reconcile_file(canonical_path, specs):
    canonical = load_model(canonical_path)
    projection = build_model(specs, schema_version=2)
    return reconcile(canonical, projection)