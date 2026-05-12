import pandas as pd
import feedparser
from sqlalchemy import create_engine, text
from zoneinfo import ZoneInfo

# DB CONNECT
print(f"{'DB CONNECT':=^50}")
engine = create_engine("mariadb+mariadbconnector://root:1022@localhost:3306/LITTLEB")
df = pd.read_sql("SELECT * FROM TRACKING_YOUTUBER", engine)
print(df)

kst = ZoneInfo("Asia/Seoul")
the_time = (pd.Timestamp.now(tz=kst).tz_localize(None) - pd.Timedelta(hours=1)).floor('h')
# NEW VIDEOS
print(f"{'NEW VIDEOS':=^50}")
with engine.connect() as conn:
    for chid in df.CHANNEL_ID:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={chid}"
        feed = feedparser.parse(rss_url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        feed_df = pd.DataFrame(feed.entries)[['author', 'yt_videoid', 'link', 'title', 'published', 'updated']]

        # 시간 변환 및 필터링
        for col in ['published', 'updated']:
            feed_df[col] = pd.to_datetime(feed_df[col], utc=True).dt.tz_convert(kst).dt.tz_localize(None)
        feed_df = feed_df[feed_df['published'] >= the_time]
        feed_df['CHANNEL_ID'] = chid
        print(feed_df)

        # DB INSERT
        if feed_df.empty:
            continue
        conn.execute(
            text("INSERT IGNORE INTO TRACKING_VIDEOS (CHANNEL_ID, AUTHOR, YT_VIDEOID, LINK, TITLE, PUBLISHED, UPDATED) VALUES (:CHANNEL_ID, :author, :yt_videoid, :link, :title, :published, :updated)"),
            feed_df.to_dict(orient='records')
        )
    conn.commit()