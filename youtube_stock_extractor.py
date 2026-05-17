"""
YouTube 영상 링크 → 자막(STT) → 추천주 + 목표가 추출

실행명령예시 >> python youtube_stock_extractor.py dJ7q2e9qspE
"""

import re
import os
import json
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import insert
import anthropic
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

load_dotenv()
DB_URL = os.environ["DB_URL"]

def get_transcript(video_id: str) -> tuple[str, list[dict]]:
    """
    YouTube 자막 가져오기
    Returns: (전체 텍스트, 세그먼트 리스트)
    """
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        # 수동자막 → 자동자막 → 영어번역 순으로 시도
        try:
            transcript = transcript_list.find_manually_created_transcript(["ko"])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(["ko"])
            except Exception:
                transcript = transcript_list.find_transcript(["en"]).translate("ko")

        # 세그먼트 변환
        fetched = transcript.fetch()
        segments = [{"text": seg.text, "start": int(seg.start)} for seg in fetched]
        full_text = " ".join(seg["text"] for seg in segments)
        
        return full_text, segments

    except (NoTranscriptFound, TranscriptsDisabled):
        # 검증 후 시도 예정 (자막 실패 시, 직접 음성을 받아서 텍스트로 변환)
        # return _get_transcript_via_whisper(video_id)
        return "N", []


def _get_transcript_via_whisper(video_id: str) -> str:
    """자막이 없을 때 yt-dlp + Whisper로 STT (fallback)"""
    try:
        import yt_dlp
        import whisper
        import tempfile, os

        url = f"https://www.youtube.com/watch?v={video_id}"
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "audio.mp3")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": audio_path,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language="ko")
            return result["text"]

    except ImportError:
        raise RuntimeError(
            "자막이 없습니다. Whisper fallback을 쓰려면 다음을 설치하세요:\n"
            "  uv add yt-dlp openai-whisper\n"
            "  그리고 ffmpeg도 PATH에 있어야 합니다."
        )


def _format_transcript_with_timestamps(segments: list[dict]) -> str:
    """Claude에 넘길 타임스탬프 포함 텍스트 생성. 매 30초마다 시간 표시."""
    lines = []
    last_marked = -30
    for seg in segments:
        if seg["start"] - last_marked >= 30:
            lines.append(f"\n[{seg['start']}s]")
            last_marked = seg["start"]
        lines.append(seg["text"])
    return " ".join(lines)


def extract_stocks_from_transcript(transcript: str, segments: list[dict], video_id: str) -> pd.DataFrame:
    """Claude API로 추천주 + 목표가 + 구간 링크 추출 → DataFrame 반환"""
    client = anthropic.Anthropic()

    formatted = _format_transcript_with_timestamps(segments) if segments else transcript

    system_prompt = """주어진 텍스트를 분석하여 언급된 모든 추천 종목과 목표가를 JSON 배열로 반환하세요.
텍스트에는 [숫자s] 형식의 타임스탬프가 포함되어 있습니다. 각 종목 설명이 시작되는 타임스탬프를 찾아주세요.

반환 형식 (JSON 배열만):
[
  {
    "EXPERT_NAME": "추천자 (있으면)",
    "STOCK_NAME": "종목명",
    "TICKER": "종목코드 (있으면, 없으면 null)",
    "OPINION": "매수/상향조정/하향조정 (있으면)",
    "TARGET_PRICE": 목표가_숫자 (원 단위, 없으면 null),
    "CURRENT_PRICE": 현재가_숫자 (언급된 경우, 없으면 null),
    "SELLOFF_PRICE": 손절가_숫자 (원 단위, 없으면 null),
    "START_SECONDS": 해당_종목_설명_시작_타임스탬프_숫자 (없으면 null),
    "REASON": "추천 이유 요약 (있으면)"
  }
]

- 목표가가 '만원' 단위면 10000 곱해서 원 단위로 변환 (예: 15만원 → 150000)
- start_seconds는 [숫자s] 에서 숫자만 추출한 정수
- 종목이 전혀 없으면 빈 배열 [] 반환
- JSON 외 다른 텍스트는 절대 출력하지 마세요"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"다음 방송 텍스트에서 추천 종목과 목표가를 추출해주세요:\n\n{formatted[:10000]}",
            }
        ],
    )

    raw = message.content[0].text.strip()
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    stocks = json.loads(json_match.group() if json_match else raw)

    df = pd.DataFrame(stocks)
    df["YT_VIDEOID"] = video_id
    df["TIMESTAMPED_LINK"] = df["START_SECONDS"].apply(
        lambda t: f"https://www.youtube.com/watch?v={video_id}&t={int(t)}" if pd.notna(t) else None
    )

    return df


def analyze_youtube_video(video_id: str) -> pd.DataFrame:
    """YouTube URL → 추천주 + 목표가 + 구간 링크 분석 (메인 함수)"""
    print(f"[1/3] 자막 추출 중... (video_id: {video_id})")
    transcript, segments = get_transcript(video_id)
    print(f"[2/3] 자막 추출 완료 ({len(transcript)}자)")

    print("[3/3] 추천주 + 목표가 분석 중...")
    df = extract_stocks_from_transcript(transcript, segments, video_id)

    return df

if __name__ == "__main__":
    import sys

    video_id = sys.argv[1]
    df = analyze_youtube_video(video_id)

    # 결과 출력
    print(f"\n{'='*60}")
    print(f"영상: {video_id}")
    print(f"{'='*60}")
    if df.empty:
        print("추천 종목을 찾지 못했습니다.")
    else:
        print(df)

    engine = create_engine(DB_URL)

    # master_stocks 조인으로 TICKER 보강 (Claude가 못 잡은 경우 대비)
    df_stocks = pd.read_sql("SELECT TICKER, STOCK_NAME FROM master_stocks", engine)
    df = df.merge(df_stocks, on="STOCK_NAME", how="left", suffixes=("", "_master"))
    df["TICKER"] = df["TICKER"].fillna(df["TICKER_master"])
    df.drop(columns=["TICKER_master"], inplace=True)

    # DB INSERT IGNORE
    def insert_ignore(table, conn, keys, data_iter):
        stmt = insert(table.table).prefix_with("IGNORE")
        conn.execute(stmt, [dict(zip(keys, row)) for row in data_iter])

    db_cols = ["YT_VIDEOID", "EXPERT_NAME", "TICKER", "STOCK_NAME", "OPINION",
               "CURRENT_PRICE", "TARGET_PRICE", "SELLOFF_PRICE", "REASON", "TIMESTAMPED_LINK"]
    df[db_cols].to_sql("extracted_stocks", engine, if_exists="append", index=False, method=insert_ignore)