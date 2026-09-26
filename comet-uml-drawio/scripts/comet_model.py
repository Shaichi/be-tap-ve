#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comet_model.py - Trich xuat canonical semantic model tu mot bo COMET spec.

Model la semantic index trung gian, khong co toa do/draw.io:
  - nodes: use case, actor, boundary/control/entity/class, component, deployment...
  - links: actor-uses, interaction message, state-machine-of, entity/class,
           component relation, deployment containment...
  - provenance: spec nao dong gop cho concept/link
  - id: canonical id on dinh theo bundle + kind + ten chuan hoa
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from comet_check import lifelines, load, mname, norm, obj_class, st_of


def bundle_of(spec):
    return norm(spec.get("bundle")) or "__default__"


def display_bundle(bundle):
    return "default" if bundle == "__default__" else bundle


def canonical_id(bundle, kind, name):
    raw = "%s:%s:%s" % (bundle, kind, norm(name))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return "%s:%s" % (kind, digest)


def add_node(nodes, bundle, kind, name, spec, **fields):
    if not name:
        return None
    name = str(name)
    nid = canonical_id(bundle, kind, name)
    node = nodes.setdefault(nid, {
        "id": nid,
        "bundle": display_bundle(bundle),
        "kind": kind,
        "name": name,
        "nameKey": norm(name),
        "sources": [],
    })
    src = spec.get("_src")
    if src and src not in node["sources"]:
        node["sources"].append(src)
    diagram = norm(spec.get("diagram"))
    if diagram:
        node.setdefault("diagramKinds", [])
        if diagram not in node["diagramKinds"]:
            node["diagramKinds"].append(diagram)
    for k, v in fields.items():
        if v in (None, "", [], {}):
            continue
        if isinstance(v, list):
            node.setdefault(k, [])
            for x in v:
                if x not in node[k]:
                    node[k].append(x)
        else:
            node[k] = v
    return nid


def add_link(links, bundle, kind, source, target, spec, **fields):
    if not source or not target:
        return
    serialized = json.dumps(fields, sort_keys=True, ensure_ascii=False)
    key = (bundle, kind, source, target, serialized)
    link = links.get(key)
    if link is None:
        link = {
            "id": canonical_id(
                bundle, "link",
                "%s|%s|%s|%s" % (kind, source, target, serialized),
            ),
            "bundle": display_bundle(bundle),
            "kind": kind,
            "source": source,
            "target": target,
            "sources": [],
        }
        link.update(fields)
        links[key] = link
    src = spec.get("_src")
    if src and src not in link["sources"]:
        link["sources"].append(src)


def build_model(specs):
    nodes, links = {}, {}
    activity_sources = defaultdict(list)
    bundle_names = defaultdict(lambda: {"nodeIds": [], "linkIds": []})

    for spec in specs:
        bundle = bundle_of(spec)
        diagram = norm(spec.get("diagram"))
        spec.setdefault("_src", str(spec.get("diagram") or "diagram"))

        if diagram == "usecase":
            els = {str(e.get("id", e.get("name"))): e for e in spec.get("elements", [])}
            for e in spec.get("elements", []):
                typ = norm(e.get("type"))
                name = e.get("name", e.get("id"))
                if typ == "usecase":
                    add_node(nodes, bundle, "usecase", name, spec)
                elif typ == "actor":
                    add_node(nodes, bundle, "actor", name, spec, stereotype=st_of(e))
            for r in spec.get("relations", []):
                a, b = els.get(str(r.get("from"))), els.get(str(r.get("to")))
                if not a or not b:
                    continue
                if a.get("type") == "actor" and b.get("type") == "usecase":
                    aid = add_node(nodes, bundle, "actor", a.get("name", a.get("id")), spec)
                    uid = add_node(nodes, bundle, "usecase", b.get("name", b.get("id")), spec)
                    add_link(links, bundle, "actor-uses", aid, uid, spec, relation=norm(r.get("type", "association")))
                elif b.get("type") == "actor" and a.get("type") == "usecase":
                    aid = add_node(nodes, bundle, "actor", b.get("name", b.get("id")), spec)
                    uid = add_node(nodes, bundle, "usecase", a.get("name", a.get("id")), spec)
                    add_link(links, bundle, "actor-uses", aid, uid, spec, relation=norm(r.get("type", "association")))

        if diagram in ("context", "bizcontext"):
            for e in spec.get("elements", []):
                typ = norm(e.get("type"))
                name = e.get("name", e.get("id"))
                if typ == "system" or st_of(e) == "software system":
                    add_node(nodes, bundle, "system", name, spec, role=st_of(e) or "system")
                elif typ in ("external", "class"):
                    add_node(nodes, bundle, "external", name, spec, role=st_of(e) or "external")
            els = {str(e.get("id", e.get("name"))): e for e in spec.get("elements", [])}
            for r in spec.get("relations", spec.get("flows", [])):
                a, b = els.get(str(r.get("from"))), els.get(str(r.get("to")))
                if not a or not b:
                    continue
                if a.get("type") == "system":
                    source = add_node(nodes, bundle, "system", a.get("name", a.get("id")), spec)
                    target = add_node(nodes, bundle, "external", b.get("name", b.get("id")), spec)
                elif b.get("type") == "system":
                    source = add_node(nodes, bundle, "external", a.get("name", a.get("id")), spec)
                    target = add_node(nodes, bundle, "system", b.get("name", b.get("id")), spec)
                else:
                    continue
                add_link(links, bundle, "context-flow", source, target, spec,
                         label=r.get("label") or r.get("name") or "")

        if diagram == "class":
            els = {str(e.get("id", e.get("name"))): e for e in spec.get("elements", [])}
            for e in spec.get("elements", []):
                typ = norm(e.get("type"))
                name = e.get("name", e.get("id"))
                if not name or typ in ("note", "enumeration"):
                    continue
                role = st_of(e)
                kind = "entity" if role == "entity" else ("interface" if typ == "interface" else "class")
                add_node(nodes, bundle, kind, name, spec,
                         stereotype=role, attributes=e.get("attributes") or [])
            for r in spec.get("relations", []):
                a, b = els.get(str(r.get("from"))), els.get(str(r.get("to")))
                if not a or not b:
                    continue
                ak = "entity" if st_of(a) == "entity" else "class"
                bk = "entity" if st_of(b) == "entity" else "class"
                aid = add_node(nodes, bundle, ak, a.get("name", a.get("id")), spec)
                bid = add_node(nodes, bundle, bk, b.get("name", b.get("id")), spec)
                add_link(links, bundle, "class-relation", aid, bid, spec,
                         relation=norm(r.get("type", "association")),
                         label=r.get("label") or r.get("name") or "")

        if diagram == "erd":
            els = {str(e.get("id", e.get("name"))): e for e in spec.get("elements", [])}
            for e in spec.get("elements", []):
                typ = norm(e.get("type"))
                if typ == "entity":
                    add_node(nodes, bundle, "entity", e.get("name", e.get("id")), spec)
                elif typ == "relationship":
                    add_node(nodes, bundle, "erd-relationship", e.get("name", e.get("id")), spec)
            for r in spec.get("relations", []):
                a, b = els.get(str(r.get("from"))), els.get(str(r.get("to")))
                if not a or not b:
                    continue
                ak = "erd-relationship" if norm(a.get("type")) == "relationship" else "entity"
                bk = "erd-relationship" if norm(b.get("type")) == "relationship" else "entity"
                aid = add_node(nodes, bundle, ak, a.get("name", a.get("id")), spec)
                bid = add_node(nodes, bundle, bk, b.get("name", b.get("id")), spec)
                add_link(links, bundle, "erd-relation", aid, bid, spec,
                         name=r.get("name") or r.get("label") or "",
                         fromCard=r.get("fromCard") or r.get("card") or "",
                         toCard=r.get("toCard") or "")

        if diagram in ("communication", "sequence"):
            uc = spec.get("useCase") or spec.get("title")
            ucid = add_node(nodes, bundle, "usecase", uc, spec) if uc else None
            els = lifelines(spec)

            for e in spec.get("elements", []):
                typ = norm(e.get("type"))
                name = e.get("name") if typ == "actor" else obj_class(e)
                if not name:
                    continue
                if typ == "actor":
                    kind, role = "actor", "actor"
                else:
                    st = st_of(e)
                    if st in {"boundary", "user interaction", "input", "output", "i/o", "proxy", "gui"}:
                        kind = "boundary"
                    elif st in {"control", "coordinator", "state dependent control", "state-dependent control", "timer"}:
                        kind = "control"
                    elif st in {"entity", "database wrapper", "data abstraction"}:
                        kind = "entity"
                    else:
                        kind = "application-logic"
                    role = st
                nid = add_node(nodes, bundle, kind, name, spec, stereotype=role)
                if ucid and kind in {"actor", "control", "boundary", "entity", "application-logic"}:
                    add_link(links, bundle, "interaction-member", ucid, nid, spec, useCase=uc)
                if kind == "control" and role in SDCROLES:
                    add_node(nodes, bundle, "state-machine", name, spec, stateMachineOf=name)

            for m in spec.get("messages", []):
                a, b = els.get(str(m.get("from"))), els.get(str(m.get("to")))
                if not a or not b:
                    continue

                def endpoint(e):
                    if e.get("type") == "actor":
                        return add_node(nodes, bundle, "actor", e.get("name", e.get("id")), spec)
                    return add_node(nodes, bundle, "object", obj_class(e), spec, stereotype=st_of(e))

                source, target = endpoint(a), endpoint(b)
                add_link(
                    links, bundle, "message", source, target, spec,
                    useCase=uc,
                    name=m.get("name") or "",
                    nameKey=mname(m.get("name") or ""),
                    seq=str(m.get("seq") or ""),
                    type=str(m.get("type") or "sync"),
                )

        if diagram == "state":
            cls = spec.get("stateMachineOf") or spec.get("title")
            control = add_node(nodes, bundle, "control", cls, spec)
            machine = add_node(nodes, bundle, "state-machine", cls, spec, stateMachineOf=cls)
            add_link(links, bundle, "state-machine-of", machine, control, spec)
            for r in spec.get("relations", []):
                if norm(r.get("type", "transition")) not in ("transition", "flow"):
                    continue
                ev = mname(r.get("event"))
                actions = r.get("action") or []
                if isinstance(actions, str):
                    actions = [x.strip() for x in actions.split(",") if x.strip()]
                for action in actions:
                    action = mname(action)
                    if action:
                        add_link(links, bundle, "state-action", machine, control, spec, name=action)
                if ev:
                    add_link(links, bundle, "state-event", control, machine, spec, name=ev)

        if diagram == "activity":
            uc = spec.get("useCase")
            if uc:
                add_node(nodes, bundle, "usecase", uc, spec)
                activity_sources[(bundle, norm(uc))].append(spec.get("_src", ""))

        if diagram == "component":
            for e in spec.get("elements", []):
                typ = norm(e.get("type"))
                if typ in ("component", "subsystem", "interface"):
                    add_node(nodes, bundle, typ, e.get("name", e.get("id")), spec, stereotype=st_of(e))
            els = {str(e.get("id", e.get("name"))): e for e in spec.get("elements", [])}
            for r in spec.get("relations", []):
                a, b = els.get(str(r.get("from"))), els.get(str(r.get("to")))
                if a and b:
                    aid = add_node(nodes, bundle, norm(a.get("type")), a.get("name", a.get("id")), spec)
                    bid = add_node(nodes, bundle, norm(b.get("type")), b.get("name", b.get("id")), spec)
                    add_link(links, bundle, "component-relation", aid, bid, spec,
                             relation=norm(r.get("type", "association")))

        if diagram == "deployment":
            for e in spec.get("elements", []):
                typ = norm(e.get("type"))
                if typ in ("node", "device", "executionenvironment", "component", "artifact"):
                    add_node(nodes, bundle, typ, e.get("name", e.get("id")), spec, stereotype=st_of(e))
            els = {str(e.get("id", e.get("name"))): e for e in spec.get("elements", [])}
            for e in spec.get("elements", []):
                if not e.get("in"):
                    continue
                child = add_node(nodes, bundle, norm(e.get("type")), e.get("name", e.get("id")), spec)
                parent = els.get(str(e.get("in")))
                if child and parent:
                    parent_id = add_node(nodes, bundle, norm(parent.get("type")), parent.get("name", parent.get("id")), spec)
                    add_link(links, bundle, "deployment-contained", parent_id, child, spec)

    for nid, node in sorted(nodes.items()):
        bundle_names[node["bundle"]]["nodeIds"].append(nid)
    for link in sorted(links.values(), key=lambda x: x["id"]):
        bundle_names[link["bundle"]]["linkIds"].append(link["id"])

    coverage = {}
    impact_map = {}
    for nid, node in sorted(nodes.items()):
        related = []
        for link in links.values():
            if link["source"] == nid or link["target"] == nid:
                related.append(link["id"])
        impact_map[nid] = {
            "name": node["name"],
            "bundle": node["bundle"],
            "diagramKinds": sorted(node.get("diagramKinds", [])),
            "sources": sorted(node.get("sources", [])),
            "relatedLinkIds": sorted(set(related)),
        }

    for bundle_name in sorted(bundle_names):
        usecases = {}
        entities = {}
        components = {}
        for nid, node in nodes.items():
            if node["bundle"] != bundle_name:
                continue
            if node["kind"] == "usecase":
                usecases[nid] = {
                    "name": node["name"],
                    "actors": [],
                    "interactionSources": [],
                    "activitySources": sorted(activity_sources.get((bundle_name, norm(node["name"])), [])),
                }
            elif node["kind"] == "entity":
                entities[nid] = {
                    "name": node["name"],
                    "diagramKinds": sorted(node.get("diagramKinds", [])),
                    "sources": sorted(node.get("sources", [])),
                }
            elif node["kind"] in ("component", "subsystem"):
                components[nid] = {
                    "name": node["name"],
                    "diagramKinds": sorted(node.get("diagramKinds", [])),
                    "sources": sorted(node.get("sources", [])),
                }

        for link in links.values():
            if link["bundle"] != bundle_name:
                continue
            if link["kind"] == "actor-uses" and link["target"] in usecases:
                actor = nodes.get(link["source"])
                if actor and actor["name"] not in usecases[link["target"]]["actors"]:
                    usecases[link["target"]]["actors"].append(actor["name"])
            elif link["kind"] == "interaction-member" and link.get("useCase"):
                for uid, u in usecases.items():
                    if norm(u["name"]) == norm(link["useCase"]) and link["sources"]:
                        for src in link["sources"]:
                            if src not in u["interactionSources"]:
                                u["interactionSources"].append(src)

        for uid, u in usecases.items():
            if not u["interactionSources"]:
                u["interactionSources"] = []
            u["actors"] = sorted(u["actors"])
            u["interactionSources"] = sorted(u["interactionSources"])

        coverage[bundle_name] = {
            "useCases": {k: usecases[k] for k in sorted(usecases)},
            "entities": {k: entities[k] for k in sorted(entities)},
            "components": {k: components[k] for k in sorted(components)},
        }

    out = {
        "schemaVersion": 1,
        "kind": "comet-semantic-model",
        "bundles": {k: v for k, v in sorted(bundle_names.items())},
        "nodes": {k: nodes[k] for k in sorted(nodes)},
        "links": {k["id"]: k for k in sorted(links.values(), key=lambda x: x["id"])},
        "coverage": coverage,
        "impactMap": {k: impact_map[k] for k in sorted(impact_map)},
        "stats": {
            "bundles": len(bundle_names),
            "nodes": len(nodes),
            "links": len(links),
            "specs": len(specs),
        },
    }
    payload = json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    out["fingerprint"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return out


SDCROLES = {"state dependent control", "state-dependent control"}


def main():
    ap = argparse.ArgumentParser(description="Xuat canonical semantic model cho bo COMET")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--json", action="store_true", help="in JSON ra stdout")
    ap.add_argument("-o", "--output", help="ghi model JSON vao file")
    a = ap.parse_args()

    model = build_model(load(a.specs))
    text = json.dumps(model, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
