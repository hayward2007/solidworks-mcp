On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

' Save with PLA material
swModel.ForceRebuild3 True
Dim errors, warnings
swModel.Save3 1, errors, warnings

WScript.StdOut.WriteLine "Model saved with PLA material"

' Now try to access Simulation
Dim COSMOSWORKS
Set COSMOSWORKS = swApp.GetAddInObject("SldWorks.Simulation")

If COSMOSWORKS Is Nothing Then
    WScript.StdOut.WriteLine "Simulation add-in not loaded"
    WScript.StdOut.WriteLine "Please enable it in Tools > Add-Ins"
    WScript.Quit
End If

Dim CWApp
Set CWApp = COSMOSWORKS.COSMOSWORKS

If CWApp Is Nothing Then
    WScript.StdOut.WriteLine "COSMOSWORKS interface not available"
    WScript.Quit
End If

Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

If CWDoc Is Nothing Then
    WScript.StdOut.WriteLine "CWDoc not available - Simulation may need initialization"
    WScript.StdOut.WriteLine "Please click on the Simulation tab in SolidWorks"
    WScript.Quit
End If

WScript.StdOut.WriteLine "Simulation interface ready"

' Get Study Manager
Dim StudyMgr
Set StudyMgr = CWDoc.StudyManager

WScript.StdOut.WriteLine "Study count: " & StudyMgr.StudyCount

' Create new static study
Dim newStudy
Dim errCode

Set newStudy = StudyMgr.CreateNewStudy3("Static_50N_PLA", 0, 0, errCode)

If newStudy Is Nothing Then
    WScript.StdOut.WriteLine "CreateNewStudy3 failed, error: " & errCode
    
    ' Try alternate methods
    Set newStudy = StudyMgr.CreateNewStudy("Static_50N_PLA", 0, errCode)
    
    If newStudy Is Nothing Then
        WScript.StdOut.WriteLine "CreateNewStudy also failed"
        
        ' Check if study already exists
        If StudyMgr.StudyCount > 0 Then
            Set newStudy = StudyMgr.GetStudy(0)
            WScript.StdOut.WriteLine "Using existing study: " & newStudy.Name
        End If
    End If
End If

If Not newStudy Is Nothing Then
    WScript.StdOut.WriteLine "Study available: " & newStudy.Name
    newStudy.Activate
    WScript.StdOut.WriteLine "Study activated"
End If