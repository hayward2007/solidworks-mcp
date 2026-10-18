On Error Resume Next

Dim swApp
Set swApp = GetObject(, "SldWorks.Application")

' Make SolidWorks visible and active
swApp.Visible = True
swApp.WindowState = 2 ' Maximized

Dim swModel
Set swModel = swApp.ActiveDoc

WScript.StdOut.WriteLine "Model: " & swModel.GetTitle

' Use WScript Shell to automate
Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

' Activate SolidWorks
Dim activated
activated = WshShell.AppActivate("SOLIDWORKS")
WScript.StdOut.WriteLine "Window activated: " & activated

WScript.Sleep 500

' Try to access Simulation menu via keyboard
' Alt key to access menu bar
WshShell.SendKeys "%"
WScript.Sleep 200

' Type "Simulation" to find the menu
WshShell.SendKeys "Simulation"
WScript.Sleep 300

' Press Enter or Down arrow
WshShell.SendKeys "{ENTER}"
WScript.Sleep 300

WScript.StdOut.WriteLine "Attempted to open Simulation menu"

' Alternative: Use the Simulation toolbar/tab
' First escape any open menus
WshShell.SendKeys "{ESCAPE}"
WScript.Sleep 200

WScript.StdOut.WriteLine ""
WScript.StdOut.WriteLine "Please check SolidWorks - you may need to:"
WScript.StdOut.WriteLine "1. Click on the Simulation tab at the bottom"
WScript.StdOut.WriteLine "2. Right-click in the Simulation tree"
WScript.StdOut.WriteLine "3. Select 'New Study' > 'Static'"