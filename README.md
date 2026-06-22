# MoaActuatorBasedOnDoSA

DoSA-2D, DoSA-3D 및 FEMM/Maxwell/GetDP 솔버를 통합한 액추에이터 설계/해석 자동화 툴킷입니다.

## 주요 문서

- **가상환경 실행 퀵 스타트 가이드**: [Doc/Venv_Quick_Start.md](Doc/Venv_Quick_Start.md)
- **Maxwell 2D 연동 상세 튜토리얼 (Solenoid)**: [Doc/Maxwell2D_Solenoid_Tutorial.md](Doc/Maxwell2D_Solenoid_Tutorial.md)
- **EXE 빌드/패키징 가이드 (개발자 전용)**: [packaging/release/README.md](packaging/release/README.md)

---

## 제공 노트북 (Jupyter Notebooks)

패키지의 핵심 기능 검증 및 개별 솔버(FEMM, GetDP, Maxwell) 실습을 위해 루트 폴더에 아래의 주피터 노트북을 제공합니다:
- **[tutorial_moa_actuator.ipynb](tutorial_moa_actuator.ipynb)**: FEMM 2D, Maxwell 2D/3D, GetDP 3D 연동 종합 가이드
- **[tutorial_dosa_maxwell_mvp.ipynb](tutorial_dosa_maxwell_mvp.ipynb)**: DoSA-Maxwell 2D/3D MVP 변환 연동 가이드
- **[test_moa_actuator.ipynb](test_moa_actuator.ipynb)**: AEDT 설치 없이 파서 및 dry-run 검증 가이드

---

## 폴더 구조

```text
MoaActuatorBasedOnDoSA/
├── moa_actuator/      # 통합 액추에이터 자동화 핵심 라이브러리 (Python)
│   ├── solvers/       # FEMM, Maxwell(pyAEDT), GetDP 솔버 백엔드 코드
│   └── gui/           # PyQt6 기반 시각화 및 제어 GUI 코드
├── DoSA-2D/           # DoSA-2D 액추에이터 2D 설계 툴 (C#)
├── DoSA-3D/           # DoSA-3D 액추에이터 3D 설계 툴 (C#)
├── example/           # Solenoid 등 전자기 검증용 샘플 파일 (.dsa, .dsa3d)
├── refDoc/            # 각 시뮬레이션 해석 가이드용 참고 PDF 문서들
├── archive/           # 예전 코드 및 개발자 프로토타입 노트북 아카이브
└── packaging/         # PyInstaller spec 및 배포본 생성 스크립트
```

## 주요 솔버 지원 사항

| 솔버 (Solver) | 차원 | 지원 범위 | 필요 환경 |
|---|---|---|---|
| **FEMM** | 2D (축대칭) | 정자기 해석 및 전류/변위 스윕 힘 연산 | pyfemm + FEMM 4.2 설치 |
| **Maxwell** | 2D/3D (Revolve) | 정자기/과도해석 시뮬레이션 및 데이터 추출 | pyaedt + Ansys AEDT 설치 |
| **GetDP** | 3D (3차원 유한요소) | Gmsh 메싱 연계 3차원 유한요소 전자기 해석 | getdp + gmsh 설치 |
