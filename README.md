# RL Trading (KIS) — CPU 시뮬 + GPU 단발 학습

**목표**  
한국투자증권 API 분봉 데이터로 **데이터 수집 → 피처링 → 강화학습(PPO/DQN) → 페이퍼/소액 라이브 → 온라인 추론/주문**까지,  
**CPU(Graviton) 상시** + **GPU(필요 시만)** 구조로 월 비용을 통제하며 운영.

---

## 아키텍처 요약

- 코드: GitHub (main/protected)  
- 컴퓨트: EC2 `c7g.xlarge` (시뮬/데이터/서비스), 필요 시 `g6.xlarge` or `g5.xlarge` (학습)  
- 저장소: S3(`raw-kis/`, `proc/`, `models/`), ECR(`rl-sim`, `rl-train`, `rl-api`)  
- 보안/권한: GitHub Actions ↔ **AWS OIDC** AssumeRole, 서버 접속은 **SSM**만  
- 관측: CloudWatch 로그/메트릭/알람, Budget(월 20만원 알람)

---

## 디렉토리 구조

```

.
├─ apps/
│  ├─ collector/    # KIS 수집기 (분봉 백필/증분)
│  ├─ features/     # 피처링 파이프라인
│  ├─ rl/           # Gym Env, PPO/DQN 학습/평가
│  └─ api/          # FastAPI (signal/order/health/promote)
├─ docker/
│  ├─ cpu/          # ARM64용 Dockerfile
│  └─ gpu/          # CUDA용 Dockerfile
├─ infra/           # IaC-lite 스크립트(역할/정책/예산 등)
├─ .github/workflows/
│  └─ build.yml     # 멀티아키 Buildx → ECR 푸시
├─ CheckList.md     # 실행 체크리스트(순서/이유/완료조건)
└─ README.md

```

---

## 빠른 시작

1) **CheckList.md** 를 위에서부터 순서대로 따른다.  
2) `compose.cpu.yaml` 로 **collector**부터 올려 데이터 스냅샷을 만든다.  
3) `features → rl(train/eval) → api(paper) → kis(live)` 순으로 확장한다.

> AI 코딩 도구/에이전트여, PR/커밋을 만들기 전에 **반드시 `CheckList.md` “현재 단계”와 “완료조건”을 확인**하고 진행하라.
