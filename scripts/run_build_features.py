"""
scripts/run_build_features.py

Daily OHLCV 데이터를 바탕으로 Factor 생성 및 전처리.
결과는 data/proc/features/{today}.parquet 저장.
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd


NUMERIC_COLS = ["open", "high", "low", "close", "volume", "value"]


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """문자열로 온 숫자 컬럼들을 안전하게 숫자로 변환."""
    out = df.copy()

    # date -> datetime
    if not np.issubdtype(out["date"].dtype, np.datetime64):
        out["date"] = pd.to_datetime(out["date"], errors="coerce")

    # 숫자 컬럼: 콤마/공백 제거 후 to_numeric
    for c in NUMERIC_COLS:
        if c in out.columns:
            out[c] = (
                out[c]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            out[c] = pd.to_numeric(out[c], errors="coerce")

    return out


def add_factors(group: pd.DataFrame) -> pd.DataFrame:
    """
    단일 종목 데이터프레임(group)에 팩터를 추가.
    전제: group은 날짜 오름차순, 숫자 컬럼은 모두 numeric.
    """
    df = group.sort_values("date").copy()

    # 수익률(모멘텀)
    df["ret_1d"]   = df["close"].pct_change(1)
    df["ret_5d"]   = df["close"].pct_change(5)
    df["ret_20d"]  = df["close"].pct_change(20)
    df["ret_60d"]  = df["close"].pct_change(60)
    df["ret_120d"] = df["close"].pct_change(120)

    # EMA (추세)
    df["ema_20"]  = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_60"]  = df["close"].ewm(span=60, adjust=False).mean()
    df["ema_120"] = df["close"].ewm(span=120, adjust=False).mean()
    df["momentum"] = df["close"] / df["ema_120"] - 1

    # 변동성
    df["volatility_20d"] = df["ret_1d"].rolling(20, min_periods=10).std()
    df["volatility_60d"] = df["ret_1d"].rolling(60, min_periods=20).std()

    # 거래/유동성
    df["vol_ma20"]  = df["volume"].rolling(20, min_periods=10).mean()
    df["vol_ma60"]  = df["volume"].rolling(60, min_periods=20).mean()
    df["volume_mean_ratio"] = df["vol_ma20"] / df["vol_ma60"]

    # 거래대금 안정화
    df["value_traded"] = np.log1p(df["value"])

    # (옵션) 다음날 수익률을 타깃으로 쓸 수 있도록 미리 추가
    df["target_ret_1d"] = df["close"].shift(-1) / df["close"] - 1

    return df


def winsorize(df: pd.DataFrame, cols: list[str], p: float = 0.01) -> pd.DataFrame:
    """각 컬럼별로 하위 p, 상위 (1-p) 분위수로 클리핑."""
    out = df.copy()
    for c in cols:
        if c in out.columns:
            q_low, q_high = out[c].quantile([p, 1 - p])
            out[c] = out[c].clip(lower=q_low, upper=q_high)
    return out


def main():
    today = datetime.now().strftime("%Y%m%d")
    infile = Path(f"data/raw/kis/daily/{today}.parquet")
    if not infile.exists():
        raise FileNotFoundError(f"Daily OHLCV 파일 없음: {infile}")

    df = pd.read_parquet(infile)
    print("원본 데이터:", df.shape)

    # 1) 타입 정리
    df = _coerce_numeric(df)

    # 최소 컬럼 체크
    required = {"date", "symbol", "open", "high", "low", "close", "volume", "value"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 2) 종목별 레코드가 너무 적은 것 제외 (ex: 60거래일 미만)
    counts = df.groupby("symbol")["date"].count()
    enough = counts[counts >= 60].index
    df = df[df["symbol"].isin(enough)]

    # 3) 종목별 팩터 생성
    df_feat = (
        df.sort_values(["symbol", "date"])
          .groupby("symbol", group_keys=False)
          .apply(add_factors)
    )

    # 4) 윈저라이즈 (극단값 완화)
    clip_cols = [
        "ret_1d", "ret_5d", "ret_20d", "ret_60d", "ret_120d",
        "momentum", "volatility_20d", "volatility_60d",
        "volume_mean_ratio", "value_traded", "target_ret_1d",
    ]
    df_feat = winsorize(df_feat, clip_cols, p=0.01)

    # 5) 저장
    outdir = Path("data/proc/features")
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / f"{today}.parquet"
    df_feat.to_parquet(outfile, index=False)
    print("✅ Factor 저장 완료:", outfile, "shape:", df_feat.shape)


if __name__ == "__main__":
    main()
