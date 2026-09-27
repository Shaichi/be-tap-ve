#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comet_datadict.py - Sinh Data Dictionary (Markdown) tu ERD vat ly crow's foot ("type": "table" + "columns").

  python comet_datadict.py "./uml/sds_03_database.json" -o ./uml/<Sys>_DataDictionary.md
  python comet_datadict.py "./uml/*.json"                 (chi lay spec ERD co bang; in ra stdout)

Data dictionary la BAN SINH tu spec, khong viet tay: moi lan sua bang/cot trong spec -> chay lai lenh nay, de
tai lieu (SDS I.3 / phu luc) va so do Database Design luon khop nhau.

Moi bang: ten, entity (ERD khai niem), bang cot (#, ten, kieu, PK, FK -> bang tham chieu, NOT NULL, mo ta).
FK -> bang dich: cot co "ref" ("users.id" / "users") thi dung; khong thi suy tu ten cot (job_id -> jobs) trong
cac bang co quan he voi bang nay; con lai 1 bang cha duy nhat chua khop -> bang do; khong suy duoc -> "?".
Mo ta cot lay tu "description" / "note" cua cot (neu co).
"""
from __future__ import annotations

import argparse
import sys

sys.dont_write_bytecode = True
from comet_check import compact, load, norm, snake  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MANY = ("n", "*", "m")


def is_many(card):
    c = norm(card)
    return any(x in c for x in MANY)


def plural_forms(base):
    forms = {base, base + "s", base + "es"}
    if base.endswith("y"):
        forms.add(base[:-1] + "ies")
    return forms


def cell(v):
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")


def fk_targets(tables, relations):
    """(id bang, ten cot) -> ten bang dich cho moi cot "fk": true."""
    names = {tid: str(e.get("name") or tid) for tid, e in tables.items()}
    related, parents = {tid: [] for tid in tables}, {tid: [] for tid in tables}
    for r in relations:
        a, b = str(r.get("from")), str(r.get("to"))
        if a not in tables or b not in tables:
            continue
        related[a].append(b)
        related[b].append(a)
        ca, cb = r.get("fromCard", r.get("fromMult")), r.get("toCard", r.get("toMult"))
        if is_many(cb) and not is_many(ca):
            parents[b].append(a)
        elif is_many(ca) and not is_many(cb):
            parents[a].append(b)
        elif norm(ca) == "1" and norm(cb) != "1":   # 1 - 0..1: ben 0..1 giu FK
            parents[b].append(a)
        elif norm(cb) == "1" and norm(ca) != "1":
            parents[a].append(b)
        else:   # 1-1 / N-N: chua biet ben giu FK -> ca hai
            parents[a].append(b)
            parents[b].append(a)
    out = {}
    for tid, e in tables.items():
        cols = [c for c in e.get("columns") or [] if isinstance(c, dict) and c.get("fk")]
        todo = []
        for c in cols:
            ref = c.get("ref") or c.get("references")
            if ref:
                out[(tid, c.get("name"))] = str(ref).split(".")[0]
                continue
            base = snake(c.get("name"))
            base = base[:-3] if base.endswith("_id") else base
            pool = related[tid] or list(tables)
            forms = plural_forms(base)
            hit = [t for t in pool if t != tid and (norm(names[t]) in forms or
                                                  compact(tables[t].get("entity") or "") == compact(base))]
            hit = hit or [t for t in pool if t != tid and any(norm(names[t]).endswith("_" + f) for f in forms)]
            if len(hit) == 1:
                out[(tid, c.get("name"))] = names[hit[0]]
            else:
                todo.append(c)
        used = {out[k] for k in out if k[0] == tid}
        rest = sorted({names[p] for p in parents[tid] if p != tid} - used)
        for c in todo:
            out[(tid, c.get("name"))] = rest[0] if len(rest) == 1 else "?"
    return out


def render(specs, title=None):
    erds = [s for s in specs if str(s.get("diagram", "")).lower() == "erd" and
            any(norm(e.get("type")) == "table" for e in s.get("elements", []))]
    if not erds:
        raise SystemExit("Khong co spec ERD vat ly nao (\"type\": \"table\" + \"columns\").")
    title = title or (erds[0].get("title") or "Database Design").replace("Database Design", "Data Dictionary")
    if "Data Dictionary" not in title:
        title += " - Data Dictionary"
    lines = ["# " + title, "",
             "> Sinh tu dong boi `comet_datadict.py` tu %s - khong sua tay; sua spec roi chay lai."
             % ", ".join("`%s`" % s["_src"].replace("\\", "/").split("/")[-1] for s in erds), ""]
    n = 0
    for s in erds:
        tables = {str(e.get("id", e.get("name"))): e for e in s.get("elements", []) if norm(e.get("type")) == "table"}
        fks = fk_targets(tables, s.get("relations", []))
        for tid, e in tables.items():
            n += 1
            ent = e.get("entity")
            ent = ", ".join(ent) if isinstance(ent, list) else ent
            lines.append("## %d. `%s`%s" % (n, e.get("name") or tid, " - Entity: %s" % ent if ent else ""))
            if e.get("description") or e.get("note"):
                lines += ["", cell(e.get("description") or e.get("note"))]
            lines += ["", "| # | Column | Type | PK | FK -> | NOT NULL | Description |",
                      "|---|---|---|---|---|---|---|"]
            for i, c in enumerate([c for c in e.get("columns") or [] if isinstance(c, dict)], 1):
                nn = c.get("pk") or c.get("nullable") is False or c.get("notNull")
                lines.append("| %d | `%s` | %s | %s | %s | %s | %s |" % (
                    i, cell(c.get("name")), cell(c.get("type")), "x" if c.get("pk") else "",
                    cell(fks.get((tid, c.get("name")), "")) if c.get("fk") else "", "x" if nn else "",
                    cell(c.get("description") or c.get("note") or "")))
            lines.append("")
        rels = [r for r in s.get("relations", []) if str(r.get("from")) in tables and str(r.get("to")) in tables]
        if rels:
            lines += ["## Relationships", "", "| From | Card | To | Card |", "|---|---|---|---|"]
            for r in rels:
                lines.append("| `%s` | %s | `%s` | %s |" % (
                    tables[str(r["from"])].get("name") or r["from"], cell(r.get("fromCard", r.get("fromMult"))),
                    tables[str(r["to"])].get("name") or r["to"], cell(r.get("toCard", r.get("toMult")))))
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Sinh Data Dictionary (Markdown) tu ERD vat ly")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("-o", "--out", help="file .md (mac dinh: stdout)")
    ap.add_argument("--title", help="tieu de (mac dinh: '<Sys> - Data Dictionary')")
    a = ap.parse_args()
    md = render(load(a.specs), a.title)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        print("Data dictionary ->", a.out)
    else:
        print(md)


if __name__ == "__main__":
    main()
