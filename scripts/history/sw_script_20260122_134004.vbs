On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

' Make SolidWorks window active
swApp.Visible = True
swApp.WindowState = 2 ' Maximize

' Use Shell to send keyboard shortcuts
Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

' Activate SolidWorks window
WshShell.AppActivate "SOLIDWORKS"
WScript.Sleep 500

' Use keyboard shortcuts to access material
' Typically right-click on part requires selecting the part first

' First, try to select the solid body
Dim bodies
bodies = swModel.GetBodies2(0, False)

If IsArray(bodies) Then
    WScript.StdOut.WriteLine "Found " & UBound(bodies) + 1 & " bodies"
    
    Dim body
    Set body = bodies(0)
    
    If Not body Is Nothing Then
        Dim bRet
        bRet = body.Select2(False, Nothing)
        WScript.StdOut.WriteLine "Body selected: " & bRet
    End If
End If

' Try applying material via the model document
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Trying direct material assignment..."

' Use SetMaterialPropertyValues with explicit array
Dim matProps(9)
matProps(0) = CDbl(3500000000)  ' Elastic modulus 3.5 GPa
matProps(1) = CDbl(0.36)        ' Poisson ratio
matProps(2) = CDbl(1287000000)  ' Shear modulus
matProps(3) = CDbl(0.000068)    ' Thermal expansion
matProps(4) = CDbl(0.13)        ' Thermal conductivity
matProps(5) = CDbl(1800)        ' Specific heat
matProps(6) = CDbl(1240)        ' Density
matProps(7) = CDbl(50000000)    ' Tensile strength
matProps(8) = CDbl(60000000)    ' Yield strength
matProps(9) = CDbl(0.5)         ' Hardening

swModel.MaterialPropertyValues = matProps

If Err.Number <> 0 Then
    WScript.StdOut.WriteLine "Error: " & Err.Description
    Err.Clear
Else
    WScript.StdOut.WriteLine "MaterialPropertyValues assigned"
End If

' Verify
Dim readBack
readBack = swModel.MaterialPropertyValues

If IsArray(readBack) Then
    WScript.StdOut.WriteLine "Read back values:"
    WScript.StdOut.WriteLine "  E = " & readBack(0) & " Pa"
    WScript.StdOut.WriteLine "  v = " & readBack(1)
    WScript.StdOut.WriteLine "  Density = " & readBack(6) & " kg/m³"
Else
    WScript.StdOut.WriteLine "Could not read back (not an array)"
End If

' Force update
swModel.ForceRebuild3 True
swModel.GraphicsRedraw2