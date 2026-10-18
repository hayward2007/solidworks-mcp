On Error Resume Next

' Recorded macro style for creating simulation study

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

Dim Part
Set Part = swApp.ActiveDoc

WScript.StdOut.WriteLine "Part: " & Part.GetTitle
WScript.StdOut.WriteLine "Material: PLA (confirmed)"

' Access Simulation through standard path
Dim COSMOSWORKS
Set COSMOSWORKS = swApp.GetAddInObject("SldWorks.Simulation")

If COSMOSWORKS Is Nothing Then
    WScript.StdOut.WriteLine "ERROR: Cannot get Simulation add-in"
    WScript.Quit 1
End If

Dim COSMOSObject
Set COSMOSObject = COSMOSWORKS.COSMOSWORKS

If COSMOSObject Is Nothing Then
    WScript.StdOut.WriteLine "ERROR: Cannot get COSMOSWORKS object"
    WScript.Quit 1
End If

Dim CWAddinCallBack
Set CWAddinCallBack = COSMOSObject

Dim ActDoc
Set ActDoc = CWAddinCallBack.ActiveDoc

If ActDoc Is Nothing Then
    WScript.StdOut.WriteLine "ERROR: Cannot get ActiveDoc in Simulation"
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "This typically means:"
    WScript.StdOut.WriteLine "1. Simulation license is not active, OR"
    WScript.StdOut.WriteLine "2. Document needs to be initialized in Simulation"
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "Please try: Click on Simulation tab in SolidWorks"
    WScript.Quit 1
End If

Dim StudyMngr
Set StudyMngr = ActDoc.StudyManager

WScript.StdOut.WriteLine "StudyManager obtained"
WScript.StdOut.WriteLine "Current studies: " & StudyMngr.StudyCount

' Try all possible study creation methods
Dim Study
Dim errCode

' Method A: CreateNewStudy3 with explicit parameters
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Trying CreateNewStudy3..."
Set Study = StudyMngr.CreateNewStudy3("Static 1", CLng(0), CLng(0), errCode)
WScript.StdOut.WriteLine "  Result: Study=" & (Not Study Is Nothing) & ", errCode=" & errCode

' Method B: CreateNewStudy2
If Study Is Nothing Then
    WScript.StdOut.WriteLine "Trying CreateNewStudy2..."
    Set Study = StudyMngr.CreateNewStudy2("Static 1", CLng(0), CLng(0))
    WScript.StdOut.WriteLine "  Result: Study=" & (Not Study Is Nothing)
End If

' Method C: CreateNewStudy
If Study Is Nothing Then
    WScript.StdOut.WriteLine "Trying CreateNewStudy..."
    Set Study = StudyMngr.CreateNewStudy("Static 1", CLng(0), errCode)
    WScript.StdOut.WriteLine "  Result: Study=" & (Not Study Is Nothing) & ", errCode=" & errCode
End If

WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Final study count: " & StudyMngr.StudyCount

If StudyMngr.StudyCount > 0 Then
    Set Study = StudyMngr.GetStudy(0)
    Study.Activate
    WScript.StdOut.WriteLine "Study activated: " & Study.Name
End If