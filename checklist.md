# 실행 체크리스트

## A. 준비
- [ ] `kis_devlp.yaml` / `kis_prod.yaml` 설정 (AppKey, Secret, 계좌)
- [ ] 패키지 설치 (`poetry install` or `pip install -r requirements.txt`)
- [ ] `data/` 폴더 생성 (raw/proc/features/outputs)

## B. 데이터 수집
- [ ] `scripts/run_collect_ohlcv_daily.py` 실행 (백필/증분)
- [ ] `scripts/run_collect_intraday.py` 실행 (분봉 리샘플)
- [ ] 저장된 Parquet/duckdb 정상 확인

## C. 피처링
- [ ] `scripts/run_build_features_daily.py` 실행
- [ ] 팩터 컬럼 정상 생성 여부 확인

## D. 유니버스
- [ ] `scripts/run_build_universe.py` 실행
- [ ] 종목 수 / 필터링 규칙 확인

## E. ML 학습/스코어링
- [ ] `scripts/run_train_ml.py` 실행 (Cross-validation 통과)
- [ ] `scripts/run_score_ml.py` 실행 (스코어/랭킹 파일 생성)

## F. 포트폴리오
- [ ] `scripts/run_portfolio_build.py` 실행
- [ ] 결과 가중치/주문 제안 sanity check

## G. 백테스트
- [ ] `scripts/run_backtest.py` 실행
- [ ] 성과 리포트 검증 (수익률/위험지표)

## H. 주문/실행
- [ ] 모의투자 계좌에서 `scripts/run_order_rebalance.py` 실행
- [ ] WS 체결통보 → 체결상태 로그 확인
- [ ] 리스크 가드 동작 확인

## I. API 서비스
- [ ] `apps/api` FastAPI 실행 (`uvicorn main:app`)
- [ ] `/signals` `/orders` `/health` 엔드포인트 확인

## J. 운영 모니터링
- [ ] CloudWatch 로그/알람 확인
- [ ] AWS Budgets 알람 확인
