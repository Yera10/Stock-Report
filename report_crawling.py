from selenium import webdriver
from selenium.webdriver.common.by import By
from urls import HKurl
import pandas as pd
import re
import FinanceDataReader as fdr
import numpy as np

#    INPUT
sdate = input('검색기간 시작 날짜 (YYYY-MM-DD 형태로 입력): ')
edate = input('검색기간 끝 날짜 (YYYY-MM-DD 형태로 입력): ')
analyst = input('검색할 ANALYST 입력  (전체검색할 경우 Enter) : ')


#   크롬에서 웹페이지 접속
driver = webdriver.Chrome()
driver.get(HKurl(sdate, edate)) # 오류출력 고치기

# ANALYST 검색
if analyst!='':
    search_element = driver.find_element(By.ID, 'search_text')   # 검색창
    search_element.send_keys(analyst)   # 검색어 입력
    search_btn = driver.find_elements(By.CSS_SELECTOR, '#f_search > div > div.hd_top > div.btn_r > a')   # 클릭
    search_btn[0].click()
    analyst_quoted = re.search(r'search_text=([^&]*)', driver.current_url).groups()[0]  # ANALYST quote

# 총 페이지수 
# page_num = len(driver.find_elements_by_css_selector('#contents > div.paging > a'))-1

#   CRAWLING
Report_arr = None    # 결과담을 리스트
page = 1
while True:
    #   해당 페이지 모든 리포트
    allReportElement = driver.find_elements(By.CSS_SELECTOR, '#contents > div.table_style01 > table > tbody > tr')

    #   마지막 페이지 > 종료
    if (len(allReportElement)==0) or (allReportElement[0].find_element(By.TAG_NAME, 'td').text=='결과가 없습니다.'):
        driver.quit()
        break

    #   report text 가져오기
    body = driver.find_elements(By.CSS_SELECTOR, '#contents > div.table_style01 > table > tbody> tr > td')
    body_text = [b.text for b in body]
    body_arr = np.array(body_text).reshape((-1, 9))

    #   합치기
    if Report_arr is not None:
        Report_arr = np.concatenate([Report_arr, body_arr])
    else:
        Report_arr = body_arr.copy()
    
    # verbose
    print(f'\rpage {page} {"■"*page}', end='')
    
    # next page
    page +=1
    url = HKurl(sdate, edate, page=page, analyst_quoted=(analyst_quoted if analyst!="" else ""))    # 오류 출력되는 부분
    driver.get(url)

#   PREPROCESSING
df = pd.DataFrame(Report_arr)
df.drop(columns=[6, 7, 8], inplace=True)
df.columns = ['reporting_date', 'title', 'target_price', 'opinion', 'analyst', 'provider']

# 종목명, 종목코드 추가
df[['name', 'ticker']] = df.title.str.extract('(.+)\((\s*\d{6}\s*)\)')
df.loc[df.ticker.isnull(), ['name', 'ticker']] = df.title[df.ticker.isnull()].str.extract('([^\s\d]+)(\d{6})').values   # {종목명}({종목코드}) 의 형식일 경우

# DROP
print('\n===================Non Ticker DROP=====================\n')
print(df[df.ticker.isnull()])
df.drop(index=df[df.ticker.isnull()].index, inplace=True)
print('\n===================Non TargetPrice DROP=====================\n')
print(df[df.target_price=='0'])
df.drop(index=df[df.target_price=='0'].index, inplace=True)

# 당일 종가 추가
get_close_price = lambda x: fdr.DataReader(*x[['ticker','reporting_date', 'reporting_date']])['Close'][0]
df['close_price'] = df.apply(get_close_price, axis=1)

# 데이터타입 변환
df.reporting_date = pd.to_datetime(df.reporting_date)
df.target_price = df.target_price.str.replace(',', '').astype(int)

# 당일 종가 없는 것 체크
print('\n===================Non Close Price=====================\n')
for x in df[['ticker', 'reporting_date', 'title']].values:
    if fdr.DataReader(*x[[0,1,1]]).shape[0]==0:
        print(x)

# SAVE
df = df[['reporting_date', 'provider', 'analyst', 'name', 'ticker', 'close_price', 'target_price', 'opinion', 'title']]
df.to_csv(f'consensus_{analyst}_{sdate.replace("-",".")}~{edate.replace("-",".")}.csv', encoding='utf-8', index=False)
print('\nSAVE COMPLETE')