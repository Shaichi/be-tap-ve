# Scratch: ve PNG gan dung tu file .drawio (dung Geometry cua validate_drawio) de soat bo cuc bang mat.
# Chi doc script cua skill, khong sua. Chay: python -B render_png.py file.drawio outdir
import math
import os
import sys

sys.path.insert(0, r"C:\Users\pc\.claude\skills\comet-uml-drawio\scripts")
from validate_drawio import Geometry, load_pages, plain  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

SC = 1.6


def font(sz, bold=False):
    try:
        return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", int(sz * SC))
    except Exception:
        return ImageFont.load_default()


def P(x, y):
    return (x * SC + 20, y * SC + 20)


def text_block(d, cx, cy, value, sz=12, anchor="mm"):
    import re
    rows = [plain(r) for r in re.split(r"<br\s*/?>", value or "", flags=re.I)]
    rows = [r for r in rows]
    lh = sz * 1.3
    y0 = cy - (len(rows) - 1) * lh / 2
    for i, r in enumerate(rows):
        d.text(P(cx, y0 + i * lh), r, fill="black", font=font(sz), anchor=anchor)


def arrow(d, kind, fill, p, q):
    dx, dy = p[0] - q[0], p[1] - q[1]
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    s = 10
    a = (p[0] - ux * s + nx * s * 0.5, p[1] - uy * s + ny * s * 0.5)
    b = (p[0] - ux * s - nx * s * 0.5, p[1] - uy * s - ny * s * 0.5)
    if kind in ("block", "classic"):
        d.polygon([P(*p), P(*a), P(*b)], fill="black" if fill else "white", outline="black")
    elif kind in ("open", "openThin"):
        d.line([P(*a), P(*p), P(*b)], fill="black", width=2)
    elif kind.startswith("diamond"):
        m = (p[0] - ux * 8, p[1] - uy * 8)
        e = (p[0] - ux * 16, p[1] - uy * 16)
        d.polygon([P(*p), P(m[0] + nx * 4.5, m[1] + ny * 4.5), P(*e), P(m[0] - nx * 4.5, m[1] - ny * 4.5)],
                  fill="black" if fill else "white", outline="black")


def dashed(d, pts, width=2):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        L = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(L / 10))
        for i in range(n):
            if i % 2 == 0:
                t0, t1 = i / n, min(1, (i + 1) / n)
                d.line([P(x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0), P(x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1)],
                       fill="black", width=width)


def render(name, model, out):
    G = Geometry(model)
    maxx = maxy = 0
    for v in G.verts:
        maxx, maxy = max(maxx, v.ax + v.w), max(maxy, v.ay + v.h + 20)
    for _, (c, pts) in G.edges.items():
        for p in pts:
            maxx, maxy = max(maxx, p[0]), max(maxy, p[1])
    for r, *_ in G.labels:
        maxx, maxy = max(maxx, r[2]), max(maxy, r[3])
    img = Image.new("RGB", (int((maxx + 40) * SC + 40), int((maxy + 40) * SC + 40)), "white")
    d = ImageDraw.Draw(img)
    for v in sorted(G.verts, key=lambda v: len(G.anc[v.id])):
        st, sh = v.st, v.shape
        x, y, w, h = v.ax, v.ay, v.w, v.h
        base = st.get("_base", "")
        if sh == "umlActor":
            cx = x + w / 2
            d.ellipse([P(cx - h * .12, y), P(cx + h * .12, y + h * .24)], outline="black", width=2)
            d.line([P(cx, y + h * .24), P(cx, y + h * .62)], fill="black", width=2)
            d.line([P(x, y + h * .36), P(x + w, y + h * .36)], fill="black", width=2)
            d.line([P(x, y + h), P(cx, y + h * .62), P(x + w, y + h)], fill="black", width=2)
            text_block(d, cx, y + h + 10, v.value)
            continue
        if sh == "umlLifeline":
            size = float(st.get("size", 40))
            cx = x + w / 2
            dashed(d, [(cx, y + size), (cx, y + h)], 1)
            if st.get("participant") == "umlActor":
                d.ellipse([P(cx - 5, y), P(cx + 5, y + 10)], outline="black", width=2)
                d.line([P(cx, y + 10), P(cx, y + 26)], fill="black", width=2)
                d.line([P(cx - 10, y + 15), P(cx + 10, y + 15)], fill="black", width=2)
                d.line([P(cx - 10, y + 40), P(cx, y + 26), P(cx + 10, y + 40)], fill="black", width=2)
                text_block(d, cx, y + size + 10, v.value)
            else:
                d.rectangle([P(x, y), P(x + w, y + size)], outline="black", width=2, fill="white")
                text_block(d, cx, y + size / 2, v.value)
            continue
        if base == "line":
            d.line([P(x, y + h / 2), P(x + w, y + h / 2)], fill="black", width=2)
            continue
        if base == "text":
            text_block(d, x + w / 2, y + h / 2, v.value)
            continue
        if base == "ellipse" or sh in ("endState",):
            fill = "black" if st.get("fillColor") in ("#000000", "#000") else "white"
            d.ellipse([P(x, y), P(x + w, y + h)], outline="black", width=2, fill=fill)
            if sh == "endState":
                d.ellipse([P(x + 4, y + 4), P(x + w - 4, y + h - 4)], fill="black")
        elif base == "rhombus":
            d.polygon([P(x + w / 2, y), P(x + w, y + h / 2), P(x + w / 2, y + h), P(x, y + h / 2)], outline="black",
                      fill="white")
        elif sh == "umlFrame":
            fw, fh = float(st.get("width", 60)), float(st.get("height", 26))
            d.rectangle([P(x, y), P(x + w, y + h)], outline="black", width=1)
            d.line([P(x + fw, y), P(x + fw, y + fh - 8), P(x + fw - 8, y + fh), P(x, y + fh)], fill="black", width=1)
            text_block(d, x + (fw - 4) / 2, y + fh / 2, v.value)
            continue
        elif base == "swimlane":
            ss = float(st.get("startSize", 26))
            d.rounded_rectangle([P(x, y), P(x + w, y + h)], radius=12 * SC if st.get("rounded") == "1" else 0,
                                outline="black", width=2, fill="white")
            d.line([P(x, y + ss), P(x + w, y + ss)], fill="black", width=1)
            text_block(d, x + w / 2, y + ss / 2, v.value)
            continue
        else:
            fill = "black" if st.get("fillColor") in ("#000000", "#000") else (None if st.get("fillColor") == "none" else "white")
            if st.get("rounded") == "1":
                d.rounded_rectangle([P(x, y), P(x + w, y + h)], radius=8 * SC, outline="black", width=2, fill=fill)
            else:
                d.rectangle([P(x, y), P(x + w, y + h)], outline="black", width=2, fill=fill)
        if v.value and plain(v.value).strip():
            if st.get("verticalAlign") == "top":
                import re
                rows = re.split(r"<br\s*/?>", v.value, flags=re.I)
                for i, r in enumerate(rows):
                    if st.get("align") == "left":
                        d.text(P(x + 6, y + 4 + i * 15.6), plain(r), fill="black", font=font(12), anchor="la")
                    else:
                        d.text(P(x + w / 2, y + 4 + i * 15.6), plain(r), fill="black", font=font(12), anchor="ma")
            else:
                text_block(d, x + w / 2, y + h / 2, v.value)
    for eid, (c, pts) in G.edges.items():
        st = c.st
        if st.get("dashed") == "1":
            dashed(d, pts)
        else:
            d.line([P(*p) for p in pts], fill="black", width=2)
        ea = st.get("endArrow", "classic")
        if ea and ea != "none":
            arrow(d, ea, st.get("endFill", "1") != "0", pts[-1], pts[-2])
        sa = st.get("startArrow", "none")
        if sa and sa != "none":
            arrow(d, sa, st.get("startFill", "1") != "0", pts[0], pts[1])
    for r, owner, dd, cell in G.labels:
        if cell.vertex and not cell.relative:
            continue
        d.rectangle([P(r[0], r[1]), P(r[2], r[3])], fill="#fffbe6", outline="#d0c080")
        text_block(d, (r[0] + r[2]) / 2, (r[1] + r[3]) / 2, cell.value, 11)
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    f, od = sys.argv[1], sys.argv[2]
    os.makedirs(od, exist_ok=True)
    for i, (name, model) in enumerate(load_pages(f)):
        if model is not None:
            render(name, model, os.path.join(od, "p%d.png" % (i + 1)))
