#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_drawio.py - Kiem tra file .drawio / mxGraphModel XML:
  * cau truc: id trung, parent/source/target khong ton tai
  * hinh hoc: hinh chong len nhau (ERROR), hinh nam trong hinh khong phai container (WARN),
    hinh qua sat nhau < 8px (WARN), canh di xuyen qua hinh (ERROR),
    hai canh chong len nhau tren cung mot doan thang (ERROR), nhan de len hinh/nhan khac (WARN)
  * UML lint: dung << >> thay vi « » (WARN), «include»/«extend» khong net dut + mui ten mo (ERROR),
    message trong sequence khong nam ngang (ERROR), stereotype khong thuoc UML/COMET (INFO),
    actor khong co lien ket (WARN)

Cach dung:
  python validate_drawio.py file.drawio [--json]
Ma thoat: 0 = khong co ERROR, 1 = co ERROR.
"""
from __future__ import annotations

import base64
import html
import json
import math
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

MIN_GAP = 8.0
EPS = 0.5

KNOWN_STEREOTYPES = {
    # COMET - doi tuong / lop
    "entity", "boundary", "control", "user interaction", "proxy", "input", "output", "i/o", "io",
    "input/output", "device i/o", "network interaction", "coordinator", "state dependent control",
    "state-dependent control", "timer", "application logic", "business logic", "algorithm", "service",
    "database wrapper", "data abstraction", "external system proxy", "gui",
    # COMET - context
    "software system", "system", "external input device", "external output device",
    "external input/output device", "external i/o device", "external user", "external system",
    "external timer", "external device",
    # COMET - actor
    "human actor", "primary actor", "secondary actor", "input device actor", "output device actor",
    "i/o device actor", "timer actor", "system actor",
    # COMET - design / subsystem / component / task
    "subsystem", "control subsystem", "coordinator subsystem", "service subsystem",
    "data collection subsystem", "data analysis subsystem", "client subsystem", "server subsystem",
    "user interaction subsystem", "input/output subsystem", "system services subsystem",
    "client", "server", "client service", "component", "composite component", "port",
    "event driven input", "event driven output", "periodic input", "demand driven", "demand",
    "event driven", "periodic", "event driven i/o", "demand driven i/o", "periodic i/o",
    "control clustering", "sequential clustering", "temporal clustering", "resource monitor",
    "passive i/o", "task", "active", "passive",
    "demand driven task", "event driven task", "periodic task", "user interaction task",
    "interface", "provided", "required",
    # UML chuan
    "include", "extend", "create", "destroy", "use", "uses", "call", "send", "instantiate",
    "realize", "trace", "refine", "derive", "import", "access", "merge", "enumeration", "datatype",
    "primitive", "abstract", "utility", "metaclass", "node", "device", "execution environment",
    "executionenvironment", "artifact", "deploy", "manifest", "executable", "file", "library",
    "document", "script", "source", "database", "signal", "exception", "actor", "model",
    "framework", "system boundary", "focus", "auxiliary", "type", "implementation class",
    "specification", "realization", "process", "thread", "table", "layer", "network",
    "communication path", "tcp/ip", "http", "https", "lan", "wan", "ethernet", "rs-232", "usb",
    "external", "asynchronous", "synchronous", "stereotype",
}


# ============================================================ helpers
def _cw(ch):
    if ch == " ":
        return 0.30
    if ch in "iljI.,:;|!'`":
        return 0.30
    if ch in "frt()[]{}-/\\\"*":
        return 0.40
    if ch in "mwMW@%":
        return 0.92
    if ord(ch) >= 0x2E80:
        return 1.0
    if ch.isupper() or ch in "«»→←↑↓":
        return 0.72
    return 0.58


def plain(value):
    v = (value or "").replace("<<", "\x01").replace(">>", "\x02")
    v = re.sub(r"<br\s*/?>", "\n", v, flags=re.I)
    v = re.sub(r"</(div|p)>", "\n", v, flags=re.I)
    v = re.sub(r"</?[a-zA-Z][^<>]*>", "", v)
    v = v.replace("\x01", "<<").replace("\x02", ">>")
    return html.unescape(v).strip("\n")


def text_box(value, size=11):
    t = plain(value)
    if not t.strip():
        return 0.0, 0.0
    lines = t.split("\n")
    w = max(sum(_cw(c) for c in l) for l in lines) * size + 4
    return w, len(lines) * size * 1.3


def parse_style(s):
    d = {}
    for part in (s or "").split(";"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
        else:
            d[part.strip()] = "1"
            d.setdefault("_base", part.strip())
    return d


def decode_diagram(d):
    m = d.find("mxGraphModel")
    if m is not None:
        return m
    txt = (d.text or "").strip()
    if not txt:
        return None
    try:
        raw = zlib.decompress(base64.b64decode(txt), -15).decode("utf-8")
        raw = urllib.parse.unquote(raw)
        return ET.fromstring(raw)
    except Exception:
        return ET.fromstring(txt)


def load_pages(path_or_xml):
    if path_or_xml.lstrip().startswith("<"):
        root = ET.fromstring(path_or_xml)
    else:
        root = ET.parse(path_or_xml).getroot()
    if root.tag == "mxGraphModel":
        return [("Page-1", root)]
    if root.tag == "mxfile":
        return [(d.get("name") or d.get("id") or "page", decode_diagram(d)) for d in root.findall("diagram")]
    if root.tag == "diagram":
        return [(root.get("name") or "page", decode_diagram(root))]
    raise ValueError("Khong nhan dien duoc dinh dang (can mxfile / diagram / mxGraphModel)")


def seg_hits_rect(p, q, r, shrink=1.0):
    """Doan thang pq co di vao phan TRONG cua hinh chu nhat r=(x0,y0,x1,y1) khong (Liang-Barsky)."""
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


def rect_overlap(a, b, tol=EPS):
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def rect_contains(a, b, tol=EPS):
    return a[0] <= b[0] + tol and a[1] <= b[1] + tol and a[2] >= b[2] - tol and a[3] >= b[3] - tol


def rect_gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return math.hypot(dx, dy) if dx and dy else max(dx, dy)


def clip_to_rect(center, toward, r):
    """Diem ra khoi hinh chu nhat r tren tia center->toward."""
    cx, cy = center
    dx, dy = toward[0] - cx, toward[1] - cy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return center
    ts = []
    if dx:
        ts += [(r[0] - cx) / dx, (r[2] - cx) / dx]
    if dy:
        ts += [(r[1] - cy) / dy, (r[3] - cy) / dy]
    t = min([t for t in ts if t > 0] or [0])
    return (cx + dx * t, cy + dy * t)


def point_along(pts, rel_x):
    L = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    tot = sum(L)
    if not tot:
        return pts[0], (1, 0)
    target = (rel_x + 1) / 2 * tot
    for (a, b), l in zip(zip(pts, pts[1:]), L):
        if target <= l + 1e-9 and l > 0:
            t = target / l
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / l, (b[1] - a[1]) / l)
        target -= l
    a, b = pts[-2], pts[-1]
    l = math.dist(a, b) or 1
    return pts[-1], ((b[0] - a[0]) / l, (b[1] - a[1]) / l)


# ============================================================ model
class Cell:
    def __init__(self, c):
        self.id = c.get("id")
        self.parent = c.get("parent")
        self.value = c.get("value", "")
        self.style_s = c.get("style", "")
        self.st = parse_style(self.style_s)
        self.vertex = c.get("vertex") == "1"
        self.edge = c.get("edge") == "1"
        self.source = c.get("source")
        self.target = c.get("target")
        g = c.find("mxGeometry")
        self.geo = g
        self.x = self.y = self.w = self.h = 0.0
        self.relative = False
        if g is not None:
            self.x = float(g.get("x", 0) or 0)
            self.y = float(g.get("y", 0) or 0)
            self.w = float(g.get("width", 0) or 0)
            self.h = float(g.get("height", 0) or 0)
            self.relative = g.get("relative") == "1"
        self.abs = None

    @property
    def rect(self):
        return (self.ax, self.ay, self.ax + self.w, self.ay + self.h)

    def has(self, k):
        return k in self.st

    @property
    def shape(self):
        return self.st.get("shape", self.st.get("_base", ""))


def is_decor(c):
    b = c.st.get("_base", "")
    return b in ("text", "line", "edgeLabel") or c.shape == "module" or c.has("edgeLabel")


def is_frame(c):
    return (c.shape == "umlFrame" or c.st.get("fillColor") == "none" or c.st.get("_base") == "group"
            or getattr(c, "is_lane", False))


def mark_lanes(verts):
    """Swimlane/partition: cac hinh 'swimlane' cung cha, ghep sat canh nhau thanh mot dai (pool).
    Lan duoc coi nhu khung: sat nhau la dung, canh duoc phep cat ngang qua lan."""
    sl = [c for c in verts if (c.st.get("_base") == "swimlane" or c.shape == "swimlane")
          and "childLayout" not in c.st]
    for i, a in enumerate(sl):
        for b in sl[i + 1:]:
            if a.parent != b.parent:
                continue
            ra, rb = a.rect, b.rect
            row = (abs(ra[1] - rb[1]) < 1 and abs(ra[3] - rb[3]) < 1
                   and (abs(ra[2] - rb[0]) < 1 or abs(rb[2] - ra[0]) < 1))
            col = (abs(ra[0] - rb[0]) < 1 and abs(ra[2] - rb[2]) < 1
                   and (abs(ra[3] - rb[1]) < 1 or abs(rb[3] - ra[1]) < 1))
            if row or col:
                a.is_lane = b.is_lane = True


def is_container(c):
    return (c.st.get("container") == "1" or c.st.get("_base") == "swimlane" or c.shape == "swimlane"
            or is_frame(c))


def shape_rect(c):
    """Vung 'dac' cua hinh. Lifeline chi tinh phan dau (duong doc net dut duoc phep cat)."""
    if c.shape == "umlLifeline":
        size = float(c.st.get("size", 40))
        return (c.ax, c.ay, c.ax + c.w, c.ay + size)
    return c.rect


class Geometry:
    """Toa do tuyet doi cua moi hinh, polyline cua moi canh, khung cua moi nhan."""

    def __init__(self, model):
        self.struct_errors = E = []
        root = model.find("root")
        cells = {}
        for c in root.findall("mxCell"):
            cell = Cell(c)
            if cell.id is None:
                continue
            if cell.id in cells:
                E.append("Trung id '%s'." % cell.id)
            cells[cell.id] = cell
        for o in root.findall("object") + root.findall("UserObject"):
            c = o.find("mxCell")
            if c is not None and o.get("id"):
                cell = Cell(c)
                cell.id = o.get("id")
                cell.value = o.get("label", "")
                if cell.id in cells:
                    E.append("Trung id '%s'." % cell.id)
                cells[cell.id] = cell
        self.cells = cells

        for c in cells.values():
            if c.parent and c.parent not in cells:
                E.append("Cell '%s' co parent '%s' khong ton tai." % (c.id, c.parent))
            if c.edge:
                for end in (c.source, c.target):
                    if end and end not in cells:
                        E.append("Canh '%s' tham chieu '%s' khong ton tai." % (c.id, end))

        # toa do tuyet doi: geometry cua con tinh tu goc cua cha
        for c in cells.values():
            if c.vertex and not c.relative:
                ax = ay = 0.0
                q, guard = c, 0
                while q is not None and q.vertex and not q.relative and guard < 60:
                    ax += q.x
                    ay += q.y
                    q = cells.get(q.parent)
                    guard += 1
                c.ax, c.ay = ax, ay

        def ancestors(c):
            out = []
            q = cells.get(c.parent)
            while q is not None and q.vertex and len(out) < 60:
                out.append(q.id)
                q = cells.get(q.parent)
            return out

        self.verts = [c for c in cells.values() if c.vertex and not c.relative and hasattr(c, "ax")]
        mark_lanes(self.verts)
        self.prim = [c for c in self.verts if not is_decor(c)]
        self.anc = {c.id: set(ancestors(c)) for c in self.verts}
        self.is_seq = any(c.shape == "umlLifeline" for c in self.verts)

        # ---- canh
        def center(vid):
            v = cells.get(vid)
            if v is None or not hasattr(v, "ax"):
                return None
            r = shape_rect(v)
            return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)

        def endpoint(c, which, toward):
            vid = c.source if which == "source" else c.target
            pre = "exit" if which == "source" else "entry"
            v = cells.get(vid)
            if v is None or not hasattr(v, "ax"):
                if c.geo is not None:
                    for p in c.geo.findall("mxPoint"):
                        if p.get("as") == ("sourcePoint" if which == "source" else "targetPoint"):
                            return (float(p.get("x", 0)), float(p.get("y", 0)))
                return None
            if pre + "X" in c.st and pre + "Y" in c.st:
                fx, fy = float(c.st[pre + "X"]), float(c.st[pre + "Y"])
                dx, dy = float(c.st.get(pre + "Dx", 0)), float(c.st.get(pre + "Dy", 0))
                return (v.ax + fx * v.w + dx, v.ay + fy * v.h + dy)
            r = shape_rect(v)
            ctr = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
            return clip_to_rect(ctr, toward, r) if toward else ctr

        self.edges = {}
        for c in cells.values():
            if not c.edge:
                continue
            p = cells.get(c.parent)
            ox, oy = (p.ax, p.ay) if (p is not None and p.vertex and hasattr(p, "ax")) else (0.0, 0.0)
            way = []
            if c.geo is not None:
                arr = c.geo.find("Array")
                if arr is not None:
                    way = [(float(q.get("x", 0)) + ox, float(q.get("y", 0)) + oy) for q in arr.findall("mxPoint")]
            s = endpoint(c, "source", way[0] if way else center(c.target))
            t = endpoint(c, "target", way[-1] if way else (s if s else center(c.source)))
            if s is None or t is None:
                continue
            if not way and c.source and "exitX" not in c.st:
                s = endpoint(c, "source", t)
            self.edges[c.id] = (c, [s] + way + [t])

        # ---- nhan: (rect, owner_id, mo_ta, text, style)
        self.labels = []
        for eid, (c, pts) in self.edges.items():
            if plain(c.value).strip():
                w, h = text_box(c.value, float(c.st.get("fontSize", 11)))
                gx = float(c.geo.get("x", 0) or 0) if c.geo is not None else 0.0
                off = _offset(c.geo)
                (px, py), _ = point_along(pts, gx)
                cx, cy = px + off[0], py + off[1]
                va = c.st.get("verticalAlign", "middle")
                if va == "bottom":
                    cy -= h / 2
                elif va == "top":
                    cy += h / 2
                self.labels.append(((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), eid,
                                    "nhan canh '%s'" % plain(c.value)[:40], c))
        for c in cells.values():
            if c.vertex and c.relative and c.parent in self.edges and plain(c.value).strip():
                ec, pts = self.edges[c.parent]
                w, h = text_box(c.value, float(c.st.get("fontSize", 11)))
                off = _offset(c.geo)
                (px, py), _ = point_along(pts, c.x)
                cx, cy = px + off[0], py + off[1]
                self.labels.append(((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), c.parent,
                                    "nhan '%s' cua canh %s" % (plain(c.value)[:30], edge_desc(ec, cells)), c))
        for v in self.verts:
            if v.st.get("labelPosition") == "right" and plain(v.value).strip():
                w, h = text_box(v.value, 12)
                self.labels.append(((v.ax + v.w + 2, v.ay + v.h / 2 - h / 2, v.ax + v.w + 6 + w, v.ay + v.h / 2 + h / 2),
                                    v.id, "ten '%s'" % plain(v.value)[:30], v))
            elif v.st.get("verticalLabelPosition") == "bottom" and v.shape != "umlLifeline" and plain(v.value).strip():
                w, h = text_box(v.value, 12)
                cx = v.ax + v.w / 2
                self.labels.append(((cx - w / 2, v.ay + v.h + 1, cx + w / 2, v.ay + v.h + 3 + h), v.id,
                                    "ten '%s'" % plain(v.value)[:30], v))


def _offset(geo):
    if geo is not None:
        for p in geo.findall("mxPoint"):
            if p.get("as") == "offset":
                return (float(p.get("x", 0)), float(p.get("y", 0)))
    return (0.0, 0.0)


def analyze_page(name, model):
    G = Geometry(model)
    E, W, I = list(G.struct_errors), [], []
    cells, prim, anc, edges = G.cells, G.prim, G.anc, G.edges

    # ------------------------------------------------ hinh / hinh
    for i in range(len(prim)):
        a = prim[i]
        ra = shape_rect(a)
        for j in range(i + 1, len(prim)):
            b = prim[j]
            rb = shape_rect(b)
            if b.id in anc[a.id] or a.id in anc[b.id]:
                continue
            if (a.shape == "umlLifeline" and is_frame(b)) or (b.shape == "umlLifeline" and is_frame(a)):
                continue
            if rect_overlap(ra, rb):
                if rect_contains(ra, rb) or rect_contains(rb, ra):
                    outer, inner = (a, b) if rect_contains(ra, rb) else (b, a)
                    if not is_container(outer):
                        W.append("'%s' nam tron trong '%s' nhung khong phai phan tu con (nen dung parent/container)."
                                 % (lbl(inner), lbl(outer)))
                else:
                    E.append("Hinh '%s' chong len hinh '%s'." % (lbl(a), lbl(b)))
            elif not is_frame(a) and not is_frame(b) and rect_gap(ra, rb) < MIN_GAP - EPS:
                W.append("Hinh '%s' va '%s' qua sat nhau (%.0fpx < %dpx)."
                         % (lbl(a), lbl(b), rect_gap(ra, rb), MIN_GAP))

    # ------------------------------------------------ canh xuyen hinh / message nghieng
    for eid, (c, pts) in edges.items():
        skip = set()
        for x in (c.source, c.target):
            if x in cells:
                skip |= anc.get(x, set())
                skip.add(x)
        for v in prim:
            if v.id in skip or is_frame(v):
                continue
            r = shape_rect(v)
            for p, q in zip(pts, pts[1:]):
                if seg_hits_rect(p, q, r, 1.5):
                    E.append("Canh '%s' (%s) di xuyen qua hinh '%s'." % (lbl(c) or eid, edge_desc(c, cells), lbl(v)))
                    break
        if G.is_seq and c.source and c.target and c.source != c.target and cells.get(c.source) is not None \
                and cells[c.source].shape == "umlLifeline":
            if abs(pts[0][1] - pts[-1][1]) > 1.0:
                E.append("Message '%s' trong sequence diagram khong nam ngang (dy=%.1f)."
                         % (plain(c.value) or eid, pts[-1][1] - pts[0][1]))

    # ------------------------------------------------ hai canh chong khit
    segs = []
    for eid, (c, pts) in edges.items():
        for p, q in zip(pts, pts[1:]):
            if abs(p[1] - q[1]) < 0.5 and abs(p[0] - q[0]) > 0.5:
                segs.append(("h", p[1], min(p[0], q[0]), max(p[0], q[0]), eid, c))
            elif abs(p[0] - q[0]) < 0.5 and abs(p[1] - q[1]) > 0.5:
                segs.append(("v", p[0], min(p[1], q[1]), max(p[1], q[1]), eid, c))
    segs.sort(key=lambda s: (s[0], s[1]))
    reported = set()
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if b[0] != a[0] or b[1] - a[1] > 1.0:
                break
            if a[4] == b[4]:
                continue
            ov = min(a[3], b[3]) - max(a[2], b[2])
            if ov > 2.0 and (a[4], b[4]) not in reported:
                reported.add((a[4], b[4]))
                E.append("Canh '%s' va '%s' chong khit len nhau tren doan dai %.0fpx (khong phan biet duoc)."
                         % (edge_desc(a[5], cells), edge_desc(b[5], cells), ov))

    # ------------------------------------------------ nhan
    labels = G.labels
    lifelines = [v for v in G.verts if v.shape == "umlLifeline"]
    for r, owner, d, cell in labels:
        if cell.st.get("labelBackgroundColor", "none") != "none":
            continue
        for v in lifelines:
            cx, top = v.ax + v.w / 2, v.ay + float(v.st.get("size", 40))
            if owner in edges and v.id in (edges[owner][0].source, edges[owner][0].target):
                continue
            if r[0] + 1 < cx < r[2] - 1 and r[1] < v.ay + v.h and r[3] > top:
                W.append("%s nam de len duong lifeline '%s' (doi vi tri nhan hoac dat labelBackgroundColor)."
                         % (d, lbl(v)))
    for i, (r, owner, d, _) in enumerate(labels):
        for v in prim:
            if v.id == owner or is_frame(v):
                continue
            if owner in edges:
                ec = edges[owner][0]
                if v.id in anc.get(ec.source, set()) | anc.get(ec.target, set()):
                    continue
            if owner in anc.get(v.id, set()) or v.id in anc.get(owner, set()):
                continue
            if rect_overlap(r, shape_rect(v), 1.0):
                W.append("%s de len hinh '%s'." % (d, lbl(v)))
        for j in range(i + 1, len(labels)):
            r2, o2, d2, _ = labels[j]
            if rect_overlap(r, r2, 1.0):
                W.append("%s de len %s." % (d, d2))
        for eid, (c, pts) in edges.items():
            if eid == owner:
                continue
            for p, q in zip(pts, pts[1:]):
                if seg_hits_rect(p, q, r, 2.0):
                    W.append("%s bi canh %s cat ngang." % (d, edge_desc(c, cells)))
                    break

    # ------------------------------------------------ UML lint
    for c in cells.values():
        raw = c.value or ""
        if "&lt;&lt;" in raw or "<<" in plain(raw):
            W.append("'%s': dung << >> - UML chuan dung guillemet « »." % plain(raw)[:40])
        for s in re.findall(r"«([^»]+)»", plain(raw)):
            for part in s.split(","):
                if part.strip().lower() not in KNOWN_STEREOTYPES:
                    I.append("Stereotype «%s» khong nam trong danh muc UML/COMET quen thuoc." % part.strip())
        if c.edge:
            t = plain(raw).lower()
            if "«include»" in t or "«extend»" in t:
                if c.st.get("dashed") != "1" or c.st.get("endArrow", "classic") not in ("open", "openThin"):
                    E.append("Quan he %s phai la net dut + mui ten mo (dashed=1;endArrow=open)." % t.split("\n")[0])
            if c.st.get("endArrow") == "block" and c.st.get("endFill") == "0" and "«" in t:
                W.append("Canh generalization/realization khong nen co stereotype: %s" % t[:30])
    if not G.is_seq:
        linked = set()
        for c, _ in edges.values():
            linked |= {c.source, c.target}
        for v in G.verts:
            if v.shape == "umlActor" and v.id not in linked:
                W.append("Actor '%s' khong co lien ket nao." % lbl(v))

    return {"page": name, "errors": _uniq(E), "warnings": _uniq(W), "infos": _uniq(I),
            "stats": {"vertices": len(prim), "edges": len(edges)}}



def _uniq(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def lbl(c):
    t = plain(c.value).replace("\n", " ").strip()
    return (t[:40] or c.id)


def edge_desc(c, cells):
    s = cells.get(c.source)
    t = cells.get(c.target)
    return "%s->%s" % (lbl(s) if s else "?", lbl(t) if t else "?")


def validate_file(path_or_xml):
    return [analyze_page(n, m) for n, m in load_pages(path_or_xml) if m is not None]


def print_report(rep, stream=sys.stdout):
    ok = True
    for p in rep:
        e, w, i = p["errors"], p["warnings"], p["infos"]
        status = "OK" if not e else "LOI"
        print("== [%s] %s: %d hinh, %d canh | %d loi, %d canh bao, %d ghi chu"
              % (status, p["page"], p["stats"]["vertices"], p["stats"]["edges"], len(e), len(w), len(i)), file=stream)
        for x in e:
            print("  ERROR:", x, file=stream)
        for x in w:
            print("  WARN :", x, file=stream)
        for x in i:
            print("  INFO :", x, file=stream)
        ok = ok and not e
    return ok


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Kiem tra so do draw.io (chong hinh, UML lint)")
    ap.add_argument("file", help=".drawio / .xml, hoac '-' de doc stdin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    src = sys.stdin.read() if a.file == "-" else a.file
    rep = validate_file(src)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        ok = all(not p["errors"] for p in rep)
    else:
        ok = print_report(rep)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
