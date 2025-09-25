# Trading Platform (KIS API 기반)

운영 원칙:  
- **CPU 상시 (Graviton/ARM64)**: 수집/피처/ML 스코어링/백테스트/서비스  
- **GPU 단발 (CUDA)**: 대규모 ML 학습, RL 학습  
---

## 설계 단계별 요약

* 퀀트를 이용한 종목(50가지) 선정
* 50가지 주식 분봉 데이터 수집
  * 보조 지표, 공포 탑욕 지수 데이터 넣기 
* 트레이딩 RL 학습하기
* ChatGPT 와 같은 에이전트를 이용한 의사결정 및 실제 거래 준비
  * API 발급 및 토큰 충전
  * 신뢰도 이상일때만 거래 - 안전장치
  * 변동성 지수를 통한 탈출 전략 - 안전장치
  * 입출력 구조화 - JSON 형태 출력하기
  * RL이 전달한 거래내용을 보고 의사결정하기
 * 재귀 개선 시스템 구현하기
  * 투자 데이터 DB 기록하기, 기록 저장, 결과 학인
  * GPT가 그 결과를 통해 회고하고, 학습하도록 만들기
  * Streamlit을 이용하여 웹사이트 대시보드 생성하기
 * 최종 - 클라우드 배포하기
   * AWS에서 EC2 서버 만들기
   * 코드 깃헙 -> 클라우드 컴퓨터로 옮기기
   * 서버 환경 설정
 * AI 에이전트 클라우드 서버 운영하기
   * 코드 초기화 및 재업로드
   * 운영 코드 활성화
   * 백그라운드 실행
   * streamlit 웹 모니터링 실행
---

## 디렉토리 구조 (수정 필요)

```

.
├─ apps/
│  ├─ collector/      # 데이터 수집기 (KIS REST/WS)
│  │  ├─ kis/         # 인증/REST/WS 커넥터
│  │  ├─ jobs/        # ohlcv\_daily, intraday\_1m 등 잡
│  │  └─ pipelines/   # 배치/증분 수집 파이프라인
│  ├─ features/       # 피처 엔지니어링 (팩터/변환/Feature Store)
│  ├─ universe/       # 유니버스(종목 선정 규칙)
│  ├─ ml/             # ML 학습/스코어링/평가 (LightGBM/XGBoost/CatBoost)
│  ├─ portfolio/      # 포트폴리오 최적화/리밸런싱/체결 시뮬
│  ├─ backtest/       # 백테스트 엔진/성과리포트
│  ├─ rl/             # (확장) Gym Env, PPO/DQN 학습/평가
│  └─ api/            # FastAPI 서비스 (signal/order/health/promote)
│     ├─ routers/
│     ├─ services/
│     └─ schemas/
├─ packages/          # 공통 모듈
│  ├─ core/           # 시간/캘린더/로그/에러/설정
│  ├─ data/           # 데이터 IO (Parquet/duckdb)
│  └─ trading/        # 주문 래퍼(KIS)/리스크 가드/체결 추적
├─ configs/           # 설정 (환경/env, 파이프라인/jobs, 전략/strategies)
├─ data/              # 로컬 개발 캐시 (raw/proc/features/outputs)
├─ docker/
│  ├─ cpu/            # ARM64용 Dockerfile
│  └─ gpu/            # CUDA용 Dockerfile
├─ infra/             # IaC-lite 스크립트 (역할/정책/예산)
├─ notebooks/         # 실험/EDA/프로토타입
├─ scripts/           # 실행 엔트리포인트 (run\_collect\_\*, run\_train\_ml 등)
├─ tests/             # 단위/통합 테스트
├─ .github/workflows/
│  └─ build.yml       # 멀티아키 Buildx → ECR 푸시
├─ CheckList.md       # 실행 체크리스트 (순서/이유/완료조건)
├─ KIS\_API.md         # KIS API 사용 노트
├─ pyproject.toml     # 의존성/패키징 (또는 requirements.txt)
└─ README.md

```
