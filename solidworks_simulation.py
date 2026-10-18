#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SolidWorks Simulation Module
----------------------------
Simulation-specific functionality with proper error handling
and ByRef parameter support using pywin32.

Version: 1.0.0
Author: Samsaam Ali Baig
Date: 2026-01-22
"""

import logging
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field
from enum import IntEnum

# Import COM module
try:
    import win32com.client
    import pythoncom
    from win32com.client import VARIANT
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False

from solidworks_com import (
    get_solidworks_com, SolidWorksCOM,
    SimStudyType, SimMeshType, SimFixtureType, SimLoadType, SimStudyError
)

logger = logging.getLogger("SolidWorksSimulation")


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SimulationStatus:
    """Status of Simulation add-in"""
    addin_loaded: bool = False
    cosmosworks_available: bool = False
    document_available: bool = False
    study_manager_available: bool = False
    study_count: int = 0
    active_study_index: int = -1
    license_type: int = 0
    error_message: str = ""


@dataclass
class StudyCreationResult:
    """Result of creating a simulation study"""
    success: bool
    study_name: str = ""
    error_code: int = -1
    error_message: str = ""
    study_object: Any = None


@dataclass
class FixtureResult:
    """Result of applying a fixture"""
    success: bool
    fixture_name: str = ""
    error_message: str = ""


@dataclass
class LoadResult:
    """Result of applying a load"""
    success: bool
    load_name: str = ""
    error_message: str = ""


@dataclass
class MeshResult:
    """Result of creating mesh"""
    success: bool
    element_count: int = 0
    node_count: int = 0
    error_message: str = ""


@dataclass
class RunResult:
    """Result of running analysis"""
    success: bool
    error_message: str = ""


@dataclass
class StressResult:
    """Stress analysis results"""
    success: bool
    max_von_mises: float = 0.0
    min_von_mises: float = 0.0
    max_principal_1: float = 0.0
    max_principal_3: float = 0.0
    units: str = "N/m^2"
    error_message: str = ""


@dataclass
class DisplacementResult:
    """Displacement analysis results"""
    success: bool
    max_resultant: float = 0.0
    max_x: float = 0.0
    max_y: float = 0.0
    max_z: float = 0.0
    units: str = "m"
    error_message: str = ""


@dataclass
class FactorOfSafetyResult:
    """Factor of safety results"""
    success: bool
    min_fos: float = 0.0
    criterion: str = ""
    error_message: str = ""


# ============================================================================
# ERROR CODE MAPPINGS
# ============================================================================

STUDY_ERROR_MESSAGES = {
    0: "Success",
    1: "Invalid study name",
    2: "Invalid study type",
    3: "Study with this name already exists",
    4: "No Simulation license available",
    5: "Unknown error",
    -1: "API call failed"
}

MESH_ERROR_MESSAGES = {
    0: "Success",
    1: "Meshing failed",
    2: "Invalid mesh parameters",
    3: "Geometry error",
    -1: "API call failed"
}


# ============================================================================
# SIMULATION CLASS
# ============================================================================

class SolidWorksSimulation:
    """
    SolidWorks Simulation automation with proper error handling.
    
    This class provides Simulation-specific functionality including:
    - Study creation
    - Material assignment
    - Fixture application
    - Load application  
    - Mesh generation
    - Analysis execution
    - Result extraction
    """
    
    def __init__(self, sw_com: SolidWorksCOM = None):
        """
        Initialize Simulation module.
        
        Args:
            sw_com: SolidWorksCOM instance (creates one if not provided)
        """
        self._sw_com = sw_com or get_solidworks_com()
        self._simulation_addin = None
        self._cosmosworks = None
        self._cw_doc = None
        self._study_manager = None
        self._current_study = None
    
    @property
    def swApp(self):
        """Get SolidWorks application"""
        return self._sw_com.swApp
    
    def _ensure_connected(self) -> bool:
        """Ensure connection to SolidWorks"""
        if self._sw_com._swApp is None:
            success, _ = self._sw_com.connect()
            return success
        return True
    
    def load_simulation_addin(self) -> Tuple[bool, str]:
        """
        Load the Simulation add-in if not already loaded.
        
        Returns:
            Tuple of (success, message)
        """
        if not self._ensure_connected():
            return False, "Not connected to SolidWorks"
        
        try:
            # Try to get the Simulation add-in
            self._simulation_addin = self.swApp.GetAddInObject("SldWorks.Simulation")
            
            if self._simulation_addin is None:
                # Try to load the add-in
                dll_path = r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\Simulation\cosworks.dll"
                result = self.swApp.LoadAddIn(dll_path)
                
                if result == 0:  # Success
                    self._simulation_addin = self.swApp.GetAddInObject("SldWorks.Simulation")
                elif result == -1:  # Already loaded
                    self._simulation_addin = self.swApp.GetAddInObject("SldWorks.Simulation")
                else:
                    return False, f"Failed to load Simulation add-in (code: {result})"
            
            if self._simulation_addin is None:
                return False, "Simulation add-in not available"
            
            return True, "Simulation add-in loaded"
            
        except Exception as e:
            logger.error(f"Error loading Simulation add-in: {e}")
            return False, f"Error: {e}"
    
    def _get_cosmosworks(self) -> Tuple[bool, str]:
        """Get COSMOSWORKS interface"""
        if self._cosmosworks is not None:
            return True, "Already available"
        
        success, msg = self.load_simulation_addin()
        if not success:
            return False, msg
        
        try:
            self._cosmosworks = self._simulation_addin.COSMOSWORKS
            if self._cosmosworks is None:
                return False, "COSMOSWORKS interface not available"
            return True, "COSMOSWORKS ready"
        except Exception as e:
            return False, f"Error getting COSMOSWORKS: {e}"
    
    def _get_cw_document(self) -> Tuple[bool, str]:
        """Get the active document in Simulation"""
        success, msg = self._get_cosmosworks()
        if not success:
            return False, msg
        
        try:
            # Force rebuild to ensure document is initialized
            model = self.swApp.ActiveDoc
            if model:
                model.ForceRebuild3(True)
            
            self._cw_doc = self._cosmosworks.ActiveDoc
            if self._cw_doc is None:
                return False, "No active document in Simulation. Click on Simulation tab first."
            return True, "Document ready"
        except Exception as e:
            return False, f"Error getting Simulation document: {e}"
    
    def _get_study_manager(self) -> Tuple[bool, str]:
        """Get the Study Manager"""
        success, msg = self._get_cw_document()
        if not success:
            return False, msg
        
        try:
            self._study_manager = self._cw_doc.StudyManager
            if self._study_manager is None:
                return False, "Study Manager not available"
            return True, "Study Manager ready"
        except Exception as e:
            return False, f"Error getting Study Manager: {e}"
    
    def get_status(self) -> SimulationStatus:
        """
        Get comprehensive status of Simulation system.
        
        Returns:
            SimulationStatus object with all status information
        """
        status = SimulationStatus()
        
        try:
            # Check add-in
            success, _ = self.load_simulation_addin()
            status.addin_loaded = success
            
            if not success:
                status.error_message = "Simulation add-in not loaded"
                return status
            
            # Check COSMOSWORKS
            success, _ = self._get_cosmosworks()
            status.cosmosworks_available = success
            
            if not success:
                status.error_message = "COSMOSWORKS not available"
                return status
            
            # Check document
            success, _ = self._get_cw_document()
            status.document_available = success
            
            if not success:
                status.error_message = "Document not available in Simulation"
                return status
            
            # Check study manager
            success, _ = self._get_study_manager()
            status.study_manager_available = success
            
            if success:
                try:
                    status.study_count = self._study_manager.StudyCount
                    status.active_study_index = self._study_manager.ActiveStudy
                except:
                    pass
            
            # Try to get license info
            try:
                status.license_type = self._cosmosworks.LicenseType
            except:
                status.license_type = -1
            
        except Exception as e:
            status.error_message = str(e)
        
        return status
    
    def create_study(
        self, 
        study_name: str, 
        study_type: SimStudyType = SimStudyType.STATIC,
        mesh_type: SimMeshType = SimMeshType.SOLID
    ) -> StudyCreationResult:
        """
        Create a new simulation study with proper error handling.
        
        Args:
            study_name: Name for the new study
            study_type: Type of study (Static, Frequency, etc.)
            mesh_type: Type of mesh (Solid, Shell, etc.)
            
        Returns:
            StudyCreationResult with success status and error details
        """
        result = StudyCreationResult(success=False, study_name=study_name)
        
        # Get study manager
        success, msg = self._get_study_manager()
        if not success:
            result.error_message = msg
            return result
        
        try:
            # Create VARIANT for error code (ByRef parameter)
            err_code = win32com.client.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_I4, 0
            )
            
            # Try CreateNewStudy3 (SW2020+)
            study = None
            try:
                study = self._study_manager.CreateNewStudy3(
                    study_name, 
                    int(study_type), 
                    int(mesh_type), 
                    err_code
                )
                result.error_code = err_code.value
            except Exception as e1:
                logger.debug(f"CreateNewStudy3 failed: {e1}")
                
                # Try CreateNewStudy2
                try:
                    study = self._study_manager.CreateNewStudy2(
                        study_name,
                        int(study_type),
                        int(mesh_type)
                    )
                    result.error_code = 0 if study else -1
                except Exception as e2:
                    logger.debug(f"CreateNewStudy2 failed: {e2}")
                    
                    # Try CreateNewStudy
                    try:
                        study = self._study_manager.CreateNewStudy(
                            study_name,
                            int(study_type),
                            err_code
                        )
                        result.error_code = err_code.value
                    except Exception as e3:
                        logger.error(f"All study creation methods failed: {e3}")
                        result.error_message = f"Study creation failed: {e3}"
                        return result
            
            if study is not None:
                result.success = True
                result.study_object = study
                result.error_message = "Study created successfully"
                self._current_study = study
                
                # Activate the study
                try:
                    study.Activate()
                except:
                    pass
            else:
                result.error_message = STUDY_ERROR_MESSAGES.get(
                    result.error_code, 
                    f"Unknown error (code: {result.error_code})"
                )
            
        except Exception as e:
            result.error_message = f"Error: {e}"
            logger.error(f"Study creation error: {e}")
        
        return result
    
    def get_study(self, study_name: str = None, index: int = None) -> Tuple[Any, str]:
        """
        Get a study by name or index.
        
        Args:
            study_name: Name of the study
            index: Index of the study (0-based)
            
        Returns:
            Tuple of (study_object, error_message)
        """
        success, msg = self._get_study_manager()
        if not success:
            return None, msg
        
        try:
            if study_name:
                # Get by name
                count = self._study_manager.StudyCount
                for i in range(count):
                    study = self._study_manager.GetStudy(i)
                    if study and study.Name == study_name:
                        self._current_study = study
                        return study, ""
                return None, f"Study '{study_name}' not found"
            
            elif index is not None:
                study = self._study_manager.GetStudy(index)
                if study:
                    self._current_study = study
                    return study, ""
                return None, f"No study at index {index}"
            
            else:
                # Get active study
                active_idx = self._study_manager.ActiveStudy
                if active_idx >= 0:
                    study = self._study_manager.GetStudy(active_idx)
                    if study:
                        self._current_study = study
                        return study, ""
                return None, "No active study"
                
        except Exception as e:
            return None, f"Error: {e}"
    
    def apply_fixture_fixed(
        self, 
        face_selection: str = None,
        study: Any = None
    ) -> FixtureResult:
        """
        Apply a fixed fixture to selected face(s).
        
        Args:
            face_selection: Face selection string (SelectByID2 format)
            study: Study object (uses current if not provided)
            
        Returns:
            FixtureResult with success status
        """
        result = FixtureResult(success=False)
        
        study = study or self._current_study
        if study is None:
            result.error_message = "No active study"
            return result
        
        try:
            # Get the loads and restraints manager
            lrm = study.LoadsAndRestraintsManager
            
            if lrm is None:
                result.error_message = "LoadsAndRestraintsManager not available"
                return result
            
            # Apply fixed geometry
            # Note: Face must be pre-selected in SolidWorks
            err_code = win32com.client.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_I4, 0
            )
            
            fixture = lrm.AddRestraint3(
                0,  # swsRestraintTypeFixed
                None,  # Uses current selection
                err_code
            )
            
            if fixture:
                result.success = True
                result.fixture_name = fixture.Name if hasattr(fixture, 'Name') else "Fixed"
                result.error_message = "Fixed fixture applied"
            else:
                result.error_message = f"Failed to apply fixture (code: {err_code.value})"
                
        except Exception as e:
            result.error_message = f"Error: {e}"
        
        return result
    
    def apply_force(
        self,
        magnitude: float,
        direction: str = "normal",
        study: Any = None
    ) -> LoadResult:
        """
        Apply a force load to selected face(s).
        
        Args:
            magnitude: Force magnitude in Newtons
            direction: "normal", "x", "y", or "z"
            study: Study object (uses current if not provided)
            
        Returns:
            LoadResult with success status
        """
        result = LoadResult(success=False)
        
        study = study or self._current_study
        if study is None:
            result.error_message = "No active study"
            return result
        
        try:
            lrm = study.LoadsAndRestraintsManager
            
            if lrm is None:
                result.error_message = "LoadsAndRestraintsManager not available"
                return result
            
            err_code = win32com.client.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_I4, 0
            )
            
            # Apply force (face must be pre-selected)
            load = lrm.AddForce3(
                0,  # swsForceTypeNormal for normal direction
                None,  # Uses current selection
                magnitude,
                err_code
            )
            
            if load:
                result.success = True
                result.load_name = load.Name if hasattr(load, 'Name') else "Force"
                result.error_message = f"Force of {magnitude}N applied"
            else:
                result.error_message = f"Failed to apply force (code: {err_code.value})"
                
        except Exception as e:
            result.error_message = f"Error: {e}"
        
        return result
    
    def create_mesh(
        self,
        quality: str = "standard",
        study: Any = None
    ) -> MeshResult:
        """
        Create mesh for the study.
        
        Args:
            quality: "draft", "standard", or "fine"
            study: Study object (uses current if not provided)
            
        Returns:
            MeshResult with success status
        """
        result = MeshResult(success=False)
        
        study = study or self._current_study
        if study is None:
            result.error_message = "No active study"
            return result
        
        try:
            mesh = study.Mesh
            
            if mesh is None:
                result.error_message = "Mesh object not available"
                return result
            
            # Set mesh quality
            quality_map = {"draft": 0, "standard": 1, "fine": 2}
            mesh.Quality = quality_map.get(quality.lower(), 1)
            
            # Create mesh
            err_code = win32com.client.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_I4, 0
            )
            
            success = mesh.CreateMesh(err_code)
            
            if success:
                result.success = True
                try:
                    result.element_count = mesh.ElementCount
                    result.node_count = mesh.NodeCount
                except:
                    pass
                result.error_message = f"Mesh created ({result.element_count} elements)"
            else:
                result.error_message = f"Mesh creation failed (code: {err_code.value})"
                
        except Exception as e:
            result.error_message = f"Error: {e}"
        
        return result
    
    def run_analysis(self, study: Any = None) -> RunResult:
        """
        Run the simulation analysis.
        
        Args:
            study: Study object (uses current if not provided)
            
        Returns:
            RunResult with success status
        """
        result = RunResult(success=False)
        
        study = study or self._current_study
        if study is None:
            result.error_message = "No active study"
            return result
        
        try:
            err_code = win32com.client.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_I4, 0
            )
            
            success = study.RunAnalysis(err_code)
            
            if success:
                result.success = True
                result.error_message = "Analysis completed successfully"
            else:
                result.error_message = f"Analysis failed (code: {err_code.value})"
                
        except Exception as e:
            result.error_message = f"Error: {e}"
        
        return result
    
    def get_stress_results(self, study: Any = None) -> StressResult:
        """
        Get stress results from completed analysis.
        
        Args:
            study: Study object (uses current if not provided)
            
        Returns:
            StressResult with stress values
        """
        result = StressResult(success=False)
        
        study = study or self._current_study
        if study is None:
            result.error_message = "No active study"
            return result
        
        try:
            results = study.Results
            
            if results is None:
                result.error_message = "Results not available"
                return result
            
            # Get stress component
            stress = results.GetStressComponent(0)  # von Mises
            
            if stress:
                result.success = True
                result.max_von_mises = stress.GetMaximum()
                result.min_von_mises = stress.GetMinimum()
                result.error_message = "Stress results retrieved"
                
        except Exception as e:
            result.error_message = f"Error: {e}"
        
        return result
    
    def get_displacement_results(self, study: Any = None) -> DisplacementResult:
        """
        Get displacement results from completed analysis.
        
        Args:
            study: Study object (uses current if not provided)
            
        Returns:
            DisplacementResult with displacement values
        """
        result = DisplacementResult(success=False)
        
        study = study or self._current_study
        if study is None:
            result.error_message = "No active study"
            return result
        
        try:
            results = study.Results
            
            if results is None:
                result.error_message = "Results not available"
                return result
            
            # Get displacement component
            disp = results.GetDisplacementComponent(3)  # Resultant
            
            if disp:
                result.success = True
                result.max_resultant = disp.GetMaximum()
                result.error_message = "Displacement results retrieved"
                
        except Exception as e:
            result.error_message = f"Error: {e}"
        
        return result


# ============================================================================
# SINGLETON INSTANCE  
# ============================================================================

_simulation_instance: Optional[SolidWorksSimulation] = None

def get_simulation() -> SolidWorksSimulation:
    """Get or create the Simulation instance"""
    global _simulation_instance
    if _simulation_instance is None:
        _simulation_instance = SolidWorksSimulation()
    return _simulation_instance


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("Testing SolidWorks Simulation module...")
    
    sim = get_simulation()
    status = sim.get_status()
    
    print(f"\nSimulation Status:")
    print(f"  Add-in loaded: {status.addin_loaded}")
    print(f"  COSMOSWORKS available: {status.cosmosworks_available}")
    print(f"  Document available: {status.document_available}")
    print(f"  Study Manager available: {status.study_manager_available}")
    print(f"  Study count: {status.study_count}")
    print(f"  License type: {status.license_type}")
    print(f"  Error: {status.error_message}")
