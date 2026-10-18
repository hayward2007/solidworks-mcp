Option Explicit

' Create Sketch From Input Script
' Author: Samsaam Ali Baig
' Description: Creates shapes based on input parameters

Dim swApp, swModel, swSketchMgr
Dim shapeType, param1, param2, param3, param4

' Get command line arguments
If WScript.Arguments.Count >= 1 Then
    shapeType = LCase(WScript.Arguments(0))
Else
    shapeType = "circle"
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

Set swSketchMgr = swModel.SketchManager

' Draw based on shape type
Select Case shapeType
    Case "circle"
        ' Default: circle at origin with 50mm radius
        param1 = 0      ' X center
        param2 = 0      ' Y center
        param3 = 0.05   ' Radius (50mm)
        
        If WScript.Arguments.Count >= 2 Then param3 = CDbl(WScript.Arguments(1))
        If WScript.Arguments.Count >= 3 Then param1 = CDbl(WScript.Arguments(2))
        If WScript.Arguments.Count >= 4 Then param2 = CDbl(WScript.Arguments(3))
        
        WScript.Echo "Drawing circle..."
        swSketchMgr.CreateCircle param1, param2, 0, param1 + param3, param2, 0
        WScript.Echo "SUCCESS: Circle created"
        
    Case "rectangle"
        ' Default: rectangle centered at origin
        param1 = -0.05  ' X1
        param2 = -0.025 ' Y1
        param3 = 0.05   ' X2
        param4 = 0.025  ' Y2
        
        If WScript.Arguments.Count >= 2 Then param1 = CDbl(WScript.Arguments(1))
        If WScript.Arguments.Count >= 3 Then param2 = CDbl(WScript.Arguments(2))
        If WScript.Arguments.Count >= 4 Then param3 = CDbl(WScript.Arguments(3))
        If WScript.Arguments.Count >= 5 Then param4 = CDbl(WScript.Arguments(4))
        
        WScript.Echo "Drawing rectangle..."
        swSketchMgr.CreateCornerRectangle param1, param2, 0, param3, param4, 0
        WScript.Echo "SUCCESS: Rectangle created"
        
    Case "line"
        ' Default: horizontal line
        param1 = 0    ' X1
        param2 = 0    ' Y1
        param3 = 0.1  ' X2
        param4 = 0    ' Y2
        
        If WScript.Arguments.Count >= 2 Then param1 = CDbl(WScript.Arguments(1))
        If WScript.Arguments.Count >= 3 Then param2 = CDbl(WScript.Arguments(2))
        If WScript.Arguments.Count >= 4 Then param3 = CDbl(WScript.Arguments(3))
        If WScript.Arguments.Count >= 5 Then param4 = CDbl(WScript.Arguments(4))
        
        WScript.Echo "Drawing line..."
        swSketchMgr.CreateLine param1, param2, 0, param3, param4, 0
        WScript.Echo "SUCCESS: Line created"
        
    Case Else
        WScript.Echo "Error: Unknown shape type: " & shapeType
        WScript.Echo "Supported shapes: circle, rectangle, line"
        WScript.Quit(1)
End Select

WScript.Quit(0)
