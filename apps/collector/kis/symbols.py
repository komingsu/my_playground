"""
apps/collector/kis/symbols.py

전 종목 심볼 마스터를 수집하여 저장.
- FDR 'KRX' 기반 전체 상장종목 메타 확보 (섹터/산업/시총/주식수/밸류)
- KOSPI200, KOSDAQ150 구성종목 플래그 추가 (가능한 경우)
출력:
  data/raw/kis/symbol_master/{YYYYMMDD}.parquet
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

import pandas as pd
import FinanceDataReader as fdr  # pip install finance-datareader


def _safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def get_symbol_master() -> pd.DataFrame:
    # 1) 전체 상장(KRX)
    krx = fdr.StockListing("KRX")
    rename_map = {
        "Code": "symbol",
        "Name": "name",
        "Market": "market",
        "Sector": "sector",
        "Industry": "industry",
        "Marcap": "market_cap",
        "Stocks": "shares",
        "PER": "per",
        "PBR": "pbr",
        "EPS": "eps",
        "BPS": "bps",
    }
    for k, v in rename_map.items():
        if k in krx.columns:
            krx = krx.rename(columns={k: v})

    cols = [c for c in ["symbol", "name", "market", "sector", "industry",
                        "market_cap", "shares", "per", "pbr", "eps", "bps"] if c in krx.columns]
    df = krx[cols].dropna(subset=["symbol"]).drop_duplicates("symbol")
    for c in ["market_cap", "shares", "per", "pbr", "eps", "bps"]:
        if c in df.columns:
            df[c] = _safe_numeric(df[c])

    # 2) 지수 구성종목 플래그
    for idx_name, colflag in [("KOSPI200", "is_kospi200"), ("KOSDAQ150", "is_kosdaq150")]:
        try:
            idx_df = fdr.StockListing(idx_name)
            sym_col = "Code" if "Code" in idx_df.columns else "Symbol"
            syms = set(idx_df[sym_col].astype(str).str.zfill(6))
            df[colflag] = df["symbol"].astype(str).str.zfill(6).isin(syms)
        except Exception:
            df[colflag] = False

    if "market" in df.columns:
        df["market"] = df["market"].astype(str)

    return df


def save_symbol_master():
    today = datetime.now().strftime("%Y%m%d")
    outdir = Path("data/raw/kis/symbol_master")
    outdir.mkdir(parents=True, exist_ok=True)
    df = get_symbol_master()
    path = outdir / f"{today}.parquet"
    df.to_parquet(path, index=False)
    print(f"✅ Symbol master 저장: {path} (종목 수: {len(df)})")


if __name__ == "__main__":
    save_symbol_master()
