#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Emit the machine-readable system manifest trio.

Given the same COMET source specs this creates:
  <prefix>.model.json
  <prefix>.consistency.json
  <prefix>.repair.json

The canonical v2 model is generated once and its fingerprint binds the two
operational manifests to the same semantic snapshot.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comet_check import load
from comet_model import build_model
from comet_plan import build_plan
from comet_reconcile import load_model


def build_manifests(specs, canonical_model=None):
    projection_model = build_model(specs, schema_version=2)
    plan = build_plan(specs, canonical_model=canonical_model)

    violations = []
    impacted = set()
    regenerate = set()
    for step in plan["steps"]:
        impacted.update(step.get("impactedConceptIds", []))
        regenerate.update(step.get("regenerateSources", []))
        violations.append({
            "id": step["id"],
            "rule": step["rule"],
            "severity": step["severity"],
            "message": step["message"],
            "sources": step.get("sources", []),
            "affectedConceptIds": step.get("affectedConceptIds", []),
            "impactedConceptIds": step.get("impactedConceptIds", []),
            "affectedDiagramKinds": step.get("affectedDiagramKinds", []),
            "regenerateSources": step.get("regenerateSources", []),
            "action": step.get("action", ""),
        })

    model = canonical_model if canonical_model is not None else projection_model
    consistency = {
        "schemaVersion": 1,
        "kind": "comet-consistency-manifest",
        "modelSchemaVersion": model["schemaVersion"],
        "modelFingerprint": model["fingerprint"],
        "projectionFingerprint": projection_model["fingerprint"],
        "canonicalSourceOfTruth": canonical_model is not None,
        "summary": {
            "errors": plan["summary"]["errors"],
            "warnings": plan["summary"]["warnings"],
            "infos": plan["summary"]["infos"],
            "violations": len(violations),
        },
        "status": "clean" if not plan["summary"]["errors"] and not plan["summary"]["warnings"] else "violations",
        "violations": violations,
        "impactedConceptIds": sorted(impacted),
        "regenerateSources": sorted(regenerate),
        "dependencyGraph": {
            "nodeCount": len(projection_model.get("dependencyGraph", {}).get("nodes", {})),
            "edgeCount": len(projection_model.get("dependencyGraph", {}).get("edges", [])),
        },
    }
    if "canonicalReconciliation" in plan:
        consistency["canonicalReconciliation"] = plan["canonicalReconciliation"]

    return model, consistency, plan


def main():
    ap = argparse.ArgumentParser(description="Xuat system.model.json + consistency + repair manifests")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("-o", "--prefix", default="system",
                    help="prefix output (mac dinh: system)")
    ap.add_argument("--canonical-model",
                    help="duong dan model v2 authoritative; spec chi duoc xem la projection cua model nay")
    a = ap.parse_args()

    specs = load(a.specs)
    canonical = load_model(a.canonical_model) if a.canonical_model else None
    model, consistency, plan = build_manifests(specs, canonical_model=canonical)
    prefix = Path(a.prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)

    paths = {
        "model": prefix.with_name(prefix.name + ".model.json"),
        "consistency": prefix.with_name(prefix.name + ".consistency.json"),
        "repair": prefix.with_name(prefix.name + ".repair.json"),
    }
    paths["model"].write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["consistency"].write_text(json.dumps(consistency, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["repair"].write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "model": str(paths["model"]),
        "consistency": str(paths["consistency"]),
        "repair": str(paths["repair"]),
        "modelFingerprint": model["fingerprint"],
        "status": consistency["status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
