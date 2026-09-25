#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preview_svg.py - Ve xem truoc file .drawio thanh HTML/SVG (offline, gan dung) de kiem tra bang mat
bo cuc: vi tri hinh, duong noi, nhan. Khong thay the draw.io, chi de soat loi chong hinh.

  python preview_svg.py out.drawio [-o preview.html]
  python preview_svg.py out.drawio -o preview.html --png   # + moi trang 1 anh PNG (Chrome/Edge headless)
"""
from __future__ import annotations

import argparse
import glob
import html
import math
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True  # khong ghi __pycache__ vao thu muc skill
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_drawio import Geometry, load_pages, plain, shape_rect  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _t(x, y, text, size=12, anchor="middle", bold=False, italic=False, valign="middle", underline=""):
    lines = text.split("\n")
    lh = size * 1.3
    if valign == "middle":
        y0 = y - (len(lines) - 1) * lh / 2
    elif valign == "top":
        y0 = y + size
    else:
        y0 = y - (len(lines) - 1) * lh
    out = []
    for i, l in enumerate(lines):
        body = html.escape(l)
        if underline and l.startswith(underline):   # <u>ten</u>: kieu -> chi gach chan phan ten
            body = '<tspan text-decoration="underline">%s</tspan>%s' % (html.escape(underline),
                                                                        html.escape(l[len(underline):]))
        out.append('<text x="%.1f" y="%.1f" font-size="%d" text-anchor="%s" dominant-baseline="%s"%s%s>%s</text>'
                   % (x, y0 + i * lh, size, anchor, "central" if valign == "middle" else "auto",
                      ' font-weight="bold"' if bold else "", ' font-style="italic"' if italic else "",
                      body))
    return "".join(out)


def _rich(value):
    """Tach dong, nhan dien <b>/<i> theo tung dong."""
    v = value or ""
    import re
    rows = re.split(r"<br\s*/?>", v, flags=re.I)
    out = []
    for r in rows:
        m = re.match(r"\s*<u>(.*?)</u>", r)
        out.append((plain(r), "<b>" in r, "<i>" in r, plain(m.group(1)) if m else ""))
    return out


def _lines_block(x, y, rows, size=12, anchor="middle", valign="middle"):
    lh = size * 1.3
    n = len(rows)
    if valign == "middle":
        y0 = y - (n - 1) * lh / 2
    else:
        y0 = y + lh / 2
    return "".join(_t(x, y0 + i * lh, r[0], size, anchor, r[1], r[2], underline=r[3] if len(r) > 3 else "")
                   for i, r in enumerate(rows))


def marker(kind, fill, p, q, size=10):
    """Mui ten tai p, huong tu q -> p."""
    dx, dy = p[0] - q[0], p[1] - q[1]
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    if kind in ("block", "classic", "blockThin"):
        a = (p[0] - ux * size + nx * size * 0.5, p[1] - uy * size + ny * size * 0.5)
        b = (p[0] - ux * size - nx * size * 0.5, p[1] - uy * size - ny * size * 0.5)
        return '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" stroke="#000"/>' % (
            p[0], p[1], a[0], a[1], b[0], b[1], "#000" if fill else "#fff")
    if kind in ("open", "openThin"):
        a = (p[0] - ux * size + nx * size * 0.45, p[1] - uy * size + ny * size * 0.45)
        b = (p[0] - ux * size - nx * size * 0.45, p[1] - uy * size - ny * size * 0.45)
        return '<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="#000"/>' % (
            a[0], a[1], p[0], p[1], b[0], b[1])
    if kind in ("diamond", "diamondThin"):
        s = 16
        m = (p[0] - ux * s / 2, p[1] - uy * s / 2)
        e = (p[0] - ux * s, p[1] - uy * s)
        w = 4.5
        return '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" stroke="#000"/>' % (
            p[0], p[1], m[0] + nx * w, m[1] + ny * w, e[0], e[1], m[0] - nx * w, m[1] - ny * w,
            "#000" if fill else "#fff")
    return ""


def _rounded_path(pts, r=8.0):
    """Duong gap khuc bo tron goc (giong rounded=1 cua draw.io)."""
    d = ["M%.1f,%.1f" % pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        l1, l2 = math.dist(a, b), math.dist(b, c)
        k = min(r, l1 / 2, l2 / 2)
        if k < 0.5:
            d.append("L%.1f,%.1f" % b)
            continue
        p = (b[0] + (a[0] - b[0]) * k / l1, b[1] + (a[1] - b[1]) * k / l1)
        q = (b[0] + (c[0] - b[0]) * k / l2, b[1] + (c[1] - b[1]) * k / l2)
        d.append("L%.1f,%.1f Q%.1f,%.1f %.1f,%.1f" % (p[0], p[1], b[0], b[1], q[0], q[1]))
    d.append("L%.1f,%.1f" % pts[-1])
    return " ".join(d)


def render_page(name, model):
    svg, _, _ = render_svg(model)
    return "<h3>%s</h3>%s" % (html.escape(name), svg)


def render_svg(model):
    """-> (the <svg>, rong, cao)"""
    G = Geometry(model)
    S = []
    maxx = maxy = 0
    for v in G.verts:
        maxx, maxy = max(maxx, v.ax + v.w), max(maxy, v.ay + v.h)
    order = sorted(G.verts, key=lambda v: len(G.anc[v.id]))
    for v in order:
        st, sh = v.st, v.shape
        x, y, w, h = v.ax, v.ay, v.w, v.h
        fill = st.get("fillColor", "#ffffff")
        fill = "none" if fill == "none" else fill
        stroke = st.get("strokeColor", "#000")
        stroke = "none" if stroke == "none" else ("#000" if stroke in ("inherit", "default") else stroke)
        dash = ' stroke-dasharray="6 4"' if st.get("dashed") == "1" else ""
        rows = _rich(v.value)
        fs = str(st.get("fontStyle", "0"))
        if fs.isdigit() and int(fs) & 1:   # fontStyle=1: ca o in dam
            rows = [(r[0], True) + tuple(r[2:]) for r in rows]
        base = st.get("_base", "")
        if sh == "umlActor":
            cx = x + w / 2
            S.append('<g stroke="#000" fill="none"><circle cx="%.1f" cy="%.1f" r="%.1f" fill="#fff"/>'
                     '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/><line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                     '<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f"/></g>'
                     % (cx, y + h * 0.12, h * 0.12, cx, y + h * 0.24, cx, y + h * 0.62, x, y + h * 0.36, x + w,
                        y + h * 0.36, x, y + h, cx, y + h * 0.62, x + w, y + h))
            if st.get("labelPosition") == "right":
                S.append(_lines_block(x + w + 6, y + h / 2, rows, 12, "start"))
            else:
                S.append(_lines_block(x + w / 2, y + h + 4, rows, 12, "middle", "top"))
            continue
        if sh == "umlLifeline":
            size = float(st.get("size", 40))
            cx = x + w / 2
            S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000" stroke-dasharray="6 4"/>'
                     % (cx, y + size, cx, y + h))
            if st.get("participant") == "umlActor":
                S.append('<g stroke="#000" fill="none"><circle cx="%.1f" cy="%.1f" r="5" fill="#fff"/>'
                         '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/><line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                         '<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f"/></g>'
                         % (cx, y + 5, cx, y + 10, cx, y + 26, cx - 10, y + 15, cx + 10, y + 15, cx - 10,
                            y + 40, cx, y + 26, cx + 10, y + 40))
                S.append(_lines_block(cx, y + size + 2, rows, 12, "middle", "top"))
            else:
                S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#fff" stroke="#000"/>'
                         % (x, y, w, size))
                S.append(_lines_block(cx, y + size / 2, rows))
            continue
        if base == "line":
            S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000"/>' % (x, y + h / 2, x + w, y + h / 2))
            continue
        if base == "text":
            if st.get("align") == "left":
                S.append(_lines_block(x + float(st.get("spacingLeft", 2)), y + (4 if st.get("verticalAlign") == "top" else h / 2),
                                      rows, int(float(st.get("fontSize", 12))), "start",
                                      "top" if st.get("verticalAlign") == "top" else "middle"))
            else:
                S.append(_lines_block(x + w / 2, y + h / 2, rows))
            continue
        if base == "ellipse" or sh in ("endState", "sumEllipse"):
            S.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s"/>'
                     % (x + w / 2, y + h / 2, w / 2, h / 2, "#fff" if sh == "endState" else fill, stroke))
            if sh == "endState":
                S.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="#000"/>'
                         % (x + w / 2, y + h / 2, w / 2 - 4, h / 2 - 4))
        elif base == "rhombus":
            S.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="#fff" stroke="#000"/>'
                     % (x + w / 2, y, x + w, y + h / 2, x + w / 2, y + h, x, y + h / 2))
            if st.get("double") == "1":  # ERD Chen: quan he xac dinh -> hinh thoi vien kep
                S.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="#000"/>'
                         % (x + w / 2, y + 5, x + w - 9, y + h / 2, x + w / 2, y + h - 5, x + 9, y + h / 2))
        elif sh == "folder":
            tw, th = float(st.get("tabWidth", 60)), float(st.get("tabHeight", 20))
            S.append('<path d="M%.1f %.1f h%.1f v%.1f h%.1f v%.1f h%.1f z" fill="#fff" stroke="#000"/>'
                     % (x, y, tw, th, w - tw, h - th, -w))
            S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000"/>' % (x, y + th, x + tw, y + th))
            S.append(_lines_block(x + 8, y + 2, rows, 12, "start", "top"))
            continue
        elif sh == "cube":
            s = float(st.get("size", 12))
            S.append('<path d="M%.1f %.1f l%.1f %.1f h%.1f v%.1f l%.1f %.1f h%.1f z" fill="#f4f4f4" stroke="#000"/>'
                     % (x, y + s, s, -s, w - s, h - s, -s, s, -(w - s)))
            S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#fff" stroke="#000"/>'
                     % (x, y + s, w - s, h - s))
            if st.get("verticalAlign") == "top":
                S.append(_lines_block(x + (w - s) / 2, y + s + 4, rows, 12, "middle", "top"))
            else:
                S.append(_lines_block(x + (w - s) / 2, y + s + (h - s) / 2, rows))
            continue
        elif sh in ("note", "note2"):
            s = float(st.get("size", 14))
            S.append('<path d="M%.1f %.1f h%.1f l%.1f %.1f v%.1f h%.1f z" fill="#fff" stroke="#000"/>'
                     % (x, y, w - s, s, s, h - s, -w))
        elif sh == "umlFrame":
            fw, fh = float(st.get("width", 60)), float(st.get("height", 26))
            S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#000"/>' % (x, y, w, h))
            S.append('<path d="M%.1f %.1f h%.1f v%.1f l%.1f %.1f h%.1f" fill="#fff" stroke="#000"/>'
                     % (x, y, fw, fh - 8, -8, 8, -(fw - 8)))
            S.append(_lines_block(x + (fw - 4) / 2, y + fh / 2, rows))
            continue
        elif base == "swimlane":
            ss = float(st.get("startSize", 26))
            rx = 12 if st.get("rounded") == "1" else 0
            hf = fill if fill not in ("none", "#ffffff") else "#fff"
            S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" fill="#fff" stroke="#000"%s/>'
                     % (x, y, w, h, rx, dash))
            if st.get("horizontal") == "0":  # tieu de doc ben trai
                S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="#000"/>'
                         % (x, y, ss, h, hf))
                S.append('<text x="%.1f" y="%.1f" font-size="12" font-weight="bold" text-anchor="middle" '
                         'dominant-baseline="central" transform="rotate(-90 %.1f %.1f)">%s</text>'
                         % (x + ss / 2, y + h / 2, x + ss / 2, y + h / 2,
                            html.escape(" ".join(r[0] for r in rows))))
            else:
                if hf != "#fff":
                    S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" fill="%s" stroke="#000"%s/>'
                             % (x, y, w, ss, rx, hf, dash))
                S.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000"/>' % (x, y + ss, x + w, y + ss))
                S.append(_lines_block(x + w / 2, y + ss / 2, rows))
            continue
        else:
            rx = 0
            if st.get("rounded") == "1":
                rx = min(h / 2, float(st.get("arcSize", 20)) / 100 * min(w, h)) if st.get("absoluteArcSize") != "1" \
                    else float(st.get("arcSize", 20)) / 2
            f = "#000" if fill == "#000000" else ("none" if fill == "none" else "#fff")
            S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" stroke="%s"%s/>'
                     % (x, y, w, h, rx, f, stroke, dash))
            if st.get("double") == "1":  # ERD Chen: thuc the yeu -> vien kep
                S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#000"/>'
                         % (x + 3, y + 3, w - 6, h - 6))
            if sh == "module":
                S.append('<rect x="%.1f" y="%.1f" width="8" height="4" fill="#fff" stroke="#000"/>'
                         '<rect x="%.1f" y="%.1f" width="8" height="4" fill="#fff" stroke="#000"/>'
                         % (x - 4, y + 4, x - 4, y + 12))
        if rows and any(r[0] for r in rows):
            if st.get("labelPosition") == "right":
                S.append(_lines_block(x + w + 6, y + h / 2, rows, 12, "start"))
            elif st.get("verticalLabelPosition") == "bottom":
                S.append(_lines_block(x + w / 2, y + h + 4, rows, 12, "middle", "top"))
            elif st.get("verticalAlign") == "top":
                if st.get("align") == "left":
                    S.append(_lines_block(x + 8, y + 4, rows, 12, "start", "top"))
                else:
                    S.append(_lines_block(x + w / 2, y + 4, rows, 12, "middle", "top"))
            else:
                S.append(_lines_block(x + w / 2, y + h / 2, rows))

    for eid, (c, pts) in G.edges.items():
        st = c.st
        dash = ' stroke-dasharray="6 4"' if st.get("dashed") == "1" else ""
        if st.get("rounded") == "1" and len(pts) > 2:
            S.append('<path d="%s" fill="none" stroke="#000"%s/>' % (_rounded_path(pts), dash))
        else:
            S.append('<polyline points="%s" fill="none" stroke="#000"%s/>'
                     % (" ".join("%.1f,%.1f" % p for p in pts), dash))
        ea = st.get("endArrow", "classic")
        if ea and ea != "none":
            S.append(marker(ea, st.get("endFill", "1") != "0", pts[-1], pts[-2]))
        sa = st.get("startArrow", "none")
        if sa and sa != "none":
            S.append(marker(sa, st.get("startFill", "1") != "0", pts[0], pts[1]))
        for p in pts:
            maxx, maxy = max(maxx, p[0]), max(maxy, p[1])
    for r, owner, d, cell in G.labels:
        if cell.vertex and not cell.relative:
            continue  # nhan cua hinh da ve
        bg = cell.st.get("labelBackgroundColor", "#ffffff")
        if bg != "none":
            S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#fff" opacity="0.9"/>'
                     % (r[0], r[1], r[2] - r[0], r[3] - r[1]))
        S.append(_lines_block((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, _rich(cell.value), 11))
        maxx, maxy = max(maxx, r[2]), max(maxy, r[3])
    W, H = int(maxx + 30), int(maxy + 30)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'font-family="Helvetica, Arial, sans-serif" style="background:#fff;border:1px solid #ccc">%s</svg>'
            % (W, H, "".join(S))), W, H


def find_browser():
    """Chrome/Edge/Chromium de chup PNG headless; bien moi truong CHROME de chi dinh duong dan."""
    env = os.environ.get("CHROME")
    if env and os.path.isfile(env):
        return env
    cands = []
    for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
        if root:
            cands += [os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"),
                      os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe")]
    cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for c in cands:
        if os.path.isfile(c):
            return c
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"):
        p = shutil.which(n)
        if p:
            return p
    return None


def shoot(browser, html_path, png_path, w, h):
    prof = tempfile.mkdtemp(prefix="drawio_png_")
    try:
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        "--force-device-scale-factor=1", "--user-data-dir=" + prof,
                        "--window-size=%d,%d" % (w, h), "--screenshot=" + os.path.abspath(png_path),
                        pathlib.Path(html_path).resolve().as_uri()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    return os.path.isfile(png_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", default="preview.html")
    ap.add_argument("--png", action="store_true",
                    help="chup them moi trang thanh <out>_p<N>.png bang Chrome/Edge headless (de AI tu xem anh)")
    a = ap.parse_args()
    files = []   # tu mo rong *.drawio (PowerShell/cmd khong mo rong glob)
    for f in a.files:
        files += (sorted(glob.glob(f)) if any(c in f for c in "*?[") else []) or [f]
    parts, pages = [], []
    for f in files:
        for name, model in load_pages(f):
            if model is not None:
                title = "%s — %s" % (os.path.basename(f), name)
                svg, w, h = render_svg(model)
                parts.append("<h3>%s</h3>%s" % (html.escape(title), svg))
                pages.append((title, svg, w, h))
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write('<!doctype html><meta charset="utf-8"><title>preview</title>'
                 '<body style="font-family:sans-serif;background:#f6f6f6">%s</body>' % "".join(parts))
    print("Da ghi:", a.out)
    if not a.png:
        return
    browser = find_browser()
    if not browser:
        print("Khong tim thay Chrome/Edge/Chromium (dat bien CHROME=duong_dan) -> bo qua --png; mo %s de xem." % a.out)
        return
    stem = os.path.splitext(a.out)[0]
    for i, (title, svg, w, h) in enumerate(pages, 1):
        png = "%s.png" % stem if len(pages) == 1 else "%s_p%d.png" % (stem, i)
        tmp = "%s_p%d.tmp.html" % (stem, i)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write('<!doctype html><meta charset="utf-8"><body style="margin:0;background:#fff">'
                     '<div style="font:bold 14px sans-serif;padding:6px 8px;height:18px;white-space:nowrap">'
                     '%s</div>%s</body>' % (html.escape(title), svg))
        try:
            # so do hep: noi rong cua so theo tieu de de khong bi cat chu
            ok = shoot(browser, tmp, png, max(w + 4, int(len(title) * 8.5) + 24), h + 36)
        finally:
            os.remove(tmp)
        print(("Da chup: %s  (%s)" if ok else "Chup that bai: %s  (%s)") % (png, title))


if __name__ == "__main__":
    main()
