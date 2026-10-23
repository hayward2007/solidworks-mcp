"""
SolidWorks MCP Package
----------------------
Model Context Protocol server for SolidWorks automation.

Version: 3.0.0
Author: Samsaam Ali Baig
"""

__version__ = "3.0.0"
__author__ = "Samsaam Ali Baig"

from .config import get_config, reload_config, save_config, SolidWorksConfig
from .constants import SwErrors, SwPlanes, SwDocumentTypes, SwViews
from .utils import (
    UnitConverter, 
    mm, cm, inch, ft,
    find_solidworks,
    find_template,
    get_solidworks_info
)

__all__ = [
    # Version
    "__version__",
    "__author__",
    
    # Main class
    "SolidWorksAutomation",
    
    # Config
    "get_config",
    "reload_config", 
    "save_config",
    "SolidWorksConfig",
    
    # Constants
    "SwErrors",
    "SwPlanes",
    "SwDocumentTypes",
    "SwViews",
    
    # Utils
    "UnitConverter",
    "mm", "cm", "inch", "ft",
    "find_solidworks",
    "find_template",
    "get_solidworks_info",
]


def __getattr__(name):
    # Knowledge/review/numerical modules also run without Windows COM.
    if name == "SolidWorksAutomation":
        from .automation import SolidWorksAutomation
        return SolidWorksAutomation
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
