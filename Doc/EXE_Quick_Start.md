# MoA Actuator EXE Quick Start (Windows)

이 문서는 개발팀이 pyMotorEnv_310 가상환경에서 빌드한 exe를, 사용자(비개발자)가 빠르게 실행해
Maxwell 2D Solenoid 예제를 검증하는 절차를 안내합니다.

대상 독자:
- Python/IDE 없이 exe만 사용하는 사용자
- Ansys Maxwell(AEDT) 사용 가능 환경이 준비된 사용자

참조 예제:
- example/Dosa_2D_Solenoid/Solenoid.dsa

---

## 1) 배포물 구성 (권장)

배포 폴더 예시:

- MoA_Actuator_EXE/
- MoA_Actuator_EXE/moa_actuator_gui.exe
- MoA_Actuator_EXE/config/
- MoA_Actuator_EXE/config/unified_plan.json
- MoA_Actuator_EXE/config/DoSA_MS.dmat
- MoA_Actuator_EXE/example/
- MoA_Actuator_EXE/example/Dosa_2D_Solenoid/Solenoid.dsa

권장 사항:
- exe와 config 파일은 반드시 함께 배포
- example 폴더를 동봉하면 사용자 검증 시간이 크게 줄어듦

---

## 2) 사용자 실행 절차 (비개발자)

### 2.1 사전 확인

- Windows 환경
- Ansys Electronics Desktop/Maxwell 설치 및 라이선스 사용 가능
- 배포 폴더가 로컬 드라이브(예: D:\Tools\MoA_Actuator_EXE)에 위치

### 2.2 실행

- moa_actuator_gui.exe 더블클릭
- 또는 PowerShell에서 실행:

  .\moa_actuator_gui.exe

### 2.3 Solenoid 예제 열기

1. File -> Open...
2. example/Dosa_2D_Solenoid/Solenoid.dsa 선택

### 2.4 Solver 설정

권장 초기값:
- Mode: 2d
- Solver: maxwell
- Output Dir: ./output
- Dry Run (no AEDT): 해제
- Non-graphical: 필요 시 선택

### 2.5 실행 순서

1. Build
2. Solve
3. 성공 시 Log에서 Result: OK 확인
4. Project 경로(.aedt) 생성 여부 확인

---

## 3) 개발자 빌드 절차 (pyMotorEnv_310)

이 절차는 배포 exe를 만드는 담당자용입니다.

### 3.1 가상환경 활성화

PowerShell:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& c:\Users\user\.ansys_python_venvs\pyMotorEnv_310\Scripts\Activate.ps1

### 3.2 프로젝트 루트 이동

cd E:\KDH\gitDosa_Actuator\MoaActuatorBasedOnDoSA

### 3.3 빌드 의존성 설치

python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m pip install -e .[all]

### 3.4 exe 빌드 (spec 고정)

python -m PyInstaller --noconfirm --clean packaging/pyinstaller/moa_actuator_gui.spec

빌드 결과:
- dist/moa_actuator_gui/

이 spec은 GUI 전용 엔트리(`moa_actuator/gui_entry.py`)를 사용하므로, exe 더블클릭 시 바로 GUI가 열립니다.

### 3.5 배포 폴더 조립

powershell -ExecutionPolicy Bypass -File packaging/release/assemble_release.ps1

생성 결과:
- release/MoA_Actuator_EXE/

실행:
- run_moa_actuator_gui.bat 더블클릭
- 또는 moa_actuator_gui.exe 직접 실행

---

## 4) 배포 전 검증 체크리스트

- exe 실행 시 GUI 창 정상 표시
- File -> Open으로 Solenoid.dsa 열기 가능
- Build 성공
- Solve 성공
- output 폴더에 .aedt 생성
- 재실행 시 동일 절차 재현 가능

---

## 5) 자주 발생하는 이슈

1. 실행은 되지만 Maxwell 연결 실패
- 원인: AEDT 라이선스/버전/세션 문제
- 조치: AEDT 단독 실행 확인 후 재시도

2. config 파일 누락
- 원인: 배포 시 config 하위 파일 미포함
- 조치: unified_plan.json, DoSA_MS.dmat 포함 재패키징

3. 경로 권한 문제
- 원인: Program Files 등 쓰기 제한 경로에서 output 생성 실패
- 조치: 사용자 쓰기 가능한 경로로 배포 또는 Output Dir 변경

---

## 6) 운영 권장안

현 단계(개발 진행 중)에서의 권장:
- 사용자 배포: exe 우선
- 개발/디버깅: pyMotorEnv_310 가상환경 유지

즉, 사용자 경험은 exe로 단순화하고, 내부 문제 해결은 가상환경에서 빠르게 대응하는 2-트랙 운영이 가장 안정적입니다.
