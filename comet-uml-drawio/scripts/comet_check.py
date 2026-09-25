#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comet_check.py - Kiem tra tinh nhat quan giua cac so do theo phuong phap COMET (Gomaa).

  python comet_check.py spec1.json spec2.json ...     (hoac 1 file {"diagrams":[...]})

Quy tac kiem tra:
  R1  Moi use case (trong so do usecase) co it nhat 1 so do tuong tac (communication/sequence)
      co "useCase" (hoac "title") trung ten.
  R2  Actor trong so do tuong tac phai co trong mo hinh use case (neu co so do usecase).
  R3  Actor chi trao doi message voi doi tuong boundary («user interaction», «input», «output»,
      «I/O», «proxy»...) - trong COMET actor khong goi truc tiep control/entity.
  R4  Doi tuong trong so do tuong tac phai co stereotype cau truc COMET hop le.
  R5  Doi tuong «entity» phai co lop «entity» cung ten trong entity class model (neu co class diagram).
  R6  Doi tuong «entity» la thu dong: khong chu dong gui message toi actor / boundary / control
      ngoai tra loi (reply) - chi canh bao.
  R7  Moi doi tuong «state dependent control» phai co statechart ("stateMachineOf" = ten lop).
  R8  Su kien (event) tren statechart phai la message DEN doi tuong control do trong cac so do tuong tac;
      hanh dong (action) phai la message DI tu doi tuong do. Nguoc lai: message den control nen
      xuat hien la event tren statechart (tru reply - du lieu tra ve khong bat buoc la event).
  R9  So thu tu message (seq) khong trung trong mot so do; message phai co ten.
  R10 Lop «entity» trong mo hinh phan tich chi co thuoc tinh (canh bao neu co operations).
  R11 Context diagram: dung dung 1 «software system»; lop ngoai dung stereotype «external ...».
  R12 Cung mot use case co ca communication va sequence diagram: hai so do phai co cung tap message
      (cung ten, cung cap doi tuong gui/nhan); khac so thu tu -> ghi chu.
  R13 Doi tuong boundary («user interaction», «input», «output», «proxy»...) trong so do tuong tac phai
      trao doi message voi it nhat 1 actor (proxy <-> he thong ngoai ma no dai dien).
  R14 Moi actor cua use case model co lop ngoai cung ten trong context diagram (chi ghi chu, khi co ca 2
      so do; actor nguoi chi tuong tac qua thiet bi co the vang mat).
  (Ten message/event duoc so khop sau khi bo danh sach tham so: placeOrder(cart) ~ placeOrder.)
Statechart (well-formedness UML, ap dung cho moi spec "state"):
  S1  Initial pseudostate: khong co transition vao, dung 1 transition ra, transition do KHONG co
      event/guard (chi duoc co action); moi cap (region) toi da 1 initial.
  S2  Final state khong co transition ra.
  S3  Choice/junction co >= 2 transition ra: moi transition co guard; toi da 1 [else].
  S4  State khong co transition vao (khong toi duoc) / khong co transition ra (ngo cut).
  S5  Nhieu transition ra khoi 1 state cung event ma khong co guard phan biet -> khong tat dinh.
Activity diagram (well-formedness UML, ap dung cho moi spec "activity"):
  A1  Decision/choice co >= 2 luong ra: moi luong ra phai co guard [..]; toi da 1 [else].
  A2  Fork: 1 luong vao, >= 2 luong ra. Join: >= 2 luong vao, 1 luong ra.
  A3  Initial node khong co luong vao, dung 1 luong ra; final node khong co luong ra.
  A4  Merge khong dung de tach nhanh (>= 2 luong ra); "decision" chi co 1 luong ra la merge.
  A5  Action khong co luong ra (ngo cut) / khong co luong vao.
  A6  Action co >= 2 luong vao (= join ngam, cho du moi luong) hoac >= 2 luong ra (= fork ngam)
      -> gop nhanh bang merge, re nhanh bang decision, song song bang fork/join.
Class diagram (ap dung cho moi spec "class"):
  C1  Thuoc tinh phai co kieu: "ten: Kieu".
  C2  Association/aggregation/composition co multiplicity o ca 2 dau (WARN); association co ten/role (INFO).
ERD / screen flow / context diagram nghiep vu:
  E1  Entity co khoa chinh (PK). E2 Relationship co cardinality 2 dau + ten. E3 Nhieu-nhieu -> entity trung gian.
  F1  Moi man hinh toi duoc tu diem bat dau. F2 Dieu huong co thao tac kich hoat (trigger).
  B1  Dung 1 he thong trung tam. B2 Luong co ten, noi he thong <-> ben ngoai. B3 Moi thuc the ngoai co luong.
--partial: chi kiem mot phan bo so do -> cac quy tac "thieu so do doi ung" (R1, R7) ha xuong INFO.
Ma thoat 1 neu co ERROR.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BOUNDARY = {"boundary", "user interaction", "input", "output", "i/o", "io", "input/output", "device i/o",
            "proxy", "network interaction", "gui", "external system proxy"}
CONTROL = {"control", "coordinator", "state dependent control", "state-dependent control", "timer"}
APPLOGIC = {"application logic", "business logic", "algorithm", "service"}
ENTITY = {"entity", "database wrapper", "data abstraction"}
COMET_OBJ = BOUNDARY | CONTROL | APPLOGIC | ENTITY
SDC = {"state dependent control", "state-dependent control"}
EXTERNAL = {"external input device", "external output device", "external input/output device",
            "external i/o device", "external user", "external system", "external timer", "external device"}
ACT_FLOW = {"flow", "transition", "controlflow", "control flow", "objectflow", "object flow"}
FINALS = {"final", "activityfinal", "flowfinal"}


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def mname(s):
    """Ten message/event de so khop giua cac so do: bo danh sach tham so (placeOrder(cart) ~ placeOrder)."""
    return norm(re.sub(r"\(.*?\)", " ", str(s or "")))


def st_of(e):
    s = e.get("stereotype")
    if isinstance(s, (list, tuple)):
        s = s[0] if s else ""
    return norm(str(s or "").strip("«»<>"))


def obj_class(e):
    return e.get("class") or e.get("name") or e.get("id")


def is_reply(m):
    return str(m.get("type", "")).lower() in ("reply", "return")


def lifelines(s):
    """id -> phan tu cua so do tuong tac; sequence: id chua khai bao duoc uml2drawio tu tao ':id'."""
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    if str(s.get("diagram", "")).lower() == "sequence":
        for m in s.get("messages", []):
            for x in (m.get("from"), m.get("to")):
                if x is not None and str(x) not in els:
                    els[str(x)] = {"id": x, "type": "object", "class": str(x)}
    return els


def party(e):
    """Khoa so khop mot ben gui/nhan giua cac so do: ten actor hoac ten lop cua doi tuong."""
    return norm(e.get("name", e.get("id")) if e.get("type") == "actor" else obj_class(e))


def expand(paths):
    """Tu mo rong *.json - PowerShell/cmd khong mo rong glob cho chuong trinh ngoai."""
    out = []
    for p in paths:
        out += (sorted(glob.glob(p)) if any(c in p for c in "*?[") else []) or [p]
    return out


def load(paths):
    out = []
    for p in expand(paths):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        items = d["diagrams"] if isinstance(d, dict) and "diagrams" in d else (d if isinstance(d, list) else [d])
        for i, s in enumerate(items):
            s["_src"] = p if len(items) == 1 else "%s#%d" % (p, i + 1)
            out.append(s)
    return out


def split_actions(a):
    if not a:
        return []
    if isinstance(a, (list, tuple)):
        return [mname(x) for x in a if x]
    a = re.sub(r"\(.*?\)", " ", str(a))
    return [mname(x) for x in re.split(r"[,;]", a) if x.strip()]


def parse_label(lbl):
    """'Event [guard] / a1, a2' -> (event, [actions])"""
    lbl = str(lbl or "")
    ev, _, act = lbl.partition("/")
    ev = re.sub(r"\[.*?\]", "", ev)
    return mname(ev), split_actions(act)


def trans_parts(r):
    """Transition -> (event, guard, [actions]) tu truong event/guard/action hoac label 'Ev [g] / a'."""
    if r.get("event") or r.get("guard") or r.get("action"):
        return mname(r.get("event")), guard_of(r), split_actions(r.get("action"))
    ev, acts = parse_label(r.get("label") or r.get("name"))
    return ev, guard_of(r), acts


def guard_of(r):
    """Guard cua luong: truong 'guard' hoac '[..]' trong label/name; '' neu khong co."""
    if r.get("guard"):
        return norm(str(r["guard"]).strip("[]"))
    m = re.search(r"\[(.*?)\]", str(r.get("label") or r.get("name") or ""))
    return norm(m.group(1)) if m else ""


def check_activity(s, E, W, I):
    src = s["_src"]
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    ins, outs = defaultdict(list), defaultdict(list)
    for r in s.get("relations", []):
        if norm(r.get("type", "flow")) in ACT_FLOW:
            outs[str(r.get("from"))].append(r)
            ins[str(r.get("to"))].append(r)
    for i, e in els.items():
        t, nm = norm(e.get("type")), e.get("name") or i
        ni, no = len(ins[i]), len(outs[i])
        if t in ("decision", "choice"):
            if no >= 2:
                miss = [str(r.get("to")) for r in outs[i] if not guard_of(r)]
                if miss:
                    W.append("A1 [%s] Decision '%s': luong ra toi %s thieu guard [dieu kien] (dat truong \"guard\")."
                             % (src, nm, ", ".join(miss)))
                if sum(guard_of(r) == "else" for r in outs[i]) > 1:
                    W.append("A1 [%s] Decision '%s' co nhieu hon 1 nhanh [else]." % (src, nm))
            elif ni >= 2:
                I.append("A4 [%s] '%s' co %d luong vao va %d luong ra -> day la merge, nen dung type \"merge\"."
                         % (src, nm, ni, no))
        elif t == "merge" and no >= 2:
            W.append("A4 [%s] Merge '%s' co %d luong ra - merge chi gop luong; muon re nhanh hay dung \"decision\" "
                     "co guard." % (src, nm, no))
        elif t == "fork" and (ni != 1 or no < 2):
            W.append("A2 [%s] Fork '%s' phai co 1 luong vao va >= 2 luong ra (dang %d vao, %d ra)." % (src, nm, ni, no))
        elif t == "join" and (ni < 2 or no != 1):
            W.append("A2 [%s] Join '%s' phai co >= 2 luong vao va 1 luong ra (dang %d vao, %d ra)." % (src, nm, ni, no))
        elif t == "initial":
            if ni:
                E.append("A3 [%s] Initial node '%s' khong duoc co luong vao." % (src, nm))
            if no != 1:
                W.append("A3 [%s] Initial node '%s' nen co dung 1 luong ra (dang %d)." % (src, nm, no))
        elif t in FINALS:
            if no:
                E.append("A3 [%s] Final node '%s' khong duoc co luong ra." % (src, nm))
        elif t == "action":
            if not no:
                W.append("A5 [%s] Action '%s' khong co luong ra - noi toi buoc tiep theo hoac activity final."
                         % (src, nm))
            if not ni:
                I.append("A5 [%s] Action '%s' khong co luong vao (bat dau tu initial node se ro hon)." % (src, nm))
            if ni >= 2:
                W.append("A6 [%s] Action '%s' co %d luong vao - UML hieu la join ngam (cho DU moi luong moi chay, "
                         "nhanh re tu decision se ket mai); gop nhanh bang node \"merge\" roi moi vao action."
                         % (src, nm, ni))
            if no >= 2:
                W.append("A6 [%s] Action '%s' co %d luong ra - UML hieu la fork ngam (chay SONG SONG moi nhanh); "
                         "re nhanh dung \"decision\" + guard, song song dung \"fork\"/\"join\"." % (src, nm, no))


def check_state(s, E, W, I):
    """S1-S5: well-formedness cua statechart."""
    src = s["_src"]
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    ins, outs = defaultdict(list), defaultdict(list)
    for r in s.get("relations", []):
        if norm(r.get("type", "transition")) in ("transition", "flow"):
            outs[str(r.get("from"))].append(r)
            ins[str(r.get("to"))].append(r)
    parent = {i: str(e["in"]) for i, e in els.items() if e.get("in") not in (None, "")}
    kids = defaultdict(list)
    for i, p in parent.items():
        kids[p].append(i)

    def up(i):   # to tien (chong vong lap do spec sai)
        seen = []
        while i in parent and parent[i] not in seen:
            i = parent[i]
            seen.append(i)
        return seen

    def down(i):
        out, st = [], list(kids[i])
        while st:
            k = st.pop()
            if k not in out:
                out.append(k)
                st += kids[k]
        return out

    name = lambda i: (els[i].get("name") or i) if i in els else i
    inits = defaultdict(list)
    for i, e in els.items():
        t, nm = norm(e.get("type")), e.get("name") or i
        if t == "initial":
            inits[parent.get(i)].append(i)
            if ins[i]:
                E.append("S1 [%s] Initial pseudostate '%s' khong duoc co transition vao." % (src, nm))
            if len(outs[i]) != 1:
                E.append("S1 [%s] Initial pseudostate '%s' phai co dung 1 transition ra (dang %d)."
                         % (src, nm, len(outs[i])))
            for r in outs[i]:
                ev, g, _ = trans_parts(r)
                if ev or g:
                    E.append("S1 [%s] Transition tu initial pseudostate toi '%s' co %s - UML chi cho phep action "
                             "tren transition khoi tao; chuyen event/guard sang transition ke tiep (initial -> "
                             "state cho, vd 'Idle' -> ... tren event do)."
                             % (src, name(str(r.get("to"))), "event '%s'" % ev if ev else "guard [%s]" % g))
        elif t == "final":
            if outs[i]:
                E.append("S2 [%s] Final state '%s' khong duoc co transition ra." % (src, nm))
        elif t in ("choice", "junction") and len(outs[i]) >= 2:
            miss = [name(str(r.get("to"))) for r in outs[i] if not trans_parts(r)[1]]
            if miss:
                W.append("S3 [%s] %s '%s': transition ra toi %s thieu guard [dieu kien]."
                         % (src, t.capitalize(), nm, ", ".join(miss)))
            if sum(trans_parts(r)[1] == "else" for r in outs[i]) > 1:
                W.append("S3 [%s] %s '%s' co nhieu hon 1 nhanh [else]." % (src, t.capitalize(), nm))
        elif t == "state":
            if not ins[i] and not any(ins[k] for k in down(i)):
                W.append("S4 [%s] State '%s' khong co transition vao - khong bao gio toi duoc (noi tu initial "
                         "hoac state truoc do)." % (src, nm))
            if not kids[i] and not outs[i] and not any(outs[a] for a in up(i)):
                I.append("S4 [%s] State '%s' khong co transition ra (ngo cut) - neu day la ket thuc, noi toi "
                         "final state." % (src, nm))
        if t == "state":
            by_ev = defaultdict(list)
            for r in outs[i]:
                ev, g, _ = trans_parts(r)
                by_ev[ev].append(g)
            for ev, gs in by_ev.items():
                if len(gs) >= 2 and ("" in gs or len(set(gs)) < len(gs)):
                    W.append("S5 [%s] '%s' co %d transition cung %s ma khong co guard phan biet -> khong tat dinh."
                             % (src, nm, len(gs), "event '%s'" % ev if ev else "completion (khong event)"))
    for p, lst in inits.items():
        if len(lst) > 1:
            E.append("S1 [%s] %s co %d initial pseudostate - moi region chi duoc 1."
                     % (src, "Statechart" if p is None else "State '%s'" % name(p), len(lst)))
    if els and None not in inits:
        W.append("S1 [%s] Statechart chua co initial pseudostate o cap ngoai cung (type \"initial\")." % src)


def check_class(s, E, W, I):
    """C1-C2: class diagram - thuoc tinh co kieu, association/aggregation/composition co multiplicity."""
    src = s["_src"]
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    name = lambda i: (els[i].get("name") or i) if i in els else i
    for i, e in els.items():
        if norm(e.get("type")) in ("enumeration", "note"):
            continue
        untyped = [str(a) for a in e.get("attributes") or [] if ":" not in str(a)]
        if untyped:
            W.append("C1 [%s] Lop '%s': thuoc tinh %s chua co kieu - viet 'ten: Kieu' (vd 'bankName: String')."
                     % (src, name(i), ", ".join("'%s'" % a for a in untyped)))
    for r in s.get("relations", []):
        t = norm(r.get("type"))
        if t not in ("association", "aggregation", "composition"):
            continue
        a, b = str(r.get("from")), str(r.get("to"))
        miss = [name(x) for x, k in ((a, "fromMult"), (b, "toMult")) if not str(r.get(k) or "").strip()]
        if miss:
            W.append("C2 [%s] %s '%s' - '%s' thieu multiplicity o dau %s (dat \"fromMult\"/\"toMult\", vd \"1\", "
                     "\"0..*\", \"1..*\")." % (src, t.capitalize(), name(a), name(b),
                                                " va ".join("'%s'" % m for m in miss)))
        if t == "association" and not any(r.get(k) for k in ("label", "name", "fromRole", "toRole")):
            I.append("C2 [%s] Association '%s' - '%s' chua co ten (dong tu, vd 'Maintains') hoac role."
                     % (src, name(a), name(b)))


def _er_keys(a):
    if isinstance(a, dict):
        ks = {x.strip().upper() for x in re.split(r"[,/]", str(a.get("key") or "")) if x.strip()}
        return ks | ({"PK"} if a.get("pk") else set()) | ({"FK"} if a.get("fk") else set())
    m = re.match(r"^\s*((?:PK|FK|UK|AK)(?:\s*[,/]\s*(?:PK|FK|UK|AK))*)\s+", str(a), re.I)
    return {x.strip().upper() for x in re.split(r"[,/]", m.group(1))} if m else set()


def check_erd(s, E, W, I):
    """E1-E3: ERD - moi entity co khoa chinh; relationship co cardinality 2 dau; nhieu-nhieu -> bang trung gian."""
    src = s["_src"]
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    name = lambda i: (els[i].get("name") or i) if i in els else i
    for i, e in els.items():
        if norm(e.get("type")) not in ("entity", "table", "class"):
            continue
        if not any("PK" in _er_keys(a) for a in e.get("attributes") or []):
            W.append("E1 [%s] Entity '%s' chua co khoa chinh (thuoc tinh 'PK ten: Kieu' hoac {\"key\": \"PK\"})."
                     % (src, name(i)))
    many = ("*", "0..*", "1..*", "0..n", "1..n", "n", "m", "many")
    for r in s.get("relations", []):
        a, b = str(r.get("from")), str(r.get("to"))
        if a not in els or b not in els:
            E.append("E2 [%s] Relationship tham chieu entity khong ton tai (%s -> %s)." % (src, a, b))
            continue
        fc, tc = r.get("fromCard", r.get("fromMult")), r.get("toCard", r.get("toMult"))
        miss = [name(x) for x, c in ((a, fc), (b, tc)) if not str(c or "").strip()]
        if miss:
            W.append("E2 [%s] Relationship '%s' - '%s' thieu cardinality o dau %s (\"fromCard\"/\"toCard\": \"1\", "
                     "\"0..1\", \"1..*\", \"0..*\")." % (src, name(a), name(b), " va ".join("'%s'" % m for m in miss)))
        elif str(fc).strip().lower() in many and str(tc).strip().lower() in many:
            I.append("E3 [%s] '%s' - '%s' la quan he nhieu-nhieu: o muc logic/vat ly nen tach thanh entity trung gian "
                     "(associative entity) voi 2 quan he 1-nhieu." % (src, name(a), name(b)))
        if not (r.get("label") or r.get("name")):
            I.append("E2 [%s] Relationship '%s' - '%s' chua co ten (dong tu, vd 'places')." % (src, name(a), name(b)))


def check_screenflow(s, E, W, I):
    """F1-F2: screen flow - moi man hinh toi duoc tu diem bat dau; dieu huong co thao tac kich hoat."""
    src = s["_src"]
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    name = lambda i: (els[i].get("name") or i) if i in els else i
    adj = defaultdict(set)
    ins = defaultdict(int)
    for r in s.get("relations", []):
        a, b = str(r.get("from")), str(r.get("to"))
        adj[a].add(b)
        ins[b] += 1
        ta = norm(els.get(a, {}).get("type"))
        if ta in ("screen", "page", "dialog", "popup") and not (r.get("trigger") or r.get("event") or r.get("label")):
            I.append("F2 [%s] Dieu huong '%s' -> '%s' chua ghi thao tac kich hoat (\"trigger\", vd 'Nhan Dang nhap')."
                     % (src, name(a), name(b)))
    starts = [i for i, e in els.items() if norm(e.get("type")) == "initial"]
    if not starts:
        starts = [i for i, e in els.items() if norm(e.get("type")) in ("screen", "page") and not ins[i]][:1]
    seen, todo = set(starts), list(starts)
    while todo:
        for n in adj[todo.pop()]:
            if n not in seen:
                seen.add(n)
                todo.append(n)
    for i, e in els.items():
        if norm(e.get("type")) in ("screen", "page", "dialog", "popup") and i not in seen:
            W.append("F1 [%s] Man hinh '%s' khong toi duoc tu diem bat dau." % (src, name(i)))


def check_bizcontext(s, E, W, I):
    """B1-B3: context diagram nghiep vu - 1 he thong trung tam; luong co ten, noi he thong voi ben ngoai."""
    src = s["_src"]
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    name = lambda i: (els[i].get("name") or i) if i in els else i
    centers = [i for i, e in els.items()
               if norm(e.get("type")) in ("system", "process", "business", "center", "centre", "organization")]
    if len(centers) != 1:
        E.append("B1 [%s] Can dung 1 he thong/doanh nghiep trung tam (type \"system\"), dang co %d."
                 % (src, len(centers)))
        return
    c = centers[0]
    used = set()
    for r in s.get("relations", s.get("flows", [])) or []:
        a, b = str(r.get("from")), str(r.get("to"))
        used |= {a, b}
        if c not in (a, b):
            W.append("B2 [%s] Luong '%s' -> '%s' khong di qua he thong trung tam - luong giua cac ben ngoai nam ngoai "
                     "pham vi context diagram." % (src, name(a), name(b)))
        if not (r.get("label") or r.get("name") or r.get("data")):
            W.append("B2 [%s] Luong '%s' -> '%s' chua co ten du lieu (vd 'Don dat hang')." % (src, name(a), name(b)))
    for i in els:
        if i != c and i not in used:
            W.append("B3 [%s] Thuc the ngoai '%s' khong trao doi luong du lieu nao voi he thong." % (src, name(i)))


def check(specs, partial=False):
    E, W, I = [], [], []
    MISS = I if partial else W   # "thieu so do doi ung": chi la ghi chu khi co y kiem mot phan bo so do
    by = defaultdict(list)
    for s in specs:
        by[str(s.get("diagram", "")).lower()].append(s)

    # ---- collect
    usecases, uc_actors = {}, {}   # ten chuan hoa -> ten goc
    for s in by["usecase"]:
        for e in s.get("elements", []):
            if e.get("type") == "usecase":
                usecases[norm(e.get("name", e.get("id")))] = e.get("name", e.get("id"))
            if e.get("type") == "actor":
                uc_actors[norm(e.get("name", e.get("id")))] = e.get("name", e.get("id"))
    entity_classes = {}
    for s in by["class"]:
        for e in s.get("elements", []):
            if st_of(e) == "entity":
                entity_classes[norm(e.get("name", e.get("id")))] = e
                if e.get("operations"):
                    W.append("R10 [%s] Lop «entity» '%s' co operations - trong mo hinh phan tich COMET, "
                             "entity class chi nen co thuoc tinh (operations xac dinh o pha thiet ke)."
                             % (s["_src"], e.get("name")))

    inter = by["communication"] + by["sequence"]
    ctl_in, ctl_out = defaultdict(set), defaultdict(set)   # class name -> messages (khong ke reply)
    rep_in, rep_out = defaultdict(set), defaultdict(set)   # reply den / di tu control
    shown = {}   # ten da chuan hoa -> ten goc (de in thong bao)
    sdc_classes = {}
    covered = set()
    for s in inter:
        src = s["_src"]
        covered.add(norm(s.get("useCase") or s.get("title")))
        els = lifelines(s)
        seqs = defaultdict(int)
        talks_actor = set()
        for e in els.values():
            if e.get("type") == "actor":
                if uc_actors and norm(e.get("name", e.get("id"))) not in uc_actors:
                    W.append("R2 [%s] Actor '%s' khong co trong mo hinh use case." % (src, e.get("name")))
                continue
            st = st_of(e)
            if st not in COMET_OBJ:
                W.append("R4 [%s] Doi tuong '%s' co stereotype «%s» khong phai stereotype cau truc doi tuong COMET "
                         "(boundary/control/application logic/entity)." % (src, obj_class(e), st or "?"))
            if st in ENTITY and entity_classes and norm(obj_class(e)) not in entity_classes:
                W.append("R5 [%s] Doi tuong «entity» ':%s' khong co lop «entity» tuong ung trong entity class model."
                         % (src, obj_class(e)))
            if st in SDC:
                sdc_classes[norm(obj_class(e))] = obj_class(e)
        for m in s.get("messages", []):
            a, b = els.get(str(m.get("from"))), els.get(str(m.get("to")))
            name = m.get("name", m.get("label"))
            if a is None or b is None:
                E.append("R9 [%s] Message '%s' tham chieu doi tuong khong ton tai (%s -> %s)."
                         % (src, name, m.get("from"), m.get("to")))
                continue
            if not name and not is_reply(m):
                E.append("R9 [%s] Message %s -> %s khong co ten." % (src, m.get("from"), m.get("to")))
            if m.get("seq"):
                seqs[str(m["seq"])] += 1
            ta = "actor" if a.get("type") == "actor" else st_of(a)
            tb = "actor" if b.get("type") == "actor" else st_of(b)
            if ta == "actor" and tb != "actor" and tb not in BOUNDARY:
                W.append("R3 [%s] Actor '%s' gui '%s' truc tiep toi doi tuong «%s» '%s' - COMET yeu cau actor "
                         "giao tiep qua doi tuong boundary." % (src, a.get("name"), name, tb, obj_class(b)))
            if tb == "actor" and ta != "actor" and ta not in BOUNDARY:
                W.append("R3 [%s] Doi tuong «%s» '%s' gui '%s' truc tiep toi actor '%s' - nen qua doi tuong boundary."
                         % (src, ta, obj_class(a), name, b.get("name")))
            if ta in ENTITY and not is_reply(m) and tb != "entity":
                if s.get("diagram") == "sequence" or tb in ("actor",) or tb in BOUNDARY | CONTROL:
                    I.append("R6 [%s] Doi tuong «entity» '%s' gui '%s' toi '%s' - entity la thu dong, hay chac day "
                             "la du lieu tra ve cho loi goi truoc do." % (src, obj_class(a), name,
                                                                        obj_class(b) if tb != "actor" else b.get("name")))
            if name:
                shown.setdefault(mname(name), name)
            if tb in SDC and a is not b and name:
                (rep_in if is_reply(m) else ctl_in)[norm(obj_class(b))].add(mname(name))
            if ta in SDC and a is not b and name:
                (rep_out if is_reply(m) else ctl_out)[norm(obj_class(a))].add(mname(name))
            if b.get("type") == "actor":
                talks_actor.add(str(m.get("from")))
            if a.get("type") == "actor":
                talks_actor.add(str(m.get("to")))
        for k, n in seqs.items():
            if n > 1:
                E.append("R9 [%s] So thu tu message '%s' bi trung %d lan." % (src, k, n))
        for i, e in els.items():   # R13
            st = st_of(e)
            if e.get("type") != "actor" and st in BOUNDARY and i not in talks_actor:
                W.append("R13 [%s] Doi tuong «%s» '%s' khong trao doi message voi actor nao - boundary la noi he "
                         "thong giao tiep voi ben ngoai%s." % (src, st, obj_class(e),
                                                              " (proxy phai noi voi actor/he thong ngoai ma no dai dien,"
                                                              " vd actor «external system» o cot phai)"
                                                              if st == "proxy" else " (them actor va message vao/ra)"))

    # R1
    for uc, ucname in usecases.items():
        if inter and uc not in covered:
            MISS.append("R1 Use case '%s' chua co so do tuong tac (communication/sequence) - dat \"useCase\": \"%s\"."
                        % (ucname, ucname))

    # R7 / R8
    sm_of = {}
    for s in by["state"]:
        cls = s.get("stateMachineOf") or s.get("title")
        sm_of[norm(cls)] = s
    for k, cls in sdc_classes.items():
        if k not in sm_of:
            MISS.append("R7 Doi tuong «state dependent control» '%s' chua co statechart (\"stateMachineOf\": \"%s\")."
                        % (cls, cls))
    for k, s in sm_of.items():
        src = s["_src"]
        events, actions = set(), set()
        for r in s.get("relations", []):
            if str(r.get("type", "transition")).lower() not in ("transition", "flow"):
                continue
            ev, _, acts = trans_parts(r)
            if ev:
                events.add(ev)
            actions.update(acts)
        for e in s.get("elements", []):
            for a in e.get("activities", []) or []:
                _, _, rest = str(a).partition("/")
                actions.update(split_actions(rest))
        if not any(k in d for d in (ctl_in, ctl_out, rep_in, rep_out)):
            if inter:
                I.append("R8 [%s] Statechart '%s' khong khop voi doi tuong «state dependent control» nao trong cac "
                         "so do tuong tac da cho - bo qua kiem tra event/action." % (src, k))
            continue
        for ev in sorted(events):
            if ev not in ctl_in[k] and ev not in rep_in[k]:
                I.append("R8 [%s] Event '%s' chua xuat hien la message DEN '%s' trong so do tuong tac nao "
                         "(co the thuoc use case chua ve)." % (src, ev, k))
        for ac in sorted(actions):
            if ac not in ctl_out[k] and ac not in rep_out[k]:
                I.append("R8 [%s] Action '%s' chua xuat hien la message DI tu '%s' trong so do tuong tac nao."
                         % (src, ac, k))
        cls = sdc_classes.get(k, k)
        for m in sorted(ctl_in[k]):   # reply den control (du lieu tra ve) khong bat buoc la event
            if m not in events:
                W.append("R8 [%s] Message '%s' den '%s' khong la event cua transition nao tren statechart - dat "
                         "event trung ten message." % (src, shown.get(m, m), cls))
        for m in sorted(ctl_out[k]):
            if m not in actions:
                W.append("R8 [%s] Message '%s' do '%s' gui ra khong la action/activity nao tren statechart - them "
                         "\"action\" tren transition (hoac entry/do/exit) trung ten message."
                         % (src, shown.get(m, m), cls))

    # R11
    for s in by["context"]:
        sw = [e for e in s.get("elements", []) if st_of(e) in ("software system", "system")]
        if len(sw) != 1:
            E.append("R11 [%s] Context diagram phai co dung 1 lop «software system» (dang co %d)." % (s["_src"], len(sw)))
        for e in s.get("elements", []):
            if e in sw or norm(e.get("type")) == "note":
                continue
            if st_of(e) not in EXTERNAL:
                W.append("R11 [%s] Lop '%s' trong context diagram nen co stereotype «external input device / external "
                         "output device / external I/O device / external user / external system / external timer»."
                         % (s["_src"], e.get("name")))
        byid = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
        for r in s.get("relations", []):
            if norm(r.get("type", "association")) != "association":
                continue
            miss = [w for w, ok in (("ten quan he (Inputs to / Outputs to / Interacts with / Awakens)",
                                     r.get("label") or r.get("name")),
                                    ("multiplicity", r.get("fromMult") or r.get("toMult"))) if not ok]
            if miss:
                ends = [byid.get(str(r.get(k)), {}).get("name", r.get(k)) for k in ("from", "to")]
                I.append("R11 [%s] Quan he %s - %s nen co %s (nhu context diagram cua Gomaa)."
                         % (s["_src"], ends[0], ends[1], " va ".join(miss)))

    # R14 - actor cua use case model <-> lop ngoai cua context diagram (khop ca cum tu: "ATM Customer" ~
    # "ATM Customer Keypad Display"); actor nguoi chi tuong tac qua thiet bi co the vang -> chi ghi chu
    if by["context"] and uc_actors:
        ctx = [(s["_src"], norm(e.get("name", e.get("id")))) for s in by["context"] for e in s.get("elements", [])
               if st_of(e) not in ("software system", "system") and norm(e.get("type")) != "note"]
        srcs = ", ".join(s["_src"] for s in by["context"])
        for k, aname in uc_actors.items():
            if not any(re.search(r"(?<!\w)%s(?!\w)" % re.escape(k), x) for _, x in ctx):
                I.append("R14 [%s] Actor '%s' cua use case model chua co lop ngoai cung ten trong context diagram - "
                         "them lop «external …» ten '%s' (he thong ngoai: «external system», timer: «external timer»),"
                         " tru khi actor chi tuong tac qua cac thiet bi «external … device» da ve." % (srcs, aname, aname))

    # R12
    check_comm_vs_seq(inter, W, I)

    # A1-A5
    for s in by["activity"]:
        check_activity(s, E, W, I)
    # S1-S5
    for s in by["state"]:
        check_state(s, E, W, I)
    # C1-C2
    for s in by["class"]:
        check_class(s, E, W, I)
    # E1-E3, F1-F2, B1-B3
    for s in by["erd"]:
        check_erd(s, E, W, I)
    for s in by["screenflow"]:
        check_screenflow(s, E, W, I)
    for s in by["bizcontext"]:
        check_bizcontext(s, E, W, I)
    return E, W, I


def check_comm_vs_seq(inter, W, I):
    """R12: communication va sequence diagram cua cung use case phai the hien cung mot tap message."""
    groups = defaultdict(lambda: defaultdict(list))
    for s in inter:
        uc = s.get("useCase") or s.get("title")
        groups[norm(uc)][str(s.get("diagram", "")).lower()].append(s)
    for uc, g in groups.items():
        if not g["communication"] or not g["sequence"]:
            continue
        src = "%s <> %s" % (", ".join(s["_src"] for s in g["communication"]),
                            ", ".join(s["_src"] for s in g["sequence"]))
        ucname = g["communication"][0].get("useCase") or g["communication"][0].get("title")
        rows = {}
        for kind in ("communication", "sequence"):
            rows[kind] = []
            for s in g[kind]:
                els = lifelines(s)
                for m in s.get("messages", []):
                    a, b = els.get(str(m.get("from"))), els.get(str(m.get("to")))
                    if a is None or b is None:
                        continue   # R9 da bao
                    name = m.get("name", m.get("label")) or ""
                    rows[kind].append((mname(name), name, party(a), party(b), str(m.get("seq") or "")))
        rc, rs = rows["communication"], rows["sequence"]
        shown = {r[0]: r[1] for r in rc + rs if r[0]}
        anon = {"communication": {(r[2], r[3]) for r in rc if not r[0]},
                "sequence": {(r[2], r[3]) for r in rs if not r[0]}}   # reply khong ten
        nc, ns = {r[0] for r in rc if r[0]}, {r[0] for r in rs if r[0]}
        for only, rows_, here, there in ((nc - ns, rc, "communication", "sequence"),
                                         (ns - nc, rs, "sequence", "communication")):
            for n in sorted(only):
                if any((r[2], r[3]) in anon[there] for r in rows_ if r[0] == n):
                    continue   # ben kia la reply khong ten giua dung cap doi tuong
                W.append("R12 [%s] Message '%s' co trong %s diagram nhung khong co trong %s diagram cua use case "
                         "'%s' - hai so do phai the hien cung kich ban (ten viet giong het)."
                         % (src, shown[n], here, there, ucname))
        for n in sorted(nc & ns):
            pc = {(r[2], r[3]) for r in rc if r[0] == n}
            ps = {(r[2], r[3]) for r in rs if r[0] == n}
            if not pc & ps:
                fmt = lambda p: ", ".join("%s -> %s" % x for x in sorted(p))
                W.append("R12 [%s] Message '%s' khac ben gui/nhan: communication %s; sequence %s."
                         % (src, shown[n], fmt(pc), fmt(ps)))
            qc = {r[4] for r in rc if r[0] == n and r[4]}
            qs = {r[4] for r in rs if r[0] == n and r[4]}
            if qc and qs and not qc & qs:
                I.append("R12 [%s] Message '%s' co so thu tu khac nhau: communication %s, sequence %s."
                         % (src, shown[n], "/".join(sorted(qc)), "/".join(sorted(qs))))


def main():
    ap = argparse.ArgumentParser(description="Kiem tra nhat quan COMET giua cac so do")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--partial", action="store_true",
                    help="chi kiem mot phan bo so do: R1/R7 (thieu so do doi ung) chi la INFO")
    a = ap.parse_args()
    E, W, I = check(load(a.specs), partial=a.partial)
    print("COMET check: %d loi, %d canh bao, %d ghi chu" % (len(E), len(W), len(I)))
    for x in E:
        print("  ERROR:", x)
    for x in W:
        print("  WARN :", x)
    for x in I:
        print("  INFO :", x)
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    main()
