# KRX 전체 종목 리스트를 master_stocks 테이블에 갱신

import FinanceDataReader as fdr
from sqlalchemy import text
from dotenv import load_dotenv
from core.db import get_engine

load_dotenv()


if __name__ == "__main__":
    print("KRX 종목 리스트 다운로드 중...")
    df = fdr.StockListing("KRX")[["Code", "Name", "Market"]]
    df.columns = ["TICKER", "STOCK_NAME", "MARKET"]
    df = df[df["TICKER"].notna() & df["STOCK_NAME"].notna()].drop_duplicates("TICKER")
    print(f"총 {len(df)}개 종목")

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE master_stocks"))
        df.to_sql("master_stocks", conn, if_exists="append", index=False)

    print("업데이트 완료")
