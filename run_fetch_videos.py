# 신규 영상 수집

import html
import os
import requests
import pandas as pd
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from sqlalchemy import text
from core.db import get_engine

load_dotenv()

KST = ZoneInfo("Asia/Seoul")
API_KEY = os.environ["YOUTUBE_API_KEY"]


def fetch_new_videos(channel_id: str, published_after: str) -> list[dict]:
    params = {
        "key": API_KEY,
        "channelId": channel_id,
        "part": "snippet",
        "order": "date",
        "publishedAfter": published_after,
        "maxResults": 50,
        "type": "video",
    }
    resp = requests.get("https://www.googleapis.com/youtube/v3/search", params=params).json()

    videos = []
    for item in resp.get("items", []):
        video_id = item["id"]["videoId"]
        videos.append({
            "CHANNEL_ID":    item["snippet"]["channelId"],
            "CHANNEL_TITLE": item["snippet"]["channelTitle"],
            "YT_VIDEOID":    video_id,
            "LINK":          f"https://www.youtube.com/watch?v={video_id}",
            "TITLE":         html.unescape(item["snippet"]["title"]),
            "PUBLISHED":     pd.to_datetime(item["snippet"]["publishedAt"])
                             .tz_convert(KST).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return videos


if __name__ == "__main__":
    engine = get_engine()
    df_channels = pd.read_sql("SELECT CHANNEL_ID FROM MASTER_youtuber", engine)
    since = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=1)).floor("h").strftime("%Y-%m-%dT%H:%M:%SZ")

    for channel_id in df_channels["CHANNEL_ID"]:
        videos = fetch_new_videos(channel_id, since)
        if videos:
            with engine.connect() as conn:
                conn.execute(
                    text("INSERT IGNORE INTO TRACKING_VIDEOS "
                        "(CHANNEL_ID, CHANNEL_TITLE, YT_VIDEOID, LINK, TITLE, PUBLISHED) "
                        "VALUES (:CHANNEL_ID, :CHANNEL_TITLE, :YT_VIDEOID, :LINK, :TITLE, :PUBLISHED)"),
                    videos,
                )
                conn.commit()
        print(f"{channel_id}: {len(videos)}개 저장")
