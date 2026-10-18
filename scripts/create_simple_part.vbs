Option Explicit

' Create Simple Part Script
' Author: Samsaam Ali Baig
' Description: Creates a new part document in SolidWorks

Dim swApp, swModel, templatePath

' Connect to SolidWorks
On Error Resume Next
WScript.Echo "Connecting to SolidWorks..."
Set swApp = GetObject(, "SldWorks.Application")

If Err.Number <> 0 Then
    Err.Clear
    WScript.Echo "SolidWorks is not running. Launching SolidWorks..."
    Set swApp = CreateObject("SldWorks.Application")
    
    If Err.Number <> 0 Then
        WScript.Echo "Error connecting to SolidWorks: " & Err.Description
        WScript.Quit(1)
    End If
End If

swApp.Visible = True
WScript.Echo "Successfully connected to SolidWorks."
On Error Goto 0

' Create new document
On Error Resume Next
WScript.Echo "Creating new document..."

' Get template path from user preferences
templatePath = swApp.GetUserPreferenceStringValue(9)

' If not found, try default path
If templatePath = "" Then
    templatePath = swApp.GetExecutablePath
    templatePath = Left(templatePath, InStrRev(templatePath, "\"))
    templatePath = templatePath & "data\templates\Part.prtdot"
    
    If Err.Number <> 0 Then
        WScript.Echo "Error getting template path: " & Err.Description
        templatePath = "C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2023\templates\Part.prtdot"
        Err.Clear
    End If
End If

WScript.Echo "Using template: " & templatePath

' Create new document
Set swModel = swApp.NewDocument(templatePath, 0, 0, 0)

If Err.Number <> 0 Then
    WScript.Echo "Error creating document: " & Err.Description
    WScript.Quit(1)
End If

If swModel Is Nothing Then
    WScript.Echo "Error: Model not created."
    WScript.Quit(1)
End If

WScript.Echo "New document created successfully."

' Set isometric view
swModel.ShowNamedView2 "*Isometric", 7
swModel.ViewZoomtofit2

WScript.Echo "SUCCESS: New part file created."
WScript.Quit(0)
