# 신규 영상 수집

import html
import os
import re
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
    """유튜브 search API를 통해 영상 기본정보 수집"""
    # 영상조회
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

    # 영상 FETCH
    videos = []
    for item in resp.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        videos.append({
            "CHANNEL_ID":    snippet["channelId"],
            "CHANNEL_TITLE": snippet["channelTitle"],
            "YT_VIDEOID":    video_id,
            "LINK":          f"https://www.youtube.com/watch?v={video_id}",
            "TITLE":         html.unescape(snippet["title"]),
            "PUBLISHED":     pd.to_datetime(snippet["publishedAt"])
                             .tz_convert(KST).strftime("%Y-%m-%d %H:%M:%S"),
            "DESCRIPTION":   snippet.get("description", ""),
            "IS_LIVE":       snippet.get("liveBroadcastContent", "none"),
        })
    return videos


def fetch_video_details(video_ids: list[str]) -> dict[str, dict]:
    """유튜브 videos API로 duration/tags/categoryId 수집 (최대 50개 배치)"""
    # 영상정보 조회
    params = {
        "key": API_KEY,
        "id": ",".join(video_ids),
        "part": "contentDetails,snippet",
    }
    resp = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params).json()

    # 영상정보 파싱
    details = {}
    for item in resp.get("items", []):
        video_id = item["id"]
        snippet = item.get("snippet", {})
        content = item.get("contentDetails", {})

        raw_duration = content.get("duration", "PT0S")
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", raw_duration)
        seconds = (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) if m else 0

        details[video_id] = {
            "DURATION_SEC": seconds,
            "TAGS":         ",".join(snippet.get("tags", [])),
            "CATEGORY_ID":  snippet.get("categoryId", ""),
        }
    return details


if __name__ == "__main__":
    engine = get_engine()
    df_channels = pd.read_sql("SELECT CHANNEL_ID FROM MASTER_youtuber", engine)
    since = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=2)).floor("h").strftime("%Y-%m-%dT%H:%M:%SZ")

    for channel_id in df_channels["CHANNEL_ID"]:
        videos = fetch_new_videos(channel_id, since)
        if not videos:
            print(f"{channel_id}: 0개 저장")
            continue

        video_ids = [v["YT_VIDEOID"] for v in videos]
        details = fetch_video_details(video_ids)
        for v in videos:
            v.update(details.get(v["YT_VIDEOID"], {"DURATION_SEC": 0, "TAGS": "", "CATEGORY_ID": ""}))

        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT IGNORE INTO TRACKING_VIDEOS "
                    "(CHANNEL_ID, CHANNEL_TITLE, YT_VIDEOID, LINK, TITLE, PUBLISHED, "
                    "DESCRIPTION, IS_LIVE, DURATION_SEC, TAGS, CATEGORY_ID) "
                    "VALUES (:CHANNEL_ID, :CHANNEL_TITLE, :YT_VIDEOID, :LINK, :TITLE, :PUBLISHED, "
                    ":DESCRIPTION, :IS_LIVE, :DURATION_SEC, :TAGS, :CATEGORY_ID)"
                ),
                videos,
            )
            conn.commit()
        print(f"{channel_id}: {len(videos)}개 저장")
