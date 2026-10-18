Option Explicit

' SolidWorks Connection Script
' Author: Samsaam Ali Baig
' Description: Connects to running SolidWorks instance or launches new one

Function ConnectToSolidWorks()
    Dim swApp
    
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
    
    Set ConnectToSolidWorks = swApp
End Function

' Execute connection if this script is run directly
If WScript.ScriptName = "connect_to_sw.vbs" Then
    Dim swApp
    Set swApp = ConnectToSolidWorks()
    WScript.Echo "SUCCESS: Connection established"
    WScript.Quit(0)
End If
