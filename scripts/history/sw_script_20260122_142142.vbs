On Error Resume Next

' This script mimics recorded macro format exactly

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim Part
Set Part = swApp.ActiveDoc

Dim COSMOSWORKS
Set COSMOSWORKS = swApp.GetAddInObject("SldWorks.Simulation")

Dim COSMOSObject
Set COSMOSObject = COSMOSWORKS.COSMOSWORKS

Dim CWAddinCallBack
Set CWAddinCallBack = COSMOSObject

Dim ActDoc
Set ActDoc = CWAddinCallBack.ActiveDoc

WScript.StdOut.WriteLine "ActDoc valid: " & (Not ActDoc Is Nothing)

Dim StudyMngr
Set StudyMngr = ActDoc.StudyManager

Dim Study
Dim NStudy

' Try different study type constants
' 0 = swsAnalysisStudyTypeStatic
' 1 = swsAnalysisStudyTypeFrequency  
' 2 = swsAnalysisStudyTypeBuckling
' 3 = swsAnalysisStudyTypeThermal

Dim studyType
studyType = 0 ' Static

Dim meshType
meshType = 0 ' Solid mesh

' Try API from SW2024/2025
Set NStudy = StudyMngr.CreateNewStudy3("Static 1", studyType, meshType, Null)

WScript.StdOut.WriteLine "CreateNewStudy3 result: " & (Not NStudy Is Nothing)

If NStudy Is Nothing Then
    ' Check if there's an active study
    Dim activeIdx
    activeIdx = StudyMngr.ActiveStudy
    WScript.StdOut.WriteLine "Active study index: " & activeIdx
    
    ' Try to get study by index
    If StudyMngr.StudyCount > 0 Then
        Set Study = StudyMngr.GetStudy(0)
        WScript.StdOut.WriteLine "Got existing study"
    End If
Else
    Set Study = NStudy
    WScript.StdOut.WriteLine "New study created"
End If

' Check study count
WScript.StdOut.WriteLine "Study count: " & StudyMngr.StudyCount

If Err.Number <> 0 Then
    WScript.StdOut.WriteLine "Error: " & Err.Number & " - " & Err.Description
End If