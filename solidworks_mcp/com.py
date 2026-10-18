"""
Helpers for late-bound SolidWorks COM objects
---------------------------------------------
SolidWorks 2025 is reached through late binding (pywin32 dynamic dispatch):

* zero-argument members (GetTitle, GetType, FirstFeature, GetNextFeature, ...)
  run as soon as they are accessed, so adding "()" fails  -> use val()
* methods that take arguments are sometimes mistaken for properties
                                                          -> use call()
* numeric arrays must be passed as VT_ARRAY | VT_R8        -> use arr()

These helpers are also injected into execute_python scripts.
"""

import types

import pythoncom
import win32com.client

NOCALL = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)   # empty Callout argument
DEFAULT_PLANES = ("front", "top", "right")                       # order of the three default planes


def val(obj, name):
    """Read a zero-argument member, whether pywin32 exposes it as a property or a method."""
    member = getattr(obj, name)
    return member() if isinstance(member, types.MethodType) else member


def call(obj, name, *args):
    """Call a method that takes arguments, forcing method (not property) semantics."""
    obj._FlagAsMethod(name)
    return getattr(obj, name)(*args)


def arr(values):
    """Numeric array argument (VT_ARRAY | VT_R8)."""
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values])


def strings(values):
    """String array argument (VT_ARRAY | VT_BSTR)."""
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [str(v) for v in values])


def byref_int(value=0):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, value)


def byref_bool(value=False):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, value)


def features(doc):
    """All top-level features of a document, in tree order."""
    out, feat = [], val(doc, "FirstFeature")
    while feat is not None:
        out.append(feat)
        feat = val(feat, "GetNextFeature")
    return out


def feature(doc, name):
    """Top-level feature by name (None if missing)."""
    return next((f for f in features(doc) if f.Name == name), None)


def default_plane_name(doc, which):
    """Actual (possibly localized) name of the default Front/Top/Right plane.

    Names follow the UI language ("Front Plane" vs "정면"), but the three default
    planes are always the first reference planes in the tree, in Front, Top, Right order.
    """
    which = which.lower().replace(" plane", "")
    if which not in DEFAULT_PLANES:
        raise ValueError(f"plane must be one of {DEFAULT_PLANES}")
    planes = []
    feat = val(doc, "FirstFeature")
    while feat is not None and len(planes) < 3:
        if val(feat, "GetTypeName2") == "RefPlane":
            planes.append(feat.Name)
        feat = val(feat, "GetNextFeature")
    return planes[DEFAULT_PLANES.index(which)]


def select(doc, name, type_name, append=False, mark=0, x=0.0, y=0.0, z=0.0):
    """SelectByID2 shortcut. Coordinates are metres (used as the pick point)."""
    return call(doc.Extension, "SelectByID2", name, type_name, x, y, z, append, mark, NOCALL, 0)
