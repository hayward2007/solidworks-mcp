On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

swApp.Visible = True

' Try running specific Simulation commands
' These command IDs are for Simulation functions

WScript.StdOut.WriteLine "Attempting UI commands for New Study..."

' Command IDs to try
Dim cmds
cmds = Array(57645, 57646, 57647, 40050, 40051, 40052, 40053)

Dim cmd
For Each cmd In cmds
    swApp.RunCommand cmd, ""
    WScript.Sleep 100
Next

WScript.StdOut.WriteLine "Commands sent"

' Check if study was created
WScript.Sleep 1000

Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

Dim CWApp
Set CWApp = simObj.COSMOSWORKS

Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

If Not CWDoc Is Nothing Then
    Dim StudyMgr
    Set StudyMgr = CWDoc.StudyManager
    WScript.StdOut.WriteLine "Study count after commands: " & StudyMgr.StudyCount
    
    If StudyMgr.StudyCount > 0 Then
        Dim Study
        Set Study = StudyMgr.GetStudy(0)
        WScript.StdOut.WriteLine "Study found: " & Study.Name
    End If
End If