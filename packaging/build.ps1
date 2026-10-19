# Builds the Windows installer on your own PC: dist\installer\Stemquill-Setup-x.y.z.exe
#
# Needs Python 3.11 or 3.12, Inno Setup 6 (https://jrsoftware.org/isdl.php) and the Microsoft
# Visual C++ Redistributable x64 (https://aka.ms/vs/17/release/vc_redist.x64.exe).
# Run from the repo root in PowerShell:   .\packaging\build.ps1
# Then upload the installer to https://skynrlabs.itch.io/stemquill

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Check($ok, $msg) { if (-not $ok) { Write-Error $msg } }

Step "Checking this PC has what the build needs"
# Some audio libraries (soxr, used by librosa) need the Visual C++ runtime. Python doesn't ship
# MSVCP140.dll, and PyInstaller can only bundle it into the app if this PC has it.
$vcDll = Join-Path $env:SystemRoot "System32\msvcp140.dll"
Check (Test-Path $vcDll) ("The Microsoft Visual C++ Redistributable (x64) isn't installed. " +
    "Install it from https://aka.ms/vs/17/release/vc_redist.x64.exe, reopen PowerShell, then build again.")

# Find a real Python 3.12 or 3.11 and run everything through it ("& $py -m pip", "& $py -m PyInstaller"):
# a bare "pip" or "pyinstaller" can belong to another Python or sit outside PATH, and "python" can be
# Windows' Microsoft Store shortcut (WindowsApps\python.exe), which isn't Python at all.
function Find-Python {
    # Windows PowerShell turns a program's error output into a stop when it's redirected, so relax that here
    $ErrorActionPreference = "Continue"
    foreach ($try in @("py -3.12", "py -3.11", "python")) {
        $words = @($try -split " ")
        $cmd = $words[0]
        if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { continue }
        $argList = @($words | Select-Object -Skip 1) + @("-c", "import sys; print(sys.executable)")
        $exe = & $cmd @argList 2>$null | Select-Object -Last 1
        if ($LASTEXITCODE -ne 0 -or -not $exe -or $exe -like "*\WindowsApps\*" -or -not (Test-Path $exe)) { continue }
        $ver = & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($ver -in @("3.11", "3.12")) { return $exe }
    }
    return $null
}
$py = Find-Python
Check ($py) ("Couldn't find Python 3.12 or 3.11. Install Python 3.12 from https://www.python.org/downloads/ " +
    "(tick 'Add python.exe to PATH'), reopen PowerShell, then build again.")
Write-Host "Using $(& $py --version) at $py"

Step "Installing Stemquill and PyInstaller"
& $py -m pip install --upgrade pip
& $py -m pip install . pyinstaller
Check ($LASTEXITCODE -eq 0) "pip install failed"
$version = & $py -c "import stemquill; print(stemquill.__version__)"
Check ($LASTEXITCODE -eq 0 -and $version) "Stemquill installed, but Python can't load it (see the error above)"

Step "Building the app ($version)"
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue
& $py -m PyInstaller --noconfirm packaging\stemquill.spec
Check ($LASTEXITCODE -eq 0) "PyInstaller failed"
# The app must carry its own copy, so it runs on PCs without the Visual C++ Redistributable
$bundled = Get-ChildItem -Recurse dist\Stemquill -Filter msvcp140.dll -ErrorAction SilentlyContinue
Check ($bundled) "MSVCP140.dll wasn't bundled into the app, so it would crash on PCs without the Visual C++ runtime"

Step "Smoke test: convert a drum loop"
$tmp = Join-Path $env:TEMP "stemquill-build-test"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
New-Item -ItemType Directory $tmp | Out-Null
& $py packaging\make_test_stem.py "$tmp\test-drums.wav"
$p = Start-Process -FilePath "dist\Stemquill\Stemquill.exe" -Wait -PassThru `
     -ArgumentList "`"$tmp\test-drums.wav`" --type drums --bpm 120 --out `"$tmp\out`""
Check ($p.ExitCode -eq 0 -and (Test-Path "$tmp\out\test-drums - drums.mid")) "The built app couldn't convert a drum loop"

Step "Smoke test: open the window"
# The tests above only use the command line, which doesn't need the window toolkit (Tcl/Tk); a build
# missing it would pass them and then never open from the Start menu.
$flag = "$tmp\window-ok.txt"
$crashLog = Join-Path $env:APPDATA "Stemquill\crash.log"
$env:STEMQUILL_CHECK_WINDOW = $flag
$p = Start-Process -FilePath "dist\Stemquill\Stemquill.exe" -PassThru
Remove-Item Env:\STEMQUILL_CHECK_WINDOW
if (-not $p.WaitForExit(120000)) { $p.Kill() }
if (-not (Test-Path $flag) -and (Test-Path $crashLog)) {
    Write-Host "`nLast crash report from $crashLog`n" -ForegroundColor Yellow
    Get-Content $crashLog -Tail 40
}
Check (Test-Path $flag) "The built app couldn't open its window (see the crash report above, if any)"

Step "Building the chord-detection add-on"
& $py -m pip install --no-deps --target dist\addons\chords -r packaging\chords-addon.txt
Check ($LASTEXITCODE -eq 0) "Add-on install failed"
# trim parts basic-pitch never uses
Remove-Item -Recurse -Force dist\addons\chords\bin -ErrorAction SilentlyContinue
Remove-Item -Force dist\addons\chords\pretty_midi\*.sf2 -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\addons\chords\onnxruntime\transformers, dist\addons\chords\onnxruntime\quantization, dist\addons\chords\onnxruntime\tools -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\addons\chords\basic_pitch\saved_models\icassp_2022\nmp -ErrorAction SilentlyContinue
Remove-Item -Force dist\addons\chords\basic_pitch\saved_models\icassp_2022\*.tflite -ErrorAction SilentlyContinue

Step "Smoke test: chords with the add-on"
& $py packaging\make_test_stem.py "$tmp\test-chords.wav" chords
Copy-Item -Recurse dist\addons dist\Stemquill\addons
$env:STEMQUILL_LOG = "$tmp\addon.log"
$p = Start-Process -FilePath "dist\Stemquill\Stemquill.exe" -Wait -PassThru `
     -ArgumentList "`"$tmp\test-chords.wav`" --type melodic --bpm 120 --out `"$tmp\out`""
Remove-Item Env:\STEMQUILL_LOG
Remove-Item -Recurse -Force dist\Stemquill\addons
Check ($p.ExitCode -eq 0 -and (Select-String -Path "$tmp\addon.log" -Pattern "\(basic-pitch\)" -Quiet)) "The chord add-on wasn't used"

Step "Writing the open-source licenses"
# Every bundled library's license, the add-on's too, next to Stemquill.exe (the installer copies it; About shows it)
& $py -m stemquill.licenses --out dist\Stemquill\THIRD_PARTY_LICENSES.txt --addon dist\addons\chords
Check ($LASTEXITCODE -eq 0 -and (Select-String -Path dist\Stemquill\THIRD_PARTY_LICENSES.txt -Pattern "basic-pitch" -Quiet)) "Couldn't write the licenses file"

Step "Building the installer"
# Inno Setup installs to Program Files, or to your user folder when installed without admin rights
$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
Check ($iscc) "Inno Setup 6 isn't installed (or isn't where expected). Get it from https://jrsoftware.org/isdl.php"
Write-Host "Using $iscc"
& $iscc "/DAppVersion=$version" packaging\installer.iss
Check ($LASTEXITCODE -eq 0) "Inno Setup failed"

$exe = Get-Item "dist\installer\Stemquill-Setup-$version.exe"
Write-Host "`nDone: $($exe.FullName) ($([math]::Round($exe.Length / 1MB, 1)) MB)" -ForegroundColor Green
Write-Host "Upload it to https://skynrlabs.itch.io/stemquill"
