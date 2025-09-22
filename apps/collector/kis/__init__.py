"""
KIS API Collector Package

이 패키지는 한국투자증권(KIS) API 기반의 데이터 수집 모듈을 포함합니다.
현재 제공 기능:
- daily_candle.py : 실전 계정 기반 일봉 데이터 조회 및 저장

예시 사용법:
    from apps.collector.kis.daily_candle import get_daily_candle, get_or_load_access_token

    token = get_or_load_access_token()
    df = get_daily_candle("005930", access_token=token)
"""

# 외부에서 import 시 바로 접근할 수 있게 export
from .daily_candle import get_daily_candle