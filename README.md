# Stock-Report
증권사 리포트 수집/분석 자동화

## 환경셋팅
```
# Poetry 설치 (Windows Powershell)
$ (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# Poetry 설치 (Mac)
$ curl -sSL https://install.python-poetry.org | python3 -

# Poetry 환경변수에 등록하기
# Poetry 위치 : C:\Users\SEJONG\AppData\Roaming\Python\Scripts\

# 프로젝트 폴더 내에 가상환경을 저장
$ poetry config virtualenvs.in-project true 

# Poetry 가상환경 실행
$ poetry shell
```

### 한경 컨센서스 크롤링
```
python report_crawling.py
```