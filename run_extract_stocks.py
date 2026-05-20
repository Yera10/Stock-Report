"""
YouTube 영상 → 추천주 + 목표가 추출 → DB 저장
실행: python run_extract_stocks.py <VIDEO_ID>
"""

import sys
import pandas as pd
from sqlalchemy import text
from dotenv import load_dotenv
from core.db import get_engine, insert_ignore
from core.transcript import get_transcript
from core.extractor import extract_stocks
from core.matcher import match_ticker

load_dotenv()

DB_COLS = ["YT_VIDEOID", "EXPERT_NAME", "TICKER", "STOCK_NAME_EXTRACTED", "STOCK_NAME", "OPINION",
           "CURRENT_PRICE", "TARGET_PRICE", "SELLOFF_PRICE", "REASON", "TIMESTAMPED_LINK"]


if __name__ == "__main__":
    video_id = sys.argv[1]
    engine = get_engine()

    # 자막 가져오기
    print(f"[1/3] 자막 추출 중... ({video_id})", end='\r')
    transcript, segments = get_transcript(video_id)
    print(f"[1/3] 자막 추출 완료 ({len(transcript)}자)")

    # 추천주 추출
    print("[3/3] Claude 분석 중...")
    df = extract_stocks(transcript, segments, video_id)

    if df.empty:
        print("추천 종목이 없음")
    else:
        # TICKER 보강
        master_stocks = pd.read_sql("SELECT TICKER, STOCK_NAME, STOCK_NAME_NORM FROM master_stocks", engine)
        mask = df["TICKER"].isna()
        if mask.any():
            matched = match_ticker(df.loc[mask, "STOCK_NAME_EXTRACTED"].tolist(), master_stocks)
            tickers, normed_names = zip(*matched)
            df.loc[mask, "TICKER"] = tickers
            df.loc[mask, "STOCK_NAME"] = normed_names

        print(f"\n{'='*60}")
        print(df)

        # DB INSERT
        df[DB_COLS].to_sql("extracted_stocks", engine, if_exists="append", index=False, method=insert_ignore)

    # EXTRACTED 플래그 업데이트
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE tracking_videos SET EXTRACTED = 1 WHERE YT_VIDEOID = :video_id"),
            {"video_id": video_id}
        )
    print("\nDB 저장 완료")
