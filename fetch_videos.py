import pandas as pd
import requests
from sqlalchemy import create_engine, text
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
from pprint import pprint
import html

# DB CONNECT
print(f"{'DB CONNECT':=^50}")
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
engine = create_engine("mariadb+mariadbconnector://root:1022@localhost:3306/LITTLEB")
df = pd.read_sql("SELECT * FROM TRACKING_YOUTUBER", engine)
print(df)

kst = ZoneInfo("Asia/Seoul")
the_time = (pd.Timestamp.now(tz='UTC') - pd.Timedelta(hours=1)).floor('h').strftime('%Y-%m-%dT%H:%M:%SZ')

# NEW VIDEOS
print(f"{'NEW VIDEOS':=^50}")
with engine.connect() as conn:
    for chid in df.CHANNEL_ID:
        # API 요청
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "key": API_KEY,
            "channelId": chid,
            "part": "snippet",
            "order": "date",
            "publishedAfter": the_time,
            "maxResults": 50,
            "type": "video",
        }
        resp = requests.get(url, params=params).json()
        # pprint(resp)

        # TO Dict
        videos = []
        for item in resp.get("items", []):
            video_id = item["id"]["videoId"]
            videos.append({
                'CHANNEL_ID': item["snippet"]['channelId'],
                "CHANNEL_TITLE":   item["snippet"]["channelTitle"],
                "YT_VIDEOID": video_id,
                "LINK":       f"https://www.youtube.com/watch?v={video_id}",
                "TITLE":     html.unescape(item["snippet"]["title"]),
                "PUBLISHED": pd.to_datetime(item["snippet"]["publishedAt"]).tz_convert(kst).strftime('%Y-%m-%d %H:%M:%S')
            })
        pprint(videos)

        # DB INSERT
        if not videos:
            continue
        conn.execute(
            text("INSERT IGNORE INTO TRACKING_VIDEOS (CHANNEL_ID, CHANNEL_TITLE, YT_VIDEOID, LINK, TITLE, PUBLISHED) VALUES (:CHANNEL_ID, :CHANNEL_TITLE, :YT_VIDEOID, :LINK, :TITLE, :PUBLISHED)"),
            videos
        )
    conn.commit()