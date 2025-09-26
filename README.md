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
my_playground/
├─ README.md                      # 현재 상태/다음 액션(1개)만 기재
├─ libs/
│  ├─ kis_auth.py                # KIS 토큰 발급/갱신 유틸(공용 인증)  :contentReference[oaicite:1]{index=1}
│  └─ daily_candle.py            # 일봉(1d) 수집/저장 로직(기존)       :contentReference[oaicite:2]{index=2}
├─ scripts/
│  ├─ run_collect_daily.py       # 일봉 수집 엔트리(기존)              :contentReference[oaicite:3]{index=3}
│  └─ run_score_quant.py         # 스코어 산출/TopN 선정(기존)         :contentReference[oaicite:4]{index=4}
├─ data/
│  ├─ raw/                       # 원천(무가공) 저장소
│  │  └─ kis_daily/<SYM>/1d/    # 일봉 parquet(증분) - daily_candle 결과
│  ├─ proc/
│  │  └─ selection/
│  │     └─ 20250923_top50.csv  # 현재 선정된 Top 50 (유니버스 소스)   :contentReference[oaicite:5]{index=5}
│  └─ meta/
│     └─ top50_symbols.txt      # (다음 단계에서) 분봉 수집용 심볼 리스트로 변환
```
