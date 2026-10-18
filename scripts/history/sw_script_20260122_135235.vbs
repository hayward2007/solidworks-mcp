On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

' Try using ISimulation interface from model
Dim swSim
Set swSim = swModel.GetSimulation

If swSim Is Nothing Then
    WScript.StdOut.WriteLine "GetSimulation returned Nothing"
Else
    WScript.StdOut.WriteLine "Got ISimulation interface"
    
    ' Create study via ISimulation
    Dim swStudy
    Set swStudy = swSim.CreateStudy("PLA_50N_Analysis", 0, 0)
    
    If Not swStudy Is Nothing Then
        WScript.StdOut.WriteLine "SUCCESS: Study created via ISimulation!"
        WScript.StdOut.WriteLine "Study name: " & swStudy.Name
    Else
        WScript.StdOut.WriteLine "CreateStudy returned Nothing"
    End If
End If

' Also try running the New Study command
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Running New Study command..."

' Make window active
swApp.Visible = True

' RunCommand for Simulation New Study
swApp.RunCommand 57645, "" ' Simulation New Study command ID

WScript.Sleep 500

' Check study count now
Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

Dim CWApp
Set CWApp = simObj.COSMOSWORKS

Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

If Not CWDoc Is Nothing Then
    Dim StudyMgr
    Set StudyMgr = CWDoc.StudyManager
    WScript.StdOut.WriteLine "Study count after command: " & StudyMgr.StudyCount
End If