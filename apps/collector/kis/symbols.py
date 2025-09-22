"""
apps/collector/kis/symbols.py

전 종목 심볼 마스터를 수집하여 저장하는 모듈.
FinanceDataReader를 통해 KOSPI/KOSDAQ 종목리스트 확보.
"""

import FinanceDataReader as fdr
import pandas as pd
from pathlib import Path
from datetime import datetime


def get_symbol_master() -> pd.DataFrame:
    """
    KOSPI/KOSDAQ 전체 종목 리스트 반환.

    Returns
    -------
    pd.DataFrame
        컬럼: symbol, name, market
    """
    kospi = fdr.StockListing("KOSPI")
    kosdaq = fdr.StockListing("KOSDAQ")
    df = pd.concat([kospi, kosdaq], ignore_index=True)
    df = df.rename(columns={"Code": "symbol", "Name": "name", "Market": "market"})
    return df[["symbol", "name", "market"]]


def save_symbol_master():
    today = datetime.now().strftime("%Y%m%d")
    df = get_symbol_master()
    outdir = Path("data/raw/kis/symbol_master")
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / f"{today}.parquet"
    df.to_parquet(outfile, index=False)
    print("✅ Symbol master 저장 완료:", outfile, "종목 수:", len(df))


if __name__ == "__main__":
    save_symbol_master()
