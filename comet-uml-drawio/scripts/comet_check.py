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
  E1  Relationship noi dung thuc the. E2 Du ban so 2 dau (Chen: 1/N/M; crow's foot: 1, 0..1, 1..N, 0..N).
  E3  Quan he co ten (Chen: hinh thoi; crow's foot khai niem: dong tu -ing tren duong noi).
  E4  Bang vat ly (crow's foot, "type": "table") co cot khoa chinh "pk": true.
  F1  Moi man hinh toi duoc tu man hinh goc. F2 Site map chi gom man hinh/popup + mui ten khong nhan: khong
      initial/final/decision, khong "items", khong trigger/guard/label.
  B1  Dung 1 he thong trung tam. B2 Luong co ten, noi he thong <-> ben ngoai. B3 Moi thuc the ngoai co luong.
Ngon ngu (moi spec):
  L1  Chu tren so do mac dinh tieng Anh: co chu co dau (tieng Viet...) ma spec khong dat "lang" khac "en" -> WARN.
Muc thiet ke ("level": "design" - class/sequence kieu SDS: Controller/Service/Repository/DTO):
  Khong ap R3/R4/R10; C2 thieu multiplicity chi la INFO; R1/X2 chi la INFO khi bundle khong co so do tuong
  tac muc phan tich cho use case do.
  X8  Lifeline cua sequence muc thiet ke phai la lop trong class diagram muc thiet ke cung bundle va cung
      "useCase" (WARN; use case khong co class diagram rieng -> so voi moi lop thiet ke cua bundle, INFO);
      lifeline "external": true (Client/Browser) bo qua; message khong trung operation cua lop -> INFO.
  X7  Bang vat ly ("type": "table", "entity": ...) tro toi entity cua ERD khai niem cung bundle.
  X9  Lop entity trong class diagram muc thiet ke (ten = "entity" cua bang vat ly cung bundle): moi thuoc tinh
      phai co cot tuong ung (camelCase <-> snake_case, "doctor: Doctor" ~ doctor_id); bo qua List/Set/[].
  X10 Package diagram cung bundle co dat lop vao package -> moi lop cua class diagram muc thiet ke phai co mat
      trong package diagram (bo qua kieu framework co "<...>", vd JpaRepository<User, Long>).
  R15 Sequence muc thiet ke: loi goi dong bo (sync, mac dinh) A -> B phai co reply B -> A phia sau (hoac dat
      "type": "async" neu khong cho ket qua).
Ho so SEP490 (--profile sep490: Report 3 SRS + Report 4 SDS, moi bundle; --partial -> INFO):
  P1  SRS du so do: context (bizcontext), business flow (activity), ERD khai niem, use case, screen flow.
  P2  SDS du so do: architecture (component), package, database design (ERD co "table"), class + sequence
      muc thiet ke.
  P3  Moi actor cua use case model co so do use case rieng ("UCs for <Actor>").
  P4  Business flow (activity) la swimlane: co "partitions" gom lan "System".
  P5  Code designs: >= 2 use case co du cap class + sequence "level": "design" cung "useCase"; class thiet ke
      phai co sequence cung useCase; "useCase" cua class thiet ke co trong use case model.
  P6  Co sequence muc thiet ke cho luong xac thuc (Login / Sign in / Authentication).
  P7  Moi entity cua ERD khai niem co bang vat ly tro toi ("entity") trong database design.
  P8  Bang/entity co cot trang thai (status, *_status, state) -> co it nhat 1 statechart cho entity do
      ("stateMachineOf": "<Entity>").
  P9  Software Architecture (component) khong dung stereotype doi tuong COMET (control, entity, database wrapper,
      proxy, user interaction...) - kien truc phan tang chi dat "subsystem" cho tang.
  P10 Screen flow: man hinh quan tri/dashboard (Dashboard, Admin, Management...) chi toi duoc qua man Login.
--partial: chi kiem mot phan bo so do -> cac quy tac "thieu so do doi ung" (R1, R7) ha xuong INFO.
Ma thoat 1 neu co ERROR.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import unicodedata
from collections import defaultdict

sys.dont_write_bytecode = True  # khong ghi __pycache__ vao thu muc skill
from uml2drawio import CHEN_REL, CROWFOOT_END, FLOW_NODES, NAV_LABELS, crowfoot_mode, is_artifact, norm_key  # noqa: E402

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


def is_design(s):
    """Spec muc thiet ke (SDS: Controller/Service/Repository...): khong ap cac luat phan tich COMET (R3/R4/R10, C2 multiplicity)."""
    return norm(s.get("level")) == "design"


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
        if is_artifact(d):
            continue
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
            (I if is_design(s) else W).append("C2 [%s] %s '%s' - '%s' thieu multiplicity o dau %s (dat \"fromMult\"/\"toMult\", vd \"1\", "
                     "\"0..*\", \"1..*\")." % (src, t.capitalize(), name(a), name(b),
                                                " va ".join("'%s'" % m for m in miss)))
        if t == "association" and not any(r.get(k) for k in ("label", "name", "fromRole", "toRole")):
            I.append("C2 [%s] Association '%s' - '%s' chua co ten (dong tu, vd 'Maintains') hoac role."
                     % (src, name(a), name(b)))


def check_erd(s, E, W, I):
    """E1-E3: ERD ky hieu Chen - quan he noi dung phan tu; du ban so 2 dau (1/N/M); quan he (hinh thoi) co ten."""
    if crowfoot_mode(s):
        return check_erd_crowfoot(s, E, W, I)
    src = s["_src"]
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    name = lambda i: (els[i].get("name") or i) if i in els else i
    dia = {i for i, e in els.items() if norm(e.get("type")) in CHEN_REL}
    for r in s.get("relations", []):
        a, b = str(r.get("from")), str(r.get("to"))
        if a not in els or b not in els:
            E.append("E1 [%s] Relationship tham chieu thuc the khong ton tai (%s -> %s)." % (src, a, b))
            continue
        fc, tc = r.get("fromCard", r.get("fromMult")), r.get("toCard", r.get("toMult"))
        if a in dia or b in dia:   # canh noi thuc the voi hinh thoi (quan he bac 3+): ban so o dau thuc the
            ent = b if a in dia else a
            if not str((tc if a in dia else fc) or r.get("card") or r.get("cardinality") or "").strip():
                W.append("E2 [%s] Canh '%s' - hinh thoi '%s' thieu ban so (\"card\": \"1\" / \"N\" / \"M\")."
                         % (src, name(ent), name(a if a in dia else b)))
            continue
        miss = [name(x) for x, c in ((a, fc), (b, tc)) if not str(c or "").strip()]
        if miss:
            W.append("E2 [%s] Relationship '%s' - '%s' thieu ban so o dau %s (\"fromCard\"/\"toCard\": \"1\", "
                     "\"N\", \"M\")." % (src, name(a), name(b), " va ".join("'%s'" % m for m in miss)))
        if not (r.get("label") or r.get("name")):
            W.append("E3 [%s] Relationship '%s' - '%s' chua co ten (dong tu, vd 'has_role') - hinh thoi se trong."
                     % (src, name(a), name(b)))
    for d in dia:
        if not els[d].get("name"):
            W.append("E3 [%s] Hinh thoi quan he '%s' chua co ten." % (src, d))


def check_erd_crowfoot(s, E, W, I):
    """E1-E4 cho ERD crow's foot: muc khai niem (entity + attributes) va muc vat ly (table + columns)."""
    src = s["_src"]
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    name = lambda i: (els[i].get("name") or i) if i in els else i
    for r in s.get("relations", []):
        a, b = str(r.get("from")), str(r.get("to"))
        if a not in els or b not in els:
            E.append("E1 [%s] Relationship tham chieu thuc the khong ton tai (%s -> %s)." % (src, a, b))
            continue
        for end, c in ((a, r.get("fromCard", r.get("fromMult"))), (b, r.get("toCard", r.get("toMult")))):
            if not str(c or "").strip():
                W.append("E2 [%s] Relationship '%s' - '%s' thieu ban so o dau '%s' (\"1\", \"0..1\", \"1..N\", "
                         "\"0..N\")." % (src, name(a), name(b), name(end)))
            elif norm_key(c) not in CROWFOOT_END:
                W.append("E2 [%s] Relationship '%s' - '%s': ban so '%s' khong phai ky hieu crow's foot "
                         "(1, 0..1, 1..N, 0..N)." % (src, name(a), name(b), c))
        physical = norm(els[a].get("type")) == "table" and norm(els[b].get("type")) == "table"
        if not physical and not (r.get("label") or r.get("name")):
            W.append("E3 [%s] Relationship '%s' - '%s' chua co nhan dong tu (vd 'creating', 'having')."
                     % (src, name(a), name(b)))
    for i, e in els.items():
        if norm(e.get("type")) == "table" and e.get("columns") and                 not any(isinstance(c, dict) and c.get("pk") for c in e["columns"]):
            W.append("E4 [%s] Bang '%s' chua co cot khoa chinh (\"pk\": true)." % (src, name(i)))


def check_screenflow(s, E, W, I):
    """F1-F2: screen flow (site map) - moi man hinh toi duoc tu goc; chi co man hinh/popup va mui ten khong nhan."""
    src = s["_src"]
    els, adj, starts = screen_graph(s)
    name = lambda i: (els[i].get("name") or i) if i in els else i
    for i, e in els.items():
        if norm(e.get("type")) in FLOW_NODES:
            W.append("F2 [%s] Site map khong co nut %s ('%s') - noi thang man hinh -> man hinh, goc dat bang "
                     "\"root\"." % (src, norm(e.get("type")), i))
        elif e.get("items") or e.get("fields"):
            W.append("F2 [%s] Man hinh '%s' co 'items' - site map chi ghi ten man hinh, bo 'items'." % (src, name(i)))
    for r in s.get("relations", []):
        a, b = str(r.get("from")), str(r.get("to"))
        if any(r.get(k) for k in NAV_LABELS):
            W.append("F2 [%s] Dieu huong '%s' -> '%s' co nhan - site map ve mui ten khong nhan, bo %s."
                     % (src, name(a), name(b), "/".join(k for k in NAV_LABELS if r.get(k))))
    seen = reach(adj, starts)
    for i, e in els.items():
        if norm(e.get("type")) in ("screen", "page", "dialog", "popup") and i not in seen:
            W.append("F1 [%s] Man hinh '%s' khong toi duoc tu man hinh goc." % (src, name(i)))


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


NO_TEXT_KEYS = {"_src", "id", "from", "to", "type", "diagram", "lang", "style", "direction", "notation", "side"}


def _accented(s):
    """Co chu cai mang dau (a-grave, e-circumflex, d-stroke...) -> khong phai tieng Anh thuan."""
    return any(ch in "đĐ" or (ch.isalpha() and any(unicodedata.combining(c)
                                                     for c in unicodedata.normalize("NFD", ch)))
               for ch in s)


def check_lang(s, W):
    """L1: chu hien tren so do mac dinh bang tieng Anh; ngon ngu khac phai khai "lang" ro rang."""
    if not str(s.get("lang") or "en").lower().startswith("en"):
        return
    found = []

    def walk(v, key=None):
        if key in NO_TEXT_KEYS:
            return
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str) and _accented(v) and v not in found:
            found.append(v)
    walk(s)
    if found:
        W.append("L1 [%s] So do mac dinh viet tieng Anh nhung co %d chuoi co dau (vd %s) - dich sang tieng Anh, "
                 "hoac dat \"lang\": \"vi\" neu nguoi dung yeu cau ro ngon ngu khac."
                 % (s["_src"], len(found), ", ".join("'%s'" % t for t in found[:3])))


def _scope_key(s):
    """Phạm vi consistency opt-in: chỉ `bundle` tách namespace; spec cũ không có bundle giữ hành vi cũ."""
    return norm(s.get("bundle")) or "__default__"


def _scoped_name(s, value):
    return (_scope_key(s), norm(value))


PROFILES = ("sep490",)
AUTH_RE = re.compile(r"\b(log ?in|sign ?in|auth\w*)\b", re.I)
LOGIN_RE = re.compile(r"\b(log ?in|sign ?in)\b", re.I)
ADMIN_RE = re.compile(r"dashboard|\badmin|management|\bmanage\b", re.I)
STATUS_RE = re.compile(r"(^|_)(status|state)$")
COLLECTION_RE = re.compile(r"\b(list|set|collection|map|iterable|page)\s*<|\[\]", re.I)


def snake(s):
    """createdAt / Created At / created-at -> created_at."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(s or "").strip())
    return re.sub(r"[\s\-]+", "_", s).lower()


def compact(s):
    """So khop ten lop <-> entity: 'Schedule Slot' ~ 'ScheduleSlot' ~ 'schedule_slot'."""
    return re.sub(r"[\s_\-]+", "", norm(s))


def parse_attr(a):
    """'-createdAt: LocalDateTime' / '+ Full Name' / {"name", "type"} -> (ten, kieu)."""
    if isinstance(a, dict):
        return str(a.get("name") or "").strip(), str(a.get("type") or "").strip()
    n, _, typ = str(a).lstrip("+-#~/ ").partition(":")
    return n.split("[")[0].strip(), typ.strip()


def table_entity(e):
    ent = e.get("entity")
    if isinstance(ent, list):
        ent = ent[0] if ent else None
    return ent or e.get("name") or e.get("id")


def screen_graph(s):
    """Screen flow -> (els, adj, starts): goc = "root", hoac initial, hoac man hinh dau tien khong co mui ten vao."""
    els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
    adj, ins = defaultdict(set), defaultdict(int)
    for r in s.get("relations", []):
        a, b = str(r.get("from")), str(r.get("to"))
        adj[a].add(b)
        ins[b] += 1
    starts = [s["root"]] if s.get("root") in els else \
        [i for i, e in els.items() if norm(e.get("type")) == "initial"] or \
        [i for i, e in els.items() if norm(e.get("type")) in ("screen", "page") and not ins[i]][:1]
    return els, adj, starts


def reach(adj, starts, blocked=()):
    seen = {x for x in starts if x not in blocked}
    todo = list(seen)
    while todo:
        for n in sorted(adj[todo.pop()]):
            if n not in seen and n not in blocked:
                seen.add(n)
                todo.append(n)
    return seen


def check_profile_sep490(specs, by, out):
    """P1-P10: bo so do du theo template SEP490 Report 3 (SRS) + Report 4 (SDS), kiem theo tung bundle."""
    scopes = defaultdict(lambda: defaultdict(list))   # bundle -> diagram -> specs
    for d, ss in by.items():
        for s in ss:
            scopes[_scope_key(s)][d].append(s)
    for scope, g in sorted(scopes.items()):
        tag = "bundle %s" % ("-" if scope == "__default__" else scope)
        erd_types = lambda s: {norm(e.get("type")) for e in s.get("elements", [])}
        concept_erd = [s for s in g["erd"] if "entity" in erd_types(s)]
        physical_erd = [s for s in g["erd"] if "table" in erd_types(s)]
        d_class = [s for s in g["class"] if is_design(s)]
        d_seq = [s for s in g["sequence"] + g["communication"] if is_design(s)]
        srs = (("SRS I.1 Context Diagram", g["bizcontext"], "bizcontext"),
               ("SRS I.2 Business Flows", g["activity"], "activity swimlane"),
               ("SRS I.3.1 Entity Relationship Diagram", concept_erd, "erd crowfoot co entity"),
               ("SRS I.4.3 Use Case Diagrams", g["usecase"], "usecase"),
               ("SRS I.5.1a Screen Flow", g["screenflow"], "screenflow"))
        sds = (("SDS I.1 Software Architecture", g["component"], "component"),
               ("SDS I.2 Package Diagram", g["package"], "package"),
               ("SDS I.3 Database Design", physical_erd, "erd crowfoot co table"),
               ("SDS II Code Designs - class", d_class, "class \"level\": \"design\""),
               ("SDS II Code Designs - sequence", d_seq, "sequence \"level\": \"design\""))
        out += ["P1 [%s] Thieu so do cho muc %s (%s)." % (tag, sec, kind) for sec, have, kind in srs if not have]
        out += ["P2 [%s] Thieu so do cho muc %s (%s)." % (tag, sec, kind) for sec, have, kind in sds if not have]

        # P3 - moi actor mot so do use case rieng
        actors, own = {}, set()
        for s in g["usecase"]:
            names = [e.get("name", e.get("id")) for e in s.get("elements", []) if e.get("type") == "actor"]
            for a in names:
                actors.setdefault(norm(a), a)
            title = norm(s.get("title"))
            for a in names:
                if len(names) == 1 or norm(a) in title:
                    own.add(norm(a))
        miss = [actors[a] for a in sorted(actors) if a not in own]
        if miss:
            out.append("P3 [%s] Actor chua co so do use case rieng (\"UCs for <Actor>\", SRS I.4.3): %s."
                       % (tag, ", ".join("'%s'" % a for a in miss)))

        # P4 - business flow la swimlane co lan System
        for s in g["activity"]:
            parts = [norm(x.get("name", x.get("id")) if isinstance(x, dict) else x) for x in s.get("partitions") or []]
            if "system" not in parts:
                out.append("P4 [%s] Business flow '%s' phai la swimlane: \"partitions\" = actor tham gia + \"System\"."
                           % (s["_src"], s.get("title")))

        # P5 - code designs: cap class + sequence thiet ke
        uc_names = {norm(e.get("name", e.get("id"))) for s in g["usecase"] for e in s.get("elements", [])
                    if e.get("type") == "usecase"}
        seq_ucs = {norm(s.get("useCase")) for s in d_seq if s.get("useCase")}
        pairs = set()
        for s in d_class:
            uc = norm(s.get("useCase"))
            if not uc:
                out.append("P5 [%s] Class diagram thiet ke thieu \"useCase\" (SDS II: moi bo code design gan 1 use case)."
                           % s["_src"])
                continue
            if uc_names and uc not in uc_names:
                out.append("P5 [%s] \"useCase\": '%s' khong co trong use case model cung bundle."
                           % (s["_src"], s.get("useCase")))
            if uc in seq_ucs:
                pairs.add(uc)
            else:
                out.append("P5 [%s] Class diagram thiet ke cua '%s' chua co sequence \"level\": \"design\" cung useCase."
                           % (s["_src"], s.get("useCase")))
        if (d_class or d_seq) and len(pairs) < 2:
            out.append("P5 [%s] SDS II Code Designs can >= 2 use case co du cap class + sequence muc thiet ke (hien co %d)."
                       % (tag, len(pairs)))

        # P6 - luong xac thuc
        if not any(AUTH_RE.search(" ".join(str(s.get(k) or "") for k in ("useCase", "title"))) for s in d_seq):
            out.append("P6 [%s] Thieu sequence muc thiet ke cho luong xac thuc (SDS III.1.1 Authentication Flow, "
                       "\"useCase\": \"Login\")." % tag)

        # P7 - moi entity khai niem co bang vat ly
        if concept_erd and physical_erd:
            ents = {}
            for s in concept_erd:
                for e in s.get("elements", []):
                    if norm(e.get("type")) == "entity":
                        ents.setdefault(norm(e.get("name", e.get("id"))), e.get("name", e.get("id")))
            mapped = set()
            for s in physical_erd:
                for e in s.get("elements", []):
                    if norm(e.get("type")) == "table" and e.get("entity"):
                        mapped |= {norm(x) for x in (e["entity"] if isinstance(e["entity"], list) else [e["entity"]])}
            rest = [ents[k] for k in sorted(ents) if k not in mapped]
            if rest:
                out.append("P7 [%s] Entity ERD khai niem chua co bang trong Database Design (dat \"entity\" cho bang): %s."
                           % (tag, ", ".join("'%s'" % x for x in rest)))

        # P8 - entity co cot trang thai can statechart
        stateful = {}
        for s in physical_erd:
            for e in s.get("elements", []):
                if norm(e.get("type")) == "table" and any(
                        isinstance(c, dict) and STATUS_RE.search(snake(c.get("name"))) for c in e.get("columns") or []):
                    stateful.setdefault(compact(table_entity(e)), table_entity(e))
        for s in concept_erd:
            for e in s.get("elements", []):
                if norm(e.get("type")) == "entity" and any(
                        STATUS_RE.search(snake(parse_attr(a)[0])) for a in e.get("attributes") or []):
                    stateful.setdefault(compact(e.get("name", e.get("id"))), e.get("name", e.get("id")))
        if stateful:
            sm = {compact(s.get("stateMachineOf")) for s in g["state"]}
            titles = [compact(s.get("title")) for s in g["state"]]
            if not any(k in sm or any(k in x for x in titles) for k in stateful):
                out.append("P8 [%s] Chua co statechart cho entity co trang thai (cot status): %s - ve it nhat 1 so do "
                           "trang thai cho entity chinh (\"diagram\": \"state\", \"stateMachineOf\": \"<Entity>\"; "
                           "state = gia tri cot status, event = use case/operation doi trang thai)."
                           % (tag, ", ".join("'%s'" % stateful[k] for k in sorted(stateful))))

        # P9 - kien truc phan tang khong dung stereotype doi tuong COMET
        for s in g["component"]:
            bad = sorted({"'%s' «%s»" % (e.get("name", e.get("id")), st_of(e))
                          for e in s.get("elements", []) if st_of(e) in COMET_OBJ})
            if bad:
                out.append("P9 [%s] Software Architecture dung stereotype doi tuong COMET: %s - kien truc phan tang "
                           "(SDS I.1) chi dat \"stereotype\": \"subsystem\" cho tang, component con de trong; "
                           "stereotype COMET danh cho so do phan tich." % (s["_src"], ", ".join(bad)))

        # P10 - man hinh quan tri chi toi duoc qua Login
        for s in g["screenflow"]:
            els, adj, starts = screen_graph(s)
            screens = {i: e.get("name") or i for i, e in els.items()
                       if norm(e.get("type")) in ("screen", "page", "dialog", "popup")}
            admin = {i for i, n in screens.items() if ADMIN_RE.search(str(n))}
            login = {i for i, n in screens.items() if LOGIN_RE.search(str(n))}
            if not admin:
                continue
            if not login:
                out.append("P10 [%s] Screen flow co man hinh quan tri (%s) nhung khong co man Login - them Login "
                           "truoc cac dashboard theo vai tro." % (s["_src"], ", ".join(
                               "'%s'" % screens[i] for i in sorted(admin))))
                continue
            leak = sorted(admin & reach(adj, starts, login))
            if leak:
                out.append("P10 [%s] Man hinh %s toi duoc tu goc ma khong qua Login - noi Login -> <Role> Dashboard, "
                           "khong noi thang tu Home/man cong khai." % (s["_src"], ", ".join(
                               "'%s'" % screens[i] for i in leak)))


def check(specs, partial=False, profile=None):
    E, W, I = [], [], []
    for s in specs:
        check_lang(s, W)
    MISS = I if partial else W   # "thieu so do doi ung": chi la ghi chu khi co y kiem mot phan bo so do
    by = defaultdict(list)
    for s in specs:
        by[str(s.get("diagram", "")).lower()].append(s)

    # ---- collect
    usecases, uc_actors = {}, {}   # (scope, ten chuan hoa) -> ten goc
    for s in by["usecase"]:
        for e in s.get("elements", []):
            if e.get("type") == "usecase":
                usecases[_scoped_name(s, e.get("name", e.get("id")))] = e.get("name", e.get("id"))
            if e.get("type") == "actor":
                uc_actors[_scoped_name(s, e.get("name", e.get("id")))] = e.get("name", e.get("id"))
    entity_classes = {}
    for s in by["class"]:
        for e in s.get("elements", []):
            if st_of(e) == "entity":
                entity_classes[_scoped_name(s, e.get("name", e.get("id")))] = e
                if e.get("operations") and not is_design(s):
                    W.append("R10 [%s] Lop «entity» '%s' co operations - trong mo hinh phan tich COMET, "
                             "entity class chi nen co thuoc tinh (operations xac dinh o pha thiet ke)."
                             % (s["_src"], e.get("name")))

    # R2/R5/R14 chi so voi mo hinh CÙNG bundle: bundle khong co use case/entity model/context thi khong bi kiem.
    uc_actor_scopes = {scope for scope, _ in uc_actors}
    entity_scopes = {scope for scope, _ in entity_classes}
    inter = by["communication"] + by["sequence"]
    ctl_in, ctl_out = defaultdict(set), defaultdict(set)   # (scope, class name) -> messages
    rep_in, rep_out = defaultdict(set), defaultdict(set)   # (scope, class name) -> reply messages
    shown = {}   # ten da chuan hoa -> ten goc (de in thong bao)
    sdc_classes = {}
    covered = set()
    analysis_scopes = {_scope_key(s) for s in inter if not is_design(s)}
    for s in inter:
        src = s["_src"]
        design = is_design(s)
        covered.add(_scoped_name(s, s.get("useCase") or s.get("title")))
        els = lifelines(s)
        seqs = defaultdict(int)
        talks_actor = set()
        for e in els.values():
            if e.get("type") == "actor":
                if _scope_key(s) in uc_actor_scopes and _scoped_name(s, e.get("name", e.get("id"))) not in uc_actors:
                    W.append("R2 [%s] Actor '%s' khong co trong mo hinh use case." % (src, e.get("name")))
                continue
            st = st_of(e)
            if st not in COMET_OBJ and not design:
                W.append("R4 [%s] Doi tuong '%s' co stereotype «%s» khong phai stereotype cau truc doi tuong COMET "
                         "(boundary/control/application logic/entity)." % (src, obj_class(e), st or "?"))
            if st in ENTITY and _scope_key(s) in entity_scopes and _scoped_name(s, obj_class(e)) not in entity_classes:
                W.append("R5 [%s] Doi tuong «entity» ':%s' khong co lop «entity» tuong ung trong entity class model."
                         % (src, obj_class(e)))
            if st in SDC:
                sdc_classes[_scoped_name(s, obj_class(e))] = obj_class(e)
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
            if design:
                pass   # thiet ke: actor/Client goi thang Controller - khong ap R3
            elif ta == "actor" and tb != "actor" and tb not in BOUNDARY:
                W.append("R3 [%s] Actor '%s' gui '%s' truc tiep toi doi tuong «%s» '%s' - COMET yeu cau actor "
                         "giao tiep qua doi tuong boundary." % (src, a.get("name"), name, tb, obj_class(b)))
            if not design and tb == "actor" and ta != "actor" and ta not in BOUNDARY:
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
                (rep_in if is_reply(m) else ctl_in)[_scoped_name(s, obj_class(b))].add(mname(name))
            if ta in SDC and a is not b and name:
                (rep_out if is_reply(m) else ctl_out)[_scoped_name(s, obj_class(a))].add(mname(name))
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
            # Bundle chi co so do tuong tac muc thiet ke (SDS chi can 2-3 bo thiet ke) -> chi ghi chu.
            (MISS if uc[0] in analysis_scopes else I).append("R1 Use case '%s' chua co so do tuong tac (communication/sequence) - dat \"useCase\": \"%s\"."
                        % (ucname, ucname))

    # R7 / R8
    sm_of = {}
    for s in by["state"]:
        cls = s.get("stateMachineOf") or s.get("title")
        sm_of[_scoped_name(s, cls)] = s
    for k, cls in sdc_classes.items():
        if k not in sm_of:
            MISS.append("R7 Doi tuong «state dependent control» '%s' chua co statechart (\"stateMachineOf\": \"%s\")."
                        % (cls, cls))
    for k, s in sm_of.items():
        src = s["_src"]
        # k = (scope, ten chuan hoa) -> in ten goc nhu tac gia viet (uu tien ten class trong interaction)
        cls = sdc_classes.get(k) or str(s.get("stateMachineOf") or s.get("title") or k[1])
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
                         "so do tuong tac da cho - bo qua kiem tra event/action." % (src, cls))
            continue
        for ev in sorted(events):
            if ev not in ctl_in[k] and ev not in rep_in[k]:
                I.append("R8 [%s] Event '%s' chua xuat hien la message DEN '%s' trong so do tuong tac nao "
                         "(co the thuoc use case chua ve)." % (src, ev, cls))
        for ac in sorted(actions):
            if ac not in ctl_out[k] and ac not in rep_out[k]:
                I.append("R8 [%s] Action '%s' chua xuat hien la message DI tu '%s' trong so do tuong tac nao."
                         % (src, ac, cls))
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

    # R14 - actor cua use case model <-> lop ngoai cua context diagram (khop ca cum tu).
    # Khi spec co `bundle`, chi so sanh actor voi context cung bundle; spec cu khong co bundle van dung namespace mac dinh.
    if by["context"] and uc_actors:
        ctx_by_scope = defaultdict(list)
        for s in by["context"]:
            for e in s.get("elements", []):
                if st_of(e) not in ("software system", "system") and norm(e.get("type")) != "note":
                    ctx_by_scope[_scope_key(s)].append((s["_src"], norm(e.get("name", e.get("id")))))
        ctx_scopes = {_scope_key(s) for s in by["context"]}
        for (scope, actor_key), aname in uc_actors.items():
            if scope not in ctx_scopes:
                continue
            ctx = ctx_by_scope.get(scope, [])
            srcs = ", ".join(src for src, _ in ctx) or ", ".join(s["_src"] for s in by["context"] if _scope_key(s) == scope)
            if not any(re.search(r"(?<!\w)%s(?!\w)" % re.escape(actor_key), x) for _, x in ctx):
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
    # X8 - sequence muc thiet ke <-> class diagram muc thiet ke cung bundle
    check_design_trace(by, W, I)
    # X9/X10 - lop entity thiet ke <-> bang; lop thiet ke <-> package diagram; R15 - sync co reply
    check_design_structure(by, W)
    check_sync_replies(by, W)
    # E1-E3, F1-F2, B1-B3
    for s in by["erd"]:
        check_erd(s, E, W, I)
    for s in by["screenflow"]:
        check_screenflow(s, E, W, I)
    for s in by["bizcontext"]:
        check_bizcontext(s, E, W, I)

    # Cross-diagram traceability layer (X1-X6).
    xE, xW, xI = check_cross_diagrams(by, partial=partial)
    E.extend(xE)
    W.extend(xW)
    I.extend(xI)
    if profile == "sep490":
        # P7 thay cho ghi chu X7 "entity chua co bang" (tranh bao 2 lan).
        I[:] = [x for x in I if not x.startswith("X7 [bundle")]
        check_profile_sep490(specs, by, MISS)
    elif profile:
        raise ValueError("profile khong ho tro: %s (co: %s)" % (profile, ", ".join(PROFILES)))
    return E, W, I



def _spec_ref_name(s):
    """Khoa trace use case cho interaction/activity spec."""
    d = norm(s.get("diagram"))
    if d in ("communication", "sequence"):
        return norm(s.get("useCase") or s.get("title"))
    return norm(s.get("useCase"))


def _same_bundle(a, b, shared_names=()):
    # Chi `bundle` la khoa namespace (giong _scope_key); `system` cua use case la ten he thong, khong phai scope.
    ka, kb = norm(a.get("bundle")), norm(b.get("bundle"))
    if ka and kb:
        return ka == kb
    if ka or kb:
        return False

    # Nhan dien prefix cua title neu chua co bundle key.
    def title_stem(s):
        t = norm(s.get("title"))
        for sep in (" - ", " — ", ":", " / "):
            if sep in t:
                return t.split(sep, 1)[0].strip()
        return t

    ta, tb = title_stem(a), title_stem(b)
    if ta and tb and ta == tb and len(ta) >= 3:
        return True

    # Neu chia se it nhat 2 ten nghiep vu, coi nhu cung bundle.
    return len(set(shared_names)) >= 2


def _note_unmatched_pair(rule, left, right, left_kind, right_kind, I):
    """Mot cap duy nhat khong khai bao bundle ma heuristic khong ghep duoc -> ghi chu thay vi bo qua im lang."""
    if len(left) != 1 or len(right) != 1:
        return
    (ls, lnames), (rs, rnames) = left[0], right[0]
    if ls.get("bundle") or rs.get("bundle") or _same_bundle(ls, rs, lnames & rnames):
        return
    I.append("%s [%s <> %s] Khong so sanh %s voi %s: khong co \"bundle\", title khac tien to va chung it hon 2 ten. "
             "Neu cung mot he thong, dat cung \"bundle\" de kiem %s." % (rule, ls["_src"], rs["_src"], left_kind,
                                                                      right_kind, rule))


def check_cross_diagrams(by, partial=False):
    """X1-X6: traceability cheo mo rong; X1-X3 ton trong namespace `bundle` neu duoc khai bao."""
    E, W, I = [], [], []
    MISS = I if partial else W

    # ------------------------------------------------ X1: interaction/activity tham chieu use case khong ton tai trong CÙNG bundle
    declared_uc = defaultdict(set)
    for s in by["usecase"]:
        scope = _scope_key(s)
        for e in s.get("elements", []):
            if e.get("type") == "usecase" and (e.get("name") or e.get("id")):
                declared_uc[scope].add(norm(e.get("name", e.get("id"))))
    for s in by["communication"] + by["sequence"] + by["activity"]:
        ref = _spec_ref_name(s)
        if not ref or not declared_uc:
            continue
        in_scope = declared_uc.get(_scope_key(s))
        if in_scope and ref in in_scope:
            continue
        # Bundle co use case model ma khong co ten nay -> tham chieu treo (WARN);
        # bundle chua co use case model nao -> co the chi la bo so do chua day du (--partial: INFO).
        (W if in_scope else MISS).append(
            "X1 [%s] %s '%s' tham chieu use case '%s' nhung use case nay khong ton tai trong bundle '%s'."
            % (s["_src"], s.get("diagram", "diagram"), s.get("title") or ref,
               s.get("useCase") or s.get("title"), s.get("bundle") or "default"))

    # ------------------------------------------------ X2: actor gan use case phai xuat hien trong interaction CÙNG bundle
    actor_by_uc = defaultdict(set)
    actor_display = {}
    for s in by["usecase"]:
        els = {str(e.get("id", e.get("name"))): e for e in s.get("elements", [])}
        scope = _scope_key(s)
        for rel in s.get("relations", []):
            a, b = els.get(str(rel.get("from"))), els.get(str(rel.get("to")))
            if not a or not b:
                continue
            if a.get("type") == "actor" and b.get("type") == "usecase":
                actor_key = norm(a.get("name", a.get("id")))
                uc_key = (scope, norm(b.get("name", b.get("id"))))
                actor_by_uc[uc_key].add(actor_key)
                actor_display[(uc_key, actor_key)] = a.get("name", a.get("id"))
            elif b.get("type") == "actor" and a.get("type") == "usecase":
                actor_key = norm(b.get("name", b.get("id")))
                uc_key = (scope, norm(a.get("name", a.get("id"))))
                actor_by_uc[uc_key].add(actor_key)
                actor_display[(uc_key, actor_key)] = b.get("name", b.get("id"))
    actors_in_inter = defaultdict(set)
    analysis_inter = set()
    for s in by["communication"] + by["sequence"]:
        ref = _spec_ref_name(s)
        if not ref:
            continue
        if not is_design(s):
            analysis_inter.add((_scope_key(s), ref))
        actors_in_inter[(_scope_key(s), ref)].update(
            norm(e.get("name", e.get("id"))) for e in s.get("elements", []) if e.get("type") == "actor")
    for (scope, uc), actors in actor_by_uc.items():
        if (scope, uc) not in actors_in_inter:
            continue  # R1 xu ly thieu interaction; interaction co nhung khong co actor van phai bao X2
        actual = actors_in_inter[(scope, uc)]
        missing = sorted(actors - actual)
        if missing:
            (MISS if (scope, uc) in analysis_inter else I).append("X2 [%s] Use case '%s' (bundle '%s') co actor %s trong use case model nhung actor do khong "
                        "xuat hien trong communication/sequence cua use case." %
                        (", ".join(sorted(set(s["_src"] for s in by["usecase"] if _scope_key(s) == scope))),
                         uc, "default" if scope == "__default__" else scope,
                         ", ".join("'%s'" % actor_display.get(((scope, uc), x), x) for x in missing)))

    # ------------------------------------------------ X3: statechart phai truy nguoc duoc ve SDC control trong CÙNG bundle
    controls = defaultdict(list)
    for s in by["communication"] + by["sequence"]:
        scope = _scope_key(s)
        for e in s.get("elements", []):
            if e.get("type") == "actor":
                continue
            if st_of(e) in SDC:
                controls[(scope, norm(obj_class(e)))].append(s["_src"])
    lifecycle = defaultdict(set)   # scope -> entity/bang: statechart vong doi entity (SEP490) khong can SDC control
    for s in by["erd"] + by["class"]:
        for e in s.get("elements", []):
            if norm(e.get("type")) in ("entity", "table") or (s in by["class"] and st_of(e) == "entity"):
                lifecycle[_scope_key(s)].add(compact(table_entity(e) if norm(e.get("type")) == "table"
                                                     else e.get("name", e.get("id"))))
    for s in by["state"]:
        cls = norm(s.get("stateMachineOf") or s.get("title"))
        if s.get("stateMachineOf") and compact(cls) in lifecycle[_scope_key(s)]:
            continue
        if not cls:
            W.append("X3 [%s] Statechart khong co 'stateMachineOf'/'title' de truy vet ve control object." % s["_src"])
            continue
        # Control co the nam trong interaction chua duoc dua vao lan kiem nay (--partial: INFO).
        if (by["communication"] or by["sequence"]) and (_scope_key(s), cls) not in controls:
            MISS.append("X3 [%s] Statechart '%s' (bundle '%s') khong truy vet duoc toi doi tuong "
                        "«state dependent control» cung ten trong communication/sequence cung bundle." %
                        (s["_src"], s.get("stateMachineOf") or s.get("title"),
                         s.get("bundle") or "default"))

    # ------------------------------------------------ X4: ERD <-> entity class, chi so sanh khi co dau hieu cung bundle
    erd_specs = []
    cls_specs = []
    for s in by["erd"]:
        names = {norm(e.get("name", e.get("id"))) for e in s.get("elements", [])
                 if e.get("type") == "entity" and (e.get("name") or e.get("id"))}
        if names:
            erd_specs.append((s, names))
    for s in by["class"]:
        names = {norm(e.get("name", e.get("id"))) for e in s.get("elements", [])
                 if st_of(e) == "entity" and (e.get("name") or e.get("id"))}
        if names:
            cls_specs.append((s, names))
    _note_unmatched_pair("X4", erd_specs, cls_specs, "ERD", "entity class model", I)
    for es, enames in erd_specs:
        for cs, cnames in cls_specs:
            shared = sorted(enames & cnames)
            if not _same_bundle(es, cs, shared):
                continue
            only_erd = sorted(enames - cnames)
            only_cls = sorted(cnames - enames)
            if only_erd:
                W.append("X4 [%s <> %s] ERD co entity %s nhung entity class model thieu %s." %
                         (es["_src"], cs["_src"], ", ".join("'%s'" % x for x in shared),
                          ", ".join("'%s'" % x for x in only_erd)))
            if only_cls:
                I.append("X4 [%s <> %s] Entity class model co %s chua xuat hien trong ERD cung bundle." %
                         (es["_src"], cs["_src"], ", ".join("'%s'" % x for x in only_cls)))

    # ------------------------------------------------ X7: bang vat ly ("entity": ...) <-> thuc the ERD khai niem
    concept = defaultdict(set)   # bundle -> ten entity cua ERD khai niem
    for s in by["erd"]:
        for e in s.get("elements", []):
            if norm(e.get("type")) == "entity" and (e.get("name") or e.get("id")):
                concept[norm(s.get("bundle"))].add(norm(e.get("name", e.get("id"))))
    mapped = defaultdict(set)
    for s in by["erd"]:
        key = norm(s.get("bundle"))
        for e in s.get("elements", []):
            if norm(e.get("type")) != "table" or not e.get("entity"):
                continue
            ents = e["entity"] if isinstance(e["entity"], list) else [e["entity"]]
            for ent in ents:
                if not concept[key]:
                    continue
                if norm(ent) in concept[key]:
                    mapped[key].add(norm(ent))
                else:
                    W.append("X7 [%s] Bang '%s' tro toi entity '%s' khong co trong ERD khai niem cung bundle."
                             % (s["_src"], e.get("name", e.get("id")), ent))
    for key, names in mapped.items():
        rest = sorted(concept[key] - names)
        if rest:
            I.append("X7 [bundle %s] Entity khai niem chua co bang vat ly nao tro toi (\"entity\"): %s."
                     % (key or "-", ", ".join("'%s'" % x for x in rest)))

    # ------------------------------------------------ X5: logical component <-> deployment component
    comp_specs = []
    dep_specs = []
    for s in by["component"]:
        # Deployment thường map subsystem/component cấp cao; component con có "in" được triển khai
        # cùng container cha và không bắt buộc phải xuất hiện như một artifact/component riêng.
        names = {norm(e.get("name", e.get("id"))) for e in s.get("elements", [])
                 if e.get("type") in ("component", "subsystem")
                 and not e.get("in")
                 and (e.get("name") or e.get("id"))}
        if names:
            comp_specs.append((s, names))
    for s in by["deployment"]:
        names = {norm(e.get("name", e.get("id"))) for e in s.get("elements", [])
                 if e.get("type") == "component" and (e.get("name") or e.get("id"))}
        if names:
            dep_specs.append((s, names))
    _note_unmatched_pair("X5", comp_specs, dep_specs, "component diagram", "deployment diagram", I)
    for cs, cnames in comp_specs:
        for ds, dnames in dep_specs:
            shared = sorted(cnames & dnames)
            if not _same_bundle(cs, ds, shared):
                continue
            missing_logical = sorted(dnames - cnames)
            not_deployed = sorted(cnames - dnames)
            if missing_logical:
                W.append("X5 [%s <> %s] Deployment co component %s khong ton tai trong component diagram." %
                         (cs["_src"], ds["_src"], ", ".join("'%s'" % x for x in missing_logical)))
            if not_deployed:
                I.append("X5 [%s <> %s] Component diagram co %s chua duoc anh xa vao deployment diagram." %
                         (cs["_src"], ds["_src"], ", ".join("'%s'" % x for x in not_deployed)))

    # ------------------------------------------------ X6: cung ten object khong duoc doi vai tro structural trong cung bundle
    roles = defaultdict(set)
    sources = defaultdict(set)
    for s in by["communication"] + by["sequence"]:
        scope = _scope_key(s)
        for e in s.get("elements", []):
            if e.get("type") == "actor":
                continue
            n = norm(obj_class(e))
            if not n:
                continue
            key = (scope, n)
            roles[key].add(st_of(e))
            sources[key].add(s["_src"])
    for s in by["class"]:
        scope = _scope_key(s)
        for e in s.get("elements", []):
            if st_of(e) == "entity":
                n = norm(e.get("name", e.get("id")))
                if n:
                    key = (scope, n)
                    roles[key].add("entity")
                    sources[key].add(s["_src"])
    for (scope, n), rs in roles.items():
        structural = {r for r in rs if r in COMET_OBJ or r == "entity"}
        if "entity" in structural and len(structural) > 1:
            W.append("X6 [%s] Ten '%s' trong bundle '%s' xuat hien voi vai tro structural mau thuan: %s. "
                     "Mot doi tuong entity khong nen dong thoi la boundary/control/application logic." %
                     (", ".join(sorted(sources[(scope, n)])), n,
                      "default" if scope == "__default__" else scope,
                      ", ".join(sorted(structural))))
    return E, W, I


def check_design_trace(by, W, I):
    """X8: lifeline cua sequence muc thiet ke phai la lop trong class diagram muc thiet ke cung bundle;
    message goi toi lop co khai bao operations nen trung ten mot operation (INFO)."""
    classes = defaultdict(dict)   # (scope, useCase|"") -> ten lop chuan hoa -> tap ten operation
    for s in by["class"]:
        if not is_design(s):
            continue
        for e in s.get("elements", []):
            if norm(e.get("type")) in ("note", "enumeration"):
                continue
            ops = {mname(str(o).lstrip("+-#~ ").split("(")[0].split(":")[0]) for o in e.get("operations") or []}
            for k in ((_scope_key(s), ""), (_scope_key(s), norm(s.get("useCase")))):
                classes[k].setdefault(norm(e.get("name", e.get("id"))), set()).update(ops)
    for s in by["sequence"] + by["communication"]:
        if not is_design(s):
            continue
        scope = _scope_key(s)
        pool = classes.get((scope, norm(s.get("useCase"))))
        # Khong co class diagram rieng cho use case nay (vd SDS III Authentication Flow) -> so voi moi lop
        # thiet ke cua bundle nhung chi ghi chu.
        MISSING = W if pool else I
        pool = pool or classes.get((scope, ""))
        if not pool:
            continue   # bundle chua co class diagram muc thiet ke -> khong kiem
        els = lifelines(s)
        for i, e in els.items():
            if e.get("type") == "actor" or e.get("external"):
                continue
            if norm(obj_class(e)) not in pool:
                MISSING.append("X8 [%s] Lifeline '%s' khong co lop cung ten trong class diagram muc thiet ke cung bundle - "
                         "them lop vao class diagram (hoac dat \"external\": true neu la Client/Browser/he thong ngoai)."
                         % (s["_src"], obj_class(e)))
        for m in s.get("messages", []):
            b = els.get(str(m.get("to")))
            name = m.get("name", m.get("label"))
            if b is None or is_reply(m) or not name or b.get("type") == "actor" or b.get("external"):
                continue
            ops = pool.get(norm(obj_class(b)))
            if ops and mname(name) not in ops:
                I.append("X8 [%s] Message '%s' toi '%s' khong trung operation nao cua lop trong class diagram."
                         % (s["_src"], name, obj_class(b)))


def check_design_structure(by, W):
    """X9: thuoc tinh lop entity (muc thiet ke) <-> cot bang vat ly cung bundle.
    X10: lop thiet ke <-> lop dat trong package diagram cung bundle (chi khi package diagram co lop)."""
    tables = defaultdict(dict)   # scope -> compact(entity) -> (ten bang, tap cot)
    for s in by["erd"]:
        for e in s.get("elements", []):
            if norm(e.get("type")) != "table" or not e.get("entity"):
                continue
            cols = {norm(c.get("name")) for c in e.get("columns") or [] if isinstance(c, dict) and c.get("name")}
            for ent in e["entity"] if isinstance(e["entity"], list) else [e["entity"]]:
                tables[_scope_key(s)].setdefault(compact(ent), (e.get("name", e.get("id")), cols))
    placed = defaultdict(set)   # scope -> lop co trong package diagram
    for s in by["package"]:
        for e in s.get("elements", []):
            if norm(e.get("type")) in ("class", "interface", "enumeration", "enum"):
                placed[_scope_key(s)].add(compact(e.get("name", e.get("id"))))
    for s in by["class"]:
        if not is_design(s):
            continue
        scope = _scope_key(s)
        missing = []
        for e in s.get("elements", []):
            typ = norm(e.get("type") or "class")
            cname = e.get("name", e.get("id"))
            if typ in ("class", "interface", "enumeration", "enum") and placed[scope] and \
                    "<" not in str(cname) and compact(cname) not in placed[scope]:
                missing.append(cname)
            tb = tables[scope].get(compact(cname)) if typ == "class" else None
            if not tb or not tb[1]:
                continue
            bad = []
            for a in e.get("attributes") or []:
                n, at = parse_attr(a)
                if not n or COLLECTION_RE.search(at):
                    continue
                sn = snake(n)
                if sn not in tb[1] and sn + "_id" not in tb[1]:
                    bad.append(n)
            if bad:
                W.append("X9 [%s] Lop entity '%s' co thuoc tinh khong co cot tuong ung trong bang '%s' (SDS I.3): %s - "
                         "them cot vao bang hoac sua ten cho khop (camelCase <-> snake_case)."
                         % (s["_src"], cname, tb[0], ", ".join("'%s'" % x for x in bad)))
        if missing:
            W.append("X10 [%s] Lop thiet ke chua co trong package diagram (SDS I.2) cung bundle: %s - dat lop vao "
                     "package dung tang (\"in\": <id package>)." % (s["_src"], ", ".join("'%s'" % x for x in missing)))


def check_sync_replies(by, W):
    """R15: sequence muc thiet ke - moi loi goi dong bo A -> B co reply B -> A phia sau."""
    for s in by["sequence"]:
        if not is_design(s):
            continue
        els = lifelines(s)
        pending = []
        for m in s.get("messages", []):
            a, b = str(m.get("from")), str(m.get("to"))
            if a not in els or b not in els or a == b:
                continue
            if norm(m.get("type") or "sync") in ("sync", "call"):
                if els[b].get("type") != "actor":
                    pending.append((a, b, m.get("name", m.get("label"))))
            elif is_reply(m):
                for k in range(len(pending) - 1, -1, -1):
                    if pending[k][:2] == (b, a):
                        del pending[k]
                        break
        for a, b, name in pending:
            W.append("R15 [%s] Loi goi dong bo '%s' (%s -> %s) chua co reply - them message \"type\": \"reply\" "
                     "tu %s ve %s (ket qua / void), hoac dat \"type\": \"async\" neu khong cho ket qua."
                     % (s["_src"], name, obj_class(els[a]), obj_class(els[b]), obj_class(els[b]), obj_class(els[a])))


def check_comm_vs_seq(inter, W, I):
    """R12: communication va sequence diagram cua cung use case phai the hien cung mot tap message."""
    groups = defaultdict(lambda: defaultdict(list))
    for s in inter:
        uc = s.get("useCase") or s.get("title")
        groups[(_scope_key(s), norm(uc))][str(s.get("diagram", "")).lower()].append(s)
    for (scope, uc), g in groups.items():
        if not g["communication"] or not g["sequence"]:
            continue
        src = "%s <> %s" % (", ".join(s["_src"] for s in g["communication"]),
                            ", ".join(s["_src"] for s in g["sequence"]))
        ucname = g["communication"][0].get("useCase") or g["communication"][0].get("title")
        bundle_name = "default" if scope == "__default__" else scope
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
                         % (src, shown[n], here, there, ucname + " (bundle " + bundle_name + ")"))
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
    ap.add_argument("--profile", choices=PROFILES,
                    help="kiem bo so do du theo template (sep490: Report 3 SRS + Report 4 SDS, luat P1-P10)")
    ap.add_argument("--strict", action="store_true",
                    help="co WARN thi tra ma thoat 1 (dung cho CI/kiem tra cuoi)")
    ap.add_argument("--json", action="store_true",
                    help="xuat report JSON may-doc thay vi output text")
    ap.add_argument("--model-schema-version", choices=("1", "2"), default="2",
                    help="schema semantic model embedded in --json (mac dinh: 2)")
    ap.add_argument("--legacy-model", action="store_true",
                    help="alias cua --model-schema-version 1")
    a = ap.parse_args()
    specs = load(a.specs)
    E, W, I = check(specs, partial=a.partial, profile=a.profile)
    if a.json:
        # Import lazily de tranh circular import khi comet_model tai cac helper tu module nay.
        from comet_model import build_model
        version = 1 if a.legacy_model else int(a.model_schema_version)
        print(json.dumps({
            "summary": {"errors": len(E), "warnings": len(W), "infos": len(I)},
            "errors": E,
            "warnings": W,
            "infos": I,
            "partial": bool(a.partial),
            "profile": a.profile,
            "strict": bool(a.strict),
            "model": build_model(specs, schema_version=version),
        }, ensure_ascii=False, indent=2))
    else:
        print("COMET check: %d loi, %d canh bao, %d ghi chu" % (len(E), len(W), len(I)))
        for x in E:
            print("  ERROR:", x)
        for x in W:
            print("  WARN :", x)
        for x in I:
            print("  INFO :", x)
    sys.exit(1 if E or (a.strict and W) else 0)


if __name__ == "__main__":
    main()
