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
