# Maxwell 2D 연동 튜토리얼 (DoSA 2D Solenoid)

이 문서는 `example/Dosa_2D_Solenoid/Solenoid.dsa` 예제를 사용해 MoA Actuator와 Ansys Maxwell 2D를 연동하는 절차를 설명합니다.

전제:
- PyAnsys 개발 가상환경 구성은 별도 PPT에서 안내됨
- 이 문서는 실행/검증 절차에 집중함

---

## 1. 어떤 기준으로 문서를 쓰는 것이 좋은가? (가상환경 배포 가이드)

현재 운영 방침 기준으로는 **가상환경 기반의 실행(python -m moa_actuator gui 및 Jupyter Notebook)**을 핵심 배포 방식으로 채택하고 있습니다.

권장 이유:
- 개발 단계에서 패키지 업데이트 및 기능 확장이 빈번하므로, 가상환경 연동을 통한 대응이 가장 신속함.
- 사용자 및 개발자가 동일한 환경(`pyMotorEnv_310`)을 유지하여 디버깅 및 문제 해결 생산성 향상.
- 단독 EXE의 경우 DLL 충돌 및 라이브러리 연동 제약이 남아있어, 안정적인 가상환경 구동을 기본 가이드로 설정함.

권장 문서 전략:
- 메인 사용자 가이드: Venv Quick Start (가상환경 퀵 스타트 가이드)
- 기술 상세 검증: 가상환경 기반 상세 튜토리얼 (본 문서 및 주피터 노트북)

---

## 2. 대상 예제

- 입력 파일: `example/Dosa_2D_Solenoid/Solenoid.dsa`
- 설계 이름: `Solenoid`
- 테스트 포함: `force_test`, `stroke_test`, `current_test`

---

## 3. 빠른 실행 (GUI 기준)

### 3.1 프로젝트 루트로 이동

```powershell
cd [프로젝트_루트_경로]
```

### 3.2 GUI 실행

```powershell
python -m moa_actuator gui
```

### 3.3 Solenoid 예제 열기

GUI에서:
1. `File` -> `Open...`
2. `example/Dosa_2D_Solenoid/Solenoid.dsa` 선택

### 3.4 Solver 패널 설정

권장 초기값:
- `Mode`: `2d`
- `Solver`: `maxwell`
- `Output Dir`: `./output`
- `Dry Run (no AEDT)`: 해제
- `Non-graphical`: 필요에 따라 선택
  - 디버깅/확인: 해제(그래픽 모드)
  - 배치 실행: 체크(비그래픽)
- `Profile`: `default` (또는 팀에서 지정한 profile)

### 3.5 실행

1. `Build` 클릭
2. `Solve` 클릭
3. 성공 시 결과 플롯(Force) 자동 갱신

성공 시 로그에서 확인할 항목:
- `Result: OK`
- `Project: ... .aedt`

---

## 4. CLI 재현 절차 (자동화/검증용)

GUI와 동일 작업을 CLI로 재현할 수 있습니다.

### 4.1 입력 파일 점검

```powershell
python -m moa_actuator inspect --input .\example\Dosa_2D_Solenoid\Solenoid.dsa
```

### 4.2 Dry-run (명령 생성 검증)

```powershell
python -m moa_actuator run --input .\example\Dosa_2D_Solenoid\Solenoid.dsa --mode 2d --solver maxwell --profile default --out-dir .\output --dry-run
```

### 4.3 실제 Maxwell 실행

```powershell
python -m moa_actuator run --input .\example\Dosa_2D_Solenoid\Solenoid.dsa --mode 2d --solver maxwell --profile default --out-dir .\output
```

그래픽으로 AEDT 창을 보고 싶으면:

```powershell
python -m moa_actuator run --input .\example\Dosa_2D_Solenoid\Solenoid.dsa --mode 2d --solver maxwell --profile default --out-dir .\output --graphical
```

---

## 5. 산출물 확인

기본적으로 다음 위치에 결과가 생성됩니다.

- `output/` 아래 AEDT 프로젝트 및 결과
- 실행 요약 JSON (CLI 실행 시)

팀 운영 팁:
- 실행 이력은 날짜별 하위 폴더를 써서 분리 권장
- 예: `--out-dir .\output\solenoid_20260622`

---

## 6. 자주 발생하는 이슈

1) Maxwell 세션 연결/라이선스 이슈
- 증상: Build/Solve 실패, AEDT 세션 연결 오류
- 조치: AEDT 수동 실행 후 재시도, 라이선스 상태 확인

2) 비그래픽 모드 실패
- 증상: `Non-graphical`에서만 실패
- 조치: 그래픽 모드로 먼저 검증 후 비그래픽 전환

3) 경로 문제
- 증상: 파일 미탐색
- 조치: 프로젝트 루트에서 실행, 상대경로 대신 절대경로 사용

---

## 7. 가상환경 배포의 운영상 장점

가상환경을 기본 배포판으로 활용함으로써 다음 이점을 얻습니다.
- 코드 수정 시 추가 패키징 절차(PyInstaller) 없이 즉각적으로 실행에 반영됨.
- 에러 로그 및 가상환경 출력을 통해 정확한 오류 지점 추적이 가능.
- Jupyter Notebook을 통한 풍부한 데이터 가시화(matplotlib, pandas) 연계 학습 지원.

---

## 8. 권장 문서 세트

1. 본 문서: Maxwell 2D 연동 튜토리얼 (기술 검증 및 가상환경 기준)
2. [Doc/Venv_Quick_Start.md](Venv_Quick_Start.md): 가상환경 빠른 실행 및 주피터 노트북 구동 가이드
3. 레포지토리 루트 README.md: 전체 패키지 소개 및 빠른 실행 시작점 제공
