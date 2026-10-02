#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comet_project.py - Canonical-first compiler: mot file canonical -> cac diagram source spec.

  python comet_project.py bootstrap examples/*.json -o system.canonical.json
  python comet_project.py compile system.canonical.json -o specs/ [--check]
  python comet_project.py model system.canonical.json -o system.model.json
  python comet_project.py validate system.canonical.json

File canonical (kind "comet-canonical-model") la nguon su that duy nhat:
  concepts       identity + ten + thuoc tinh dung chung (stereotype, attributes...) cua moi concept
  relationships  quan he giua hai concept (association, include, generalization...)
  interactions   danh sach message dung chung cho communication + sequence cua cung use case
  views          moi view -> mot spec: phan tu tham chieu concept {"ref": key} + du lieu cuc bo cua so do

Doi ten mot concept trong file canonical -> moi spec/diagram lien quan doi theo sau khi compile.
Spec compile ra mang "conceptId" nen identity semantic on dinh qua cac lan doi ten.
Phan tu hanh vi (state/activity: action, state, decision...) va ghi chu la cuc bo, khong thanh concept.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
from comet_check import load, norm  # noqa: E402
from comet_semantic import _new_concept, _raw_bundle, canonical_concept_id  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DOC_KIND = "comet-canonical-model"
DOC_SCHEMA = 1

DIAGRAMS = {"usecase", "context", "class", "communication", "sequence", "state", "activity", "package",
            "component", "deployment", "erd", "screenflow", "bizcontext"}
BEHAVIOR = {"state", "activity"}
INTERACTION = {"communication", "sequence"}
# So do co quan he cau truc giua concept (duoc nang len thanh canonical relationship).
STRUCTURAL = DIAGRAMS - BEHAVIOR - INTERACTION
DEFAULT_REL = {"activity": "flow", "state": "transition", "erd": "relationship", "screenflow": "navigate"}

LOCAL_TYPES = {"note", "text", "initial", "final", "activityfinal", "flowfinal", "choice", "decision", "merge",
               "junction", "fork", "join", "history", "deephistory", "shallowhistory", "state", "action",
               "frame", "fragment"}
# Truong semantic dung chung cua concept -> nhom so do ma truong do duoc chieu vao.
PROJECTED = {
    "stereotype": {"class", "package", "communication", "sequence", "component", "deployment"},
    "attributes": {"class", "package", "context"},
    "operations": {"class", "package", "context"},
    "abstract": {"class", "package", "context"},
    "literals": {"class", "package", "context"},
    "aliases": DIAGRAMS,
}
IDENTITY_KEYS = ("conceptId", "semanticId", "modelId")
SPEC_ANCHOR_IDS = ("useCaseConceptId", "stateMachineOfConceptId")
VIEW_REL_KEYS = ("id", "side", "style")
VIEW_META = {"id", "output", "interaction", "messageOmit", "autoInclude", "relationsKey"}
ELEMENT_META = {"ref", "omit", "nameField"}
KIND_PRIORITY = ["usecase", "actor", "system", "external", "class", "interface", "enumeration", "datatype",
                 "component", "subsystem", "package", "node", "device", "executionenvironment", "artifact",
                 "entity", "table", "relationship", "screen", "page", "popup", "dialog"]
AUTO_REL_TYPES = {
    "usecase": {"association", "include", "extend", "generalization"},
    "context": {"association", "dependency"},
    "class": {"association", "aggregation", "composition", "generalization", "realization", "dependency"},
    "package": {"association", "aggregation", "composition", "generalization", "realization", "dependency"},
    "component": {"provides", "requires", "usage", "dependency", "connector", "association", "realization"},
    "deployment": {"communicationpath", "connector", "dependency", "association"},
    "erd": {"relationship"},
    "screenflow": {"navigate"},
    "bizcontext": {"flow"},
}
# Bootstrap bat autoInclude theo nhom so do: concept moi cua cac kind nay tu vao view duy nhat cua nhom.
AUTO_KINDS = {
    "usecase": ("usecase", ["actor", "usecase"]),
    "context": ("context", ["external"]),
    "bizcontext": ("context", ["external"]),
    "erd": ("erd", ["entity"]),
}


class CanonicalError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(i["message"] for i in issues))


# ----------------------------------------------------------------------------- helpers

def _dump(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _slug(text, fallback="concept"):
    s = unicodedata.normalize("NFKD", str(text or "").replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or fallback


def _unique(key, taken):
    out, n = key, 2
    while out in taken:
        out = "%s-%d" % (key, n)
        n += 1
    taken.add(out)
    return out


def _majority(values):
    """Gia tri xuat hien nhieu nhat; hoa -> gia tri gap dau tien (thu tu spec da sap xep)."""
    counts, first = defaultdict(int), {}
    for i, v in enumerate(values):
        k = _dump(v)
        counts[k] += 1
        first.setdefault(k, (i, v))
    best = min(counts, key=lambda k: (-counts[k], first[k][0]))
    return copy.deepcopy(first[best][1])


def _bundle_key(value):
    b = norm(value)
    return "" if b in ("", "default", "__default__") else b


def _diagram(spec):
    return norm(spec.get("diagram"))


def _name_field(element):
    if norm(element.get("type")) == "object":
        return "class" if element.get("class") else "name"
    return "name"


def _is_concept_element(diagram, element):
    if diagram in BEHAVIOR or norm(element.get("type")) in LOCAL_TYPES:
        return False
    return bool(str(element.get(_name_field(element)) or "").strip())


def _identity(element):
    for key in IDENTITY_KEYS:
        if element.get(key):
            return ("id", str(element[key]))
    alias_of = element.get("aliasOf") or element.get("canonicalName")
    if alias_of:
        return ("name", norm(alias_of))
    return ("name", norm(element.get(_name_field(element))))


def _kind_of(types):
    kinds = {"class" if t == "object" else t for t in types if t}
    for k in KIND_PRIORITY:
        if k in kinds:
            return k
    return sorted(kinds)[0] if kinds else "concept"


def _rel_list_key(spec):
    return "flows" if "flows" in spec and "relations" not in spec else "relations"


def _output_name(src, taken):
    path, _, index = str(src).partition("#")
    base = os.path.basename(path) or "diagram.json"
    if index:
        stem, ext = os.path.splitext(base)
        base = "%s-%s%s" % (stem, index, ext or ".json")
    return _unique(base, taken)


# ----------------------------------------------------------------------------- bootstrap

def bootstrap_canonical(specs, bundle=None):
    """Dung file canonical tu bo spec hien co (projection -> canonical); compile lai cho ra dung cac spec do."""
    if bundle is not None:
        specs = [s for s in specs if _bundle_key(s.get("bundle")) == _bundle_key(bundle)]
    bundles = sorted({_bundle_key(s.get("bundle")) for s in specs})
    if len(bundles) > 1:
        raise ValueError("Specs span several bundles (%s); bootstrap one bundle at a time with --bundle."
                         % ", ".join(b or "default" for b in bundles))
    ordered = sorted(specs, key=lambda s: str(s.get("_src", "")))
    doc_bundle = next((s.get("bundle") for s in ordered if _bundle_key(s.get("bundle"))), None)
    raw_bundle = _raw_bundle(doc_bundle)

    # 1) Gom representation theo identity.
    reps = defaultdict(list)            # identity -> [(diagram, element)]
    order = []
    for spec in ordered:
        diagram = _diagram(spec)
        for e in spec.get("elements", []):
            if _is_concept_element(diagram, e):
                ident = _identity(e)
                if ident not in reps:
                    order.append(ident)
                reps[ident].append((diagram, e))

    concepts, key_of, taken = {}, {}, set()
    for ident in order:
        items = reps[ident]
        names = [str(e.get(_name_field(e))) for _, e in items
                 if ident[0] == "id" or not (e.get("aliasOf") or e.get("canonicalName"))]
        if not names:
            names = [str(items[0][1].get("aliasOf") or items[0][1].get("canonicalName"))]
        name = _majority(names)
        concept = {"name": name, "kind": _kind_of([norm(e.get("type")) for _, e in items])}
        concept["conceptId"] = ident[1] if ident[0] == "id" else canonical_concept_id(raw_bundle, "name:" + ident[1])
        for prop, groups in PROJECTED.items():
            values = [e[prop] for d, e in items if d in groups and prop in e]
            if values:
                concept[prop] = _majority(values)
        key = _unique(_slug(name), taken)
        key_of[ident] = key
        concepts[key] = concept

    by_name = {}
    for key, c in concepts.items():
        by_name.setdefault(norm(c["name"]), key)

    def concept_ref(value):
        """Tham chieu spec-level (useCase, partition...) -> {"ref"} khi trung dung ten mot concept."""
        if isinstance(value, str):
            key = key_of.get(("name", norm(value)))
            if key and concepts[key]["name"] == value:
                return {"ref": key}
        return value

    relationships, rel_index, rel_taken = {}, {}, set()
    interactions, int_taken = {}, set()
    views, out_taken = [], set()
    pending_messages = []  # (view, diagram, spec, converted messages)

    for spec in ordered:
        diagram = _diagram(spec)
        output = _output_name(spec.get("_src") or (spec.get("diagram") or "diagram") + ".json", out_taken)
        view = {"id": os.path.splitext(output)[0], "output": output}
        elements = spec.get("elements", [])

        # local id -> concept key (chi voi phan tu concept khong co id tuong minh: id = ten, doi theo concept)
        ref_count = defaultdict(int)
        implicit = {}
        for e in elements:
            if _is_concept_element(diagram, e):
                key = key_of[_identity(e)]
                ref_count[key] += 1
                if "id" not in e and _name_field(e) == "name":
                    implicit[str(e.get("name"))] = key

        def local_ref(value):
            if isinstance(value, str) and value in implicit and ref_count[implicit[value]] == 1:
                return {"ref": implicit[value]}
            return value

        anchors = {}
        for field in ("useCase", "stateMachineOf", "system"):
            if field in spec:
                anchors[field] = concept_ref(spec[field])

        for k, v in spec.items():
            if k == "_src":
                continue
            if k in anchors:
                view[k] = anchors[k]
            elif k == "title" and any(isinstance(a, dict) and spec.get(f) == v
                                      for f, a in anchors.items() if f != "system"):
                view[k] = next(a for f, a in anchors.items() if f != "system" and isinstance(a, dict)
                               and spec.get(f) == v)
            elif k == "partitions" and diagram == "activity" and isinstance(v, list):
                parts = []
                for p in v:
                    if isinstance(p, dict) and "name" in p:
                        p = dict(p, name=concept_ref(p["name"]))
                    else:
                        p = concept_ref(p)
                    parts.append(p)
                view[k] = parts
            elif k == "elements":
                view[k] = [_bootstrap_element(diagram, e, key_of, concepts, concept_ref, local_ref) for e in v]
            elif k in ("relations", "flows"):
                if k == "flows" and "relations" in spec:
                    view[k] = copy.deepcopy(v)
                    continue
                view["relations"] = _bootstrap_relations(diagram, spec, v, key_of, relationships,
                                                         rel_index, rel_taken, ref_count, local_ref)
                if k == "flows":
                    view["relationsKey"] = "flows"
            elif k == "messages" and diagram in INTERACTION:
                msgs = []
                for m in v:
                    m = copy.deepcopy(m)
                    for f in ("from", "to"):
                        if f in m:
                            m[f] = local_ref(m[f])
                    msgs.append(m)
                view["interaction"] = None
                pending_messages.append((view, spec, msgs))
            elif k == "root":
                view[k] = local_ref(v)
            elif k in SPEC_ANCHOR_IDS:
                continue
            else:
                view[k] = copy.deepcopy(v)
        views.append(view)

    # 2) Interaction dung chung: gop communication + sequence cung use case khi message khop nhau.
    groups = defaultdict(list)
    for item in pending_messages:
        view, spec, _ = item
        groups[norm(spec.get("useCase") or spec.get("title") or view["id"])].append(item)
    for gkey, items in groups.items():
        merged = _merge_messages([msgs for _, _, msgs in items])
        buckets = [items] if merged is not None else [[it] for it in items]
        for bucket in buckets:
            msgs_list = [msgs for _, _, msgs in bucket]
            messages = merged if len(bucket) > 1 else msgs_list[0]
            iid = _unique(_slug(bucket[0][1].get("useCase") or bucket[0][1].get("title") or bucket[0][0]["id"],
                                "interaction"), int_taken)
            interactions[iid] = {"messages": messages}
            for view, _, msgs in bucket:
                view["interaction"] = iid
                union = {k for m in messages for k in m}
                have = {k for m in msgs for k in m}
                if union - have:
                    view["messageOmit"] = sorted(union - have)

    doc = {"kind": DOC_KIND, "schemaVersion": DOC_SCHEMA}
    if doc_bundle is not None:
        doc["bundle"] = doc_bundle
    doc.update({"concepts": concepts, "relationships": relationships, "interactions": interactions,
                "views": views})

    # 3) Auto-include chi bat cho view duy nhat cua nhom (vd mot use case view) va chi khi no khong them gi
    #    luc bootstrap (round-trip giu nguyen); ve sau concept moi cung kind tu xuat hien trong view do.
    families = defaultdict(list)
    for view in views:
        auto = AUTO_KINDS.get(norm(view.get("diagram")))
        if auto:
            families[auto[0]].append(view)
    for family_views in families.values():
        if len(family_views) != 1:
            continue
        view = family_views[0]
        diagram = norm(view.get("diagram"))
        before = _compile_view(doc, view, "", [])
        options = [True, False] if AUTO_REL_TYPES.get(diagram) else [False]
        for with_rels in options:
            view["autoInclude"] = {"kinds": list(AUTO_KINDS[diagram][1]), "relationships": with_rels}
            if _compile_view(doc, view, "", []) == before:
                break
            del view["autoInclude"]
    return doc


def _bootstrap_element(diagram, e, key_of, concepts, concept_ref, local_ref):
    if not _is_concept_element(diagram, e):
        out = copy.deepcopy(e)
        if diagram == "activity" and "partition" in out:
            out["partition"] = concept_ref(out["partition"])
        if "in" in out:
            out["in"] = local_ref(out["in"])
        return out
    key = key_of[_identity(e)]
    concept = concepts[key]
    nf = _name_field(e)
    ve = {"ref": key}
    for k, v in e.items():
        if k in IDENTITY_KEYS:
            continue
        if k == nf:
            if v != concept["name"]:
                ve[k] = v
        elif k in PROJECTED and diagram in PROJECTED[k]:
            if concept.get(k) != v:
                ve[k] = copy.deepcopy(v)
        elif k == "in":
            ve[k] = local_ref(v)
        else:
            ve[k] = copy.deepcopy(v)
    if norm(e.get("type")) == "object" and nf == "name":
        ve["nameField"] = "name"
    omit = [p for p, groups in PROJECTED.items() if diagram in groups and p in concept and p not in e]
    if omit:
        ve["omit"] = omit
    return ve


def _bootstrap_relations(diagram, spec, rels, key_of, relationships, rel_index, rel_taken, ref_count, local_ref):
    els = {}
    for e in spec.get("elements", []):
        els[str(e.get("id", e.get("name")))] = e
    out = []
    for r in rels:
        a, b = str(r.get("from")), str(r.get("to"))
        ea, eb = els.get(a), els.get(b)
        if (diagram in STRUCTURAL and ea is not None and eb is not None
                and _is_concept_element(diagram, ea) and _is_concept_element(diagram, eb)):
            ka, kb = key_of[_identity(ea)], key_of[_identity(eb)]
            typ = r.get("type") or DEFAULT_REL.get(diagram, "association")
            props = {k: copy.deepcopy(v) for k, v in r.items()
                     if k not in ("from", "to", "type") and k not in VIEW_REL_KEYS}
            ikey = (typ, ka, kb, _dump(props))
            rid = rel_index.get(ikey)
            if rid is None:
                rid = _unique("%s:%s->%s" % (_slug(typ, "rel"), ka, kb), rel_taken)
                rel_index[ikey] = rid
                relationships[rid] = dict({"type": typ, "from": ka, "to": kb}, **props)
            vr = {"ref": rid}
            if "type" not in r:
                vr["implicitType"] = True
            if ref_count[ka] > 1:
                vr["from"] = r.get("from")
            if ref_count[kb] > 1:
                vr["to"] = r.get("to")
            for k in VIEW_REL_KEYS:
                if k in r:
                    vr[k] = copy.deepcopy(r[k])
            out.append(vr)
        else:
            inline = copy.deepcopy(r)
            for f in ("from", "to"):
                if f in inline:
                    inline[f] = local_ref(inline[f])
            out.append(inline)
    return out


def _merge_messages(lists):
    """Gop message cua nhieu view thanh 1 danh sach; None neu khong gop duoc (khac thu tu/gia tri)."""
    if len(lists) < 2 or len({len(x) for x in lists}) != 1:
        return None
    merged = []
    for group in zip(*lists):
        m = {}
        for msg in group:
            for k, v in msg.items():
                if k in m and m[k] != v:
                    return None
                m.setdefault(k, copy.deepcopy(v))
        merged.append(m)
    # Moi view phai tai tao dung message goc khi bo cac truong no chua bao gio co.
    for msgs in lists:
        have = {k for m in msgs for k in m}
        if [{k: v for k, v in m.items() if k in have} for m in merged] != msgs:
            return None
    return merged


# ----------------------------------------------------------------------------- compile

def _concept_semantic_id(doc, key):
    concept = doc["concepts"][key]
    if concept.get("conceptId"):
        return str(concept["conceptId"])
    return canonical_concept_id(_raw_bundle(doc.get("bundle")), "name:" + norm(concept.get("name")))


def _issue(sink, code, view, message, severity="error"):
    sink.append({"rule": code, "severity": severity, "view": view,
                 "message": "%s [%s] %s" % (code, view, message)})


def _compile_view(doc, view, base, sink, projected=None):
    concepts = doc.get("concepts", {})
    relationships = doc.get("relationships", {})
    vid = str(view.get("id") or view.get("output") or "?")
    diagram = norm(view.get("diagram"))

    named_refs = set()

    def ref_name(value, where):
        if isinstance(value, dict) and set(value) == {"ref"}:
            key = value["ref"]
            if key not in concepts:
                _issue(sink, "K4", vid, "%s tham chieu concept khong ton tai '%s'." % (where, key))
                return str(key)
            named_refs.add(key)
            return concepts[key].get("name")
        return value

    # Phan tu: concept ref + auto-include.
    elements, element_keys = [], []
    for ve in view.get("elements", []) or []:
        if isinstance(ve, dict) and "ref" in ve:
            key = ve["ref"]
            if key not in concepts:
                _issue(sink, "K4", vid, "Phan tu tham chieu concept khong ton tai '%s'." % key)
                continue
            elements.append(_compile_element(doc, key, ve, diagram))
            element_keys.append(key)
        else:
            e = copy.deepcopy(ve)
            if isinstance(e, dict) and diagram == "activity" and "partition" in e:
                e["partition"] = ref_name(e["partition"], "partition")
            elements.append(e)
            element_keys.append(None)

    auto = view.get("autoInclude") or {}
    present = set(k for k in element_keys if k)
    for kind in auto.get("kinds", []) or []:
        for key in sorted(concepts):
            if key not in present and norm(concepts[key].get("kind")) == norm(kind):
                ve = {"ref": key, "type": concepts[key].get("kind"), "id": key}
                elements.append(_compile_element(doc, key, ve, diagram))
                element_keys.append(key)
                present.add(key)

    by_key = defaultdict(list)
    local_ids = defaultdict(int)
    for e, key in zip(elements, element_keys):
        if isinstance(e, dict):
            lid = str(e.get("id", e.get("name")))  # cung quy uoc local id voi comet_check/uml2drawio
            local_ids[lid] += 1
            if key:
                by_key[key].append(lid)
    for lid, n in local_ids.items():
        if n > 1:
            _issue(sink, "K6", vid, "Trung local id '%s' (%d phan tu)." % (lid, n))

    def resolve(value, where):
        if isinstance(value, dict) and set(value) == {"ref"}:
            ids = by_key.get(value["ref"], [])
            if len(ids) != 1:
                _issue(sink, "K5", vid, "%s: concept '%s' co %d phan tu trong view (can dung 1)."
                       % (where, value["ref"], len(ids)))
                return str(value["ref"])
            return ids[0]
        return value

    for e in elements:
        if isinstance(e, dict) and "in" in e:
            e["in"] = resolve(e["in"], "in")

    # Quan he.
    relations, used_rels, emitted_rels = [], set(), set()
    for vr in view.get("relations", []) or []:
        if isinstance(vr, dict) and "ref" in vr:
            rid = vr["ref"]
            rel = relationships.get(rid)
            if rel is None:
                _issue(sink, "K4", vid, "Quan he tham chieu relationship khong ton tai '%s'." % rid)
                continue
            used_rels.add(rid)
            emitted_rels.add(rid)
            relations.append(_compile_relation(rel, vr, diagram, by_key, resolve, sink, vid, rid))
        else:
            r = copy.deepcopy(vr)
            for f in ("from", "to"):
                if isinstance(r, dict) and f in r:
                    r[f] = resolve(r[f], f)
            relations.append(r)
    if auto.get("relationships"):
        allowed = AUTO_REL_TYPES.get(diagram, set())
        users = _relationship_diagrams(doc)
        for rid in sorted(relationships):
            rel = relationships[rid]
            if rid in used_rels or norm(rel.get("type")) not in allowed:
                continue
            if users.get(rid) and diagram not in users[rid]:
                continue
            if rel.get("from") in present and rel.get("to") in present:
                emitted_rels.add(rid)
                relations.append(_compile_relation(rel, {"ref": rid}, diagram, by_key, resolve, sink, vid, rid))

    # Message tu interaction dung chung.
    messages = None
    if view.get("interaction") is not None:
        inter = doc.get("interactions", {}).get(view["interaction"])
        if inter is None:
            _issue(sink, "K4", vid, "Tham chieu interaction khong ton tai '%s'." % view["interaction"])
            messages = []
        else:
            omit = set(view.get("messageOmit") or [])
            messages = []
            for m in inter.get("messages", []):
                m = {k: copy.deepcopy(v) for k, v in m.items() if k not in omit}
                for f in ("from", "to"):
                    if f in m:
                        m[f] = resolve(m[f], "message %s" % f)
                messages.append(m)
            if diagram == "communication":
                for m in messages:
                    for f in ("from", "to"):
                        if f in m and str(m[f]) not in local_ids:
                            _issue(sink, "K8", vid, "Message '%s' %s '%s' khong co phan tu trong view."
                                   % (m.get("name", "?"), f, m[f]))

    spec = {}
    for k, v in view.items():
        if k in VIEW_META:
            if k == "interaction" and messages is not None:
                spec["messages"] = messages
            continue
        if k in ("useCase", "stateMachineOf", "system", "title"):
            spec[k] = ref_name(v, k)
            anchor = {"useCase": "useCaseConceptId", "stateMachineOf": "stateMachineOfConceptId"}.get(k)
            if anchor and isinstance(v, dict) and v.get("ref") in concepts:
                spec[anchor] = _concept_semantic_id(doc, v["ref"])
        elif k == "partitions" and isinstance(v, list):
            spec[k] = [dict(p, name=ref_name(p["name"], "partition")) if isinstance(p, dict) and "name" in p
                       and isinstance(p["name"], dict) else ref_name(p, "partition") for p in v]
        elif k == "elements":
            spec[k] = elements
        elif k == "relations":
            spec[view.get("relationsKey") or "relations"] = relations
        elif k == "root":
            spec[k] = resolve(v, "root")
        else:
            spec[k] = copy.deepcopy(v)
    if auto and "elements" not in spec and elements:
        spec["elements"] = elements
    if projected is not None:
        projected["concepts"].update(k for k in element_keys if k)
        projected["concepts"].update(named_refs)
        projected["relationships"].update(emitted_rels)
    if auto.get("relationships") and relations and "relations" not in view:
        spec["relations"] = relations
    spec["_src"] = os.path.join(base, view.get("output") or vid + ".json") if base else \
        str(view.get("output") or vid + ".json")
    return spec


def _compile_element(doc, key, ve, diagram):
    concept = doc["concepts"][key]
    typ = ve.get("type")
    nf = ve.get("nameField") or ("class" if norm(typ) == "object" else "name")
    out = {}
    for k in ("id", "type"):
        if k in ve:
            out[k] = copy.deepcopy(ve[k])
    out[nf] = copy.deepcopy(ve[nf]) if nf in ve else concept.get("name")
    for k, v in ve.items():
        if k in ELEMENT_META or k in out:
            continue
        out[k] = copy.deepcopy(v)
    omit = set(ve.get("omit") or [])
    for prop, groups in PROJECTED.items():
        if diagram in groups and prop in concept and prop not in out and prop not in omit:
            out[prop] = copy.deepcopy(concept[prop])
    out["conceptId"] = _concept_semantic_id(doc, key)
    return out


def _compile_relation(rel, vr, diagram, by_key, resolve, sink, vid, rid):
    out = {}
    typ = rel.get("type") or DEFAULT_REL.get(diagram, "association")
    if not vr.get("implicitType"):
        out["type"] = typ
    for f in ("from", "to"):
        if f in vr:
            out[f] = resolve(vr[f], f)
            continue
        ids = by_key.get(rel.get(f), [])
        if len(ids) != 1:
            _issue(sink, "K5", vid, "Relationship '%s': dau %s concept '%s' co %d phan tu trong view "
                   "(can dung 1 hoac khai bao \"%s\" trong view)." % (rid, f, rel.get(f), len(ids), f))
            out[f] = str(rel.get(f))
        else:
            out[f] = ids[0]
    for k, v in rel.items():
        if k not in ("type", "from", "to"):
            out[k] = copy.deepcopy(v)
    for k in VIEW_REL_KEYS:
        if k in vr:
            out[k] = copy.deepcopy(vr[k])
    return out


def _relationship_diagrams(doc):
    users = defaultdict(set)
    for view in doc.get("views", []):
        for vr in view.get("relations", []) or []:
            if isinstance(vr, dict) and "ref" in vr:
                users[vr["ref"]].add(norm(view.get("diagram")))
    return users


# ----------------------------------------------------------------------------- validate / compile API

def validate_canonical(doc):
    """K-rules: loi cau truc file canonical. Tra ve danh sach issue {rule, severity, view, message}."""
    sink = []
    if not isinstance(doc, dict) or doc.get("kind") != DOC_KIND:
        _issue(sink, "K1", "doc", "File khong phai %s." % DOC_KIND)
        return sink
    if doc.get("schemaVersion") != DOC_SCHEMA:
        _issue(sink, "K1", "doc", "schemaVersion phai la %d." % DOC_SCHEMA)
    for field, typ in (("concepts", dict), ("relationships", dict), ("interactions", dict), ("views", list)):
        if not isinstance(doc.get(field, typ()), typ):
            _issue(sink, "K1", "doc", "'%s' phai la %s." % (field, typ.__name__))
    if sink:
        return sink
    concepts = doc.get("concepts", {})
    for key, c in concepts.items():
        if not isinstance(c, dict) or not str(c.get("name") or "").strip():
            _issue(sink, "K2", "concepts", "Concept '%s' thieu name." % key)
    ids = defaultdict(list)
    for key, c in concepts.items():
        if isinstance(c, dict):
            try:
                ids[_concept_semantic_id(doc, key)].append(key)
            except Exception:
                pass
    for cid, keys in ids.items():
        if len(keys) > 1:
            _issue(sink, "K3", "concepts", "Nhieu concept cung identity '%s': %s." % (cid, ", ".join(sorted(keys))))
    for rid, rel in doc.get("relationships", {}).items():
        for f in ("from", "to"):
            if not isinstance(rel, dict) or rel.get(f) not in concepts:
                _issue(sink, "K9", "relationships", "Relationship '%s' co dau %s khong phai concept." % (rid, f))
    for iid, inter in doc.get("interactions", {}).items():
        if not isinstance(inter, dict) or not isinstance(inter.get("messages", []), list):
            _issue(sink, "K1", "interactions", "Interaction '%s' phai co 'messages' la list." % iid)
    if sink:
        return sink
    outputs = defaultdict(int)
    projected = {"concepts": set(), "relationships": set()}
    doc_bundle = _bundle_key(doc.get("bundle"))
    for view in doc.get("views", []):
        vid = str(view.get("id") or view.get("output") or "?")
        if norm(view.get("diagram")) not in DIAGRAMS:
            _issue(sink, "K7", vid, "Loai so do khong ho tro '%s'." % view.get("diagram"))
            continue
        if not view.get("output"):
            _issue(sink, "K7", vid, "View thieu 'output'.")
        outputs[str(view.get("output"))] += 1
        if _bundle_key(view.get("bundle")) not in ("", doc_bundle):
            _issue(sink, "K7", vid, "Bundle cua view khac bundle cua file canonical.")
        _compile_view(doc, view, "", sink, projected)
    for out, n in outputs.items():
        if n > 1 and out != "None":
            _issue(sink, "K7", out, "Nhieu view cung output '%s'." % out)
    # Khai bao canonical ma khong view nao ve -> canh bao (dung vi tri bao M1/M4 cho canonical-first).
    for rid in sorted(set(doc.get("relationships", {})) - projected["relationships"]):
        _issue(sink, "K10", "relationships", "Relationship '%s' khong duoc view nao chieu - them {\"ref\": \"%s\"} "
               "vao relations cua view phu hop (hoac bat autoInclude)." % (rid, rid), severity="warning")
    for key in sorted(set(concepts) - projected["concepts"]):
        _issue(sink, "K11", "concepts", "Concept '%s' khong duoc view nao chieu - them {\"ref\": \"%s\"} vao "
               "elements cua view phu hop." % (key, key), severity="warning")
    return sink


def compile_projections(doc, base=""):
    """File canonical -> danh sach spec (moi spec co _src = base/output). Loi K -> CanonicalError."""
    issues = [i for i in validate_canonical(doc) if i["severity"] == "error"]
    if issues:
        raise CanonicalError(issues)
    return [_compile_view(doc, view, base, []) for view in doc.get("views", [])]


def normalize_spec(spec):
    """Dang so sanh round-trip: bo _src va truong identity do compiler phat ra."""
    out = {k: copy.deepcopy(v) for k, v in spec.items() if k != "_src" and k not in SPEC_ANCHOR_IDS}
    for e in out.get("elements", []) or []:
        if isinstance(e, dict):
            for k in IDENTITY_KEYS:
                e.pop(k, None)
    return out


def verify_roundtrip(specs, doc):
    """So spec goc voi spec compile tu doc; tra ve danh sach output bi lech (rong = khop)."""
    compiled = compile_projections(doc)
    ordered = sorted(specs, key=lambda s: str(s.get("_src", "")))
    if len(ordered) != len(compiled):
        return ["spec count %d != view count %d" % (len(ordered), len(compiled))]
    return [c["_src"] for s, c in zip(ordered, compiled) if normalize_spec(s) != normalize_spec(c)]


def canonical_fingerprint(doc):
    return hashlib.sha256(_dump(doc).encode("utf-8")).hexdigest()


def canonical_semantic_model(doc):
    """Model semantic v2 authoritative sinh tu file canonical (dung cho reconcile/plan/manifest)."""
    from comet_model import build_model
    model = build_model(compile_projections(doc), schema_version=2)
    raw_bundle = _raw_bundle(doc.get("bundle"))
    for key in sorted(doc.get("concepts", {})):
        concept = doc["concepts"][key]
        cid = _concept_semantic_id(doc, key)
        if not cid.startswith("concept:"):
            cid = canonical_concept_id(raw_bundle, "id:" + cid)
        if cid not in model["concepts"]:
            # Concept khai bao nhung chua co view nao chieu -> van la canonical (reconcile bao M1).
            c = _new_concept(raw_bundle, concept.get("name", key), cid)
            c["semanticKinds"] = [str(concept.get("kind") or "concept")]
            c["aliases"] = sorted(set(str(a) for a in concept.get("aliases") or []))
            model["concepts"][cid] = c
    model["sourceOfTruth"] = dict(model.get("sourceOfTruth", {}), mode="canonical",
                                  canonicalFingerprint=canonical_fingerprint(doc))
    model["stats"]["concepts"] = len(model["concepts"])
    model.pop("fingerprint", None)
    model["fingerprint"] = hashlib.sha256(_dump(model).encode("utf-8")).hexdigest()
    return model


def load_canonical(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("kind") != DOC_KIND:
        raise ValueError("%s is not a %s document" % (path, DOC_KIND))
    return doc


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description="Canonical-first compiler: system.canonical.json <-> diagram specs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bootstrap", help="tao file canonical tu cac spec hien co")
    b.add_argument("specs", nargs="+")
    b.add_argument("-o", "--output", default="system.canonical.json")
    b.add_argument("--bundle", help="chi lay spec cua bundle nay")
    c = sub.add_parser("compile", help="sinh cac spec tu file canonical")
    c.add_argument("doc")
    c.add_argument("-o", "--outdir", default=".")
    c.add_argument("--check", action="store_true", help="khong ghi; exit 1 neu spec thieu hoac cu")
    m = sub.add_parser("model", help="xuat semantic model v2 authoritative tu file canonical")
    m.add_argument("doc")
    m.add_argument("-o", "--output", default="system.model.json")
    v = sub.add_parser("validate", help="kiem tra K-rules cua file canonical")
    v.add_argument("doc")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "bootstrap":
            specs = load(a.specs)
            doc = bootstrap_canonical(specs, bundle=a.bundle)
            if a.bundle is not None:
                specs = [s for s in specs if _bundle_key(s.get("bundle")) == _bundle_key(a.bundle)]
            mismatches = verify_roundtrip(specs, doc)
            _write_json(a.output, doc)
            print(json.dumps({"output": a.output, "concepts": len(doc["concepts"]),
                              "relationships": len(doc["relationships"]),
                              "interactions": len(doc["interactions"]), "views": len(doc["views"]),
                              "roundTrip": "exact" if not mismatches else "mismatch",
                              "mismatches": mismatches}, ensure_ascii=False, indent=2))
            return 1 if mismatches else 0
        doc = load_canonical(a.doc)
        if a.cmd == "validate":
            issues = validate_canonical(doc)
            for i in issues:
                print(("ERROR " if i["severity"] == "error" else "WARN  ") + i["message"])
            print("%d loi." % sum(i["severity"] == "error" for i in issues))
            return 1 if any(i["severity"] == "error" for i in issues) else 0
        if a.cmd == "model":
            model = canonical_semantic_model(doc)
            _write_json(a.output, model)
            print(json.dumps({"output": a.output, "fingerprint": model["fingerprint"],
                              "concepts": len(model["concepts"])}, ensure_ascii=False, indent=2))
            return 0
        specs = compile_projections(doc)
        for i in validate_canonical(doc):
            print("WARN  " + i["message"], file=sys.stderr)
        stale = []
        for spec in specs:
            path = Path(a.outdir) / spec.pop("_src")
            if a.check:
                try:
                    current = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    current = None
                if current != spec:
                    stale.append(str(path))
            else:
                _write_json(path, spec)
        if a.check:
            for p in stale:
                print("STALE " + p)
            print("%d/%d spec cu hoac thieu." % (len(stale), len(specs)))
            return 1 if stale else 0
        print("Da ghi %d spec vao %s." % (len(specs), a.outdir))
        return 0
    except CanonicalError as exc:
        for i in exc.issues:
            print("ERROR " + i["message"], file=sys.stderr)
        return 1
    except ValueError as exc:
        print("ERROR %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
