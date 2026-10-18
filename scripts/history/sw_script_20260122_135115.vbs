On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

' Try to load the Simulation add-in
Dim simPath
simPath = "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\Simulation\cosworks.dll"

WScript.StdOut.WriteLine "Attempting to load Simulation add-in..."

Dim loadResult
loadResult = swApp.LoadAddIn(simPath)

WScript.StdOut.WriteLine "LoadAddIn result: " & loadResult
' -1 = already loaded, 0 = success, other = error

' Wait a moment
WScript.Sleep 1000

' Try to get the add-in object now
Dim simObj
Set simObj = swApp.GetAddInObject("SldWorks.Simulation")

If simObj Is Nothing Then
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "Simulation still not available."
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "Please manually enable Simulation:"
    WScript.StdOut.WriteLine "1. In SolidWorks, go to Tools > Add-Ins"
    WScript.StdOut.WriteLine "2. Check 'SOLIDWORKS Simulation' (both boxes)"
    WScript.StdOut.WriteLine "3. Click OK"
    WScript.StdOut.WriteLine ""
    WScript.StdOut.WriteLine "Then tell me when ready."
Else
    WScript.StdOut.WriteLine "SUCCESS: Simulation add-in is now loaded!"
    
    Dim cwApp
    Set cwApp = simObj.COSMOSWORKS
    
    If Not cwApp Is Nothing Then
        WScript.StdOut.WriteLine "COSMOSWORKS interface available"
    End If
End If