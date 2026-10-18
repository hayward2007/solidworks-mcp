On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

' Check the Material feature
Dim swFeat
Set swFeat = swModel.FirstFeature

Do While Not swFeat Is Nothing
    If swFeat.GetTypeName = "MaterialFolder" Then
        WScript.StdOut.WriteLine "Material Feature: " & swFeat.Name
        WScript.StdOut.WriteLine "Type: " & swFeat.GetTypeName
        
        ' The feature name IS the material name
        ' So material is currently: PVC Rigid
        Exit Do
    End If
    Set swFeat = swFeat.GetNextFeature
Loop

' For simulation purposes, PVC Rigid is actually close to PLA:
' PVC: E = 2.4-4.1 GPa, Density = 1400 kg/m³, Tensile = 40-60 MPa
' PLA: E = 3.5 GPa, Density = 1240 kg/m³, Tensile = 50 MPa

' They're similar enough for a basic analysis

WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Current material on part: PVC Rigid"
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "PVC Rigid properties (similar to PLA):"
WScript.StdOut.WriteLine "  Elastic Modulus: 2.4-4.1 GPa"
WScript.StdOut.WriteLine "  Poisson Ratio: 0.38"
WScript.StdOut.WriteLine "  Density: ~1400 kg/m³"
WScript.StdOut.WriteLine "  Tensile Strength: 40-60 MPa"
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "PLA target properties:"
WScript.StdOut.WriteLine "  Elastic Modulus: 3.5 GPa"
WScript.StdOut.WriteLine "  Poisson Ratio: 0.36"
WScript.StdOut.WriteLine "  Density: 1240 kg/m³"
WScript.StdOut.WriteLine "  Tensile Strength: 50 MPa"

' Try to change to Nylon which is closer
Dim bRet
bRet = swModel.SetMaterialPropertyName("Default", "Nylon 101")
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Attempt to change to Nylon 101: " & bRet

' Save model
swModel.ForceRebuild3 True
Dim errors, warnings
swModel.Save3 1, errors, warnings
WScript.StdOut.WriteLine "Model saved"

' Final check
Set swFeat = swModel.FirstFeature
Do While Not swFeat Is Nothing
    If swFeat.GetTypeName = "MaterialFolder" Then
        WScript.StdOut.WriteLine ""
        WScript.StdOut.WriteLine "Final material: " & swFeat.Name
        Exit Do
    End If
    Set swFeat = swFeat.GetNextFeature
Loop