# Builds the Windows installer on your own PC: dist\installer\Stemquill-Setup-x.y.z.exe
#
# Needs Python 3.11 and Inno Setup 6 (https://jrsoftware.org/isdl.php).
# Run from the repo root in PowerShell:   .\packaging\build.ps1
# Then upload the installer to https://skynrlabs.itch.io/stemquill

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Check($ok, $msg) { if (-not $ok) { Write-Error $msg } }

Step "Installing Stemquill and PyInstaller"
python -m pip install --upgrade pip
pip install . pyinstaller
Check ($LASTEXITCODE -eq 0) "pip install failed"
$version = python -c "import stemquill; print(stemquill.__version__)"

Step "Building the app ($version)"
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue
pyinstaller --noconfirm packaging\stemquill.spec
Check ($LASTEXITCODE -eq 0) "PyInstaller failed"

Step "Smoke test: convert a drum loop"
$tmp = Join-Path $env:TEMP "stemquill-build-test"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
New-Item -ItemType Directory $tmp | Out-Null
python packaging\make_test_stem.py "$tmp\test-drums.wav"
$p = Start-Process -FilePath "dist\Stemquill\Stemquill.exe" -Wait -PassThru `
     -ArgumentList "`"$tmp\test-drums.wav`" --type drums --bpm 120 --out `"$tmp\out`""
Check ($p.ExitCode -eq 0 -and (Test-Path "$tmp\out\test-drums - drums.mid")) "The built app couldn't convert a drum loop"

Step "Building the chord-detection add-on"
pip install --no-deps --target dist\addons\chords -r packaging\chords-addon.txt
Check ($LASTEXITCODE -eq 0) "Add-on install failed"
# trim parts basic-pitch never uses
Remove-Item -Recurse -Force dist\addons\chords\bin -ErrorAction SilentlyContinue
Remove-Item -Force dist\addons\chords\pretty_midi\*.sf2 -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\addons\chords\onnxruntime\transformers, dist\addons\chords\onnxruntime\quantization, dist\addons\chords\onnxruntime\tools -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\addons\chords\basic_pitch\saved_models\icassp_2022\nmp -ErrorAction SilentlyContinue
Remove-Item -Force dist\addons\chords\basic_pitch\saved_models\icassp_2022\*.tflite -ErrorAction SilentlyContinue

Step "Smoke test: chords with the add-on"
python packaging\make_test_stem.py "$tmp\test-chords.wav" chords
Copy-Item -Recurse dist\addons dist\Stemquill\addons
$env:STEMQUILL_LOG = "$tmp\addon.log"
$p = Start-Process -FilePath "dist\Stemquill\Stemquill.exe" -Wait -PassThru `
     -ArgumentList "`"$tmp\test-chords.wav`" --type melodic --bpm 120 --out `"$tmp\out`""
Remove-Item Env:\STEMQUILL_LOG
Remove-Item -Recurse -Force dist\Stemquill\addons
Check ($p.ExitCode -eq 0 -and (Select-String -Path "$tmp\addon.log" -Pattern "\(basic-pitch\)" -Quiet)) "The chord add-on wasn't used"

Step "Building the installer"
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
Check (Test-Path $iscc) "Inno Setup 6 isn't installed. Get it from https://jrsoftware.org/isdl.php"
& $iscc "/DAppVersion=$version" packaging\installer.iss
Check ($LASTEXITCODE -eq 0) "Inno Setup failed"

$exe = Get-Item "dist\installer\Stemquill-Setup-$version.exe"
Write-Host "`nDone: $($exe.FullName) ($([math]::Round($exe.Length / 1MB, 1)) MB)" -ForegroundColor Green
Write-Host "Upload it to https://skynrlabs.itch.io/stemquill"
