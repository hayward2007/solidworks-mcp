#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SolidWorks COM Automation Module
--------------------------------
Direct COM automation using pywin32 for better error handling
and proper ByRef parameter support.

Version: 1.0.0
Author: Samsaam Ali Baig
Date: 2026-01-22
"""

import logging
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from enum import IntEnum

# COM automation imports
try:
    import win32com.client
    import pythoncom
    from win32com.client import VARIANT
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("WARNING: pywin32 not installed. Run: pip install pywin32")

logger = logging.getLogger("SolidWorksCOM")


# ============================================================================
# ENUMERATIONS (SolidWorks API Constants)
# ============================================================================

class SwDocumentTypes(IntEnum):
    """SolidWorks document types"""
    PART = 1
    ASSEMBLY = 2
    DRAWING = 3


class SwPlanes(IntEnum):
    """Standard reference planes"""
    FRONT = 1
    TOP = 2
    RIGHT = 3


class SwEndConditions(IntEnum):
    """Extrusion end conditions"""
    BLIND = 0
    THROUGH_ALL = 1
    THROUGH_ALL_BOTH = 2
    UP_TO_VERTEX = 3
    UP_TO_SURFACE = 4
    OFFSET_FROM_SURFACE = 5
    MID_PLANE = 6
    UP_TO_BODY = 7


class SimStudyType(IntEnum):
    """Simulation study types"""
    STATIC = 0
    FREQUENCY = 1
    BUCKLING = 2
    THERMAL = 3
    DROP_TEST = 4
    FATIGUE = 5
    NONLINEAR = 6
    LINEAR_DYNAMIC = 7
    PRESSURE_VESSEL = 8


class SimMeshType(IntEnum):
    """Simulation mesh types"""
    SOLID = 0
    SHELL = 1
    BEAM = 2
    MIXED = 3


class SimFixtureType(IntEnum):
    """Simulation fixture types"""
    FIXED = 0
    ROLLER_SLIDER = 1
    FIXED_HINGE = 2
    SYMMETRY = 3


class SimLoadType(IntEnum):
    """Simulation load types"""
    FORCE = 0
    PRESSURE = 1
    TORQUE = 2
    GRAVITY = 3
    CENTRIFUGAL = 4
    TEMPERATURE = 5


class SimStudyError(IntEnum):
    """Simulation study creation error codes"""
    SUCCESS = 0
    INVALID_NAME = 1
    INVALID_TYPE = 2
    STUDY_EXISTS = 3
    NO_LICENSE = 4
    UNKNOWN_ERROR = 5


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SolidWorksInfo:
    """SolidWorks application information"""
    version: str
    build: str
    year: int
    is_connected: bool
    active_document: Optional[str] = None
    document_type: Optional[int] = None


@dataclass
class SimulationInfo:
    """Simulation add-in information"""
    is_loaded: bool
    is_licensed: bool
    license_type: int
    version: str
    study_count: int
    active_study: Optional[str] = None


@dataclass 
class StudyResult:
    """Result of study creation"""
    success: bool
    study_name: Optional[str]
    error_code: int
    error_message: str
    study_object: Any = None


@dataclass
class AnalysisResult:
    """Result of running analysis"""
    success: bool
    max_stress: Optional[float] = None
    max_displacement: Optional[float] = None
    min_factor_of_safety: Optional[float] = None
    error_message: str = ""


# ============================================================================
# SOLIDWORKS COM CLASS
# ============================================================================

class SolidWorksCOM:
    """
    Direct COM automation for SolidWorks using pywin32.
    
    This class provides proper error handling and ByRef parameter support
    that is not available when using VBScript.
    """
    
    def __init__(self):
        self._swApp = None
        self._simulation = None
        self._cosmosworks = None
        
    @property
    def is_available(self) -> bool:
        """Check if pywin32 is available"""
        return PYWIN32_AVAILABLE
    
    @property
    def swApp(self):
        """Get or create SolidWorks application object"""
        if self._swApp is None:
            self.connect()
        return self._swApp
    
    def connect(self, launch_if_needed: bool = True) -> Tuple[bool, str]:
        """
        Connect to SolidWorks application.
        
        Args:
            launch_if_needed: Launch SolidWorks if not running
            
        Returns:
            Tuple of (success, message)
        """
        if not PYWIN32_AVAILABLE:
            return False, "pywin32 is not installed. Run: pip install pywin32"
        
        try:
            # Try to connect to running instance
            self._swApp = win32com.client.GetObject(Class="SldWorks.Application")
            self._swApp.Visible = True
            logger.info("Connected to existing SolidWorks instance")
            return True, "Connected to SolidWorks"
            
        except Exception as e:
            if launch_if_needed:
                try:
                    # Launch new instance
                    self._swApp = win32com.client.Dispatch("SldWorks.Application")
                    self._swApp.Visible = True
                    logger.info("Launched new SolidWorks instance")
                    return True, "Launched SolidWorks"
                except Exception as e2:
                    logger.error(f"Failed to launch SolidWorks: {e2}")
                    return False, f"Failed to connect/launch SolidWorks: {e2}"
            else:
                return False, f"SolidWorks is not running: {e}"
    
    def get_info(self) -> SolidWorksInfo:
        """Get SolidWorks application information"""
        if self._swApp is None:
            return SolidWorksInfo(
                version="", build="", year=0, 
                is_connected=False
            )
        
        try:
            version = self._swApp.RevisionNumber
            try:
                build = str(self._swApp.GetBuildNumbers2())
            except:
                build = "Unknown"
            
            # Parse year from version (e.g., "33.5.0" -> 2025)
            major = int(version.split('.')[0])
            year_map = {33: 2025, 32: 2024, 31: 2023, 30: 2022, 29: 2021}
            year = year_map.get(major, 2020 + (major - 28))
            
            # Get active document info
            active_doc = self._swApp.ActiveDoc
            doc_name = None
            doc_type = None
            if active_doc:
                doc_name = active_doc.GetTitle()
                doc_type = active_doc.GetType()
            
            return SolidWorksInfo(
                version=version,
                build=build,
                year=year,
                is_connected=True,
                active_document=doc_name,
                document_type=doc_type
            )
        except Exception as e:
            logger.error(f"Error getting SolidWorks info: {e}")
            return SolidWorksInfo(
                version="", build="", year=0,
                is_connected=False
            )
    
    def get_active_document(self):
        """Get the active document"""
        if self._swApp is None:
            return None
        return self._swApp.ActiveDoc
    
    def create_new_part(self) -> Tuple[bool, str, Any]:
        """
        Create a new part document.
        
        Returns:
            Tuple of (success, message, model_object)
        """
        try:
            if self._swApp is None:
                success, msg = self.connect()
                if not success:
                    return False, msg, None
            
            # Get template path
            template = self._swApp.GetUserPreferenceStringValue(9)  # swDefaultTemplatePart
            if not template:
                # Try to find template
                exe_path = self._swApp.GetExecutablePath()
                template = exe_path.rsplit('\\', 1)[0] + "\\data\\templates\\Part.prtdot"
            
            # Create new document
            model = self._swApp.NewDocument(template, 0, 0, 0)
            
            if model:
                model.ShowNamedView2("*Isometric", 7)
                model.ViewZoomtofit2()
                return True, "New part created", model
            else:
                return False, "Failed to create new part", None
                
        except Exception as e:
            logger.error(f"Error creating new part: {e}")
            return False, f"Error: {e}", None
    
    def select_plane(self, plane: str = "Front") -> bool:
        """Select a reference plane"""
        model = self.get_active_document()
        if not model:
            return False
        
        plane_names = {
            "Front": "Front Plane",
            "Top": "Top Plane", 
            "Right": "Right Plane"
        }
        plane_name = plane_names.get(plane, "Front Plane")
        
        return model.Extension.SelectByID2(
            plane_name, "PLANE", 0, 0, 0, False, 0, None, 0
        )
    
    def create_sketch(self, plane: str = "Front") -> Tuple[bool, str]:
        """Create a new sketch on specified plane"""
        model = self.get_active_document()
        if not model:
            return False, "No active document"
        
        try:
            self.select_plane(plane)
            model.InsertSketch2(True)
            return True, f"Sketch created on {plane} Plane"
        except Exception as e:
            return False, f"Error creating sketch: {e}"
    
    def draw_circle(self, x: float, y: float, radius: float) -> Tuple[bool, str]:
        """Draw a circle in active sketch"""
        model = self.get_active_document()
        if not model:
            return False, "No active document"
        
        try:
            sketch_mgr = model.SketchManager
            sketch_mgr.CreateCircle(x, y, 0, x + radius, y, 0)
            return True, f"Circle drawn at ({x}, {y}) with radius {radius}"
        except Exception as e:
            return False, f"Error drawing circle: {e}"
    
    def extrude(self, depth: float, both_directions: bool = False) -> Tuple[bool, str]:
        """Extrude the active sketch"""
        model = self.get_active_document()
        if not model:
            return False, "No active document"
        
        try:
            # Exit sketch mode
            model.InsertSketch2(True)
            
            # Create extrusion
            feat_mgr = model.FeatureManager
            direction = 6 if both_directions else 0  # MidPlane or Blind
            
            feat = feat_mgr.FeatureExtrusion2(
                True,   # Sd (single direction)
                False,  # Flip
                False,  # Dir
                direction,  # T1 (end condition)
                0,      # T2
                depth,  # D1 (depth)
                depth,  # D2
                False, False, False, False,
                0, 0, False, False, False, False,
                True, True, True, 0, 0, False
            )
            
            if feat:
                return True, f"Extruded {depth}m"
            else:
                return False, "Extrusion failed"
                
        except Exception as e:
            return False, f"Error extruding: {e}"
    
    def save_document(self, filepath: str) -> Tuple[bool, str]:
        """Save the active document"""
        model = self.get_active_document()
        if not model:
            return False, "No active document"
        
        try:
            errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            
            result = model.Extension.SaveAs(
                filepath, 0, 1, None, errors, warnings
            )
            
            if result:
                return True, f"Saved to {filepath}"
            else:
                return False, f"Save failed. Errors: {errors.value}, Warnings: {warnings.value}"
                
        except Exception as e:
            return False, f"Error saving: {e}"
    
    def apply_material(self, material_name: str, database: str = "") -> Tuple[bool, str]:
        """Apply material to the active part"""
        model = self.get_active_document()
        if not model:
            return False, "No active document"
        
        try:
            config = model.GetActiveConfiguration().Name
            result = model.SetMaterialPropertyName2(config, database, material_name)
            
            if result:
                return True, f"Material '{material_name}' applied"
            else:
                # Try without database
                result = model.SetMaterialPropertyName(config, material_name)
                if result:
                    return True, f"Material '{material_name}' applied"
                return False, f"Failed to apply material '{material_name}'"
                
        except Exception as e:
            return False, f"Error applying material: {e}"


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Global instance for reuse
_sw_com_instance: Optional[SolidWorksCOM] = None

def get_solidworks_com() -> SolidWorksCOM:
    """Get or create the SolidWorks COM instance"""
    global _sw_com_instance
    if _sw_com_instance is None:
        _sw_com_instance = SolidWorksCOM()
    return _sw_com_instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def check_pywin32() -> Tuple[bool, str]:
    """Check if pywin32 is properly installed"""
    if not PYWIN32_AVAILABLE:
        return False, "pywin32 is not installed. Run: pip install pywin32"
    
    try:
        # Test COM initialization
        pythoncom.CoInitialize()
        return True, "pywin32 is properly installed"
    except Exception as e:
        return False, f"pywin32 error: {e}"


if __name__ == "__main__":
    # Test the module
    print("Testing SolidWorks COM module...")
    
    available, msg = check_pywin32()
    print(f"pywin32: {msg}")
    
    if available:
        sw = get_solidworks_com()
        connected, msg = sw.connect()
        print(f"Connection: {msg}")
        
        if connected:
            info = sw.get_info()
            print(f"SolidWorks {info.year} (v{info.version})")
            print(f"Active document: {info.active_document}")
