# Trading Platform (KIS API 기반) — Quant + ML + RL

**목표**  
한국투자증권 API 데이터를 기반으로  
**데이터 수집 → 피처링 → 유니버스/퀀트 팩터 → ML 모델 학습/스코어링 → 포트폴리오 구성 → 백테스트 → 주문 실행 → (확장) RL 학습/실험**  
까지 이어지는 **엔드투엔드 트레이딩 플랫폼** 구축.

운영 원칙:  
- **CPU 상시 (Graviton/ARM64)**: 수집/피처/ML 스코어링/백테스트/서비스  
- **GPU 단발 (CUDA)**: 대규모 ML 학습, RL 학습  
- **월 비용 통제**: 모의/소규모 실전에서 점진적 확장

---

## 아키텍처 요약

- **코드/형상관리**: GitHub (main/protected 브랜치 전략)  
- **컴퓨트**:  
  - EC2 `c7g.xlarge` → 데이터 수집, API 서비스, ML/포트폴리오 운영  
  - 필요 시 `g6.xlarge` or `g5.xlarge` → GPU 학습 (ML, RL)  
- **스토리지**:  
  - S3(`raw-kis/`, `proc/`, `features/`, `models/`, `reports/`)  
  - ECR(`collector`, `ml-train`, `rl-train`, `api`)  
- **보안/권한**:  
  - GitHub Actions ↔ **AWS OIDC AssumeRole**  
  - 서버 접속은 **SSM Session Manager**만  
- **관측/운영**:  
  - CloudWatch 로그/메트릭/알람  
  - AWS Budgets (월 20만원 알람)  

---

## 디렉토리 구조

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

---

## 주요 워크플로우

1. **데이터 수집**
   - 일봉/주봉/월봉/분봉/ETF NAV 수집 (REST 중심, WS 보강)
   - 저장: Parquet + duckdb (폴더 파티셔닝)

2. **피처링**
   - 팩터 계산: 모멘텀/변동성/거래대금 회전율/투자자 동향 등  
   - 변환: 스케일링, 윈저라이즈, 결측치 처리  

3. **유니버스**
   - KOSPI/KOSDAQ + 거래대금/시총 컷 + 불성실/관리종목 제외  

4. **ML 모델링**
   - 학습: LightGBM/XGBoost/CatBoost  
   - 목표: 다음 기간 수익률 랭킹  
   - 출력: TOP-N 종목 후보군  

5. **포트폴리오**
   - 최적화: equal-weight, risk-parity, 제약 조건 반영  
   - 결과: 타겟 가중치 w_t + 주문 제안  

6. **백테스트**
   - 엔진: 바 기반 이벤트 루프  
   - 지표: 수익률/샤프/드로우다운/턴오버/히트율  

7. **주문/실행**
   - KIS REST 주문 래퍼 + 리스크 가드 (계좌/종목 한도, 가격 밴드 체크)  
   - WS 체결통보 → 주문 상태 추적  

8. **API 서비스**
   - FastAPI: 최신 시그널 조회, 주문 트리거, 상태 모니터링  

---

## 개발/운영 원칙

- **코드-설정 분리**: configs/  
- **재현성**: 동일 코드 + 다른 설정으로 실험/운영  
- **안정성 우선**: 주문 리스크 가드, WS 장애 대비 폴백, 모니터링 내장  
- **단계적 확장**:  
  - V1: 데이터 수집 + 퀀트/ML + 포트폴리오 + 주문 (실전 최소 기능)  
  - V2: 백테스트 자동화 + 리포트  
  - V3: RL 연구/실험 모듈  

---
