"""
scripts/run_collect_daily.py

심볼 마스터를 기반으로 최근 1년치 전 종목 일봉 수집 후 저장.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from libs.kis_auth import get_or_load_access_token
from libs.daily_candle import get_daily_candle


def main():
    today = datetime.now().strftime("%Y%m%d")
    access_token = get_or_load_access_token(env="real")

    # 1) 심볼 마스터 로드
    master_path = Path(f"data/raw/kis/symbol_master/{today}.parquet")
    if not master_path.exists():
        raise FileNotFoundError(f"심볼 마스터 파일 없음: {master_path}")
    df_symbols = pd.read_parquet(master_path)
    symbols = df_symbols["symbol"].tolist()
    print(f"총 {len(symbols)} 종목 대상 수집")

    # 2) 조회 기간: 최근 1년
    end_date = today
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    # 3) 수집 루프
    all_rows = []
    for i, sym in enumerate(symbols, 1):
        try:
            df = get_daily_candle(sym, start_date, end_date, access_token, env="real")
            if not df.empty:
                all_rows.append(df)
        except Exception as e:
            print(f"⚠️ {sym} 실패:", e)

        if i % 50 == 0:
            print(f"진행률: {i}/{len(symbols)}")
            time.sleep(1)

    if not all_rows:
        print("⚠️ 수집된 데이터 없음")
        return

    df_all = pd.concat(all_rows, ignore_index=True)

    # 4) 저장
    outdir = Path("data/raw/kis/daily")
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / f"{today}.parquet"
    df_all.to_parquet(outfile, index=False)
    print("✅ 저장 완료:", outfile, "행 개수:", len(df_all))


if __name__ == "__main__":
    main()
