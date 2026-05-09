"""
한국 주식 현재가와 최근 6개월 일봉 데이터를 조회하는 모듈입니다.

조회 우선순위:
1. FinanceDataReader로 6자리 종목번호 조회
2. yfinance로 종목번호.KS 조회
3. yfinance로 종목번호.KQ 조회

모든 조회는 실패해도 앱이 중단되지 않도록 예외 처리합니다.
"""

from __future__ import annotations

from datetime import date
from dateutil.relativedelta import relativedelta

import FinanceDataReader as fdr
import pandas as pd
import yfinance as yf


def _latest_close_from_history(history: pd.DataFrame) -> float | None:
    """일봉 데이터에서 가장 최근 종가를 추출합니다."""
    if history.empty or "Close" not in history.columns:
        return None
    close_series = history["Close"].dropna()
    if close_series.empty:
        return None
    return float(close_series.iloc[-1])


def _normalize_history(history: pd.DataFrame) -> pd.DataFrame:
    """Plotly 차트에서 쓰기 쉽게 Date 컬럼을 가진 DataFrame으로 정리합니다."""
    if history.empty or "Close" not in history.columns:
        return pd.DataFrame()

    result = history.copy()
    if "Date" not in result.columns:
        result = result.reset_index()

    # FinanceDataReader는 인덱스명이 Date인 경우가 많고, yfinance도 reset 후 Date가 생깁니다.
    if "Date" not in result.columns and "index" in result.columns:
        result = result.rename(columns={"index": "Date"})

    if "Date" not in result.columns:
        return pd.DataFrame()

    result["Date"] = pd.to_datetime(result["Date"]).dt.date
    return result


def _fetch_fdr_history(stock_code: str) -> pd.DataFrame:
    """FinanceDataReader로 최근 6개월 일봉 데이터를 조회합니다."""
    end = date.today()
    start = end - relativedelta(months=6)
    return fdr.DataReader(stock_code, start, end)


def _fetch_yfinance_history(symbol: str, period: str = "6mo") -> pd.DataFrame:
    """yfinance로 최근 일봉 데이터를 조회합니다."""
    return yf.Ticker(symbol).history(period=period, auto_adjust=False)


def fetch_price_history(stock_code: str) -> pd.DataFrame:
    """우선순위에 따라 최근 6개월 일봉 차트 데이터를 조회합니다."""
    clean_code = str(stock_code).strip()

    try:
        history = _normalize_history(_fetch_fdr_history(clean_code))
        if not history.empty:
            return history
    except Exception:
        pass

    for suffix in (".KS", ".KQ"):
        try:
            history = _normalize_history(_fetch_yfinance_history(f"{clean_code}{suffix}"))
            if not history.empty:
                return history
        except Exception:
            pass

    return pd.DataFrame()


def fetch_current_price(stock_code: str) -> float | None:
    """우선순위에 따라 현재가 또는 최근 종가를 조회합니다."""
    clean_code = str(stock_code).strip()

    try:
        price = _latest_close_from_history(_fetch_fdr_history(clean_code))
        if price is not None:
            return price
    except Exception:
        pass

    for suffix in (".KS", ".KQ"):
        symbol = f"{clean_code}{suffix}"
        try:
            ticker = yf.Ticker(symbol)
            try:
                last_price = ticker.fast_info.get("last_price")
                if last_price is not None:
                    return float(last_price)
            except Exception:
                pass

            price = _latest_close_from_history(
                ticker.history(period="5d", auto_adjust=False)
            )
            if price is not None:
                return price
        except Exception:
            pass

    return None


def add_current_prices(watchlist: pd.DataFrame) -> pd.DataFrame:
    """watchlist DataFrame에 현재가 컬럼을 추가합니다."""
    if watchlist.empty:
        return watchlist.copy()

    result = watchlist.copy()
    result["current_price"] = result["stock_code"].apply(fetch_current_price)
    return result
