# MoA Actuator 가상환경 실행 퀵 스타트 가이드 (Windows)

이 문서는 사용자 및 개발자가 배포용 exe 대신 **가상환경**을 활성화하여 `moa_actuator` GUI 프로그램 및 Jupyter Notebook 예제를 직접 실행하는 절차를 안내합니다.

현 개발 단계에서는 가상환경 기반 실행이 오류 분석 및 패키지 업데이트 대응이 가장 신속하므로 이 방식을 기본 배포/실행 수단으로 권장합니다.

---

## 1. 사전 요구사항

- **OS**: Windows 10 이상
- **Python**: Python 3.10.x 이상
- **Ansys AEDT**: Ansys Electronics Desktop 및 Maxwell 설치 및 라이선스 사용 가능 상태 (버전 2022 R2 이상 권장)
- **가상환경 경로**: `[가상환경_폴더_경로]` (예: `C:\Users\[사용자_계정]\.ansys_python_venvs\PyMotorEnv_310` 또는 루트 폴더 내 자동 생성된 `.venv` 폴더)

---

## 2. Git/GitHub 및 VS Code 기본 설정 (초보자용 가이드)

> [!NOTE]
> Git 및 GitHub을 사용해본 적이 없거나 코드 편집기가 낯선 분들을 위한 사전 가이드입니다. 이미 환경이 준비되신 분들은 **3장**으로 바로 넘어가셔도 좋습니다.

### 2.1 GitHub에서 소스 코드 가져오기

* **방법 A. 가장 간단한 방법 (ZIP 다운로드 - Git 미설치자용)**:
  1. 웹 브라우저로 [GitHub 레포지토리](https://github.com/MoaSysConverg/MoaActuatorBasedOnDoSA)에 접속합니다.
  2. 우측 상단의 초록색 **`Code`** 버튼을 클릭하고 **`Download ZIP`**을 누릅니다.
  3. 다운로드된 ZIP 파일의 압축을 로컬 드라이브의 원하는 경로(예: `C:\MoaActuator` 등)에 풉니다.
* **방법 B. 표준 방법 (Git Clone 사용)**:
  1. [Git 공식 사이트](https://git-scm.com/)에서 Windows용 설치 파일을 받아 기본값(Next 클릭)으로 설치를 마칩니다.
  2. 명령 프롬프트(CMD) 또는 PowerShell을 열고, 코드를 다운로드받을 경로로 이동한 뒤 아래 명령어를 입력합니다:
     ```powershell
     git clone https://github.com/MoaSysConverg/MoaActuatorBasedOnDoSA.git
     ```
  3. 다운로드가 완료되면 해당 폴더가 로컬에 생성됩니다.

### 2.2 VS Code 설치 및 개발 확장 기능 설정

1. [VS Code 공식 사이트](https://code.visualstudio.com/)에서 에디터를 설치합니다.
2. VS Code를 실행한 후, `File` -> `Open Folder...`를 클릭하여 방금 다운로드받은(또는 ZIP 압축을 푼) **프로젝트 루트 폴더**를 선택하여 엽니다.
3. 좌측의 블록 모양 아이콘인 **`Extensions (확장 기능, 단축키: Ctrl+Shift+X)`** 탭을 클릭하여 아래 필수 기능들을 검색창에 입력하고 **`Install`** 버튼을 누릅니다.
   - **`Python`** (by Microsoft): Python 코드 실행 및 자동 완성 지원
   - **`Jupyter`** (by Microsoft): 주피터 노트북(`.ipynb`) 파일 실행에 필수
   - **`Pylance`** (by Microsoft): 실시간 오류 체크 및 코드 힌트 지원

---

## 3. 개발 및 실행 환경 준비 (최초 1회)

가상환경을 설정하고 패키지를 설치하는 방법은 **자동 설치(배치 파일)**와 **수동 설치** 중 원하는 방식을 선택하실 수 있습니다.

### 방법 A. 원클릭 자동 설치 및 실행 (가장 간편한 방법 👍)

1. **환경 구축 (최초 1회)**:
   - 레포지토리 루트 폴더 내의 **`setup_venv.bat`** 파일을 더블 클릭하여 실행합니다.
   - 자동으로 로컬 가상환경(`.venv`)을 생성하고 `moa_actuator`와 모든 해석 관련 의존성 패키지를 설치합니다.
2. **GUI 툴킷 실행**:
   - 설치 완료 후, 루트 폴더 내의 **`run_gui.bat`** 파일을 더블 클릭하면 복잡한 가상환경 활성화 명령어 없이 바로 GUI 프로그램이 실행됩니다.

---

### 방법 B. 수동 가상환경 설치 및 활성화

**기존에 생성해 둔 전용 가상환경(`PyMotorEnv_310` 등)에 직접 연결하여 설치하고 싶을 때 사용합니다.**

PowerShell을 실행한 후 아래 순서대로 명령어를 입력합니다.

#### B.1 가상환경 활성화
```powershell
# 스크립트 실행 권한 부여 (필요 시)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# 가상환경 활성화 스크립트 실행
& "C:\Users\[사용자_계정]\.ansys_python_venvs\PyMotorEnv_310\Scripts\Activate.ps1"
```

#### B.2 패키지 설치 (의존성 포함)
레포지토리 루트 폴더(`[프로젝트_루트_경로]`)로 이동하여 패키지를 개발자(Editable) 모드로 설치합니다.
```powershell
# 패키지 루트 폴더로 이동
cd [프로젝트_루트_경로]

# 의존성 패키지(GUI, Maxwell, FEMM 등) 및 패키지 설치
python -m pip install -e .[all]
```

---

## 4. GUI 실행 방법

- **방법 A (자동)**: `run_gui.bat` 파일 더블 클릭
- **방법 B (수동)**: 가상환경이 활성화된 터미널에서 다음 명령어 입력
  ```powershell
  python -m moa_actuator gui
  ```

### GUI를 통한 Solenoid 예제 검증 절차

1. **설계 파일 열기**:
   - GUI 상단 메뉴의 `File` -> `Open...` 클릭
   - `example/Dosa_2D_Solenoid/Solenoid.dsa` 선택하여 로드
2. **해석 조건 설정**:
   - **Mode**: `2d`
   - **Solver**: `maxwell` (또는 `femm`)
   - **Output Dir**: `./output`
   - **Dry Run (no AEDT)**: 실제 Maxwell 구동을 보려면 체크 해제
   - **Profile**: `default` 선택
3. **빌드 및 해석**:
   - `Build` 클릭하여 전자기 형상 생성
   - `Solve` 클릭하여 시뮬레이션 연동 구동
   - 결과 로그에서 `Result: OK`가 출력되는지 확인

---

## 5. Jupyter Notebook 검증 방법

레포지토리 루트에는 솔버 연동 및 특성 곡선 추출 과정을 직관적으로 테스트할 수 있는 노트북들이 포함되어 있습니다.

### 5.1 주피터 노트북 실행

가상환경 활성화 상태에서 아래 명령어를 수행합니다. (방법 A의 경우 `.venv\Scripts\activate.bat` 실행 후 입력)

```powershell
jupyter notebook
```

### 5.2 주요 제공 노트북 설명

- **[tutorial_moa_actuator.ipynb](file:///d:/MoaDoSa/MoaActuatorBasedOnDoSA/tutorial_moa_actuator.ipynb)**:
  - `moa_actuator` 전체 기능을 다루는 핵심 종합 튜토리얼입니다.
  - **FEMM 2D**(전류/변위 스윕에 따른 힘 곡선 그리기), **Maxwell 2D/3D**, **GetDP 3D** 솔버 구동 방법을 모두 다룹니다.
- **[tutorial_dosa_maxwell_mvp.ipynb](file:///d:/MoaDoSa/MoaActuatorBasedOnDoSA/tutorial_dosa_maxwell_mvp.ipynb)**:
  - DoSA 파일에서 파싱한 기하학적 형상과 속성을 Maxwell로 1:1 매핑 빌드해 주는 MVP 튜토리얼입니다.
- **[test_moa_actuator.ipynb](file:///d:/MoaDoSa/MoaActuatorBasedOnDoSA/test_moa_actuator.ipynb)**:
  - AEDT 연결 없이 파서, 지오메트리 좌표, 재질 매핑 테이블 및 모의 빌드(Dry-run) 결과를 출력해 보는 단위 테스트용 노트북입니다.

---

## 6. 자주 발생하는 트러블슈팅

1. **`python -m moa_actuator gui` 실행 시 PyQt6 DLL 관련 에러**:
   - PySide2나 타 Qt 바인딩이 동일 가상환경 내에 깔려 있을 때 충돌이 나거나 Windows DLL 탐색 경로가 안 맞아 발생할 수 있습니다. 
   - 가상환경 내에서 `python -e`Editable 모드로 재설치되면서 경로 설정이 완료되었는지 확인하고, 문제가 지속되면 로컬 환경의 DLL 경로를 청소해 줍니다.
2. **Maxwell(AEDT) 연동 시 gRPC 관련 오류**:
   - Ansys Maxwell 프로그램이 정상적으로 활성화되는지 먼저 확인하고, AEDT를 관리자 권한 등으로 단독 실행한 후 다시 시도해 주십시오. (Ansys 버전은 최소 2022 R2 이상 필요)
3. **Dry-run을 통한 사전 확인**:
   - AEDT를 띄울 수 없는 환경이나 빠른 빌드 시뮬레이션 명령 흐름 검증은 `Dry Run` 체크박스를 활성화(또는 CLI 실행 시 `--dry-run` 추가)하여 명령 시퀀스가 정상인지 먼저 점검할 수 있습니다.
