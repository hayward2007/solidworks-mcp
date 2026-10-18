On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

WScript.StdOut.WriteLine "Model: " & swModel.GetTitle

' Rebuild and make sure model is ready
swModel.ForceRebuild3 True

' Get Simulation add-in
Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

If simObj Is Nothing Then
    WScript.StdOut.WriteLine "Loading Simulation add-in..."
    swApp.LoadAddIn "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\Simulation\cosworks.dll"
    WScript.Sleep 1000
    Set simObj = swApp.GetAddInObject("SldWorks.Simulation")
End If

WScript.StdOut.WriteLine "Simulation add-in: " & (Not simObj Is Nothing)

' Get COSMOSWORKS
Dim CWApp
Set CWApp = simObj.COSMOSWORKS

WScript.StdOut.WriteLine "COSMOSWORKS: " & (Not CWApp Is Nothing)

' Get active doc
Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

WScript.StdOut.WriteLine "CWDoc: " & (Not CWDoc Is Nothing)

If Not CWDoc Is Nothing Then
    ' Get study manager
    Dim StudyMgr
    Set StudyMgr = CWDoc.StudyManager
    
    WScript.StdOut.WriteLine "StudyManager: " & (Not StudyMgr Is Nothing)
    WScript.StdOut.WriteLine "Study count: " & StudyMgr.StudyCount
    
    ' Try to create study with different parameters
    ' swsAnalysisStudyTypeStatic = 0
    ' swsAnalysisStudySubTypeNone = 0
    
    Dim Study
    Dim errCode
    
    ' Method 1
    errCode = 0
    Set Study = StudyMgr.CreateNewStudy3("Static1", 0, 0, errCode)
    WScript.StdOut.WriteLine "Method 1 (CreateNewStudy3): errCode=" & errCode & ", Study=" & (Not Study Is Nothing)
    
    ' Method 2
    If Study Is Nothing Then
        Set Study = StudyMgr.CreateNewStudy2("Static1", 0, 0)
        WScript.StdOut.WriteLine "Method 2 (CreateNewStudy2): Study=" & (Not Study Is Nothing)
    End If
    
    ' Method 3
    If Study Is Nothing Then
        Set Study = StudyMgr.CreateNewStudy("Static1", 0, errCode)
        WScript.StdOut.WriteLine "Method 3 (CreateNewStudy): errCode=" & errCode & ", Study=" & (Not Study Is Nothing)
    End If
    
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "Final study count: " & StudyMgr.StudyCount
    
    If StudyMgr.StudyCount > 0 Then
        Set Study = StudyMgr.GetStudy(0)
        WScript.StdOut.WriteLine "Got study: " & Study.Name
    End If
End If