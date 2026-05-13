"""
Supabase 데이터베이스 처리 모듈입니다.

Streamlit secrets에 저장된 Supabase URL과 anon key로 watchlist 테이블에
접속합니다. 기존 데이터와 호환되도록 recent_high 컬럼은 건드리지 않고,
새 theme 컬럼은 없을 때도 앱이 깨지지 않게 fallback 처리합니다.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client


TABLE_NAME = "watchlist"


@st.cache_resource
def get_supabase_client() -> Client:
    """Streamlit secrets에서 Supabase 클라이언트를 생성합니다."""
    url = st.secrets["supabase"]["url"]
    anon_key = st.secrets["supabase"]["anon_key"]
    return create_client(url, anon_key)


def normalize_stock_code(stock_code: str) -> str:
    """종목번호를 6자리 숫자 문자열로 정리합니다."""
    return str(stock_code).strip()


def normalize_user_id(user_id: str) -> str:
    """사용자 ID 앞뒤 공백을 제거합니다."""
    return str(user_id).strip()


def is_valid_stock_code(stock_code: str) -> bool:
    """한국 주식 종목번호 형식인 6자리 숫자인지 검사합니다."""
    return re.fullmatch(r"\d{6}", normalize_stock_code(stock_code)) is not None


def init_db() -> None:
    """Supabase 클라이언트 초기화와 secrets 설정을 확인합니다."""
    get_supabase_client()


def _is_missing_theme_error(exc: Exception) -> bool:
    """Supabase에 theme 컬럼이 아직 없을 때 나는 오류인지 판별합니다."""
    message = str(exc).lower()
    return "theme" in message and (
        "does not exist" in message
        or "could not find" in message
        or "schema cache" in message
        or "42703" in message
        or "pgrst204" in message
    )


def _rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Supabase 응답 rows를 앱이 기대하는 컬럼을 가진 DataFrame으로 바꿉니다."""
    columns = [
        "id",
        "user_id",
        "theme",
        "name",
        "stock_code",
        "target_price",
        "memo",
        "created_at",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows).reindex(columns=columns)
    df["theme"] = df["theme"].fillna("")
    df["memo"] = df["memo"].fillna("")
    return df


def is_theme_column_available() -> bool:
    """
    theme 컬럼이 Supabase watchlist 테이블에 있는지 확인합니다.

    컬럼이 없으면 앱은 빈 테마로 조회하고, README의 SQL 안내를 보여줄 수
    있습니다.
    """
    client = get_supabase_client()
    try:
        client.table(TABLE_NAME).select("theme").limit(1).execute()
        return True
    except Exception as exc:
        if _is_missing_theme_error(exc):
            return False
        raise


def add_stock(
    user_id: str,
    theme: str,
    name: str,
    stock_code: str,
    target_price: int,
    memo: str,
) -> None:
    """새 종목을 Supabase watchlist 테이블에 저장합니다."""
    client = get_supabase_client()
    payload = {
        "user_id": normalize_user_id(user_id),
        "theme": theme.strip(),
        "name": name.strip(),
        "stock_code": normalize_stock_code(stock_code),
        "target_price": float(target_price),
        "memo": memo.strip(),
    }
    try:
        client.table(TABLE_NAME).insert(payload).execute()
    except Exception as exc:
        if not _is_missing_theme_error(exc):
            raise
        payload.pop("theme", None)
        client.table(TABLE_NAME).insert(payload).execute()


def update_stock(
    user_id: str,
    item_id: Any,
    theme: str,
    name: str,
    stock_code: str,
    target_price: int,
    memo: str,
) -> None:
    """user_id와 id가 모두 일치하는 기존 종목 정보를 수정합니다."""
    client = get_supabase_client()
    payload = {
        "theme": theme.strip(),
        "name": name.strip(),
        "stock_code": normalize_stock_code(stock_code),
        "target_price": float(target_price),
        "memo": memo.strip(),
    }
    try:
        (
            client.table(TABLE_NAME)
            .update(payload)
            .eq("user_id", normalize_user_id(user_id))
            .eq("id", item_id)
            .execute()
        )
    except Exception as exc:
        if not _is_missing_theme_error(exc):
            raise
        payload.pop("theme", None)
        (
            client.table(TABLE_NAME)
            .update(payload)
            .eq("user_id", normalize_user_id(user_id))
            .eq("id", item_id)
            .execute()
        )


def delete_stock(user_id: str, item_id: Any) -> None:
    """user_id와 id가 모두 일치하는 종목만 삭제합니다."""
    client = get_supabase_client()
    (
        client.table(TABLE_NAME)
        .delete()
        .eq("user_id", normalize_user_id(user_id))
        .eq("id", item_id)
        .execute()
    )


def stock_code_exists(
    user_id: str,
    stock_code: str,
    exclude_id: Any | None = None,
) -> bool:
    """같은 user_id 안에서 같은 종목번호가 이미 있는지 확인합니다."""
    client = get_supabase_client()
    query = (
        client.table(TABLE_NAME)
        .select("id")
        .eq("user_id", normalize_user_id(user_id))
        .eq("stock_code", normalize_stock_code(stock_code))
        .limit(1)
    )
    if exclude_id is not None:
        query = query.neq("id", exclude_id)
    response = query.execute()
    return bool(response.data)


def get_stocks(user_id: str) -> pd.DataFrame:
    """특정 user_id에 등록된 모든 종목을 DataFrame으로 반환합니다."""
    client = get_supabase_client()
    select_with_theme = "id,user_id,theme,name,stock_code,target_price,memo,created_at"
    select_without_theme = "id,user_id,name,stock_code,target_price,memo,created_at"

    try:
        response = (
            client.table(TABLE_NAME)
            .select(select_with_theme)
            .eq("user_id", normalize_user_id(user_id))
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        if not _is_missing_theme_error(exc):
            raise
        response = (
            client.table(TABLE_NAME)
            .select(select_without_theme)
            .eq("user_id", normalize_user_id(user_id))
            .order("created_at", desc=True)
            .execute()
        )

    return _rows_to_dataframe(response.data or [])


# 이전 app.py 코드와 외부 테스트 스크립트 호환을 위한 별칭입니다.
add_item = add_stock
update_item = update_stock
delete_item = delete_stock
get_watchlist = get_stocks
