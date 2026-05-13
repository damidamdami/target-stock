# target-stock

`target-stock`은 사용자가 직접 입력한 되돌림 목표가에 현재가가 얼마나 가까워졌는지 확인하는 Streamlit 대시보드입니다.

앱 화면 제목은 **주식 목표가 추적 웹 대시보드**로 표시됩니다.

## 주요 기능

- 테마, 종목명, 종목번호, 목표가, 메모 등록
- Supabase `watchlist` 테이블 저장
- 사용자 ID별 데이터 분리
- 같은 사용자 ID 안에서 종목번호 중복 등록 방지
- FinanceDataReader 우선 현재가 조회
- yfinance `.KS`, `.KQ` fallback 조회
- 목표가와의 차이, 조정 진행률, 상태 자동 계산
- 최근 6개월 일봉 차트
- 표에서 직접 수정 후 저장
- 종목 삭제
- CSV 다운로드

## Supabase 테이블 업데이트

테마 입력을 사용하려면 Supabase SQL Editor에서 아래 SQL을 한 번 실행합니다.

```sql
alter table public.watchlist
add column if not exists theme text;
```

기존 `recent_high` 컬럼은 삭제하지 않아도 됩니다. 앱 화면, 입력, 수정, 계산에서는 더 이상 사용하지 않습니다.

기존 데이터의 `theme` 값이 `null`이면 앱에서는 빈칸으로 표시됩니다.

## 로컬 실행

```bash
cd /Users/damdamm/Desktop/stock_dashboard
/opt/anaconda3/bin/python3.12 -m pip install -r requirements.txt
/opt/anaconda3/bin/python3.12 -m streamlit run app.py
```

일반 Python 환경에서는 아래처럼 실행할 수 있습니다.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Secrets

Streamlit Cloud 또는 로컬 `.streamlit/secrets.toml`에 아래 구조로 Supabase 값을 설정합니다.

```toml
[supabase]
url = "https://bndctwtpmtayboiwvoef.supabase.co"
anon_key = "실제 sb_publishable 키"
```

## Streamlit Cloud 배포

배포 앱 이름은 `target-stock`을 사용합니다.

Streamlit Cloud 설정 예시:

- App name: `target-stock`
- Main file path: `app.py`
- Python version: `3.11+`
- App URL 예시: `https://target-stock.streamlit.app`

배포 후 Streamlit Cloud의 Secrets 메뉴에 Supabase 설정을 추가해야 합니다.
