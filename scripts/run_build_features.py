"""
scripts/run_build_features.py

Daily OHLCV 기반 멀티팩터 피처 생성.
- 심볼 마스터(섹터/시총/밸류 등) 병합
- 모멘텀/변동성/유동성 + size/turnover + (가능시) PER/PBR/EPS/BPS
- 유동성: 20일 평균 거래대금 로그로 안정화
- 최소 거래일수 MIN_BARS (데이터 충분하면 252로 올려 운영 권장)

입력:
  data/raw/kis/daily/{YYYYMMDD}.parquet
  data/raw/kis/symbol_master/{YYYYMMDD}.parquet
출력:
  data/proc/features/{YYYYMMDD}.parquet
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

# ==== 설정 ====
# 데이터가 아직 얕으면 120부터 시작 → 충분히 쌓이면 252로 변경 권장
MIN_BARS = 120

NUMERIC_COLS = ["open", "high", "low", "close", "volume", "value"]
BASE_COLS = ["date", "open", "high", "low", "close", "volume", "value"]


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "date" in out.columns and not np.issubdtype(out["date"].dtype, np.datetime64):
        out["date"] = pd.to_datetime(out["date"], errors="coerce")

    for c in NUMERIC_COLS:
        if c in out.columns:
            out[c] = out[c].astype(str).str.replace(",", "", regex=False).str.strip()
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def add_factors(group: pd.DataFrame) -> pd.DataFrame:
    df = group.sort_values("date").copy()

    # 수익률(모멘텀)
    df["ret_1d"]   = df["close"].pct_change(1)
    df["ret_5d"]   = df["close"].pct_change(5)
    df["ret_20d"]  = df["close"].pct_change(20)
    df["ret_60d"]  = df["close"].pct_change(60)
    df["ret_120d"] = df["close"].pct_change(120)

    # EMA/추세
    df["ema_20"]  = df["close"].ewm(span=20,  adjust=False).mean()
    df["ema_60"]  = df["close"].ewm(span=60,  adjust=False).mean()
    df["ema_120"] = df["close"].ewm(span=120, adjust=False).mean()
    df["momentum"] = df["close"] / df["ema_120"] - 1

    # 변동성
    df["volatility_20d"] = df["ret_1d"].rolling(20,  min_periods=10).std()
    df["volatility_60d"] = df["ret_1d"].rolling(60,  min_periods=20).std()

    # 거래/유동성 (안정화): 20일 평균 거래대금의 로그
    df["val_ma20"]  = df["value"].rolling(20, min_periods=10).mean()
    df["val_ma60"]  = df["value"].rolling(60, min_periods=20).mean()
    df["value_traded"] = np.log1p(df["val_ma20"])

    # 거래량 평균 비율
    df["vol_ma20"]  = df["volume"].rolling(20, min_periods=10).mean()
    df["vol_ma60"]  = df["volume"].rolling(60, min_periods=20).mean()
    df["volume_mean_ratio"] = df["vol_ma20"] / df["vol_ma60"]

    # 타깃(옵션)
    df["target_ret_1d"] = df["close"].shift(-1) / df["close"] - 1

    return df


def winsorize(df: pd.DataFrame, cols: list[str], p: float = 0.01) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            q_low, q_high = out[c].quantile([p, 1 - p])
            out[c] = out[c].clip(lower=q_low, upper=q_high)
    return out


def _safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce"
    )


def main():
    today = datetime.now().strftime("%Y%m%d")
    daily_path = Path(f"data/raw/kis/daily/{today}.parquet")
    if not daily_path.exists():
        raise FileNotFoundError(f"Daily OHLCV 파일 없음: {daily_path}")

    df = pd.read_parquet(daily_path)
    print("원본 데이터:", df.shape)

    # 1) 타입 정리
    df = _coerce_numeric(df)

    required = {"date", "symbol", "open", "high", "low", "close", "volume", "value"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 2) 종목별 레코드 수 필터
    cnt = df.groupby("symbol")["date"].count()
    keep_syms = cnt[cnt >= MIN_BARS].index
    df = df[df["symbol"].isin(keep_syms)]

    # 3) 팩터 생성 (symbol 복원)
    df_feat = (
        df.sort_values(["symbol", "date"])
          .groupby("symbol", group_keys=True)[BASE_COLS]
          .apply(add_factors)
          .reset_index(level=0)
          .rename(columns={"level_0": "symbol"})
    )

    if "symbol" not in df_feat.columns:
        raise RuntimeError("팩터 생성 후 'symbol' 컬럼이 존재하지 않습니다.")

    # 4) 심볼 마스터 병합(섹터/시총/밸류 등)
    sym_path = Path(f"data/raw/kis/symbol_master/{today}.parquet")
    if sym_path.exists():
        sm = pd.read_parquet(sym_path)
        cols = [c for c in ["symbol", "name", "market", "sector", "industry",
                            "market_cap", "shares", "per", "pbr", "eps", "bps",
                            "is_kospi200", "is_kosdaq150"] if c in sm.columns]
        sm = sm[cols].drop_duplicates("symbol")
        for c in ["market_cap", "shares", "per", "pbr", "eps", "bps"]:
            if c in sm.columns:
                sm[c] = _safe_numeric(sm[c])
        df_feat = df_feat.merge(sm, on="symbol", how="left")
    else:
        print("⚠️ symbol_master가 없어 메타 병합 생략")

    # 파생: size/turnover
    if "market_cap" in df_feat.columns:
        df_feat["log_mcap"] = np.log1p(df_feat["market_cap"])
        df_feat["turnover"] = df_feat["value"] / df_feat["market_cap"]
    else:
        df_feat["log_mcap"] = np.nan
        df_feat["turnover"] = np.nan

    # 5) 윈저라이즈
    clip_cols = [
        "ret_1d", "ret_5d", "ret_20d", "ret_60d", "ret_120d",
        "momentum", "volatility_20d", "volatility_60d",
        "volume_mean_ratio", "value_traded", "target_ret_1d",
        "log_mcap", "turnover", "per", "pbr", "eps", "bps",
    ]
    df_feat = winsorize(df_feat, clip_cols, p=0.01)

    # 6) 저장
    outdir = Path("data/proc/features")
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / f"{today}.parquet"
    df_feat.to_parquet(outfile, index=False)
    print("✅ Factor 저장 완료:", outfile, "shape:", df_feat.shape)


if __name__ == "__main__":
    main()
