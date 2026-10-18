Option Explicit

' Draw Circle Script
' Author: Samsaam Ali Baig
' Description: Draws a circle in the active sketch

Dim swApp, swModel, swSketchMgr
Dim centerX, centerY, radius

' Default parameters (in meters)
centerX = 0
centerY = 0
radius = 0.05  ' 50mm

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

Set swSketchMgr = swModel.SketchManager

' Draw circle
WScript.Echo "Drawing circle at (" & centerX & ", " & centerY & ") with radius " & radius
swSketchMgr.CreateCircle centerX, centerY, 0, centerX + radius, centerY, 0

WScript.Echo "SUCCESS: Circle drawn"
WScript.Quit(0)
