On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

swModel.ForceRebuild3 True

WScript.StdOut.WriteLine "Model: " & swModel.GetTitle

' Get Simulation
Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

Dim CWApp
Set CWApp = simObj.COSMOSWORKS

Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

If CWDoc Is Nothing Then
    WScript.StdOut.WriteLine "CWDoc not available"
    WScript.Quit
End If

' Get Study Manager
Dim StudyMgr
Set StudyMgr = CWDoc.StudyManager

Dim studyCount
studyCount = StudyMgr.StudyCount

WScript.StdOut.WriteLine "Study count: " & studyCount

If studyCount > 0 Then
    ' Get the first study
    Dim Study
    Set Study = StudyMgr.GetStudy(0)
    
    If Not Study Is Nothing Then
        WScript.StdOut.WriteLine ""
        WScript.StdOut.WriteLine "Found study: " & Study.Name
        WScript.StdOut.WriteLine "Study type: " & Study.AnalysisType
        
        ' Activate it
        Study.Activate
        WScript.StdOut.WriteLine "Study activated!"
        
        ' Now let's set up the analysis
        WScript.StdOut.WriteLine ""
        WScript.StdOut.WriteLine "Proceeding with analysis setup..."
    End If
Else
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "No studies found yet."
    WScript.StdOut.WriteLine "Please create a Static study in SolidWorks Simulation."
End If