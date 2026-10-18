Option Explicit

' Create Sketch Script
' Author: Samsaam Ali Baig
' Description: Creates a new sketch on the Front Plane

Dim swApp, swModel, swPart

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

Set swPart = swModel

' Select Front Plane
WScript.Echo "Selecting Front Plane..."
swModel.Extension.SelectByID2 "Front Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0

' Insert sketch
WScript.Echo "Creating sketch..."
swModel.InsertSketch2 True

WScript.Echo "SUCCESS: Sketch created on Front Plane"
WScript.Quit(0)
