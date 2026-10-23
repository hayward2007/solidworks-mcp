"""model_report helpers:  python -m unittest solidworks_mcp.tests.test_verification  (Windows, needs pywin32)"""
import importlib.util
import unittest

HAS_PYWIN32 = importlib.util.find_spec("win32com") is not None


class QuirkyMassProperty:
    """Behaves like SolidWorks' IMassProperty: after Volume or SurfaceArea has been read,
    Mass and Density come back as if the density were 1 kg/m3."""

    CenterOfMass = (0.0, 0.0, 0.005)

    def __init__(self, volume_m3=24e-6, area_m2=6.8e-3, density=7900.0):
        self._volume, self._area, self._density, self._spoiled = volume_m3, area_m2, density, False

    @property
    def Volume(self):
        self._spoiled = True
        return self._volume

    @property
    def SurfaceArea(self):
        self._spoiled = True
        return self._area

    @property
    def Density(self):
        return 1.0 if self._spoiled else self._density

    @property
    def Mass(self):
        return self._volume * self.Density


@unittest.skipUnless(HAS_PYWIN32, "solidworks_mcp.verification imports pywin32 (Windows)")
class MassPropertiesTests(unittest.TestCase):
    def test_mass_and_density_are_read_before_volume(self):
        from solidworks_mcp.verification import mass_properties
        block = mass_properties(QuirkyMassProperty())  # 60 x 40 x 10 mm block of AISI 1020
        self.assertEqual(block["density_kg_m3"], 7900.0)
        self.assertAlmostEqual(block["mass_kg"], 0.1896, places=6)
        self.assertEqual(block["volume_mm3"], 24000.0)
        self.assertEqual(block["area_mm2"], 6800.0)
        self.assertEqual(block["center_mm"], [0.0, 0.0, 5.0])


if __name__ == "__main__":
    unittest.main()
