"""Finite element matrices of ToPy, computed numerically (Gauss quadrature, exact for these
polynomials) instead of with SymPy.

Unit square / cube elements (half side 0.5), E = 1, nu = 1/3 by default, as in ToPy.
Node order (ToPy): 2D (-,-) (+,-) (+,+) (-,+); 3D the same at z- then z+. DOFs per node: x, y(, z).

Q4     bilinear plane-stress quadrilateral
Q5B    Pian-Sumihara 5-beta assumed-stress quadrilateral (better in bending)
Q4a5B  Q4 with the De Klerk-Groenwold parameter that removes spurious modes
H8     trilinear hexahedron
H18B   18-beta assumed-stress hexahedron

Ported from ToPy (c) William Hunter, MIT License - see LICENSE_TOPY.md.
"""
from __future__ import annotations

import numpy as np

_G3 = (np.array([-np.sqrt(0.6), 0.0, np.sqrt(0.6)]), np.array([5 / 9, 8 / 9, 5 / 9]))
A = B = C = 0.5          # half element dimensions


def _gauss(n_dim):
    """Gauss points (scaled to [-0.5, 0.5]) and weights for n_dim dimensions."""
    p, w = _G3[0] * 0.5, _G3[1] * 0.5
    if n_dim == 2:
        X, Y = np.meshgrid(p, p, indexing="ij")
        W = np.outer(w, w)
        return np.c_[X.ravel(), Y.ravel()], W.ravel()
    X, Y, Z = np.meshgrid(p, p, p, indexing="ij")
    W = np.einsum("i,j,k->ijk", w, w, w)
    return np.c_[X.ravel(), Y.ravel(), Z.ravel()], W.ravel()


def c_plane_stress(E=1.0, nu=1 / 3):
    return E / (1 - nu ** 2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])


def c_solid(E=1.0, nu=1 / 3):
    g = E / ((1 + nu) * (1 - 2 * nu))
    G = E / (2 * (1 + nu))
    Cm = np.zeros((6, 6))
    Cm[:3, :3] = nu * g
    np.fill_diagonal(Cm[:3, :3], (1 - nu) * g)
    Cm[3, 3] = Cm[4, 4] = Cm[5, 5] = G
    return Cm


def _b2(x, y):
    dNdx = np.array([-(B - y), (B - y), (B + y), -(B + y)]) / (4 * A * B)
    dNdy = np.array([-(A - x), -(A + x), (A + x), (A - x)]) / (4 * A * B)
    Bm = np.zeros((3, 8))
    Bm[0, 0::2] = dNdx
    Bm[1, 1::2] = dNdy
    Bm[2, 0::2] = dNdy
    Bm[2, 1::2] = dNdx
    return Bm


_SIGNS3 = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], dtype=float)


def _b3(x, y, z):
    s = _SIGNS3
    fx, fy, fz = (A + s[:, 0] * x), (B + s[:, 1] * y), (C + s[:, 2] * z)
    k = 8 * A * B * C
    dNdx = s[:, 0] * fy * fz / k
    dNdy = s[:, 1] * fx * fz / k
    dNdz = s[:, 2] * fx * fy / k
    Bm = np.zeros((6, 24))
    Bm[0, 0::3] = dNdx
    Bm[1, 1::3] = dNdy
    Bm[2, 2::3] = dNdz
    Bm[3, 0::3] = dNdy
    Bm[3, 1::3] = dNdx
    Bm[4, 1::3] = dNdz
    Bm[4, 2::3] = dNdy
    Bm[5, 0::3] = dNdz
    Bm[5, 2::3] = dNdx
    return Bm


def q4(E=1.0, nu=1 / 3):
    Cm = c_plane_stress(E, nu)
    pts, w = _gauss(2)
    return sum(wi * _b2(*p).T @ Cm @ _b2(*p) for p, wi in zip(pts, w))


def q5b(E=1.0, nu=1 / 3):
    Cm = c_plane_stress(E, nu)
    Ci = np.linalg.inv(Cm)
    pts, w = _gauss(2)
    J = np.zeros((5, 8))
    H = np.zeros((5, 5))
    for (x, y), wi in zip(pts, w):
        P = np.zeros((3, 5))
        P[:3, :3] = np.eye(3)
        P[0, 3], P[1, 4] = y / B, x / A
        J += wi * P.T @ _b2(x, y)
        H += wi * P.T @ Ci @ P
    return J.T @ np.linalg.solve(H, J)


def q4bar(E=1.0, nu=1 / 3):
    """Kbar of De Klerk and Groenwold (constant 2x8 'stress divergence' operator)."""
    Cm = c_plane_stress(E, nu)
    m = np.array([1.0, -1.0, 1.0, -1.0]) / (4 * A * B)      # d2N/dxdy (other 2nd derivatives vanish)
    dBx = np.zeros((3, 8))                                    # d/dx of B
    dBx[1, 1::2] = m
    dBx[2, 0::2] = m
    dBy = np.zeros((3, 8))                                    # d/dy of B
    dBy[0, 0::2] = m
    dBy[2, 1::2] = m
    cx, cy = Cm @ dBx, Cm @ dBy
    Bbar = np.vstack([cx[0] + cy[2], cy[1] + cx[2]])
    return Bbar.T @ Bbar * (4 * A * B)


def q4a5b(E=1.0, nu=1 / 3):
    alpha = (2 * A ** 2 * (1 - nu) * (2 * nu ** 2 - nu + 1)) / (3 * (nu + 1) * E ** 2)
    return q4(E, nu) - alpha * E * q4bar(E, nu)


def h8(E=1.0, nu=1 / 3):
    Cm = c_solid(E, nu)
    pts, w = _gauss(3)
    return sum(wi * _b3(*p).T @ Cm @ _b3(*p) for p, wi in zip(pts, w))


def h18b(E=1.0, nu=1 / 3):
    Cm = c_solid(E, nu)
    Ci = np.linalg.inv(Cm)
    pts, w = _gauss(3)
    J = np.zeros((18, 24))
    H = np.zeros((18, 18))
    for (x, y, z), wi in zip(pts, w):
        P = np.zeros((6, 18))
        P[:, :6] = np.eye(6)
        P[0, 6:9] = (y / B, z / C, y * z / (B * C))
        P[1, 9:12] = (x / A, z / C, x * z / (A * C))
        P[2, 12:15] = (x / A, y / B, x * y / (A * B))
        P[3, 15], P[4, 16], P[5, 17] = z / C, x / A, y / B
        J += wi * P.T @ _b3(x, y, z)
        H += wi * P.T @ Ci @ P
    return J.T @ np.linalg.solve(H, J)


ELEMENTS = {"Q4": (q4, 2), "Q5B": (q5b, 2), "Q4A5B": (q4a5b, 2), "H8": (h8, 3), "H18B": (h18b, 3)}


def element_matrix(name: str, E=1.0, nu=1 / 3) -> np.ndarray:
    key = name.upper()
    if key not in ELEMENTS:
        raise ValueError("element must be one of %s (thermal elements are not included)" % ", ".join(ELEMENTS))
    K = ELEMENTS[key][0](E, nu)
    K[np.abs(K) < 1e-12] = 0.0
    return 0.5 * (K + K.T)
