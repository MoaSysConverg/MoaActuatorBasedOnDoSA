# EXE Release Packaging

이 폴더는 MoA Actuator GUI exe 배포본을 재현 가능하게 만드는 스크립트를 제공합니다.

## 파일

- assemble_release.ps1: dist 결과물 + 필수 config/example를 합쳐 release 폴더 생성

## 사용 순서

1. pyMotorEnv_310 활성화
2. PyInstaller spec 빌드
3. release 폴더 조립

PowerShell 예시:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& c:\Users\user\.ansys_python_venvs\pyMotorEnv_310\Scripts\Activate.ps1
cd E:\KDH\gitDosa_Actuator\MoaActuatorBasedOnDoSA
python -m PyInstaller --noconfirm --clean packaging/pyinstaller/moa_actuator_gui.spec
powershell -ExecutionPolicy Bypass -File packaging/release/assemble_release.ps1

생성 결과:
- release/MoA_Actuator_EXE/
