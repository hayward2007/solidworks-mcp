"""
SolidWorks Feature Operations
-----------------------------
Create 3D features: extrude, cut, fillet, chamfer, etc.

FIXED for SolidWorks 2025:
- FeatureExtrusion3 instead of FeatureExtrusion2
- FeatureCut4 with correct parameters
- Better error handling
"""

import logging
import traceback
from typing import Optional, Dict

import win32com.client
import pythoncom

from ..constants import SwErrors, SwEndConditions

logger = logging.getLogger(__name__)


class FeatureOperations:
    """
    Mixin class for feature operations
    
    Requires parent class to have:
    - get_active_doc(): Document access method
    - _result(): Result factory method
    - _units: UnitConverter instance
    """
    
    def extrude_sketch(self, depth: float = 10, both_directions: bool = False,
                       unit: str = None) -> Dict:
        """
        Extrude the active sketch (Boss-Extrude)
        FIXED: Uses multiple API methods for compatibility with SW 2025
        
        Args:
            depth: Extrusion depth
            both_directions: Extrude in both directions (mid-plane)
            unit: Unit for depth
        
        Returns:
            Result dictionary
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            # Convert depth to meters
            depth_m = self._units.to_meters(depth, unit)
            
            # Exit sketch first
            doc.InsertSketch2(True)
            doc.ClearSelection2(True)
            
            # Try multiple extrusion methods for compatibility
            feat = None
            method_used = ""
            
            # Method 1: FeatureExtrusion3 (SW 2015+)
            try:
                if both_directions:
                    # Mid-plane extrusion
                    feat = doc.FeatureManager.FeatureExtrusion3(
                        True,           # Sd (single direction - ignored for mid-plane)
                        False,          # Flip
                        False,          # Dir
                        6,              # T1 = swEndCondMidPlane
                        0,              # T2
                        depth_m,        # D1
                        0,              # D2
                        False, False,   # Dchk1, Dchk2
                        False, False,   # Ddir1, Ddir2
                        0.0, 0.0,       # Dang1, Dang2 (draft angles)
                        False, False,   # OffsetReverse1, OffsetReverse2
                        False,          # TranslateSurface
                        True,           # MergeResult
                        True,           # UseFeatScope
                        True,           # UseAutoSelect
                        0,              # T0
                        0.0,            # StartOffset
                        False           # FlipStartOffset
                    )
                else:
                    # Single direction blind extrusion
                    feat = doc.FeatureManager.FeatureExtrusion3(
                        True,           # Sd
                        False,          # Flip
                        False,          # Dir
                        0,              # T1 = swEndCondBlind
                        0,              # T2
                        depth_m,        # D1
                        0,              # D2
                        False, False,   # Dchk1, Dchk2
                        False, False,   # Ddir1, Ddir2
                        0.0, 0.0,       # Dang1, Dang2
                        False, False,   # OffsetReverse1, OffsetReverse2
                        False,          # TranslateSurface
                        True,           # MergeResult
                        True,           # UseFeatScope
                        True,           # UseAutoSelect
                        0,              # T0
                        0.0,            # StartOffset
                        False           # FlipStartOffset
                    )
                if feat:
                    method_used = "FeatureExtrusion3"
            except Exception as e:
                logger.debug(f"FeatureExtrusion3 failed: {e}")
            
            # Method 2: FeatureExtrusion2 (older API)
            if feat is None:
                try:
                    end_cond = 6 if both_directions else 0
                    feat = doc.FeatureManager.FeatureExtrusion2(
                        True,           # Sd
                        False,          # Flip
                        False,          # Dir
                        end_cond,       # T1
                        0,              # T2
                        depth_m,        # D1
                        0,              # D2
                        False, False,   # Dchk1, Dchk2
                        False, False,   # Ddir1, Ddir2
                        0.0, 0.0,       # Dang1, Dang2
                        False, False,   # OffsetReverse1, OffsetReverse2
                        False,          # TranslateSurface
                        True,           # MergeResult
                        True,           # UseFeatScope
                        True            # UseAutoSelect
                    )
                    if feat:
                        method_used = "FeatureExtrusion2"
                except Exception as e:
                    logger.debug(f"FeatureExtrusion2 failed: {e}")
            
            # Method 3: Simple Extrusion via InsertProtrusionBlend (fallback)
            if feat is None:
                try:
                    # Try the simple Boss-Extrude
                    feat = doc.FeatureManager.FeatureBossSimple(depth_m)
                    if feat:
                        method_used = "FeatureBossSimple"
                except Exception as e:
                    logger.debug(f"FeatureBossSimple failed: {e}")
            
            if feat is None:
                return self._result(False,
                    "Extrusion failed - ensure sketch has closed profile. Try: create_sketch, draw_circle/rectangle, then extrude_sketch",
                    SwErrors.swFeatureError)
            
            unit_str = unit or self._units.default_unit.value
            direction = "both directions" if both_directions else "one direction"
            
            return self._result(True, f"Extruded {depth}{unit_str} ({direction}) [{method_used}]",
                              SwErrors.swSuccess,
                              {"depth": depth, "unit": unit_str, 
                               "both_directions": both_directions,
                               "api_method": method_used})
            
        except Exception as e:
            logger.error(f"Extrude error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFeatureError)
    
    def cut_extrude(self, depth: float = 10, through_all: bool = False,
                    both_directions: bool = False, unit: str = None) -> Dict:
        """
        Cut extrude (remove material)
        FIXED: Multiple API methods for SW 2025 compatibility
        
        Args:
            depth: Cut depth (ignored if through_all=True)
            through_all: Cut through entire model
            both_directions: Cut in both directions
            unit: Unit for depth
        
        Returns:
            Result dictionary
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            # Convert depth to meters
            depth_m = self._units.to_meters(depth, unit)
            
            # Exit sketch
            doc.InsertSketch2(True)
            
            # Determine end condition
            if through_all:
                if both_directions:
                    end_cond = 2  # swEndCondThroughAllBoth
                else:
                    end_cond = 1  # swEndCondThroughAll
                cut_depth = 0
            else:
                if both_directions:
                    end_cond = 6  # swEndCondMidPlane
                else:
                    end_cond = 0  # swEndCondBlind
                cut_depth = depth_m
            
            feat = None
            method_used = ""
            
            # Method 1: FeatureCut4 (SW 2014+)
            try:
                feat = doc.FeatureManager.FeatureCut4(
                    True,           # Sd
                    False,          # Flip
                    False,          # Dir
                    end_cond,       # T1
                    0,              # T2
                    cut_depth,      # D1
                    cut_depth,      # D2
                    False, False,   # Dchk1, Dchk2
                    False, False,   # Ddir1, Ddir2
                    0.0, 0.0,       # Dang1, Dang2
                    False, False,   # OffsetReverse1, OffsetReverse2
                    False,          # TranslateSurface
                    False,          # NormalCut
                    False,          # FlipSide
                    False,          # AssemblyFeatureScope
                    False,          # AutoSelectComponents
                    False,          # PropagateFeatureToParts
                    0,              # T0 (start condition)
                    0.0,            # StartOffset
                    False           # FlipStartOffset
                )
                if feat:
                    method_used = "FeatureCut4"
            except Exception as e:
                logger.debug(f"FeatureCut4 failed: {e}")
            
            # Method 2: FeatureCut3
            if feat is None:
                try:
                    feat = doc.FeatureManager.FeatureCut3(
                        True,           # Sd
                        False,          # Flip
                        False,          # Dir
                        end_cond,       # T1
                        0,              # T2
                        cut_depth,      # D1
                        cut_depth,      # D2
                        False, False,   # Dchk1, Dchk2
                        False, False,   # Ddir1, Ddir2
                        0.0, 0.0,       # Dang1, Dang2
                        False, False,   # OffsetReverse1, OffsetReverse2
                        False,          # TranslateSurface
                        False,          # NormalCut
                        False           # FlipSide
                    )
                    if feat:
                        method_used = "FeatureCut3"
                except Exception as e:
                    logger.debug(f"FeatureCut3 failed: {e}")
            
            # Method 3: Simple cut
            if feat is None:
                try:
                    feat = doc.FeatureManager.FeatureCutSimple(cut_depth)
                    if feat:
                        method_used = "FeatureCutSimple"
                except Exception as e:
                    logger.debug(f"FeatureCutSimple failed: {e}")
            
            if feat is None:
                return self._result(False,
                    "Cut failed - ensure sketch has closed profile on a face",
                    SwErrors.swFeatureError)
            
            unit_str = unit or self._units.default_unit.value
            cut_type = "through all" if through_all else f"{depth}{unit_str}"
            
            return self._result(True, f"Cut extrude: {cut_type} [{method_used}]",
                              SwErrors.swSuccess,
                              {"depth": depth, "through_all": through_all,
                               "api_method": method_used})
            
        except Exception as e:
            logger.error(f"Cut extrude error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFeatureError)
    
    def fillet_edges(self, radius: float = 2, unit: str = None) -> Dict:
        """
        Add fillet to selected edges
        
        Args:
            radius: Fillet radius
            unit: Unit for radius
        
        Returns:
            Result dictionary
        
        Note: Select edges first using execute_python or manual selection
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            # Convert radius to meters
            radius_m = self._units.to_meters(radius, unit)
            
            feat = None
            method_used = ""
            
            # Method 1: FeatureFillet3
            try:
                feat = doc.FeatureManager.FeatureFillet3(
                    195,        # Options
                    radius_m,   # Radius
                    0,          # Fillet type
                    0,          # Overflow type
                    0, 0,       # Radius type, Profile type
                    0, 0, 0,
                    0, 0, 0,
                    0, 0, 0
                )
                if feat:
                    method_used = "FeatureFillet3"
            except Exception as e:
                logger.debug(f"FeatureFillet3 failed: {e}")
            
            # Method 2: SimpleFillet
            if feat is None:
                try:
                    feat = doc.FeatureManager.SimpleFillet(radius_m, True, True, True)
                    if feat:
                        method_used = "SimpleFillet"
                except Exception as e:
                    logger.debug(f"SimpleFillet failed: {e}")
            
            if feat is None:
                return self._result(False,
                    "Fillet failed - select edges first (Ctrl+click edges in SolidWorks)",
                    SwErrors.swFeatureError)
            
            unit_str = unit or self._units.default_unit.value
            
            return self._result(True, f"Fillet: r={radius}{unit_str} [{method_used}]",
                              SwErrors.swSuccess,
                              {"radius": radius, "unit": unit_str})
            
        except Exception as e:
            logger.error(f"Fillet error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFeatureError)
    
    def chamfer_edges(self, distance: float = 2, angle: float = 45,
                      unit: str = None) -> Dict:
        """
        Add chamfer to selected edges
        
        Args:
            distance: Chamfer distance
            angle: Chamfer angle in degrees
            unit: Unit for distance
        
        Returns:
            Result dictionary
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            import math
            dist_m = self._units.to_meters(distance, unit)
            angle_rad = math.radians(angle)
            
            feat = None
            
            # Try InsertFeatureChamfer
            try:
                feat = doc.FeatureManager.InsertFeatureChamfer(
                    1,          # Type (1 = Distance-Angle)
                    dist_m,     # Distance
                    angle_rad,  # Angle
                    dist_m,     # Other distance
                    0,          # Flip flag
                    False,      # Tangent propagation
                    False       # Face-edge chamfer
                )
            except Exception as e:
                logger.debug(f"InsertFeatureChamfer failed: {e}")
            
            if feat is None:
                return self._result(False,
                    "Chamfer failed - select edges first",
                    SwErrors.swFeatureError)
            
            unit_str = unit or self._units.default_unit.value
            
            return self._result(True, f"Chamfer: {distance}{unit_str} x {angle}°",
                              SwErrors.swSuccess,
                              {"distance": distance, "angle": angle, "unit": unit_str})
            
        except Exception as e:
            logger.error(f"Chamfer error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFeatureError)
    
    def list_features(self) -> Dict:
        """
        List all features in the active document
        NOTE: The fixed version is in server.py (_list_features_fixed)
        
        Returns:
            Result dictionary with feature list
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            features = []
            feat = doc.FirstFeature()
            
            while feat:
                try:
                    name = feat.Name
                    feat_type = feat.GetTypeName2()
                    
                    features.append({
                        "name": name,
                        "type": feat_type,
                    })
                except:
                    pass
                
                feat = feat.GetNextFeature()
            
            return self._result(True, f"{len(features)} features found",
                              SwErrors.swSuccess,
                              {"features": features, "count": len(features)})
            
        except Exception as e:
            logger.error(f"List features error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
    
    def select_edge(self, edge_index: int = 1) -> Dict:
        """
        Select an edge by index
        
        Args:
            edge_index: Edge index (1-based)
        
        Returns:
            Result dictionary
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            # Clear current selection
            doc.ClearSelection2(True)
            
            # Note: Proper edge selection requires knowing the edge name
            # This is a placeholder - use execute_python for precise selection
            
            return self._result(True, f"Use execute_python for edge selection",
                              SwErrors.swSuccess)
            
        except Exception as e:
            return self._result(False, f"Error: {e}", SwErrors.swSelectionError)
