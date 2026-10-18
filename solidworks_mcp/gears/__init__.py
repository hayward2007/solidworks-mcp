"""Gear geometry (standards based, pure Python) and native SolidWorks gear builders.

geometry  involute cylindrical gears: tooth space generation, pair checks, planetary sets,
          racks, worm sets (no CAD dependency)
bevel     straight and spiral bevel gear geometry (Tredgold back-cone sections)
build     SolidWorks features: spur, helical, herringbone, internal (ring) gears, racks,
          bevel gears; volume and mesh checks
"""
from .geometry import (Gear, mesh, shift_for_centre_distance, planetary, planet_phases, rack_profile,
                       worm_set, inv, inv_inverse, nearest_module, ISO53_PROFILES)

__all__ = ["Gear", "mesh", "shift_for_centre_distance", "planetary", "planet_phases", "rack_profile",
           "worm_set", "inv", "inv_inverse", "nearest_module", "ISO53_PROFILES"]
