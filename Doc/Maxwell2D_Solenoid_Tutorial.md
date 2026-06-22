# Maxwell 2D 연동 튜토리얼 (DoSA 2D Solenoid)

이 문서는 `example/Dosa_2D_Solenoid/Solenoid.dsa` 예제를 사용해 MoA Actuator와 Ansys Maxwell 2D를 연동하는 절차를 설명합니다.

전제:
- PyAnsys 개발 가상환경 구성은 별도 PPT에서 안내됨
- 이 문서는 실행/검증 절차에 집중함

---

## 1. 어떤 기준으로 문서를 쓰는 것이 좋은가? (exe vs 가상환경)

현재 운영 방침 기준으로는 **사용자 배포는 exe 우선**, **개발/디버깅은 가상환경 병행**이 적합합니다.

권장 이유:
- 사용자 입장에서는 설치/실행 진입장벽이 가장 낮음
- 개발팀은 pyMotorEnv_310에서 문제 재현/수정이 빠름
- 배포와 개발을 분리하면 운영 안정성이 올라감

권장 문서 전략:
- 메인 사용자 문서: EXE Quick Start
- 기술 검증 문서: 가상환경 기반 상세 튜토리얼(이 문서)

즉, 현재 단계에서는 **2-트랙(exe 배포 + 가상환경 개발) 문서 체계**가 가장 효율적입니다.

---

## 2. 대상 예제

- 입력 파일: `example/Dosa_2D_Solenoid/Solenoid.dsa`
- 설계 이름: `Solenoid`
- 테스트 포함: `force_test`, `stroke_test`, `current_test`

---

## 3. 빠른 실행 (GUI 기준)

### 3.1 프로젝트 루트로 이동

```powershell
cd E:\KDH\gitDosa_Actuator\MoaActuatorBasedOnDoSA
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

## 7. exe 배포는 언제 권장하나?

아래 조건을 만족하면 exe 기준 문서를 메인으로 전환해도 좋습니다.

- 기능/입출력 포맷이 2~4주 이상 안정
- 대상 사용자가 Python 환경 없이 써야 함
- 사내 배포/업데이트 체계(버전 고지, 롤백)가 준비됨

그 전까지는:
- 개발/검증: 가상환경 기준(권장)
- 데모/비개발자 배포: exe 보조 제공

---

## 8. 권장 문서 세트

1. 본 문서: Maxwell 2D 연동 튜토리얼(기술 검증/개발 기준)
2. 별도 2~3페이지: exe Quick Start(사용자 배포 기준)
3. 별도 PPT: PyAnsys 개발환경 구축 가이드

이 구성이 현재 개발 단계에서 유지보수 비용과 사용자 성공률을 가장 잘 균형 맞춥니다.
