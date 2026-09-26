#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schema v2 semantic layer for Bé Tập Vẽ.

v2 deliberately separates:
- canonical concepts: stable system identity
- representations: diagram-local projections of a concept
- aliases: explicit alternate identity/name declarations
- relationships: semantic edges between canonical concepts
- provenance: source/diagram/local-element evidence
- constraints: machine-readable invariants for agents
- dependencyGraph / impactMap: system-wide change propagation
- derivedArtifacts: regeneration targets, never business-semantic edits

Backward compatibility is preserved by retaining the v1 nodes/links/coverage/impactMap
shape inside the v2 document and by providing upgrade_v1_model().
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque

from comet_check import norm, obj_class, st_of


SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1


def _display_bundle(bundle):
    return "default" if bundle == "__default__" else bundle


def _hash_id(prefix, *parts):
    raw = "|".join(str(p) for p in parts)
    return prefix + ":" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def canonical_concept_id(bundle, identity_key):
    """Stable v2 identity: bundle + explicit concept identity, or semantic name fallback."""
    return _hash_id("concept", bundle, norm(identity_key))


def _element_name(element):
    return element.get("name") or element.get("class") or element.get("id")


def _explicit_identity(element):
    value = element.get("conceptId") or element.get("semanticId") or element.get("modelId")
    if value:
        value = str(value)
        if value.startswith("concept:"):
            return ("concept-id", value)
        return ("concept-id", value)

    alias_of = element.get("aliasOf") or element.get("canonicalName")
    if alias_of:
        return ("alias-of", str(alias_of))

    return ("name", norm(_element_name(element)))


def _identity_id(bundle, element):
    kind, value = _explicit_identity(element)
    if kind == "concept-id" and value.startswith("concept:"):
        return value
    if kind == "concept-id":
        return canonical_concept_id(bundle, "id:" + value)
    if kind == "alias-of":
        target = value if str(value).startswith("concept:") else canonical_concept_id(bundle, "name:" + value)
        return target
    return canonical_concept_id(bundle, "name:" + value)


def _semantic_kinds(diagram, element):
    typ = norm(element.get("type"))
    role = st_of(element)
    out = set()

    if typ in ("actor", "external") or role.startswith("external "):
        out.add("party")
    elif typ == "usecase":
        out.add("usecase")
    elif role in {
        "entity", "database wrapper", "data abstraction",
        "boundary", "user interaction", "input", "output", "i/o",
        "io", "input/output", "device i/o", "proxy", "network interaction",
        "gui", "external system proxy", "control", "coordinator",
        "state dependent control", "state-dependent control", "timer",
        "application logic", "business logic", "algorithm", "service",
    }:
        out.add(role)
    elif typ in ("class", "interface", "entity"):
        out.add("domain-object")
    elif typ in ("component", "subsystem"):
        out.add("component")
    elif typ in ("node", "device", "executionenvironment", "artifact"):
        out.add("deployment-resource")
    elif typ:
        out.add(typ)

    if not out:
        out.add(norm(diagram) or "concept")
    return sorted(out)


def _source_name(source):
    return str(source or "").split("#", 1)[0]


def _spec_node_id(source):
    return _hash_id("spec", source)


def _representation_id(bundle, diagram, source, local_id, ordinal):
    return _hash_id("representation", bundle, diagram, source, local_id, ordinal)


def _relationship_id(bundle, kind, source_id, target_id, attrs):
    serial = json.dumps(attrs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _hash_id("relationship", bundle, kind, source_id, target_id, serial)


def _constraint_id(kind, *parts):
    return _hash_id("constraint", kind, *parts)


def _new_concept(bundle, name, cid):
    return {
        "id": cid,
        "bundle": _display_bundle(bundle),
        "kind": "canonical-concept",
        "name": str(name),
        "nameKey": norm(name),
        "aliases": [],
        "semanticKinds": [],
        "roles": [],
        "representations": [],
        "relationshipIds": [],
        "provenance": [],
        "legacyNodeIds": [],
    }


def _add_unique(items, value):
    if value not in items:
        items.append(value)


def _ensure_concept(concepts, bundle, cid, name):
    concept = concepts.setdefault(cid, _new_concept(bundle, name, cid))
    if not concept["name"] and name:
        concept["name"] = str(name)
    if norm(name) and norm(name) != concept["nameKey"]:
        _add_unique(concept["aliases"], str(name))
    return concept


def _add_provenance(concept, *, source, diagram, local_id=None, role="", representation_id=None):
    item = {
        "source": source,
        "diagram": diagram,
    }
    if local_id is not None:
        item["localId"] = str(local_id)
    if role:
        item["role"] = role
    if representation_id:
        item["representationId"] = representation_id
    if item not in concept["provenance"]:
        concept["provenance"].append(item)


def _dedupe_sort_model(model):
    for concept in model["concepts"].values():
        for key in ("aliases", "semanticKinds", "roles", "representations", "relationshipIds", "legacyNodeIds"):
            concept[key] = sorted(set(concept.get(key, [])))
        concept["provenance"] = sorted(
            concept.get("provenance", []),
            key=lambda x: (
                str(x.get("source", "")),
                str(x.get("diagram", "")),
                str(x.get("localId", "")),
                str(x.get("role", "")),
                str(x.get("representationId", "")),
            ),
        )
    for rep in model["representations"].values():
        if "aliases" in rep:
            rep["aliases"] = sorted(set(rep["aliases"]))
    return model


def _build_dependency_graph(concepts, representations, relationships, derived_artifacts):
    graph_nodes = {}
    graph_edges = []

    for cid, concept in sorted(concepts.items()):
        graph_nodes[cid] = {
            "id": cid,
            "kind": "concept",
            "name": concept["name"],
            "bundle": concept["bundle"],
        }

    for rid, rep in sorted(representations.items()):
        graph_nodes[rid] = {
            "id": rid,
            "kind": "representation",
            "diagram": rep["diagram"],
            "source": rep["source"],
            "conceptId": rep["conceptId"],
        }
        sid = _spec_node_id(rep["source"])
        graph_nodes.setdefault(sid, {
            "id": sid,
            "kind": "spec",
            "source": rep["source"],
        })
        graph_edges.append({
            "id": _hash_id("edge", sid, rid, "declares"),
            "source": sid,
            "target": rid,
            "kind": "declares",
        })
        graph_edges.append({
            "id": _hash_id("edge", rid, rep["conceptId"], "projects"),
            "source": rid,
            "target": rep["conceptId"],
            "kind": "projects-to",
        })

    for artifact in derived_artifacts:
        aid = artifact["id"]
        graph_nodes[aid] = {
            "id": aid,
            "kind": "derived-artifact",
            "artifactKind": artifact["kind"],
            "source": artifact["source"],
            "diagram": artifact["diagram"],
        }
        sid = _spec_node_id(artifact["source"])
        graph_nodes.setdefault(sid, {
            "id": sid,
            "kind": "spec",
            "source": artifact["source"],
        })
        graph_edges.append({
            "id": _hash_id("edge", sid, aid, "regenerates"),
            "source": sid,
            "target": aid,
            "kind": "regenerates",
        })

    for rel_id, rel in sorted(relationships.items()):
        graph_nodes[rel_id] = {
            "id": rel_id,
            "kind": "relationship",
            "relationshipKind": rel["kind"],
            "sourceConceptId": rel["sourceConceptId"],
            "targetConceptId": rel["targetConceptId"],
        }
        graph_edges.append({
            "id": _hash_id("edge", rel_id, rel["sourceConceptId"], "source"),
            "source": rel_id,
            "target": rel["sourceConceptId"],
            "kind": "relationship-source",
        })
        graph_edges.append({
            "id": _hash_id("edge", rel_id, rel["targetConceptId"], "target"),
            "source": rel_id,
            "target": rel["targetConceptId"],
            "kind": "relationship-target",
        })

    return {
        "nodes": {k: graph_nodes[k] for k in sorted(graph_nodes)},
        "edges": sorted(graph_edges, key=lambda x: x["id"]),
    }


def _concept_neighbors(relationships):
    neighbors = defaultdict(set)
    for rel in relationships.values():
        a, b = rel["sourceConceptId"], rel["targetConceptId"]
        if not a or not b or a == b:
            continue
        neighbors[a].add(b)
        neighbors[b].add(a)
    return neighbors


def _impact_map(concepts, representations, relationships, dependency_graph):
    neighbors = _concept_neighbors(relationships)
    rep_by_concept = defaultdict(list)
    for rid, rep in representations.items():
        rep_by_concept[rep["conceptId"]].append(rid)

    rel_by_concept = defaultdict(list)
    for rid, rel in relationships.items():
        rel_by_concept[rel["sourceConceptId"]].append(rid)
        rel_by_concept[rel["targetConceptId"]].append(rid)

    out = {}
    for cid, concept in sorted(concepts.items()):
        reachable = {cid}
        queue = deque([(cid, 0)])
        while queue:
            current, depth = queue.popleft()
            # Full semantic propagation is intentional; regenerated files are still
            # bounded by the source-level projection lists below.
            if depth >= len(concepts):
                continue
            for nxt in sorted(neighbors.get(current, ())):
                if nxt not in reachable:
                    reachable.add(nxt)
                    queue.append((nxt, depth + 1))

        impacted = sorted(reachable - {cid})
        direct = sorted(neighbors.get(cid, ()))
        source_self = sorted({
            representations[r]["source"]
            for r in rep_by_concept.get(cid, [])
        })
        source_impacted = sorted({
            representations[r]["source"]
            for other in reachable
            for r in rep_by_concept.get(other, [])
        })
        diagrams = sorted({
            representations[r]["diagram"]
            for other in reachable
            for r in rep_by_concept.get(other, [])
        })
        relationship_ids = sorted({
            rid
            for other in reachable
            for rid in rel_by_concept.get(other, [])
        })

        out[cid] = {
            "conceptId": cid,
            "name": concept["name"],
            "bundle": concept["bundle"],
            "representationIds": sorted(rep_by_concept.get(cid, [])),
            "diagramKinds": sorted({
                representations[r]["diagram"]
                for r in rep_by_concept.get(cid, [])
            }),
            "sources": source_self,
            "directConceptIds": direct,
            "impactedConceptIds": impacted,
            "impactedDiagramKinds": diagrams,
            "impactedSources": source_impacted,
            "regenerateSources": source_self,
            "relatedRelationshipIds": relationship_ids,
        }
    return out


def _declarative_constraints():
    rows = [
        ("canonical-identity", "system", "A concept has one canonical identity within a bundle; repeated diagrams are projections."),
        ("projection-provenance", "system", "Every diagram-local representation keeps source, diagram kind and canonical concept provenance."),
        ("bundle-isolation", "system", "Semantic identity and relationships never cross bundle namespaces."),
        ("explicit-alias", "system", "Use aliasOf/conceptId when equal display names represent different or intentionally aliased concepts."),
        ("mechanical-repair-only", "system", "Automatic repair may change mechanical projection data only; business semantics remain advisory."),
    ]
    return [
        {
            "id": _constraint_id(kind),
            "kind": kind,
            "scope": scope,
            "severity": "error" if kind in {"canonical-identity", "bundle-isolation"} else "info",
            "description": description,
        }
        for kind, scope, description in rows
    ]


def build_semantic_v2(v1_model, specs):
    """Upgrade a v1 model and enrich it with source-backed canonical concepts."""
    model = upgrade_v1_model(v1_model)

    # Source-backed representations are the authoritative bridge between canonical
    # identity and diagram-local syntax.
    identity_collisions = defaultdict(set)
    for spec in specs or []:
        bundle = norm(spec.get("bundle")) or "__default__"
        diagram = norm(spec.get("diagram"))
        source = str(spec.get("_src") or spec.get("diagram") or "diagram")
        elements = spec.get("elements", [])

        # Top-level semantic anchors which have no element entry.
        anchors = []
        if spec.get("useCase"):
            anchors.append({"id": "__usecase__", "name": spec.get("useCase"), "type": "usecase"})
        if spec.get("stateMachineOf"):
            anchors.append({"id": "__stateMachineOf__", "name": spec.get("stateMachineOf"), "type": "object"})
        if not elements and spec.get("title") and diagram in {"context", "bizcontext", "class", "component", "deployment", "erd"}:
            anchors.append({"id": "__title__", "name": spec.get("title"), "type": diagram})

        for ordinal, element in enumerate(elements + anchors):
            name = _element_name(element)
            if not name:
                continue
            cid = _identity_id(bundle, element)
            identity_collisions[(bundle, norm(name))].add(cid)
            concept = _ensure_concept(model["concepts"], bundle, cid, name)

            role = st_of(element)
            for semantic_kind in _semantic_kinds(diagram, element):
                _add_unique(concept["semanticKinds"], semantic_kind)
            if role:
                _add_unique(concept["roles"], role)

            local_id = element.get("id", name)
            rid = _representation_id(bundle, diagram, source, local_id, ordinal)
            rep = model["representations"].setdefault(rid, {
                "id": rid,
                "conceptId": cid,
                "bundle": _display_bundle(bundle),
                "diagram": diagram,
                "source": source,
                "localId": str(local_id),
                "localKind": norm(element.get("type")) or "derived",
                "name": str(name),
                "role": role,
                "derived": bool(element.get("id", None) is None and str(local_id).startswith("__")),
            })

            _add_unique(concept["representations"], rid)
            _add_provenance(
                concept,
                source=source,
                diagram=diagram,
                local_id=local_id,
                role=role,
                representation_id=rid,
            )

            aliases = element.get("aliases") or element.get("alias")
            if isinstance(aliases, str):
                aliases = [aliases]
            for alias in aliases or []:
                alias = str(alias).strip()
                if not alias:
                    continue
                _add_unique(concept["aliases"], alias)
                model["aliases"][_hash_id("alias", cid, norm(alias))] = {
                    "id": _hash_id("alias", cid, norm(alias)),
                    "kind": "name-alias",
                    "conceptId": cid,
                    "alias": alias,
                    "source": source,
                    "diagram": diagram,
                    "localId": str(local_id),
                }

            alias_of = element.get("aliasOf") or element.get("canonicalName")
            if alias_of:
                alias_id = _hash_id("alias", rid, str(alias_of))
                model["aliases"][alias_id] = {
                    "id": alias_id,
                    "kind": "representation-alias",
                    "conceptId": cid,
                    "alias": str(name),
                    "target": str(alias_of),
                    "source": source,
                    "diagram": diagram,
                    "localId": str(local_id),
                }

        # Every spec is a projection source even when it contains no elements.
        model["derivedArtifacts"].append({
            "id": _hash_id("artifact", source, diagram, "drawio"),
            "kind": "diagram-projection",
            "generator": "uml2drawio.py",
            "source": source,
            "sourceFile": _source_name(source),
            "diagram": diagram,
            "regenerate": "regenerate this diagram from source spec; never patch .drawio semantics",
        })

    # Map v1 node ids to canonical concepts. Source-backed explicit IDs win when
    # there is exactly one identity for a display name in the same bundle.
    node_to_concept = {}
    for nid, node in v1_model.get("nodes", {}).items():
        bundle = norm(node.get("bundle")) or "__default__"
        name = node.get("name")
        candidates = sorted(identity_collisions.get((bundle, norm(name)), set()))
        if len(candidates) == 1:
            cid = candidates[0]
        else:
            cid = canonical_concept_id(bundle, "name:" + norm(name))
        node_to_concept[nid] = cid
        concept = _ensure_concept(model["concepts"], bundle, cid, name)
        _add_unique(concept["legacyNodeIds"], nid)
        for kind in [node.get("kind")]:
            if kind:
                _add_unique(concept["semanticKinds"], str(kind))
        role = node.get("stereotype")
        if role:
            _add_unique(concept["roles"], str(role))

        for source in node.get("sources", []):
            diagram_kinds = node.get("diagramKinds") or [""]
            for diagram in diagram_kinds:
                _add_provenance(concept, source=source, diagram=diagram, role=str(role or ""))

    # Build canonical relationships from stable v1 relationships.
    for legacy_id, link in v1_model.get("links", {}).items():
        source_id = node_to_concept.get(link.get("source"))
        target_id = node_to_concept.get(link.get("target"))
        if not source_id or not target_id:
            continue
        attrs = {
            k: v for k, v in link.items()
            if k not in {"id", "bundle", "kind", "source", "target", "sources"}
        }
        rid = _relationship_id(
            norm(link.get("bundle")) or "__default__",
            str(link.get("kind") or "relationship"),
            source_id,
            target_id,
            attrs,
        )
        rel = model["relationships"].setdefault(rid, {
            "id": rid,
            "bundle": link.get("bundle", "default"),
            "kind": str(link.get("kind") or "relationship"),
            "sourceConceptId": source_id,
            "targetConceptId": target_id,
            "attributes": attrs,
            "sources": [],
            "legacyLinkIds": [],
        })
        rel["sources"] = sorted(set(rel.get("sources", []) + list(link.get("sources", []))))
        _add_unique(rel["legacyLinkIds"], legacy_id)
        _add_unique(model["concepts"][source_id]["relationshipIds"], rid)
        _add_unique(model["concepts"][target_id]["relationshipIds"], rid)

        if link.get("kind") == "actor-external-alias":
            alias_id = _hash_id("alias", source_id, target_id, "actor-external")
            model["aliases"][alias_id] = {
                "id": alias_id,
                "kind": "role-alias",
                "sourceConceptId": source_id,
                "targetConceptId": target_id,
                "semanticIdentity": link.get("semanticIdentity", ""),
                "source": list(link.get("sources", [])),
            }

    for (bundle, name_key), candidates in sorted(identity_collisions.items()):
        if len(candidates) > 1:
            cid = _hash_id("constraint", "identity-ambiguity", bundle, name_key)
            model["constraints"].append({
                "id": cid,
                "kind": "identity-ambiguity",
                "scope": "bundle",
                "severity": "warning",
                "bundle": _display_bundle(bundle),
                "nameKey": name_key,
                "candidateConceptIds": sorted(candidates),
                "description": "Equal display names map to multiple explicit concept identities; use aliasOf/conceptId deliberately.",
            })

    model["derivedArtifacts"] = [
        by_id for _, by_id in sorted({a["id"]: a for a in model["derivedArtifacts"]}.items())
    ]

    model["constraints"].extend(
        c for c in _declarative_constraints()
        if c["id"] not in {x["id"] for x in model["constraints"]}
    )

    _dedupe_sort_model(model)
    model["dependencyGraph"] = _build_dependency_graph(
        model["concepts"], model["representations"], model["relationships"], model["derivedArtifacts"]
    )
    concept_impact = _impact_map(
        model["concepts"], model["representations"], model["relationships"], model["dependencyGraph"]
    )
    model["conceptImpactMap"] = concept_impact
    # Compatibility surface: keep legacy node-id impact entries while v2 concept IDs
    # become the canonical keys for new tooling.
    legacy_impact = dict(v1_model.get("impactMap", {}))
    legacy_impact.update(concept_impact)
    model["impactMap"] = legacy_impact

    model["stats"].update({
        "concepts": len(model["concepts"]),
        "representations": len(model["representations"]),
        "relationships": len(model["relationships"]),
        "aliases": len(model["aliases"]),
        "constraints": len(model["constraints"]),
        "derivedArtifacts": len(model["derivedArtifacts"]),
    })
    model["sourceOfTruth"] = {
        "mode": "projection-bootstrap",
        "authoritativeSections": ["concepts", "aliases", "relationships", "constraints"],
        "derivedSections": [
            "nodes", "links", "representations", "coverage", "impactMap", "conceptImpactMap",
            "dependencyGraph", "derivedArtifacts", "stats"
        ],
        "projectionRule": "diagram specs are projections of canonical concepts; business semantics are not auto-repaired",
    }

    model["compatibility"]["sourceTruth"] = {
        "mode": "canonical-v2",
        "projectionRule": "diagrams are local representations; semantic changes belong in canonical concepts/specs",
        "legacyFieldsPreserved": True,
    }
    model["schemaVersion"] = SCHEMA_VERSION

    # Fingerprint excludes itself and uses canonical JSON ordering.
    model.pop("fingerprint", None)
    payload = json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    model["fingerprint"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return model


def upgrade_v1_model(v1_model):
    """Upgrade a v1 document without spec files.

    The result is intentionally conservative: it preserves all v1 data and creates
    canonical concepts from existing node names. Source-backed representations are
    enriched later by build_semantic_v2(..., specs).
    """
    concepts = {}
    node_map = {}
    for nid, node in sorted(v1_model.get("nodes", {}).items()):
        bundle = norm(node.get("bundle")) or "__default__"
        name = node.get("name") or node.get("id") or nid
        cid = canonical_concept_id(bundle, "name:" + norm(name))
        node_map[nid] = cid
        concept = _ensure_concept(concepts, bundle, cid, name)
        _add_unique(concept["legacyNodeIds"], nid)
        _add_unique(concept["semanticKinds"], str(node.get("kind") or "concept"))
        role = node.get("stereotype")
        if role:
            _add_unique(concept["roles"], str(role))
        for source in node.get("sources", []):
            for diagram in node.get("diagramKinds") or [""]:
                _add_provenance(concept, source=source, diagram=diagram, role=str(role or ""))

    relationships = {}
    aliases = {}
    for legacy_id, link in sorted(v1_model.get("links", {}).items()):
        a = node_map.get(link.get("source"))
        b = node_map.get(link.get("target"))
        if not a or not b:
            continue
        attrs = {
            k: v for k, v in link.items()
            if k not in {"id", "bundle", "kind", "source", "target", "sources"}
        }
        rid = _relationship_id(
            norm(link.get("bundle")) or "__default__",
            str(link.get("kind") or "relationship"),
            a,
            b,
            attrs,
        )
        rel = relationships.setdefault(rid, {
            "id": rid,
            "bundle": link.get("bundle", "default"),
            "kind": str(link.get("kind") or "relationship"),
            "sourceConceptId": a,
            "targetConceptId": b,
            "attributes": attrs,
            "sources": [],
            "legacyLinkIds": [],
        })
        rel["sources"] = sorted(set(rel["sources"] + list(link.get("sources", []))))
        _add_unique(rel["legacyLinkIds"], legacy_id)
        _add_unique(concepts[a]["relationshipIds"], rid)
        _add_unique(concepts[b]["relationshipIds"], rid)

        if rel["kind"] == "actor-external-alias":
            aid = _hash_id("alias", a, b, "actor-external")
            aliases[aid] = {
                "id": aid,
                "kind": "role-alias",
                "sourceConceptId": a,
                "targetConceptId": b,
                "semanticIdentity": link.get("semanticIdentity", ""),
                "source": list(link.get("sources", [])),
            }

    derived = []
    for source in sorted({
        source
        for node in v1_model.get("nodes", {}).values()
        for source in node.get("sources", [])
    }):
        diagrams = sorted({
            d
            for node in v1_model.get("nodes", {}).values()
            if source in node.get("sources", [])
            for d in node.get("diagramKinds", [])
        })
        for diagram in diagrams:
            derived.append({
                "id": _hash_id("artifact", source, diagram, "drawio"),
                "kind": "diagram-projection",
                "generator": "uml2drawio.py",
                "source": source,
                "sourceFile": _source_name(source),
                "diagram": diagram,
                "regenerate": "regenerate this diagram from source spec; never patch .drawio semantics",
            })

    out = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": v1_model.get("kind", "comet-semantic-model"),
        "bundles": v1_model.get("bundles", {}),
        "nodes": v1_model.get("nodes", {}),
        "links": v1_model.get("links", {}),
        "coverage": v1_model.get("coverage", {}),
        "impactMap": v1_model.get("impactMap", {}),
        "stats": dict(v1_model.get("stats", {})),
        "fingerprint": v1_model.get("fingerprint", ""),
        "concepts": concepts,
        "representations": {},
        "aliases": aliases,
        "relationships": relationships,
        "constraints": _declarative_constraints(),
        "dependencyGraph": {"nodes": {}, "edges": []},
        "derivedArtifacts": derived,
        "sourceOfTruth": {
            "mode": "legacy-upgrade",
            "authoritativeSections": ["concepts", "aliases", "relationships", "constraints"],
            "derivedSections": ["nodes", "links", "representations", "coverage", "impactMap", "conceptImpactMap", "dependencyGraph", "derivedArtifacts", "stats"],
            "projectionRule": "v1 model upgraded for compatibility; source specs should be reconciled before treating it as authoritative",
        },
        "compatibility": {
            "legacySchemaVersion": LEGACY_SCHEMA_VERSION,
            "upgradedFrom": LEGACY_SCHEMA_VERSION,
            "legacyNodeIdsStable": True,
            "legacyLinkIdsStable": True,
            "legacyFieldsPreserved": True,
        },
    }
    out["stats"].update({
        "concepts": len(concepts),
        "representations": 0,
        "relationships": len(relationships),
        "aliases": len(aliases),
        "constraints": len(out["constraints"]),
        "derivedArtifacts": len(derived),
    })
    out["dependencyGraph"] = _build_dependency_graph(
        out["concepts"], out["representations"], out["relationships"], out["derivedArtifacts"]
    )
    out["conceptImpactMap"] = _impact_map(
        out["concepts"], out["representations"], out["relationships"], out["dependencyGraph"]
    )
    legacy_impact = dict(v1_model.get("impactMap", {}))
    legacy_impact.update(out["conceptImpactMap"])
    out["impactMap"] = legacy_impact
    out.pop("fingerprint", None)
    payload = json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    out["fingerprint"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return out


def model_for_schema(model, schema_version):
    if int(schema_version) == LEGACY_SCHEMA_VERSION:
        return {k: v for k, v in model.items() if k not in {
            "concepts", "representations", "aliases", "relationships",
            "constraints", "dependencyGraph", "derivedArtifacts",
            "compatibility", "sourceOfTruth", "conceptImpactMap"
        }} | {"schemaVersion": LEGACY_SCHEMA_VERSION}
    if int(schema_version) != SCHEMA_VERSION:
        raise ValueError("Unsupported semantic model schema version: %s" % schema_version)
    return model
