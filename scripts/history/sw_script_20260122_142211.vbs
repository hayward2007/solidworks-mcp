On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

' Make SolidWorks active and visible
swApp.Visible = True
swApp.WindowState = 2

Dim swModel
Set swModel = swApp.ActiveDoc

WScript.StdOut.WriteLine "Attempting to create study via UI automation..."

' Use WScript Shell
Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

' Activate SolidWorks window
WshShell.AppActivate "SOLIDWORKS"
WScript.Sleep 500

' Send keyboard shortcut for Simulation Study
' Try menu: Simulation > Study
WshShell.SendKeys "%s" ' Alt+S for Simulation menu (may vary)
WScript.Sleep 300

WshShell.SendKeys "{ESCAPE}" ' Cancel if wrong menu
WScript.Sleep 200

' Try right-click approach via context menu
' First, try the toolbar approach

WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "=============================================="
WScript.StdOut.WriteLine "MANUAL STEPS REQUIRED:"
WScript.StdOut.WriteLine "=============================================="
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "The Simulation API cannot create studies - this may be"
WScript.StdOut.WriteLine "due to license restrictions or API limitations."
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Please create the study manually:"
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "1. In SolidWorks, go to Simulation menu (or tab)"
WScript.StdOut.WriteLine "2. Click 'New Study'"
WScript.StdOut.WriteLine "3. Select 'Static' as the study type"
WScript.StdOut.WriteLine "4. Name it: Static_50N_PLA"
WScript.StdOut.WriteLine "5. Click OK"
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Once the study is created, tell me and I will:"
WScript.StdOut.WriteLine "- Apply the fixture (fixed face)"
WScript.StdOut.WriteLine "- Apply 50N force"
WScript.StdOut.WriteLine "- Create mesh"
WScript.StdOut.WriteLine "- Run the analysis"
WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "=============================================="