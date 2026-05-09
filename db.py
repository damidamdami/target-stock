"""
Supabase 데이터베이스 처리 모듈입니다.

Streamlit의 .streamlit/secrets.toml에 저장된 Supabase URL과 anon key를 읽어
watchlist 테이블에 CRUD 요청을 보냅니다. 키 값은 코드에 하드코딩하지 않고
항상 st.secrets["supabase"]에서 읽습니다.
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
    """
    Supabase 연결과 secrets 설정을 확인합니다.

    테이블 생성은 Supabase에서 이미 완료되어 있다는 전제이므로 여기서는
    클라이언트 초기화만 수행합니다.
    """
    get_supabase_client()


def _rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Supabase 응답 rows를 앱이 기대하는 컬럼을 가진 DataFrame으로 바꿉니다."""
    columns = [
        "id",
        "user_id",
        "name",
        "stock_code",
        "recent_high",
        "target_price",
        "memo",
        "created_at",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).reindex(columns=columns)


def add_item(
    user_id: str,
    name: str,
    stock_code: str,
    recent_high: int,
    target_price: int,
    memo: str,
) -> None:
    """새 종목을 Supabase watchlist 테이블에 저장합니다."""
    client = get_supabase_client()
    client.table(TABLE_NAME).insert(
        {
            "user_id": normalize_user_id(user_id),
            "name": name.strip(),
            "stock_code": normalize_stock_code(stock_code),
            "recent_high": float(recent_high),
            "target_price": float(target_price),
            "memo": memo.strip(),
        }
    ).execute()


def update_item(
    user_id: str,
    item_id: Any,
    name: str,
    stock_code: str,
    recent_high: int,
    target_price: int,
    memo: str,
) -> None:
    """user_id와 id가 모두 일치하는 기존 종목 정보를 수정합니다."""
    client = get_supabase_client()
    client.table(TABLE_NAME).update(
        {
            "name": name.strip(),
            "stock_code": normalize_stock_code(stock_code),
            "recent_high": float(recent_high),
            "target_price": float(target_price),
            "memo": memo.strip(),
        }
    ).eq("user_id", normalize_user_id(user_id)).eq("id", item_id).execute()


def delete_item(user_id: str, item_id: Any) -> None:
    """user_id와 id가 모두 일치하는 종목만 삭제합니다."""
    client = get_supabase_client()
    client.table(TABLE_NAME).delete().eq("user_id", normalize_user_id(user_id)).eq(
        "id",
        item_id,
    ).execute()


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


def get_watchlist(user_id: str) -> pd.DataFrame:
    """특정 user_id에 등록된 모든 종목을 DataFrame으로 반환합니다."""
    client = get_supabase_client()
    response = (
        client.table(TABLE_NAME)
        .select("id,user_id,name,stock_code,recent_high,target_price,memo,created_at")
        .eq("user_id", normalize_user_id(user_id))
        .order("created_at", desc=True)
        .execute()
    )
    return _rows_to_dataframe(response.data or [])
