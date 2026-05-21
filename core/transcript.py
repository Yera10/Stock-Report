import os
import time
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig

PROXY_STATE_FILE = Path(__file__).parent.parent / ".proxy_state"


def _load_proxy_urls() -> list[str]:
    return [url for i in range(1, 11) if (url := os.environ.get(f"PROXY_URL_{i}"))]


def _get_last_index() -> int:
    if PROXY_STATE_FILE.exists():
        return int(PROXY_STATE_FILE.read_text().strip())
    return 0

def _save_index(idx: int):
    PROXY_STATE_FILE.write_text(str(idx))


def _build_youtube_api(proxy_url: str | None) -> YouTubeTranscriptApi:
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
        )

def _fetch_transcript(api: YouTubeTranscriptApi, video_id: str) -> tuple[str, list[dict]]:
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
    return " ".join(seg["text"] for seg in segments), segments


def get_transcript(video_id: str) -> tuple[str, list[dict]]:
    """YouTube 자막 가져오기."""
    proxy_urls = _load_proxy_urls()
    start = _get_last_index()
    for i in range(len(proxy_urls)):
        idx = (start + i) % len(proxy_urls)
        try:
            time.sleep(1)
            result = _fetch_transcript(_build_youtube_api(proxy_urls[idx]), video_id)
            _save_index(idx)
            return result
        except Exception as e:
            print(f"  프록시 {idx + 1} 실패 ({e.__class__.__name__})")
    raise RuntimeError("모든 프록시 실패")


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
