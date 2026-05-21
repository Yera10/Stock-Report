"""
YouTube 영상 → 추천주 + 목표가 추출 → DB 저장
실행: python run_extract_stocks.py
"""

import pandas as pd
from sqlalchemy import text
from dotenv import load_dotenv
from core.db import get_engine, insert_ignore
from core.transcript import get_transcript
from youtube_transcript_api._errors import VideoUnplayable
from core.extractor import extract_stocks
from core.matcher import match_ticker

load_dotenv()

DB_COLS = ["YT_VIDEOID", "EXPERT_NAME", "TICKER", "STOCK_NAME_EXTRACTED", "STOCK_NAME", "OPINION",
           "CURRENT_PRICE", "TARGET_PRICE", "SELLOFF_PRICE", "REASON", "TIMESTAMPED_LINK"]


if __name__ == "__main__":
    engine = get_engine()

    videos = pd.read_sql(
        "SELECT YT_VIDEOID FROM tracking_videos WHERE EXTRACTED = 0 ORDER BY PUBLISHED DESC LIMIT 15",
        engine
    )

    if videos.empty:
        print("처리할 영상 없음")
        exit()

    master_stocks = pd.read_sql("SELECT TICKER, STOCK_NAME, STOCK_NAME_NORM FROM master_stocks", engine)

    for i, video_id in enumerate(videos["YT_VIDEOID"], 1):
        print(f"\n[{i}/{len(videos)}] {video_id}")

        try:
            print(f"  [{video_id}] 자막 추출 중...", end="\r")
            transcript, segments = get_transcript(video_id)
            print(f"  [{video_id}] 자막 추출 완료 ({len(transcript)}자)")

            print("  Claude 분석 중...")
            df = extract_stocks(transcript, segments, video_id)

            if df.empty:
                print("  추천 종목 없음")
            else:
                # TICKER 보강
                mask = df["TICKER"].isna()
                if mask.any():
                    matched = match_ticker(df.loc[mask, "STOCK_NAME_EXTRACTED"].tolist(), master_stocks)
                    tickers, normed_names = zip(*matched)
                    df.loc[mask, "TICKER"] = tickers
                    df.loc[mask, "STOCK_NAME"] = normed_names

                df[DB_COLS].to_sql("extracted_stocks", engine, if_exists="append", index=False, method=insert_ignore)
                print(f"  {len(df)}개 종목 저장")

            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE tracking_videos SET EXTRACTED = 1 WHERE YT_VIDEOID = :video_id"),
                    {"video_id": video_id}
                )

        except VideoUnplayable:
            print("  재생 불가 영상, 스킵")
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE tracking_videos SET EXTRACTED = 1 WHERE YT_VIDEOID = :video_id"),
                    {"video_id": video_id}
                )
        except Exception as e:
            print(f"  실패: {e.__class__.__name__}: {e}")
