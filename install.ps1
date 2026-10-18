# SolidWorks MCP - one-line installer for Windows
#
#   irm https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/install.ps1 | iex
#
# With options, e.g. install Python 3.13 with winget when no Python 3.10+ is found:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/install.ps1))) -InstallPython
# From a downloaded copy of the repository:
#   powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 [options]
#
# What it does: gets the code (git clone, or the GitHub zip when git is missing; an existing
# install is updated), finds a 64-bit Python 3.10+, then runs setup_mcp.py --yes, which creates
# .venv, installs requirements.txt, self-tests the server and registers it in Claude Desktop and
# Claude Code together with the solidworks-design skill. Safe to run again.
#
# Options:
#   -InstallDir <path>      where the code goes (default: the copy this script is in,
#                           otherwise $HOME\solidworks-mcp)
#   -InstallPython          install Python 3.13 with winget if no Python 3.10+ is found
#   -NoClaudeDesktop, -NoClaudeCode, -NoSkill    leave that part alone
#   -DesktopConfig <paths>  claude_desktop_config.json files to update instead of the detected ones
#   -SkillsDir <path>       Claude Code skills folder (default: $HOME\.claude\skills)
#   -Uninstall              remove the registrations and the skill (keeps the folder)

param(
    [string]$InstallDir = '',
    [switch]$InstallPython,
    [switch]$NoClaudeDesktop,
    [switch]$NoClaudeCode,
    [switch]$NoSkill,
    [string[]]$DesktopConfig = @(),
    [string]$SkillsDir = '',
    [switch]$Uninstall,
    [string]$Repo = 'hayward2007/solidworks-mcp',
    [string]$Branch = 'main'
)

# Child scope: with irm | iex nothing below changes the caller's session
& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'  # the progress bar makes Invoke-WebRequest very slow on PowerShell 5.1
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    } catch { }
    $env:PYTHONUNBUFFERED = '1'
    # Set only when this file itself runs (-File); empty for irm | iex and [scriptblock]::Create
    $ScriptFile = if ($PSCommandPath -and (Split-Path -Leaf $PSCommandPath) -ieq 'install.ps1') { $PSCommandPath } else { '' }

    function Say([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
    function Note([string]$Text) { Write-Host "    $Text" }

    function Test-Interactive {
        try { return [Environment]::UserInteractive -and -not [Console]::IsInputRedirected } catch { return $false }
    }

    # Run a native program with its output on screen; the caller reads $LASTEXITCODE.
    # (With ErrorActionPreference = Stop, PowerShell 5.1 turns stderr lines such as git progress into errors.)
    function Invoke-Native([string]$Exe, [string[]]$Arguments) {
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try { & $Exe @Arguments | Out-Host } finally { $ErrorActionPreference = $old }
    }

    function Get-PythonInfo([string]$Exe, [string[]]$Prefix = @()) {
        # -> @{ Exe; Version } for a 64-bit Python 3.10+, otherwise $null
        $code = 'import struct, sys; print(sys.executable); print(''%d.%d'' % sys.version_info[:2]); print(struct.calcsize(''P'') * 8)'
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'SilentlyContinue'
        try {
            $out = @($null | & $Exe @Prefix -c $code 2>$null)
            $rc = $LASTEXITCODE
        } catch {
            return $null
        } finally {
            $ErrorActionPreference = $old
        }
        if ($rc -ne 0 -or $out.Count -lt 3) { return $null }
        try { $version = [version]("$($out[-2])".Trim()) } catch { return $null }
        if ($version -lt [version]'3.10' -or "$($out[-1])".Trim() -ne '64') { return $null }
        return [pscustomobject]@{ Exe = "$($out[-3])".Trim(); Version = $version }
    }

    function Find-Python {
        $candidates = New-Object System.Collections.Generic.List[object]
        $py = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($py) {
            $old = $ErrorActionPreference
            $ErrorActionPreference = 'SilentlyContinue'
            try { $listing = @($null | & $py.Path -0p 2>$null) } catch { $listing = @() } finally { $ErrorActionPreference = $old }
            foreach ($line in $listing) {
                if ("$line" -match '([A-Za-z]:\\.*?pythonw?\.exe)') {
                    $candidates.Add([pscustomobject]@{ Exe = $Matches[1]; Prefix = @() })
                }
            }
            $candidates.Add([pscustomobject]@{ Exe = $py.Path; Prefix = @('-3') })
        }
        foreach ($name in @('python', 'python3')) {
            foreach ($cmd in @(Get-Command $name -CommandType Application -All -ErrorAction SilentlyContinue)) {
                $candidates.Add([pscustomobject]@{ Exe = $cmd.Path; Prefix = @() })
            }
        }
        $patterns = @()
        if ($env:LOCALAPPDATA) {
            $patterns += Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.*\python.exe'
            $patterns += Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe'
        }
        if ($env:ProgramFiles) { $patterns += Join-Path $env:ProgramFiles 'Python3*\python.exe' }
        foreach ($pattern in $patterns) {
            foreach ($file in @(Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue)) {
                $candidates.Add([pscustomobject]@{ Exe = $file.FullName; Prefix = @() })
            }
        }
        $found = @{}
        foreach ($candidate in $candidates) {
            $info = Get-PythonInfo $candidate.Exe $candidate.Prefix
            if ($info -and -not $found.ContainsKey($info.Exe.ToLowerInvariant())) { $found[$info.Exe.ToLowerInvariant()] = $info }
        }
        # Prefer the newest Python that numpy, scipy and pywin32 ship wheels for, then anything newer
        $tested = @($found.Values | Where-Object { $_.Version -le [version]'3.14' } | Sort-Object Version -Descending)
        $newer = @($found.Values | Where-Object { $_.Version -gt [version]'3.14' } | Sort-Object Version)
        $all = @($tested) + @($newer)
        if ($all.Count -gt 0) { return $all[0] }
        return $null
    }

    function Install-PythonWithWinget {
        $winget = Get-Command winget -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $winget) { Note 'winget is not available on this PC.'; return }
        Say 'Installing Python 3.13 with winget (for this user only)'
        Invoke-Native $winget.Path @('install', '--id', 'Python.Python.3.13', '--exact', '--scope', 'user', '--silent',
                                       '--accept-package-agreements', '--accept-source-agreements')
    }

    function Get-Code([string]$Dir) {
        $git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (Test-Path -LiteralPath (Join-Path $Dir '.git')) {
            if ($git) {
                Say "Updating $Dir (git pull)"
                Invoke-Native $git.Path @('-C', $Dir, 'pull', '--ff-only')
                if ($LASTEXITCODE -ne 0) { Note 'git pull failed - continuing with the files that are there.' }
            } else {
                Note 'git not found - keeping the files that are there.'
            }
            return
        }
        $hasFiles = (Test-Path -LiteralPath $Dir) -and (@(Get-ChildItem -LiteralPath $Dir -Force -ErrorAction SilentlyContinue).Count -gt 0)
        if ($hasFiles -and -not (Test-Path -LiteralPath (Join-Path $Dir 'setup_mcp.py'))) {
            throw "$Dir already exists and is not a SolidWorks MCP folder. Choose another folder with -InstallDir."
        }
        if ((-not $hasFiles) -and $git) {
            Say "Downloading $Repo into $Dir (git clone)"
            Invoke-Native $git.Path @('clone', '--depth', '1', '--branch', $Branch, "https://github.com/$Repo.git", $Dir)
            if ($LASTEXITCODE -eq 0) { return }
            Note 'git clone failed - trying the zip download instead.'
        }
        Say "Downloading $Repo ($Branch) as a zip into $Dir"
        $tag = [guid]::NewGuid().ToString('N')
        $zip = Join-Path $env:TEMP "solidworks-mcp-$tag.zip"
        $unpacked = Join-Path $env:TEMP "solidworks-mcp-$tag"
        try {
            Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip
            Expand-Archive -LiteralPath $zip -DestinationPath $unpacked -Force
            $top = @(Get-ChildItem -LiteralPath $unpacked -Directory)[0].FullName
            New-Item -ItemType Directory -Force -Path $Dir | Out-Null
            Invoke-Native 'robocopy.exe' @($top, $Dir, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
            if ($LASTEXITCODE -ge 8) { throw "copying the files into $Dir failed (robocopy exit code $LASTEXITCODE)" }
        } finally {
            Remove-Item -LiteralPath $zip, $unpacked -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    function Invoke-Main {
        if ($env:OS -ne 'Windows_NT') {
            Write-Host 'SolidWorks MCP needs Windows: SolidWorks and pywin32 only run there.'
            return 1
        }
        $here = if ($ScriptFile) { (Split-Path -Parent $ScriptFile).TrimEnd('\') } else { '' }
        if ($InstallDir) {
            $dir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InstallDir).TrimEnd('\')
        } elseif ($here -and (Test-Path -LiteralPath (Join-Path $here 'setup_mcp.py'))) {
            $dir = $here
        } else {
            $dir = Join-Path $HOME 'solidworks-mcp'
        }
        Write-Host "SolidWorks MCP installer - folder: $dir"

        if ($Uninstall) {
            if (-not (Test-Path -LiteralPath (Join-Path $dir 'setup_mcp.py'))) {
                Write-Host "Nothing to remove: $dir is not a SolidWorks MCP folder."
                return 1
            }
        } elseif ($here -and ($dir -ieq $here)) {
            Note 'using this copy of the repository as it is'
        } else {
            Get-Code $dir
        }
        if (-not (Test-Path -LiteralPath 'Registry::HKEY_CLASSES_ROOT\SldWorks.Application')) {
            Note 'SolidWorks was not found on this PC. The server installs anyway but needs SolidWorks to work.'
        }

        Say 'Looking for a 64-bit Python 3.10 or newer'
        $python = Find-Python
        if (-not $python) {
            $install = [bool]$InstallPython
            if (-not $install -and (Test-Interactive)) {
                $answer = Read-Host 'Python 3.10+ was not found. Install Python 3.13 now with winget? [Y/n]'
                $install = ($answer -eq '' -or $answer -match '^[Yy]')
            }
            if ($install) {
                Install-PythonWithWinget
                $python = Find-Python
            }
        }
        if (-not $python) {
            Write-Host 'Python 3.10 or newer (64-bit) was not found.'
            Write-Host 'Run the installer again with -InstallPython to install Python 3.13 with winget,'
            Write-Host 'or install Python from https://www.python.org/downloads/ and run it again.'
            return 2
        }
        Note "$($python.Exe) ($($python.Version))"

        $arguments = @((Join-Path $dir 'setup_mcp.py'), '--yes')
        if ($NoClaudeDesktop) { $arguments += '--no-desktop' }
        foreach ($path in $DesktopConfig) { $arguments += @('--desktop-config', $path) }
        if ($NoClaudeCode) { $arguments += '--no-claude-code' }
        if ($NoSkill) { $arguments += '--no-skill' }
        if ($SkillsDir) { $arguments += @('--skills-dir', $SkillsDir.TrimEnd('\')) }
        if ($Uninstall) { $arguments += '--uninstall' }
        Invoke-Native $python.Exe $arguments
        return $LASTEXITCODE
    }

    try {
        $exitCode = @(Invoke-Main)[-1]
    } catch {
        Write-Host "SolidWorks MCP installer failed: $($_.Exception.Message)" -ForegroundColor Red
        $exitCode = 1
    }
    if ($exitCode -eq 0 -and -not $Uninstall) {
        Write-Host ''
        Write-Host 'Installed. Fully quit Claude Desktop (tray icon > Quit) and start it again.' -ForegroundColor Green
    }
    if ($ScriptFile) { exit $exitCode }
    if ($exitCode -ne 0) { throw "SolidWorks MCP installer stopped (code $exitCode). See the messages above." }
}
