"""
apps/collector/kis/daily_candle.py

단일 종목의 일봉(OHLCV) 데이터를 KIS API에서 조회하는 모듈.
"""

import os
import requests
import pandas as pd
from datetime import datetime
from typing import Optional

def get_daily_candle(
    symbol: str,
    start_date: str,
    end_date: str,
    access_token: str,
    env: str = "real",
) -> pd.DataFrame:
    """
    KIS API: 일봉 조회 (inquire-daily-itemchartprice)

    Parameters
    ----------
    symbol : str
        종목코드 (예: "005930")
    start_date : str
        조회 시작일 (YYYYMMDD)
    end_date : str
        조회 종료일 (YYYYMMDD)
    access_token : str
        KIS 인증 토큰
    env : str
        "real" (실전) 또는 "mock" (모의)

    Returns
    -------
    pd.DataFrame
        일봉 데이터 (date, open, high, low, close, volume, value, symbol)
    """
    base_url = (
        "https://openapi.koreainvestment.com:9443"
        if env == "real"
        else "https://openapivts.koreainvestment.com:29443"
    )
    tr_id = "FHKST03010100" if env == "real" else "VTKST03010100"

    url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {access_token}",
        "appkey": os.getenv("KIS_API_KEY"),
        "appsecret": os.getenv("KIS_API_SECRET"),
        "tr_id": tr_id,
    }
    params = {
        "fid_cond_mrkt_div_code": "J",   # J=주식
        "fid_input_iscd": symbol,
        "fid_org_adj_prc": "1",          # 수정주가
        "fid_period_div_code": "D",      # 일봉
        "fid_input_date_1": start_date,
        "fid_input_date_2": end_date,
    }

    res = requests.get(url, headers=headers, params=params, timeout=10)
    res.raise_for_status()
    data = res.json()

    if "output2" not in data:
        return pd.DataFrame()

    df = pd.DataFrame(data["output2"])
    df = df.rename(
        columns={
            "stck_bsop_date": "date",
            "stck_oprc": "open",
            "stck_hgpr": "high",
            "stck_lwpr": "low",
            "stck_clpr": "close",
            "acml_vol": "volume",
            "acml_tr_pbmn": "value",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df["symbol"] = symbol
    return df
