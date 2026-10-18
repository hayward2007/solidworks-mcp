Option Explicit

' Create Extrude Script
' Author: Samsaam Ali Baig
' Description: Extrudes the active sketch

Dim swApp, swModel, swFeatMgr
Dim depth

' Default depth (in meters)
depth = 0.01  ' 10mm

' Get command line argument for depth
If WScript.Arguments.Count >= 1 Then
    depth = CDbl(WScript.Arguments(0))
End If

' Connect to SolidWorks
On Error Resume Next
Set swApp = GetObject(, "SldWorks.Application")
If Err.Number <> 0 Then
    WScript.Echo "Error: SolidWorks is not running"
    WScript.Quit(1)
End If
On Error Goto 0

' Get active document
Set swModel = swApp.ActiveDoc
If swModel Is Nothing Then
    WScript.Echo "Error: No active document"
    WScript.Quit(1)
End If

Set swFeatMgr = swModel.FeatureManager

' Exit sketch mode if active
WScript.Echo "Exiting sketch mode..."
swModel.InsertSketch2 True

' Create extrusion
WScript.Echo "Creating extrusion with depth: " & depth & "m"

' FeatureExtrusion2 parameters:
' Sd (single direction), Flip, Dir, T1 (end condition), T2, D1 (depth), D2
' Dchk1, Dchk2, Ddir1, Ddir2, Dang1, Dang2, OffsetReverse1, OffsetReverse2
' TranslateS, MergeResult, UseFeatScope, UseAutoSelect, T0, StartOffset, FlipStartOffset
swFeatMgr.FeatureExtrusion2 True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False

WScript.Echo "SUCCESS: Sketch extruded by " & depth & "m"
WScript.Quit(0)
