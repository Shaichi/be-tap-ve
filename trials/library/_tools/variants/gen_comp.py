import json, copy
UPD = "Update Copy Status"
def base(order, rel_order, direction=None, withdrawn=True):
    els = {
        "i": {"id": "i", "type": "initial"},
        "avail": {"id": "avail", "type": "state", "name": "Available"},
        "resv": {"id": "resv", "type": "state", "name": "Reserved"},
        "co": {"id": "co", "type": "state", "name": "Checked Out"},
        "ci": {"id": "ci", "type": "initial", "in": "co"},
        "onloan": {"id": "onloan", "type": "state", "name": "On Loan", "in": "co"},
        "overdue": {"id": "overdue", "type": "state", "name": "Overdue", "in": "co"},
        "ret": {"id": "ret", "type": "choice"},
        "lost": {"id": "lost", "type": "state", "name": "Lost"},
        "f": {"id": "f", "type": "final"},
    }
    rels = {
        "init": {"type": "transition", "from": "i", "to": "avail"},
        "co1": {"type": "transition", "from": "avail", "to": "co", "event": "Check Out Copy", "action": [UPD, "Copy Checked Out"]},
        "co2": {"type": "transition", "from": "resv", "to": "co", "event": "Check Out Copy", "action": [UPD, "Copy Checked Out"]},
        "cinit": {"type": "transition", "from": "ci", "to": "onloan"},
        "due": {"type": "transition", "from": "onloan", "to": "overdue", "event": "Due Date Passed", "action": UPD},
        "ret": {"type": "transition", "from": "co", "to": "ret", "event": "Return Copy", "action": "Copy Returned"},
        "g1": {"type": "transition", "from": "ret", "to": "resv", "guard": "reservation pending", "action": UPD},
        "g2": {"type": "transition", "from": "ret", "to": "avail", "guard": "else", "action": UPD},
        "exp": {"type": "transition", "from": "resv", "to": "avail", "event": "Reservation Expired", "action": UPD},
        "lostT": {"type": "transition", "from": "co", "to": "lost", "event": "Copy Reported Lost", "action": UPD},
        "found": {"type": "transition", "from": "lost", "to": "avail", "event": "Lost Copy Found", "action": UPD},
        "wo": {"type": "transition", "from": "lost", "to": "f", "event": "Copy Written Off"},
        "wd": {"type": "transition", "from": "avail", "to": "f", "event": "Copy Withdrawn"},
    }
    if not withdrawn:
        rel_order = [r for r in rel_order if r != "wd"]
    spec = {"diagram": "state", "title": "Book Copy Control", "stateMachineOf": "Book Copy Control",
            "elements": [els[k] for k in order], "relations": [rels[k] for k in rel_order]}
    if direction:
        spec["direction"] = direction
    return spec

O1 = ["i", "avail", "resv", "co", "ci", "onloan", "overdue", "ret", "lost", "f"]
R1 = ["init", "co1", "co2", "cinit", "due", "ret", "g1", "g2", "exp", "lostT", "found", "wo", "wd"]
O2 = ["resv", "i", "avail", "co", "ci", "onloan", "overdue", "ret", "lost", "f"]
R2 = ["exp", "co2", "init", "co1", "cinit", "due", "ret", "g1", "g2", "lostT", "found", "wo", "wd"]
V = {
    "c1": base(O1, R1),
    "c2": base(O1, R1, "LR"),
    "c3": base(O2, R2),
    "c4": base(O2, R2, "LR"),
    "c5": base(O1, R1, None, False),
    "c6": base(O1, R1, "LR", False),
}
for k, s in V.items():
    json.dump(s, open("st_%s.json" % k, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", k)
