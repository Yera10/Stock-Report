import os
import time
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig


def _build_api() -> YouTubeTranscriptApi:
    proxy_url = os.environ.get("PROXY_URL")
    if proxy_url:
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=proxy_url,
                https_url=proxy_url,
            )
        )
    return YouTubeTranscriptApi()


def get_transcript(video_id: str) -> tuple[str, list[dict]]:
    """YouTube 자막 가져오기."""
    time.sleep(1)  # API rate limit 방지 위해 약간의 딜레이
    api = _build_api()
    transcript_list = api.list(video_id)

    try:
        transcript = transcript_list.find_manually_created_transcript(["ko"])
    except Exception:
        try:
            transcript = transcript_list.find_generated_transcript(["ko"])
        except Exception:
            transcript = transcript_list.find_transcript(["en"]).translate("ko")

    fetched = transcript.fetch()
    segments = [{"text": seg.text, "start": int(seg.start)} for seg in fetched]
    full_text = " ".join(seg["text"] for seg in segments)
    return full_text, segments


def format_with_timestamps(segments: list[dict]) -> str:
    """매 30초마다 타임스탬프 마커를 삽입한 텍스트 생성"""
    lines = []
    last_marked = -5
    for seg in segments:
        if seg["start"] - last_marked >= 5:
            lines.append(f"\n[{seg['start']}s]")
            last_marked = seg["start"]
        lines.append(seg["text"])
    return " ".join(lines)


def _get_transcript_via_whisper(video_id: str) -> tuple[str, list[dict]]:
    """자막 없을 때 yt-dlp + Whisper로 STT (fallback)"""
    try:
        import yt_dlp
        import whisper
        import tempfile
        import os

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
            return result["text"], []

    except ImportError:
        raise RuntimeError(
            "자막이 없습니다. Whisper fallback을 쓰려면:\n"
            "  uv add yt-dlp openai-whisper\n"
            "  ffmpeg도 PATH에 있어야 합니다."
        )
