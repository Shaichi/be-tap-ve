#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_tests.py - kiem thu hoi quy cua bo skill comet-uml-drawio (chi dung thu vien chuan).

    python tests/run_tests.py              # chay tat ca (~15-30 giay)
    python tests/run_tests.py -v           # in tung test
    python tests/run_tests.py -k Fuzz      # loc theo ten (unittest -k)

Nhom test:
  TestExamples   moi vi du trong examples/ sinh ra 0 ERROR / 0 WARN, comet_check sach
  TestFuzz       spec ngau nhien (co seed): 0 ERROR; cong hinh thoi nam tren chu vi
  TestValidator  validate_drawio bat dung loi tren XML tu dung (chong hinh, canh xuyen hinh, ...)
  TestGenerator  ky hieu UML + bo cuc cua uml2drawio cho tung loai so do
  TestCometCheck moi luat R1-R14, S1-S5, A1-A6, C1-C2 bat dung va khong bao nham
  TestCLI        3 script chay bang dong lenh (ma thoat, glob, --xml-only, --png)
  TestInstall    install.py: cai / cai lai / go, khong dong vao thu muc la
  TestDocs       tai lieu + lenh /uml-* khop voi code (duong dan, ma luat, spec mau)

Bien moi truong: COMET_FUZZ_SEEDS (so seed moi loai, mac dinh 80); COMET_TEST_PNG=0 (bo qua chup PNG).
Chay duoc o ban nguon (co commands/) lan ban da cai (cac lenh la thu muc anh em cua engine).
"""
import base64
import contextlib
import copy
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from xml.sax.saxutils import quoteattr

sys.dont_write_bytecode = True
ENGINE = Path(__file__).resolve().parent.parent
SCRIPTS, EXAMPLES, REFS = ENGINE / "scripts", ENGINE / "examples", ENGINE / "references"
sys.path[:0] = [str(SCRIPTS), str(ENGINE / "tests")]

import comet_check as C          # noqa: E402
import comet_model as M           # noqa: E402
import comet_plan as CP       # noqa: E402
import comet_manifest as CM   # noqa: E402
import comet_reconcile as CR # noqa: E402
import comet_project as PJ    # noqa: E402
import install as INST           # noqa: E402
import preview_svg as P          # noqa: E402
import uml2drawio as U           # noqa: E402
import validate_drawio as V      # noqa: E402
from fuzz_specs import GENERATORS  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

EXAMPLE_FILES = sorted(EXAMPLES.glob("*.json"))
COMMAND_SRC = ENGINE / "commands"
HAS_COMMANDS = COMMAND_SRC.is_dir()
EXPECTED_COMMANDS = {"uml-usecase", "uml-context", "uml-class", "uml-communication", "uml-sequence",
                     "uml-statechart", "uml-activity", "uml-package", "uml-component", "uml-deployment",
                     "uml-comet", "uml-erd", "uml-screenflow", "uml-bizcontext"}
FUZZ_SEEDS = int(os.environ.get("COMET_FUZZ_SEEDS", "80"))
# bo cuc fuzz da biet con WARN (nhan multiplicity bi canh song song cung cap lop cat qua) - van 0 ERROR
FUZZ_KNOWN_WARN = {("class", 52), ("class", 63), ("class", 64), ("state", 299)}


# ============================================================ helpers
def gen(*specs):
    """specs -> (xml mxfile, canh bao luc sinh). generate() sua spec tai cho -> luon deepcopy."""
    mx, _, warns = U.generate(copy.deepcopy(list(specs)))
    return ET.tostring(mx, encoding="unicode"), warns


def report(xml):
    """validator -> (errors, warnings, infos) gop moi trang."""
    E, W, I = [], [], []
    for p in V.validate_file(xml):
        E += p["errors"]
        W += p["warnings"]
        I += p["infos"]
    return E, W, I


def pages(xml):
    return V.load_pages(xml)


def cells(xml, page=0):
    """id -> mxCell cua mot trang."""
    return {c.get("id"): c for c in pages(xml)[page][1].iter("mxCell")}


def geo(xml, page=0):
    """Toa do tuyet doi (validate_drawio.Geometry) cua mot trang."""
    return V.Geometry(pages(xml)[page][1])


def rects(G):
    return {c.id: c.rect for c in G.verts}


def style(c):
    return V.parse_style(c.get("style"))


def text(c):
    return V.plain(c.get("value"))


def edges(cs):
    return [c for c in cs.values() if c.get("edge") == "1"]


def edge_between(cs, s, t):
    es = [c for c in edges(cs) if (c.get("source"), c.get("target")) == (s, t)]
    if len(es) != 1:
        raise AssertionError("can dung 1 canh %s->%s, co %d" % (s, t, len(es)))
    return es[0]


def edge_by_label(cs, label):
    for c in edges(cs):
        if label in text(c):
            return c
    raise AssertionError("khong co canh co nhan %r" % label)


def end_labels(cs, eid):
    """Nhan multiplicity/role gan dau mut cua canh (cell con cua canh)."""
    return {text(c) for c in cs.values() if c.get("parent") == eid}


def check(*specs, partial=False):
    specs = copy.deepcopy(list(specs))
    for i, s in enumerate(specs):
        s.setdefault("_src", "%s#%d" % (s.get("diagram"), i + 1))
    return C.check(specs, partial)


def codes(msgs, code=None):
    """Tap ma luat ('R1', 'S3'...) cua cac thong bao; co code -> danh sach thong bao cua ma do."""
    if code:
        return [m for m in msgs if m.split(" ", 1)[0] == code]
    return {m.split(" ", 1)[0] for m in msgs}


def el(spec, eid):
    return next(e for e in spec["elements"] if e.get("id") == eid)


def msg(spec, name):
    return next(m for m in spec["messages"] if m.get("name") == name)


# ---- XML tu dung cho validator
BOX = "rounded=0;whiteSpace=wrap;html=1;"
LIFE = "shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;size=40;"
LANE = "swimlane;html=1;startSize=30;horizontal=1;container=1;collapsible=0;"


def vx(id, x, y, w, h, style=BOX, value=None, parent="1"):
    return ('<mxCell id="%s" value=%s style="%s" vertex="1" parent="%s"><mxGeometry x="%s" y="%s" width="%s" '
            'height="%s" as="geometry"/></mxCell>' % (id, quoteattr(id if value is None else value), style, parent,
                                                      x, y, w, h))


def ed(id, s, t, style="endArrow=open;html=1;", value="", pts=(), parent="1"):
    arr = ('<Array as="points">%s</Array>' % "".join('<mxPoint x="%s" y="%s"/>' % p for p in pts)) if pts else ""
    return ('<mxCell id="%s" value=%s style="%s" edge="1" parent="%s" source="%s" target="%s">'
            '<mxGeometry relative="1" as="geometry">%s</mxGeometry></mxCell>'
            % (id, quoteattr(value), style, parent, s, t, arr))


def graph(*cs):
    return ('<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>%s</root></mxGraphModel>'
            % "".join(cs))


# ---- chay script nhu nguoi dung
def run(script, *args, stdin=None, cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-B", str(SCRIPTS / script)] + [str(a) for a in args],
                          input=stdin, capture_output=True, text=True, encoding="utf-8",
                          cwd=str(cwd or ENGINE), env=env, timeout=600)


@contextlib.contextmanager
def quiet():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        yield


class TmpMixin:
    def tmpdir(self):
        d = Path(tempfile.mkdtemp(prefix="comet_test_"))
        self.addCleanup(lambda: d.exists() and INST.rmtree(d))
        return d


# ============================================================ bo spec COMET mau (he thong dat hang)
SHOP_UC = {"diagram": "usecase", "title": "Shop", "system": "Shop System", "elements": [
    {"id": "cust", "type": "actor", "name": "Customer"},
    {"id": "pg", "type": "actor", "name": "Payment Gateway", "side": "right"},
    {"id": "po", "type": "usecase", "name": "Place Order"},
    {"id": "vo", "type": "usecase", "name": "View Order"}], "relations": [
    {"type": "association", "from": "cust", "to": "po"},
    {"type": "association", "from": "cust", "to": "vo"},
    {"type": "association", "from": "po", "to": "pg"}]}

SHOP_CTX = {"diagram": "context", "title": "Shop - Context", "elements": [
    {"id": "sys", "type": "system", "name": "Shop System", "stereotype": "software system"},
    {"id": "cu", "type": "external", "name": "Customer", "stereotype": "external user"},
    {"id": "pg", "type": "external", "name": "Payment Gateway", "stereotype": "external system"}], "relations": [
    {"type": "association", "from": "cu", "to": "sys", "label": "Interacts with", "fromMult": "1..*", "toMult": "1"},
    {"type": "association", "from": "pg", "to": "sys", "label": "Interacts with", "fromMult": "1", "toMult": "1"}]}

SHOP_CLS = {"diagram": "class", "title": "Shop - Entity classes", "elements": [
    {"id": "ord", "type": "class", "name": "Order", "stereotype": "entity", "attributes": ["orderId: Integer"]},
    {"id": "acc", "type": "class", "name": "Customer Account", "stereotype": "entity",
     "attributes": ["accountId: Integer"]}], "relations": [
    {"type": "association", "from": "acc", "to": "ord", "label": "Places", "fromMult": "1", "toMult": "0..*"}]}

_SHOP_OBJ = [
    {"id": "cust", "type": "actor", "name": "Customer"},
    {"id": "ui", "type": "object", "class": "Customer Interaction", "stereotype": "user interaction"},
    {"id": "ctl", "type": "object", "class": "Order Control", "stereotype": "state dependent control"},
    {"id": "ord", "type": "object", "class": "Order", "stereotype": "entity"},
    {"id": "px", "type": "object", "class": "Payment Proxy", "stereotype": "proxy"},
    {"id": "pg", "type": "actor", "name": "Payment Gateway", "side": "right"}]
_SHOP_MSG = [("cust", "ui", "Order Request"), ("ui", "ctl", "Place Order(cart)"), ("ctl", "ord", "Create Order"),
             ("ctl", "px", "Pay"), ("px", "pg", "Payment Request"), ("pg", "px", "Payment Approved"),
             ("px", "ctl", "Paid"), ("ctl", "ui", "Order Confirmed"), ("ui", "cust", "Confirmation Display")]

SHOP_COMM = {"diagram": "communication", "title": "Place Order", "useCase": "Place Order",
             "elements": copy.deepcopy(_SHOP_OBJ),
             "messages": [{"seq": str(i), "from": a, "to": b, "name": n} for i, (a, b, n) in enumerate(_SHOP_MSG, 1)]}

SHOP_SEQ = {"diagram": "sequence", "title": "Place Order", "useCase": "Place Order",
            "elements": copy.deepcopy(_SHOP_OBJ),
            "messages": [{"id": "m%d" % i, "seq": str(i), "from": a, "to": b, "name": n,
                          "type": "reply" if i in (6, 7) else "sync"} for i, (a, b, n) in enumerate(_SHOP_MSG, 1)]}
SHOP_SEQ["messages"].insert(3, {"id": "m3r", "from": "ord", "to": "ctl", "type": "reply"})   # reply khong ten

SHOP_STM = {"diagram": "state", "title": "Order Control", "stateMachineOf": "Order Control", "elements": [
    {"id": "i", "type": "initial"},
    {"id": "idle", "type": "state", "name": "Idle"},
    {"id": "paying", "type": "state", "name": "Waiting for Payment"}], "relations": [
    {"type": "transition", "from": "i", "to": "idle"},
    {"type": "transition", "from": "idle", "to": "paying", "event": "Place Order", "action": ["Create Order", "Pay"]},
    {"type": "transition", "from": "paying", "to": "idle", "event": "Paid", "action": "Order Confirmed"}]}

SHOP_KEYS = ("uc", "ctx", "cls", "comm", "stm", "seq")


def shop():
    return dict(zip(SHOP_KEYS, copy.deepcopy([SHOP_UC, SHOP_CTX, SHOP_CLS, SHOP_COMM, SHOP_STM, SHOP_SEQ])))


# ============================================================ 1. vi du
class TestExamples(unittest.TestCase):
    def test_one_example_per_diagram_type(self):
        kinds = [json.loads(p.read_text(encoding="utf-8"))["diagram"] for p in EXAMPLE_FILES]
        self.assertEqual(set(kinds), set(U.FRAME_KIND))   # moi loai so do co it nhat 1 vi du

    def test_each_example_clean(self):
        for p in EXAMPLE_FILES:
            with self.subTest(example=p.name):
                xml, warns = gen(*U.load_specs([str(p)]))
                E, W, _ = report(xml)
                self.assertEqual((warns, E, W), ([], [], []))

    def test_all_examples_in_one_file(self):
        specs = U.load_specs([str(p) for p in EXAMPLE_FILES])
        xml, warns = gen(*specs)
        names = [n for n, _ in pages(xml)]
        self.assertEqual(len(names), len(specs))
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(report(xml)[:2], ([], []))

    def test_examples_comet_consistent(self):
        E, W, _ = C.check(C.load([str(p) for p in EXAMPLE_FILES]), partial=True)
        self.assertEqual((E, W), ([], []))
        E, W, _ = C.check(C.load([str(p) for p in EXAMPLE_FILES]))
        self.assertEqual(E, [])
        self.assertEqual(codes(W), {"R1"})   # chi con: use case chua ve so do tuong tac

    def test_deterministic(self):
        specs = U.load_specs([str(EXAMPLES / "atm_comm_validate_pin.json")])
        self.assertEqual(gen(*specs)[0], gen(*specs)[0])


# ============================================================ 2. fuzz
class TestFuzz(unittest.TestCase):
    def test_random_specs_no_overlap(self):
        for kind, make in sorted(GENERATORS.items()):
            for seed in range(FUZZ_SEEDS):
                xml, _ = gen(make(seed))
                E, W, _ = report(xml)
                with self.subTest(kind=kind, seed=seed):
                    self.assertEqual(E, [])
                    if (kind, seed) not in FUZZ_KNOWN_WARN:
                        self.assertEqual(W, [])

    def test_rhombus_ports_on_perimeter(self):
        """Moi dau canh noi vao hinh thoi nam tren chu vi: |fx-0.5| + |fy-0.5| = 0.5."""
        specs = [GENERATORS["activity"](s) for s in range(FUZZ_SEEDS)]
        specs += U.load_specs([str(EXAMPLES / "atm_activity_withdraw.json")])
        n = 0
        for sp in specs:
            cs = cells(gen(sp)[0])
            for c in edges(cs):
                st = style(c)
                for end, pre in (("source", "exit"), ("target", "entry")):
                    v = cs.get(c.get(end))
                    if v is None or "rhombus" not in (v.get("style") or ""):
                        continue
                    n += 1
                    fx, fy = float(st[pre + "X"]), float(st[pre + "Y"])
                    with self.subTest(spec=sp.get("title"), edge=c.get("id"), end=end):
                        self.assertAlmostEqual(abs(fx - 0.5) + abs(fy - 0.5), 0.5, delta=0.01)
        self.assertGreater(n, 50)


# ============================================================ 3. validator
class TestValidator(TmpMixin, unittest.TestCase):
    def v(self, *cs):
        return report(graph(*cs))

    def test_clean_graph(self):
        g = graph(vx("a", 0, 0, 100, 40), vx("b", 300, 0, 100, 40), ed("e", "a", "b"))
        self.assertEqual(report(g), ([], [], []))
        self.assertEqual(V.validate_file(g)[0]["stats"], {"vertices": 2, "edges": 1})

    def test_overlapping_shapes_error(self):
        E, _, _ = self.v(vx("a", 0, 0, 100, 40), vx("b", 50, 20, 100, 40))
        self.assertTrue(any("chong len hinh" in e for e in E), E)

    def test_shapes_too_close_warning(self):
        E, W, _ = self.v(vx("a", 0, 0, 100, 40), vx("b", 104, 0, 100, 40))
        self.assertEqual(E, [])
        self.assertTrue(any("qua sat nhau (4px" in w for w in W), W)

    def test_nesting_needs_container(self):
        _, W, _ = self.v(vx("a", 0, 0, 200, 200), vx("b", 50, 50, 40, 40))
        self.assertTrue(any("nam tron trong" in w for w in W), W)
        self.assertEqual(self.v(vx("a", 0, 0, 200, 200, BOX + "container=1;"), vx("b", 50, 50, 40, 40))[:2], ([], []))
        self.assertEqual(self.v(vx("a", 0, 0, 200, 200), vx("b", 50, 50, 40, 40, parent="a"))[:2], ([], []))

    def test_edge_through_shape_error(self):
        base = [vx("a", 0, 0, 100, 40), vx("b", 400, 0, 100, 40), vx("c", 200, 0, 60, 40)]
        E, _, _ = self.v(*base, ed("e", "a", "b"))
        self.assertTrue(any("di xuyen qua hinh 'c'" in e for e in E), E)
        E, _, _ = self.v(*base, ed("e", "a", "b", pts=[(150, -60), (450, -60)]))   # vong qua phia tren
        self.assertEqual(E, [])

    def test_coincident_edges_error(self):
        base = [vx("a", 0, 0, 60, 40), vx("b", 300, 0, 60, 40)]
        E, _, _ = self.v(*base, ed("e1", "a", "b"), ed("e2", "a", "b"))
        self.assertTrue(any("chong khit" in e for e in E), E)
        E, _, _ = self.v(*base, ed("e1", "a", "b", "endArrow=open;html=1;exitX=1;exitY=0.25;entryX=0;entryY=0.25;"),
                         ed("e2", "a", "b", "endArrow=open;html=1;exitX=1;exitY=0.75;entryX=0;entryY=0.75;"))
        self.assertEqual(E, [])

    def test_include_extend_notation(self):
        base = [vx("a", 0, 0, 120, 50, "ellipse;html=1;"), vx("b", 300, 0, 120, 50, "ellipse;html=1;")]
        E, _, _ = self.v(*base, ed("e", "a", "b", "endArrow=block;endFill=1;html=1;", "«include»"))
        self.assertTrue(any("net dut" in e for e in E), E)
        E, _, _ = self.v(*base, ed("e", "a", "b", "endArrow=open;endFill=0;dashed=1;html=1;", "«extend»"))
        self.assertEqual(E, [])

    def test_guillemets_and_stereotypes(self):
        _, W, _ = self.v(vx("a", 0, 0, 120, 50, value="<<entity>><br>Account"))
        self.assertTrue(any("guillemet" in w for w in W), W)
        _, _, I = self.v(vx("a", 0, 0, 120, 50, value="«frobnicator»<br>X"))
        self.assertTrue(any("«frobnicator»" in i for i in I), I)
        self.assertEqual(self.v(vx("a", 0, 0, 120, 50, value="«entity»<br>Account")), ([], [], []))

    def test_structure_errors(self):
        E, _, _ = self.v(vx("a", 0, 0, 50, 50), vx("a", 200, 0, 50, 50))
        self.assertTrue(any("Trung id 'a'" in e for e in E), E)
        E, _, _ = self.v(vx("a", 0, 0, 50, 50, parent="zz"))
        self.assertTrue(any("parent 'zz'" in e for e in E), E)
        E, _, _ = self.v(vx("a", 0, 0, 50, 50), ed("e", "a", "zz"))
        self.assertTrue(any("'zz' khong ton tai" in e for e in E), E)

    def test_sequence_message_horizontal(self):
        L = [vx("l1", 0, 0, 100, 300, LIFE, ":A"), vx("l2", 300, 0, 100, 300, LIFE, ":B")]
        tilt = "endArrow=block;endFill=1;html=1;exitX=0.5;exitY=0.3;entryX=0.5;entryY=0.5;"
        flat = "endArrow=block;endFill=1;html=1;exitX=0.5;exitY=0.3;entryX=0.5;entryY=0.3;"
        E, _, _ = self.v(*L, ed("m", "l1", "l2", tilt, "go"))
        self.assertTrue(any("khong nam ngang" in e for e in E), E)
        self.assertEqual(self.v(*L, ed("m", "l1", "l2", flat, "go"))[:2], ([], []))

    def test_unlinked_actor_and_label_on_shape(self):
        actor = "shape=umlActor;html=1;labelPosition=right;verticalLabelPosition=middle;align=left;"
        _, W, _ = self.v(vx("act", 0, 0, 30, 60, actor, "A Very Long Actor Name"), vx("b", 40, 10, 100, 40))
        self.assertTrue(any("khong co lien ket" in w for w in W), W)
        self.assertTrue(any("de len hinh 'b'" in w for w in W), W)

    def test_swimlanes_touch_and_edges_cross(self):
        self.assertEqual(self.v(vx("L1", 0, 0, 200, 300, LANE, "Lane 1"), vx("L2", 200, 0, 200, 300, LANE, "Lane 2"),
                                vx("a", 50, 60, 100, 40, parent="L1"), vx("b", 50, 60, 100, 40, parent="L2"),
                                ed("e", "a", "b"))[:2], ([], []))

    def test_input_formats_and_compressed_page(self):
        model = graph(vx("a", 0, 0, 50, 50), vx("b", 10, 10, 50, 50))   # dung 1 loi chong hinh
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        data = base64.b64encode(co.compress(urllib.parse.quote(model).encode()) + co.flush()).decode()
        for src, name in ((model, "Page-1"), ('<diagram name="D">%s</diagram>' % model, "D"),
                          ('<mxfile><diagram name="Z" id="p1">%s</diagram></mxfile>' % data, "Z")):
            with self.subTest(page=name):
                rep = V.validate_file(src)
                self.assertEqual([p["page"] for p in rep], [name])
                self.assertEqual(len(rep[0]["errors"]), 1)
        with self.assertRaises(ValueError):
            V.load_pages("<foo/>")

    def test_cli(self):
        d = self.tmpdir()
        bad = d / "bad.drawio"
        bad.write_text(graph(vx("a", 0, 0, 50, 50), vx("b", 10, 10, 50, 50)), encoding="utf-8")
        r = run("validate_drawio.py", bad)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ERROR", r.stdout)
        r = run("validate_drawio.py", bad, "--json")
        self.assertEqual(len(json.loads(r.stdout)[0]["errors"]), 1)
        r = run("validate_drawio.py", "-", stdin=graph(vx("a", 0, 0, 50, 50)))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[OK]", r.stdout)


# ============================================================ 4. generator
UC_SPEC = {"diagram": "usecase", "title": "ATM", "system": "Banking System", "elements": [
    {"id": "cust", "type": "actor", "name": "ATM Customer"},
    {"id": "bank", "type": "actor", "name": "Bank Server", "side": "right"},
    {"id": "wd", "type": "usecase", "name": "Withdraw Funds"},
    {"id": "vp", "type": "usecase", "name": "Validate PIN"},
    {"id": "rc", "type": "usecase", "name": "Print Receipt"}], "relations": [
    {"type": "association", "from": "cust", "to": "wd"},
    {"type": "association", "from": "wd", "to": "bank"},
    {"type": "include", "from": "wd", "to": "vp"},
    {"type": "extend", "from": "rc", "to": "wd", "condition": "receipt requested"}]}

CLASS_SPEC = {"diagram": "class", "title": "Accounts", "elements": [
    {"id": "acct", "type": "class", "name": "Account", "abstract": True, "stereotype": "<<entity>>",
     "attributes": ["balance: Real"]},
    {"id": "chk", "type": "class", "name": "Checking Account", "attributes": ["overdraft: Real"],
     "operations": ["+ debit(amount: Real)"]},
    {"id": "cust", "type": "class", "name": "Customer", "attributes": ["name: String"]},
    {"id": "bank", "type": "class", "name": "Bank", "attributes": ["bankName: String"]},
    {"id": "card", "type": "class", "name": "ATM Card", "attributes": ["cardId: String"]},
    {"id": "ifc", "type": "interface", "name": "Auditable", "operations": ["audit()"]},
    {"id": "kind", "type": "enumeration", "name": "AccountKind", "literals": ["CHECKING", "SAVINGS"]}], "relations": [
    {"type": "generalization", "from": "chk", "to": "acct"},
    {"type": "composition", "from": "bank", "to": "acct", "fromMult": "1", "toMult": "0..*"},
    {"type": "aggregation", "from": "cust", "to": "card", "fromMult": "1", "toMult": "1..*"},
    {"type": "association", "from": "cust", "to": "acct", "label": "Owns", "fromMult": "1..*", "toMult": "1..*",
     "fromRole": "owner"},
    {"type": "realization", "from": "acct", "to": "ifc"},
    {"type": "dependency", "from": "acct", "to": "kind", "stereotype": "use"}]}

STATE_SPEC = {"diagram": "state", "title": "ATM Control", "stateMachineOf": "ATM Control", "elements": [
    {"id": "i", "type": "initial"},
    {"id": "idle", "type": "state", "name": "Idle", "activities": ["entry / Display Welcome"]},
    {"id": "proc", "type": "state", "name": "Processing"},
    {"id": "pi", "type": "initial", "in": "proc"},
    {"id": "val", "type": "state", "name": "Validating PIN", "in": "proc", "activities": ["do / Check PIN"]},
    {"id": "ch", "type": "choice", "in": "proc"},
    {"id": "menu", "type": "state", "name": "Waiting for Choice", "in": "proc"},
    {"id": "closed", "type": "state", "name": "Closed Down"},
    {"id": "f", "type": "final"}], "relations": [
    {"type": "transition", "from": "i", "to": "idle"},
    {"type": "transition", "from": "idle", "to": "proc", "event": "Card Inserted", "action": ["Get PIN", "Beep"]},
    {"type": "transition", "from": "pi", "to": "val"},
    {"type": "transition", "from": "val", "to": "ch", "event": "PIN Checked"},
    {"type": "transition", "from": "ch", "to": "menu", "guard": "valid"},
    {"type": "transition", "from": "ch", "to": "val", "guard": "else", "action": "Invalid PIN Prompt"},
    {"type": "transition", "from": "menu", "to": "menu", "event": "Tick"},
    {"type": "transition", "from": "proc", "to": "idle", "event": "Cancel", "action": "Eject"},
    {"type": "transition", "from": "idle", "to": "closed", "event": "Switch Off"},
    {"type": "transition", "from": "closed", "to": "f", "event": "Power Down"}]}

ACT_SPEC = {"diagram": "activity", "title": "Withdraw Funds", "partitions": ["ATM Customer", "ATM", "Bank Server"],
            "elements": [
                {"id": "start", "type": "initial", "partition": "ATM Customer"},
                {"id": "insert", "type": "action", "name": "Insert Card", "partition": "ATM Customer"},
                {"id": "validate", "type": "action", "name": "Validate PIN", "partition": "Bank Server"},
                {"id": "d1", "type": "decision"},   # khong khai bao lan -> theo lan cua nut ke
                {"id": "menu", "type": "action", "name": "Display Menu", "partition": "ATM"},
                {"id": "invalid", "type": "action", "name": "Display Invalid PIN", "partition": "ATM"},
                {"id": "m1", "type": "merge", "partition": "ATM"},
                {"id": "eject", "type": "action", "name": "Eject Card", "partition": "ATM"},
                {"id": "end", "type": "activityFinal", "partition": "ATM Customer"}], "relations": [
                {"type": "flow", "from": "start", "to": "insert"},
                {"type": "flow", "from": "insert", "to": "validate"},
                {"type": "flow", "from": "validate", "to": "d1"},
                {"type": "flow", "from": "d1", "to": "menu", "guard": "PIN valid"},
                {"type": "flow", "from": "d1", "to": "invalid", "guard": "PIN invalid"},
                {"type": "flow", "from": "menu", "to": "m1"},
                {"type": "flow", "from": "invalid", "to": "m1"},
                {"type": "flow", "from": "m1", "to": "eject"},
                {"type": "flow", "from": "eject", "to": "end"}]}

SEQ_SPEC = {"diagram": "sequence", "title": "Validate PIN", "elements": [
    {"id": "cust", "type": "actor", "name": "ATM Customer"},
    {"id": "cr", "type": "object", "class": "Card Reader Interface", "stereotype": "input"},
    {"id": "ctl", "type": "object", "name": "atmCtl", "class": "ATM Control", "stereotype": "state dependent control"},
    {"id": "tx", "type": "object", "class": "ATM Transaction", "stereotype": "entity"}], "messages": [
    {"id": "m1", "from": "cust", "to": "cr", "name": "Card Reader Input", "type": "async"},
    {"id": "m2", "from": "cr", "to": "ctl", "name": "Card Inserted"},
    {"id": "m3", "from": "ctl", "to": "tx", "type": "create"},
    {"id": "m4", "from": "ctl", "to": "ctl", "name": "Start Timer"},
    {"id": "m5", "from": "ctl", "to": "tx", "name": "Check PIN"},
    {"id": "m6", "from": "tx", "to": "ctl", "name": "PIN Status", "type": "reply"},
    {"id": "m7", "from": "ctl", "to": "cr", "name": "Eject"},
    {"id": "m8", "from": "ctl", "to": "cr", "name": "Confiscate"}], "fragments": [
    {"type": "loop", "guard": "retry < 3", "from": "m5", "to": "m8"},
    {"type": "alt", "operands": [{"guard": "PIN invalid", "from": "m7", "to": "m7"},
                                 {"guard": "else", "from": "m8", "to": "m8"}]}]}

COMP_SPEC = {"diagram": "component", "title": "Banking", "elements": [
    {"id": "atm", "type": "component", "name": "ATM Client"},
    {"id": "svc", "type": "component", "name": "Bank Service", "stereotype": "service subsystem"},
    {"id": "ib", "type": "interface", "name": "IBankService", "notation": "lollipop"},
    {"id": "ia", "type": "interface", "name": "IAudit", "notation": "lollipop"}], "relations": [
    {"type": "provides", "from": "svc", "to": "ib"},
    {"type": "requires", "from": "atm", "to": "ib"},
    {"type": "realization", "from": "svc", "to": "ia"}]}

DEPLOY_SPEC = {"diagram": "deployment", "title": "Deployment", "elements": [
    {"id": "atm", "type": "device", "name": "ATM"},
    {"id": "srv", "type": "node", "name": "Bank Server"},
    {"id": "jvm", "type": "executionEnvironment", "name": "JVM", "in": "srv"},
    {"id": "war", "type": "artifact", "name": "bank.war", "in": "jvm"},
    {"id": "cli", "type": "artifact", "name": "atm-client.jar", "in": "atm"}], "relations": [
    {"type": "communicationpath", "from": "atm", "to": "srv", "stereotype": "WAN", "fromMult": "1..*", "toMult": "1"}]}


class TestGenerator(unittest.TestCase):
    def clean(self, spec):
        xml, warns = gen(spec)
        E, W, _ = report(xml)
        self.assertEqual((warns, E, W), ([], [], []))
        return xml, cells(xml), geo(xml)

    def test_usecase(self):
        xml, cs, G = self.clean(UC_SPEC)
        R = rects(G)
        self.assertIn("shape=umlActor", cs["cust"].get("style"))
        self.assertTrue(cs["wd"].get("style").startswith("ellipse"))
        bnd = R["system_boundary"]
        self.assertEqual(text(cs["system_boundary"]), "Banking System")
        for u in ("wd", "vp", "rc"):
            self.assertTrue(V.rect_contains(bnd, R[u]), u)
        self.assertLess(R["cust"][2], bnd[0])      # actor chinh ben trai he thong
        self.assertGreater(R["bank"][0], bnd[2])   # actor phu ("side": "right") ben phai
        inc, ext = edge_by_label(cs, "«include»"), edge_by_label(cs, "«extend»")
        self.assertEqual((inc.get("source"), inc.get("target")), ("wd", "vp"))    # base -> included
        self.assertEqual((ext.get("source"), ext.get("target")), ("rc", "wd"))    # extension -> base
        for e in (inc, ext):
            self.assertEqual((style(e).get("dashed"), style(e).get("endArrow")), ("1", "open"))
        self.assertIn("[receipt requested]", text(ext))
        self.assertEqual(style(edge_between(cs, "cust", "wd")).get("endArrow"), "none")
        self.assertEqual(text(cs["diagram_frame"]), "uc ATM")

    def test_class_notation(self):
        xml, cs, G = self.clean(CLASS_SPEC)
        gz, rz = style(edge_between(cs, "chk", "acct")), style(edge_between(cs, "acct", "ifc"))
        self.assertEqual((gz.get("endArrow"), gz.get("endFill"), gz.get("dashed")), ("block", "0", None))
        self.assertEqual((rz.get("endArrow"), rz.get("endFill"), rz.get("dashed")), ("block", "0", "1"))
        comp, aggr = edge_between(cs, "bank", "acct"), edge_between(cs, "cust", "card")
        self.assertEqual((style(comp).get("startArrow"), style(comp).get("startFill")), ("diamondThin", "1"))
        self.assertEqual((style(aggr).get("startArrow"), style(aggr).get("startFill")), ("diamondThin", "0"))
        self.assertEqual(end_labels(cs, comp.get("id")), {"1", "0..*"})
        dep = edge_between(cs, "acct", "kind")
        self.assertEqual((style(dep).get("dashed"), style(dep).get("endArrow")), ("1", "open"))
        self.assertIn("«use»", text(dep))
        own = edge_between(cs, "cust", "acct")
        self.assertEqual((text(own), style(own).get("endArrow")), ("Owns", "none"))
        self.assertEqual(end_labels(cs, own.get("id")), {"owner\n1..*", "1..*"})
        acct = cs["acct"].get("value")
        self.assertIn("<i>", acct)                                   # abstract -> in nghieng
        self.assertIn("«entity»", acct)                              # <<entity>> -> «entity»
        self.assertNotIn("<<", text(cs["acct"]))
        self.assertIn("balance: Real", text(cs["acct__attrs"]))
        self.assertIn("debit(amount: Real)", text(cs["chk__ops"]))
        self.assertIn("chk__sep", cs)
        self.assertIn("«interface»", text(cs["ifc"]))
        self.assertIn("«enumeration»", text(cs["kind"]))
        self.assertIn("CHECKING", text(cs["kind__attrs"]))
        self.assertEqual(check(CLASS_SPEC), ([], [], []))

    def test_statechart(self):
        xml, cs, G = self.clean(STATE_SPEC)
        self.assertIn("container=1", cs["proc"].get("style"))
        for k in ("pi", "val", "ch", "menu"):
            self.assertEqual(cs[k].get("parent"), "proc", k)
        self.assertIn("entry / Display Welcome", text(cs["idle__acts"]))
        self.assertEqual(text(edge_between(cs, "idle", "proc")), "Card Inserted / Get PIN, Beep")
        self.assertEqual(text(edge_between(cs, "ch", "menu")), "[valid]")
        self.assertEqual(text(edge_between(cs, "ch", "val")), "[else] / Invalid PIN Prompt")
        self.assertEqual(text(edge_between(cs, "menu", "menu")), "Tick")        # self-transition
        self.assertEqual(text(edge_between(cs, "i", "idle")), "")
        self.assertEqual(text(cs["diagram_frame"]), "stm ATM Control")
        self.assertEqual(check(STATE_SPEC)[:2], ([], []))

    def test_pseudostate_shapes(self):
        def R(kind, direction="TB"):
            return U.render({"id": "x", "type": kind}, direction, "state")
        self.assertEqual((R("history").value, R("deephistory").value), ("H", "H*"))
        self.assertIn("shape=endState", R("final").style)
        self.assertIn("fillColor=#000000", R("initial").style)
        self.assertTrue(R("choice").style.startswith("rhombus"))
        self.assertIn("shape=sumEllipse", R("flowFinal").style)
        self.assertEqual((R("fork").w, R("fork").h, R("join", "LR").w), (120, 6, 6))

    def test_stereotype_normalisation(self):
        self.assertEqual(U.stereo("entity"), "«entity»")
        self.assertEqual(U.stereo("«entity»"), "«entity»")
        self.assertEqual(U.stereo("<<entity>>"), "«entity»")
        self.assertEqual(U.stereo(["input", "device"]), "«input, device»")
        self.assertEqual(U.stereo(""), "")

    def test_activity_swimlanes(self):
        lanes = ["lane_ATM_Customer", "lane_ATM", "lane_Bank_Server"]
        want = {"start": 0, "insert": 0, "end": 0, "menu": 1, "invalid": 1, "m1": 1, "eject": 1,
                "validate": 2, "d1": 2}
        for direction, horiz in (("TB", "1"), ("LR", "0")):
            with self.subTest(direction=direction):
                sp = dict(copy.deepcopy(ACT_SPEC), direction=direction)
                xml, cs, G = self.clean(sp)
                R = rects(G)
                for l in lanes:
                    st = style(cs[l])
                    self.assertEqual((st.get("_base"), st.get("horizontal"), st.get("startSize")),
                                     ("swimlane", horiz, "30"))
                self.assertEqual([text(cs[l]) for l in lanes], ACT_SPEC["partitions"])
                for a, b in zip(lanes, lanes[1:]):   # cac lan xep sat nhau thanh mot dai
                    ra, rb = R[a], R[b]
                    if direction == "TB":
                        self.assertAlmostEqual(ra[2], rb[0], delta=0.5)
                        self.assertEqual((round(ra[1]), round(ra[3])), (round(rb[1]), round(rb[3])))
                    else:
                        self.assertAlmostEqual(ra[3], rb[1], delta=0.5)
                        self.assertEqual((round(ra[0]), round(ra[2])), (round(rb[0]), round(rb[2])))
                for k, li in want.items():
                    lr, er = R[lanes[li]], R[k]
                    self.assertEqual(cs[k].get("parent"), lanes[li], k)
                    self.assertTrue(V.rect_contains(lr, er), k)
                    self.assertGreaterEqual(er[1] if direction == "TB" else er[0],
                                            (lr[1] if direction == "TB" else lr[0]) + 30, k)   # duoi tieu de lan
                self.assertEqual(check(sp)[:2], ([], []))

    def test_partition_warnings(self):
        sp = copy.deepcopy(ACT_SPEC)
        el(sp, "insert")["partition"] = "Nowhere"
        self.assertTrue(any("partition 'Nowhere' khong ton tai" in w for w in gen(sp)[1]))
        sp = copy.deepcopy(ACT_SPEC)
        del sp["partitions"]
        self.assertTrue(any("khong khai bao 'partitions'" in w for w in gen(sp)[1]))

    def test_sequence(self):
        xml, cs, G = self.clean(SEQ_SPEC)
        R = rects(G)
        for p in ("cust", "cr", "ctl", "tx"):
            self.assertIn("shape=umlLifeline", cs[p].get("style"))
            self.assertNotIn("<u>", cs[p].get("value"))              # UML 2: lifeline khong gach chan
        self.assertIn("participant=umlActor", cs["cust"].get("style"))
        self.assertEqual(text(cs["ctl"]), "«state dependent control»\natmCtl : ATM Control")
        self.assertEqual(text(cs["cr"]), "«input»\n: Card Reader Interface")
        ys = []
        for m in ("m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"):
            pts = G.edges[m][1]
            ys.append(pts[0][1])
            if m != "m4":
                self.assertAlmostEqual(pts[0][1], pts[-1][1], delta=0.5, msg=m)   # message nam ngang
        self.assertEqual(ys, sorted(ys))                                          # dung thu tu khai bao
        self.assertEqual((style(cs["m2"]).get("endArrow"), style(cs["m2"]).get("endFill")), ("block", "1"))
        self.assertEqual((style(cs["m1"]).get("endArrow"), style(cs["m1"]).get("dashed")), ("open", None))
        self.assertEqual((style(cs["m6"]).get("endArrow"), style(cs["m6"]).get("dashed")), ("open", "1"))
        self.assertEqual(text(cs["m3"]), "«create»")
        self.assertGreater(R["tx"][1], R["cust"][1] + 40)                         # lifeline duoc tao sau
        self.assertEqual((cs["m4"].get("source"), cs["m4"].get("target")), ("ctl", "ctl"))
        self.assertEqual(len(cs["m4"].findall("mxGeometry/Array/mxPoint")), 2)
        loop, alt = R["frag_loop"], R["frag_alt"]
        self.assertEqual((text(cs["frag_loop"]), text(cs["frag_alt"])), ("loop", "alt"))
        self.assertTrue(V.rect_contains(loop, alt))                               # fragment long nhau
        guards = {text(c) for c in cs.values() if (c.get("id") or "").startswith("frag_") and "_g" in c.get("id")}
        self.assertEqual(guards, {"[retry < 3]", "[PIN invalid]", "[else]"})
        self.assertEqual(style(cs["frag_alt_sep1"]).get("dashed"), "1")
        for m, f in (("m5", loop), ("m7", alt), ("m8", alt)):
            self.assertTrue(f[1] < G.edges[m][1][0][1] < f[3], m)

    def test_sequence_autocreate_and_bad_fragment(self):
        sp = {"diagram": "sequence", "title": "T", "elements": [{"id": "a", "type": "object", "class": "A"}],
              "messages": [{"from": "a", "to": "zz", "name": "Ping"}]}
        xml, warns = gen(sp)
        self.assertTrue(any("'zz' khong ton tai -> tu tao" in w for w in warns), warns)
        self.assertIn("umlLifeline", cells(xml)["zz"].get("style"))
        sp["fragments"] = [{"type": "opt", "from": "m1", "to": "m9"}]
        with self.assertRaises(SystemExit):
            gen(sp)

    def test_communication(self):
        xml, cs, G = self.clean(SHOP_COMM)
        cx = {c.id: (c.rect[0] + c.rect[2]) / 2 for c in G.verts}
        cat = {"cust": 0, "ui": 1, "px": 1, "ctl": 2, "ord": 4, "pg": 9}   # cot COMET trai -> phai
        for a in cat:
            for b in cat:
                if cat[a] < cat[b]:
                    self.assertLess(cx[a], cx[b], (a, b))
        links = edges(cs)
        self.assertEqual(len(links), 5)                                   # 1 link cho moi cap doi tuong
        self.assertTrue(all(style(c).get("endArrow") == "none" for c in links))
        lab = {frozenset((c.get("source"), c.get("target"))): text(c) for c in links}
        self.assertIn("2: Place Order(cart) →", lab[frozenset(("ui", "ctl"))])   # mui ten theo huong that
        self.assertIn("← 8: Order Confirmed", lab[frozenset(("ui", "ctl"))])
        sp = copy.deepcopy(SHOP_COMM)
        for m in sp["messages"]:
            del m["seq"]
        self.assertIn("1: Order Request", gen(sp)[0])                    # tu danh so
        sp["autonumber"] = False
        self.assertNotIn("1: Order Request", gen(sp)[0])

    def test_component_lollipop(self):
        xml, cs, G = self.clean(COMP_SPEC)
        R = rects(G)
        self.assertTrue(cs["ib"].get("style").startswith("ellipse"))
        self.assertEqual((R["ib"][2] - R["ib"][0], R["ib"][3] - R["ib"][1]), (20, 20))
        prov, req = style(edge_between(cs, "svc", "ib")), edge_between(cs, "atm", "ib")
        self.assertEqual((prov.get("endArrow"), prov.get("dashed")), ("none", None))   # provided: net lien
        self.assertEqual((style(req).get("dashed"), style(req).get("endArrow")), ("1", "open"))
        self.assertIn("«use»", text(req))                                             # required: «use»
        self.assertEqual(style(edge_between(cs, "svc", "ia")).get("endArrow"), "none")  # realization -> ball
        self.assertIn("shape=module", cs["atm__icon"].get("style"))
        self.assertIn("«service subsystem»", text(cs["svc"]))

    def test_deployment_nesting(self):
        xml, cs, G = self.clean(DEPLOY_SPEC)
        self.assertEqual({k: cs[k].get("parent") for k in ("jvm", "war", "cli")},
                         {"jvm": "srv", "war": "jvm", "cli": "atm"})
        for k in ("atm", "srv"):
            self.assertIn("shape=cube", cs[k].get("style"))
            self.assertIn("container=1", cs[k].get("style"))
        self.assertIn("«WAN»", text(edge_between(cs, "atm", "srv")))
        self.assertIn("«artifact»", text(cs["war"]))

    def test_shop_diagrams_clean(self):
        for key, sp in shop().items():
            with self.subTest(diagram=key):
                self.clean(sp)

    def test_bad_references_warn_and_skip(self):
        sp = {"diagram": "class", "title": "T", "elements": [
            {"id": "a", "type": "class", "name": "A"}, {"id": "b", "type": "class", "name": "B", "in": "nope"}],
            "relations": [{"type": "association", "from": "a", "to": "ghost"}]}
        xml, warns = gen(sp)
        self.assertTrue(any("'ghost' khong ton tai -> bo qua" in w for w in warns), warns)
        self.assertTrue(any("in='nope' khong ton tai" in w for w in warns), warns)
        self.assertEqual(edges(cells(xml)), [])
        self.assertEqual(report(xml)[0], [])

    def test_cross_container_relation_attaches_to_boundary(self):
        sp = {"diagram": "state", "title": "T", "elements": [
            {"id": "i", "type": "initial"}, {"id": "c", "type": "state", "name": "Composite"},
            {"id": "ci", "type": "initial", "in": "c"}, {"id": "s", "type": "state", "name": "Inner", "in": "c"},
            {"id": "o", "type": "state", "name": "Outer"}], "relations": [
            {"type": "transition", "from": "i", "to": "c"}, {"type": "transition", "from": "ci", "to": "s"},
            {"type": "transition", "from": "s", "to": "o", "event": "Done"}]}
        xml, warns = gen(sp)
        self.assertTrue(any("vuot bien container" in w for w in warns), warns)
        e = edge_by_label(cells(xml), "Done")
        self.assertEqual((e.get("source"), e.get("target")), ("c", "o"))
        self.assertEqual(report(xml)[0], [])

    def test_page_names_unique(self):
        a = {"diagram": "class", "title": "X", "elements": [{"id": "a", "type": "class", "name": "A"}]}
        xml, _ = gen(a, a, a, dict(SHOP_COMM, title="Y"), dict(SHOP_SEQ, title="Y"))
        self.assertEqual([n for n, _ in pages(xml)],
                         ["X (class)", "X (class) 2", "X (class) 3", "Y (communication)", "Y (sequence)"])

    def test_frame_and_escaping(self):
        sp = {"diagram": "state", "title": "R&D <Lab>", "elements": [{"id": "s", "type": "state", "name": "A & B <x>"}]}
        xml, _ = gen(sp)
        cs = cells(xml)
        self.assertEqual(text(cs["diagram_frame"]), "stm R&D <Lab>")
        self.assertEqual(text(cs["s"]), "A & B <x>")
        cs = cells(gen(dict(sp, frame=False))[0])
        self.assertFalse(any("umlFrame" in (c.get("style") or "") for c in cs.values()))


    def test_design_class_full_notation(self):
        sp = json.loads((EXAMPLES / "order_design_class.json").read_text(encoding="utf-8"))
        xml, cs, G = self.clean(sp)
        vals = " ".join(c.get("value") or "" for c in cs.values())
        for s in ("-name: String", "#amount: float", "+getPriceForQuantity(qty: int): float"):
            self.assertIn(s, vals)                                                     # visibility + kieu + operation
        self.assertIn("<i>Payment</i>", cs["pay"].get("value"))                        # abstract in nghieng
        agg = edge_between(cs, "ord", "od")
        self.assertEqual((style(agg).get("startArrow"), style(agg).get("startFill")), ("diamondThin", "0"))
        self.assertIn("line item", " ".join(end_labels(cs, agg.get("id"))))             # role
        nav = style(edge_between(cs, "od", "item"))
        self.assertEqual(nav.get("endArrow"), "open")                                  # navigable
        for c in ("cash", "chk", "cr"):
            g = style(edge_between(cs, c, "pay"))
            self.assertEqual((g.get("endArrow"), g.get("endFill")), ("block", "0"))      # generalization con -> cha
        self.assertEqual(check(sp, partial=True), ([], [], []))

    def test_action_rounded_rect_and_decision_question(self):
        sp = {"diagram": "activity", "title": "T", "elements": [
            {"id": "s", "type": "initial"}, {"id": "a", "type": "action", "name": "Nhập số tiền"},
            {"id": "d", "type": "decision", "question": "Số dư có đủ để rút không?"},
            {"id": "b", "type": "action", "name": "Rút tiền"}, {"id": "m", "type": "merge"},
            {"id": "f", "type": "activityFinal"}], "relations": [
            {"from": "s", "to": "a"}, {"from": "a", "to": "d"}, {"from": "d", "to": "b", "guard": "Có"},
            {"from": "d", "to": "m", "guard": "Không"}, {"from": "b", "to": "m"}, {"from": "m", "to": "f"}]}
        xml, cs, G = self.clean(sp)
        st = style(cs["a"])
        self.assertEqual((st.get("rounded"), st.get("absoluteArcSize")), ("1", "1"))   # chu nhat bo goc
        self.assertEqual(style(cs["d"]).get("_base"), "rhombus")
        self.assertEqual(" ".join(text(cs["d"]).split()), "Số dư có đủ để rút không?")   # tu xuong dong
        self.assertEqual(text(cs["m"]), "")                                            # merge de trong
        R = rects(G)
        self.assertGreater(R["d"][2] - R["d"][0], R["m"][2] - R["m"][0])               # thoi noi cho vua chu
        self.assertEqual(text(edge_between(cs, "d", "b")), "[Có]")

    def test_erd_chen(self):
        sp = {"diagram": "erd", "title": "Chen", "elements": [
            {"id": "u", "type": "entity", "name": "User"},
            {"id": "r", "type": "entity", "name": "Role"},
            {"id": "c", "type": "entity", "name": "Comment", "weak": True},
            {"id": "s", "type": "entity", "name": "Student"}, {"id": "k", "type": "entity", "name": "Course"},
            {"id": "enr", "type": "relationship", "name": "enrolls"}], "relations": [
            {"from": "r", "to": "u", "name": "has_role", "fromCard": "M", "toCard": "N"},
            {"from": "u", "to": "c", "name": "comments", "fromCard": "1", "toCard": "N"},
            {"from": "c", "to": "c", "name": "replies", "fromCard": "1", "toCard": "N"},
            {"from": "s", "to": "enr", "card": "N"}, {"from": "enr", "to": "k", "card": "M"},
            {"from": "u", "to": "enr", "card": "1"}]}
        xml, cs, G = self.clean(sp)
        self.assertFalse(any("umlFrame" in (c.get("style") or "") for c in cs.values()))   # khong khung
        self.assertEqual(text(cs["u"]), "User")                                        # o chi ghi ten, in dam
        self.assertEqual(style(cs["u"]).get("fontStyle"), "1")
        self.assertEqual(style(cs["c"]).get("double"), "1")                            # thuc the yeu: vien kep
        dia = {text(c): k for k, c in cs.items() if style(c).get("_base") == "rhombus"}
        self.assertEqual(sorted(dia), ["comments", "enrolls", "has_role", "replies"])
        for e in edges(cs):                                                            # duong lien khong mui ten
            st = style(e)
            self.assertEqual((st.get("endArrow"), st.get("startArrow")), ("none", "none"))
            self.assertEqual(text(e), "")
        hr = dia["has_role"]
        self.assertEqual(end_labels(cs, edge_between(cs, "r", hr).get("id")), {"M"})   # ban so phia thuc the
        self.assertEqual(end_labels(cs, edge_between(cs, hr, "u").get("id")), {"N"})
        rp = dia["replies"]
        self.assertEqual(end_labels(cs, edge_between(cs, "c", rp).get("id")), {"1"})   # de quy
        self.assertEqual(end_labels(cs, edge_between(cs, rp, "c").get("id")), {"N"})
        self.assertEqual(end_labels(cs, edge_between(cs, "enr", "k").get("id")), {"M"})  # bac 3
        self.assertEqual(check(sp), ([], [], []))
        attr = copy.deepcopy(sp)
        attr["elements"][0]["attributes"] = ["PK id: INT"]
        warns = gen(attr)[1]
        self.assertTrue(any("khong ve thuoc tinh" in w for w in warns), warns)         # thuoc tinh bi bo qua

    def test_screenflow_legacy_flow_spec(self):
        # spec kieu luong chi tiet cu (initial/decision/items/trigger) -> van ve thanh site map, kem canh bao
        sp = {"diagram": "screenflow", "title": "SF", "elements": [
            {"id": "s", "type": "initial"},
            {"id": "a", "type": "screen", "name": "Login", "items": ["Email", "[Login]"]},
            {"id": "d", "type": "decision", "question": "Valid?"},
            {"id": "e", "type": "dialog", "name": "Error"},
            {"id": "h", "type": "page", "name": "Home"}], "relations": [
            {"type": "navigate", "from": "s", "to": "a"},
            {"type": "navigate", "from": "a", "to": "d", "trigger": "Login"},
            {"type": "navigate", "from": "d", "to": "h", "guard": "yes"},
            {"type": "navigate", "from": "d", "to": "e", "guard": "no"},
            {"type": "navigate", "from": "e", "to": "a", "trigger": "OK"}]}
        xml, warns = gen(sp)
        self.assertEqual(report(xml)[:2], ([], []))
        for k in ("nut initial", "nut decision", "'items' cua 'Login'", "nhan cua 4 dieu huong"):
            self.assertTrue(any(k in w for w in warns), k)
        cs = cells(xml)
        self.assertNotIn("s", cs)
        self.assertNotIn("d", cs)
        self.assertNotIn("a__ui", cs)
        self.assertEqual(text(cs["a"]), "Login")
        self.assertEqual(style(cs["e"]).get("rounded"), "1")                           # dialog bo goc
        self.assertIsNotNone(edge_between(cs, "a", "h"))                              # noi thang qua decision
        self.assertIsNotNone(edge_between(cs, "a", "e"))
        for e in edges(cs):
            self.assertEqual(text(e), "")
        self.assertFalse(any("umlFrame" in (c.get("style") or "") for c in cs.values()))
        W = check(sp, partial=True)[1]
        for k in ("nut initial", "nut decision", "'Login' co 'items'", "co nhan"):
            self.assertTrue(any("F2" in w and k in w for w in W), k)

    def test_screenflow_sitemap_tree(self):
        sp = json.loads((EXAMPLES / "lms_screenflow_sitemap.json").read_text(encoding="utf-8"))
        xml, cs, G = self.clean(sp)
        R = rects(G)
        cy = {k: (r[1] + r[3]) / 2 for k, r in R.items()}
        cx = {k: (r[0] + r[2]) / 2 for k, r in R.items()}
        self.assertFalse(any("umlFrame" in (c.get("style") or "") for c in cs.values()))   # khong khung
        self.assertEqual(text(cs["home"]), "Home")                                     # o chi ghi ten
        self.assertEqual(style(cs["home"]).get("rounded"), "0")
        self.assertEqual(style(cs["login"]).get("rounded"), "1")                       # popup bo goc
        for e in edges(cs):
            self.assertEqual(text(e), "")                                              # khong nhan
            self.assertEqual(style(e).get("rounded"), "1")
            self.assertEqual(style(e).get("endArrow"), "open")
        for a, b in (("posts", "post"), ("blogs", "blog"), ("subject", "price"), ("home", "myreg")):
            self.assertAlmostEqual(cy[a], cy[b], delta=0.5)                            # same: cung hang
            self.assertLess(R[a][2], R[b][0])
        self.assertAlmostEqual(cx["profile"], cx["home"], delta=0.5)                   # top: ngay tren
        self.assertLess(R["profile"][3], R["home"][1])
        self.assertLess(R["login"][2], R["home"][0])                                   # left
        self.assertLess(cy["register"], cy["login"])
        self.assertGreater(cy["reset"], cy["login"])
        self.assertLess(cy["blogs"], cy["home"])                                       # up
        self.assertGreater(cy["addpost"], cy["posts"])                                 # down: hang duoi
        self.assertAlmostEqual(cx["addpost"], cx["post"], delta=0.5)
        self.assertLess(cy["dim"], cy["subject"])                                      # branch side
        self.assertGreater(cy["slessons"], cy["subject"])
        ex = [float(style(edge_between(cs, "subject", k)).get("exitX", -1)) for k in ("dim", "slessons")]
        self.assertEqual(ex, [1.0, 1.0])                                               # toa tu canh phai
        self.assertEqual(float(style(edge_between(cs, "posts", "addpost")).get("exitY", -1)), 1.0)
        self.assertTrue(U.sitemap_mode(sp))
        self.assertEqual(check(sp, partial=True)[:2], ([], []))

    def test_bizcontext_orthogonal(self):
        sp = json.loads((EXAMPLES / "shop_bizcontext.json").read_text(encoding="utf-8"))
        xml, cs, G = self.clean(sp)
        R = rects(G)
        self.assertEqual(style(cs["shop"]).get("_base"), "ellipse")
        c = R["shop"]
        ext = [e["id"] for e in sp["elements"] if e["type"] == "external"]
        side = {i: (R[i][2] <= c[0]) - (R[i][0] >= c[2]) for i in ext}                # 1 trai, -1 phai
        self.assertEqual(set(side.values()), {1, -1})                                  # 2 cot hai ben elip
        es = edges(cs)
        self.assertEqual(len(es), len(sp["relations"]))                                # moi luong 1 mui ten
        labels = {}
        for e in es:
            self.assertIn("shop", (e.get("source"), e.get("target")))
            pts = G.edges[e.get("id")][1]
            self.assertLessEqual(len(pts), 3)                                          # toi da 1 lan gap
            for p, q in zip(pts, pts[1:]):
                self.assertTrue(abs(p[0] - q[0]) < 0.5 or abs(p[1] - q[1]) < 0.5)      # vuong goc
            ext_end = pts[0] if e.get("target") == "shop" else pts[-1]
            nxt = pts[1] if e.get("target") == "shop" else pts[-2]
            self.assertLess(abs(ext_end[1] - nxt[1]), 0.5)                             # ra ngang tu canh hop
            labels.setdefault((e.get("source"), e.get("target")), []).append(text(e))
        self.assertEqual(sorted(labels[("kh", "shop")]), sorted(["Purchase Order", "Payment Details"]))
        self.assertEqual(sorted(labels[("shop", "kh")]), sorted(["Order Confirmation", "E-Invoice"]))
        self.assertEqual(G.label_poly, {})                                             # nhan nam ngang
        self.assertAlmostEqual(c[2] - c[0], c[3] - c[1], delta=0.5)                   # hinh tron
        cx, cy, r = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2, (c[2] - c[0]) / 2
        for _, pts in G.edges.values():                                                # khong xuyen hinh tron
            for p, q in zip(pts, pts[1:]):
                for k in range(1, 20):
                    x, y = p[0] + (q[0] - p[0]) * k / 20, p[1] + (q[1] - p[1]) * k / 20
                    self.assertGreater(math.hypot(x - cx, y - cy), r - 1.0)
        self.assertTrue(any(len(p) == 3 for _, p in G.edges.values()))                 # co duong gap
        # "side" tren element ep cot
        sp2 = json.loads(json.dumps(sp))
        for el in sp2["elements"]:
            if el["id"] == "thue":
                el["side"] = "left"
        _, _, G2 = self.clean(sp2)
        self.assertLessEqual(rects(G2)["thue"][2], rects(G2)["shop"][0])

    def test_bizcontext_many_flows_compact(self):
        # hop co nhieu luong: hop cao ra, hinh tron chi nho vua du (luong du thi gap vao dinh/day), khong cat nhau
        els = [{"id": "s", "type": "system", "name": "Hệ thống"},
               {"id": "a", "type": "external", "name": "Khách hàng", "side": "left"},
               {"id": "b", "type": "external", "name": "Nhân viên", "side": "left"},
               {"id": "c", "type": "external", "name": "Ngân hàng", "side": "right"}]
        rel = [{"from": x, "to": "s", "label": "Luồng %s%d" % (x, k)} if k % 2 else
               {"from": "s", "to": x, "label": "Luồng %s%d" % (x, k)} for x in "ab" for k in range(12)]
        rel.append({"from": "c", "to": "s", "label": "Luồng c"})
        xml, cs, G = self.clean({"diagram": "bizcontext", "title": "T", "elements": els, "relations": rel})
        R = rects(G)
        self.assertGreater(R["a"][3] - R["a"][1], 12 * 18)                              # hop cao du 12 mui ten
        self.assertLess(R["s"][2] - R["s"][0], 400)                                     # hinh tron khong phinh
        segs = [(p, q) for _, pts in G.edges.values() for p, q in zip(pts, pts[1:])]
        for i, (p, q) in enumerate(segs):                                               # khong cat nhau
            for u, v in segs[i + 1:]:
                if (abs(p[0] - q[0]) < 0.5) == (abs(u[0] - v[0]) < 0.5):
                    continue
                (h1, h2), (v1, v2) = ((p, q), (u, v)) if abs(p[1] - q[1]) < 0.5 else ((u, v), (p, q))
                self.assertFalse(min(h1[0], h2[0]) + 1 < v1[0] < max(h1[0], h2[0]) - 1 and
                                 min(v1[1], v2[1]) + 1 < h1[1] < max(v1[1], v2[1]) - 1)

    def test_rotated_label_geometry(self):
        c45 = math.cos(math.radians(45))
        P = V.rot_poly(0, 0, 100, 14, c45, c45)                         # nhan 100x14 xoay 45 do
        self.assertTrue(V.poly_hit(P, [(-50, 50), (50, -50)], -2))      # doan cat ngang nhan
        self.assertFalse(V.poly_hit(P, [(30, -30), (60, -10)], -2))     # trong khung bao nhung khong cham nhan
        self.assertFalse(V.poly_hit(P, V.poly_of_rect((20, -40, 40, -20)), -1))
        self.assertTrue(V.poly_hit(P, V.poly_of_rect((20, 20, 40, 40)), -1))

# ============================================================ 5. comet_check
def stm(*rels, extra=(), initial=True):
    els = ([{"id": "i", "type": "initial"}] if initial else []) + [
        {"id": "a", "type": "state", "name": "A"}, {"id": "b", "type": "state", "name": "B"}] + list(extra)
    return {"diagram": "state", "title": "T", "stateMachineOf": "T", "elements": els,
            "relations": [dict(r, type="transition") for r in rels]}


STM_OK = ({"from": "i", "to": "a"}, {"from": "a", "to": "b", "event": "Go"}, {"from": "b", "to": "a", "event": "Back"})


def act(*rels, extra=()):
    els = [{"id": "s", "type": "initial"}, {"id": "a", "type": "action", "name": "A"},
           {"id": "b", "type": "action", "name": "B"}, {"id": "f", "type": "activityFinal"}] + list(extra)
    return {"diagram": "activity", "title": "T", "elements": els, "relations": [dict(r, type="flow") for r in rels]}


ACT_OK = ({"from": "s", "to": "a"}, {"from": "a", "to": "b"}, {"from": "b", "to": "f"})
DEC, MERGE = {"id": "d", "type": "decision"}, {"id": "m", "type": "merge"}
FORK, JOIN = {"id": "fk", "type": "fork"}, {"id": "j", "type": "join"}


class TestCometCheck(unittest.TestCase):
    def expect(self, mutate, level, code, needle=None, partial=False):
        s = shop()
        mutate(s)
        E, W, I = check(*s.values(), partial=partial)
        hits = codes({"E": E, "W": W, "I": I}[level], code)
        self.assertTrue(hits, "thieu %s %s. E=%s W=%s I=%s" % (level, code, E, W, I))
        if needle:
            self.assertTrue(any(needle in h for h in hits), hits)
        return E, W, I

    def expect_one(self, spec, level, code, needle):
        E, W, I = check(spec)
        hits = codes({"E": E, "W": W, "I": I}[level], code)
        self.assertTrue(any(needle in h for h in hits), "thieu %s %s '%s'. E=%s W=%s I=%s"
                        % (level, code, needle, E, W, I))

    def test_baseline(self):
        E, W, I = check(*shop().values())
        self.assertEqual(E, [])
        self.assertEqual(len(W), 1)
        self.assertTrue(W[0].startswith("R1 Use case 'View Order'"), W)
        E, W, I = check(*shop().values(), partial=True)
        self.assertEqual((E, W), ([], []))
        self.assertTrue(codes(I, "R1"))

    def test_R1_R7_missing_counterparts(self):
        def add_uc(s):
            s["uc"]["elements"].append({"id": "co", "type": "usecase", "name": "Cancel Order"})
        self.expect(add_uc, "W", "R1", "Cancel Order")
        self.expect(add_uc, "I", "R1", "Cancel Order", partial=True)
        self.expect(lambda s: s.pop("stm"), "W", "R7", "Order Control")
        E, W, I = self.expect(lambda s: s.pop("stm"), "I", "R7", partial=True)
        self.assertFalse(codes(W, "R7"))

    def test_R2_actor_not_in_use_case_model(self):
        self.expect(lambda s: s["comm"]["elements"].append({"id": "co", "type": "actor", "name": "Courier"}),
                    "W", "R2", "Courier")

    def test_R3_actor_talks_to_non_boundary(self):
        self.expect(lambda s: s["comm"]["messages"].append({"seq": "10", "from": "cust", "to": "ctl", "name": "Cancel"}),
                    "W", "R3", "Order Control")

    def test_R4_unknown_stereotype(self):
        self.expect(lambda s: el(s["comm"], "ui").update(stereotype="widget"), "W", "R4", "widget")

    def test_R5_entity_without_class(self):
        self.expect(lambda s: el(s["comm"], "ord").update({"class": "Invoice"}), "W", "R5", "Invoice")

    def test_R6_entity_is_passive(self):
        self.expect(lambda s: s["comm"]["messages"].append({"seq": "10", "from": "ord", "to": "ctl",
                                                              "name": "Order Created"}), "I", "R6", "Order Created")

    def test_R8_events_actions_match_messages(self):
        def rename_event(s):
            s["stm"]["relations"][1]["event"] = "Submit Order"
        E, W, I = self.expect(rename_event, "W", "R8", "'Place Order(cart)'")
        self.assertTrue(any("'submit order'" in x for x in codes(I, "R8")), I)

        def drop_action(s):
            s["stm"]["relations"][1]["action"] = ["Create Order"]
        self.expect(drop_action, "W", "R8", "'Pay'")

    def test_R8_entry_activity_and_label_forms(self):
        def entry(s):
            s["stm"]["relations"][2].pop("action")
            el(s["stm"], "idle")["activities"] = ["entry / Order Confirmed"]

        def label(s):
            for r in s["stm"]["relations"]:
                ev, a = r.pop("event", None), r.pop("action", None)
                if ev:
                    r["label"] = "%s / %s" % (ev, ", ".join(a) if isinstance(a, list) else a)
        for f in (entry, label):
            with self.subTest(form=f.__name__):
                s = shop()
                f(s)
                self.assertEqual(check(*s.values(), partial=True)[:2], ([], []))

    def test_R9_message_errors(self):
        self.expect(lambda s: s["comm"]["messages"][2].update(seq="2"), "E", "R9", "bi trung")
        self.expect(lambda s: s["comm"]["messages"][2].pop("name"), "E", "R9", "khong co ten")
        self.expect(lambda s: s["comm"]["messages"][2].update(to="ghost"), "E", "R9", "khong ton tai")

    def test_R10_entity_operations(self):
        self.expect(lambda s: el(s["cls"], "ord").update(operations=["cancel()"]), "W", "R10", "Order")

    def test_R11_context(self):
        self.expect(lambda s: s["ctx"]["elements"].append(
            {"id": "s2", "type": "system", "name": "Other", "stereotype": "software system"}), "E", "R11", "dang co 2")
        self.expect(lambda s: el(s["ctx"], "pg").update(stereotype="partner"), "W", "R11", "Payment Gateway")
        self.expect(lambda s: s["ctx"]["relations"][0].pop("label"), "I", "R11", "ten quan he")

    def test_R12_communication_vs_sequence(self):
        def drop(s):
            s["seq"]["messages"] = [m for m in s["seq"]["messages"] if m.get("name") != "Order Confirmed"]
        self.expect(drop, "W", "R12", "Order Confirmed")
        self.expect(lambda s: msg(s["seq"], "Pay").update({"from": "ui"}), "W", "R12", "khac ben gui/nhan")
        self.expect(lambda s: msg(s["seq"], "Pay").update(seq="40"), "I", "R12", "so thu tu khac nhau")

    def test_R13_boundary_without_actor(self):
        def f(s):
            s["comm"]["elements"].append({"id": "prn", "type": "object", "class": "Receipt Output",
                                          "stereotype": "output"})
            s["comm"]["messages"].append({"seq": "10", "from": "ctl", "to": "prn", "name": "Print Receipt"})
        self.expect(f, "W", "R13", "Receipt Output")

    def test_R14_actor_missing_in_context(self):
        def f(s):
            s["uc"]["elements"].append({"id": "aud", "type": "actor", "name": "Auditor"})
            s["uc"]["relations"].append({"type": "association", "from": "aud", "to": "vo"})
        self.expect(f, "I", "R14", "Auditor")

    def test_X1_cross_usecase_reference(self):
        def f(s):
            s["comm"]["useCase"] = "Ghost Use Case"
        self.expect(f, "W", "X1", "Ghost Use Case")

    def test_X2_actor_participation(self):
        def f(s):
            s["uc"]["elements"].append({"id": "aud", "type": "actor", "name": "Auditor"})
            s["uc"]["relations"].append({"type": "association", "from": "aud", "to": "po"})
        self.expect(f, "W", "X2", "Auditor")

    def test_X2_interaction_without_actor_lifeline(self):
        def f(s):
            for k in ("comm", "seq"):
                for e in s[k]["elements"]:
                    if e.get("type") == "actor":
                        e.update(type="object", **{"class": e.pop("name")})
        self.expect(f, "W", "X2", "Customer")

    def test_X3_statechart_reverse_traceability(self):
        s = shop()
        el(s["comm"], "ctl")["stereotype"] = "control"
        el(s["seq"], "ctl")["stereotype"] = "control"
        E, W, I = check(*s.values())
        self.assertTrue(codes(W, "X3"), "thieu X3. E=%s W=%s I=%s" % (E, W, I))

    def test_X4_erd_entity_class_traceability(self):
        s = shop()
        erd = {"diagram": "erd", "title": "Shop - ERD", "elements": [
            {"id": "ord", "type": "entity", "name": "Order"},
            {"id": "inv", "type": "entity", "name": "Invoice"},
        ], "relations": []}
        E, W, I = check(*s.values(), erd)
        self.assertTrue(codes(W, "X4"), "thieu X4. E=%s W=%s I=%s" % (E, W, I))

    def test_X5_component_deployment_traceability(self):
        comp = {"diagram": "component", "title": "Shop - Components", "system": "Shop", "bundle": "shop-bundle",
                "elements": [{"id": "svc", "type": "component", "name": "Order Service"},
                             {"id": "pay", "type": "component", "name": "Payment Service"},
                             {"id": "dao", "type": "component", "name": "Order DAO", "in": "svc"}],
                "relations": []}
        dep = {"diagram": "deployment", "title": "Shop - Deployment", "system": "Different Metadata Name", "bundle": "shop-bundle",
               "elements": [{"id": "srv", "type": "node", "name": "Server"},
                             {"id": "svc", "type": "component", "name": "Order Service"},
                             {"id": "ghost", "type": "component", "name": "Ghost Service"}],
               "relations": []}
        E, W, I = check(comp, dep)
        self.assertTrue(codes(W, "X5"), "thieu X5. E=%s W=%s I=%s" % (E, W, I))
        self.assertFalse(any("Order DAO" in x for x in W + I), "component con khong nen bi bat X5: %s %s" % (W, I))

    def test_X6_role_collision(self):
        s = shop()
        el(s["comm"], "ord")["stereotype"] = "control"
        E, W, I = check(*s.values())
        self.assertTrue(codes(W, "X6"), "thieu X6. E=%s W=%s I=%s" % (E, W, I))

    def test_bundle_isolation(self):
        # Cùng tên use case nhưng khác bundle không được trộn coverage/actors.
        a = shop()
        for sp in a.values():
            sp["bundle"] = "shop-a"

        b_uc = copy.deepcopy(SHOP_UC)
        b_uc["bundle"] = "shop-b"
        b_uc["elements"].append({"id": "aud2", "type": "actor", "name": "Auditor"})
        b_uc["relations"].append({"type": "association", "from": "aud2", "to": "po"})
        E, W, I = check(a["uc"], a["comm"], a["seq"], b_uc)
        self.assertTrue(codes(W, "R1"), "bundle-b phai tu kiem R1 rieng: %s" % W)

        b_comm = copy.deepcopy(SHOP_COMM)
        b_comm["bundle"] = "shop-b"
        b_seq = copy.deepcopy(SHOP_SEQ)
        b_seq["bundle"] = "shop-b"
        E, W, I = check(a["uc"], a["comm"], a["seq"], b_uc, b_comm, b_seq)
        self.assertTrue(codes(W, "X2"), "bundle-b phai tu kiem actor rieng: %s" % W)
        self.assertFalse(any("shop-a" in x and "X2" in x for x in W), "khong duoc trộn bundle: %s" % W)

        # X1 không được "mượn" use case trùng tên ở bundle khác.
        ghost = copy.deepcopy(SHOP_COMM)
        ghost["bundle"] = "shop-c"
        E, W, I = check(a["uc"], a["comm"], a["seq"], ghost)
        self.assertTrue(codes(W, "X1"), "tham chieu use case sang bundle khac phai bi bat: %s" % W)

        # X3 không được "mượn" control từ bundle khác.
        st = {
            "diagram": "state", "title": "Order Control - State", "stateMachineOf": "Order Control",
            "bundle": "shop-c",
            "elements": [{"id": "i", "type": "initial"}, {"id": "a", "type": "state", "name": "Idle"}],
            "relations": [{"from": "i", "to": "a"}],
        }
        E, W, I = check(a["uc"], a["comm"], a["seq"], st)
        self.assertTrue(codes(W, "X3"), "statechart phai trace control cung bundle: %s" % W)

        # R12 không được so sánh communication/sequence ở hai bundle khác nhau.
        c2 = copy.deepcopy(SHOP_COMM)
        q2 = copy.deepcopy(SHOP_SEQ)
        c2["bundle"], q2["bundle"] = "shop-b", "shop-c"
        c2["messages"] = c2["messages"][:-1]
        E, W, I = check(c2, q2)
        self.assertFalse(codes(W, "R12"), "R12 khong duoc tron bundle: %s" % W)

        # X6 role collision cũng chỉ có ý nghĩa trong cùng bundle.
        role_cls = copy.deepcopy(SHOP_CLS)
        role_cls["bundle"] = "shop-c"
        role_comm = copy.deepcopy(SHOP_COMM)
        role_comm["bundle"] = "shop-b"
        el(role_comm, "ord")["stereotype"] = "control"
        E, W, I = check(role_cls, role_comm)
        self.assertFalse(codes(W, "X6"), "X6 khong duoc tron role khac bundle: %s" % W)

    def test_R8_messages_show_class_name_not_scope_tuple(self):
        E, W, I = C.check(C.load([str(p) for p in EXAMPLES.glob("atm_*.json")]))
        r8 = [x for x in W + I if x.startswith("R8")]
        self.assertTrue(r8)
        self.assertFalse(any("__default__" in x or "('" in x for x in r8), r8)
        # Ten goc nhu tac gia viet, khong phai khoa da chuan hoa 'atm control'.
        self.assertTrue(all("'ATM Control'" in x for x in r8), r8)

    def test_X1_X3_partial_bundle_without_model_is_info(self):
        a = shop()
        for sp in a.values():
            sp["bundle"] = "shop-a"
        ghost = copy.deepcopy(SHOP_COMM)
        ghost["bundle"] = "shop-c"
        ghost["useCase"] = "Ship Order"
        st = {"diagram": "state", "title": "Ship Control", "stateMachineOf": "Ship Control", "bundle": "shop-c",
              "elements": [{"id": "i", "type": "initial"}, {"id": "a", "type": "state", "name": "Idle"}],
              "relations": [{"from": "i", "to": "a"}]}
        E, W, I = check(a["uc"], a["comm"], a["seq"], ghost, st, partial=True)
        self.assertFalse(codes(W, "X1") or codes(W, "X3"), "bundle chua co model -> chi INFO khi --partial: %s" % W)
        self.assertTrue(codes(I, "X1") and codes(I, "X3"), I)
        # Bundle co use case model nhung khong co ten nay -> van la tham chieu treo (WARN) ca khi --partial.
        dangling = copy.deepcopy(a["comm"])
        dangling["useCase"] = "Ghost Use Case"
        E, W, I = check(a["uc"], a["comm"], a["seq"], dangling, partial=True)
        self.assertTrue(codes(W, "X1"), W)

    def test_X4_X5_scope_ignores_system_field_and_notes_unmatched_pair(self):
        erd = {"diagram": "erd", "title": "Shop - ERD", "elements": [
            {"id": "ord", "type": "entity", "name": "Order"}, {"id": "inv", "type": "entity", "name": "Invoice"}]}
        cls = copy.deepcopy(SHOP_CLS)
        cls["system"] = "Shop System"   # ten he thong, khong phai namespace -> khong duoc tat X4
        E, W, I = check(erd, cls)
        self.assertTrue(codes(W, "X4"), "system khong phai scope key: W=%s I=%s" % (W, I))
        # Cap duy nhat, khong bundle, title khac, khong chung ten -> ghi chu thay vi im lang.
        other = {"diagram": "erd", "title": "Warehouse ERD", "elements": [
            {"id": "b", "type": "entity", "name": "Bin"}]}
        E, W, I = check(other, copy.deepcopy(SHOP_CLS))
        self.assertFalse(codes(W, "X4"), W)
        self.assertTrue(any(x.startswith("X4") and "bundle" in x for x in I), I)

    def test_semantic_model(self):
        specs = C.load([str(EXAMPLES / "atm_usecase.json"),
                        str(EXAMPLES / "atm_context.json"),
                        str(EXAMPLES / "atm_comm_validate_pin.json"),
                        str(EXAMPLES / "atm_seq_validate_pin.json"),
                        str(EXAMPLES / "atm_statechart.json"),
                        str(EXAMPLES / "atm_entity.json"),
                        str(EXAMPLES / "banking_component.json"),
                        str(EXAMPLES / "atm_deployment.json")])
        for sp in specs:
            sp["bundle"] = "atm-banking"
        model = M.build_model(specs)
        self.assertEqual(model["schemaVersion"], 2)
        self.assertEqual(model["kind"], "comet-semantic-model")
        self.assertEqual(model["stats"]["bundles"], 1)
        names = {n["name"] for n in model["nodes"].values()}
        for expected in ("Validate PIN", "ATM Customer", "ATM Control", "Banking System"):
            self.assertIn(expected, names)
        kinds = {n["kind"] for n in model["nodes"].values()}
        self.assertIn("usecase", kinds)
        self.assertIn("control", kinds)
        self.assertIn("entity", kinds)
        self.assertTrue(model["fingerprint"])
        plan_specs = copy.deepcopy(specs)
        plan_specs[2]["elements"][1]["stereotype"] = "invalid stereotype"
        plan = CP.build_plan(plan_specs)
        self.assertEqual(plan["kind"], "comet-repair-plan")
        self.assertGreaterEqual(plan["summary"]["warnings"], 1)
        self.assertTrue(any(x["rule"] == "R4" for x in plan["steps"]))
        self.assertTrue(any(x["action"] for x in plan["steps"]))
        borrow = next(v for v in model["coverage"]["atm-banking"]["useCases"].values()
                      if v["name"] == "Validate PIN")
        self.assertTrue(borrow["interactionSources"])
        ctl = next(n for n in model["nodes"].values() if n["name"] == "ATM Control" and n["kind"] == "control")
        self.assertIn("communication", ctl["diagramKinds"])
        self.assertIn("state", ctl["diagramKinds"])
        self.assertIn("impactMap", model)
        self.assertTrue(model["impactMap"][ctl["id"]]["relatedLinkIds"])
        alias_links = [x for x in model["links"].values() if x["kind"] == "actor-external-alias"]
        self.assertTrue(any(x["semanticIdentity"] == "atm customer" for x in alias_links))

    def test_json_report(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            warn = copy.deepcopy(SHOP_COMM)
            warn["elements"][1]["stereotype"] = "invalid stereotype"
            (d / "warn.json").write_text(json.dumps(warn), encoding="utf-8")
            r = run("comet_check.py", "--json", d / "warn.json")
            self.assertEqual(r.returncode, 0, r.stdout)
            payload = json.loads(r.stdout)
            self.assertIn("summary", payload)
            self.assertGreaterEqual(payload["summary"]["warnings"], 1)
            self.assertTrue(any("R4" in x for x in payload["warnings"]))
            self.assertEqual(payload["model"]["kind"], "comet-semantic-model")
            self.assertIn("fingerprint", payload["model"])

    def test_statechart_rules(self):
        self.assertEqual(check(stm(*STM_OK)), ([], [], []))
        self.expect_one(stm({"from": "i", "to": "a", "event": "Go"}, *STM_OK[1:]), "E", "S1", "event 'go'")
        self.expect_one(stm({"from": "i", "to": "a", "guard": "ready"}, *STM_OK[1:]), "E", "S1", "guard [ready]")
        self.expect_one(stm(*STM_OK, {"from": "b", "to": "i", "event": "Reset"}), "E", "S1", "transition vao")
        self.expect_one(stm(*STM_OK, extra=[{"id": "i2", "type": "initial"}]), "E", "S1", "co 2 initial")
        self.expect_one(stm(*STM_OK[1:], initial=False), "W", "S1", "chua co initial")
        fin = [{"id": "f", "type": "final"}]
        self.expect_one(stm(*STM_OK, {"from": "b", "to": "f", "event": "End"}, {"from": "f", "to": "a", "event": "X"},
                            extra=fin), "E", "S2", "Final state")
        ch = [{"id": "c", "type": "choice"}]
        base = (STM_OK[0], {"from": "a", "to": "c", "event": "Check"}, {"from": "b", "to": "a", "event": "Back"})
        self.expect_one(stm(*base, {"from": "c", "to": "b", "guard": "ok"}, {"from": "c", "to": "a"}, extra=ch),
                        "W", "S3", "thieu guard")
        self.expect_one(stm(*base, {"from": "c", "to": "b", "guard": "else"}, {"from": "c", "to": "a", "guard": "else"},
                            extra=ch), "W", "S3", "nhieu hon 1")
        self.expect_one(stm(*STM_OK, {"from": "z", "to": "a", "event": "X"},
                            extra=[{"id": "z", "type": "state", "name": "Z"}]), "W", "S4", "'Z' khong co transition vao")
        self.expect_one(stm(*STM_OK, {"from": "a", "to": "d", "event": "Die"},
                            extra=[{"id": "d", "type": "state", "name": "D"}]), "I", "S4", "'D' khong co transition ra")
        self.expect_one(stm(*STM_OK, {"from": "a", "to": "a", "event": "Go"}), "W", "S5", "khong tat dinh")
        # hop le: guard phan biet, self-transition, composite state co initial rieng
        ok = stm(STM_OK[0], {"from": "a", "to": "b", "event": "Go", "guard": "x > 0"},
                 {"from": "a", "to": "a", "event": "Go", "guard": "x <= 0"}, STM_OK[2],
                 {"from": "b", "to": "c", "event": "Enter"}, {"from": "ci", "to": "c1"},
                 {"from": "c", "to": "a", "event": "Leave"},
                 extra=[{"id": "c", "type": "state", "name": "C"}, {"id": "ci", "type": "initial", "in": "c"},
                        {"id": "c1", "type": "state", "name": "C1", "in": "c"}])
        self.assertEqual(check(ok), ([], [], []))

    def test_activity_rules(self):
        self.assertEqual(check(act(*ACT_OK)), ([], [], []))
        dec = ({"from": "s", "to": "a"}, {"from": "a", "to": "d"}, {"from": "b", "to": "f"})
        self.expect_one(act(*dec, {"from": "d", "to": "b", "guard": "ok"}, {"from": "d", "to": "f"}, extra=[DEC]),
                        "W", "A1", "thieu guard")
        self.expect_one(act(*dec, {"from": "d", "to": "b", "guard": "else"}, {"from": "d", "to": "f", "guard": "else"},
                            extra=[DEC]), "W", "A1", "nhieu hon 1")
        self.expect_one(act({"from": "s", "to": "fk"}, {"from": "fk", "to": "a"}, *ACT_OK[1:], extra=[FORK]),
                        "W", "A2", "Fork")
        self.expect_one(act(ACT_OK[0], {"from": "a", "to": "j"}, {"from": "j", "to": "b"}, ACT_OK[2], extra=[JOIN]),
                        "W", "A2", "Join")
        self.expect_one(act(*ACT_OK, {"from": "b", "to": "s"}), "E", "A3", "khong duoc co luong vao")
        self.expect_one(act(*ACT_OK, {"from": "f", "to": "a"}), "E", "A3", "Final node")
        self.expect_one(act({"from": "s", "to": "a"}, {"from": "s", "to": "b"}, {"from": "a", "to": "f"},
                            {"from": "b", "to": "f"}), "W", "A3", "dung 1 luong ra")
        self.expect_one(act(ACT_OK[0], {"from": "a", "to": "m"}, {"from": "m", "to": "b"}, {"from": "m", "to": "f"},
                            ACT_OK[2], extra=[MERGE]), "W", "A4", "Merge")
        self.expect_one(act({"from": "s", "to": "fk"}, {"from": "fk", "to": "a"}, {"from": "fk", "to": "b"},
                            {"from": "a", "to": "d"}, {"from": "b", "to": "d"}, {"from": "d", "to": "f"},
                            extra=[FORK, DEC]), "I", "A4", "day la merge")
        self.expect_one(act({"from": "s", "to": "a"}, {"from": "a", "to": "f"}), "W", "A5", "'B' khong co luong ra")
        self.expect_one(act({"from": "s", "to": "a"}, {"from": "a", "to": "f"}), "I", "A5", "'B' khong co luong vao")
        self.expect_one(act({"from": "s", "to": "d"}, {"from": "d", "to": "a", "guard": "x"},
                            {"from": "d", "to": "b", "guard": "y"}, {"from": "a", "to": "b"}, ACT_OK[2], extra=[DEC]),
                        "W", "A6", "join ngam")
        self.expect_one(act(*ACT_OK, {"from": "a", "to": "f"}), "W", "A6", "fork ngam")

    def test_lang_default_english(self):
        sp = {"diagram": "activity", "title": "Rút tiền", "elements": [
            {"id": "s", "type": "initial"}, {"id": "d", "type": "decision", "question": "Đủ số dư?"},
            {"id": "a", "type": "action", "name": "Dispense Cash"}, {"id": "f", "type": "activityFinal"}],
            "relations": [{"from": "s", "to": "d"}, {"from": "d", "to": "a", "guard": "Có"},
                          {"from": "d", "to": "f", "guard": "else"}, {"from": "a", "to": "f"}]}
        self.expect_one(sp, "W", "L1", "3 chuoi co dau")
        self.assertIn("'Rút tiền'", codes(check(sp)[1], "L1")[0])
        sp["lang"] = "vi"                                                               # yeu cau ro -> het L1
        self.assertEqual(codes(check(sp)[1], "L1"), [])
        en = {"diagram": "class", "title": "Order «entity» – Model", "elements": [   # «», – khong tinh la chu co dau
            {"id": "c", "type": "class", "name": "Order", "attributes": ["id: String"]}], "relations": []}
        self.assertEqual(codes(check(en)[1], "L1"), [])

    def test_erd_screenflow_bizcontext_rules(self):
        for f in ("elearn_erd", "lms_screenflow_sitemap", "shop_bizcontext"):
            sp = json.loads((EXAMPLES / (f + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(check(sp), ([], [], []), f)
        erd = {"diagram": "erd", "title": "E", "elements": [
            {"id": "a", "type": "entity", "name": "A"}, {"id": "b", "type": "entity", "name": "B"},
            {"id": "r", "type": "relationship"}], "relations": [
            {"from": "a", "to": "b", "fromCard": "M", "toCard": "N", "name": "r"},
            {"from": "a", "to": "b", "fromCard": "1", "name": "x"}, {"from": "a", "to": "zz", "fromCard": "1", "toCard": "1"},
            {"from": "a", "to": "b", "fromCard": "1", "toCard": "N"},
            {"from": "a", "to": "r", "card": "1"}, {"from": "r", "to": "b"}]}
        self.expect_one(erd, "E", "E1", "khong ton tai")
        self.expect_one(erd, "W", "E2", "o dau 'B'")
        self.expect_one(erd, "W", "E2", "hinh thoi 'r' thieu ban so")
        self.expect_one(erd, "W", "E3", "'A' - 'B' chua co ten")
        self.expect_one(erd, "W", "E3", "Hinh thoi quan he 'r' chua co ten")
        self.assertEqual(check(erd)[2], [])                                            # nhieu-nhieu hop le
        sf = {"diagram": "screenflow", "title": "S", "elements": [
            {"id": "s", "type": "initial"}, {"id": "a", "type": "screen", "name": "A"},
            {"id": "b", "type": "screen", "name": "B"}, {"id": "c", "type": "dialog", "name": "C"}], "relations": [
            {"from": "s", "to": "a"}, {"from": "a", "to": "c"}, {"from": "b", "to": "a", "trigger": "x"}]}
        self.expect_one(sf, "W", "F1", "'B' khong toi duoc")
        self.expect_one(sf, "W", "F2", "'B' -> 'A' co nhan")
        self.expect_one(sf, "W", "F2", "nut initial")
        bz = {"diagram": "bizcontext", "title": "B", "elements": [
            {"id": "s", "type": "system", "name": "S"}, {"id": "x", "type": "external", "name": "X"},
            {"id": "y", "type": "external", "name": "Y"}, {"id": "z", "type": "external", "name": "Z"}], "relations": [
            {"from": "x", "to": "s"}, {"from": "x", "to": "y", "label": "d"}]}
        self.expect_one(bz, "W", "B2", "chua co ten")
        self.expect_one(bz, "W", "B2", "khong di qua")
        self.expect_one(bz, "W", "B3", "'Z'")
        bz["elements"].append({"id": "t", "type": "system", "name": "T"})
        self.expect_one(bz, "E", "B1", "dang co 2")

    def test_class_rules(self):
        base = {"diagram": "class", "title": "T", "elements": [
            {"id": "a", "type": "class", "name": "A", "attributes": ["x: Integer"]},
            {"id": "b", "type": "class", "name": "B", "attributes": ["y: String"]},
            {"id": "k", "type": "enumeration", "name": "K", "literals": ["ONE"]}], "relations": [
            {"type": "association", "from": "a", "to": "b", "label": "Has", "fromMult": "1", "toMult": "*"}]}
        self.assertEqual(check(base), ([], [], []))
        s = copy.deepcopy(base)
        s["elements"][0]["attributes"] = ["x"]
        self.expect_one(s, "W", "C1", "'x'")
        s = copy.deepcopy(base)
        del s["relations"][0]["toMult"]
        self.expect_one(s, "W", "C2", "dau 'B'")
        s = copy.deepcopy(base)
        del s["relations"][0]["label"]
        self.expect_one(s, "I", "C2", "chua co ten")

    def test_name_matching_helpers(self):
        self.assertEqual(C.mname("Place Order(cart, qty)"), "place order")
        self.assertEqual(C.mname("  PIN   Entered "), "pin entered")
        self.assertEqual(C.parse_label("Card Inserted [valid] / Get PIN, Beep(x)"), ("card inserted", ["get pin", "beep"]))
        self.assertEqual(C.trans_parts({"label": "Ev [ok] / a; b"}), ("ev", "ok", ["a", "b"]))
        self.assertEqual(C.guard_of({"guard": "[else]"}), "else")
        self.assertEqual(C.st_of({"stereotype": ["«Entity»", "x"]}), "entity")
        self.assertEqual(sorted(C.lifelines({"diagram": "sequence", "elements": [],
                                             "messages": [{"from": "a", "to": "b"}]})), ["a", "b"])




class TestSemanticModelV2(unittest.TestCase):
    @staticmethod
    def specs():
        return [
            {
                "diagram": "usecase",
                "bundle": "shop-v2",
                "_src": "usecase.json",
                "elements": [
                    {"id": "customer", "type": "actor", "name": "Client", "conceptId": "customer.party"},
                    {"id": "place", "type": "usecase", "name": "Place Order"},
                ],
                "relations": [{"from": "customer", "to": "place", "type": "association"}],
            },
            {
                "diagram": "context",
                "bundle": "shop-v2",
                "_src": "context.json",
                "elements": [
                    {"id": "shop", "type": "system", "name": "Shop System", "stereotype": "software system"},
                    {"id": "customer", "type": "external", "name": "Customer",
                     "conceptId": "customer.party", "aliases": ["Buyer"]},
                ],
                "relations": [{"from": "shop", "to": "customer", "label": "orders"}],
            },
            {
                "diagram": "class",
                "bundle": "shop-v2",
                "_src": "class.json",
                "elements": [
                    {"id": "customer", "type": "class", "name": "Customer",
                     "conceptId": "customer.party", "stereotype": "entity", "attributes": ["id: String"]},
                    {"id": "order", "type": "class", "name": "Order",
                     "stereotype": "entity", "attributes": ["id: String"]},
                ],
                "relations": [{"from": "customer", "to": "order", "type": "association", "label": "places",
                               "fromMult": "1", "toMult": "*"}],
            },
            {
                "diagram": "communication",
                "bundle": "shop-v2",
                "_src": "communication.json",
                "useCase": "Place Order",
                "elements": [
                    {"id": "actor", "type": "actor", "name": "Client", "conceptId": "customer.party"},
                    {"id": "control", "type": "object", "class": "Order Control", "stereotype": "control"},
                    {"id": "order", "type": "object", "class": "Order", "conceptId": "order.entity",
                     "stereotype": "entity"},
                ],
                "messages": [
                    {"from": "actor", "to": "control", "name": "placeOrder", "seq": "1"},
                    {"from": "control", "to": "order", "name": "saveOrder", "seq": "2"},
                ],
            },
        ]

    def test_canonical_identity_aliases_and_provenance(self):
        model = M.build_model(copy.deepcopy(self.specs()))
        customer = next(c for c in model["concepts"].values() if c["id"].endswith(
            M.canonical_concept_id("shop-v2", "id:customer.party").split(":")[-1]))
        self.assertEqual(customer["kind"], "canonical-concept")
        self.assertIn("entity", customer["semanticKinds"])
        self.assertIn("party", customer["semanticKinds"])
        self.assertIn("Customer", customer["aliases"])
        self.assertGreaterEqual(len(customer["representations"]), 3)
        self.assertTrue(all("source" in p and "diagram" in p for p in customer["provenance"]))

    def test_bundle_isolation_and_deterministic_fingerprint(self):
        specs = self.specs()
        first = M.build_model(copy.deepcopy(specs))
        second = M.build_model(list(reversed(copy.deepcopy(specs))))
        self.assertEqual(first["fingerprint"], second["fingerprint"])

        isolated = copy.deepcopy(specs[0])
        isolated["bundle"] = "other-system"
        other = M.build_model(specs + [isolated])
        shop_id = M.canonical_concept_id("shop-v2", "id:customer.party")
        other_id = M.canonical_concept_id("other-system", "id:customer.party")
        self.assertIn(shop_id, other["concepts"])
        self.assertIn(other_id, other["concepts"])
        self.assertNotEqual(shop_id, other_id)

    def test_dependency_impact_propagation(self):
        model = M.build_model(copy.deepcopy(self.specs()))
        customer = next(c for c in model["concepts"].values() if c["nameKey"] == "client")
        order = next(c for c in model["concepts"].values() if c["nameKey"] == "order")
        impact = model["conceptImpactMap"][customer["id"]]
        self.assertIn(order["id"], impact["impactedConceptIds"])
        self.assertIn("class", impact["impactedDiagramKinds"])
        self.assertIn("class.json", impact["impactedSources"])
        self.assertTrue(model["dependencyGraph"]["edges"])

    def test_v1_backward_compatibility(self):
        v1 = M.build_model_v1(copy.deepcopy(self.specs()))
        self.assertEqual(v1["schemaVersion"], 1)
        v2 = M.upgrade_v1_model(v1)
        self.assertEqual(v2["schemaVersion"], 2)
        self.assertEqual(v2["nodes"], v1["nodes"])
        self.assertEqual(v2["links"], v1["links"])

        legacy = M.model_for_schema(M.build_model(copy.deepcopy(self.specs())), 1)
        self.assertEqual(legacy["schemaVersion"], 1)
        self.assertIn("nodes", legacy)
        self.assertNotIn("concepts", legacy)
        self.assertNotIn("sourceOfTruth", legacy)
        self.assertNotIn("conceptImpactMap", legacy)
        legacy_again = M.model_for_schema(M.build_model(copy.deepcopy(self.specs())), 1)
        self.assertEqual(legacy["fingerprint"], legacy_again["fingerprint"])

    def test_repair_plan_carries_canonical_impact(self):
        specs = self.specs()
        bad = copy.deepcopy(specs[-1])
        bad["elements"][1]["stereotype"] = "invalid stereotype"
        plan = CP.build_plan(specs[:-1] + [bad])
        self.assertTrue(plan["steps"])
        self.assertTrue(any(step["affectedConceptIds"] for step in plan["steps"]))

    def test_authoritative_reconcile_detects_drift(self):
        specs = self.specs()
        canonical = M.build_model(copy.deepcopy(specs))
        changed = copy.deepcopy(canonical)
        customer = next(c for c in changed["concepts"].values() if c["nameKey"] == "client")
        customer["name"] = "Buyer"
        customer["nameKey"] = "buyer"
        result = CR.reconcile(changed, M.build_model(copy.deepcopy(specs)))
        self.assertEqual(result["status"], "drift")
        self.assertTrue(any(x["rule"] == "M3" for x in result["drift"]))

    def test_reconcile_missing_alias_is_M6_warning(self):
        specs = self.specs()
        canonical = M.build_model(copy.deepcopy(specs))
        next(iter(canonical["concepts"].values()))["aliases"].append("Declared Alias")
        result = CR.reconcile(canonical, M.build_model(copy.deepcopy(specs)))
        self.assertEqual([(x["rule"], x["severity"]) for x in result["drift"]], [("M6", "warning")])
        self.assertEqual(result["summary"]["errors"], 0)

    def atm_specs(self):
        return C.load([str(p) for p in sorted(EXAMPLES.glob("atm_*.json"))])

    def test_representation_ids_ignore_element_order(self):
        specs = self.atm_specs()
        shuffled = copy.deepcopy(specs)
        for s in shuffled:
            s["elements"] = list(reversed(s.get("elements", [])))
        a, b = M.build_model(specs), M.build_model(shuffled)
        self.assertEqual(sorted(a["representations"]), sorted(b["representations"]))
        self.assertEqual(a["fingerprint"], b["fingerprint"])

    def test_default_bundle_has_one_concept_per_name_and_no_object_nodes(self):
        model = M.build_model(self.atm_specs())
        names = [c["nameKey"] for c in model["concepts"].values()]
        self.assertEqual(len(names), len(set(names)), "concept trung ten trong bundle mac dinh")
        self.assertFalse([n for n in model["nodes"].values() if n["kind"] == "object"])
        ctl = next(n["id"] for n in model["nodes"].values() if n["kind"] == "control" and n["nameKey"] == "atm control")
        self.assertTrue(any(l["kind"] == "message" and ctl in (l["source"], l["target"]) for l in model["links"].values()))

    def test_repair_plan_targets_named_concept(self):
        specs = self.atm_specs()
        model = M.build_model(specs)
        plan = CP.build_plan(specs, model=model)
        names = lambda step: {model["concepts"][c]["name"] for c in step["affectedConceptIds"]}
        r8 = [s for s in plan["steps"] if s["rule"] == "R8"]
        self.assertTrue(r8)
        self.assertTrue(all(names(s) == {"ATM Control"} for s in r8), [names(s) for s in r8])
        query = next(s for s in plan["steps"] if s["rule"] == "R1" and "Query Account" in s["message"])
        self.assertEqual(names(query), {"Query Account"})
        self.assertTrue(all("directlyImpactedConceptIds" in s for s in plan["steps"]))

    def test_manifest_builds_model_once(self):
        calls = []
        real = CM.build_model

        def counting(*a, **k):
            calls.append(1)
            return real(*a, **k)
        CM.build_model, CP.build_model = counting, counting
        try:
            CM.build_manifests(self.atm_specs())
        finally:
            CM.build_model, CP.build_model = real, real
        self.assertEqual(len(calls), 1)

    def test_activity_coverage_default_bundle(self):
        specs = C.load([str(EXAMPLES / "atm_usecase.json"), str(EXAMPLES / "atm_activity_withdraw.json")])
        model = M.build_model(specs, schema_version=1)
        withdraw = next(u for u in model["coverage"]["default"]["useCases"].values() if u["name"] == "Withdraw Funds")
        self.assertTrue(any("atm_activity_withdraw.json" in s for s in withdraw["activitySources"]), withdraw)

    def test_manifest_binds_authoritative_fingerprint(self):
        specs = self.specs()
        canonical = M.build_model(copy.deepcopy(specs))
        model, consistency, repair = CM.build_manifests(copy.deepcopy(specs), canonical_model=canonical)
        self.assertEqual(model["fingerprint"], canonical["fingerprint"])
        self.assertEqual(consistency["modelFingerprint"], canonical["fingerprint"])
        self.assertEqual(repair["modelFingerprint"], canonical["fingerprint"])
        self.assertTrue(consistency["canonicalSourceOfTruth"])



# ============================================================ 6. dong lenh
class TestCanonicalProjection(TmpMixin, unittest.TestCase):
    """comet_project: file canonical -> spec (canonical-first) va bootstrap nguoc lai."""

    @staticmethod
    def examples():
        return C.load([str(p) for p in EXAMPLE_FILES])

    def doc(self):
        return PJ.bootstrap_canonical(self.examples())

    @staticmethod
    def by_diagram(specs, diagram):
        return [s for s in specs if s["diagram"] == diagram]

    def test_bootstrap_roundtrip_all_examples(self):
        specs = self.examples()
        doc = PJ.bootstrap_canonical(specs)
        self.assertEqual(PJ.validate_canonical(doc), [])
        self.assertEqual(PJ.verify_roundtrip(specs, doc), [])
        compiled = PJ.compile_projections(doc)
        self.assertEqual(len(compiled), len(EXAMPLE_FILES))
        # conceptId chi phat cho concept, khong cho phan tu hanh vi cuc bo.
        act = self.by_diagram(compiled, "activity")[0]
        self.assertFalse(any("conceptId" in e for e in act["elements"]))
        self.assertIn("useCaseConceptId", act)

    def test_compiled_specs_have_check_and_semantic_parity(self):
        compiled = PJ.compile_projections(self.doc(), base=str(EXAMPLES))
        self.assertEqual(C.check(compiled), C.check(self.examples()))
        model = M.build_model(compiled)
        self.assertEqual(model["fingerprint"], M.build_model(self.examples())["fingerprint"])
        self.assertEqual([c for c in model["constraints"] if c["kind"] == "identity-ambiguity"], [])

    def test_bootstrap_roundtrip_fuzz_specs(self):
        # Nhieu class diagram chung ten lop nhung khac attributes/stereotype -> override/omit theo view.
        specs = [dict(GENERATORS["class"](seed), _src="class%02d.json" % seed) for seed in range(FUZZ_SEEDS)]
        specs += [dict(GENERATORS[k](seed), _src="%s%02d.json" % (k, seed))
                  for k in ("activity", "state") for seed in range(FUZZ_SEEDS)]
        doc = PJ.bootstrap_canonical(copy.deepcopy(specs))
        self.assertEqual(PJ.verify_roundtrip(specs, doc), [])

    def test_bootstrap_deterministic_and_order_independent(self):
        a = PJ.bootstrap_canonical(self.examples())
        b = PJ.bootstrap_canonical(list(reversed(self.examples())))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(PJ.canonical_semantic_model(a)["fingerprint"], PJ.canonical_semantic_model(b)["fingerprint"])

    def test_comm_and_seq_share_one_interaction(self):
        doc = self.doc()
        views = [v for v in doc["views"] if v["diagram"] in ("communication", "sequence")]
        self.assertEqual({v["interaction"] for v in views}, {"validate-pin"})
        comm = next(v for v in views if v["diagram"] == "communication")
        self.assertEqual(comm["messageOmit"], ["id", "type"])
        doc["interactions"]["validate-pin"]["messages"][0]["name"] = "Insert Card"
        compiled = PJ.compile_projections(doc)
        first = [s["messages"][0]["name"] for s in compiled if s["diagram"] in ("communication", "sequence")]
        self.assertEqual(first, ["Insert Card", "Insert Card"])
        self.assertNotIn("R12", codes(C.check(compiled)[1]))

    def test_rename_concept_propagates_everywhere(self):
        doc = self.doc()
        doc["concepts"]["atm-customer"]["name"] = "Bank Customer"
        compiled = PJ.compile_projections(doc)
        self.assertNotIn("ATM Customer", json.dumps(compiled, ensure_ascii=False))
        for diagram in ("usecase", "communication", "sequence", "context"):
            names = {e.get("name") for s in self.by_diagram(compiled, diagram) for e in s["elements"]}
            self.assertIn("Bank Customer", names, diagram)
        act = self.by_diagram(compiled, "activity")[0]
        self.assertIn("Bank Customer", act["partitions"])
        self.assertEqual(act["elements"][0]["partition"], "Bank Customer")
        base = C.check(PJ.compile_projections(self.doc()))
        self.assertEqual([len(x) for x in C.check(compiled)], [len(x) for x in base])
        # Identity semantic on dinh: cung concept id, khong co concept "ma" theo ten moi.
        after = M.build_model(compiled)
        self.assertEqual(set(PJ.canonical_semantic_model(self.doc())["concepts"]), set(after["concepts"]))
        self.assertEqual([c for c in after["constraints"] if c["kind"] == "identity-ambiguity"], [])

    def test_rename_use_case_keeps_anchor_identity(self):
        doc = self.doc()
        key = next(k for k, c in doc["concepts"].items() if c["name"] == "Validate PIN")
        doc["concepts"][key]["name"] = "Verify PIN"
        compiled = PJ.compile_projections(doc)
        comm = self.by_diagram(compiled, "communication")[0]
        self.assertEqual((comm["useCase"], comm["title"]), ("Verify PIN", "Verify PIN"))
        self.assertEqual(C.check(compiled)[1], [w.replace("Validate PIN", "Verify PIN")
                                                 for w in C.check(PJ.compile_projections(self.doc()))[1]])
        model = M.build_model(compiled)
        self.assertEqual([c for c in model["constraints"] if c["kind"] == "identity-ambiguity"], [])

    def test_new_use_case_auto_included_without_invented_interaction(self):
        doc = self.doc()
        doc["concepts"]["change-pin"] = {"name": "Change PIN", "kind": "usecase"}
        doc["relationships"]["association:atm-customer->change-pin"] = {
            "type": "association", "from": "atm-customer", "to": "change-pin"}
        compiled = PJ.compile_projections(doc)
        uc = self.by_diagram(compiled, "usecase")[0]
        self.assertEqual(uc["elements"][-1]["name"], "Change PIN")
        self.assertEqual(uc["relations"][-1], {"type": "association", "from": "cust", "to": "change-pin"})
        self.assertEqual(len(self.by_diagram(compiled, "communication")), 1)
        self.assertTrue(any(w.startswith("R1") and "Change PIN" in w for w in C.check(compiled)[1]))

    def test_reconcile_canonical_doc(self):
        doc = self.doc()
        canonical = PJ.canonical_semantic_model(doc)
        self.assertEqual(canonical["sourceOfTruth"]["mode"], "canonical")
        compiled = PJ.compile_projections(doc)
        self.assertEqual(CR.reconcile(canonical, M.build_model(compiled))["status"], "clean")
        # Sua tay ten trong spec da compile (giu conceptId) -> M3 drift, khong phai M1/M2.
        comm = self.by_diagram(compiled, "communication")[0]
        next(e for e in comm["elements"] if e.get("name") == "ATM Customer")["name"] = "ATM Client"
        rules = {d["rule"] for d in CR.reconcile(canonical, M.build_model(compiled))["drift"]}
        self.assertIn("M3", rules)
        self.assertFalse({"M1", "M2"} & rules)
        # Concept khai bao nhung khong view nao chieu -> M1.
        doc["concepts"]["orphan"] = {"name": "Orphan Concept", "kind": "class"}
        result = CR.reconcile(PJ.canonical_semantic_model(doc), M.build_model(PJ.compile_projections(doc)))
        self.assertEqual([d["rule"] for d in result["drift"]], ["M1"])

    def test_validation_errors(self):
        doc = self.doc()
        doc["views"][0]["elements"].append({"ref": "missing"})
        doc["relationships"]["bad"] = {"type": "association", "from": "atm-customer", "to": "nope"}
        self.assertIn("K9", {i["rule"] for i in PJ.validate_canonical(doc)})
        del doc["relationships"]["bad"]
        self.assertIn("K4", {i["rule"] for i in PJ.validate_canonical(doc)})
        with self.assertRaises(PJ.CanonicalError):
            PJ.compile_projections(doc)
        doc = self.doc()
        uc = next(v for v in doc["views"] if v["diagram"] == "usecase")
        uc["elements"].append(dict(uc["elements"][0]))   # concept xuat hien 2 lan -> quan he mo ho
        self.assertTrue({"K5", "K6"} <= {i["rule"] for i in PJ.validate_canonical(doc)})
        doc = self.doc()
        doc["views"][0]["diagram"] = "gantt"
        self.assertIn("K7", {i["rule"] for i in PJ.validate_canonical(doc)})
        self.assertEqual(PJ.validate_canonical({"kind": "x"})[0]["rule"], "K1")

    def test_bundle_preserved_and_mixed_bundles_rejected(self):
        a = dict(copy.deepcopy(SHOP_UC), bundle="Shop", _src="uc.json")
        b = dict(copy.deepcopy(SHOP_CTX), bundle="Shop", _src="ctx.json")
        doc = PJ.bootstrap_canonical([a, b])
        self.assertEqual(doc["bundle"], "Shop")
        self.assertTrue(all(s["bundle"] == "Shop" for s in PJ.compile_projections(doc)))
        self.assertEqual(PJ.verify_roundtrip([a, b], doc), [])
        c = dict(copy.deepcopy(SHOP_CLS), bundle="Other", _src="cls.json")
        with self.assertRaises(ValueError):
            PJ.bootstrap_canonical([a, b, c])
        self.assertEqual(len(PJ.bootstrap_canonical([a, b, c], bundle="shop")["views"]), 2)

    def test_explicit_concept_id_preserved(self):
        specs = TestSemanticModelV2.specs()
        doc = PJ.bootstrap_canonical(specs)
        self.assertIn("customer.party", {c.get("conceptId") for c in doc["concepts"].values()})
        self.assertEqual(PJ.verify_roundtrip(specs, doc), [])
        self.assertEqual(set(M.build_model(PJ.compile_projections(doc))["concepts"]),
                         set(M.build_model(TestSemanticModelV2.specs())["concepts"]))

    def test_cli_bootstrap_compile_check_model_reconcile(self):
        d = self.tmpdir()
        canon = d / "system.canonical.json"
        r = run("comet_project.py", "bootstrap", *EXAMPLE_FILES, "-o", canon)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["roundTrip"], "exact")
        self.assertEqual(run("comet_project.py", "validate", canon).returncode, 0)
        out = d / "specs"
        self.assertEqual(run("comet_project.py", "compile", canon, "-o", out).returncode, 0)
        self.assertEqual(len(list(out.glob("*.json"))), len(EXAMPLE_FILES))
        self.assertEqual(run("comet_project.py", "compile", canon, "-o", out, "--check").returncode, 0)
        seq = out / "atm_seq_validate_pin.json"
        seq.write_text(seq.read_text(encoding="utf-8").replace("PIN Prompt", "Enter PIN"), encoding="utf-8")
        r = run("comet_project.py", "compile", canon, "-o", out, "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("atm_seq_validate_pin.json", r.stdout)
        run("comet_project.py", "compile", canon, "-o", out)
        r = run("comet_project.py", "model", canon, "-o", d / "system.model.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        model = json.loads((d / "system.model.json").read_text(encoding="utf-8"))
        self.assertEqual(model["sourceOfTruth"]["mode"], "canonical")
        r = run("comet_reconcile.py", canon, *sorted(out.glob("*.json")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["status"], "clean")
        r = run("comet_manifest.py", *sorted(out.glob("*.json")), "-o", d / "system", "--canonical-model", canon)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotEqual(run("comet_project.py", "compile", d / "missing.json", "-o", out).returncode, 0)


class TestCLI(TmpMixin, unittest.TestCase):
    def test_uml2drawio(self):
        d = self.tmpdir()
        r = run("uml2drawio.py", EXAMPLES / "atm_statechart.json", "-o", d / "stm.drawio")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[OK]", r.stderr)
        self.assertEqual(len(pages(str(d / "stm.drawio"))), 1)
        # glob trong ngoac kep: script tu mo rong (PowerShell/cmd khong mo rong)
        r = run("uml2drawio.py", EXAMPLES / "atm_*.json", "-o", d / "all.drawio")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(pages(str(d / "all.drawio"))), len(list(EXAMPLES.glob("atm_*.json"))))
        r = run("uml2drawio.py", EXAMPLES / "atm_context.json", "--xml-only", cwd=d)   # chi in, khong ghi file
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.lstrip().startswith("<mxGraphModel"))
        shutil.copy(EXAMPLES / "atm_context.json", d / "ctx.json")
        self.assertEqual(run("uml2drawio.py", d / "ctx.json").returncode, 0)             # mac dinh: canh spec
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["all.drawio", "ctx.drawio", "ctx.json", "stm.drawio"])

    def test_comet_check(self):
        r = run("comet_check.py", "--partial", EXAMPLES / "*.json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("0 loi, 0 canh bao", r.stdout)

        d = self.tmpdir()
        bad = copy.deepcopy(SHOP_COMM)
        bad["messages"][2]["seq"] = "2"
        (d / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        r = run("comet_check.py", d / "bad.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ERROR: R9", r.stdout)

        warn = copy.deepcopy(SHOP_COMM)
        warn["useCase"] = "Ghost Use Case"
        (d / "warn.json").write_text(json.dumps(warn), encoding="utf-8")
        r = run("comet_check.py", d / "warn.json")
        self.assertEqual(r.returncode, 0, r.stdout)
        r = run("comet_check.py", "--strict", d / "warn.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("WARN", r.stdout)

        model_file = d / "model.json"
        r = run("comet_model.py", EXAMPLES / "atm_usecase.json", EXAMPLES / "atm_context.json",
                "-o", model_file)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        payload = json.loads(model_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["kind"], "comet-semantic-model")
        self.assertIn("fingerprint", payload)

        repair_input = copy.deepcopy(SHOP_COMM)
        repair_input["elements"][1]["stereotype"] = "invalid stereotype"
        repair_json = d / "repair-input.json"
        repair_json.write_text(json.dumps(repair_input), encoding="utf-8")
        canonical_file = d / "canonical.json"
        canonical_file.write_text(json.dumps(CM.build_manifests(
            [copy.deepcopy(SHOP_COMM)])[0], ensure_ascii=False), encoding="utf-8")
        r = run("comet_reconcile.py", canonical_file, repair_json)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        reconciliation = json.loads(r.stdout)
        self.assertEqual(reconciliation["kind"], "comet-canonical-reconciliation")
        self.assertEqual(reconciliation["status"], "clean")
        plan_file = d / "repair.json"
        r = run("comet_plan.py", repair_json, "-o", plan_file)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        repair = json.loads(plan_file.read_text(encoding="utf-8"))
        self.assertEqual(repair["kind"], "comet-repair-plan")
        self.assertTrue(any(step["rule"] == "R4" for step in repair["steps"]))

        canonical_manifest = d / "canonical-manifest.json"
        canonical_specs = [str(EXAMPLES / "atm_usecase.json"), str(EXAMPLES / "atm_context.json")]
        canonical_model = CM.build_manifests(C.load(canonical_specs))[0]
        canonical_manifest.write_text(json.dumps(canonical_model, ensure_ascii=False), encoding="utf-8")
        prefix = d / "system"
        r = run("comet_manifest.py", *canonical_specs, "--canonical-model", canonical_manifest, "-o", prefix)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        model_payload = json.loads((d / "system.model.json").read_text(encoding="utf-8"))
        consistency_payload = json.loads((d / "system.consistency.json").read_text(encoding="utf-8"))
        repair_payload = json.loads((d / "system.repair.json").read_text(encoding="utf-8"))
        self.assertEqual(model_payload["fingerprint"], consistency_payload["modelFingerprint"])
        self.assertEqual(model_payload["fingerprint"], repair_payload["modelFingerprint"])
        self.assertTrue(consistency_payload["canonicalSourceOfTruth"])
        self.assertIn("canonicalReconciliation", consistency_payload)

    def test_preview_svg(self):
        for p in EXAMPLE_FILES:
            for name, model in pages(gen(*U.load_specs([str(p)]))[0]):
                svg, w, h = P.render_svg(model)
                with self.subTest(example=p.name):
                    self.assertTrue(svg.startswith("<svg"))
                    self.assertGreater(min(w, h), 50)
                    ET.fromstring(svg)   # SVG la XML hop le

    @unittest.skipUnless(os.environ.get("COMET_TEST_PNG", "1") != "0" and P.find_browser(),
                         "khong co Chrome/Edge (hoac COMET_TEST_PNG=0)")
    def test_preview_png(self):
        d = self.tmpdir()
        r = run("uml2drawio.py", EXAMPLES / "atm_statechart.json", EXAMPLES / "atm_context.json", "-o", d / "two.drawio")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run("preview_svg.py", d / "two.drawio", "-o", d / "p.html", "--png")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for n in ("p_p1.png", "p_p2.png"):   # nhieu trang -> <stem>_p<N>.png
            data = (d / n).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            w, h = struct.unpack(">II", data[16:24])
            self.assertGreater(min(w, h), 100, n)
        self.assertEqual(list(d.glob("*.tmp.html")), [])


# ============================================================ 7. cai dat
class TestInstall(TmpMixin, unittest.TestCase):
    def test_plan(self):
        items = INST.plan()
        self.assertEqual(items[0], ("comet-uml-drawio", INST.ROOT))
        if HAS_COMMANDS:
            self.assertEqual({n for n, _ in items[1:]}, EXPECTED_COMMANDS)

    def test_install_reinstall_uninstall(self):
        dest = self.tmpdir() / "skills"
        with quiet():
            self.assertTrue(INST.install(dest, False))
        eng = dest / "comet-uml-drawio"
        for f in ("SKILL.md", "scripts/uml2drawio.py", "examples/atm_statechart.json", "references/comet-method.md",
                  "tests/run_tests.py", "tests/fuzz_specs.py"):
            self.assertTrue((eng / f).is_file(), f)
        for junk in ("out", "commands", ".claude", "scripts/__pycache__", "tests/__pycache__"):
            self.assertFalse((eng / junk).exists(), junk)
        names = (eng / INST.MANIFEST).read_text(encoding="utf-8").split()
        self.assertEqual(names, [n for n, _ in INST.plan()[1:]])
        for n in names:
            f = dest / n / "SKILL.md"
            body = f.read_text(encoding="utf-8")
            self.assertNotIn(INST.PLACEHOLDER, body)
            self.assertIn(eng.absolute().as_posix() + "/scripts/uml2drawio.py", body)
            self.assertEqual(INST.skill_name(f), n)
        # cai lai: lenh cu trong manifest (khong con trong commands/) bi go; skill la khong bi dong toi
        (dest / "uml-old").mkdir()
        (dest / "uml-old" / "SKILL.md").write_text("---\nname: uml-old\n---\n", encoding="utf-8")
        (eng / INST.MANIFEST).write_text("\n".join(names + ["uml-old"]) + "\n", encoding="utf-8")
        (dest / "mine").mkdir()
        (dest / "mine" / "SKILL.md").write_text("---\nname: mine\n---\n", encoding="utf-8")
        with quiet():
            self.assertTrue(INST.install(dest, False))
        self.assertFalse((dest / "uml-old").exists())
        with quiet():
            self.assertTrue(INST.uninstall(dest, False))
        self.assertEqual([p.name for p in dest.iterdir()], ["mine"])

    def test_refuses_foreign_dirs_and_dry_run(self):
        dest = self.tmpdir()
        foreign = dest / "comet-uml-drawio"
        foreign.mkdir()
        (foreign / "SKILL.md").write_text("---\nname: someone-else\n---\n", encoding="utf-8")
        with quiet():
            self.assertFalse(INST.install(dest, False))
        self.assertEqual((foreign / "SKILL.md").read_text(encoding="utf-8"), "---\nname: someone-else\n---\n")
        self.assertEqual([p.name for p in dest.iterdir()], ["comet-uml-drawio"])
        with quiet():
            self.assertTrue(INST.install(dest / "dry", True))
        self.assertFalse((dest / "dry").exists())

    def test_refuses_source_parent_as_dest(self):
        r = run("install.py", "--dest", ENGINE.parent, "--dry-run")   # --dry-run: guard hong cung khong ghi gi
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("trung thu muc", r.stderr)


# ============================================================ 8. tai lieu
def command_files():
    """ten lenh -> SKILL.md: ban nguon commands/<ten>/, ban da cai <skills>/<ten>/ (theo manifest)."""
    if HAS_COMMANDS:
        return {p.parent.name: p for p in sorted(COMMAND_SRC.glob("*/SKILL.md"))}
    man = ENGINE / INST.MANIFEST
    return {n: ENGINE.parent / n / "SKILL.md" for n in (man.read_text(encoding="utf-8").split() if man.is_file() else [])}


class TestDocs(unittest.TestCase):
    def test_commands(self):
        cmds = command_files()
        if not cmds:
            self.skipTest("engine cai rieng, khong co lenh /uml-*")
        self.assertEqual(set(cmds), EXPECTED_COMMANDS)
        prefix = INST.PLACEHOLDER if HAS_COMMANDS else ENGINE.as_posix()
        for name, f in cmds.items():
            body = f.read_text(encoding="utf-8")
            with self.subTest(command=name):
                fm = re.match(r"---\n(.*?)\n---\n", body, re.S).group(1)
                self.assertEqual(INST.skill_name(f), name)
                self.assertRegex(fm, r"(?m)^description: \S")
                self.assertRegex(fm, r"(?m)^user-invocable: true$")
                self.assertIn("$ARGUMENTS", body)
                refs = {r.rstrip(".") for r in re.findall(re.escape(prefix) + r"/([\w./-]+)", body)}
                self.assertTrue({"scripts/uml2drawio.py", "scripts/comet_check.py", "scripts/preview_svg.py"} <= refs)
                if name == "uml-comet":   # lenh tong: dan toi tung lenh con (moi lenh con chi toi vi du cua no)
                    links = set(re.findall(r"\(\.\./(uml-[\w-]+)/SKILL\.md\)", body))
                    self.assertEqual(links, EXPECTED_COMMANDS - {"uml-comet"})
                else:
                    self.assertTrue(any(r.startswith("examples/") for r in refs))
                for r in refs:
                    self.assertTrue((ENGINE / r).exists(), r)
        used = "".join(f.read_text(encoding="utf-8") for f in cmds.values())
        for p in EXAMPLE_FILES:
            self.assertIn("examples/" + p.name, used)   # moi vi du la khuon cua it nhat 1 lenh

    def test_skill_md_links_every_command(self):
        body = (ENGINE / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(INST.skill_name(ENGINE / "SKILL.md"), "comet-uml-drawio")
        self.assertEqual(set(re.findall(r"\(\.\./(uml-[\w-]+)/SKILL\.md\)", body)), EXPECTED_COMMANDS)

    def test_mentioned_files_exist(self):
        docs = [ENGINE / "SKILL.md"] + sorted(REFS.glob("*.md")) + list(command_files().values())
        pat = r"\b((?:examples|references|scripts|tests)/[\w.-]+\.(?:json|md|py))"
        for doc in docs:
            for rel in set(re.findall(pat, doc.read_text(encoding="utf-8"))):
                with self.subTest(doc=doc.name, ref=rel):
                    self.assertTrue((ENGINE / rel).is_file())

    def test_rule_codes_documented(self):
        emitted = set(re.findall(r'"([RSACEFBLX]\d{1,2}) ', (SCRIPTS / "comet_check.py").read_text(encoding="utf-8")))
        documented = set()
        doc = (REFS / "comet-method.md").read_text(encoding="utf-8")
        for a, b in re.findall(r"(?m)^\| ([RSACEFBLX]\d{1,2})(?:–([RSACEFBLX]\d{1,2}))? \|", doc):
            documented |= {"%s%d" % (a[0], k) for k in range(int(a[1:]), int((b or a)[1:]) + 1)}
        self.assertEqual(emitted, documented)

    def test_diagram_types_documented(self):
        doc = (REFS / "spec-format.md").read_text(encoding="utf-8")
        row = next(l for l in doc.splitlines() if l.startswith("| `diagram`"))
        self.assertEqual(set(re.findall(r"`(\w+)`", row)) - {"diagram"}, set(U.FRAME_KIND))

    def test_spec_format_examples_valid(self):
        n = 0
        for block in re.findall(r"```json\n(.*?)```", (REFS / "spec-format.md").read_text(encoding="utf-8"), re.S):
            try:
                sp = json.loads(block)
            except ValueError:
                continue   # doan trich (nhieu object), khong phai spec day du
            if not isinstance(sp, dict) or "diagram" not in sp:
                continue
            n += 1
            with self.subTest(title=sp.get("title")):
                xml, warns = gen(sp)
                self.assertEqual((warns,) + report(xml)[:2], ([], [], []))
                self.assertEqual(check(sp, partial=True)[:2], ([], []))
        self.assertGreaterEqual(n, 2)


if __name__ == "__main__":
    unittest.main()
