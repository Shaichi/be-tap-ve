# -*- coding: utf-8 -*-
"""Sinh spec ngau nhien (co seed) de kiem thu bo cuc: class, activity (swimlane), state (long nhau)."""
import random

REL = ["association", "aggregation", "composition", "generalization", "dependency", "association"]
MULT = [None, "1", "0..1", "1..*", "0..*", "*"]


def rand_class(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 11)
    els = []
    for i in range(n):
        attrs = ["attr%d: String" % k for k in range(rng.randint(0, 3))]
        els.append({"id": "c%d" % i, "type": "class", "name": "Class%d%s" % (i, "X" * rng.randint(0, 8)),
                    "stereotype": rng.choice([None, "entity"]), "attributes": attrs})
    rels = []
    for _ in range(rng.randint(n - 1, 2 * n)):
        a, b = rng.randrange(n), rng.randrange(n)
        if a == b and rng.random() < 0.7:
            continue
        t = rng.choice(REL)
        r = {"type": t, "from": "c%d" % a, "to": "c%d" % b}
        if t in ("association", "aggregation", "composition"):
            r["fromMult"], r["toMult"] = rng.choice(MULT), rng.choice(MULT)
            if rng.random() < 0.4:
                r["label"] = rng.choice(["Owns", "Uses", "Has", "Manages Account For"])
        rels.append({k: v for k, v in r.items() if v is not None})
    for e in els:
        if e["stereotype"] is None:
            del e["stereotype"]
    return {"diagram": "class", "title": "Fuzz class %d" % seed, "elements": els, "relations": rels}


def rand_activity(seed):
    rng = random.Random(seed)
    lanes = ["Lane %s" % c for c in "ABCD"[: rng.randint(2, 4)]]
    n = rng.randint(5, 14)
    els = [{"id": "start", "type": "initial", "partition": lanes[0]}]
    kinds = ["action"] * 6 + ["decision", "merge", "fork", "join"]
    for i in range(n):
        k = rng.choice(kinds)
        e = {"id": "n%d" % i, "type": k, "partition": rng.choice(lanes)}
        if k == "action":
            e["name"] = rng.choice(["Do Step %d" % i, "Validate Request %d" % i, "Notify %d" % i])
        els.append(e)
    els.append({"id": "end", "type": "activityFinal", "partition": rng.choice(lanes)})
    ids = [e["id"] for e in els]
    rels = [{"type": "flow", "from": ids[i], "to": ids[i + 1]} for i in range(len(ids) - 1)]
    for _ in range(rng.randint(1, n)):
        a, b = rng.randrange(1, len(ids) - 1), rng.randrange(1, len(ids) - 1)
        if a != b:
            r = {"type": "flow", "from": ids[a], "to": ids[b]}
            if els[a]["type"] == "decision":
                r["guard"] = rng.choice(["ok", "not ok", "else", "retry"])
            rels.append(r)
    return {"diagram": "activity", "title": "Fuzz activity %d" % seed, "partitions": lanes,
            "elements": els, "relations": rels}


def rand_state(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 10)
    els = [{"id": "init", "type": "initial"}]
    comps = []
    for i in range(n):
        e = {"id": "s%d" % i, "type": "state", "name": "State %d" % i}
        if rng.random() < 0.3:
            e["activities"] = ["entry / Do %d" % i]
        if comps and rng.random() < 0.35:
            e["in"] = rng.choice(comps)
        elif rng.random() < 0.2:
            comps.append(e["id"])
        els.append(e)
    ids = [e["id"] for e in els if e["id"] not in comps] + comps
    rels = []
    for _ in range(rng.randint(n, 2 * n)):
        a, b = rng.choice(ids), rng.choice(ids[1:])
        r = {"type": "transition", "from": a, "to": b}
        if a != "init":
            r["event"] = rng.choice(["Card Inserted", "Cancel", "PIN Entered", "Timeout"])
            if rng.random() < 0.3:
                r["action"] = rng.choice(["Eject", "Display Menu"])
        rels.append(r)
    return {"diagram": "state", "title": "Fuzz state %d" % seed, "elements": els, "relations": rels}


GENERATORS = {"class": rand_class, "activity": rand_activity, "state": rand_state}
