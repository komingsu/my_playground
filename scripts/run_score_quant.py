"""
scripts/run_score_quant.py

목적
- 가장 최근 팩터 스냅샷(= feature 패널에서 최신 날짜 단면)을 불러와
  유니버스 필터링(유동성 컷) → 스코어링/랭킹 → TOP-N(기본 50) 선별 → 가중치 부여(EW/리스크조정)
  까지 수행하여 저장.

입력
- data/proc/features/{YYYYMMDD}.parquet : run_build_features.py 결과 (1년 패널)
- (선택) data/raw/kis/symbol_master/{YYYYMMDD}.parquet : 종목 메타(있으면 조인, 없어도 OK)

출력
- data/proc/selection/{YYYYMMDD}_top50.parquet
- data/proc/selection/{YYYYMMDD}_top50.csv

스코어(예시)
    score = 0.5 * Z(momentum) 
          + 0.3 * Z(-volatility_20d) 
          + 0.2 * Z(liquidity)
여기서
    momentum := ret_60d (또는 ema 기반 momentum)
    volatility_20d := 20일 표준편차 (낮을수록 좋게 음의 부호)
    liquidity := value_traded (log(거래대금)) 또는 volume_mean_ratio

가중치
- 기본: Equal Weight (1/N)
- 옵션: Inverse-Vol (최근 60일 변동성 역수 비례), 심한 쏠림 방지용 cap(예: 5%)

사용
    python -m scripts.run_score_quant
옵션 변경은 코드 상단 파라미터 수정
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd


# =========================
# 설정 파라미터
# =========================
TOP_N = 50
LIQUIDITY_CUTOFF_PCT = 0.20   # 하위 20% 유동성 컷 (값이 클수록 많이 제거)
WEIGHTING_METHOD = "equal"    # "equal" 또는 "inv_vol"
MAX_WEIGHT_CAP = 0.05         # 리스크조정 시 종목당 최대 비중(예: 5%)

# 팩터 컬럼 이름 (run_build_features.py 기준)
FACTOR_COLS = {
    "momentum": "ret_60d",          # 필요시 "momentum" (close/ema120 -1)로 바꿔도 됨
    "volatility": "volatility_20d",
    "liquidity": "value_traded",    # 또는 "volume_mean_ratio"
}

# 파일명 날짜(오늘 기준). 과거 파일을 쓰고 싶으면 YYYYMMDD로 고정해도 됨.
# TODAY = datetime.now().strftime("%Y%m%d")
TODAY = 20250922


@dataclass
class Inputs:
    features_path: Path
    symbols_path: Optional[Path] = None


def _latest_cross_section(df: pd.DataFrame) -> pd.DataFrame:
    """panel에서 가장 최근 date의 단면만 추출 (symbol별 마지막이 아닌, 전 종목 동일 최근일자)."""
    # 가장 최근 영업일 찾기
    latest_date = df["date"].max()
    cs = df[df["date"] == latest_date].copy()
    cs["date"] = pd.to_datetime(cs["date"])
    return cs


def _zscore(series: pd.Series) -> pd.Series:
    """표준화 (평균/표준편차). 값이 모두 동일하면 0 반환."""
    s = series.astype(float)
    mu = s.mean()
    sigma = s.std(ddof=0)
    if not np.isfinite(sigma) or sigma == 0:
        return pd.Series(np.zeros(len(s)), index=series.index)
    return (s - mu) / sigma


def _prep_inputs() -> Inputs:
    """입력 파일 경로 확인."""
    feat_path = Path(f"data/proc/features/{TODAY}.parquet")
    if not feat_path.exists():
        raise FileNotFoundError(f"features 파일이 없습니다: {feat_path}")

    sym_path = Path(f"data/raw/kis/symbol_master/{TODAY}.parquet")
    # 심볼 마스터는 없어도 진행 가능
    return Inputs(features_path=feat_path, symbols_path=sym_path if sym_path.exists() else None)


def _load_features(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    # 안전한 타입 정리
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["close", "volume", "value", "ret_60d", "volatility_20d", "value_traded", "volume_mean_ratio", "momentum"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _merge_symbol_meta(cs: pd.DataFrame, symbols_path: Optional[Path]) -> pd.DataFrame:
    """symbol_master가 있으면 조인 (시장/이름/섹터 등). 없어도 통과."""
    if symbols_path is None:
        return cs
    try:
        sm = pd.read_parquet(symbols_path)
        # 최소 컬럼 rename/선택 (FDR 기반이면 symbol/name/market만 있을 수도 있음)
        cols = [c for c in ["symbol", "name", "market"] if c in sm.columns]
        sm = sm[cols].drop_duplicates("symbol")
        out = cs.merge(sm, on="symbol", how="left")
        return out
    except Exception as e:
        print(f"⚠️ symbol_master 병합 실패, 메타정보 없이 진행합니다: {e}")
        return cs


def _apply_liquidity_filter(cs: pd.DataFrame, liquidity_col: str = "value_traded", cutoff_pct: float = 0.20) -> pd.DataFrame:
    """
    유동성 기준 하위 퍼센타일 컷. 기본은 log(거래대금) value_traded.
    하위 20% 제거 → 남은 80%에서만 랭킹.
    """
    if liquidity_col not in cs.columns:
        print(f"⚠️ 유동성 컬럼({liquidity_col})이 없어 컷을 생략합니다.")
        return cs

    q = cs[liquidity_col].quantile(cutoff_pct)
    kept = cs[cs[liquidity_col] >= q].copy()
    print(f"유동성 컷: {liquidity_col} {cutoff_pct*100:.0f}% 분위수={q:,.3f} → 유지 {len(kept)}/{len(cs)}")
    return kept


def _compute_score(cs: pd.DataFrame, cols: dict) -> pd.DataFrame:
    """
    스코어 계산 (크로스섹션 Z-score 조합).
    momentum: 높을수록 좋음
    volatility: 낮을수록 좋음 → 음(-) 가중
    liquidity: 높을수록 좋음
    """
    need = [cols["momentum"], cols["volatility"], cols["liquidity"]]
    for c in need:
        if c not in cs.columns:
            raise ValueError(f"필요 컬럼 누락: {c}")

    # 결측 제거(필요 컬럼)
    cs = cs.dropna(subset=need).copy()

    cs["z_mom"] = _zscore(cs[cols["momentum"]])
    cs["z_vol"] = _zscore(cs[cols["volatility"]])     # 낮을수록 좋게 만들기 위해 가중에서 - 부호
    cs["z_liq"] = _zscore(cs[cols["liquidity"]])

    # 가중합 (필요시 가중치 조정)
    w_mom, w_vol, w_liq = 0.5, 0.3, 0.2
    cs["score"] = w_mom * cs["z_mom"] + (-w_vol) * cs["z_vol"] + w_liq * cs["z_liq"]
    return cs


def _pick_top_n(cs: pd.DataFrame, n: int) -> pd.DataFrame:
    out = cs.sort_values("score", ascending=False).head(n).copy()
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def _assign_weights(df_top: pd.DataFrame, method: str = "equal", cap: float = 0.05) -> pd.DataFrame:
    """
    method
      - "equal": 동일비중
      - "inv_vol": 최근 60일 변동성의 역수 비중 (cap 적용)
    """
    out = df_top.copy()

    if method == "equal":
        out["weight"] = 1.0 / len(out)
        return out

    if method == "inv_vol":
        col = "volatility_60d" if "volatility_60d" in out.columns else "volatility_20d"
        if col not in out.columns:
            print("⚠️ 변동성 컬럼이 없어 equal로 대체합니다.")
            out["weight"] = 1.0 / len(out)
            return out

        vol = pd.to_numeric(out[col], errors="coerce")
        inv = 1.0 / vol.replace(0, np.nan)
        inv = inv.fillna(inv.median())  # 0/NaN 안정화
        w = inv / inv.sum()

        # cap 적용
        if cap is not None and cap > 0:
            w = w.clip(upper=cap)
            w = w / w.sum()  # 재정규화

        out["weight"] = w.values
        return out

    # unknown → equal
    print(f"⚠️ 알 수 없는 WEIGHTING_METHOD={method}, equal로 대체")
    out["weight"] = 1.0 / len(out)
    return out


def main():
    inputs = _prep_inputs()
    df_feat = _load_features(inputs.features_path)
    print(f"features 로드: {df_feat.shape}, date 범위: {df_feat['date'].min()} ~ {df_feat['date'].max()}")

    # 최신 단면
    cs = _latest_cross_section(df_feat)
    cs = _merge_symbol_meta(cs, inputs.symbols_path)

    # 유동성 컷
    cs = _apply_liquidity_filter(cs, liquidity_col=FACTOR_COLS["liquidity"], cutoff_pct=LIQUIDITY_CUTOFF_PCT)

    # 스코어 계산
    cs = _compute_score(cs, FACTOR_COLS)

    # TOP-N
    df_top = _pick_top_n(cs, TOP_N)

    # 가중치
    df_port = _assign_weights(df_top, method=WEIGHTING_METHOD, cap=MAX_WEIGHT_CAP)

    # 정리하여 저장
    cols_out = ["date", "symbol", "name", "market", "score", "rank", "weight"]
    # 필요한 팩터도 같이 저장하고 싶으면 아래에 추가
    for c in [FACTOR_COLS["momentum"], FACTOR_COLS["volatility"], FACTOR_COLS["liquidity"], "close", "volume", "value"]:
        if c in df_port.columns and c not in cols_out:
            cols_out.append(c)

    df_out = df_port[[c for c in cols_out if c in df_port.columns]].reset_index(drop=True)

    outdir = Path("data/proc/selection")
    outdir.mkdir(parents=True, exist_ok=True)
    outfile_parquet = outdir / f"{TODAY}_top{TOP_N}.parquet"
    outfile_csv = outdir / f"{TODAY}_top{TOP_N}.csv"

    df_out.to_parquet(outfile_parquet, index=False)
    df_out.to_csv(outfile_csv, index=False, encoding="utf-8-sig")

    print(f"✅ TOP{TOP_N} 저장 완료:")
    print(f" - {outfile_parquet}")
    print(f" - {outfile_csv}")
    print("\n상위 10개 미리보기:")
    print(df_out.head(10))
    print("\n요약:")
    print(df_out.describe(include='all'))


if __name__ == "__main__":
    main()
