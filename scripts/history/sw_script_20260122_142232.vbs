On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

' Try ISimulation from the model
Dim swSim
Set swSim = swModel.Extension.GetSimulation

If swSim Is Nothing Then
    WScript.StdOut.WriteLine "Extension.GetSimulation returned Nothing"
    
    ' Try alternate path
    Set swSim = swModel.GetSimulation
    
    If swSim Is Nothing Then
        WScript.StdOut.WriteLine "ModelDoc.GetSimulation also returned Nothing"
    End If
End If

If Not swSim Is Nothing Then
    WScript.StdOut.WriteLine "Got ISimulation interface"
    
    ' Try to create study
    Dim swStudy
    
    ' ISimulation::CreateStudy2(name, type, subtype)
    Set swStudy = swSim.CreateStudy2("Static_Analysis", 0, 0)
    
    If Not swStudy Is Nothing Then
        WScript.StdOut.WriteLine "SUCCESS: Created study via ISimulation!"
        WScript.StdOut.WriteLine "Study: " & swStudy.Name
    Else
        WScript.StdOut.WriteLine "CreateStudy2 returned Nothing"
        
        ' Try CreateStudy
        Set swStudy = swSim.CreateStudy("Static_Analysis", 0)
        
        If Not swStudy Is Nothing Then
            WScript.StdOut.WriteLine "SUCCESS: Created study via CreateStudy!"
        Else
            WScript.StdOut.WriteLine "CreateStudy also returned Nothing"
        End If
    End If
End If

' Final check through COSMOSWORKS
Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

Dim CWApp
Set CWApp = simObj.COSMOSWORKS

Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

If Not CWDoc Is Nothing Then
    Dim StudyMgr
    Set StudyMgr = CWDoc.StudyManager
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "Final study count: " & StudyMgr.StudyCount
End If

If Err.Number <> 0 Then
    WScript.StdOut.WriteLine "Error: " & Err.Description
End If