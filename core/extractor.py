import re
import json
import pandas as pd
import anthropic
from core.transcript import format_with_timestamps

SYSTEM_PROMPT = """주어진 텍스트를 분석하여 언급된 모든 추천 종목과 목표가를 JSON 배열로 반환하세요.
텍스트에는 [숫자s] 형식의 타임스탬프가 포함되어 있습니다. 각 종목 설명이 시작되는 타임스탬프를 찾아주세요.

반환 형식 (JSON 배열만):
[
  {
    "EXPERT_NAME": "추천자 (있으면)",
    "STOCK_NAME_EXTRACTED": "종목명",
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
- START_SECONDS는 [숫자s] 에서 숫자만 추출한 정수
- TARGET_PRICE는 출연 전문가 본인이 직접 제시하는 목표가만 추출. "증권사가 목표가를 얼마로 제시했다", "누가 얼마 목표가를 잡았다" 등 타인/기관의 목표가를 인용하는 경우는 null로 처리
- 종목이 전혀 없으면 빈 배열 [] 반환
- JSON 외 다른 텍스트는 절대 출력하지 마세요"""


def extract_stocks(transcript: str, segments: list[dict], video_id: str) -> pd.DataFrame:
    """자막 텍스트 → 추천주 DataFrame (Claude API)"""
    formatted = format_with_timestamps(segments) if segments else transcript

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"다음 방송 텍스트에서 추천 종목과 목표가를 추출해주세요:\n\n{formatted[:10000]}"}],
    )

    raw = message.content[0].text.strip()
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    
    stocks = json.loads(json_match.group() if json_match else raw)

    df = pd.DataFrame(stocks)
    if df.empty:
        return df
    df["YT_VIDEOID"] = video_id
    df["TIMESTAMPED_LINK"] = df["START_SECONDS"].apply(
        lambda t: f"https://www.youtube.com/watch?v={video_id}&t={int(t)}" if pd.notna(t) else None
    )
    return df
