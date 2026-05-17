import re
import pandas as pd
from rapidfuzz import process, fuzz


def normalize(name: str) -> str:
    """공백·법인표기·특수문자 제거 후 대문자화"""
    if not isinstance(name, str):
        return ""
    name = re.sub(r"\s", "", name)
    name = re.sub(r"\(주\)|㈜|\(유\)", "", name)
    name = re.sub(r"[^\w]", "", name)
    return name.upper()


def match_ticker(df: pd.DataFrame, df_stocks: pd.DataFrame) -> pd.DataFrame:
    """정규화 exact match → fuzzy match 순으로 TICKER + STOCK_NAME 보강"""
    df_stocks = df_stocks.copy()
    df_stocks["NORM"] = df_stocks["STOCK_NAME"].map(normalize)
    norm_to_ticker = dict(zip(df_stocks["NORM"], df_stocks["TICKER"]))
    norm_to_name   = dict(zip(df_stocks["NORM"], df_stocks["STOCK_NAME"]))
    norm_keys = list(norm_to_ticker.keys())

    def lookup(row):
        if pd.notna(row.get("TICKER")):
            return row["TICKER"], row["STOCK_NAME"]

        norm = normalize(row["STOCK_NAME"])

        if norm in norm_to_ticker:
            return norm_to_ticker[norm], norm_to_name[norm]

        result = process.extractOne(norm, norm_keys, scorer=fuzz.ratio, score_cutoff=80)
        if result:
            return norm_to_ticker[result[0]], norm_to_name[result[0]]

        return None, row["STOCK_NAME"]

    matched = df.apply(lookup, axis=1, result_type="expand")
    df["TICKER"]     = matched[0]
    df["STOCK_NAME"] = matched[1]
    return df
