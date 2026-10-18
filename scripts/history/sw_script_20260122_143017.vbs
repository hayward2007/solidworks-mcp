On Error Resume Next

' DIAGNOSTIC SCRIPT - Identifying all issues with Simulation API

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

WScript.StdOut.WriteLine "=============================================="
WScript.StdOut.WriteLine "SOLIDWORKS SIMULATION API DIAGNOSTIC REPORT"
WScript.StdOut.WriteLine "=============================================="
WScript.StdOut.WriteLine ""

' 1. SOLIDWORKS VERSION
WScript.StdOut.WriteLine "1. SOLIDWORKS VERSION INFO"
WScript.StdOut.WriteLine "   Version: " & swApp.RevisionNumber
WScript.StdOut.WriteLine "   Build: " & swApp.GetBuildNumbers2
WScript.StdOut.WriteLine ""

' 2. SIMULATION ADD-IN STATUS
WScript.StdOut.WriteLine "2. SIMULATION ADD-IN STATUS"

Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

If simObj Is Nothing Then
    WScript.StdOut.WriteLine "   Status: NOT LOADED"
    WScript.StdOut.WriteLine "   Issue: Add-in not available via GetAddInObject"
Else
    WScript.StdOut.WriteLine "   Status: LOADED"
    WScript.StdOut.WriteLine "   Object Type: " & TypeName(simObj)
End If
WScript.StdOut.WriteLine ""

' 3. COSMOSWORKS INTERFACE
WScript.StdOut.WriteLine "3. COSMOSWORKS INTERFACE"

If Not simObj Is Nothing Then
    Dim CWApp
    Set CWApp = simObj.COSMOSWORKS
    
    If CWApp Is Nothing Then
        WScript.StdOut.WriteLine "   COSMOSWORKS: NOT AVAILABLE"
        WScript.StdOut.WriteLine "   Issue: simObj.COSMOSWORKS returns Nothing"
    Else
        WScript.StdOut.WriteLine "   COSMOSWORKS: AVAILABLE"
        WScript.StdOut.WriteLine "   Object Type: " & TypeName(CWApp)
        
        ' Try to get properties
        Dim licType, simVer
        licType = CWApp.LicenseType
        simVer = CWApp.Version
        
        WScript.StdOut.WriteLine "   License Type: " & licType & " (0=None, 1=Std, 2=Pro, 3=Premium)"
        WScript.StdOut.WriteLine "   Sim Version: " & simVer
        
        If Err.Number <> 0 Then
            WScript.StdOut.WriteLine "   Property Error: " & Err.Description
            Err.Clear
        End If
    End If
End If
WScript.StdOut.WriteLine ""

' 4. ACTIVE DOCUMENT IN SIMULATION
WScript.StdOut.WriteLine "4. SIMULATION DOCUMENT STATUS"

If Not CWApp Is Nothing Then
    Dim CWDoc
    Set CWDoc = CWApp.ActiveDoc
    
    If CWDoc Is Nothing Then
        WScript.StdOut.WriteLine "   CWDoc: NOT AVAILABLE"
        WScript.StdOut.WriteLine "   Issue: CWApp.ActiveDoc returns Nothing"
    Else
        WScript.StdOut.WriteLine "   CWDoc: AVAILABLE"
        WScript.StdOut.WriteLine "   Object Type: " & TypeName(CWDoc)
    End If
End If
WScript.StdOut.WriteLine ""

' 5. STUDY MANAGER
WScript.StdOut.WriteLine "5. STUDY MANAGER STATUS"

If Not CWDoc Is Nothing Then
    Dim StudyMgr
    Set StudyMgr = CWDoc.StudyManager
    
    If StudyMgr Is Nothing Then
        WScript.StdOut.WriteLine "   StudyManager: NOT AVAILABLE"
    Else
        WScript.StdOut.WriteLine "   StudyManager: AVAILABLE"
        WScript.StdOut.WriteLine "   Object Type: " & TypeName(StudyMgr)
        WScript.StdOut.WriteLine "   Study Count: " & StudyMgr.StudyCount
        WScript.StdOut.WriteLine "   Active Study: " & StudyMgr.ActiveStudy
    End If
End If
WScript.StdOut.WriteLine ""

' 6. STUDY CREATION TEST
WScript.StdOut.WriteLine "6. STUDY CREATION TEST"

If Not StudyMgr Is Nothing Then
    Dim testStudy
    Dim errCode
    
    ' Test CreateNewStudy3
    Err.Clear
    Set testStudy = StudyMgr.CreateNewStudy3("TestStudy", 0, 0, errCode)
    WScript.StdOut.WriteLine "   CreateNewStudy3:"
    WScript.StdOut.WriteLine "      Result: " & (Not testStudy Is Nothing)
    WScript.StdOut.WriteLine "      Error Code: " & errCode
    If Err.Number <> 0 Then
        WScript.StdOut.WriteLine "      VBScript Error: " & Err.Number & " - " & Err.Description
        Err.Clear
    End If
    
    ' Test CreateNewStudy2
    Err.Clear
    Set testStudy = StudyMgr.CreateNewStudy2("TestStudy2", 0, 0)
    WScript.StdOut.WriteLine "   CreateNewStudy2:"
    WScript.StdOut.WriteLine "      Result: " & (Not testStudy Is Nothing)
    If Err.Number <> 0 Then
        WScript.StdOut.WriteLine "      VBScript Error: " & Err.Number & " - " & Err.Description
        Err.Clear
    End If
End If
WScript.StdOut.WriteLine ""

' 7. ISIMULATION INTERFACE (Alternate path)
WScript.StdOut.WriteLine "7. ISIMULATION INTERFACE (Model-based)"

Dim swModel
Set swModel = swApp.ActiveDoc

Dim swSim
Set swSim = swModel.GetSimulation

If swSim Is Nothing Then
    WScript.StdOut.WriteLine "   ISimulation: NOT AVAILABLE"
    WScript.StdOut.WriteLine "   Issue: swModel.GetSimulation returns Nothing"
Else
    WScript.StdOut.WriteLine "   ISimulation: AVAILABLE"
    WScript.StdOut.WriteLine "   Object Type: " & TypeName(swSim)
End If
WScript.StdOut.WriteLine ""

' 8. VBSCRIPT LIMITATIONS TEST
WScript.StdOut.WriteLine "8. VBSCRIPT/COM INTERFACE TEST"
WScript.StdOut.WriteLine "   Script Engine: VBScript (cscript.exe)"
WScript.StdOut.WriteLine "   Data Type Support: Variant only (no strong typing)"
WScript.StdOut.WriteLine "   Error Handling: On Error Resume Next (silent failures)"
WScript.StdOut.WriteLine ""

WScript.StdOut.WriteLine "=============================================="
WScript.StdOut.WriteLine "END OF DIAGNOSTIC REPORT"
WScript.StdOut.WriteLine "=============================================="