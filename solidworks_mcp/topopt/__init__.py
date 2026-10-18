"""Structural topology optimisation (SIMP): minimum compliance and compliant mechanisms,
2D plane stress and 3D, ToPy problem definition (TPD) compatible.

Python 3 / scipy port of ToPy by William Hunter (https://github.com/williamhunter/topy,
MIT License, see LICENSE_TOPY.md; parts of the 2D code follow Ole Sigmund's 99-line code).
Heat-conduction problems are left out.

problem   TPD reader/writer and the geometric spec in mm (from_spec)
topology  the optimiser (Topology)
export    preview PNG, 2D contour loops, 3D STL surface
run       background job runner (python -m solidworks_mcp.topopt.run JOB_DIR)
cad       SolidWorks: extruded plate from 2D loops, STL import
"""
from .problem import from_spec, parse_tpd, to_tpd
from .topology import Topology

__all__ = ["from_spec", "parse_tpd", "to_tpd", "Topology"]
