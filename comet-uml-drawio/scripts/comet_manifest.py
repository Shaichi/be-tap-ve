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

from comet_check import check, load
from comet_model import build_model
from comet_plan import build_plan


def build_manifests(specs):
    model = build_model(specs, schema_version=2)
    errors, warnings, infos = check(specs)
    plan = build_plan(specs)

    violations = []
    impacted = set()
    regenerate = set()
    for step in plan["steps"]:
        affected = sorted(set(step.get("affectedConceptIds", [])))
        impacted.update(step.get("impactedConceptIds", []))
        regenerate.update(step.get("regenerateSources", []))
        violations.append({
            "id": step["id"],
            "rule": step["rule"],
            "severity": step["severity"],
            "message": step["message"],
            "sources": step.get("sources", []),
            "affectedConceptIds": affected,
            "impactedConceptIds": step.get("impactedConceptIds", []),
            "affectedDiagramKinds": step.get("affectedDiagramKinds", []),
            "regenerateSources": step.get("regenerateSources", []),
            "action": step.get("action", ""),
        })

    consistency = {
        "schemaVersion": 1,
        "kind": "comet-consistency-manifest",
        "modelSchemaVersion": model["schemaVersion"],
        "modelFingerprint": model["fingerprint"],
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
            "violations": len(violations),
        },
        "status": "clean" if not errors and not warnings else "violations",
        "violations": violations,
        "impactedConceptIds": sorted(impacted),
        "regenerateSources": sorted(regenerate),
        "dependencyGraph": {
            "nodeCount": len(model.get("dependencyGraph", {}).get("nodes", {})),
            "edgeCount": len(model.get("dependencyGraph", {}).get("edges", [])),
        },
    }

    return model, consistency, plan


def main():
    ap = argparse.ArgumentParser(description="Xuat system.model.json + consistency + repair manifests")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("-o", "--prefix", default="system",
                    help="prefix output (mac dinh: system)")
    a = ap.parse_args()

    specs = load(a.specs)
    model, consistency, plan = build_manifests(specs)
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
