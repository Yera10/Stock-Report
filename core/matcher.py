import re
import pandas as pd
from rapidfuzz import process, fuzz


def normalize(name: str) -> str:
    """문자열 정규화함수 : 공백·법인표기·특수문자 제거 후 대문자화"""
    if not isinstance(name, str):
        return ""
    name = re.sub(r"\s", "", name)
    name = re.sub(r"\(주\)|㈜|\(유\)", "", name)
    name = re.sub(r"[^\w]", "", name)
    return name.upper()


def match_ticker(stock_names: list[str], master_stocks: pd.DataFrame) -> list[tuple[str | None, str]]:
    """추출한 종목명에 맞는 TICKER 매칭하는 함수"""
    norm_to_ticker = dict(zip(master_stocks["STOCK_NAME_NORM"], master_stocks["TICKER"]))
    norm_to_name   = dict(zip(master_stocks["STOCK_NAME_NORM"], master_stocks["STOCK_NAME"]))
    norm_keys = list(norm_to_ticker.keys())

    # TICKER 매칭
    results = []
    for name in stock_names:
        norm = normalize(name)

        # 정규화 매칭
        if norm in norm_to_ticker:
            results.append((norm_to_ticker[norm], norm_to_name[norm]))
            continue
        
        # 퍼지 매칭
        hit = process.extractOne(norm, norm_keys, scorer=fuzz.ratio, score_cutoff=80)
        if hit:
            results.append((norm_to_ticker[hit[0]], norm_to_name[hit[0]]))
        else:
            results.append((None, name))

    return results
