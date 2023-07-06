
def HKurl(sdate, edate, page=1, analyst_quoted=''):
    return f"http://consensus.hankyung.com/analysis/list?skinType=business&sdate={sdate}&edate={edate}&search_text={analyst_quoted}&now_page={page}"