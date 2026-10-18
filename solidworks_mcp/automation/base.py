"""
SolidWorks Automation Base
--------------------------
Core automation class with connection management and utility methods.
"""

import os
import time
import logging
import datetime
import traceback
import types
from typing import Optional, Dict, Any, Tuple

# COM imports
import win32com.client
import pythoncom

from ..constants import SwErrors, SwPlanes, SwDocumentTypes, SwViews
from ..config import get_config
from ..utils import UnitConverter, find_solidworks, find_template

logger = logging.getLogger(__name__)


class SolidWorksAutomation:
    """
    Core SolidWorks automation class
    
    Handles connection management, document operations, and provides
    utility methods for all automation tasks.
    """
    
    def __init__(self):
        """Initialize automation instance"""
        self._sw_app = None
        self._connected = False
        self._config = get_config()
        self._units = UnitConverter(self._config.default_unit)
        self._sw_exe_path = None
        
        logger.info("SolidWorksAutomation initialized")
    
    # ========================================================================
    # Properties
    # ========================================================================
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to SolidWorks"""
        if not self._connected or self._sw_app is None:
            return False
        
        try:
            # Test connection by accessing a property
            _ = self._sw_app.RevisionNumber
            return True
        except:
            try:
                # Some versions use method instead of property
                _ = self._sw_app.RevisionNumber()
                return True
            except:
                self._connected = False
                self._sw_app = None
                return False
    
    @property
    def units(self) -> UnitConverter:
        """Get unit converter"""
        return self._units
    
    @property
    def app(self):
        """Get SolidWorks application object"""
        return self._sw_app
    
    # ========================================================================
    # Result Helper
    # ========================================================================
    
    def _result(self, success: bool, message: str,
                error_code: SwErrors = SwErrors.swSuccess,
                data: Optional[Dict] = None) -> Dict:
        """
        Create standardized result dictionary
        
        Args:
            success: Operation success status
            message: Human-readable message
            error_code: Error code enum
            data: Optional additional data
        
        Returns:
            Standardized result dictionary
        """
        result = {
            "success": success,
            "message": message,
            "error_code": int(error_code),
            "error_name": error_code.name,
            "timestamp": datetime.datetime.now().isoformat()
        }
        if data:
            result["data"] = data
        return result
    
    # ========================================================================
    # Connection Methods
    # ========================================================================
    
    def _try_connect_com(self) -> bool:
        """
        Try multiple COM connection methods
        
        Returns:
            True if connection successful
        """
        methods = [
            # Method 1: GetObject (running instance)
            lambda: win32com.client.GetObject(Class="SldWorks.Application"),
            # Method 2: Dispatch (creates or gets existing)
            lambda: win32com.client.Dispatch("SldWorks.Application"),
            # Method 3: Dynamic Dispatch
            lambda: win32com.client.dynamic.Dispatch("SldWorks.Application"),
            # Method 4: GetActiveObject
            lambda: win32com.client.GetActiveObject("SldWorks.Application"),
        ]
        
        for i, method in enumerate(methods):
            try:
                logger.debug(f"Trying connection method {i+1}...")
                pythoncom.CoInitialize()
                self._sw_app = method()
                
                if self._sw_app is not None:
                    self._sw_app.Visible = True
                    
                    # Get version (property or method)
                    try:
                        version = self._sw_app.RevisionNumber
                    except:
                        version = self._sw_app.RevisionNumber()
                    
                    logger.info(f"Connected via method {i+1}: {version}")
                    self._connected = True
                    return True
                    
            except Exception as e:
                logger.debug(f"Method {i+1} failed: {e}")
                continue
        
        return False
    
    def connect(self) -> Dict:
        """
        Connect to SolidWorks - launches if not running
        
        Returns:
            Result dictionary with connection status
        """
        try:
            logger.info("=== Connecting to SolidWorks ===")
            
            # Step 1: Try connecting to running instance
            if self._try_connect_com():
                try:
                    version = self._sw_app.RevisionNumber
                except:
                    version = self._sw_app.RevisionNumber()
                
                return self._result(True, f"Connected to SolidWorks {version}",
                                  SwErrors.swSuccess,
                                  {"version": str(version), "launched": False})
            
            # Step 2: Find SolidWorks executable
            if self._sw_exe_path is None:
                if self._config.exe_path != "auto":
                    self._sw_exe_path = self._config.exe_path
                else:
                    self._sw_exe_path = find_solidworks()
            
            if not self._sw_exe_path or not os.path.exists(self._sw_exe_path):
                return self._result(False,
                    f"SolidWorks not found. Set exe_path in config or install SolidWorks.",
                    SwErrors.swSolidWorksNotFound)
            
            # Step 3: Launch SolidWorks
            logger.info(f"Launching SolidWorks: {self._sw_exe_path}")
            os.startfile(self._sw_exe_path)
            
            # Step 4: Wait for SolidWorks to start
            logger.info("Waiting for SolidWorks startup...")
            max_wait = self._config.startup_timeout
            retry_interval = self._config.connection_retry_interval
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                time.sleep(retry_interval)
                elapsed = int(time.time() - start_time)
                logger.debug(f"Connection attempt at {elapsed}s...")
                
                if self._try_connect_com():
                    try:
                        version = self._sw_app.RevisionNumber
                    except:
                        version = self._sw_app.RevisionNumber()
                    
                    logger.info(f"Connected after {elapsed}s")
                    return self._result(True,
                        f"Launched and connected to SolidWorks {version} (took {elapsed}s)",
                        SwErrors.swSuccess,
                        {"version": str(version), "launched": True, "startup_time": elapsed})
            
            return self._result(False,
                f"Timeout after {max_wait}s. Close any dialogs and try again.",
                SwErrors.swConnectionError)
            
        except Exception as e:
            logger.error(f"Connection error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Connection error: {e}",
                              SwErrors.swConnectionError)
    
    def disconnect(self) -> Dict:
        """
        Disconnect from SolidWorks (does not close SolidWorks)
        
        Returns:
            Result dictionary
        """
        self._sw_app = None
        self._connected = False
        logger.info("Disconnected from SolidWorks")
        return self._result(True, "Disconnected from SolidWorks")
    
    # ========================================================================
    # Document Methods
    # ========================================================================
    
    def get_active_doc(self) -> Tuple[Any, Optional[Dict]]:
        """
        Get active document with auto-connect
        
        Returns:
            Tuple of (document, error_result)
            - If successful: (document, None)
            - If failed: (None, error_dict)
        """
        if not self.is_connected:
            result = self.connect()
            if not result["success"]:
                return None, result
        
        doc = self._sw_app.ActiveDoc
        if doc is None:
            return None, self._result(False,
                "No document open. Use create_new_part first.",
                SwErrors.swNoActiveDocument)
        
        return doc, None
    
    def _get_doc_title(self, doc) -> str:
        """Get document title (handles property/method difference)"""
        try:
            title = doc.GetTitle
            if callable(title):
                return title()
            return title
        except:
            return "Unknown"
    
    def _get_doc_path(self, doc) -> str:
        """Get document path (handles property/method difference)"""
        try:
            path = doc.GetPathName
            if callable(path):
                return path()
            return path
        except:
            return ""

    @staticmethod
    def _com_value(obj, name: str):
        """
        Read a zero-argument COM member (GetType, GetNext, GetFirstDocument, ...).

        With late binding (seen on SolidWorks 2025) pywin32 runs such members as
        soon as they are accessed and hands back the result, so adding "()" fails:
        "member not found" when the result is a COM object, "'int' object is not
        callable" when it is a number. With type information they come back as
        methods instead, so call them only in that case.
        """
        member = getattr(obj, name)
        return member() if isinstance(member, types.MethodType) else member

    def _default_plane_name(self, doc, plane_name: str) -> Optional[str]:
        """
        Actual (possibly localized) name of a default plane, e.g. "정면" for
        "Front Plane" in Korean SolidWorks. Plane names follow the UI language,
        but the three default planes are always the first reference planes in
        the feature tree, in Front, Top, Right order.
        """
        order = [SwPlanes.FRONT, SwPlanes.TOP, SwPlanes.RIGHT]
        if plane_name not in order:
            return None
        planes = []
        feat = self._com_value(doc, "FirstFeature")
        while feat is not None and len(planes) < 3:
            if self._com_value(feat, "GetTypeName2") == "RefPlane":
                planes.append(feat.Name)
            feat = self._com_value(feat, "GetNextFeature")
        index = order.index(plane_name)
        return planes[index] if index < len(planes) else None
