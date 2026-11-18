# Chinese Screen OCR launcher.
#
# Started by "Chinese Screen OCR.bat". When the environment is ready it starts the
# app straight away without showing anything. Otherwise it opens a small setup
# window that shows progress and a log while it:
#   1. finds Python 3.12 (64-bit), or downloads it from python.org into .runtime\
#   2. creates the virtual environment .venv\
#   3. installs the pinned packages from app\requirements.txt
#   4. checks the installed versions and imports
#   5. loads the OCR engine once (its models ship in app\models)
# and then starts the app. Nothing outside this folder is changed.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$AppDir   = $PSScriptRoot
$RootDir  = Split-Path $AppDir -Parent
$VenvDir  = Join-Path $RootDir '.venv'
$Runtime  = Join-Path $RootDir '.runtime'
$Lock     = Join-Path $AppDir 'requirements.txt'
$Marker   = Join-Path $VenvDir 'setup-complete.txt'
$DataDir  = Join-Path $env:APPDATA 'ChineseScreenOCR'
$SetupLog = Join-Path $DataDir 'setup.log'
$AppLog   = Join-Path $DataDir 'ocr_app.log'
$VenvPyw  = Join-Path $VenvDir 'Scripts\pythonw.exe'

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

function Get-LockHash {
    (Get-FileHash -Algorithm SHA256 -Path $Lock).Hash
}

function Test-Ready {
    (Test-Path $VenvPyw) -and (Test-Path $Marker) -and
        ((Get-Content -Raw -Path $Marker).Trim() -eq (Get-LockHash))
}

function Start-App {
    # Returns $null when the app is still running a few seconds later,
    # otherwise a message describing why it stopped.
    $p = Start-Process -FilePath $VenvPyw -ArgumentList '"main.py"' -WorkingDirectory $AppDir -PassThru
    for ($i = 0; $i -lt 16; $i++) {
        Start-Sleep -Milliseconds 500
        if ($p.HasExited) {
            $tail = ''
            if (Test-Path $AppLog) { $tail = (Get-Content -Path $AppLog -Tail 15) -join "`r`n" }
            return "The app closed right after starting (exit code $($p.ExitCode)).`r`n$tail"
        }
    }
    return $null
}

# ---------------------------------------------------------------- fast path
if (Test-Ready) {
    $startError = Start-App
    if ($null -eq $startError) { exit 0 }
}
else {
    $startError = $null
}

# ---------------------------------------------------------------- setup window
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$Accent = [System.Drawing.Color]::FromArgb(15, 108, 189)
$Danger = [System.Drawing.Color]::FromArgb(196, 43, 28)
$Ok     = [System.Drawing.Color]::FromArgb(15, 123, 15)
$Muted  = [System.Drawing.Color]::FromArgb(97, 97, 97)
$Bg     = [System.Drawing.Color]::FromArgb(243, 243, 243)
$Text   = [System.Drawing.Color]::FromArgb(27, 27, 27)

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Chinese Screen OCR - Setup'
$form.ClientSize = New-Object System.Drawing.Size(600, 430)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedSingle'
$form.MaximizeBox = $false
$form.BackColor = $Bg
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9.5)

$title = New-Object System.Windows.Forms.Label
$title.Text = 'Chinese Screen OCR'
$title.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 15)
$title.ForeColor = $Text
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(22, 18)
$form.Controls.Add($title)

$sub = New-Object System.Windows.Forms.Label
$sub.Text = 'First start: setting everything up. This is done only once and needs an internet connection.'
$sub.ForeColor = $Muted
$sub.AutoSize = $false
$sub.Size = New-Object System.Drawing.Size(556, 20)
$sub.Location = New-Object System.Drawing.Point(24, 52)
$form.Controls.Add($sub)

$status = New-Object System.Windows.Forms.Label
$status.Text = 'Starting...'
$status.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 10.5)
$status.ForeColor = $Text
$status.AutoSize = $false
$status.AutoEllipsis = $true
$status.Size = New-Object System.Drawing.Size(460, 42)
$status.Location = New-Object System.Drawing.Point(22, 86)
$form.Controls.Add($status)

$stepLabel = New-Object System.Windows.Forms.Label
$stepLabel.Text = ''
$stepLabel.ForeColor = $Muted
$stepLabel.TextAlign = 'TopRight'
$stepLabel.Size = New-Object System.Drawing.Size(90, 24)
$stepLabel.Location = New-Object System.Drawing.Point(488, 88)
$form.Controls.Add($stepLabel)

# Flat progress bar in the app's accent colour (the stock one is green and can't be recoloured).
$track = New-Object System.Windows.Forms.Panel
$track.BackColor = [System.Drawing.Color]::FromArgb(224, 224, 224)
$track.Size = New-Object System.Drawing.Size(556, 6)
$track.Location = New-Object System.Drawing.Point(22, 132)
$form.Controls.Add($track)
$fill = New-Object System.Windows.Forms.Panel
$fill.BackColor = $Accent
$fill.Size = New-Object System.Drawing.Size(0, 6)
$fill.Location = New-Object System.Drawing.Point(0, 0)
$track.Controls.Add($fill)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ReadOnly = $true
$logBox.ScrollBars = 'Vertical'
$logBox.WordWrap = $true
$logBox.BackColor = [System.Drawing.Color]::White
$logBox.ForeColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$logBox.Font = New-Object System.Drawing.Font('Consolas', 8.75)
$logBox.BorderStyle = 'FixedSingle'
$logBox.Size = New-Object System.Drawing.Size(556, 222)
$logBox.Location = New-Object System.Drawing.Point(22, 150)
$form.Controls.Add($logBox)

function New-Button($text, $x, $width) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text
    $b.FlatStyle = 'System'
    $b.Size = New-Object System.Drawing.Size($width, 30)
    $b.Location = New-Object System.Drawing.Point($x, 384)
    $form.Controls.Add($b)
    return $b
}
$btnLog   = New-Button 'Open log file' 22 120
$btnRetry = New-Button 'Try again' 378 96
$btnClose = New-Button 'Cancel' 482 96
$btnRetry.Visible = $false

# ---------------------------------------------------------------- worker
# Runs in its own runspace so the window stays responsive; it talks to the
# window only through the synchronized $sync table (a message queue).
$worker = {
    $ErrorActionPreference = 'Stop'

    function Send($type, $text, $value) {
        $sync.Queue.Enqueue(@{ Type = $type; Text = $text; Value = $value })
    }
    function Log($line) {
        Send 'log' $line $null
        try { [IO.File]::AppendAllText($p.SetupLog, ((Get-Date -Format 'HH:mm:ss') + '  ' + $line + "`r`n")) } catch {}
    }
    function Step($n, $text) { Send 'step' $text $n; Log ''; Log "== $text" }
    function Fail($text) { throw [Exception]::new($text) }

    # Runs a program, sends each output line to $onLine and the log, returns the exit code.
    function Invoke-Logged($exe, [string[]]$arguments, $onLine) {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $exe
        $psi.Arguments = ($arguments | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
        $psi.WorkingDirectory = $p.AppDir
        $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
        $psi.EnvironmentVariables['PYTHONUTF8'] = '1'
        $psi.EnvironmentVariables['PYTHONUNBUFFERED'] = '1'
        $psi.EnvironmentVariables['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
        $psi.EnvironmentVariables['PIP_NO_INPUT'] = '1'
        $proc = [Diagnostics.Process]::Start($psi)
        $sync.Proc = $proc
        $errTask = $proc.StandardError.ReadToEndAsync()
        while ($null -ne ($line = $proc.StandardOutput.ReadLine())) {
            if ($sync.Cancel) { break }
            Log $line
            if ($onLine) { & $onLine $line }
        }
        $proc.WaitForExit()
        foreach ($l in ($errTask.Result -split "`r?`n")) { if ($l.Trim()) { Log $l } }
        $sync.Proc = $null
        if ($sync.Cancel) { Fail 'Cancelled.' }
        return $proc.ExitCode
    }

    # Full path of a 64-bit Python 3.12 that can create virtual environments, or $null.
    function Test-Python($exe) {
        if (-not $exe -or -not (Test-Path $exe)) { return $null }
        try {
            $out = & $exe -c "import sys, struct, venv, ensurepip; print(sys.executable if sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8 else '')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -Last 1).Trim() }
        } catch {}
        return $null
    }

    function Find-Python {
        $candidates = @(
            (Join-Path $p.Runtime 'python\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
            (Join-Path $env:ProgramFiles 'Python312\python.exe')
        )
        foreach ($c in $candidates) { $found = Test-Python $c; if ($found) { return $found } }
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($py) {
            try {
                $exe = & $py.Source -3.12 -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $exe) { $found = Test-Python ($exe | Select-Object -Last 1).Trim(); if ($found) { return $found } }
            } catch {}
        }
        return $null
    }

    function Get-File($url, $dest, $label) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $req = [Net.HttpWebRequest]::Create($url)
        $req.UserAgent = 'ChineseScreenOCR-Setup'
        $resp = $req.GetResponse()
        $total = $resp.ContentLength
        $in = $resp.GetResponseStream()
        $out = [IO.File]::Create($dest)
        try {
            $buf = New-Object byte[] 262144
            $done = 0; $lastReport = 0
            while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) {
                if ($sync.Cancel) { Fail 'Cancelled.' }
                $out.Write($buf, 0, $n); $done += $n
                if ($done - $lastReport -ge 1MB -or $done -eq $total) {
                    $lastReport = $done
                    $mb = '{0:N1} / {1:N1} MB' -f ($done / 1MB), ($total / 1MB)
                    Send 'status' "$label ($mb)" $null
                    if ($total -gt 0) { Send 'progress' $null ($done / $total) }
                }
            }
        } finally { $out.Close(); $in.Close(); $resp.Close() }
        Log "Downloaded $url"
    }

    try {
        $total = 5
        Log ("Setup started " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " in " + $p.RootDir)

        # 0. Folder path ---------------------------------------------------------
        # Qt 5 can't start from a folder with characters such as s-cedilla or u-umlaut
        # in its path; the app then uses the folder's 8.3 short name, which only
        # exists when the drive has short names enabled.
        $nonAscii = @($p.RootDir.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count -gt 0
        if ($nonAscii) {
            $short = $null
            try { $short = (New-Object -ComObject Scripting.FileSystemObject).GetFolder($p.RootDir).ShortPath } catch {}
            if (-not $short -or @($short.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count -gt 0) {
                Fail ("The folder path contains special characters, which the app can't run from:`r`n" + $p.RootDir +
                      "`r`nMove the whole folder to a simple location such as C:\ChineseScreenOCR and start it again.")
            }
            Log "The folder path has special characters; the app will use its short form: $short"
        }

        # 1. Python ------------------------------------------------------------
        Step 1 'Looking for Python 3.12'
        $venvPy = Join-Path $p.VenvDir 'Scripts\python.exe'
        $base = $null
        if (Test-Python $venvPy) {
            Log "Using the existing environment in $($p.VenvDir)"
        } else {
            $base = Find-Python
            if ($base) {
                Log "Found $base"
            } else {
                Step 1 'Downloading Python 3.12 from python.org'
                $installer = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
                Get-File 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' $installer 'Downloading Python 3.12'
                $sig = Get-AuthenticodeSignature -FilePath $installer
                if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
                    Fail "The downloaded Python installer is not signed by the Python Software Foundation ($($sig.Status))."
                }
                Log 'Installer signature: Python Software Foundation (valid)'
                Send 'status' 'Installing Python 3.12 into this folder' $null
                Send 'progress' $null -1
                $target = Join-Path $p.Runtime 'python'
                $installArgs = @('/quiet', 'InstallAllUsers=0', "`"TargetDir=$target`"", 'PrependPath=0', 'Include_launcher=0',
                                 'InstallLauncherAllUsers=0', 'Include_test=0', 'Include_doc=0', 'Include_tcltk=0',
                                 'Shortcuts=0', 'AssociateFiles=0', 'Include_pip=1')
                $proc = Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru
                Remove-Item $installer -ErrorAction SilentlyContinue
                $base = Test-Python (Join-Path $target 'python.exe')
                if (-not $base) { Fail "Python could not be installed (installer exit code $($proc.ExitCode))." }
                Log "Installed $base"
            }
        }

        # 2. Virtual environment ------------------------------------------------
        Step 2 'Creating the Python environment'
        if ($base) {
            if (Test-Path $p.VenvDir) {
                Log 'Removing the old environment (wrong Python version)'
                Remove-Item -Recurse -Force $p.VenvDir
            }
            Send 'progress' $null -1
            if ((Invoke-Logged $base @('-m', 'venv', $p.VenvDir) $null) -ne 0) { Fail 'Could not create the virtual environment.' }
        } else {
            Log 'Environment already exists'
        }
        if (-not (Test-Path $venvPy)) { Fail 'The virtual environment is incomplete.' }

        # 3. Packages -----------------------------------------------------------
        Step 3 'Installing libraries'
        $count = @(Get-Content $p.Lock | Where-Object { $_ -match '==' }).Count
        $script:seen = 0
        $onPip = {
            param($line)
            if ($line -match '^(Collecting|Requirement already satisfied:)\s+([^\s=<>]+)') {
                $script:seen++
                Send 'progress' $null ([Math]::Min(0.9, 0.9 * $script:seen / [Math]::Max(1, $count)))
                Send 'status' ("Downloading libraries ({0} of {1}): {2}" -f [Math]::Min($script:seen, $count), $count, $Matches[2]) $null
            } elseif ($line -match '^\s*Downloading\s+(\S+)\s+\(([^)]+)\)') {
                Send 'status' ("Downloading {0} ({1})" -f ($Matches[1] -replace '-[\d.].*$', ''), $Matches[2]) $null
            } elseif ($line -match '^Installing collected packages') {
                Send 'status' 'Installing libraries (this takes a few minutes)' $null
                Send 'progress' $null 0.92
            }
        }
        $pipArgs = @('-m', 'pip', 'install', '--progress-bar', 'off', '--retries', '5', '--timeout', '60', '-r', $p.Lock)
        $code = Invoke-Logged $venvPy $pipArgs $onPip
        if ($code -ne 0) {
            Log 'Retrying once (network errors are often temporary)...'
            $code = Invoke-Logged $venvPy $pipArgs $onPip
        }
        if ($code -ne 0) { Fail 'Installing the libraries failed. Check the internet connection and try again.' }
        Send 'progress' $null 1

        # 4. Check --------------------------------------------------------------
        Step 4 'Checking the installation'
        Send 'progress' $null -1
        $check = Join-Path $p.AppDir 'check_env.py'
        foreach ($what in @('versions', 'imports')) {
            if ((Invoke-Logged $venvPy @('-u', $check, $what) $null) -ne 0) { Fail "The installation check failed ($what). See the log." }
        }

        # 5. OCR models -----------------------------------------------------------
        Step 5 'Loading the OCR engine'
        Send 'progress' $null -1
        if ((Invoke-Logged $venvPy @('-u', $check, 'models') $null) -ne 0) { Fail 'The OCR engine could not be loaded. See the log.' }

        Set-Content -Path $p.Marker -Value $p.LockHash -Encoding ASCII
        Log 'Setup complete.'
        Send 'done' 'Ready' $null
    }
    catch {
        $msg = $_.Exception.Message
        Log "ERROR: $msg"
        if ($_.InvocationInfo) { Log $_.InvocationInfo.PositionMessage }
        Send 'error' $msg $null
    }
}

$sync = [hashtable]::Synchronized(@{
    Queue  = New-Object 'System.Collections.Concurrent.ConcurrentQueue[object]'
    Proc   = $null
    Cancel = $false
})
$paths = @{
    AppDir = $AppDir; RootDir = $RootDir; VenvDir = $VenvDir; Runtime = $Runtime
    Lock = $Lock; Marker = $Marker; SetupLog = $SetupLog; LockHash = (Get-LockHash)
}
$state = @{ Busy = $false; Marquee = $false; MarqueeX = 0; Step = 0 }
$runspace = $null
$job = $null

function Set-Progress($fraction) {
    if ($fraction -lt 0) { $state.Marquee = $true; return }
    $state.Marquee = $false
    $fill.Left = 0
    $fill.Width = [int]($track.Width * [Math]::Max(0, [Math]::Min(1, $fraction)))
}

function Add-Log($line) {
    $logBox.AppendText($line + "`r`n")
}

function Start-Setup {
    $script:state.Busy = $true
    $sync.Cancel = $false
    $btnRetry.Visible = $false
    $btnClose.Text = 'Cancel'
    $status.ForeColor = $Text
    $fill.BackColor = $Accent
    Set-Progress 0
    $script:runspace = [runspacefactory]::CreateRunspace()
    $script:runspace.Open()
    $script:runspace.SessionStateProxy.SetVariable('sync', $sync)
    $script:runspace.SessionStateProxy.SetVariable('p', $paths)
    $script:job = [powershell]::Create()
    $script:job.Runspace = $script:runspace
    [void]$script:job.AddScript($worker)
    [void]$script:job.BeginInvoke()
}

function Show-Error($message) {
    $state.Busy = $false
    $state.Marquee = $false
    $status.Text = 'Setup did not finish: ' + $message
    $status.ForeColor = $Danger
    $fill.BackColor = $Danger
    $fill.Left = 0; $fill.Width = $track.Width
    $btnRetry.Visible = $true
    $btnClose.Text = 'Close'
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 60
$timer.Add_Tick({
    $msg = $null
    $n = 0
    while ($n -lt 200 -and $sync.Queue.TryDequeue([ref]$msg)) {
        $n++
        switch ($msg.Type) {
            'log'      { Add-Log $msg.Text }
            'status'   { $status.Text = $msg.Text }
            'step'     { $state.Step = $msg.Value; $status.Text = $msg.Text; $stepLabel.Text = "Step $($msg.Value) of 5"; Set-Progress 0 }
            'progress' { Set-Progress $msg.Value }
            'error'    { Show-Error $msg.Text }
            'done'     {
                $state.Busy = $false
                $status.Text = 'Ready. Starting Chinese Screen OCR...'
                $status.ForeColor = $Ok
                $fill.BackColor = $Ok
                Set-Progress 1
                $form.Refresh()
                $err = Start-App
                if ($null -eq $err) { $form.Close(); return }
                Add-Log $err
                Show-Error 'the app could not start. See the log below.'
            }
        }
    }
    if ($state.Marquee) {
        $w = [int]($track.Width / 4)
        $state.MarqueeX = ($state.MarqueeX + 9) % ($track.Width + $w)
        $fill.Width = $w
        $fill.Left = $state.MarqueeX - $w
    }
})

$btnRetry.Add_Click({ $logBox.Clear(); Start-Setup })
$btnClose.Add_Click({ $form.Close() })
$btnLog.Add_Click({
    if (-not (Test-Path $SetupLog)) { New-Item -ItemType File -Force -Path $SetupLog | Out-Null }
    Start-Process notepad.exe -ArgumentList ('"' + $SetupLog + '"')
})

$form.Add_FormClosing({
    param($sender, $e)
    if ($state.Busy) {
        $answer = [System.Windows.Forms.MessageBox]::Show($form,
            "Setup is still running. Stop it?`r`n`r`nIt will continue where it left off the next time you start the app.",
            'Chinese Screen OCR', 'YesNo', 'Question')
        if ($answer -ne 'Yes') { $e.Cancel = $true; return }
        $sync.Cancel = $true
        $proc = $sync.Proc
        if ($proc) { try { & taskkill.exe /PID $proc.Id /T /F | Out-Null } catch {} }
    }
    $timer.Stop()
})

$form.Add_Shown({
    $timer.Start()
    if ($startError) {
        # The environment was ready but the app did not start: show why.
        $sub.Text = 'The app could not start.'
        Add-Log $startError
        Show-Error 'the app closed right after starting. Try again to repair the setup.'
        Remove-Item -Path $Marker -ErrorAction SilentlyContinue
    } else {
        Start-Setup
    }
})

[void]$form.ShowDialog()
if ($job) { try { $job.Stop() } catch {}; $job.Dispose() }
if ($runspace) { $runspace.Close() }
