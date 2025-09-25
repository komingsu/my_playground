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
├─ libs/
│  ├─ kis_client.py              # KIS 인증/호출 공통 (일봉/분봉 공용)
│  ├─ utils_io.py                # parquet 증분 저장/리샘플 유틸
│  └─ symbols.py (선택)          # load_symbols(), (선택) 전체심볼 갱신 → 파일로 덤프
├─ scripts/
│  ├─ run_download_intraday.py   # 1분봉 수집(현재 액션의 유일 엔트리)
│  └─ run_download_daily.py (선택)# daily_candle.py를 리네임한 일봉 수집 엔트리
├─ data/
│  ├─ raw/
│  │  ├─ kis_intraday/<SYM>/1m/data.parquet  # 1분 원천(증분)
│  │  └─ kis_daily/<SYM>/1d/data.parquet     # (선택) 일봉 원천(증분)
│  ├─ proc/                     # 리샘플/보조지표 결과(다음 액션에서 생성)
│  └─ meta/top50_symbols.txt    # 유니버스 단일 진실 원천(파일 기반)
├─ archive/                      # 지금 당장 안 쓰는 파일 보관
│  └─ daily_candle.py, symbols.py (필요 시 여기로 이동)
└─ README.md
```
