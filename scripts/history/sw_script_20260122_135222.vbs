On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

WScript.StdOut.WriteLine "Model: " & swModel.GetTitle

' Get Simulation
Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

Dim CWApp
Set CWApp = simObj.COSMOSWORKS

Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

If CWDoc Is Nothing Then
    WScript.StdOut.WriteLine "Initializing document in Simulation..."
    swModel.ForceRebuild3 True
    Set CWDoc = CWApp.ActiveDoc
End If

If CWDoc Is Nothing Then
    WScript.StdOut.WriteLine "ERROR: Cannot get CWDoc"
    WScript.Quit
End If

WScript.StdOut.WriteLine "CWDoc ready"

' Get Study Manager
Dim StudyMgr
Set StudyMgr = CWDoc.StudyManager

WScript.StdOut.WriteLine "Current study count: " & StudyMgr.StudyCount

' Create static study (type 0)
Dim Study
Dim errCode

Set Study = StudyMgr.CreateNewStudy3("PLA_Cylinder_50N", 0, 0, errCode)

WScript.StdOut.WriteLine "CreateNewStudy3 error code: " & errCode

If Study Is Nothing Then
    WScript.StdOut.WriteLine "Trying alternate creation method..."
    Set Study = StudyMgr.CreateNewStudy2("PLA_Cylinder_50N", 0, 0)
End If

If Study Is Nothing And StudyMgr.StudyCount > 0 Then
    Set Study = StudyMgr.GetStudy(0)
    WScript.StdOut.WriteLine "Using existing study: " & Study.Name
End If

If Not Study Is Nothing Then
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "SUCCESS: Study ready - " & Study.Name
    Study.Activate
    WScript.StdOut.WriteLine "Study activated"
    WScript.StdOut.WriteLine "Study type: " & Study.AnalysisType
Else
    WScript.StdOut.WriteLine "ERROR: Could not create or get study"
End If

WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Final study count: " & StudyMgr.StudyCount