"""
SolidWorks Document Operations
------------------------------
Create, open, save, and manage SolidWorks documents.
"""

import os
import logging
import traceback
from typing import Optional, Dict

import win32com.client
import pythoncom

from ..constants import SwErrors, SwDocumentTypes, SwFileTypes
from ..utils import find_template

logger = logging.getLogger(__name__)


class DocumentOperations:
    """
    Mixin class for document operations
    
    Requires parent class to have:
    - self._sw_app: SolidWorks application object
    - self.is_connected: Connection status property
    - self.connect(): Connection method
    - self._result(): Result factory method
    - self._units: UnitConverter instance
    """
    
    def create_new_part(self) -> Dict:
        """
        Create a new part document
        
        Returns:
            Result dictionary with document info
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            # Find part template
            template = find_template("part")
            if not template:
                template = ""  # Let SolidWorks use default
                logger.info("Using SolidWorks default part template")
            else:
                logger.info(f"Using template: {template}")
            
            # Create document
            doc = self._sw_app.NewDocument(template, 0, 0, 0)
            
            if doc is None:
                return self._result(False, "Failed to create part document",
                                  SwErrors.swFileLoadError)
            
            # Set view
            try:
                doc.ShowNamedView2("*Isometric", 7)
                doc.ViewZoomtofit2()
            except:
                pass
            
            title = self._get_doc_title(doc)
            
            return self._result(True, f"Created part: {title}",
                              SwErrors.swSuccess,
                              {"name": title, "type": "Part"})
            
        except Exception as e:
            logger.error(f"Create part error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
    
    def create_new_assembly(self) -> Dict:
        """
        Create a new assembly document
        
        Returns:
            Result dictionary with document info
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            template = find_template("assembly")
            if not template:
                template = ""
            
            doc = self._sw_app.NewDocument(template, 0, 0, 0)
            
            if doc is None:
                return self._result(False, "Failed to create assembly",
                                  SwErrors.swFileLoadError)
            
            try:
                doc.ShowNamedView2("*Isometric", 7)
                doc.ViewZoomtofit2()
            except:
                pass
            
            title = self._get_doc_title(doc)
            
            return self._result(True, f"Created assembly: {title}",
                              SwErrors.swSuccess,
                              {"name": title, "type": "Assembly"})
            
        except Exception as e:
            logger.error(f"Create assembly error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
    
    def create_new_drawing(self, paper_size: str = "A4") -> Dict:
        """
        Create a new drawing document
        
        Args:
            paper_size: Paper size (A4, A3, A2, A1, Letter)
        
        Returns:
            Result dictionary with document info
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            template = find_template("drawing")
            if not template:
                template = ""
            
            doc = self._sw_app.NewDocument(template, 0, 0, 0)
            
            if doc is None:
                return self._result(False, "Failed to create drawing",
                                  SwErrors.swFileLoadError)
            
            title = self._get_doc_title(doc)
            
            return self._result(True, f"Created drawing: {title}",
                              SwErrors.swSuccess,
                              {"name": title, "type": "Drawing", "paper_size": paper_size})
            
        except Exception as e:
            logger.error(f"Create drawing error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
    
    def open_document(self, filepath: str) -> Dict:
        """
        Open an existing document
        
        Args:
            filepath: Path to SolidWorks file
        
        Returns:
            Result dictionary
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            if not os.path.exists(filepath):
                return self._result(False, f"File not found: {filepath}",
                                  SwErrors.swFileNotFoundError)
            
            # Determine document type from extension
            ext = os.path.splitext(filepath)[1].lower()
            type_map = {
                ".sldprt": SwDocumentTypes.swDocPART,
                ".sldasm": SwDocumentTypes.swDocASSEMBLY,
                ".slddrw": SwDocumentTypes.swDocDRAWING,
            }
            doc_type = type_map.get(ext, SwDocumentTypes.swDocPART)
            
            # Open document
            errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            
            doc = self._sw_app.OpenDoc6(filepath, int(doc_type), 0, "", errors, warnings)
            
            if doc is None or errors.value != 0:
                return self._result(False, f"Failed to open (error {errors.value})",
                                  SwErrors.swFileLoadError)
            
            title = self._get_doc_title(doc)
            
            return self._result(True, f"Opened: {title}",
                              SwErrors.swSuccess,
                              {"name": title, "path": filepath})
            
        except Exception as e:
            logger.error(f"Open document error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
    
    def save_document(self, filepath: str = None) -> Dict:
        """
        Save the active document
        FIXED v4.1: Use doc.SaveAs() as primary method (avoids COM type mismatch
        with Extension.SaveAs where None parameter fails in SW 2025).
        
        Args:
            filepath: Path to save (None = save in place)
        
        Returns:
            Result dictionary
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            if filepath:
                # Ensure absolute path
                filepath = os.path.abspath(filepath)
                
                # Ensure directory exists
                dir_path = os.path.dirname(filepath)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path)
                
                saved = False
                method_used = ""
                
                # Method 1: doc.SaveAs (simplest, most reliable for SW 2025)
                try:
                    result = doc.SaveAs(filepath)
                    if result:
                        saved = True
                        method_used = "SaveAs"
                except Exception as e:
                    logger.debug(f"doc.SaveAs failed: {e}")
                
                # Method 2: Extension.SaveAs with proper VARIANT null dispatch
                if not saved:
                    try:
                        empty_export = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
                        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                        
                        result = doc.Extension.SaveAs(
                            filepath, 0, 0, empty_export, errors, warnings
                        )
                        if result and errors.value == 0:
                            saved = True
                            method_used = "Extension.SaveAs"
                    except Exception as e:
                        logger.debug(f"Extension.SaveAs failed: {e}")
                
                # Method 3: Extension.SaveAs2
                if not saved:
                    try:
                        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                        
                        result = doc.Extension.SaveAs2(
                            filepath, 0, 0, None, "", False, errors, warnings
                        )
                        if result:
                            saved = True
                            method_used = "Extension.SaveAs2"
                    except Exception as e:
                        logger.debug(f"Extension.SaveAs2 failed: {e}")
                
                if not saved:
                    return self._result(False, "Save failed - all methods attempted",
                                      SwErrors.swFileSaveError)
                
                return self._result(True, f"Saved: {filepath} [{method_used}]",
                                  SwErrors.swSuccess,
                                  {"path": filepath, "method": method_used})
            else:
                # Save in place
                result = doc.Save3(0, 0, 0)
                
                if result != 0:
                    return self._result(False, f"Save failed (code {result})",
                                      SwErrors.swFileSaveError)
                
                path = self._get_doc_path(doc)
                return self._result(True, f"Saved: {path}",
                                  SwErrors.swSuccess, {"path": path})
            
        except Exception as e:
            logger.error(f"Save error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swFileSaveError)
    
    def close_document(self, save: bool = False) -> Dict:
        """
        Close the active document
        
        Args:
            save: Save before closing
        
        Returns:
            Result dictionary
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return self._result(True, "No document to close")
            
            title = self._get_doc_title(doc)
            
            if save:
                doc.Save3(0, 0, 0)
            
            self._sw_app.CloseDoc(title)
            
            return self._result(True, f"Closed: {title}",
                              SwErrors.swSuccess, {"document": title})
            
        except Exception as e:
            logger.error(f"Close error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
    
    def get_document_info(self) -> Dict:
        """
        Get information about the active document
        
        Returns:
            Result dictionary with document details
        """
        try:
            doc, err = self.get_active_doc()
            if err:
                return err
            
            type_names = {
                0: "None",
                1: "Part",
                2: "Assembly",
                3: "Drawing"
            }
            
            doc_type = self._com_value(doc, "GetType")
            title = self._get_doc_title(doc)
            path = self._get_doc_path(doc)
            
            info = {
                "title": title,
                "path": path if path else "Not saved",
                "type": type_names.get(doc_type, "Unknown"),
                "type_code": doc_type,
            }
            
            return self._result(True, f"{title} ({info['type']})",
                              SwErrors.swSuccess, info)
            
        except Exception as e:
            logger.error(f"Get info error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
    
    def list_open_documents(self) -> Dict:
        """
        List all open documents
        
        Returns:
            Result dictionary with document list
        """
        try:
            if not self.is_connected:
                r = self.connect()
                if not r["success"]:
                    return r
            
            docs = []
            # FIXED: zero-argument COM members are read via _com_value (SW 2025 late binding)
            doc = self._com_value(self._sw_app, "GetFirstDocument")
            
            while doc is not None:
                try:
                    title = doc.GetTitle
                    if callable(title):
                        title = title()
                    doc_type = self._com_value(doc, "GetType")
                    
                    type_names = {1: "Part", 2: "Assembly", 3: "Drawing"}
                    
                    docs.append({
                        "title": title,
                        "type": type_names.get(doc_type, "Unknown")
                    })
                except:
                    pass
                
                doc = self._com_value(doc, "GetNext")
            
            return self._result(True, f"{len(docs)} document(s) open",
                              SwErrors.swSuccess, {"documents": docs})
            
        except Exception as e:
            logger.error(f"List documents error: {e}\n{traceback.format_exc()}")
            return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
