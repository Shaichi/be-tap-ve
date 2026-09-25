# -*- coding: utf-8 -*-
"""
layout.py - Bo cuc phan tang (Sugiyama) + dinh tuyen canh truc giao khong chong lan.

Dam bao (theo cau truc thuat toan):
  * Hinh khong bao gio chong nhau (moi tang xep hinh theo thu tu, co khoang cach toi thieu).
  * Canh khong di xuyen qua hinh: canh dai tang duoc chen "dummy node" giu cho rieng,
    doan ngang chi nam trong khe giua hai tang (khong co hinh nao o do).
  * Doan ngang cua cac canh khac nhau trong cung khe duoc xep vao cac "track" rieng
    -> khong co doan thang nao trung/de len nhau.
  * Nhan giua canh la mot "label dummy" co kich thuoc that -> nhan khong de len hinh/nhan khac.
  * Nhan dau canh (multiplicity/role) nam trong "zone" duoc danh rieng o dau khe.

Moi tinh toan duoc lam trong "khong gian bo cuc" huong TB (tren -> duoi);
huong LR duoc xu ly bang cach hoan vi truc x/y o dau vao va dau ra.
"""
from __future__ import annotations

import heapq
import re
import math
from collections import defaultdict

CFG = {
    "node_sep": 44,      # khoang cach ngang toi thieu giua 2 hinh cung tang
    "dummy_sep": 18,     # khoang cach khi co dummy (duong di qua)
    "dummy_w": 12,
    "min_gap": 34,       # chieu cao toi thieu cua khe giua 2 tang
    "track_sep": 14,     # khoang cach giua cac track ngang
    "track_gap": 12,     # khoang ho toi thieu giua 2 doan ngang cung track
    "end_pad": 4,        # khoang cach tu cong den nhan dau canh
    "loop_w": 18,        # do rong vong self-loop
    "lane_pad": 26,      # le trong moi swimlane (hai ben noi dung)
    "side_off": 16,      # khoang tu goc trai/phai hinh thoi den doan doc cua canh di ra/vao goc do
    "port_gap": 12,      # khoang toi thieu giua 2 cong canh nhau khi phai gian cong vi nhan dau canh
    "lab_slack": 10,     # nhan dau canh cua cong ngoai cung duoc phep lo ra ngoai mep hinh toi da ngan nay
    "sweeps": 24,
    "coord_iters": 16,
}


class LV:
    """Dinh trong do thi bo cuc (hinh that hoac dummy)."""

    def __init__(self, id, w, h, dummy=False, node=None, edge=None, is_label=False):
        self.id = id
        self.w = float(w)
        self.h = float(h)
        self.dummy = dummy
        self.node = node
        self.edge = edge
        self.is_label = is_label
        self.rank = 0
        self.cat = 0
        self.lane = 0
        self.sr = [0.0, 0.0, float(w), float(h)]
        self.perim = "rect"
        self.side = False      # hinh thoi duoc phep dung goc trai/phai lam cong
        self.up = []
        self.down = []


class Seg:
    __slots__ = ("e", "a", "b", "ax", "bx", "track", "aside", "bside")

    def __init__(self, e, a, b):
        self.e, self.a, self.b = e, a, b
        self.ax = self.bx = None
        self.track = None
        self.aside = self.bside = 0   # -1/+1: canh ra/vao o goc trai/phai cua hinh thoi (0: canh tren/duoi)


class LEdge:
    """Canh dau vao cho bo cuc. Kich thuoc nhan tinh theo toa do THAT (w, h)."""

    def __init__(self, id, u, v, lrev=False, lab=None, slab=None, dlab=None):
        self.id, self.u, self.v = id, u, v
        self.lrev = lrev          # True: dat v "truoc" u trong bo cuc (vd generalization: cha o tren)
        self.lab, self.slab, self.dlab = lab, slab, dlab
        # ket qua (toa do that, tuong doi goc cua tang/level)
        self.pts = []
        self.lab_c = None
        self.src_c = None
        self.dst_c = None


def layered_layout(elems, ledges, direction="TB", cat_margin=None, cfg=None, lanes=None):
    """
    elems : list co thuoc tinh id, w, h, sr=(sx,sy,sw,sh), perim, category (int|None), lane (int|None)
    ledges: list[LEdge]
    lanes : None hoac list do rong toi thieu (theo truc ngang cua bo cuc) cua tung lan (swimlane/partition).
            Khi co lanes, moi lan la mot dai rieng doc theo truc rank; hinh cua lan nao nam tron trong dai do.
    Tra ve dict(w, h, cat_boxes, lanes) ; gan el.fx, el.fy (goc footprint) va cap nhat el.w/h/sr.
    """
    C = dict(CFG)
    if cfg:
        C.update(cfg)
    LR = direction.upper() == "LR"
    LANES = bool(lanes)

    def sw(a, b):
        return (b, a) if LR else (a, b)

    V = {}
    order = []
    for el in elems:
        w, h = sw(el.w, el.h)
        sx, sy = sw(el.sr[0], el.sr[1])
        ssw, ssh = sw(el.sr[2], el.sr[3])
        v = LV(el.id, w, h, node=el)
        v.sr = [sx, sy, ssw, ssh]
        v.perim = getattr(el, "perim", "rect")
        v.cat = el.category if getattr(el, "category", None) is not None else 0
        if LANES:
            ln = getattr(el, "lane", None)
            v.lane = min(max(int(ln or 0), 0), len(lanes) - 1)
        V[el.id] = v
        order.append(el.id)

    for e in ledges:
        e._lab = sw(*e.lab) if e.lab else None
        e._slab = sw(*e.slab) if e.slab else None
        e._dlab = sw(*e.dlab) if e.dlab else None
        e.pts, e.lab_c, e.src_c, e.dst_c = [], None, None, None

    loops = defaultdict(list)
    normal = []
    for e in ledges:
        if e.u == e.v:
            loops[e.u].append(e)
        else:
            normal.append(e)

    # ---------------------------------------------------------- self loops
    for vid, ls in loops.items():
        v = V[vid]
        sx, sy, ssw, ssh = v.sr
        n = len(ls)
        prev = -1e9
        lw_max = 0.0
        info = []
        for k, e in enumerate(ls):
            lw, lh = e._lab or (0.0, 0.0)
            lw_max = max(lw_max, lw)
            ya = ssh * (k + 0.22) / n
            yb = ssh * (k + 0.78) / n
            c = max((ya + yb) / 2, prev + 4 + lh / 2)
            prev = c + lh / 2
            info.append((ya, yb, c, lh))
        top_ext = max([lh / 2 - c for (_, _, c, lh) in info] + [0.0])
        bot_ext = max(prev - ssh, 0.0)
        nsy = max(sy, top_ext)
        v.h = max(v.h - sy + nsy, nsy + ssh + bot_ext)
        v.w = max(v.w, sx + ssw + C["loop_w"] + 8 + lw_max + 6)
        v.sr = [sx, nsy, ssw, ssh]
        for e, inf in zip(ls, info):
            e._loop = inf

    # ---------------------------------------------------------- orientation + cycle breaking
    for e in normal:
        a, b = (e.v, e.u) if e.lrev else (e.u, e.v)
        if V[a].cat > V[b].cat:
            a, b = b, a
        e._lu, e._lv = a, b

    out = defaultdict(list)
    for e in normal:
        out[e._lu].append(e)
    color = {}
    for s in order:
        if s in color:
            continue
        color[s] = 1
        stack = [(s, iter(list(out[s])))]
        while stack:
            x, it = stack[-1]
            e = next(it, None)
            if e is None:
                color[x] = 2
                stack.pop()
                continue
            if e._lu != x:
                continue
            y = e._lv
            if color.get(y) == 1:
                e._lu, e._lv = e._lv, e._lu          # canh nguoc -> dao
            elif y not in color:
                color[y] = 1
                stack.append((y, iter(list(out[y]))))
    for e in normal:
        e._flip = e._lu != e.u

    # ---------------------------------------------------------- ranking
    preds = defaultdict(list)
    succs = defaultdict(list)
    for e in normal:
        preds[e._lv].append(e._lu)
        succs[e._lu].append(e._lv)
    idx = {x: i for i, x in enumerate(order)}
    indeg = {x: 0 for x in order}
    for e in normal:
        indeg[e._lv] += 1
    heap = [(idx[x], x) for x in order if indeg[x] == 0]
    heapq.heapify(heap)
    topo = []
    while heap:
        _, x = heapq.heappop(heap)
        topo.append(x)
        for y in succs[x]:
            indeg[y] -= 1
            if indeg[y] == 0:
                heapq.heappush(heap, (idx[y], y))
    if len(topo) != len(order):  # an toan
        topo += [x for x in order if x not in set(topo)]

    rank = {}
    catbase, catmax = {}, {}
    cats = sorted(set(V[x].cat for x in order))
    base = 0
    for c in cats:
        mem = [x for x in topo if V[x].cat == c]
        catbase[c] = base
        for x in mem:
            rank[x] = max([base] + [rank[p] + 1 for p in preds[x] if p in rank])
        base = max(rank[x] for x in mem) + 1
    for i, c in enumerate(cats):
        catmax[c] = (catbase[cats[i + 1]] - 1) if i + 1 < len(cats) else 10 ** 9
    for x in reversed(topo):
        if not preds[x] and succs[x]:
            c = V[x].cat
            rank[x] = min(catmax[c], max(catbase[c], min(rank[y] for y in succs[x]) - 1))

    if any(e._lab for e in normal):
        for x in rank:
            rank[x] *= 2

    R = max(rank.values()) if rank else 0
    layers = [[] for _ in range(R + 1)]
    for x in order:
        V[x].rank = rank[x]
        layers[rank[x]].append(x)

    for e in normal:
        ru, rv = rank[e._lu], rank[e._lv]
        ch = [e._lu]
        mid = (ru + rv) // 2 if e._lab else None
        for r in range(ru + 1, rv):
            isl = r == mid
            if isl:
                d = LV("\x00d%s#%d" % (e.id, r), e._lab[0] + 10, e._lab[1] + 6, True, None, e, True)
            else:
                d = LV("\x00d%s#%d" % (e.id, r), C["dummy_w"], 0, True, None, e, False)
            d.rank = r
            d.cat = -1
            d.lane = V[e._lv].lane      # doan doc cua canh dai di trong lan cua dau duoi
            V[d.id] = d
            layers[r].append(d.id)
            ch.append(d.id)
        ch.append(e._lv)
        e._chain = ch
        for a, b in zip(ch, ch[1:]):
            V[a].down.append(b)
            V[b].up.append(a)

    # ---------------------------------------------------------- ordering (crossing reduction)
    pos = {}

    def reindex(r):
        for i, x in enumerate(layers[r]):
            pos[x] = i

    for r in range(R + 1):
        layers[r].sort(key=lambda x: V[x].lane)   # on dinh; lan luon la khoa sap xep dau tien
        reindex(r)

    def bary(r, attr):
        L = layers[r]

        def key(x):
            nb = getattr(V[x], attr)
            return (sum(pos[y] for y in nb) / len(nb)) if nb else pos[x]

        L.sort(key=lambda x: (V[x].lane, key(x), pos[x]))
        reindex(r)

    def crossings():
        tot = 0
        for r in range(R):
            segs = sorted((pos[a], pos[b]) for a in layers[r] for b in V[a].down)
            for i in range(len(segs)):
                ai, bi = segs[i]
                for j in range(i + 1, len(segs)):
                    if ai != segs[j][0] and bi > segs[j][1]:
                        tot += 1
        return tot

    def pc(a, b):
        c = 0
        for attr in ("up", "down"):
            A = getattr(V[a], attr)
            B = getattr(V[b], attr)
            for x in A:
                px = pos[x]
                for y in B:
                    if px > pos[y]:
                        c += 1
        return c

    def transpose():
        for _ in range(4):
            improved = False
            for r in range(R + 1):
                L = layers[r]
                for i in range(len(L) - 1):
                    a, b = L[i], L[i + 1]
                    if V[a].lane == V[b].lane and pc(a, b) > pc(b, a):
                        L[i], L[i + 1] = b, a
                        pos[a], pos[b] = i + 1, i
                        improved = True
            if not improved:
                break

    for r in range(1, R + 1):
        bary(r, "up")
    transpose()
    best = crossings()
    best_layers = [l[:] for l in layers]
    for it in range(C["sweeps"]):
        if best == 0:
            break
        if it % 2 == 0:
            for r in range(1, R + 1):
                bary(r, "up")
        else:
            for r in range(R - 1, -1, -1):
                bary(r, "down")
        transpose()
        c = crossings()
        if c < best:
            best, best_layers = c, [l[:] for l in layers]
    layers = best_layers
    for r in range(R + 1):
        reindex(r)

    # hinh thoi (decision/merge) co >= 2 canh o cung mot phia: 2 dinh tren/duoi qua hep cho nhieu canh
    # -> cho phep dung them goc trai/phai, va noi rong khung bo cuc 2 ben de doan doc canh goc co cho rieng
    for x in order:
        v = V[x]
        if v.perim == "rhombus" and x not in loops and (len(v.up) >= 2 or len(v.down) >= 2):
            v.side = True
            v.w += 2 * C["side_off"]
            v.sr[0] += C["side_off"]

    # ---------------------------------------------------------- x coordinates (PAVA)
    def anchor(x):
        v = V[x]
        return 0.0 if v.dummy else v.sr[0] + v.sr[2] / 2 - v.w / 2

    def sep(a, b):
        return C["dummy_sep"] if (V[a].dummy or V[b].dummy) else C["node_sep"]

    def groups(L):
        """Cac nhom lien tiep cung lan trong mot tang (khong co lanes: ca tang la mot nhom)."""
        out, cur = [], []
        for x in L:
            if cur and LANES and V[x].lane != V[cur[-1]].lane:
                out.append(cur)
                cur = []
            cur.append(x)
        if cur:
            out.append(cur)
        return out

    X = {}
    for r in range(R + 1):
        for G in groups(layers[r]):
            cur = 0.0
            for i, x in enumerate(G):
                if i:
                    cur += (V[G[i - 1]].w + V[x].w) / 2 + sep(G[i - 1], x)
                X[x] = cur
            if LANES:  # moi lan co toa do rieng, can giua quanh 0
                for x in G:
                    X[x] -= cur / 2

    def place(r, mode):
        for G in groups(layers[r]):
            place_group(G, mode)

    def place_group(L, mode):
        n = len(L)
        o = [0.0]
        for i in range(1, n):
            o.append(o[-1] + (V[L[i - 1]].w + V[L[i]].w) / 2 + sep(L[i - 1], L[i]))
        tgt, wts = [], []
        for i, x in enumerate(L):
            v = V[x]
            if mode == "up":
                nb = v.up
            elif mode == "down":
                nb = v.down
            else:
                nb = v.up + v.down
            if LANES:  # chi can thang hang voi hang xom cung lan (lan khac nam o dai khac)
                nb = [y for y in nb if V[y].lane == v.lane]
            if nb:
                d = sum(X[y] + anchor(y) for y in nb) / len(nb) - anchor(x)
                wt = len(nb) * (3.0 if v.dummy else 1.0)
            else:
                d, wt = X[x], 0.05
            tgt.append(d - o[i])
            wts.append(wt)
        blocks = []
        for t, w in zip(tgt, wts):
            blocks.append([t, w, 1])
            while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
                v2, w2, c2 = blocks.pop()
                v1, w1, c1 = blocks.pop()
                blocks.append([(v1 * w1 + v2 * w2) / (w1 + w2), w1 + w2, c1 + c2])
        z = []
        for val, _, cnt in blocks:
            z += [val] * cnt
        for i, x in enumerate(L):
            X[x] = z[i] + o[i]

    for it in range(C["coord_iters"]):
        if it % 2 == 0:
            for r in range(1, R + 1):
                place(r, "up")
        else:
            for r in range(R - 1, -1, -1):
                place(r, "down")
    for r in range(R + 1):
        place(r, "both")
    for r in range(1, R + 1):
        place(r, "up")

    lane_band = []
    if LANES:
        # dat moi lan vao mot dai rieng: [start, start+width), noi dung can giua dai
        lo, hi = {}, {}
        for x in X:
            l = V[x].lane
            lo[l] = min(lo.get(l, 1e18), X[x] - V[x].w / 2)
            hi[l] = max(hi.get(l, -1e18), X[x] + V[x].w / 2)
        start = 0.0
        for l, minw in enumerate(lanes):
            content = (hi[l] - lo[l]) if l in lo else 0.0
            width = max(content + 2 * C["lane_pad"], float(minw))
            shift = start + (width - content) / 2 - lo.get(l, 0.0)
            for x in X:
                if V[x].lane == l:
                    X[x] += shift
            lane_band.append((start, start + width))
            start += width
    elif X:
        minx = min(X[x] - V[x].w / 2 for x in X)
        for x in X:
            X[x] -= minx

    bh = [max([V[x].h for x in layers[r]] + [0.0]) for r in range(R + 1)]

    # ---------------------------------------------------------- ports
    gap_segs = defaultdict(list)
    for e in normal:
        e._segs = []
        for a, b in zip(e._chain, e._chain[1:]):
            s = Seg(e, a, b)
            e._segs.append(s)
            gap_segs[V[a].rank].append(s)

    outs, ins = defaultdict(list), defaultdict(list)
    for r in gap_segs:
        for s in gap_segs[r]:
            if not V[s.a].dummy:
                outs[s.a].append(s)
            if not V[s.b].dummy:
                ins[s.b].append(s)

    def xrange_(x):
        v = V[x]
        left = X[x] - v.w / 2 + v.sr[0]
        return left, left + v.sr[2]

    def pmargin(v):
        f = {"ellipse": 0.22, "rhombus": 0.2}.get(v.perim)
        if f:
            return v.sr[2] * f
        return min(12.0, v.sr[2] * 0.2)

    used_side = defaultdict(set)

    def ulab(e):   # nhan o dau "layout-u"
        return e._dlab if e._flip else e._slab

    def vlab(e):
        return e._slab if e._flip else e._dlab

    def spread(x, ss, pos, labs, lo, hi):
        """Nhan dau canh nam ben phai cong -> cong ke tiep phai cach >= do rong nhan.
        Giai min sum (p-u)^2 voi p[i+1]-p[i] >= g[i] (PAVA); khong du cho -> ghi nhu cau noi rong."""
        k = len(pos)
        pad = C["end_pad"]
        g = [(pad + labs[i][0] + 8) if labs[i] else C["port_gap"] for i in range(k - 1)]
        last = labs[-1]
        if all(pos[i + 1] - pos[i] >= g[i] for i in range(k - 1)) and (
                not last or pos[-1] + pad + last[0] <= hi + C["lab_slack"]):
            return pos
        c = [0.0]
        for gi in g:
            c.append(c[-1] + gi)
        blocks = []  # PAVA tren q = p - c (khong giam)
        for i in range(k):
            blocks.append([pos[i] - c[i], 1])
            while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
                s2, n2 = blocks.pop()
                blocks[-1][0] += s2
                blocks[-1][1] += n2
        q = []
        for s_, n_ in blocks:
            q += [s_ / n_] * n_
        m0 = pmargin(V[x]) if V[x].perim in ("ellipse", "rhombus") else min(6.0, pmargin(V[x]))
        L = lo + m0
        Hb = (hi + C["lab_slack"] - pad - last[0]) if last else hi - m0
        Hq = Hb - c[-1]
        if L > Hq:   # khong du cho: can hinh rong hon
            need_w[x] = max(need_w.get(x, 0.0), (hi - lo) + (L - Hq) + 4)
            mid = (L + Hq) / 2
            return [mid + c[i] for i in range(k)]
        return [min(max(qi, L), Hq) + c[i] for i, qi in enumerate(q)]

    need_w = {}

    def assign(dct, attr, other):
        side = "aside" if attr == "ax" else "bside"
        for x, ss in dct.items():
            ss.sort(key=lambda s: X[getattr(s, other)] + anchor(getattr(s, other)))
            lo, hi = xrange_(x)
            if V[x].side and len(ss) >= 2:
                # canh co dau kia gan nhat giu o dinh; canh xa nhat moi ben (neu dau kia nam han ve ben do)
                # ra/vao goc trai/phai -> khong con 2 mui ten dinh nhau o dinh hinh thoi
                def ox(s):
                    return X[getattr(s, other)] + anchor(getattr(s, other))
                cx, off = (lo + hi) / 2, C["side_off"]
                tip = min(ss, key=lambda s: abs(ox(s) - cx))
                rest = list(ss)
                for s, sgn in ((ss[0], -1), (ss[-1], 1)):
                    if s is tip or sgn in used_side[x]:
                        continue
                    if (sgn < 0 and ox(s) < lo - off) or (sgn > 0 and ox(s) > hi + off):
                        setattr(s, side, sgn)
                        setattr(s, attr, lo - off if sgn < 0 else hi + off)
                        used_side[x].add(sgn)
                        rest.remove(s)
                ss = rest
            m = pmargin(V[x])
            k = len(ss)
            pos = [lo + m + (hi - lo - 2 * m) * (i + 1) / (k + 1) for i in range(k)]
            labs = [ulab(s.e) if attr == "ax" else vlab(s.e) for s in ss]
            if any(labs):
                pos = spread(x, ss, pos, labs, lo, hi)
            for s, p in zip(ss, pos):
                setattr(s, attr, p)

    assign(outs, "ax", "b")
    assign(ins, "bx", "a")

    def cax(s):
        return X[s.a] if V[s.a].dummy else s.ax

    def cbx(s):
        return X[s.b] if V[s.b].dummy else s.bx

    def lab_block(s, nx):
        """Dat cong vao cua s tai nx co lam cong nam trong nhan dau canh khac (hoac nhan cua s phu cong khac)?"""
        pad = C["end_pad"]
        own = vlab(s.e)
        for t in ins.get(s.b, []):
            if t is s or t.bside:
                continue
            tl = vlab(t.e)
            if tl and t.bx + pad - 3 <= nx <= t.bx + pad + tl[0] + 3:
                return True
            if own and nx + pad - 3 <= t.bx <= nx + pad + own[0] + 3:
                return True
        return False

    def move_b(s, delta, ss=()):
        if V[s.b].dummy:
            X[s.b] += delta
        elif s.bside:              # doan doc vao goc: chi day ra xa hinh
            s.bx += s.bside * abs(delta)
        else:
            lo, hi = xrange_(s.b)
            m = pmargin(V[s.b]) * 0.5
            cands = [s.bx + k * delta for k in (1, -1, 2, -2, 3, -3)]
            cands = [nx for nx in cands if lo + m <= nx <= hi - m]
            good = [nx for nx in cands if not lab_block(s, nx)
                    and all(abs(cax(t) - nx) >= 5 for t in ss if t.e is not s.e)
                    and all(abs(t.bx - nx) >= 5 for t in ins.get(s.b, []) if t is not s and not t.bside)]
            if good:
                s.bx = good[0]
                return
            nx = s.bx + delta
            if nx > hi - m or nx < lo + m:
                nx = s.bx - delta
            s.bx = nx

    ntr = {}
    for r in range(R):
        ss = gap_segs.get(r, [])
        # 1) bo cac "khuc gay" nho
        for s in ss:
            ax, bx = cax(s), cbx(s)
            if 0 < abs(ax - bx) < 6:
                if V[s.b].dummy:
                    X[s.b] = ax
                elif s.bside:
                    lo, hi = xrange_(s.b)
                    if (s.bside < 0 and ax <= lo - 8) or (s.bside > 0 and ax >= hi + 8):
                        s.bx = ax
                else:
                    lo, hi = xrange_(s.b)
                    if lo + 4 <= ax <= hi - 4 and not lab_block(s, ax):
                        s.bx = ax
        # 2) tach cac doan doc trung x cua 2 canh khac nhau
        for _ in range(6):
            moved = False
            for s in ss:
                bx = cbx(s)
                for t in ss:
                    if t.e is s.e:
                        continue
                    if abs(cax(t) - bx) < 5:
                        move_b(s, 8.0, ss)
                        moved = True
                        break
            if not moved:
                break
        # 3) gan track cho doan ngang
        ivs = []
        for s in ss:
            ax, bx = cax(s), cbx(s)
            s.ax, s.bx = ax, bx
            s.track = None
            if abs(ax - bx) > 0.5:
                ivs.append((min(ax, bx), max(ax, bx), s))

        def tkey(t):
            s = t[2]
            return (0, -s.ax) if s.bx > s.ax else (1, s.ax)

        placed = []
        for lo, hi, s in sorted(ivs, key=tkey):
            tr = 0
            for l2, h2, t2 in placed:
                if not (h2 + C["track_gap"] <= lo or hi + C["track_gap"] <= l2):
                    tr = max(tr, t2 + 1)
            s.track = tr
            placed.append((lo, hi, tr))
        ntr[r] = (max(t for _, _, t in placed) + 1) if placed else 0

    # ---------------------------------------------------------- zones & y coordinates
    top_zone = [0.0] * (R + 1)
    bot_zone = [0.0] * (R + 1)
    for r in range(R):
        for s in gap_segs.get(r, []):
            if not V[s.a].dummy and ulab(s.e):
                v = V[s.a]
                sb = (bh[r] - v.h) / 2 + v.sr[1] + v.sr[3]
                need = sb + C["end_pad"] + ulab(s.e)[1] - bh[r]
                top_zone[r] = max(top_zone[r], need + 3)
            if not V[s.b].dummy and vlab(s.e):
                v = V[s.b]
                st = (bh[r + 1] - v.h) / 2 + v.sr[1]
                need = vlab(s.e)[1] + C["end_pad"] - st
                bot_zone[r] = max(bot_zone[r], need + 3)

    if cat_margin:
        for c, (before, after) in cat_margin.items():
            rs = [rank[x] for x in order if V[x].cat == c]
            if not rs:
                continue
            r0, r1 = min(rs), max(rs)
            if r0 > 0:
                bot_zone[r0 - 1] += before
            if r1 < R:
                top_zone[r1] += after

    inner = []
    gapH = []
    for r in range(R):
        nt = ntr.get(r, 0)
        inn = max(C["min_gap"], (nt + 1) * C["track_sep"])
        inner.append(inn)
        gapH.append(top_zone[r] + inn + bot_zone[r])
    Y = []
    y = 0.0
    for r in range(R + 1):
        Y.append(y)
        y += bh[r] + (gapH[r] if r < R else 0.0)
    total_h = y

    def track_y(s):
        r = V[s.a].rank
        nt = ntr.get(r, 0)
        return Y[r] + bh[r] + top_zone[r] + (s.track + 1) * inner[r] / (nt + 1)

    def shape_box(x):
        v = V[x]
        left = X[x] - v.w / 2 + v.sr[0]
        top = Y[v.rank] + (bh[v.rank] - v.h) / 2 + v.sr[1]
        return left, top, v.sr[2], v.sr[3]

    def port_y(x, px, side):
        v = V[x]
        left, top, w, h = shape_box(x)
        cx, cy = left + w / 2, top + h / 2
        if v.perim == "ellipse":
            dy = (h / 2) * math.sqrt(max(0.0, 1 - ((px - cx) / (w / 2)) ** 2))
        elif v.perim == "rhombus":
            dy = (h / 2) * max(0.0, 1 - abs(px - cx) / (w / 2))
        else:
            dy = h / 2
        return cy + dy if side == "bottom" else cy - dy

    # ---------------------------------------------------------- paths (layout space)
    def corner(x, sgn):
        left, top, w, h = shape_box(x)
        return (left if sgn < 0 else left + w), top + h / 2

    for e in normal:
        pts = []
        for i, s in enumerate(e._segs):
            if i == 0:
                if s.aside:
                    px, py = corner(s.a, s.aside)
                    pts += [(px, py), (s.ax, py)]
                else:
                    pts.append((s.ax, port_y(s.a, s.ax, "bottom")))
            if s.track is not None:
                ty = track_y(s)
                pts.append((s.ax, ty))
                pts.append((s.bx, ty))
            if not V[s.b].dummy:
                if s.bside:
                    px, py = corner(s.b, s.bside)
                    pts += [(s.bx, py), (px, py)]
                else:
                    pts.append((s.bx, port_y(s.b, s.bx, "top")))
        e._pts = _simplify(pts)
        e._labc = None
        for d in e._chain[1:-1]:
            if V[d].is_label:
                r = V[d].rank
                e._labc = (X[d], Y[r] + bh[r] / 2)
        if e._lab and e._labc is None:
            e._labc = _midpoint(e._pts)
        e._uc = e._vc = None
        ul, vl = ulab(e), vlab(e)
        if ul:
            s0 = e._segs[0]
            e._uc = (s0.ax + C["end_pad"] + ul[0] / 2, e._pts[0][1] + C["end_pad"] + ul[1] / 2)
        if vl:
            sl = e._segs[-1]
            e._vc = (sl.bx + C["end_pad"] + vl[0] / 2, e._pts[-1][1] - C["end_pad"] - vl[1] / 2)

    for vid, ls in loops.items():
        left, top, w, h = shape_box(vid)
        right = left + w
        for e in ls:
            ya, yb, c, lh = e._loop
            lx = right + C["loop_w"]
            e._pts = [(right, top + ya), (lx, top + ya), (lx, top + yb), (right, top + yb)]
            e._labc = (lx + 8 + e._lab[0] / 2, top + c) if e._lab else None
            e._uc = e._vc = None
            e._flip = False

    # ---------------------------------------------------------- back to real space
    def T(p):
        return (p[1], p[0]) if LR else (p[0], p[1])

    def Trect(x, y, w, h):
        return (y, x, h, w) if LR else (x, y, w, h)

    maxx = 0.0
    for x in order:
        v = V[x]
        el = v.node
        lx = X[x] - v.w / 2
        ly = Y[v.rank] + (bh[v.rank] - v.h) / 2
        maxx = max(maxx, lx + v.w)
        el.fx, el.fy = T((lx, ly))
        el.w, el.h = sw(v.w, v.h)
        sx, sy = sw(v.sr[0], v.sr[1])
        ssw, ssh = sw(v.sr[2], v.sr[3])
        el.sr = (sx, sy, ssw, ssh)
    for x in X:
        if V[x].dummy:
            maxx = max(maxx, X[x] + V[x].w / 2)

    for e in ledges:
        pts = [T(p) for p in e._pts]
        uc = T(e._uc) if e._uc else None
        vc = T(e._vc) if e._vc else None
        if e._flip:
            pts.reverse()
            uc, vc = vc, uc
        e.pts = pts
        e.lab_c = T(e._labc) if e._labc else None
        e.src_c, e.dst_c = uc, vc

    cat_boxes = {}
    for c in cats:
        rs = [rank[x] for x in order if V[x].cat == c]
        if not rs:
            continue
        r0, r1 = min(rs), max(rs)
        vs = [x for r in range(r0, r1 + 1) for x in layers[r]]
        x0 = min(X[x] - V[x].w / 2 for x in vs)
        x1 = max(X[x] + V[x].w / 2 for x in vs)
        cat_boxes[c] = Trect(x0, Y[r0], x1 - x0, Y[r1] + bh[r1] - Y[r0])

    if lane_band:
        maxx = max(maxx, lane_band[-1][1])
    W, H = sw(maxx, total_h)
    return {"w": W, "h": H, "cat_boxes": cat_boxes, "crossings": best,
            "lanes": [Trect(a, 0.0, b - a, total_h) for a, b in lane_band],
            # do rong (theo truc ngang cua bo cuc) can co de nhan dau canh khong bi canh ke ben cat
            "need_w": {} if LR else dict(need_w)}


def _simplify(pts):
    out = []
    for p in pts:
        if out and abs(out[-1][0] - p[0]) < 0.01 and abs(out[-1][1] - p[1]) < 0.01:
            continue
        out.append(p)
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        if (abs(a[0] - b[0]) < 0.01 and abs(b[0] - c[0]) < 0.01) or (
            abs(a[1] - b[1]) < 0.01 and abs(b[1] - c[1]) < 0.01
        ):
            out.pop(i)
        else:
            i += 1
    return out


def _midpoint(pts):
    L = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    tot = sum(L)
    if not tot:
        return pts[0]
    half = tot / 2
    for (a, b), l in zip(zip(pts, pts[1:]), L):
        if half <= l and l > 0:
            t = half / l
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        half -= l
    return pts[-1]


def label_geometry(pts, c):
    """Tinh (x tuong doi -1..1, offset) de dat nhan canh draw.io tai tam c."""
    if not pts or c is None:
        return 0.0, (0.0, 0.0)
    L = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    tot = sum(L) or 1.0
    best = None
    cum = 0.0
    for (a, b), l in zip(zip(pts, pts[1:]), L):
        if l == 0:
            continue
        t = ((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / (l * l)
        t = max(0.0, min(1.0, t))
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        d = math.dist(p, c)
        if best is None or d < best[0] - 1e-6:
            best = (d, cum + t * l, p)
        cum += l
    if best is None:
        return 0.0, (c[0] - pts[0][0], c[1] - pts[0][1])
    _, along, p = best
    return 2 * along / tot - 1, (c[0] - p[0], c[1] - p[1])


# =============================================================================== tree (site map)
TREE = {
    "hgap": 50,      # khe ngang giua 2 cot
    "vgap": 20,      # khe doc toi thieu giua 2 hinh cung cot
    "top_gap": 36,   # khe giua hinh va con "top" (dat ngay phia tren, cung cot)
    "stub": 14,      # tam con up/down cach mep hinh cha it nhat ngan nay (truc doc nhin thay duoc)
    "grid_m": 12,    # le cua bo dinh tuyen canh ngoai cay (khoang cach duong di toi hinh)
    "bend": 40,      # phat moi lan be goc (bo dinh tuyen)
}


def _side_tokens(e, el_sp):
    s = str((getattr(e, "rel", None) or {}).get("side") or (el_sp or {}).get("side") or "").lower()
    return {t for t in re.split(r"[\s,_\-/]+", s) if t}


def tree_layout(elems, ledges, root=None, warns=None, cfg=None):
    """Bo cuc cay kieu so do trang (site map / navigation map), goc ben trai, nhanh lon sang phai.

    * Moi man hinh con nam tren mot hang rieng; con dau tien cung hang voi cha (mui ten ngang thang),
      cac con khac xep xuong duoi, noi bang MOT duong truc doc chung di ra tu day hinh cha.
    * Cac hinh cung do sau thang cot (can giua theo cot).
    * `side` (tren quan he hoac tren phan tu con): "up" (xep phia tren, truc di ra tu dinh hinh cha),
      "down", "same" (cung hang), "top" (ngay phia tren, cung cot), "left" (nhanh sang trai - chi o goc;
      ket hop duoc: "left-up", "left-down").
    * `"branch": "side"` tren phan tu cha: con up/down noi tu CANH BEN cua cha qua khe giua 2 cot (nhanh
      quat), khong chiem cot cua cha -> gon hon; mac dinh "bottom": truc doc di ra tu day/dinh hinh cha.
    * Canh khong thuoc cay (quay lai, noi tat) -> dinh tuyen truc giao tranh hinh (A* tren luoi Hanan).
    Ket qua giong layered_layout: gan el.fx/el.fy, e.pts/lab_c/src_c/dst_c; tra dict(w, h, ...).
    """
    C = dict(TREE)
    if cfg:
        C.update(cfg)
    warns = warns if warns is not None else []
    E = {el.id: el for el in elems}
    order = [el.id for el in elems]
    out_e = defaultdict(list)
    indeg = defaultdict(int)
    for e in ledges:
        e.pts, e.lab_c, e.src_c, e.dst_c = [], None, None, None
        if e.u != e.v:
            out_e[e.u].append(e)
            indeg[e.v] += 1

    # ------------------------------------------------ cay khung (BFS theo thu tu quan he)
    parent_e = {}
    kids = defaultdict(list)
    seen = set()
    roots = []

    def bfs(r):
        roots.append(r)
        seen.add(r)
        q = [r]
        while q:
            x = q.pop(0)
            for e in out_e[x]:
                if e.v not in seen:
                    seen.add(e.v)
                    parent_e[e.v] = e
                    kids[x].append(e)
                    q.append(e.v)

    if root is not None and str(root) not in E:
        warns.append("root '%s' khong ton tai -> tu chon man hinh goc." % root)
        root = None
    if root is None and order:
        root = ([x for x in order if not indeg[x]] or order)[0]
    if root is not None:
        bfs(str(root))
    for x in order:
        if x not in seen and not indeg[x]:
            bfs(x)
    for x in order:
        if x not in seen:
            bfs(x)

    # ------------------------------------------------ phan loai con: huong (dir) + vi tri (pos)
    dir_of = {r: 1 for r in roots}
    pos_of = {}
    for r in roots:
        q = [r]
        while q:
            x = q.pop(0)
            first = {1: True, -1: True}
            info = []
            for e in kids[x]:
                t = _side_tokens(e, E[e.v].sp)
                d = dir_of[x]
                if "left" in t or "right" in t:
                    want = -1 if "left" in t else 1
                    if want != d and x not in roots:
                        warns.append("side '%s' cua %s->%s: chi man hinh goc moi re nhanh nguoc chieu -> bo qua."
                                     % ("left" if want < 0 else "right", x, e.v))
                    else:
                        d = want
                p = next((k for k in ("top", "up", "down", "same") if k in t), None)
                info.append((e, d, p))
            for e, d, p in info:           # "same" tuong minh chiem hang cua cha truoc
                if p == "same":
                    pos_of[e.v] = "same" if first[d] else "down"
                    first[d] = False
            for e, d, p in info:
                if p is None:
                    p = "same" if first[d] else "down"
                    if p == "same":
                        first[d] = False
                pos_of.setdefault(e.v, p)
                dir_of[e.v] = d
                q.append(e.v)

    # ------------------------------------------------ do sau (cot)
    depth = {}
    for r in roots:
        depth[r] = 0
        q = [r]
        while q:
            x = q.pop(0)
            for e in kids[x]:
                depth[e.v] = depth[x] if pos_of[e.v] == "top" else depth[x] + dir_of[e.v]
                q.append(e.v)

    # ------------------------------------------------ hang (y): contour [tren, duoi] theo tung cot
    vg = C["vgap"]
    off = {}

    def merge(M, B, o):
        for d, (a, b) in B.items():
            if d in M:
                M[d] = [min(M[d][0], a + o), max(M[d][1], b + o)]
            else:
                M[d] = [a + o, b + o]

    def below(M, B, gap_at=None):
        o = -math.inf
        for d, (a, b) in B.items():
            if d in M:
                o = max(o, M[d][1] - a + (gap_at or {}).get(d, vg))
        return o

    def above(M, B, gap_at=None):
        o = math.inf
        for d, (a, b) in B.items():
            if d in M:
                o = min(o, M[d][0] - b - (gap_at or {}).get(d, vg))
        return o

    ups_via_gap = {}
    fan = {x: str(E[x].sp.get("branch", "")).lower() in ("side", "fan") for x in order}

    def block(x):
        el = E[x]
        d = depth[x]
        h = el.h
        M = {d: [-h / 2, h / 2]}
        ch = kids[x]
        tops = [e for e in ch if pos_of[e.v] == "top"]
        side = fan[x]
        for e in ch:
            if pos_of[e.v] == "same":
                off[e.v] = 0.0
                merge(M, block(e.v), 0.0)
        last = None
        for e in ch:
            if pos_of[e.v] == "down":
                B = block(e.v)
                o = max(h / 2 + C["stub"], below(M, B))
                off[e.v] = last = o
                merge(M, B, o)
        if last is not None and not side:  # giu cot cua cha cho truc doc
            M[d][1] = max(M[d][1], last + vg / 2)
        ups_via_gap[x] = bool(tops) and not side
        first = None
        lim = -(h / 2 + C["top_gap"] / 2 + C["stub"]) if ups_via_gap[x] else -(h / 2 + C["stub"])
        for e in reversed(ch):
            if pos_of[e.v] == "up":
                B = block(e.v)
                o = min(lim, above(M, B))
                off[e.v] = first = o
                merge(M, B, o)
        if first is not None and not tops and not side:
            M[d][0] = min(M[d][0], first - vg / 2)
        for e in tops:
            B = block(e.v)
            o = min(-(h / 2 + C["top_gap"] + E[e.v].h / 2), above(M, B, {d: C["top_gap"]}))
            off[e.v] = o
            merge(M, B, o)
        return M

    Y = {}
    Mall = {}
    for r in roots:
        B = block(r)
        if not Mall:
            o = 0.0
        else:
            o = below(Mall, B, {k: vg * 2 for k in B})
            if o == -math.inf:
                o = max(v[1] for v in Mall.values()) - min(v[0] for v in B.values()) + vg * 2
        merge(Mall, B, o)
        Y[r] = o
        q = [r]
        while q:
            x = q.pop(0)
            for e in kids[x]:
                Y[e.v] = Y[x] + off[e.v]
                q.append(e.v)

    # ------------------------------------------------ cot (x): can giua theo cot
    colw = defaultdict(float)
    for x in order:
        colw[depth[x]] = max(colw[depth[x]], E[x].w)
    gapn = defaultdict(lambda: float(C["hgap"]))   # gapn[d]: khe giua cot d va cot ke ben phia goc
    for v, e in parent_e.items():
        if e.lab and pos_of[v] != "top":
            gapn[depth[v]] = max(gapn[depth[v]], e.lab[0] + 24)
    ds = sorted(colw)
    XC = {0: 0.0}
    for d in [k for k in ds if k > 0]:
        XC[d] = XC[d - 1] + colw[d - 1] / 2 + gapn[d] + colw[d] / 2
    for d in sorted([k for k in ds if k < 0], reverse=True):
        XC[d] = XC[d + 1] - colw[d + 1] / 2 - gapn[d] - colw[d] / 2

    R = {}
    for x in order:
        el = E[x]
        R[x] = [XC[depth[x]] - el.w / 2, Y[x] - el.h / 2, el.w, el.h]
    x0 = min(r[0] for r in R.values())
    y0 = min(r[1] for r in R.values())
    for r in R.values():
        r[0] -= x0
        r[1] -= y0
    for k in XC:
        XC[k] -= x0

    def col_edge(d, s):  # mep cot d ve phia s (+1 phai, -1 trai)
        return XC[d] + s * colw[d] / 2

    # ------------------------------------------------ canh cua cay
    segs = []       # (p, q, nguon) - de bo dinh tuyen tranh chong khit

    def add(e, pts, lab_c=None):
        e.pts = pts
        e.lab_c = lab_c
        for p, q in zip(pts, pts[1:]):
            segs.append((p, q, e.u))

    def lab_at(e, xa, xb, y):
        return ((xa + xb) / 2, y - e.lab[1] / 2 - 2) if e.lab else None

    for v, e in parent_e.items():
        u = e.u
        ru, rv = R[u], R[v]
        s = dir_of[v]
        cu = (ru[0] + ru[2] / 2, ru[1] + ru[3] / 2)
        cv = (rv[0] + rv[2] / 2, rv[1] + rv[3] / 2)
        near = rv[0] if s > 0 else rv[0] + rv[2]
        p = pos_of[v]
        if p == "same":
            xa = ru[0] + ru[2] if s > 0 else ru[0]
            add(e, [(xa, cu[1]), (near, cv[1])], lab_at(e, xa, near, cv[1]))
        elif p in ("up", "down") and fan[u]:   # nhanh quat tu canh ben qua khe giua 2 cot
            xa = ru[0] + ru[2] if s > 0 else ru[0]
            xg = col_edge(depth[u], s) + s * gapn[depth[v]] / 2
            add(e, [(xa, cu[1]), (xg, cu[1]), (xg, cv[1]), (near, cv[1])], lab_at(e, xg, near, cv[1]))
        elif p == "down" or (p == "up" and not ups_via_gap.get(u)):
            ya = ru[1] + ru[3] if p == "down" else ru[1]
            add(e, [(cu[0], ya), (cu[0], cv[1]), (near, cv[1])],
                lab_at(e, col_edge(depth[u], s), near, cv[1]))
        elif p == "up":   # co con "top" chan phia tren: truc re ra khe giua 2 cot roi moi di len
            xe = cu[0] + s * min(ru[2] / 4, 24)
            ym = ru[1] - C["top_gap"] / 2
            xg = col_edge(depth[u], s) + s * gapn[depth[v]] / 2
            add(e, [(xe, ru[1]), (xe, ym), (xg, ym), (xg, cv[1]), (near, cv[1])],
                lab_at(e, xg, near, cv[1]))
        else:  # top
            add(e, [(cu[0], ru[1]), (cu[0], rv[1] + rv[3])],
                (cu[0] + 6 + e.lab[0] / 2, (ru[1] + rv[1] + rv[3]) / 2) if e.lab else None)

    # ------------------------------------------------ canh ngoai cay: dinh tuyen truc giao
    tree_ids = {id(e) for e in parent_e.values()}
    for e in ledges:
        if id(e) in tree_ids:
            continue
        if e.u == e.v:
            r = R[e.u]
            xr, yc = r[0] + r[2], r[1] + r[3] / 2
            add(e, [(xr, yc - 8), (xr + 18, yc - 8), (xr + 18, yc + 8), (xr, yc + 8)],
                (xr + 24 + e.lab[0] / 2, yc) if e.lab else None)
            continue
        pts = _route(R, e.u, e.v, segs, C)
        add(e, pts)
        if e.lab:
            i = max(range(len(pts) - 1), key=lambda k: math.dist(pts[k], pts[k + 1]))
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            if abs(ay - by) < 0.01:
                e.lab_c = ((ax + bx) / 2, ay - e.lab[1] / 2 - 2)
            else:
                e.lab_c = (ax + 4 + e.lab[0] / 2, (ay + by) / 2)

    W = max(r[0] + r[2] for r in R.values())
    H = max(r[1] + r[3] for r in R.values())
    for e in ledges:
        for px, py in e.pts:
            W, H = max(W, px), max(H, py)
    for x in order:
        el = E[x]
        el.fx, el.fy = R[x][0] - el.sr[0], R[x][1] - el.sr[1]
    return {"w": W, "h": H, "cat_boxes": {}, "crossings": 0, "lanes": [], "need_w": {}}


def _route(R, su, tv, segs, C):
    """Duong truc giao it be goc tu hinh su den hinh tv: khong xuyen hinh nao, tranh di chong khit
    len canh da co (khac nguon). Dijkstra tren luoi Hanan (toa do mep hinh +- grid_m)."""
    m = C["grid_m"]
    rects = [(r[0], r[1], r[0] + r[2], r[1] + r[3]) for r in R.values()]
    obs = [(a - m + 0.5, b - m + 0.5, c + m - 0.5, d + m - 0.5) for a, b, c, d in rects]
    xs, ys = set(), set()
    for a, b, c, d in rects:
        xs |= {a - m, c + m}
        ys |= {b - m, d + m}

    def ports(k):   # (diem tren mep, diem ra ngoai grid_m, huong ra)
        a, b, w, h = R[k]
        cx, cy = a + w / 2, b + h / 2
        return [((a + w, cy), (a + w + m, cy), (1, 0)), ((a, cy), (a - m, cy), (-1, 0)),
                ((cx, b + h), (cx, b + h + m), (0, 1)), ((cx, b), (cx, b - m), (0, -1))]

    SP, TP = ports(su), ports(tv)
    for _, (x, y), _ in SP + TP:
        xs.add(x)
        ys.add(y)
    xs, ys = sorted(xs), sorted(ys)
    xi = {x: i for i, x in enumerate(xs)}
    yi = {y: i for i, y in enumerate(ys)}

    def inside(x, y):
        return any(a < x < c and b < y < d for a, b, c, d in obs)

    free_cache = {}

    def free(i, j):
        if (i, j) not in free_cache:
            free_cache[(i, j)] = not inside(xs[i], ys[j])
        return free_cache[(i, j)]

    def overlap_pen(p, q):
        for a, b, src in segs:
            if src == su:
                continue
            if abs(p[1] - q[1]) < 0.01 and abs(a[1] - b[1]) < 0.01 and abs(a[1] - p[1]) < 1.0:
                ov = min(max(p[0], q[0]), max(a[0], b[0])) - max(min(p[0], q[0]), min(a[0], b[0]))
            elif abs(p[0] - q[0]) < 0.01 and abs(a[0] - b[0]) < 0.01 and abs(a[0] - p[0]) < 1.0:
                ov = min(max(p[1], q[1]), max(a[1], b[1])) - max(min(p[1], q[1]), min(a[1], b[1]))
            else:
                continue
            if ov > 0.5:
                return 10000.0
        return 0.0

    targets = {(xi[x], yi[y]): (tp, (-dv[0], -dv[1])) for tp, (x, y), dv in TP}
    pq, best, prev, cnt = [], {}, {}, 0
    for sp, (x, y), dv in SP:
        st = (xi[x], yi[y], dv)
        if free(st[0], st[1]):
            best[st] = 0.0
            prev[st] = (None, sp)
            heapq.heappush(pq, (0.0, cnt, st))
            cnt += 1
    goal = None
    while pq:
        c, _, st = heapq.heappop(pq)
        if c > best.get(st, math.inf) + 1e-9:
            continue
        if goal is not None and c >= goal[0]:
            break
        i, j, dv = st
        if (i, j) in targets:
            tp, need = targets[(i, j)]
            fin = c + (0 if dv == need else C["bend"])
            if goal is None or fin < goal[0]:
                goal = (fin, st, tp)
        for nd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if nd == (-dv[0], -dv[1]):
                continue
            ni, nj = i + nd[0], j + nd[1]
            if not (0 <= ni < len(xs) and 0 <= nj < len(ys)) or not free(ni, nj):
                continue
            p, q = (xs[i], ys[j]), (xs[ni], ys[nj])
            if inside((p[0] + q[0]) / 2, (p[1] + q[1]) / 2):
                continue
            nc = c + math.dist(p, q) + (0 if nd == dv else C["bend"]) + overlap_pen(p, q)
            ns = (ni, nj, nd)
            if nc < best.get(ns, math.inf) - 1e-9:
                best[ns] = nc
                prev[ns] = (st, None)
                heapq.heappush(pq, (nc, cnt, ns))
                cnt += 1
    if goal is None:  # khong co duong: noi thang (validator se bao loi)
        a, b = R[su], R[tv]
        return [(a[0] + a[2], a[1] + a[3] / 2), (b[0], b[1] + b[3] / 2)]
    _, st, tp = goal
    path = []
    while True:
        path.append((xs[st[0]], ys[st[1]]))
        ps, sp = prev[st]
        if ps is None:
            path.append(sp)
            break
        st = ps
    path.reverse()
    path.append(tp)
    return _simplify(path)
