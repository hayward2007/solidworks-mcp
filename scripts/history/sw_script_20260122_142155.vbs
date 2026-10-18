On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

' Check Simulation license type
Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

Dim CWApp  
Set CWApp = simObj.COSMOSWORKS

WScript.StdOut.WriteLine "Checking Simulation status..."

' Try to get license info
Dim licType
licType = CWApp.LicenseType
WScript.StdOut.WriteLine "License type: " & licType

' License types:
' 0 = No license
' 1 = Simulation Standard (swsLicenseTypeSimulationStandard)
' 2 = Simulation Professional (swsLicenseTypeSimulationProfessional)
' 3 = Simulation Premium (swsLicenseTypeSimulationPremium)

If licType = 0 Then
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "WARNING: No Simulation license detected!"
    WScript.StdOut.WriteLine "You need a valid SOLIDWORKS Simulation license to create studies."
End If

' Check version
Dim simVer
simVer = CWApp.Version
WScript.StdOut.WriteLine "Simulation version: " & simVer

' Try to see if it's a permissions issue
Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

If Not CWDoc Is Nothing Then
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "CWDoc available"
    
    ' Check document type compatibility
    Dim docType
    docType = CWDoc.DocType
    WScript.StdOut.WriteLine "Document type: " & docType
    ' 0 = Part, 1 = Assembly
End If

If Err.Number <> 0 Then
    WScript.StdOut.WriteLine "Error accessing properties: " & Err.Description
    Err.Clear
End If