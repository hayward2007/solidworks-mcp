"""Result exports: preview images, 2D contour loops (mm) for CAD, 3D surface meshes (STL)."""
from __future__ import annotations

import io
import math
import struct
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

Point = Tuple[float, float]


# ----------------------------------------------------------------------------------------
# images
# ----------------------------------------------------------------------------------------
def _to_y_up(x2d: np.ndarray) -> np.ndarray:
    """desvars (rows from the top) are already in image order (row 0 = top)."""
    return x2d


def preview_png(x: np.ndarray, meta: Optional[Dict] = None, width: int = 512) -> bytes:
    """2D: density map (black = solid) with supports (blue) and loads (red);
    3D: three maximum-intensity projections (front XY, top XZ, side ZY)."""
    from PIL import Image, ImageDraw
    if x.ndim == 2:
        ny, nx = x.shape
        s = max(1, int(width // nx))
        pad = 24
        core = Image.fromarray((255 * (1 - np.clip(x, 0, 1))).astype(np.uint8), "L").resize((nx * s, ny * s), Image.NEAREST)
        img = Image.new("RGB", (nx * s + 2 * pad, ny * s + 2 * pad), (235, 235, 235))
        img.paste(core.convert("RGB"), (pad, pad))
        if meta:
            d = ImageDraw.Draw(img)
            h = meta["h"]

            def px(p):
                return (pad + p[0] / h * s, pad + (meta["size"][1] - p[1]) / h * s)
            for p in meta.get("supports_xy", [])[:400]:
                u, v = px(p)
                d.rectangle([u - 3, v - 3, u + 3, v + 3], outline=(30, 90, 220), width=2)
            arrows = [(c, f, (220, 40, 40)) for c, f in meta.get("loads", [])]
            if meta.get("output"):
                arrows.append((meta["output"][0], meta["output"][1], (20, 160, 60)))
            for c, f, col in arrows:
                u, v = px(c)
                fx, fy = f[0], f[1]
                L = math.hypot(fx, fy) or 1.0
                du, dv = 40 * fx / L, -40 * fy / L
                d.line([u, v, u + du, v + dv], fill=col, width=3)
                d.ellipse([u - 4, v - 4, u + 4, v + 4], fill=col)
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()
    nz, ny, nx = x.shape
    views = [("front XY", x.max(axis=0)),                      # (ny, nx), rows from the top
             ("top XZ", x.max(axis=1)[::-1, :]),               # (nz, nx), z toward the viewer at the bottom
             ("side ZY", x.max(axis=2).T)]                      # (ny, nz)
    tile = width // 2
    tiles = []
    s = max(1, tile // max(nx, ny, nz))                         # one scale for all three views
    for name, v in views:
        h_, w_ = v.shape
        im = Image.fromarray((255 * (1 - np.clip(v, 0, 1))).astype(np.uint8), "L").resize((w_ * s, h_ * s), Image.NEAREST)
        tiles.append((name, im))
    W = sum(t.width for _, t in tiles) + 10 * (len(tiles) + 1)
    H = max(t.height for _, t in tiles) + 30
    out = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(out)
    xo = 10
    for name, t in tiles:
        out.paste(t.convert("RGB"), (xo, 22))
        d.text((xo, 4), name, fill=(0, 0, 0))
        xo += t.width + 10
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ----------------------------------------------------------------------------------------
# 2D contours
# ----------------------------------------------------------------------------------------
def _nodal_field(x2d: np.ndarray) -> np.ndarray:
    """Node densities (ny+1, nx+1), rows from the top, as the mean of the adjacent elements,
    padded with a ring of zeros outside the domain so every contour closes."""
    ny, nx = x2d.shape
    acc = np.zeros((ny + 1, nx + 1))
    cnt = np.zeros((ny + 1, nx + 1))
    for dy in (0, 1):
        for dx in (0, 1):
            acc[dy:dy + ny, dx:dx + nx] += x2d
            cnt[dy:dy + ny, dx:dx + nx] += 1
    f = acc / cnt
    return np.pad(f, 1, constant_values=0.0)


def contours(x2d: np.ndarray, h: float, size: Sequence[float], level: float = 0.5,
             min_area_elems: float = 2.0, smooth: int = 2) -> List[List[Point]]:
    """Closed iso-density loops in mm (origin lower-left, y up) by marching squares.
    Outer boundaries are counter-clockwise, holes clockwise; points are clamped to the domain."""
    F = _nodal_field(x2d)
    R, C = F.shape
    ny = x2d.shape[0]

    def pos(r, c):
        return ((c - 1) * h, (ny - (r - 1)) * h)
    cache = {}

    def point(key):
        if key not in cache:
            kind, r, c = key
            a, b = ((r, c), (r, c + 1)) if kind == "h" else ((r, c), (r + 1, c))
            va, vb = F[a], F[b]
            t = (level - va) / (vb - va)
            pa, pb = pos(*a), pos(*b)
            cache[key] = (pa[0] + t * (pb[0] - pa[0]), pa[1] + t * (pb[1] - pa[1]))
        return cache[key]
    adj = {}
    ins = F >= level
    for r in range(R - 1):
        for c in range(C - 1):
            tl, tr, br, bl = ins[r, c], ins[r, c + 1], ins[r + 1, c + 1], ins[r + 1, c]
            if tl == tr == br == bl:
                continue
            top, right, bottom, left = ("h", r, c), ("v", r, c + 1), ("h", r + 1, c), ("v", r, c)
            E = [e for e, cut in ((top, tl != tr), (right, tr != br), (bottom, br != bl), (left, bl != tl)) if cut]
            if len(E) == 2:
                pairs = [(E[0], E[1])]
            else:                                            # saddle: resolve with the cell centre
                centre = (F[r, c] + F[r, c + 1] + F[r + 1, c + 1] + F[r + 1, c]) / 4 >= level
                pairs = [(top, right), (bottom, left)] if centre == tl else [(top, left), (bottom, right)]
            for a, b in pairs:
                adj.setdefault(a, []).append(b)
                adj.setdefault(b, []).append(a)
    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nb = adj[cur]
            nxt = nb[0] if nb[0] != prev else (nb[1] if len(nb) > 1 else None)
            if nxt is None or nxt == start or nxt in seen:
                break
            seen.add(nxt)
            loop.append(nxt)
            prev, cur = cur, nxt
        if len(loop) >= 3:
            loops.append([point(k) for k in loop])
    res = []
    Lx, Ly = size[0], size[1]
    for pts in loops:
        pts = [(min(max(p[0], 0.0), Lx), min(max(p[1], 0.0), Ly)) for p in pts]
        pts = _dedupe(pts, 1e-6 * h)
        if len(pts) < 3:
            continue
        for _ in range(smooth):
            pts = _chaikin(pts)
        pts = _simplify(pts, 0.1 * h)
        if abs(_area(pts)) < min_area_elems * h * h:
            continue
        if (_area(pts) > 0) != _probe_solid(x2d, pts, h, ny):
            pts = pts[::-1]
        res.append(pts)
    return res


def _probe_solid(x2d, pts, h, ny) -> bool:
    """True if the region just to the left of the loop's longest edge is solid."""
    best, k = -1.0, 0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L > best:
            best, k = L, i
    a, b = pts[k], pts[(k + 1) % len(pts)]
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    L = best or 1.0
    nx_, ny_ = -(b[1] - a[1]) / L, (b[0] - a[0]) / L          # left normal
    px, py = mx + 0.6 * h * nx_, my + 0.6 * h * ny_
    c, r = int(px // h), int(ny - 1 - py // h)
    if 0 <= r < x2d.shape[0] and 0 <= c < x2d.shape[1]:
        return x2d[r, c] >= 0.5
    return False


def _dedupe(pts, eps):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > eps:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


def _chaikin(pts):
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
        out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
    return out


def _simplify(pts, tol):
    """Douglas-Peucker on a closed loop."""
    if len(pts) < 8:
        return pts
    def dp(seq):
        if len(seq) < 3:
            return seq
        a, b = seq[0], seq[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1e-12
        dmax, k = 0.0, 0
        for i in range(1, len(seq) - 1):
            d = abs(dy * (seq[i][0] - a[0]) - dx * (seq[i][1] - a[1])) / L
            if d > dmax:
                dmax, k = d, i
        if dmax <= tol:
            return [a, b]
        return dp(seq[:k + 1])[:-1] + dp(seq[k:])
    half = len(pts) // 2
    first = dp(pts[:half + 1])
    second = dp(pts[half:] + [pts[0]])
    out = first[:-1] + second[:-1]
    return out if len(out) >= 4 else pts


def _area(pts) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def loops_area(loops) -> float:
    """Net area (outer CCW positive, holes negative)."""
    return sum(_area(p) for p in loops)


# ----------------------------------------------------------------------------------------
# 3D surfaces
# ----------------------------------------------------------------------------------------
def _nodal_field_3d(x3d):
    nz, ny, nx = x3d.shape
    acc = np.zeros((nz + 1, ny + 1, nx + 1))
    cnt = np.zeros_like(acc)
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                acc[a:a + nz, b:b + ny, c:c + nx] += x3d
                cnt[a:a + nz, b:b + ny, c:c + nx] += 1
    return np.pad(acc / cnt, 1, constant_values=0.0)


def surface(x3d: np.ndarray, h: float, level: float = 0.5):
    """Iso-surface (vertices mm, triangles) of the density field: marching tetrahedra on a
    conforming (Kuhn) split of every grid cube, so the mesh is closed, manifold and
    consistently oriented (normals out of the solid) without lookup tables."""
    F = _nodal_field_3d(x3d)                    # axes (k, j, i) = (z, y from the top, x), zero-padded
    F = np.where(np.abs(F - level) < 1e-9, level + 1e-9, F)       # no node exactly on the level
    K, J, I = F.shape
    ny = x3d.shape[1]
    ins = F >= level
    occ = ins[:-1, :-1, :-1].astype(np.int8) + ins[1:, :-1, :-1] + ins[:-1, 1:, :-1] + ins[:-1, :-1, 1:] \
        + ins[1:, 1:, :-1] + ins[1:, :-1, 1:] + ins[:-1, 1:, 1:] + ins[1:, 1:, 1:]
    cells = np.argwhere((occ > 0) & (occ < 8))
    nid = lambda k, j, i: (k * J + j) * I + i
    verts, vindex, tris = [], {}, []

    def pos(n):
        k, rem = divmod(n, J * I)
        j, i = divmod(rem, I)
        return np.array([(i - 1) * h, (ny - (j - 1)) * h, (k - 1) * h]), F[k, j, i]

    def edge_vertex(a, b):
        key = (a, b) if a < b else (b, a)
        v = vindex.get(key)
        if v is None:
            pa, fa = pos(a)
            pb, fb = pos(b)
            t = (level - fa) / (fb - fa)
            v = vindex[key] = len(verts)
            verts.append(pa + t * (pb - pa))
        return v

    def emit(tri, inside_pt, outside_pt):
        a, b, c = (verts[v] for v in tri)
        n = np.cross(b - a, c - a)
        if np.dot(n, outside_pt - inside_pt) < 0:
            tri = (tri[0], tri[2], tri[1])
        tris.append(tri)
    for k, j, i in cells:
        corner = {}
        for dk in (0, 1):
            for dj in (0, 1):
                for di in (0, 1):
                    corner[(dk, dj, di)] = nid(k + dk, j + dj, i + di)
        for perm in _PERMS:
            path = [(0, 0, 0)]
            cur = [0, 0, 0]
            for ax in perm:
                cur[ax] = 1
                path.append(tuple(cur))
            tet = [corner[p] for p in path]
            flags = [bool(ins.flat[n]) for n in tet]
            n_in = sum(flags)
            if n_in in (0, 4):
                continue
            pin = [n for n, f in zip(tet, flags) if f]
            pout = [n for n, f in zip(tet, flags) if not f]
            cin = np.mean([pos(n)[0] for n in pin], axis=0)
            cout = np.mean([pos(n)[0] for n in pout], axis=0)
            if n_in == 1 or n_in == 3:
                lone, others = (pin[0], pout) if n_in == 1 else (pout[0], pin)
                tri = tuple(edge_vertex(lone, o) for o in others)
                emit(tri, cin, cout)
            else:
                a, b = pin
                c, d = pout
                q = [edge_vertex(a, c), edge_vertex(a, d), edge_vertex(b, d), edge_vertex(b, c)]
                emit((q[0], q[1], q[2]), cin, cout)
                emit((q[0], q[2], q[3]), cin, cout)
    return np.asarray(verts, float), np.asarray(tris, int)


_PERMS = ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0))


def write_stl(path: str, verts: np.ndarray, faces: np.ndarray, name: str = "topopt") -> Dict:
    tri = verts[faces]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1)
    n = n / np.where(ln > 0, ln, 1)[:, None]
    with open(path, "wb") as f:
        f.write(name.encode("ascii", "replace")[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(faces)))
        rec = np.zeros(len(faces), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
        rec["n"], rec["v"] = n, tri
        f.write(rec.tobytes())
    vol = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0)
    return {"triangles": int(len(faces)), "volume_mm3": round(vol, 2)}
