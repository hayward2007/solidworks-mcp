On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

WScript.StdOut.WriteLine "Model: " & swModel.GetTitle

' Get ModelDocExtension
Dim swModelDocExt
Set swModelDocExt = swModel.Extension

' Try setting material with just the material name (no database)
' This works if the material is in any loaded database
Dim config
config = swModel.GetActiveConfiguration.Name
WScript.StdOut.WriteLine "Active config: " & config

' Try different API approaches
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Attempting various API methods..."

' Method 1: ModelDoc2::SetMaterialPropertyName
Dim res1
res1 = swModel.SetMaterialPropertyName(config, "ABS")
WScript.StdOut.WriteLine "ModelDoc2.SetMaterialPropertyName: " & res1

' Method 2: Through body
Dim swBody
Set swBody = swModel.GetBodies2(0, False)(0)

If Not swBody Is Nothing Then
    WScript.StdOut.WriteLine "Got body: " & swBody.Name
    
    ' Try SetMaterialProperty on body
    Dim res2
    res2 = swBody.SetMaterialProperty(config, "solidworks materials.sldmat", "ABS")
    WScript.StdOut.WriteLine "Body.SetMaterialProperty: " & res2
End If

' Method 3: Feature based approach
Dim swFeat
Set swFeat = swModel.FirstFeature

Do While Not swFeat Is Nothing
    If swFeat.GetTypeName = "MaterialFolder" Then
        WScript.StdOut.WriteLine "Found MaterialFolder feature: " & swFeat.Name
        
        ' Try to modify this feature
        swFeat.Select2 False, 0
        WScript.StdOut.WriteLine "MaterialFolder selected"
    End If
    Set swFeat = swFeat.GetNextFeature
Loop

' Check current state
Dim matCheck
matCheck = swModel.GetMaterialPropertyName(config)
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Current material name: " & matCheck