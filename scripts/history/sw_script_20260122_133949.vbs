On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

' Add custom material database to SolidWorks
Dim customDBPath
customDBPath = "E:\01_USBM\S9\PROJ903_RoboCUP\Design\MCP_Solidworks\3D_Print_Materials.sldmat"

' AddMaterialDatabase adds a database to SolidWorks
Dim bRet
bRet = swApp.AddMaterialDatabase(customDBPath)
WScript.StdOut.WriteLine "AddMaterialDatabase result: " & bRet

' List available databases now
Dim matDBs
matDBs = swApp.GetMaterialDatabases

If IsArray(matDBs) Then
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "Available material databases:"
    Dim i
    For i = LBound(matDBs) To UBound(matDBs)
        WScript.StdOut.WriteLine "  " & matDBs(i)
    Next
End If

' Now try to apply PLA again
bRet = swModel.SetMaterialPropertyName2("Default", customDBPath, "PLA")
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Apply PLA result: " & bRet

' Check using GetMaterialPropertyName
Dim matName
matName = swModel.GetMaterialPropertyName("Default")
WScript.StdOut.WriteLine "Current material: " & matName