"""SIMP topology optimisation for minimum compliance and compliant mechanisms.

Python 3 / scipy port of ToPy's Topology class (c) William Hunter, MIT License (see
LICENSE_TOPY.md): same problem dictionary, node and DOF numbering, Sigmund sensitivity
filter, optimality-criteria update with reciprocal / exponential (ETA) and diagonal
quadratic (APPROX = dquad) approximations, grey-scale-filter continuation (P_/Q_ HOLD,
INCR, CON, MAX), passive/active elements and mechanism springs. pysparse is replaced by
vectorised scipy.sparse assembly.

Thermal extension (not in ToPy): steady conduction with a fixed boundary film and an optional
density-weighted plate-face film (problem.py / physics.py). PROB_TYPE "heat" minimises the thermal
compliance q.theta; "comp" with a THERMAL block minimises w_s C_s/C_s0 + w_t C_t/C_t0, both
compliances normalised by their values at the first iteration (uniform design). Both terms are
self-adjoint, so the optimality-criteria update is unchanged.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, Optional

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

SOLID, VOID = 1.000, 0.001
KDATUM = 0.1                  # spring stiffness at mechanism input/output DOFs
A_LOW, A_UPP = -3.0, -1e-5    # bounds of the exponential approximation exponent
MAX_ITERS = 250
DIRECT_LIMIT_2D = 200_000     # free DOFs up to which 2D problems use a direct sparse solve


def e2sdofmap(nelx: int, nely: int, dofpn: int) -> np.ndarray:
    """ToPy's element-to-structure DOF map of the first element."""
    if dofpn == 2:
        b = np.arange(2 * (nely + 1), 2 * (nely + 1) + 2)
        a = b + 2
        return np.r_[2, 3, a, b, 0, 1]
    if dofpn == 3:
        d = np.arange(3)
        a = d + 3
        c = np.arange(3 * (nely + 1), 3 * (nely + 1) + 3)
        b = np.arange(3 * (nely + 2), 3 * (nely + 2) + 3)
        h = np.arange(3 * (nelx + 1) * (nely + 1), 3 * (nelx + 1) * (nely + 1) + 3)
        e = np.arange(3 * ((nelx + 1) * (nely + 1) + 1), 3 * ((nelx + 1) * (nely + 1) + 1) + 3)
        g = np.arange(3 * ((nelx + 1) * (nely + 1) + (nely + 1)), 3 * ((nelx + 1) * (nely + 1) + (nely + 1)) + 3)
        f = np.arange(3 * ((nelx + 1) * (nely + 1) + (nely + 2)), 3 * ((nelx + 1) * (nely + 1) + (nely + 2)) + 3)
        return np.r_[a, b, c, d, e, f, g, h]
    raise ValueError("DOF_PN must be 2 (2D) or 3 (3D) for structural problems")


class Topology:
    def __init__(self, prob: Dict):
        self.d = prob
        self.probtype = prob["PROB_TYPE"]
        if self.probtype not in ("comp", "mech", "heat"):
            raise ValueError("PROB_TYPE must be 'comp', 'mech' or 'heat'")
        self.thermal = prob.get("THERMAL")
        if self.probtype == "heat" and not self.thermal:
            raise ValueError("heat problems need a THERMAL block (geometric spec with 'thermal')")
        if self.probtype == "mech" and self.thermal:
            raise ValueError("compliant mechanisms are structural only")
        self.probname = prob.get("PROB_NAME", "")
        self.volfrac = float(prob["VOL_FRAC"])
        self.filtrad = float(prob["FILT_RAD"])
        self.p = float(prob["P_FAC"])
        self.q = float(prob.get("Q_FAC", 1.0))
        self.dofpn = int(prob["DOF_PN"])
        self.nelx, self.nely, self.nelz = int(prob["NUM_ELEM_X"]), int(prob["NUM_ELEM_Y"]), int(prob["NUM_ELEM_Z"])
        self.Ke = np.asarray(prob["ELEM_K"], dtype=float)
        self.numiter = int(prob["NUM_ITER"]) if prob.get("NUM_ITER") else MAX_ITERS
        self.chgstop = float(prob["CHG_STOP"]) if prob.get("CHG_STOP") else 0.0
        nx, ny, nz = self.nelx, self.nely, self.nelz
        three_d = nz > 0
        self.shape = (nz, ny, nx) if three_d else (ny, nx)
        nnodes = (nx + 1) * (ny + 1) * ((nz + 1) if three_d else 1)
        self.ndof = self.dofpn * nnodes
        # element DOF table in desvars (row-major) order
        base = e2sdofmap(nx, ny, self.dofpn)
        if three_d:
            Z, Y, X = np.indices(self.shape)
            off = Y + X * (ny + 1) + Z * (nx + 1) * (ny + 1)
        else:
            Y, X = np.indices(self.shape)
            off = Y + X * (ny + 1)
        self.edof = base[None, :] + self.dofpn * off.ravel()[:, None]
        n_e = self.edof.shape[1]
        self._iK = np.repeat(self.edof, n_e, axis=1).ravel()
        self._jK = np.tile(self.edof, (1, n_e)).ravel()
        self.has_struct = self.probtype != "heat"
        self.fixdof = np.unique(np.asarray(prob["FIX_DOF"], dtype=int))
        self.freedof = np.setdiff1d(np.arange(self.ndof), self.fixdof)
        self.r = np.zeros(self.ndof)
        np.add.at(self.r, np.asarray(prob["LOAD_DOF"], dtype=int), np.asarray(prob["LOAD_VAL"], dtype=float))
        self.springs = sp.csc_matrix((self.ndof, self.ndof))
        if self.probtype == "mech":
            ldo = np.asarray(prob.get("LOAD_DOF_OUT", []), dtype=int)
            lvo = np.asarray(prob.get("LOAD_VAL_OUT", []), dtype=float)
            if not len(ldo):
                raise ValueError("mechanism problems need LOAD_DOF_OUT / LOAD_VAL_OUT")
            self.loaddofout = ldo
            self.rout = np.zeros(self.ndof)
            np.add.at(self.rout, ldo, lvo)
            ld = np.asarray(prob["LOAD_DOF"], dtype=int)
            idx = np.r_[ld, ldo]
            self.springs = sp.csc_matrix((np.full(len(idx), KDATUM), (idx, idx)), shape=(self.ndof, self.ndof))
        self.u = np.zeros(self.ndof)
        self.uout = np.zeros(self.ndof)
        # passive / active elements: ToPy element numbers (column-major) -> desvars flat index
        self.pasv = self._flat(prob.get("PASV_ELEM", []))
        self.actv = self._flat(prob.get("ACTV_ELEM", []))
        self.desvars = np.full(self.shape, self.volfrac)
        self.df = np.zeros(self.shape)
        self._build_filter()
        # continuation and approximation settings (ToPy defaults)
        self._pmax = float(prob.get("P_MAX", 1))
        self._phold = int(prob.get("P_HOLD", self.numiter))
        self._pincr = prob.get("P_INCR")
        self._pcon = float(prob.get("P_CON", self.numiter))
        self._qmax = float(prob.get("Q_MAX", self.q))
        self._qhold = int(prob.get("Q_HOLD", self.numiter))
        self._qincr = prob.get("Q_INCR")
        self._qcon = float(prob.get("Q_CON", self.numiter))
        self.eta_mode = str(prob.get("ETA", "0.5")).lower()
        if self.eta_mode == "exp":
            self.a = -np.ones(self.shape) * (7 / 3 if self.probtype == "mech" else 1.0)
            self.eta = 1 / (1 - self.a)
        else:
            self.eta = float(self.eta_mode) * np.ones(self.shape)
        self.approx = (prob.get("APPROX") or "").lower() or None
        self.pcount = self.qcount = self.itercount = 0
        self.change = 1.0
        self.objfval = 0.0
        self.svtfrac = None
        self.history = []
        self.weights = tuple(prob.get("OBJ_WEIGHTS", (1.0, 0.0) if self.has_struct else (0.0, 1.0)))
        self.c0 = [None, None]
        self.parts = {}
        if self.thermal:
            self._init_thermal()

    def _init_thermal(self):
        th = self.thermal
        nn = int(th["NNODES"])
        self.tnodes = self.edof[:, ::self.dofpn] // self.dofpn
        m = self.tnodes.shape[1]
        self._iT = np.repeat(self.tnodes, m, axis=1).ravel()
        self._jT = np.tile(self.tnodes, (1, m)).ravel()
        self.KTe = np.asarray(th["KE"], float)
        self.KPe = None if th.get("PLATE") is None else np.asarray(th["PLATE"], float)
        self.KTconv = th.get("KCONV")
        self.qT = np.asarray(th["Q"], float)
        self.tfix = np.asarray(th["FIX"], int)
        self.tfree = np.setdiff1d(np.arange(nn), self.tfix)
        self.theta = np.zeros(nn)

    def _flat(self, elems):
        e = np.asarray(elems, dtype=int).ravel()
        if not len(e):
            return e
        nx, ny = self.nelx, self.nely
        if self.nelz:
            k, rem = np.divmod(e, nx * ny)
            j, i = np.divmod(rem, ny)            # column-major inside a layer
            return k * nx * ny + i * nx + j
        j, i = np.divmod(e, ny)
        return i * nx + j

    def _build_filter(self):
        """Sigmund's sensitivity filter as a sparse matrix (weights max(0, r - dist))."""
        r = self.filtrad
        rr = int(np.ceil(r))
        idx = np.arange(np.prod(self.shape)).reshape(self.shape)
        rows, cols, vals = [], [], []
        if self.nelz:
            rng = [(dk, dj, di) for dk in range(-rr, rr + 1) for dj in range(-rr, rr + 1) for di in range(-rr, rr + 1)]
        else:
            rng = [(0, dj, di) for dj in range(-rr, rr + 1) for di in range(-rr, rr + 1)]
        def window(n, d):                            # (source slice, destination slice) for a shift d
            if abs(d) >= n:
                return None
            return (slice(0, n - d), slice(d, n)) if d >= 0 else (slice(-d, n), slice(0, n + d))
        for dk, dj, di in rng:
            w = r - np.sqrt(dk * dk + dj * dj + di * di)
            if w <= 0:
                continue
            shifts = (dk, dj, di) if self.nelz else (dj, di)
            wins = [window(n, d) for n, d in zip(self.shape, shifts)]
            if any(v is None for v in wins):
                continue
            src = idx[tuple(v[0] for v in wins)]
            dst = idx[tuple(v[1] for v in wins)]
            rows.append(src.ravel())
            cols.append(dst.ravel())
            vals.append(np.full(src.size, w))
        n = idx.size
        self.H = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
        self.Hs = np.asarray(self.H.sum(axis=1)).ravel()

    # ---- one optimisation step (fea -> sens_analysis -> filter -> update), as in ToPy ----
    def _solve(self, K, rhs, guess):
        """2D: direct sparse solve. 3D: Jacobi-preconditioned CG warm-started from the last
        iteration (about 10x faster than a direct solve at 30k DOFs; same result to 1e-8),
        with a direct solve as fallback if CG does not converge."""
        Kf = K[self.freedof][:, self.freedof]
        bf = rhs[self.freedof]
        if not self.nelz and len(self.freedof) <= DIRECT_LIMIT_2D:
            return spla.spsolve(Kf.tocsc(), bf)
        Kf = Kf.tocsr()
        dinv = 1.0 / Kf.diagonal()
        M = spla.LinearOperator(Kf.shape, lambda v: dinv * v)
        try:
            x, info = spla.cg(Kf, bf, x0=guess[self.freedof], rtol=1e-8, maxiter=20000, M=M)
        except TypeError:                                           # scipy < 1.12
            x, info = spla.cg(Kf, bf, x0=guess[self.freedof], tol=1e-8, maxiter=20000, M=M)
        if info != 0:
            x = spla.splu(Kf.tocsc(), permc_spec="MMD_AT_PLUS_A").solve(bf)
        return x

    def stiffness(self):
        w = self.desvars.ravel() ** self.p
        return sp.coo_matrix(((w[:, None] * self.Ke.ravel()[None, :]).ravel(), (self._iK, self._jK)),
                             shape=(self.ndof, self.ndof)).tocsc() + self.springs

    def conductance(self):
        x = self.desvars.ravel()
        vals = (x[:, None] ** self.p * self.KTe.ravel()[None, :])
        if self.KPe is not None:                                   # plate-face film where material exists
            vals = vals + x[:, None] * self.KPe.ravel()[None, :]
        n = len(self.qT)
        K = sp.coo_matrix((vals.ravel(), (self._iT, self._jT)), shape=(n, n)).tocsc()
        return K + self.KTconv if self.KTconv is not None else K

    def _solve_thermal(self, K):
        Kf = K[self.tfree][:, self.tfree]
        if not self.nelz:
            return spla.spsolve(Kf.tocsc(), self.qT[self.tfree])
        Kf = Kf.tocsr()
        dinv = 1.0 / Kf.diagonal()
        M = spla.LinearOperator(Kf.shape, lambda v: dinv * v)
        try:
            x, info = spla.cg(Kf, self.qT[self.tfree], x0=self.theta[self.tfree], rtol=1e-9, maxiter=20000, M=M)
        except TypeError:                                           # scipy < 1.12
            x, info = spla.cg(Kf, self.qT[self.tfree], x0=self.theta[self.tfree], tol=1e-9, maxiter=20000, M=M)
        if info != 0:
            x = spla.splu(Kf.tocsc(), permc_spec="MMD_AT_PLUS_A").solve(self.qT[self.tfree])
        return x

    def fea(self):
        if self.itercount >= MAX_ITERS:
            raise RuntimeError("maximum internal number of iterations exceeded")
        if self.has_struct:
            K = self.stiffness()
            self.u[self.freedof] = self._solve(K, self.r, self.u)
            if self.probtype == "mech":
                self.uout[self.freedof] = self._solve(K, self.rout, self.uout)
        if self.thermal:
            self.theta[self.tfree] = self._solve_thermal(self.conductance())
        self.itercount += 1

    def sens_analysis(self):
        ue = self.u[self.edof]
        if self.thermal:
            self._sens_multi(ue)
        elif self.probtype == "comp":
            ce = np.einsum("ij,jk,ik->i", ue, self.Ke, ue).reshape(self.shape)
            self.objfval = float((self.desvars ** self.p * ce).sum())
            self.df = -self.p * self.desvars ** (self.p - 1) * ce
        else:
            uo = self.uout[self.edof]
            op = np.einsum("ij,jk,ik->i", ue, self.Ke, uo).reshape(self.shape)
            self.objfval = float(self.u[self.loaddofout].sum())
            self.df = self.p * self.desvars ** (self.p - 1) * op

    def _sens_multi(self, ue):
        """Weighted, normalised structural and thermal compliance (both self-adjoint)."""
        x = self.desvars
        ws, wt = self.weights
        objective, df = 0.0, np.zeros(self.shape)
        if self.has_struct and ws > 0:
            ce = np.einsum("ij,jk,ik->i", ue, self.Ke, ue).reshape(self.shape)
            cs = float((x ** self.p * ce).sum())
            if self.c0[0] is None:
                self.c0[0] = cs
            objective += ws * cs / self.c0[0]
            df += -ws * self.p * x ** (self.p - 1) * ce / self.c0[0]
            self.parts["structural"] = cs
        te = self.theta[self.tnodes]
        ke = np.einsum("ij,jk,ik->i", te, self.KTe, te).reshape(self.shape)
        dct = -self.p * x ** (self.p - 1) * ke
        if self.KPe is not None:
            dct = dct - np.einsum("ij,jk,ik->i", te, self.KPe, te).reshape(self.shape)
        ct = float(self.qT @ self.theta)
        if self.c0[1] is None:
            self.c0[1] = ct
        objective += wt * ct / self.c0[1]
        df += wt * dct / self.c0[1]
        self.parts["thermal"] = ct
        self.objfval, self.df = objective, df

    def filter_sens_sigmund(self):
        x = self.desvars.ravel()
        self.df = ((self.H @ (x * self.df.ravel())) / (self.Hs * x)).reshape(self.shape)

    def update_desvars_oc(self):
        if self._pincr is not None and self.pcount >= self._phold:
            if self.p + float(self._pincr) < self._pmax and (self.pcount - self._phold) % self._pcon == 0:
                self.p += float(self._pincr)
        if self._qincr is not None and self.qcount >= self._qhold:
            if self.q + float(self._qincr) < self._qmax and (self.qcount - self._qhold) % self._qcon == 0:
                self.q += float(self._qincr)
        self.pcount += 1
        self.qcount += 1
        if self.itercount > 1 and self.eta_mode == "exp":
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = self.desvarsold / self.desvars
                mask = np.equal(ratio, 1)
                a = 1 + np.log2(np.abs(self.dfold / self.df)) / np.log2(ratio + mask) + mask * (self.a - 1)
            self.a = np.clip(np.nan_to_num(a, nan=-1.0, posinf=A_UPP, neginf=A_LOW), A_LOW, A_UPP)
            self.eta = 1 / (1 - self.a)
        self.dfold = self.df.copy()
        self.desvarsold = self.desvars.copy()
        x, df, eta, q = self.desvars, self.df, self.eta, self.q
        move = 0.1 if self.probtype == "mech" else 0.2
        lam1, lam2 = 0.0, 100e3
        n_target = x.size * self.volfrac
        new = x
        while (lam2 - lam1) / (lam2 + lam1) > 1e-8 and lam2 > 1e-40:
            lam = 0.5 * (lam1 + lam2)
            if self.approx == "dquad" and self.probtype == "comp":   # ToPy uses dquad for comp only
                curv = -1 / (eta * x) * df
                beta = np.maximum(x - (df + lam) / curv, VOID)
                upper = np.minimum(move, x / 3)
                new = np.maximum(VOID, np.maximum(x - move, np.minimum(SOLID, np.minimum(x + upper, beta ** q))))
            else:
                new = np.maximum(VOID, np.maximum(x - move, np.minimum(SOLID, np.minimum(
                    x + move, (x * np.maximum(1e-10, -df / lam) ** eta) ** q))))
            if len(self.pasv) or len(self.actv):
                flat = new.ravel()
                flat[self.pasv] = VOID
                flat[self.actv] = SOLID
                new = flat.reshape(self.shape)
            if new.sum() - n_target > 0:
                lam1 = lam
            else:
                lam2 = lam
        self.lam = lam
        self.desvars = new
        self.change = float(np.abs(self.desvars - self.desvarsold).max())
        self.svtfrac = float(((self.desvars == SOLID) | (self.desvars == VOID)).mean())

    def step(self) -> Dict:
        t0 = time.time()
        self.fea()
        self.sens_analysis()
        self.filter_sens_sigmund()
        self.update_desvars_oc()
        rec = {"iter": self.itercount, "objective": self.objfval, "volume": float(self.desvars.mean()),
               "change": self.change, "p": self.p, "q": self.q, "eta": float(self.eta.mean()),
               "svtfrac": self.svtfrac, "time_s": round(time.time() - t0, 3)}
        if self.parts:
            rec.update({"compliance_" + k: v for k, v in self.parts.items()})
        self.history.append(rec)
        return rec

    def run(self, progress: Optional[Callable[[Dict], None]] = None, max_time: Optional[float] = None) -> Dict:
        """Iterate until NUM_ITER, or until the change drops below CHG_STOP (if given)."""
        t0 = time.time()
        while self.itercount < self.numiter:
            rec = self.step()
            if progress:
                progress(rec)
            if self.chgstop and self.change < self.chgstop:
                break
            if max_time and time.time() - t0 > max_time:
                break
        return {"iterations": self.itercount, "objective": self.objfval, "volume": float(self.desvars.mean()),
                "change": self.change, "svtfrac": self.svtfrac, "time_s": round(time.time() - t0, 2)}
