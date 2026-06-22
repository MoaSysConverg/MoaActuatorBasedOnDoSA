param(
    [string]$DistDir = "dist/moa_actuator_gui",
    [string]$OutputDir = "release/MoA_Actuator_EXE"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/5] Validate source folders"
if (-not (Test-Path $DistDir)) {
    throw "Dist folder not found: $DistDir"
}

if (-not (Test-Path "moa_actuator/config")) {
    throw "Config folder missing: moa_actuator/config"
}

if (-not (Test-Path "example/Dosa_2D_Solenoid")) {
    throw "Example folder missing: example/Dosa_2D_Solenoid"
}

Write-Host "[2/5] Reset output folder"
if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Path $OutputDir | Out-Null

Write-Host "[3/5] Copy executable bundle"
Copy-Item -Recurse -Force "$DistDir/*" $OutputDir

Write-Host "[4/5] Copy required runtime data"
New-Item -ItemType Directory -Path "$OutputDir/config" | Out-Null
Copy-Item -Recurse -Force "moa_actuator/config/*" "$OutputDir/config"

New-Item -ItemType Directory -Path "$OutputDir/example" | Out-Null
Copy-Item -Recurse -Force "example/Dosa_2D_Solenoid" "$OutputDir/example"

Write-Host "[5/5] Write launcher and readme"
@'
@echo off
setlocal
pushd %~dp0
set PATH=%~dp0_internal\PyQt6\Qt6\bin;%PATH%
if exist moa_actuator_gui.exe (
  start "" "%~dp0moa_actuator_gui.exe"
) else (
  echo moa_actuator_gui.exe not found.
  pause
)
popd
endlocal
'@ | Set-Content -Encoding ASCII "$OutputDir/run_moa_actuator_gui.bat"

@'
MoA Actuator EXE bundle

How to run:
1. Double-click run_moa_actuator_gui.bat
2. Or run moa_actuator_gui.exe directly

Included minimum runtime content:
- config/unified_plan.json
- config/DoSA_MS.dmat
- example/Dosa_2D_Solenoid/Solenoid.dsa
'@ | Set-Content -Encoding ASCII "$OutputDir/README.txt"

Write-Host "Release folder created: $OutputDir"
