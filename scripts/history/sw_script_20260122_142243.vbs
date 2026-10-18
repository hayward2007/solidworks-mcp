On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim swModel
Set swModel = swApp.ActiveDoc

' Force rebuild
swModel.ForceRebuild3 True
swModel.GraphicsRedraw2

' List all features to see if simulation study appears
WScript.StdOut.WriteLine "Feature tree:"
Dim swFeat
Set swFeat = swModel.FirstFeature

Do While Not swFeat Is Nothing
    WScript.StdOut.WriteLine "  " & swFeat.Name & " [" & swFeat.GetTypeName & "]"
    Set swFeat = swFeat.GetNextFeature
Loop

' Check configuration manager for simulation configurations
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Configurations:"
Dim configs
configs = swModel.GetConfigurationNames

If IsArray(configs) Then
    Dim i
    For i = 0 To UBound(configs)
        WScript.StdOut.WriteLine "  " & configs(i)
    Next
End If

' Save and check again
Dim errors, warnings
swModel.Save3 1, errors, warnings

WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Model saved"

' Try to access through COSMOSWORKS one more time
Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

Dim CWApp
Set CWApp = simObj.COSMOSWORKS

swModel.ForceRebuild3 True

Dim CWDoc
Set CWDoc = CWApp.ActiveDoc

If Not CWDoc Is Nothing Then
    Dim StudyMgr
    Set StudyMgr = CWDoc.StudyManager
    
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "Study count: " & StudyMgr.StudyCount
    
    Dim activeStudyIdx
    activeStudyIdx = StudyMgr.ActiveStudy
    WScript.StdOut.WriteLine "Active study index: " & activeStudyIdx
End If