"""
scripts/run_score_quant.py

유니버스 필터(지수편입 or 시총 상위) → 섹터키 생성(sector→industry→market→symbol) →
섹터별 Top K(기본 5) → 전체 재정렬 후 Top 50 → 가중치(inv-vol × liq)
+ KONEX 제외 옵션
+ 팩터 익스포저 진단 출력

입력:
  data/proc/features/{YYYYMMDD}.parquet
출력:
  data/proc/selection/{YYYYMMDD}_top50.parquet
  data/proc/selection/{YYYYMMDD}_top50.csv
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ==== 설정 ====
TOP_N = 50
SECTOR_TOP_K = 5      # 섹터별 사전 선별 개수
SECTOR_CAP = 10       # (옵션) 최종 섹터 캡을 유지하고 싶으면 사용, 아니면 상향 조절/미사용
LIQUIDITY_CUTOFF_PCT = 0.20
WEIGHTING_METHOD = "inv_vol_liq"  # "equal" | "inv_vol" | "inv_vol_liq"
MAX_WEIGHT_CAP = 0.05
EXCLUDE_KONEX = True  # KONEX 제외
USE_INDEX_IF_AVAILABLE = True     # KOSPI200/KOSDAQ150 있으면 우선 사용
# TODAY = datetime.now().strftime("%Y%m%d")
TODAY = 20250923

# 사용할 팩터 컬럼
FACTOR_COLS = {
    "momentum": "ret_60d",          # 또는 "momentum"
    "volatility": "volatility_20d",
    "liquidity": "value_traded",
    "size": "log_mcap",
    "turnover": "turnover",
    "value_per": "per",
    "value_pbr": "pbr",
}


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _zscore(s: pd.Series) -> pd.Series:
    s = _safe_numeric(s)
    mu = s.mean()
    sigma = s.std(ddof=0)
    if not np.isfinite(sigma) or sigma == 0:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - mu) / sigma


def _build_sector_key(cs: pd.DataFrame) -> pd.Series:
    # 섹터 결측 보정: sector -> industry -> market -> symbol
    s = cs.get("sector")
    if s is None or s.isna().all():
        s = cs.get("industry")
    if s is None or s.isna().all():
        s = cs.get("market")
    if s is None:
        return cs["symbol"].astype(str)
    s = s.copy()
    mask_na = s.isna() | (s.astype(str).str.strip() == "")
    s.loc[mask_na] = cs.loc[mask_na, "symbol"].astype(str)
    return s.astype(str)


def _zscore_by_sector_with_key(df: pd.DataFrame, col: str, sector_key: pd.Series) -> pd.Series:
    tmp = df[[col]].copy()
    tmp["_sec"] = sector_key.values
    return tmp.groupby("_sec")[col].transform(_zscore)


def _load_features() -> pd.DataFrame:
    path = Path(f"data/proc/features/{TODAY}.parquet")
    if not path.exists():
        raise FileNotFoundError(f"features 파일 없음: {path}")
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def _latest_cross_section(df: pd.DataFrame) -> pd.DataFrame:
    dmax = df["date"].max()
    cs = df[df["date"] == dmax].copy()
    return cs


def _apply_universe(cs: pd.DataFrame) -> pd.DataFrame:
    """
    1순위: is_kospi200 or is_kosdaq150 (옵션)
    2순위: (없으면) 시총 상위 50%
    + 유동성 컷(하위 20% 제거)
    + KONEX 제외(옵션)
    """
    base = cs.copy()

    # 지수편입 사용
    if USE_INDEX_IF_AVAILABLE and ("is_kospi200" in base.columns or "is_kosdaq150" in base.columns):
        mask = False
        if "is_kospi200" in base.columns:
            mask = mask | base["is_kospi200"].fillna(False)
        if "is_kosdaq150" in base.columns:
            mask = mask | base["is_kosdaq150"].fillna(False)
        chosen = base[mask].copy()
        if len(chosen) >= TOP_N:
            base = chosen

    # 시총 상위 50%
    if "market_cap" in base.columns and len(base) > TOP_N:
        q = base["market_cap"].quantile(0.50)
        base = base[base["market_cap"] >= q].copy()

    # 유동성 하위 20% 컷 (value_traded는 log of 20d mean value)
    if "value_traded" in base.columns and len(base) > TOP_N:
        ql = base["value_traded"].quantile(LIQUIDITY_CUTOFF_PCT)
        base = base[base["value_traded"] >= ql].copy()

    # KONEX 제외
    if EXCLUDE_KONEX and "market" in base.columns:
        base = base[base["market"] != "KONEX"].copy()

    return base


def _compute_score(cs: pd.DataFrame) -> pd.DataFrame:
    # 최소 팩터 체크
    need = []
    for k in ["momentum", "volatility", "liquidity", "size"]:
        if FACTOR_COLS[k] in cs.columns:
            need.append(FACTOR_COLS[k])
    if len(need) < 3:
        raise ValueError(f"필요 팩터 부족. 존재: {[c for c in FACTOR_COLS.values() if c in cs.columns]}")

    # 섹터 키 생성
    sector_key = _build_sector_key(cs)

    # 섹터 중립 z-score
    z = {}
    if FACTOR_COLS["momentum"] in cs.columns:
        z["mom"] = _zscore_by_sector_with_key(cs, FACTOR_COLS["momentum"], sector_key)
    if FACTOR_COLS["liquidity"] in cs.columns:
        z["liq"] = _zscore_by_sector_with_key(cs, FACTOR_COLS["liquidity"], sector_key)
    if FACTOR_COLS["size"] in cs.columns:
        z["size"] = _zscore_by_sector_with_key(cs, FACTOR_COLS["size"], sector_key)
    if FACTOR_COLS["volatility"] in cs.columns:
        z["lvol"] = -_zscore_by_sector_with_key(cs, FACTOR_COLS["volatility"], sector_key)
    if FACTOR_COLS.get("value_per") in cs.columns:
        z["val_per"] = -_zscore_by_sector_with_key(cs, FACTOR_COLS["value_per"], sector_key)
    if FACTOR_COLS.get("value_pbr") in cs.columns:
        z["val_pbr"] = -_zscore_by_sector_with_key(cs, FACTOR_COLS["value_pbr"], sector_key)

    zdf = pd.DataFrame(z, index=cs.index).fillna(0.0)

    # 가중치
    weights = {"mom": 0.30, "lvol": 0.25, "liq": 0.20, "size": 0.15, "val_per": 0.05, "val_pbr": 0.05}
    use_keys = [k for k in weights.keys() if k in zdf.columns]
    w_sum = sum(weights[k] for k in use_keys)
    for k in use_keys:
        zdf[k] = zdf[k] * (weights[k] / w_sum)

    cs = cs.copy()
    cs["score"] = zdf[use_keys].sum(axis=1)
    cs["sector_key"] = sector_key.values
    return cs


def _sector_top_k(cs: pd.DataFrame, k: int, sector_col: str = "sector_key") -> pd.DataFrame:
    """섹터별로 score 상위 k개 선별."""
    if sector_col not in cs.columns:
        cs["sector_key"] = _build_sector_key(cs)
        sector_col = "sector_key"
    # 각 섹터 내 정렬 후 head(k)
    out = (
        cs.sort_values(["sector_key", "score"], ascending=[True, False])
          .groupby(sector_col, group_keys=False)
          .head(k)
          .copy()
    )
    return out


def _final_top_n(after_sector_pick: pd.DataFrame, n: int) -> pd.DataFrame:
    """섹터별 선별 후 전체 재정렬 → 상위 n개. 부족하면 전체 후보에서 추가 보충."""
    # 1) 섹터별 top-k 묶음을 전체 정렬
    ranked = after_sector_pick.sort_values("score", ascending=False).copy()

    # 2) 상위 n컷
    if len(ranked) >= n:
        out = ranked.head(n).copy()
    else:
        # 보충: 원본 풀에서 빠진 것 중 상위 추가
        need = n - len(ranked)
        # 전체 후보 풀은 섹터 선별 이전 전체 (여기선 after_sector_pick의 원본이 없으므로 컬럼 보유용)
        # 함수 호출부에서 원본 scored를 전달해 보충
        raise RuntimeError("internal: _final_top_n는 scored 원본을 함께 사용하세요.")
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def _assign_weights(df_top: pd.DataFrame) -> pd.DataFrame:
    out = df_top.copy()

    if WEIGHTING_METHOD == "equal":
        out["weight"] = 1.0 / len(out)
        return out

    # 변동성 열
    vol_col = "volatility_60d" if "volatility_60d" in out.columns else "volatility_20d"
    vol = _safe_numeric(out.get(vol_col, np.nan)).replace(0, np.nan)

    if WEIGHTING_METHOD in ["inv_vol", "inv_vol_liq"]:
        inv = 1.0 / vol
        inv = inv.fillna(inv.median())

        if WEIGHTING_METHOD == "inv_vol":
            raw = inv
        else:
            liq = _safe_numeric(out.get("value_traded", np.nan))
            if np.isfinite(liq.std(ddof=0)) and liq.std(ddof=0) > 0:
                liq_z = (liq - liq.mean()) / liq.std(ddof=0)
                liq_scale = (liq_z - np.nanmin(liq_z))
                if np.nanmax(liq_scale) > 0:
                    liq_scale = liq_scale / np.nanmax(liq_scale)
            else:
                liq_scale = pd.Series(0.0, index=liq.index)
            raw = inv * (1 + liq_scale)

        w = raw / raw.sum()
        if MAX_WEIGHT_CAP:
            w = w.clip(upper=MAX_WEIGHT_CAP)
            w = w / w.sum()
        out["weight"] = w.values
        return out

    out["weight"] = 1.0 / len(out)
    return out


def _exposure_summary(df: pd.DataFrame) -> pd.DataFrame:
    """선정 종목의 팩터 익스포저(z-score) 요약"""
    rows = []
    def _z(s):
        std = s.std(ddof=0)
        return (s - s.mean()) / (std if std else 1)

    if "ret_60d" in df.columns:        rows.append(("mom",   float(_z(df["ret_60d"]).mean())))
    if "volatility_20d" in df.columns: rows.append(("lvol",  float(_z(-df["volatility_20d"]).mean())))
    if "value_traded" in df.columns:   rows.append(("liq",   float(_z(df["value_traded"]).mean())))
    if "log_mcap" in df.columns:       rows.append(("size",  float(_z(df["log_mcap"]).mean())))
    if "per" in df.columns:            rows.append(("val_per", float(_z(-df["per"]).mean())))
    if "pbr" in df.columns:            rows.append(("val_pbr", float(_z(-df["pbr"]).mean())))
    return pd.DataFrame(rows, columns=["factor", "mean_z"])


def main():
    df_feat = _load_features()
    print(f"features 로드: {df_feat.shape}, date 범위: {df_feat['date'].min()} ~ {df_feat['date'].max()}")

    # 최신 단면
    cs = _latest_cross_section(df_feat)

    # 진단
    if "sector" in cs.columns:
        na_count = cs["sector"].isna().sum()
        print("\n=== 섹터 정보 진단 ===")
        print(f"총 종목 수: {len(cs)}")
        print(f"sector 결측 수: {na_count} / {len(cs)} ({na_count/len(cs):.2%})")
        print(f"sector 고유값 개수: {cs['sector'].nunique(dropna=True)}")
        print("상위 10개 sector:\n", cs["sector"].value_counts().head(10))
    if "industry" in cs.columns:
        print("\n=== industry 정보 진단 ===")
        print(f"industry 고유값 개수: {cs['industry'].nunique(dropna=True)}")
        print("상위 10개 industry:\n", cs["industry"].value_counts().head(10))
    if "market" in cs.columns:
        print("\n=== market 정보 진단 ===")
        print(cs["market"].value_counts())

    # 유니버스 필터
    base = _apply_universe(cs)
    print(f"\n유니버스 크기: {len(base)}")

    # 스코어
    scored = _compute_score(base)
    if "sector_key" in scored.columns:
        print("\n섹터키 상위 분포:")
        print(scored["sector_key"].value_counts().head(10))

    # 섹터별 Top-K 선별
    sector_picks = _sector_top_k(scored, k=SECTOR_TOP_K, sector_col="sector_key")

    # 전체 재정렬 후 Top-N (부족분 보충 포함)
    # 1) 우선 섹터별 picks에서 상위 정렬
    ranked = sector_picks.sort_values("score", ascending=False).copy()

    # 2) 부족하면 scored 전체에서 보충
    if len(ranked) < TOP_N:
        need = TOP_N - len(ranked)
        remain = scored.loc[~scored["symbol"].isin(ranked["symbol"])].sort_values("score", ascending=False)
        ranked = pd.concat([ranked, remain.head(need)], ignore_index=True)

    # (옵션) 최종 섹터 캡도 적용하고 싶으면 아래 블록 주석 해제
    # ranked = ranked.sort_values("score", ascending=False).copy()
    # if "sector_key" not in ranked.columns:
    #     ranked["sector_key"] = _build_sector_key(ranked)
    # final_idx = []
    # counts = {}
    # for idx, row in ranked.iterrows():
    #     sec = str(row["sector_key"])
    #     counts.setdefault(sec, 0)
    #     if counts[sec] < SECTOR_CAP:
        #         final_idx.append(idx)
        #         counts[sec] += 1
        #     if len(final_idx) >= TOP_N:
        #         break
    # ranked = ranked.loc[final_idx].copy()

    # Top-N 확정 및 랭크
    port = ranked.sort_values("score", ascending=False).head(TOP_N).copy()
    port["rank"] = np.arange(1, len(port) + 1)

    # 가중치
    port = _assign_weights(port)

    # 결과 정리/저장
    cols_out = ["date", "symbol", "name", "market", "sector", "industry",
                "score", "rank", "weight", "close", "volume", "value",
                "log_mcap", "turnover", "ret_60d", "volatility_20d",
                "value_traded", "per", "pbr", "sector_key"]
    df_out = port[[c for c in cols_out if c in port.columns]].reset_index(drop=True)

    outdir = Path("data/proc/selection")
    outdir.mkdir(parents=True, exist_ok=True)
    p_path = outdir / f"{TODAY}_top{TOP_N}.parquet"
    c_path = outdir / f"{TODAY}_top{TOP_N}.csv"
    df_out.to_parquet(p_path, index=False)
    df_out.to_csv(c_path, index=False, encoding="utf-8-sig")

    print(f"\n✅ 저장 완료:\n - {p_path}\n - {c_path}")
    print("\n상위 10개 미리보기:")
    print(df_out.head(10))

    if "sector_key" in df_out.columns:
        print("\n섹터키 분포(선정 종목):")
        print(df_out["sector_key"].value_counts().head(10))
    if "market" in df_out.columns:
        print("\n시장 분포(선정 종목):")
        print(df_out["market"].value_counts())

    # 요약진단
    for col in ["value_traded", "volatility_20d", "log_mcap", "turnover"]:
        if col in df_out.columns:
            print(f"\n{col} 요약:")
            print(df_out[col].describe())

    print("\n팩터 익스포저 요약(z-score 기준):")
    print(_exposure_summary(df_out))

if __name__ == "__main__":
    main()
