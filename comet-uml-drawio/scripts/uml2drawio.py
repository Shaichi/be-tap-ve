#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uml2drawio.py - Sinh so do draw.io chuan UML / COMET tu spec JSON, bo cuc tu dong khong chong hinh.

Cach dung:
  python uml2drawio.py spec.json [spec2.json ...] -o out.drawio      # nhieu spec -> nhieu trang
  python uml2drawio.py spec.json --xml-only > model.xml             # chi in <mxGraphModel> (cho MCP)
  python uml2drawio.py spec.json -o out.drawio --no-validate

Loai so do (truong "diagram"):
  usecase | context | class | communication | sequence | state | activity |
  component | deployment | package | erd | screenflow | bizcontext

Xem references/spec-format.md de biet dinh dang spec day du.
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import math
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict

sys.dont_write_bytecode = True  # khong ghi __pycache__ vao thu muc skill
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import LEdge, label_geometry, layered_layout, tree_layout  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# =============================================================== text metrics
_NARROW = set("iljI.,:;|!'`")
_SEMI = set("frt()[]{}-/\\\"*")
_WIDE = set("mwMW@%")


def _cw(ch):
    if ch == " ":
        return 0.30
    if unicodedata.category(ch).startswith("M"):
        return 0.0
    if ch in _NARROW:
        return 0.30
    if ch in _SEMI:
        return 0.40
    if ch in _WIDE:
        return 0.92
    if ord(ch) >= 0x2E80:
        return 1.0
    if ch.isupper() or ch in "«»→←↑↓":
        return 0.72
    if ch.isdigit():
        return 0.58
    return 0.58


def text_size(text, size=12, bold=False):
    lines = str(text).split("\n")
    w = max(sum(_cw(c) for c in unicodedata.normalize("NFC", l)) for l in lines)
    w *= size * (1.08 if bold else 1.0)
    return math.ceil(w) + 4, math.ceil(len(lines) * size * 1.3)


def wrap(text, max_px, size=12):
    """Ngat dong theo do rong pixel uoc luong (giu cac \\n co san)."""
    out = []
    for para in str(text).split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            cand = (cur + " " + w).strip()
            if cur and text_size(cand, size)[0] > max_px:
                out.append(cur)
                cur = w
            else:
                cur = cand
        out.append(cur)
    return out


def esc(s):
    return html.escape(str(s), quote=False).replace("\n", "<br>")


def stereo(st):
    if not st:
        return ""
    if isinstance(st, (list, tuple)):
        return "«" + ", ".join(st) + "»"
    st = str(st).strip().strip("«»<>").strip()
    return "«" + st + "»"


def first_stereo(st):
    if isinstance(st, (list, tuple)):
        st = st[0] if st else ""
    return str(st or "").strip().strip("«»<>").strip().lower()


# =============================================================== COMET knowledge
# Thu tu cot (trai -> phai) trong communication diagram theo cac nhom cau truc doi tuong COMET
COMM_CAT = {
    "actor": 0,
    "boundary": 1, "user interaction": 1, "input": 1, "output": 1, "i/o": 1, "io": 1,
    "input/output": 1, "device i/o": 1, "device io": 1, "proxy": 1, "network interaction": 1,
    "gui": 1, "external system proxy": 1,
    "control": 2, "coordinator": 2, "state dependent control": 2, "state-dependent control": 2,
    "timer": 2,
    "application logic": 3, "business logic": 3, "algorithm": 3, "service": 3,
    "entity": 4, "database wrapper": 4, "data abstraction": 4,
}

FRAME_KIND = {
    "usecase": "uc", "class": "class", "context": "class", "communication": "sd",
    "sequence": "sd", "state": "stm", "activity": "act", "component": "cmp",
    "deployment": "deployment", "package": "pkg",
    # so do nghiep vu / du lieu (khong phai UML): khung chi ghi ten
    "erd": "", "screenflow": "", "bizcontext": "",
}
DEFAULT_DIR = {"usecase": "LR", "communication": "LR", "screenflow": "LR"}
# quan he khong ghi "type": mac dinh theo loai so do (activity/state: luong co guard; erd: relationship...)
DEFAULT_REL = {"activity": "flow", "state": "transition", "erd": "relationship", "screenflow": "navigate"}

SCREEN_KINDS = {"screen", "page", "dialog", "popup"}
FLOW_NODES = {"initial", "final", "activityfinal", "flowfinal", "decision", "choice", "merge", "junction"}


def sitemap_mode(spec):
    """Screen flow dang so do trang (site map): bo cuc cay, hop don gian, khong khung.
    `"layout": "tree"` / `"layered"` chon tuong minh; bo trong -> tu nhan: khong co nut initial/final/decision,
    khong man hinh nao liet ke `items`, khong dieu huong nao ghi trigger/guard/label."""
    if str(spec.get("diagram", "")).lower() != "screenflow":
        return False
    lay = str(spec.get("layout") or "").lower()
    if lay:
        return lay in ("tree", "sitemap", "site-map", "navigation")
    for e in spec.get("elements", []):
        if str(e.get("type", "")).lower() in FLOW_NODES or e.get("items") or e.get("fields") or e.get("in"):
            return False
    return not any(r.get(k) for r in spec.get("relations", [])
                   for k in ("trigger", "event", "guard", "label", "name", "action"))

CHEN_REL = {"relationship", "diamond", "relation"}


def chen_mode(spec):
    """ERD luon ve theo ky hieu Chen (muc khai niem): thuc the = o chi ghi ten, quan he = hinh thoi,
    ban so 1/N/M o dau noi phia thuc the."""
    return str(spec.get("diagram", "")).lower() == "erd"


def chen_expand(spec, warns=None):
    """Spec Chen -> spec do thi: moi relationship giua 2 entity (from/to + name) sinh 1 hinh thoi o giua va 2 canh
    khong mui ten; ban so (fromCard/toCard) ghi o dau phia entity. Relation noi thang vao phan tu hinh thoi
    (`"type": "relationship"`, cho quan he bac 3+) giu nguyen, ban so lay tu `card`."""
    sp = dict(spec)
    els = [dict(e, _chen=True) for e in spec.get("elements", [])]
    if warns is not None:
        for e in els:
            if e.get("attributes"):
                warns.append("ERD Chen khong ve thuoc tinh: bo qua 'attributes' cua '%s'." % e.get("name", e.get("id")))
    ids = {str(e.get("id", e.get("name"))) for e in els}
    dia = {str(e.get("id", e.get("name"))) for e in els if str(e.get("type", "")).lower() in CHEN_REL}
    rels = []

    def uid(base):
        base = re.sub(r"\W+", "_", base).strip("_") or "rel"
        i, c = 1, base
        while c in ids:
            i += 1
            c = "%s_%d" % (base, i)
        ids.add(c)
        return c

    for i, r in enumerate(spec.get("relations", [])):
        a, b = str(r.get("from")), str(r.get("to"))
        fc = r.get("fromCard", r.get("fromMult"))
        tc = r.get("toCard", r.get("toMult"))
        base = {k: v for k, v in r.items() if k in ("from", "to")}
        if a in dia or b in dia:
            card = r.get("card", r.get("cardinality"))
            rels.append(dict(base, type="chenlink", id=r.get("id") or "e%d" % (i + 1),
                             _sc=(fc if fc not in (None, "") else card) if b in dia else None,
                             _dc=(tc if tc not in (None, "") else card) if a in dia else None))
            continue
        name = r.get("name", r.get("label")) or ""
        rid = uid(str(r.get("id") or "r_%s" % (name or "%s_%s" % (a, b))))
        els.append({"id": rid, "type": "relationship", "name": name, "_chen": True,
                    "identifying": r.get("identifying")})
        rels.append({"type": "chenlink", "id": rid + "_a", "from": a, "to": rid, "_sc": fc})
        rels.append({"type": "chenlink", "id": rid + "_b", "from": rid, "to": b, "_dc": tc})
    sp["elements"], sp["relations"] = els, rels
    sp.setdefault("direction", "TB")
    return sp


EDGE_BASE = "html=1;rounded=0;fontSize=11;labelBackgroundColor=#ffffff;jumpStyle=arc;jumpSize=6;endSize=10;startSize=10;"


# =============================================================== element rendering
class Elem:
    def __init__(self, sp):
        self.sp = sp
        self.id = str(sp["id"])
        self.kind = str(sp.get("type", "class")).lower()
        self.style = ""
        self.value = ""
        self.w = self.h = 0.0
        self.sr = (0.0, 0.0, 0.0, 0.0)
        self.perim = "rect"
        self.category = None
        self.lane = None         # chi so partition (swimlane) - chi phan tu cap goc
        self.sub = []            # (suffix, value, style, x, y, w, h) tuong doi hinh
        self.container = False
        self.head_h = 0.0
        self.min_w = 0.0
        self.inner = (0.0, 0.0)
        self.fx = self.fy = 0.0
        self.ax = self.ay = 0.0  # toa do tuyet doi cua hinh

    def box(self, w, h):
        self.w, self.h = float(w), float(h)
        self.sr = (0.0, 0.0, float(w), float(h))


CLASSLIKE = {"class", "interface", "object", "external", "system", "datatype", "enumeration",
             "entity", "box"}
BALL = ("lollipop", "ball")
LANE_HEAD, LANE_PAD0, LANE_PAD1 = 30, 18, 22   # tieu de swimlane, le truoc/sau noi dung (theo truc rank)


def _header_lines(sp, kind):
    """(text, bold, italic) cho phan dau hop class/object."""
    lines = []
    st = sp.get("stereotype")
    if kind == "interface" and not st:
        st = "interface"
    if kind == "enumeration" and not st:
        st = "enumeration"
    if st:
        lines.append((stereo(st), False, False))
    name = sp.get("name", sp["id"])
    if kind == "object":
        cls = sp.get("class")
        oname = sp.get("name") if sp.get("class") else None
        if cls:
            name = ("%s : %s" % (oname, cls)) if oname else (": %s" % cls)
        for l in wrap(name, 220):
            lines.append((l, False, False))
    else:
        for l in wrap(name, 220):
            lines.append((l, True, bool(sp.get("abstract"))))
    return lines


def _html_lines(lines):
    out = []
    for t, b, i in lines:
        s = esc(t)
        if i:
            s = "<i>%s</i>" % s
        if b:
            s = "<b>%s</b>" % s
        out.append(s)
    return "<br>".join(out)


def render(sp, direction, diagram):
    el = Elem(sp)
    k = el.kind
    name = str(sp.get("name", sp["id"]))

    if sp.get("_container"):
        return render_container(el, sp, direction)

    if k == "actor":
        lines = ([stereo(sp["stereotype"])] if sp.get("stereotype") else []) + wrap(name, 130)
        lw, lh = text_size("\n".join(lines))
        el.value = "<br>".join(esc(l) for l in lines)
        base = "shape=umlActor;html=1;outlineConnect=0;whiteSpace=nowrap;labelBackgroundColor=none;"
        if direction == "TB":
            el.style = base + "labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=4;"
            el.w, el.h = 30 + 8 + lw, max(60, lh)
            el.sr = (0.0, (el.h - 60) / 2, 30.0, 60.0)
        else:
            el.style = base + "verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;"
            el.w, el.h = max(30, lw + 4), 60 + lh + 6
            el.sr = ((el.w - 30) / 2, 0.0, 30.0, 60.0)
        return el

    if k == "usecase":
        lines = wrap(name, 150)
        lw, lh = text_size("\n".join(lines))
        el.value = "<br>".join(esc(l) for l in lines)
        el.style = "ellipse;whiteSpace=wrap;html=1;"
        el.box(max(130, math.ceil((lw + 14) * 1.42)), max(54, math.ceil((lh + 10) * 1.42)))
        el.perim = "ellipse"
        return el

    if k == "interface" and str(sp.get("notation", "")).lower() in BALL:
        # provided interface dang "lollipop": vong tron nho + ten ben canh
        lines = wrap(name, 160)
        lw, lh = text_size("\n".join(lines))
        el.value = "<br>".join(esc(l) for l in lines)
        base = "ellipse;html=1;whiteSpace=nowrap;labelBackgroundColor=none;"
        if direction == "TB":
            el.style = base + "labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=4;"
            el.w, el.h = 20 + 8 + lw, max(20, lh)
            el.sr = (0.0, (el.h - 20) / 2, 20.0, 20.0)
        else:
            el.style = base + "verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;"
            el.w, el.h = max(20, lw + 4), 20 + lh + 6
            el.sr = ((el.w - 20) / 2, 0.0, 20.0, 20.0)
        el.perim = "ellipse"
        return el

    if diagram == "erd" and sp.get("_chen"):
        return render_chen(el, sp, name)
    if k in SCREEN_KINDS:
        return render_screen(el, sp, name)

    if k in CLASSLIKE:
        head = _header_lines(sp, k)
        attrs = [str(a) for a in sp.get("attributes", sp.get("literals", [])) or []]
        ops = [str(o) for o in sp.get("operations", []) or []]
        widths = [text_size(t, 12, b)[0] for t, b, _ in head]
        widths += [text_size(a)[0] + 12 for a in attrs + ops]
        w = max([120 if k != "object" else 110] + [x + 24 for x in widths])
        hh = len(head) * 16 + 14
        el.value = _html_lines(head)
        if attrs or ops or sp.get("compartments"):
            ah = len(attrs) * 18 + 8 if attrs else 10
            oh = len(ops) * 18 + 8 if ops else 0
            el.style = (
                "swimlane;fontStyle=0;align=center;verticalAlign=top;childLayout=stackLayout;horizontal=1;"
                "startSize=%d;horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;collapsible=0;"
                "marginBottom=0;html=1;whiteSpace=wrap;" % hh
            )
            tstyle = ("text;strokeColor=none;fillColor=none;align=left;verticalAlign=top;spacingLeft=6;"
                      "spacingRight=4;overflow=hidden;rotatable=0;points=[[0,0.5],[1,0.5]];"
                      "portConstraint=eastwest;whiteSpace=wrap;html=1;")
            y = hh
            el.sub.append(("attrs", "<br>".join(esc(a) for a in attrs), tstyle, 0, y, w, ah))
            y += ah
            if ops:
                el.sub.append(("sep", "", "line;strokeWidth=1;fillColor=none;align=left;verticalAlign=middle;"
                               "spacingTop=-1;spacingLeft=3;spacingRight=3;rotatable=0;labelPosition=right;"
                               "points=[];portConstraint=eastwest;strokeColor=inherit;", 0, y, w, 8))
                y += 8
                el.sub.append(("ops", "<br>".join(esc(o) for o in ops), tstyle, 0, y, w, oh))
                y += oh
            el.box(w, y)
        else:
            el.style = "rounded=0;whiteSpace=wrap;html=1;"
            el.box(w, max(44, hh))
        return el

    if k in ("state", "action"):
        acts = [str(a) for a in sp.get("activities", []) or []]
        lines = wrap(name, 180)
        lw, lh = text_size("\n".join(lines))
        if acts and k == "state":
            aw = max(text_size(a)[0] for a in acts)
            w = max(110, lw + 30, aw + 24)
            hh = lh + 14
            ah = len(acts) * 18 + 8
            el.style = ("swimlane;rounded=1;arcSize=16;absoluteArcSize=1;startSize=%d;html=1;whiteSpace=wrap;"
                        "collapsible=0;fontStyle=0;childLayout=stackLayout;horizontal=1;horizontalStack=0;"
                        "resizeParent=1;resizeLast=0;marginBottom=0;" % hh)
            el.value = "<br>".join(esc(l) for l in lines)
            el.sub.append(("acts", "<br>".join(esc(a) for a in acts),
                           "text;strokeColor=none;fillColor=none;align=left;verticalAlign=top;spacingLeft=8;"
                           "html=1;whiteSpace=wrap;", 0, hh, w, ah))
            el.box(w, hh + ah)
        else:
            # state: bo tron nhieu; action (UML 2.5): chu nhat bo goc nho (ban kinh ~10px), khong phai hinh vien thuoc
            el.style = ("rounded=1;whiteSpace=wrap;html=1;arcSize=40;" if k == "state" else
                        "rounded=1;absoluteArcSize=1;arcSize=20;whiteSpace=wrap;html=1;")
            el.value = "<br>".join(esc(l) for l in lines)
            el.box(max(100, lw + 36), max(40, lh + 20))
        el.perim = "rounded"
        return el

    if k == "initial":
        el.style = "ellipse;html=1;fillColor=#000000;strokeColor=#000000;"
        el.box(24, 24)
        el.perim = "ellipse"
        return el
    if k in ("final", "activityfinal"):
        el.style = "ellipse;html=1;shape=endState;fillColor=#000000;strokeColor=#000000;"
        el.box(28, 28)
        el.perim = "ellipse"
        return el
    if k == "flowfinal":
        el.style = "shape=sumEllipse;perimeter=ellipsePerimeter;html=1;"
        el.box(26, 26)
        el.perim = "ellipse"
        return el
    if k in ("history", "deephistory"):
        el.value = "H*" if k == "deephistory" else "H"
        el.style = "ellipse;html=1;"
        el.box(30, 30)
        el.perim = "ellipse"
        return el
    if k in ("choice", "decision", "merge", "junction"):
        if k == "junction":
            el.style = "ellipse;html=1;fillColor=#000000;"
            el.box(14, 14)
            el.perim = "ellipse"
            return el
        # decision/choice: in cau hoi dieu kien ("PIN hop le?") trong thoi - lay `question`, hoac `name` neu co;
        # merge chi in ten khi showName. showName=false -> an.
        if sp.get("showName") is False:
            label = ""
        elif k == "merge":
            label = sp.get("question") or (sp.get("name") if sp.get("showName") else "")
        else:
            label = sp.get("question") or sp.get("name") or ""
        label = str(label).strip()
        el.style = "rhombus;html=1;whiteSpace=wrap;fontSize=11;spacing=0;"
        if not label:
            el.box(40, 40)
        else:
            lines = wrap(label, 90)
            lw, lh = text_size("\n".join(lines), 11)
            el.value = "<br>".join(esc(l) for l in lines)
            # hinh chu nhat chu (lw x lh) nam tron trong thoi khi lw/w + lh/h <= 1 -> w = 2(lw+pad), h = 2(lh+pad);
            # tang h de thoi khong qua det (rong <= 2.2 x cao) - chi lam thoi to hon nen chu van nam trong
            w = max(60, math.ceil(2 * (lw + 8)))
            h = max(44, math.ceil(2 * (lh + 6)), math.ceil(w / 2.2))
            el.box(max(w, math.ceil(h * 1.3)), h)
        el.perim = "rhombus"
        return el
    if k in ("fork", "join"):
        el.style = "html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#000000;strokeColor=none;"
        length = sp.get("length", 120)
        el.box(*((length, 6) if direction == "TB" else (6, length)))
        return el

    if k == "note":
        lines = wrap(str(sp.get("text", name)), 220)
        lw, lh = text_size("\n".join(lines))
        el.value = "<br>".join(esc(l) for l in lines)
        el.style = "shape=note;whiteSpace=wrap;html=1;size=14;align=left;spacingLeft=6;verticalAlign=top;spacingTop=4;"
        el.box(lw + 30, lh + 20)
        return el

    if k in ("component", "subsystem_component"):
        st = sp.get("stereotype") or "component"
        head = [(stereo(st), False, False)] + [(l, True, False) for l in wrap(name, 200)]
        w = max([140] + [text_size(t, 12, b)[0] + 60 for t, b, _ in head])
        h = len(head) * 16 + 24
        el.value = _html_lines(head)
        el.style = "html=1;whiteSpace=wrap;"
        el.sub.append(("icon", "", "shape=module;jettyWidth=8;jettyHeight=4;html=1;", w - 28, 6, 20, 20))
        el.box(w, max(56, h))
        return el

    if k in ("node", "device", "executionenvironment"):
        st = sp.get("stereotype") or {"node": "node", "device": "device"}.get(k, "execution environment")
        head = [(stereo(st), False, False)] + [(l, True, False) for l in wrap(name, 200)]
        w = max([140] + [text_size(t, 12, b)[0] + 34 for t, b, _ in head])
        el.value = _html_lines(head)
        el.style = ("shape=cube;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;darkOpacity=0.05;"
                    "darkOpacity2=0.1;size=12;")
        el.box(w, len(head) * 16 + 40)
        return el

    if k == "artifact":
        head = [("«artifact»", False, False)] + [(l, False, False) for l in wrap(name, 200)]
        w = max([110] + [text_size(t)[0] + 34 for t, _, _ in head])
        el.value = _html_lines(head)
        el.style = "shape=note2;boundedLbl=1;whiteSpace=wrap;html=1;size=14;verticalAlign=middle;align=center;"
        el.box(w, len(head) * 16 + 22)
        return el

    if k in ("package", "subsystem"):
        st = sp.get("stereotype") or ("subsystem" if k == "subsystem" else None)
        head = ([(stereo(st), False, False)] if st else []) + [(name, True, False)]
        tw = max(text_size(t, 12, b)[0] for t, b, _ in head) + 16
        th = len(head) * 15 + 8
        el.value = _html_lines(head)
        el.style = ("shape=folder;tabWidth=%d;tabHeight=%d;tabPosition=left;html=1;whiteSpace=wrap;"
                    "verticalAlign=top;align=left;spacingLeft=8;spacingTop=2;" % (tw, th))
        el.box(max(150, tw + 40), th + 50)
        return el

    # fallback: hop chu nhat co stereotype
    head = ([(stereo(sp["stereotype"]), False, False)] if sp.get("stereotype") else []) + [(name, True, False)]
    el.value = _html_lines(head)
    el.style = "rounded=0;whiteSpace=wrap;html=1;"
    el.box(max([110] + [text_size(t, 12, b)[0] + 24 for t, b, _ in head]), len(head) * 16 + 20)
    return el


def render_chen(el, sp, name):
    """ERD Chen: entity = o chu nhat ten dam (thuc the yeu: vien kep); relationship = hinh thoi ten thuong."""
    if el.kind in CHEN_REL:
        lines = wrap(name, 140)
        lw, lh = text_size("\n".join(lines), 11)
        el.value = "<br>".join(esc(l) for l in lines)
        el.style = "rhombus;whiteSpace=wrap;html=1;fontSize=11;spacing=0;fillColor=#ffe6cc;"
        if el.sp.get("identifying"):
            el.style += "double=1;"
        el.box(max(72, math.ceil(lw * 1.35 + 14)), max(40, math.ceil(lh * 2 + 12)))
        el.perim = "rhombus"
        return el
    lines = wrap(name, 200)
    lw, lh = text_size("\n".join(lines), 12, True)
    el.value = "<br>".join(esc(l) for l in lines)
    el.style = "rounded=0;whiteSpace=wrap;html=1;fontStyle=1;fillColor=#dae8fc;"
    if sp.get("weak"):
        el.style = "shape=ext;double=1;" + el.style
    el.box(max(90, math.ceil(lw + 24)), max(30, math.ceil(lh + 14)))
    return el


def render_screen(el, sp, name):
    """Screen flow: man hinh = cua so co thanh tieu de (ten) + than liet ke thanh phan UI (`items`).
    dialog/popup: net dut, tieu de mau vang, «dialog»."""
    k = el.kind
    dialog = k in ("dialog", "popup")
    items = [str(x) for x in sp.get("items", sp.get("fields", [])) or []]
    if not items:
        # chi co ten: hop don gian - man hinh chu nhat, dialog/popup bo goc tron (kieu so do trang)
        lines = ([(stereo(sp["stereotype"]), False, False)] if sp.get("stereotype") else []) +                 [(l, False, False) for l in wrap(name, 200)]
        el.value = _html_lines(lines)
        el.style = ("rounded=%d;%swhiteSpace=wrap;html=1;fillColor=%s;"
                    % (1 if dialog else 0, "absoluteArcSize=1;arcSize=24;" if dialog else "",
                       "#fff2cc" if dialog else "#dae8fc"))
        el.box(max(100, max(text_size(t, 12, b)[0] for t, b, _ in lines) + 16), max(48, len(lines) * 16 + 18))
        el.perim = "rounded" if dialog else "rect"
        return el
    st = sp.get("stereotype") or ("dialog" if dialog else None)
    head = ([(stereo(st), False, False)] if st else []) + [(l, True, False) for l in wrap(name, 200)]
    lines = [l for it in items for l in wrap(it, 240)]
    w = max([150] + [text_size(t, 12, b)[0] + 24 for t, b, _ in head] + [text_size(l)[0] + 20 for l in lines])
    hh = len(head) * 16 + 10
    ah = max(44, len(lines) * 18 + 12)
    el.value = _html_lines(head)
    el.style = ("swimlane;rounded=1;arcSize=8;absoluteArcSize=1;startSize=%d;html=1;whiteSpace=wrap;collapsible=0;"
                "fontStyle=0;childLayout=stackLayout;horizontal=1;horizontalStack=0;resizeParent=1;resizeLast=0;"
                "marginBottom=0;swimlaneFillColor=#ffffff;fillColor=%s;%s"
                % (hh, "#fff2cc" if dialog else "#dae8fc", "dashed=1;" if dialog else ""))
    el.sub.append(("ui", "<br>".join(esc(l) for l in lines),
                   "text;strokeColor=none;fillColor=none;align=left;verticalAlign=top;spacingLeft=8;spacingTop=2;"
                   "html=1;whiteSpace=wrap;fontColor=#333333;", 0, hh, w, ah))
    el.box(w, hh + ah)
    el.perim = "rounded"
    return el


def render_container(el, sp, direction):
    """Container (composite state, package/subsystem, node, component...) - kich thuoc dat sau."""
    k = el.kind
    name = str(sp.get("name", sp["id"]))
    el.container = True
    if k == "state":
        lines = [(l, False, False) for l in wrap(name, 260)]
        hh = len(lines) * 16 + 12
        el.style = ("swimlane;rounded=1;arcSize=20;absoluteArcSize=1;startSize=%d;html=1;whiteSpace=wrap;"
                    "collapsible=0;fontStyle=0;container=1;" % hh)
        el.perim = "rounded"
    elif k in ("package", "subsystem"):
        st = sp.get("stereotype") or ("subsystem" if k == "subsystem" else None)
        lines = ([(stereo(st), False, False)] if st else []) + [(name, True, False)]
        tw = max(text_size(t, 12, b)[0] for t, b, _ in lines) + 16
        hh = len(lines) * 15 + 8
        el.style = ("shape=folder;tabWidth=%d;tabHeight=%d;tabPosition=left;html=1;whiteSpace=wrap;"
                    "verticalAlign=top;align=left;spacingLeft=8;spacingTop=2;container=1;collapsible=0;" % (tw, hh))
    elif k in ("node", "device", "executionenvironment"):
        st = sp.get("stereotype") or {"node": "node", "device": "device"}.get(k, "execution environment")
        lines = [(stereo(st), False, False), (name, True, False)]
        hh = len(lines) * 16 + 16
        el.style = ("shape=cube;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;darkOpacity=0.05;"
                    "darkOpacity2=0.1;size=12;verticalAlign=top;container=1;collapsible=0;")
    else:
        st = sp.get("stereotype") or ("component" if k == "component" else None)
        lines = ([(stereo(st), False, False)] if st else []) + [(name, True, False)]
        hh = len(lines) * 16 + 12
        el.style = "rounded=0;whiteSpace=wrap;html=1;verticalAlign=top;container=1;collapsible=0;"
    el.value = _html_lines(lines)
    el.head_h = hh
    el.min_w = max(text_size(t, 12, b)[0] for t, b, _ in lines) + (70 if k == "component" else 40)
    return el


def finish_container(el):
    """Goi sau khi container da co kich thuoc: them phan trang tri phu thuoc do rong (icon component)."""
    if el.kind == "component":
        el.sub.append(("icon", "", "shape=module;jettyWidth=8;jettyHeight=4;html=1;", el.w - 28, 6, 20, 20))


# =============================================================== relation styles
def rel_style(rel, diagram, to_ball=False):
    """-> (style, label, src_label, dst_label, layout_reverse)"""
    t = str(rel.get("type") or DEFAULT_REL.get(diagram, "association")).lower()
    if to_ball and t == "realization":
        t = "provides"
    label = rel.get("label", rel.get("name"))
    s_lab = "\n".join(str(x) for x in (rel.get("fromRole"), rel.get("fromMult")) if x)
    d_lab = "\n".join(str(x) for x in (rel.get("toRole"), rel.get("toMult")) if x)
    lrev = False
    nav = rel.get("navigable")
    if t == "chenlink":   # ERD Chen: duong lien khong mui ten, ban so o dau phia entity
        sc, dc = rel.get("_sc"), rel.get("_dc")
        return ("endArrow=none;startArrow=none;", None, (str(sc) if sc not in (None, "") else None),
                (str(dc) if dc not in (None, "") else None), False)
    if t == "association":
        st = "endArrow=%s;endFill=0;" % ("open" if nav else "none")
    elif t == "aggregation":
        st = "startArrow=diamondThin;startFill=0;startSize=16;endArrow=%s;endFill=0;" % ("open" if nav else "none")
    elif t == "composition":
        st = "startArrow=diamondThin;startFill=1;startSize=16;endArrow=%s;endFill=0;" % ("open" if nav else "none")
    elif t == "generalization":
        st, lrev = "endArrow=block;endFill=0;endSize=14;", True
        label = rel.get("label")
    elif t == "realization":
        st, lrev = "endArrow=block;endFill=0;endSize=14;dashed=1;", True
    elif t == "dependency":
        st = "endArrow=open;endFill=0;dashed=1;"
        if rel.get("stereotype"):
            label = stereo(rel["stereotype"]) + (("\n" + label) if label else "")
    elif t == "include":
        st = "endArrow=open;endFill=0;dashed=1;"
        label = "«include»"
    elif t == "extend":
        st, lrev = "endArrow=open;endFill=0;dashed=1;", True
        label = "«extend»" + (("\n[" + rel["condition"].strip("[]") + "]") if rel.get("condition") else "")
    elif t in ("transition", "flow", "navigate", "navigation"):
        st = "endArrow=open;endFill=0;"
        if not label:
            parts = []
            ev = rel.get("event") or rel.get("trigger")   # screen flow: trigger = thao tac nguoi dung
            if ev:
                parts.append(str(ev))
            if rel.get("guard"):
                parts.append("[" + str(rel["guard"]).strip("[]") + "]")
            txt = " ".join(parts)
            if rel.get("action"):
                act = rel["action"]
                if isinstance(act, (list, tuple)):
                    act = ", ".join(act)
                txt = (txt + " / " if txt else "/ ") + str(act)
            label = txt or None
    elif t == "anchor":
        st, lrev = "endArrow=none;dashed=1;", True
    elif t == "link":
        st = "endArrow=none;"
    elif t in ("connector", "communicationpath", "path"):
        st = "endArrow=%s;endFill=0;" % ("open" if nav else "none")
        if rel.get("stereotype"):
            label = stereo(rel["stereotype"]) + (("\n" + label) if label else "")
    elif t in ("usage", "requires", "require", "uses"):
        st = "endArrow=open;endFill=0;dashed=1;"
        label = "«use»" + (("\n" + label) if label else "")
    elif t in ("provides", "provide"):
        # component -- (lollipop): duong lien khong mui ten; interface dat "truoc" component trong bo cuc
        st, lrev = "endArrow=none;", True
    elif t == "message":  # async/sync message tren connector
        st = "endArrow=open;endFill=0;"
    else:
        st = "endArrow=none;"
    if label:
        label = "\n".join(wrap(str(label), 200))
    return st, label, (s_lab or None), (d_lab or None), lrev


# =============================================================== graph diagrams
class Out:
    def __init__(self):
        self.root = ET.Element("root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self.ids = {"0", "1"}
        self.maxx = self.maxy = 0

    def uid(self, base):
        base = re.sub(r"\s+", "_", str(base))
        i, cand = 1, base
        while cand in self.ids:
            i += 1
            cand = "%s_%d" % (base, i)
        self.ids.add(cand)
        return cand

    def vertex(self, id, value, style, x, y, w, h, parent="1", absx=None, absy=None):
        c = ET.SubElement(self.root, "mxCell", id=id, value=value or "", style=style, vertex="1", parent=parent)
        ET.SubElement(c, "mxGeometry", x=_n(x), y=_n(y), width=_n(w), height=_n(h), **{"as": "geometry"})
        ax = x if absx is None else absx
        ay = y if absy is None else absy
        self.maxx, self.maxy = max(self.maxx, ax + w), max(self.maxy, ay + h)
        return c

    def edge(self, id, value, style, src, tgt, points, parent="1", gx=None, offset=None,
             spoint=None, tpoint=None):
        attrs = dict(id=id, value=value or "", style=style, edge="1", parent=parent)
        if src:
            attrs["source"] = src
        if tgt:
            attrs["target"] = tgt
        c = ET.SubElement(self.root, "mxCell", **attrs)
        ga = {"relative": "1", "as": "geometry"}
        if gx is not None:
            ga["x"] = _n(gx, 4)
        g = ET.SubElement(c, "mxGeometry", **ga)
        if spoint:
            ET.SubElement(g, "mxPoint", x=_n(spoint[0]), y=_n(spoint[1]), **{"as": "sourcePoint"})
        if tpoint:
            ET.SubElement(g, "mxPoint", x=_n(tpoint[0]), y=_n(tpoint[1]), **{"as": "targetPoint"})
        if offset is not None:
            ET.SubElement(g, "mxPoint", x=_n(offset[0]), y=_n(offset[1]), **{"as": "offset"})
        if points:
            arr = ET.SubElement(g, "Array", **{"as": "points"})
            for p in points:
                ET.SubElement(arr, "mxPoint", x=_n(p[0]), y=_n(p[1]))
        return c

    def edge_label(self, id, parent_edge, value, gx, offset, style_extra=""):
        c = ET.SubElement(self.root, "mxCell", id=id, value=value, vertex="1", connectable="0", parent=parent_edge,
                          style="edgeLabel;resizable=0;html=1;align=center;verticalAlign=middle;fontSize=11;"
                                "labelBackgroundColor=#ffffff;" + style_extra)
        g = ET.SubElement(c, "mxGeometry", x=_n(gx, 4), relative="1", **{"as": "geometry"})
        ET.SubElement(g, "mxPoint", x=_n(offset[0]), y=_n(offset[1]), **{"as": "offset"})


def _n(v, nd=1):
    v = round(float(v), nd)
    return str(int(v)) if v == int(v) else str(v)


def _constraint(p, el, kind):
    x, y, w, h = el.ax, el.ay, el.sr[2], el.sr[3]
    fx = 0.5 if w == 0 else (p[0] - x) / w
    fy = 0.5 if h == 0 else (p[1] - y) / h
    fx, fy = min(1, max(0, fx)), min(1, max(0, fy))
    return "%sX=%s;%sY=%s;%sDx=0;%sDy=0;%sPerimeter=0;" % (kind, _n(fx, 4), kind, _n(fy, 4), kind, kind, kind)


def build_graph(spec, warns, origin):
    diagram = spec["diagram"]
    direction = str(spec.get("direction", DEFAULT_DIR.get(diagram, "TB"))).upper()
    sps = [dict(s) for s in spec.get("elements", [])]
    for s in sps:
        s.setdefault("id", s.get("name"))
        s["id"] = str(s["id"])
    ids = {s["id"] for s in sps}
    parent = {s["id"]: (str(s["in"]) if s.get("in") else None) for s in sps}
    for i, p in list(parent.items()):
        if p and p not in ids:
            warns.append("Phan tu '%s' khai bao in='%s' khong ton tai -> dat o goc." % (i, p))
            parent[i] = None
    kids = defaultdict(list)
    for s in sps:
        kids[parent[s["id"]]].append(s["id"])
    for s in sps:
        if kids.get(s["id"]):
            s["_container"] = True
    E = OrderedDict((s["id"], render(s, direction, diagram)) for s in sps)
    tree = sitemap_mode(spec) and not any(kids.get(s["id"]) for s in sps)

    # ------------------------------------------------ categories (COMET/UML conventions)
    rels = [dict(r, type=r.get("type") or DEFAULT_REL.get(diagram, "association")) for r in spec.get("relations", [])]
    cat_margin = None
    if diagram == "usecase":
        starters = {str(r.get("from")) for r in rels if str(r.get("type", "association")) == "association"}
        for el in E.values():
            if el.kind == "actor":
                side = el.sp.get("side") or ("left" if el.id in starters or el.sp.get("primary") else "right")
                el.category = 0 if side == "left" else 2
            else:
                el.category = 1
        cat_margin = {1: (34, 34)}
    elif diagram == "communication":
        for el in E.values():
            if el.kind == "actor":
                el.category = 9 if el.sp.get("side") == "right" else 0
            else:
                el.category = COMM_CAT.get(first_stereo(el.sp.get("stereotype")), 2)
        rels += comm_links(spec, warns)

    # ------------------------------------------------ partitions (swimlane, thuong dung cho activity)
    parts = _partitions(spec, E, parent, rels, warns)
    lane_w = [text_size(nm, 12, True)[0] + 30 for _, nm in parts] or None

    # ------------------------------------------------ relations -> layout edges (per level)
    def ancestors(x):
        out = [x]
        while parent.get(out[-1]):
            out.append(parent[out[-1]])
        return out

    level_edges = defaultdict(list)
    E_rel = {}
    for i, rel in enumerate(rels):
        u, v = str(rel.get("from")), str(rel.get("to"))
        if u not in E or v not in E:
            warns.append("Quan he #%d (%s): phan tu '%s' hoac '%s' khong ton tai -> bo qua." % (i + 1, rel.get("type"), u, v))
            continue
        au, av = ancestors(u), ancestors(v)
        if v in au[1:] or u in av[1:]:
            warns.append("Quan he %s->%s noi container voi phan tu con cua no: khong ho tro -> bo qua." % (u, v))
            continue
        if u == v:  # self-transition / self-association: nam o cap cua chinh phan tu
            lca, lu, lv = parent.get(u), u, v
        else:
            common = [a for a in au if a in av]
            lca = common[0] if common else None
            lu = next(a for a in au if parent.get(a) == lca)
            lv = next(a for a in av if parent.get(a) == lca)
        if (lu, lv) != (u, v):
            warns.append("Quan he %s->%s vuot bien container: da noi vao '%s'->'%s' (bien composite)." % (u, v, lu, lv))
        to_ball = E[v].kind == "interface" and str(E[v].sp.get("notation", "")).lower() in BALL
        st, lab, sl, dl, lrev = rel_style(rel, diagram, to_ball)
        eid = str(rel.get("id") or "e%d" % (i + 1))
        le = LEdge(eid, lu, lv, lrev,
                   text_size(lab, 11) if lab else None,
                   text_size(sl, 11) if sl else None,
                   text_size(dl, 11) if dl else None)
        le.rel, le.style, le.label, le.sl, le.dl = rel, st, lab, sl, dl
        level_edges[lca].append(le)
        E_rel[eid] = le

    # widen class-like boxes so multiplicity labels on one side do not collide
    if direction == "TB":
        cnt = defaultdict(int)
        mx = defaultdict(float)
        for les in level_edges.values():
            for le in les:
                for end, lab in ((le.u, le.slab), (le.v, le.dlab)):
                    if lab:
                        cnt[end] += 1
                        mx[end] = max(mx[end], lab[0])
        for x, n in cnt.items():
            el = E[x]
            if el.kind in CLASSLIKE and not el.container:
                need = (n / 2 + 1) * (mx[x] + 14)
                if need > el.w:
                    _widen(el, need)

    results = {}

    def do_level(pid):
        for k in kids.get(pid, []):
            if kids.get(k):
                res = do_level(k)
                el = E[k]
                w = max(el.min_w, res["w"] + 40)
                h = el.head_h + 16 + res["h"] + 22
                el.inner = ((w - res["w"]) / 2, el.head_h + 16)
                el.box(w, h)
                finish_container(el)
        members = [E[k] for k in kids.get(pid, [])]
        if tree:
            results[pid] = res = tree_layout(members, level_edges.get(pid, []), spec.get("root"), warns)
            return res
        snap = {el.id: (el.w, el.h, el.sr, list(el.sub)) for el in members}
        for _ in range(3):
            res = layered_layout(members, level_edges.get(pid, []), direction,
                                 cat_margin if pid is None else None, lanes=lane_w if pid is None else None)
            grow = {k: w for k, w in res.get("need_w", {}).items()
                    if E[k].kind in CLASSLIKE and not E[k].container and w > snap[k][2][2] + 0.5}
            if not grow:
                break
            # nhan multiplicity khong du cho giua cac cong -> noi rong hop class roi bo cuc lai
            for el in members:
                el.w, el.h, el.sr, el.sub = snap[el.id][0], snap[el.id][1], snap[el.id][2], list(snap[el.id][3])
            for k, w in grow.items():
                _widen(E[k], w)
                snap[k] = (E[k].w, E[k].h, E[k].sr, list(E[k].sub))
        results[pid] = res
        return res

    root = do_level(None)

    def place(pid, ox, oy):
        for k in kids.get(pid, []):
            el = E[k]
            el.ax, el.ay = ox + el.fx + el.sr[0], oy + el.fy + el.sr[1]
            if kids.get(k):
                place(k, el.ax + el.inner[0], el.ay + el.inner[1])
        for le in level_edges.get(pid, []):
            le.abs = [(x + ox, y + oy) for x, y in le.pts]
            le.alab = (le.lab_c[0] + ox, le.lab_c[1] + oy) if le.lab_c else None
            le.asrc = (le.src_c[0] + ox, le.src_c[1] + oy) if le.src_c else None
            le.adst = (le.dst_c[0] + ox, le.dst_c[1] + oy) if le.dst_c else None
            le.level = pid

    # use case system boundary: tinh truoc de day ca so do xuong neu khung vuot ra ngoai goc
    bnd = None
    if diagram == "usecase" and 1 in root["cat_boxes"]:
        bx, by, bw, bh = root["cat_boxes"][1]
        title = spec.get("system") or spec.get("title") or "System"
        tw, th = text_size(title, 12, True)
        x0, y0 = bx - 20, by - 18 - th - 8
        x1, y1 = bx + bw + 20, by + bh + 18
        if x1 - x0 < tw + 20:
            d = (tw + 20 - (x1 - x0)) / 2
            x0, x1 = x0 - d, x1 + d
        origin = (origin[0] + max(0.0, -x0), origin[1] + max(0.0, -y0))
        bnd = (title, origin[0] + x0, origin[1] + y0, origin[0] + x1, origin[1] + y1)

    # swimlane: chua cho tieu de lan phia truoc noi dung (TB: phia tren, LR: ben trai)
    TB = direction != "LR"
    lanes_abs = []
    if parts:
        d = LANE_HEAD + LANE_PAD0
        origin = (origin[0], origin[1] + d) if TB else (origin[0] + d, origin[1])
        for (lid, nm), (rx, ry, rw, rh) in zip(parts, root["lanes"]):
            x, y = origin[0] + rx, origin[1] + ry
            if TB:
                lanes_abs.append((lid, nm, x, y - d, rw, rh + d + LANE_PAD1))
            else:
                lanes_abs.append((lid, nm, x - d, y, rw + d + LANE_PAD1, rh))

    place(None, origin[0], origin[1])

    # communication: build message labels now that positions are known
    if diagram == "communication":
        for le in E_rel.values():
            if le.rel.get("_messages"):
                le.label = comm_label(le, E, direction)

    out = Out()
    extra_bbox = []
    if bnd:
        title, x0, y0, x1, y1 = bnd
        out.vertex(out.uid("system_boundary"), esc(title),
                   "rounded=0;whiteSpace=wrap;html=1;fillColor=none;verticalAlign=top;fontStyle=1;spacingTop=4;",
                   x0, y0, x1 - x0, y1 - y0)
        extra_bbox.append((x0, y0, x1, y1))

    out.ids |= set(E)  # giu cho id phan tu truoc khi sinh id cho lan
    lane_cell = []
    for lid, nm, x, y, w, h in lanes_abs:
        cid = out.uid("lane_" + lid)
        out.vertex(cid, esc(nm),
                   "swimlane;html=1;whiteSpace=wrap;startSize=%d;horizontal=%d;collapsible=0;container=1;"
                   "fontStyle=1;fillColor=#f5f5f5;" % (LANE_HEAD, 1 if TB else 0), x, y, w, h)
        lane_cell.append((cid, x, y))

    def emit_el(k, pid):
        el = E[k]
        if pid is None and lane_cell:
            cid, lx, ly = lane_cell[el.lane or 0]
            x, y, par = el.ax - lx, el.ay - ly, cid
        elif pid is None:
            x, y, par = el.ax, el.ay, "1"
        else:
            p = E[pid]
            x, y, par = el.ax - p.ax, el.ay - p.ay, p.id
        style = el.style
        out.ids.add(el.id)
        out.vertex(el.id, el.value, style, x, y, el.sr[2], el.sr[3], par, el.ax, el.ay)
        # footprint (gom ca nhan nam ngoai hinh, vd ten actor)
        out.maxx = max(out.maxx, el.ax - el.sr[0] + el.w)
        out.maxy = max(out.maxy, el.ay - el.sr[1] + el.h)
        for suf, val, st, sx, sy, sw_, sh_ in el.sub:
            out.vertex(out.uid("%s__%s" % (el.id, suf)), val, st, sx, sy, sw_, sh_, el.id, el.ax + sx, el.ay + sy)
        for c in kids.get(k, []):
            emit_el(c, k)

    for k in kids.get(None, []):
        emit_el(k, None)

    for le in E_rel.values():
        if not le.abs:
            continue
        su, sv = E[le.u], E[le.v]
        pid = le.level
        ox, oy = (0.0, 0.0) if pid is None else (E[pid].ax, E[pid].ay)
        par = "1" if pid is None else E[pid].id
        pts = le.abs
        style = (EDGE_BASE.replace("rounded=0", "rounded=1") if tree else EDGE_BASE) + le.style + _constraint(pts[0], su, "exit") + _constraint(pts[-1], sv, "entry")
        way = [(x - ox, y - oy) for x, y in pts[1:-1]]
        gx, off = (None, None)
        if le.label and le.alab:
            gx, off = label_geometry(pts, le.alab)
        eid = out.uid(le.id)
        out.edge(eid, esc(le.label) if le.label else "", style, su.id, sv.id, way, par, gx, off)
        for which, lab, c in (("src", le.sl, le.asrc), ("dst", le.dl, le.adst)):
            if lab and c:
                g, o = label_geometry(pts, c)
                out.edge_label(out.uid("%s_%s" % (eid, which)), eid, esc(lab), g, o)
        for x, y in pts:
            out.maxx, out.maxy = max(out.maxx, x), max(out.maxy, y)
        if le.alab and le.lab:
            out.maxx = max(out.maxx, le.alab[0] + le.lab[0] / 2)
            out.maxy = max(out.maxy, le.alab[1] + le.lab[1] / 2)
    for x0, y0, x1, y1 in extra_bbox:
        out.maxx, out.maxy = max(out.maxx, x1), max(out.maxy, y1)
    return out


def _partitions(spec, E, parent, rels, warns):
    """Doc 'partitions' -> [(id, ten)] va gan el.lane cho phan tu cap goc.
    Phan tu cap goc khong khai bao 'partition' nhan lan cua hang xom (theo quan he), mac dinh lan dau."""
    parts = []
    for i, p in enumerate(spec.get("partitions") or []):
        if isinstance(p, dict):
            pid = str(p.get("id", p.get("name", "lane%d" % (i + 1))))
            parts.append((pid, str(p.get("name", pid))))
        else:
            parts.append((str(p), str(p)))
    if not parts:
        for el in E.values():
            if el.sp.get("partition") is not None:
                warns.append("Phan tu '%s' co 'partition' nhung spec khong khai bao 'partitions' -> bo qua." % el.id)
                break
        return []
    key = {}
    for i, (pid, nm) in enumerate(parts):
        key.setdefault(nm, i)
    for i, (pid, nm) in enumerate(parts):
        key[pid] = i
    for el in E.values():
        p = el.sp.get("partition")
        if p is None:
            continue
        if parent.get(el.id):
            warns.append("Phan tu '%s' nam trong container: 'partition' chi ap dung cho phan tu cap goc -> bo qua." % el.id)
        elif str(p) not in key:
            warns.append("Phan tu '%s': partition '%s' khong ton tai trong 'partitions'." % (el.id, p))
        else:
            el.lane = key[str(p)]

    def top(x):
        while parent.get(x):
            x = parent[x]
        return E[x]

    changed = True
    while changed:
        changed = False
        for r in rels:
            a, b = str(r.get("from")), str(r.get("to"))
            if a not in E or b not in E:
                continue
            ta, tb = top(a), top(b)
            for x, y in ((ta, tb), (tb, ta)):
                if x.lane is None and y.lane is not None:
                    x.lane = y.lane
                    changed = True
    for el in E.values():
        if el.lane is None and not parent.get(el.id):
            el.lane = 0
    return parts


def _widen(el, w):
    # ngan con cham mep phai (vd ngan thuoc tinh, cot ten cua bang ERD) gian theo
    el.sub = [(s, v, st, x, y, (w - x if abs(x + sw_ - el.sr[2]) < 0.5 else sw_), h)
              for (s, v, st, x, y, sw_, h) in el.sub]
    el.box(w, el.sr[3])


def comm_links(spec, warns):
    links = OrderedDict()
    for i, m in enumerate(spec.get("messages", [])):
        a, b = str(m.get("from")), str(m.get("to"))
        if a == b:
            key = (a, a)
        else:
            key = tuple(sorted((a, b)))
        if key not in links:
            links[key] = {"type": "link", "from": a, "to": b, "_messages": [], "id": "L%d" % (len(links) + 1)}
        mm = dict(m)
        mm.setdefault("seq", str(i + 1) if spec.get("autonumber", True) else "")
        links[key]["_messages"].append(mm)
    rels = []
    for l in links.values():
        # nhan tam: do rong du cho mui ten
        txt = "\n".join(_msg_text(m, "→") for m in l["_messages"])
        l["label"] = txt
        rels.append(l)
    return rels


def _msg_text(m, arrow):
    seq = str(m.get("seq", "")).strip()
    name = str(m.get("name", m.get("label", "")))
    body = ("%s: %s" % (seq, name)) if seq else name
    if arrow in ("←", "↑"):
        return "%s %s" % (arrow, body)
    return "%s %s" % (body, arrow)


def comm_label(le, E, direction):
    lines = []
    for m in le.rel["_messages"]:
        a, b = E[str(m["from"])], E[str(m["to"])]
        if a.id == b.id:
            arrow = "↻"
        elif direction == "LR":
            arrow = "→" if (b.ax + b.sr[2] / 2) > (a.ax + a.sr[2] / 2) else "←"
        else:
            arrow = "↓" if (b.ay + b.sr[3] / 2) > (a.ay + a.sr[3] / 2) else "↑"
        lines.append(_msg_text(m, arrow))
    return "\n".join(lines)


# =============================================================== sequence diagram
SEQ = dict(head_gap=30, min_gap=40, msg_gap=16, self_h=26, frag_head=34, op_sep=28, frag_tail=12)


def build_sequence(spec, warns, origin):
    parts = [dict(p) for p in spec.get("elements", [])]
    for p in parts:
        p.setdefault("id", p.get("name"))
        p["id"] = str(p["id"])
    P = OrderedDict((p["id"], p) for p in parts)
    msgs = [dict(m) for m in spec.get("messages", [])]
    auto = spec.get("autonumber", False)
    idmap = {}
    for i, m in enumerate(msgs):
        m["_i"] = i
        m["id"] = str(m.get("id", "m%d" % (i + 1)))
        idmap[m["id"]] = i
        m["from"], m["to"] = str(m["from"]), str(m["to"])
        for end in ("from", "to"):
            if m[end] not in P:
                warns.append("Message '%s': lifeline '%s' khong ton tai -> tu tao." % (m["id"], m[end]))
                P[m[end]] = {"id": m[end], "type": "object", "class": m[end]}
        seq = m.get("seq", str(i + 1) if auto else "")
        name = str(m.get("name", m.get("label", "")))
        m["_text"] = "\n".join(wrap(("%s: %s" % (seq, name)) if seq else name, 260))
        m["_lw"], m["_lh"] = text_size(m["_text"], 11)
        m["_self"] = m["from"] == m["to"]

    def midx(ref):
        if isinstance(ref, int):
            return ref - 1
        if str(ref) in idmap:
            return idmap[str(ref)]
        raise SystemExit("Fragment tham chieu message khong ton tai: %r" % ref)

    frags = []
    for f in spec.get("fragments", []):
        ops = f.get("operands") or [{"guard": f.get("guard"), "from": f["from"], "to": f["to"]}]
        oo = [(o.get("guard"), midx(o["from"]), midx(o["to"])) for o in ops]
        frags.append({"type": f.get("type", "alt"), "ops": oo, "a": min(o[1] for o in oo),
                      "b": max(o[2] for o in oo), "label": f.get("label")})
    def contains(f, g):  # g nam trong f (cung pham vi: fragment khai bao sau la ben trong)
        if f is g or not (f["a"] <= g["a"] and g["b"] <= f["b"]):
            return False
        return (f["a"], -f["b"]) != (g["a"], -g["b"]) or frags.index(g) > frags.index(f)

    def nest(f):  # so tang fragment long ben trong f
        kids = [g for g in frags if contains(f, g)]
        return 1 + max(nest(g) for g in kids) if kids else 0

    for f in frags:
        f["inner"] = nest(f)

    # --- header sizes
    heads = OrderedDict()
    for pid, p in P.items():
        k = str(p.get("type", "object")).lower()
        if k == "actor":
            lines = ([stereo(p["stereotype"])] if p.get("stereotype") else []) + wrap(p.get("name", pid), 130)
            lw, lh = text_size("\n".join(lines))
            heads[pid] = dict(kind="actor", value="<br>".join(esc(l) for l in lines), w=20, hh=40,
                              span=max(lw, 30), full=40 + lh + 4)
        else:
            head = _header_lines(dict(p, id=pid), "object" if k != "class" else "class")
            head = [(t, b if k == "class" else False, i) for t, b, i in head]
            w = max([100] + [text_size(t, 12, b)[0] + 24 for t, b, _ in head])
            hh = len(head) * 16 + 16
            heads[pid] = dict(kind="obj", value=_html_lines(head), w=w, hh=hh, span=w, full=hh)
    order = list(P.keys())
    pos = {pid: i for i, pid in enumerate(order)}
    n = len(order)

    # --- horizontal spacing
    gaps = [max(heads[order[i]]["span"] / 2 + heads[order[i + 1]]["span"] / 2 + 36, 120) for i in range(n - 1)]
    cons = []
    for m in msgs:
        i, j = pos[m["from"]], pos[m["to"]]
        if m["_self"]:
            if i < n - 1:
                cons.append((i, i + 1, 30 + 10 + m["_lw"] + 50))
        else:
            a, b = min(i, j), max(i, j)
            cons.append((a, b, m["_lw"] + 40))
    for _ in range(3):
        for a, b, need in sorted(cons, key=lambda c: c[1] - c[0]):
            have = sum(gaps[a:b])
            if have < need:
                d = (need - have) / (b - a)
                for k in range(a, b):
                    gaps[k] += d
    left_ext = max(heads[order[0]]["span"] / 2, 60) + 40
    X = {order[0]: origin[0] + left_ext}
    for i in range(1, n):
        X[order[i]] = X[order[i - 1]] + gaps[i - 1]

    # --- vertical rows
    top = origin[1]
    y = top + max(h["full"] for h in heads.values()) + SEQ["head_gap"]
    starts = defaultdict(list)
    ends = defaultdict(list)
    op_starts = defaultdict(list)
    for f in frags:
        starts[f["a"]].append(f)
        ends[f["b"]].append(f)
        for oi, (g, a, b) in enumerate(f["ops"]):
            if oi > 0:
                op_starts[a].append((f, oi, g))
    created = {}
    for m in msgs:
        i = m["_i"]
        for f in sorted(starts[i], key=lambda f: -(f["b"] - f["a"])):
            f["top"] = y
            y += SEQ["frag_head"]
        for f, oi, g in op_starts[i]:
            f.setdefault("seps", []).append((y + 6, g))
            y += SEQ["op_sep"]
        y += m["_lh"] + 2
        m["_y"] = y
        if m["_self"]:
            y += SEQ["self_h"]
        if str(m.get("type", "sync")).lower() == "create":
            created[m["to"]] = m["_y"]
        y += SEQ["msg_gap"]
        for f in sorted(ends[i], key=lambda f: (f["b"] - f["a"])):
            y += SEQ["frag_tail"]
            f["bottom"] = y
            y += 8
    bottom = y + 24

    out = Out()
    LL = {}
    for pid in order:
        h = heads[pid]
        x = X[pid]
        ly = top
        if pid in created:
            ly = created[pid] - h["hh"] / 2
        height = bottom - ly
        if h["kind"] == "actor":
            st = ("shape=umlLifeline;participant=umlActor;perimeter=lifelinePerimeter;whiteSpace=nowrap;html=1;"
                  "container=1;collapsible=0;recursiveResize=0;verticalAlign=top;spacingTop=36;outlineConnect=0;"
                  "portConstraint=eastwest;labelBackgroundColor=#ffffff;size=40;")
        else:
            st = ("shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;dropTarget=0;"
                  "collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;size=%d;" % h["hh"])
        out.ids.add(pid)
        out.vertex(pid, h["value"], st, x - h["w"] / 2, ly, h["w"], height)
        out.maxx = max(out.maxx, x + h["span"] / 2)
        LL[pid] = (x - h["w"] / 2, ly, h["w"], height)

    def ry(pid, yy):
        return (yy - LL[pid][1]) / LL[pid][3]

    for m in msgs:
        t = str(m.get("type", "sync")).lower()
        a, b, yy = m["from"], m["to"], m["_y"]
        if t == "sync" or t == "call":
            arrow = "endArrow=block;endFill=1;"
        elif t == "reply" or t == "return":
            arrow = "endArrow=open;endFill=0;dashed=1;"
        elif t == "create":
            arrow = "endArrow=open;endFill=0;dashed=1;"
        else:
            arrow = "endArrow=open;endFill=0;"
        base = "html=1;rounded=0;fontSize=11;endSize=10;labelBackgroundColor=none;" + arrow
        eid = out.uid(m["id"])
        if m["_self"]:
            x = X[a]
            st = base + "verticalAlign=middle;align=center;" + \
                "exitX=0.5;exitY=%s;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.5;entryY=%s;entryDx=0;entryDy=0;entryPerimeter=0;" % (
                    _n(ry(a, yy), 4), _n(ry(a, yy + SEQ["self_h"]), 4))
            out.edge(eid, esc(m["_text"]), st, a, a, [(x + 30, yy), (x + 30, yy + SEQ["self_h"])],
                     gx=0, offset=(m["_lw"] / 2 + 8, 0))
            out.maxx = max(out.maxx, x + 40 + m["_lw"])
            continue
        if t == "create":
            lx, ly_, lw_, lh_ = LL[b]
            ey = heads[b]["hh"] / 2 / lh_
            ex = 0 if X[b] > X[a] else 1
            entry = "entryX=%s;entryY=%s;entryDx=0;entryDy=0;entryPerimeter=0;" % (ex, _n(ey, 4))
            if not m["_text"]:
                m["_text"] = "«create»"
        else:
            entry = "entryX=0.5;entryY=%s;entryDx=0;entryDy=0;entryPerimeter=0;" % _n(ry(b, yy), 4)
        # dat nhan vao khoang trong rong nhat giua cac lifeline ma message cat qua (khong de len duong lifeline)
        xa, xb = X[a], X[b]
        lo, hi = min(xa, xb), max(xa, xb)
        stops = sorted({lo, hi} | {X[p] for p in order if lo < X[p] < hi})
        g0, g1 = max(zip(stops, stops[1:]), key=lambda s: s[1] - s[0])
        gx = 0.0
        if len(stops) > 2:
            if g1 - g0 >= m["_lw"] + 12:
                gx = 2 * ((g0 + g1) / 2 - xa) / (xb - xa) - 1
            else:
                base = base.replace("labelBackgroundColor=none;", "labelBackgroundColor=#ffffff;")
        st = base + "verticalAlign=bottom;" + \
            "exitX=0.5;exitY=%s;exitDx=0;exitDy=0;exitPerimeter=0;" % _n(ry(a, yy), 4) + entry
        out.edge(eid, esc(m["_text"]), st, a, b, [], gx=gx if gx else None)

    # fragments
    for f in sorted(frags, key=lambda f: -(f["b"] - f["a"])):
        inside = msgs[f["a"]: f["b"] + 1]
        xs, right = [], []
        for m in inside:
            xs += [X[m["from"]], X[m["to"]]]
            if m["_self"]:
                right.append(X[m["from"]] + 40 + m["_lw"])
        margin = 18 + 12 * f["inner"]
        x0 = min(xs) - margin
        x1 = max(xs + right) + margin
        label = f.get("label") or f["type"]
        tw = max(50, text_size(label, 12, True)[0] + 20)
        g0 = f["ops"][0][0]
        need = tw + (text_size("[" + g0.strip("[]") + "]")[0] + 16 if g0 else 0) + 10
        for sy, g in f.get("seps", []):
            if g:
                need = max(need, text_size("[" + g.strip("[]") + "]")[0] + 20)
        if x1 - x0 < need:
            x1 = x0 + need
        fy0, fy1 = f["top"] + 4, f["bottom"]
        fid = out.uid("frag_" + f["type"])
        out.vertex(fid, "<b>%s</b>" % esc(label),
                   "shape=umlFrame;whiteSpace=wrap;html=1;pointerEvents=0;fillColor=none;width=%d;height=22;" % tw,
                   x0, fy0, x1 - x0, fy1 - fy0)
        if g0:
            gt = "[" + g0.strip("[]") + "]"
            gw, gh = text_size(gt, 11)
            out.vertex(out.uid(fid + "_g0"), esc(gt),
                       "text;html=1;align=left;verticalAlign=middle;fontSize=11;spacingLeft=2;",
                       x0 + tw + 6, fy0 + 2, gw + 6, 18)
        for k, (sy, g) in enumerate(f.get("seps", [])):
            out.edge(out.uid(fid + "_sep%d" % (k + 1)), "", "endArrow=none;dashed=1;html=1;rounded=0;dashPattern=8 4;",
                     None, None, [], spoint=(x0, sy), tpoint=(x1, sy))
            if g:
                gt = "[" + g.strip("[]") + "]"
                gw, gh = text_size(gt, 11)
                out.vertex(out.uid(fid + "_g%d" % (k + 1)), esc(gt),
                           "text;html=1;align=left;verticalAlign=middle;fontSize=11;spacingLeft=2;",
                           x0 + 6, sy + 3, gw + 6, 18)
        out.maxx = max(out.maxx, x1)
    out.maxy = max(out.maxy, bottom)
    return out


# =============================================================== business context (so do nghiep vu)
BIZ_CENTER = {"system", "process", "business", "center", "centre", "organization"}


def _seg_hits(p, q, r, shrink=2.0):
    """Doan pq di vao phan trong hinh chu nhat r=(x0,y0,x1,y1) (Liang-Barsky) - giong validator."""
    x0, y0, x1, y1 = r[0] + shrink, r[1] + shrink, r[2] - shrink, r[3] - shrink
    if x0 >= x1 or y0 >= y1:
        return False
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pp) < 1e-9:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return t1 - t0 > 1e-6


def _rects_hit(a, b, pad=0.0):
    return a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad


def build_bizcontext(spec, warns, origin):
    """Context diagram nghiep vu: he thong/doanh nghiep la hinh tron o giua, thuc the ngoai xep deu tren mot
    vong tron bao quanh; moi thuc the co toi da 2 mui ten thang (vao he thong / ra khoi he thong), nhieu luong
    du lieu cung chieu gop thanh 1 mui ten nhieu dong nhan. Nhan dat ben ngoai cap mui ten -> khong cat duong
    khac; ban kinh vong tu tang cho toi khi khong con chong hinh / nhan / duong."""
    sps = [dict(s) for s in spec.get("elements", [])]
    for s in sps:
        s.setdefault("id", s.get("name"))
        s["id"] = str(s["id"])
    if not sps:
        return Out()
    cen = next((s for s in sps if str(s.get("type", "")).lower() in BIZ_CENTER), None)
    if cen is None:
        cen = sps[0]
        warns.append("Khong co phan tu type 'system' lam trung tam -> dung '%s'." % cen["id"])
    exts = [s for s in sps if s is not cen]

    # ---- hinh
    def lines_of(s, maxw):
        st = [stereo(s["stereotype"])] if s.get("stereotype") else []
        return st, wrap(str(s.get("name", s["id"])), maxw)

    st_c, nm_c = lines_of(cen, 150)
    tw, th = text_size("\n".join(st_c + nm_c), 12, True)
    D = max(150.0, math.ceil(math.hypot(tw + 20, th + 20)))
    R0 = D / 2
    shapes = {}
    for s in exts:
        st, nm = lines_of(s, 160)
        w, h = text_size("\n".join(st + nm), 12, True)
        shapes[s["id"]] = (max(120.0, w + 28), max(54.0, h + 24), st, nm)

    # ---- luong: gom theo (thuc the ngoai, chieu)
    flows = OrderedDict()   # ext id -> {"in": [(rid, text)], "out": [...]}
    ids = {s["id"] for s in sps}
    for i, r in enumerate(spec.get("relations", spec.get("flows", [])) or []):
        u, v = str(r.get("from")), str(r.get("to"))
        text = r.get("label", r.get("name", r.get("data")))
        rid = str(r.get("id") or "f%d" % (i + 1))
        if u not in ids or v not in ids:
            warns.append("Luong #%d: phan tu '%s' hoac '%s' khong ton tai -> bo qua." % (i + 1, u, v))
            continue
        if cen["id"] not in (u, v) or u == v:
            warns.append("Luong #%d %s -> %s khong di qua he thong trung tam (context diagram chi ve luong giua "
                         "he thong va ben ngoai) -> bo qua." % (i + 1, u, v))
            continue
        ext, d = (u, "in") if v == cen["id"] else (v, "out")
        flows.setdefault(ext, {"in": [], "out": []})[d].append((rid, str(text or "")))
    for s in exts:
        if s["id"] not in flows:
            warns.append("Thuc the ngoai '%s' khong co luong du lieu nao." % s.get("name", s["id"]))

    arrows = []   # (ext, dir, rid, label_lines, offset_sign)
    for s in exts:
        f = flows.get(s["id"])
        if not f:
            continue
        dirs = [d for d in ("in", "out") if f[d]]
        for d in dirs:
            lab = [l for _, t in f[d] for l in wrap(t, 170) if t]
            sign = 0 if len(dirs) == 1 else (-1 if d == "in" else 1)
            arrows.append((s["id"], d, f[d][0][0], lab, sign))

    N = max(1, len(exts))
    GAP = 28.0   # khoang cach 2 mui ten song song cua cung thuc the
    ang = {s["id"]: -math.pi / 2 + 2 * math.pi * k / N for k, s in enumerate(exts)}
    maxdiag = max([math.hypot(w, h) for w, h, _, _ in shapes.values()] or [0])
    labsz = {}
    for a in arrows:
        labsz[a[2]] = text_size("\n".join(a[3]), 11) if a[3] else (0, 0)
    maxlab = max([max(w, h) for w, h in labsz.values()] or [0])
    R = R0 + maxdiag / 2 + max(90.0, maxlab * 0.6 + 40)
    if N > 1:
        R = max(R, (maxdiag + 40) / (2 * math.sin(math.pi / N)))

    def layout(R):
        rects = {cen["id"]: (-R0, -R0, R0, R0)}
        ctr = {}
        for s in exts:
            w, h, _, _ = shapes[s["id"]]
            cx, cy = R * math.cos(ang[s["id"]]), R * math.sin(ang[s["id"]])
            ctr[s["id"]] = (cx, cy)
            rects[s["id"]] = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        lines = {}
        for ext, d, rid, lab, sign in arrows:
            th_ = ang[ext]
            ux, uy = math.cos(th_), math.sin(th_)
            nx, ny = -uy, ux
            off = sign * GAP / 2
            pc = (off * nx + math.sqrt(max(0.0, R0 * R0 - off * off)) * ux,
                  off * ny + math.sqrt(max(0.0, R0 * R0 - off * off)) * uy)
            # diem ra khoi hinh chu nhat cua thuc the ngoai, di nguoc tia ve tam
            ex, ey = ctr[ext]
            px, py = ex + off * nx, ey + off * ny
            x0, y0, x1, y1 = rects[ext]
            ts = []
            for bound, p0, v in ((x0, px, -ux), (x1, px, -ux), (y0, py, -uy), (y1, py, -uy)):
                if abs(v) > 1e-9:
                    t = (bound - p0) / v
                    if t > 0:
                        ts.append(t)
            t = min(ts) if ts else 0
            pe = (px - ux * t, py - uy * t)
            lines[rid] = (pc, pe, (ux, uy), (nx, ny), sign)
        return rects, ctr, lines

    for _ in range(80):
        rects, ctr, lines = layout(R)
        segs = {rid: (pc, pe) for rid, (pc, pe, _, _, _) in lines.items()}
        ok = True
        # hinh / hinh
        keys = list(rects)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                if _rects_hit(rects[keys[i]], rects[keys[j]], 30):
                    ok = False
        # duong / hinh (tru 2 dau cua chinh no)
        own = {a[2]: a[0] for a in arrows}
        for rid, (p, q) in segs.items():
            for k_, r in rects.items():
                if k_ in (cen["id"], own[rid]):
                    continue
                if _seg_hits(p, q, r, 1.5):
                    ok = False
        # nhan: thu vai vi tri doc duong, ben ngoai cap mui ten
        labs = {}
        if ok:
            for ext, d, rid, lab, sign in arrows:
                if not lab:
                    continue
                lw, lh = labsz[rid]
                pc, pe, (ux, uy), (nx, ny), sg = lines[rid]
                side = sg or 1
                half = (lw * abs(nx) + lh * abs(ny)) / 2
                placed = None
                for frac in (0.5, 0.42, 0.58, 0.34, 0.66):
                    mx, my = pc[0] + (pe[0] - pc[0]) * frac, pc[1] + (pe[1] - pc[1]) * frac
                    cx, cy = mx + side * nx * (half + 5), my + side * ny * (half + 5)
                    r = (cx - lw / 2, cy - lh / 2, cx + lw / 2, cy + lh / 2)
                    bad = any(_rects_hit(r, rr, 4) for rr in rects.values())
                    bad = bad or any(_rects_hit(r, rr, 4) for rr in labs.values())
                    bad = bad or any(_seg_hits(p, q, r, 0.0) for k_, (p, q) in segs.items() if k_ != rid)
                    if not bad:
                        placed = r
                        break
                if placed is None:
                    ok = False
                    break
                labs[rid] = placed
        if ok:
            break
        R += 30
    else:
        warns.append("Khong tim duoc ban kinh khong chong nhan - kiem tra lai (qua nhieu thuc the/nhan dai).")

    # ---- dich toa do ve origin
    allr = list(rects.values()) + list(labs.values())
    minx = min(r[0] for r in allr)
    miny = min(r[1] for r in allr)
    dx, dy = origin[0] - minx, origin[1] - miny
    T = lambda p: (p[0] + dx, p[1] + dy)

    out = Out()
    out.ids |= {s["id"] for s in sps}
    cid = cen["id"]
    val = "<br>".join([esc(x) for x in st_c] + ["<b>%s</b>" % esc(x) for x in nm_c])
    out.vertex(cid, val, "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#dae8fc;strokeWidth=2;",
               -R0 + dx, -R0 + dy, D, D)
    for s in exts:
        w, h, st, nm = shapes[s["id"]]
        x0, y0, _, _ = rects[s["id"]]
        val = "<br>".join([esc(x) for x in st] + ["<b>%s</b>" % esc(x) for x in nm])
        out.vertex(s["id"], val, "rounded=0;whiteSpace=wrap;html=1;fillColor=#f5f5f5;", x0 + dx, y0 + dy, w, h)

    def frac_of(p, r):
        x0, y0, x1, y1 = r
        return (min(1, max(0, (p[0] - x0) / (x1 - x0))), min(1, max(0, (p[1] - y0) / (y1 - y0))))

    for ext, d, rid, lab, sign in arrows:
        pc, pe, _, _, _ = lines[rid]
        fc, fe = frac_of(pc, rects[cid]), frac_of(pe, rects[ext])
        if d == "in":
            src, tgt, fs, ft, pts = ext, cid, fe, fc, [T(pe), T(pc)]
        else:
            src, tgt, fs, ft, pts = cid, ext, fc, fe, [T(pc), T(pe)]
        style = (EDGE_BASE + "endArrow=block;endFill=1;"
                 "exitX=%s;exitY=%s;exitDx=0;exitDy=0;exitPerimeter=0;"
                 "entryX=%s;entryY=%s;entryDx=0;entryDy=0;entryPerimeter=0;"
                 % (_n(fs[0], 4), _n(fs[1], 4), _n(ft[0], 4), _n(ft[1], 4)))
        gx = off = None
        if lab and rid in labs:
            r = labs[rid]
            gx, off = label_geometry(pts, T(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)))
        out.edge(out.uid(rid), esc("\n".join(lab)) if lab else "", style, src, tgt, [], "1", gx, off)
    for r in allr:
        out.maxx, out.maxy = max(out.maxx, r[2] + dx), max(out.maxy, r[3] + dy)
    return out


# =============================================================== document assembly
def build_page(spec, warns):
    diagram = str(spec.get("diagram", "class")).lower()
    spec["diagram"] = diagram
    use_frame = spec.get("frame", not (sitemap_mode(spec) or chen_mode(spec)))
    title = spec.get("title") or spec.get("useCase") or spec.get("name") or diagram
    kind = FRAME_KIND.get(diagram, "")
    flabel = "%s %s" % (kind, title) if kind else title
    fw, fh = text_size(flabel, 12, True)
    origin = (40 + (24 if use_frame else 0), 40 + (44 if use_frame else 0))
    if diagram == "sequence":
        out = build_sequence(spec, warns, origin)
    elif diagram == "bizcontext":
        out = build_bizcontext(spec, warns, origin)
    else:
        out = build_graph(chen_expand(spec, warns) if chen_mode(spec) else spec, warns, origin)
    if use_frame:
        x0, y0 = 40, 40
        x1 = max(out.maxx + 24, x0 + fw + 60)
        y1 = out.maxy + 24
        fr = ET.Element("mxCell", id=out.uid("diagram_frame"), value="<b>%s</b>" % esc(flabel),
                        style="shape=umlFrame;whiteSpace=wrap;html=1;pointerEvents=0;fillColor=none;"
                              "width=%d;height=26;" % (fw + 24), vertex="1", parent="1")
        ET.SubElement(fr, "mxGeometry", x=_n(x0), y=_n(y0), width=_n(x1 - x0), height=_n(y1 - y0),
                      **{"as": "geometry"})
        out.root.insert(2, fr)  # nam duoi cung (ve truoc)
        out.maxx, out.maxy = x1, y1
    model = ET.Element("mxGraphModel", dx="1200", dy="800", grid="1", gridSize="10", guides="1", tooltips="1",
                       connect="1", arrows="1", fold="1", page="1", pageScale="1",
                       pageWidth=_n(max(850, out.maxx + 40), 0), pageHeight=_n(max(1100, out.maxy + 40), 0),
                       math="0", shadow="0")
    model.append(out.root)
    return title, model


def generate(specs):
    mxfile = ET.Element("mxfile", host="uml2drawio", agent="comet-uml-drawio", version="24.7.0")
    warns_all = []
    models = []
    pages = []
    for spec in specs:
        warns = []
        title, model = build_page(spec, warns)
        pages.append((str(title), spec, model))
        models.append(model)
        warns_all += ["[%s] %s" % (title, w) for w in warns]
    # ten trang phai phan biet duoc (vd communication + sequence cung use case): trung -> them loai so do
    cnt = defaultdict(int)
    for title, _, _ in pages:
        cnt[title] += 1
    used = set()
    for i, (title, spec, model) in enumerate(pages):
        pname = (title if cnt[title] == 1 else "%s (%s)" % (title, spec.get("diagram")))[:80]
        base, k = pname, 2
        while pname in used:
            pname, k = "%s %d" % (base, k), k + 1
        used.add(pname)
        d = ET.SubElement(mxfile, "diagram", id="page-%d" % (i + 1), name=pname)
        d.append(model)
    return mxfile, models, warns_all


def expand(paths):
    """Tu mo rong *.json - PowerShell/cmd khong mo rong glob cho chuong trinh ngoai."""
    out = []
    for p in paths:
        out += (sorted(glob.glob(p)) if any(c in p for c in "*?[") else []) or [p]
    return out


def load_specs(paths):
    specs = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "diagrams" in data:
            specs += data["diagrams"]
        elif isinstance(data, list):
            specs += data
        else:
            specs.append(data)
    return specs


def main():
    ap = argparse.ArgumentParser(description="UML/COMET spec JSON -> draw.io (bo cuc khong chong hinh)")
    ap.add_argument("specs", nargs="+", help="file spec JSON (1 so do / list / {'diagrams':[...]})")
    ap.add_argument("-o", "--out", help="file .drawio dau ra")
    ap.add_argument("--xml-only", action="store_true", help="in <mxGraphModel> cua trang dau ra stdout")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args()
    a.specs = expand(a.specs)
    specs = load_specs(a.specs)
    mxfile, models, warns = generate(specs)
    for w in warns:
        print("WARN:", w, file=sys.stderr)
    if a.xml_only:
        sys.stdout.write(ET.tostring(models[0], encoding="unicode"))
        sys.stdout.write("\n")
    out = a.out
    if not out and not a.xml_only:
        out = os.path.splitext(a.specs[0])[0] + ".drawio"
    if out:
        ET.ElementTree(mxfile).write(out, encoding="utf-8", xml_declaration=False)
        print("Da ghi:", out, file=sys.stderr)
        if not a.no_validate:
            from validate_drawio import validate_file, print_report
            rep = validate_file(out)
            ok = print_report(rep, stream=sys.stderr)
            if not ok:
                sys.exit(2)


if __name__ == "__main__":
    main()
