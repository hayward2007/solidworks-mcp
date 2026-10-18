On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

WScript.StdOut.WriteLine "Model: " & swModel.GetTitle

' Check current material
Dim swFeat
Set swFeat = swModel.FirstFeature

Do While Not swFeat Is Nothing
    If swFeat.GetTypeName = "MaterialFolder" Then
        WScript.StdOut.WriteLine "Current material: " & swFeat.Name
        Exit Do
    End If
    Set swFeat = swFeat.GetNextFeature
Loop

' Try to find and apply PLA from various sources
Dim dbPaths
dbPaths = Array( _
    "solidworks materials.sldmat", _
    "custom materials.sldmat", _
    "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english\sldmaterials\solidworks materials.sldmat", _
    "C:\Users\Samsaam Ali Baig\AppData\Roaming\SolidWorks\SOLIDWORKS 2025\materials\Custom Materials.sldmat", _
    "E:\01_USBM\S9\PROJ903_RoboCUP\Design\MCP_Solidworks\3D_Print_Materials.sldmat" _
)

Dim bRet
Dim dbPath
Dim found
found = False

WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Searching for PLA material..."

For Each dbPath In dbPaths
    bRet = swModel.SetMaterialPropertyName2("Default", dbPath, "PLA")
    If bRet Then
        WScript.StdOut.WriteLine "SUCCESS: Found PLA in " & dbPath
        found = True
        Exit For
    End If
Next

If Not found Then
    ' Try with just the name (searches all loaded databases)
    bRet = swModel.SetMaterialPropertyName("Default", "PLA")
    If bRet Then
        WScript.StdOut.WriteLine "SUCCESS: Found PLA in loaded databases"
        found = True
    End If
End If

' Check final material
swModel.ForceRebuild3 True

Set swFeat = swModel.FirstFeature
Do While Not swFeat Is Nothing
    If swFeat.GetTypeName = "MaterialFolder" Then
        WScript.StdOut.WriteLine ""
        WScript.StdOut.WriteLine "Material after search: " & swFeat.Name
        Exit Do
    End If
    Set swFeat = swFeat.GetNextFeature
Loop