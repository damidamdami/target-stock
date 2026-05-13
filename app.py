"""
주식 목표가 추적 웹 대시보드

이 앱은 상승 목표가를 자동 계산하는 도구가 아닙니다. 사용자가 차트나
피보나치 기준으로 직접 정한 "되돌림 목표가"를 입력하면, 현재가가 그
목표가에 얼마나 가까워졌는지 매일 확인할 수 있게 보여줍니다.

실행:
    streamlit run app.py
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculations import (
    calculate_adjustment_rate,
    calculate_price_gap,
    classify_status,
)
from data_fetcher import add_current_prices, fetch_price_history
from db import (
    add_stock,
    delete_stock,
    get_stocks,
    init_db,
    is_theme_column_available,
    is_valid_stock_code,
    normalize_stock_code,
    normalize_user_id,
    stock_code_exists,
    update_stock,
)


st.set_page_config(
    page_title="주식 목표가 추적 웹 대시보드",
    page_icon="📊",
    layout="wide",
)


STATUS_COLORS = {
    "대기": "#64748b",
    "조정 중": "#2563eb",
    "목표 근접": "#f59e0b",
    "목표 도달": "#16a34a",
    "하방 이탈": "#dc2626",
    "조회 실패": "#7c3aed",
    "목표가 확인": "#9333ea",
}


def to_optional_float(value: object) -> float | None:
    """NaN, 빈 값, 변환 불가 값을 None으로 바꿉니다."""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int_price(value: object) -> int:
    """가격 입력값을 정수로 반올림합니다."""
    if value is None or pd.isna(value):
        return 0
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value or value.upper() == "N/A":
            return 0
    return int(round(float(value)))


def format_price(value: float | None) -> str:
    """가격은 반올림한 정수와 천 단위 콤마로 표시합니다."""
    if value is None:
        return "N/A"
    return f"{round(value):,}"


def format_percent(value: float | None) -> str:
    """퍼센트는 소수점 1자리와 % 기호로 표시합니다."""
    if value is None:
        return "N/A"
    return f"{value:,.1f}%"


def validate_item(
    user_id: str,
    theme: str,
    name: str,
    stock_code: str,
    target_price: int,
    exclude_id: Any | None = None,
) -> str | None:
    """등록/수정 전에 사용자 입력값을 검증하고 오류 메시지를 반환합니다."""
    if not normalize_user_id(user_id):
        return "사용자 ID를 입력해 주세요."
    if not name.strip():
        return "종목명을 입력해 주세요."
    if not is_valid_stock_code(stock_code):
        return "종목번호는 005930처럼 6자리 숫자로 입력해 주세요."
    if target_price <= 0:
        return "목표가는 0보다 커야 합니다."
    if stock_code_exists(user_id, stock_code, exclude_id=exclude_id):
        return "현재 사용자 ID에 이미 등록된 종목번호입니다."
    return None


def build_dashboard_data(watchlist: pd.DataFrame) -> pd.DataFrame:
    """DB 데이터에 현재가와 계산 컬럼을 추가합니다."""
    priced = add_current_prices(watchlist)
    rows = []

    for _, row in priced.iterrows():
        current_price = to_optional_float(row.get("current_price"))
        target_price = to_optional_float(row.get("target_price"))

        price_gap = calculate_price_gap(current_price, target_price)
        adjustment_rate = calculate_adjustment_rate(current_price, target_price)
        status = classify_status(current_price, target_price)

        rows.append(
            {
                **row.to_dict(),
                "current_price": current_price,
                "price_gap": price_gap,
                "adjustment_rate": adjustment_rate,
                "status": status,
            }
        )

    return pd.DataFrame(rows)


def make_editor_table(dashboard_df: pd.DataFrame) -> pd.DataFrame:
    """st.data_editor에 넣을 표를 만듭니다."""
    if dashboard_df.empty:
        return pd.DataFrame()

    editor_df = dashboard_df[
        [
            "id",
            "theme",
            "name",
            "stock_code",
            "target_price",
            "current_price",
            "price_gap",
            "adjustment_rate",
            "status",
            "memo",
        ]
    ].copy()

    editor_df["theme"] = editor_df["theme"].fillna("")
    editor_df["memo"] = editor_df["memo"].fillna("")

    editor_df = editor_df.rename(
        columns={
            "id": "ID",
            "theme": "테마",
            "name": "종목명",
            "stock_code": "종목번호",
            "target_price": "목표가",
            "current_price": "현재가",
            "price_gap": "목표가와의 차이",
            "adjustment_rate": "조정 진행률(%)",
            "status": "상태",
            "memo": "메모",
        }
    )
    for column in ["목표가", "현재가", "목표가와의 차이"]:
        editor_df[column] = editor_df[column].apply(
            lambda value: "N/A" if pd.isna(value) else format_price(float(value))
        )
    editor_df["조정 진행률(%)"] = editor_df["조정 진행률(%)"].apply(
        lambda value: "N/A" if pd.isna(value) else format_percent(float(value))
    )
    return editor_df


def make_csv_table(editor_df: pd.DataFrame) -> pd.DataFrame:
    """CSV 다운로드용으로 가격/퍼센트 표시 형식을 맞춥니다."""
    if editor_df.empty:
        return editor_df

    csv_df = editor_df.copy()
    return csv_df.drop(columns=["ID"], errors="ignore")


def style_status(row: pd.Series) -> list[str]:
    """상태 컬럼만 배지처럼 보이도록 색상을 강조합니다."""
    color = STATUS_COLORS.get(row["상태"], "#64748b")
    styles = []
    for column in row.index:
        if column == "상태":
            styles.append(
                f"color: {color}; font-weight: 700; border-left: 4px solid {color};"
            )
        else:
            styles.append("")
    return styles


def render_summary_cards(dashboard_df: pd.DataFrame) -> None:
    """상단 요약 카드를 표시합니다."""
    total_count = len(dashboard_df)
    near_count = int((dashboard_df["status"] == "목표 근접").sum())
    reached_count = int((dashboard_df["status"] == "목표 도달").sum())
    failed_count = int((dashboard_df["status"] == "조회 실패").sum())
    adjustment_values = dashboard_df["adjustment_rate"].dropna()
    avg_adjustment = adjustment_values.mean() if not adjustment_values.empty else None

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("전체 종목 수", f"{total_count:,}개")
    col2.metric("목표 근접", f"{near_count:,}개")
    col3.metric("목표 도달", f"{reached_count:,}개")
    col4.metric("조회 실패", f"{failed_count:,}개")
    col5.metric("평균 조정 진행률", format_percent(avg_adjustment))


def render_user_id_input() -> str:
    """사이드바에서 Supabase 데이터 구분에 사용할 사용자 ID를 입력받습니다."""
    st.sidebar.header("사용자")
    user_id = st.sidebar.text_input(
        "사용자 ID",
        value=st.session_state.get("user_id", ""),
        placeholder="예: my-watchlist",
        help="같은 사용자 ID 안에서만 종목번호 중복을 막습니다.",
    )
    clean_user_id = normalize_user_id(user_id)
    st.session_state["user_id"] = clean_user_id
    return clean_user_id


def render_add_form(user_id: str) -> None:
    """사이드바에 신규 종목 등록 폼을 표시합니다."""
    st.sidebar.header("종목 등록")
    with st.sidebar.form("add_watchlist_form", clear_on_submit=True):
        theme = st.text_input("테마", placeholder="반도체 장비")
        name = st.text_input("종목명", placeholder="한미반도체")
        stock_code = st.text_input("종목번호", placeholder="042700", max_chars=6)
        target_price = st.number_input(
            "목표가",
            min_value=0,
            step=100,
            format="%d",
        )
        memo = st.text_area("메모", placeholder="직접 계산한 되돌림 목표가 기준 등")
        submitted = st.form_submit_button("등록")

    if not submitted:
        return

    clean_code = normalize_stock_code(stock_code)
    target_price_value = to_int_price(target_price)
    error = validate_item(
        user_id,
        theme,
        name,
        clean_code,
        target_price_value,
    )
    if error:
        st.sidebar.error(error)
        return

    try:
        add_stock(user_id, theme, name, clean_code, target_price_value, memo)
        st.sidebar.success("종목이 등록되었습니다.")
        st.rerun()
    except Exception as exc:
        st.sidebar.error(f"등록 중 오류가 발생했습니다: {exc}")


def render_status_legend() -> None:
    """상태 범례는 버튼처럼 보일 수 있어 표시하지 않습니다."""
    return None


def save_editor_changes(user_id: str, edited_df: pd.DataFrame) -> None:
    """data_editor에서 수정된 값을 DB에 저장합니다."""
    errors = []

    for _, row in edited_df.iterrows():
        item_id = row["ID"]
        theme = "" if pd.isna(row["테마"]) else str(row["테마"]).strip()
        name = str(row["종목명"]).strip()
        stock_code = normalize_stock_code(str(row["종목번호"]))
        target_price = to_int_price(row["목표가"])
        memo = "" if pd.isna(row["메모"]) else str(row["메모"])

        error = validate_item(
            user_id,
            theme,
            name,
            stock_code,
            target_price,
            exclude_id=item_id,
        )
        if error:
            errors.append(f"{name or stock_code}: {error}")
            continue

        try:
            update_stock(
                user_id,
                item_id,
                theme,
                name,
                stock_code,
                target_price,
                memo,
            )
        except Exception as exc:
            errors.append(f"{name}: 저장 중 오류가 발생했습니다: {exc}")

    if errors:
        st.error("일부 변경사항을 저장하지 못했습니다.")
        for error in errors:
            st.warning(error)
        return

    st.success("변경사항이 저장되었습니다.")
    st.rerun()


def render_dashboard_editor(user_id: str, dashboard_df: pd.DataFrame) -> pd.DataFrame:
    """편집 가능한 대시보드 표를 표시합니다."""
    st.subheader("대시보드 표")
    editor_df = make_editor_table(dashboard_df)

    column_config = {
        "ID": st.column_config.TextColumn("ID", disabled=True, width="small"),
        "테마": st.column_config.TextColumn("테마"),
        "종목명": st.column_config.TextColumn("종목명", required=True),
        "종목번호": st.column_config.TextColumn(
            "종목번호",
            help="005930처럼 6자리 숫자로 입력합니다.",
            required=True,
            max_chars=6,
        ),
        "목표가": st.column_config.TextColumn(
            "목표가",
            help="정수 또는 140,000처럼 콤마가 있는 숫자로 입력할 수 있습니다.",
            required=True,
        ),
        "현재가": st.column_config.TextColumn(
            "현재가",
            disabled=True,
        ),
        "목표가와의 차이": st.column_config.TextColumn(
            "목표가와의 차이",
            disabled=True,
        ),
        "조정 진행률(%)": st.column_config.TextColumn(
            "조정 진행률(%)",
            disabled=True,
        ),
        "상태": st.column_config.TextColumn("상태", disabled=True),
        "메모": st.column_config.TextColumn("메모"),
    }

    edited_df = st.data_editor(
        editor_df,
        column_config=column_config,
        disabled=[
            "ID",
            "현재가",
            "목표가와의 차이",
            "조정 진행률(%)",
            "상태",
        ],
        column_order=[
            "테마",
            "종목명",
            "종목번호",
            "목표가",
            "현재가",
            "목표가와의 차이",
            "조정 진행률(%)",
            "상태",
            "메모",
        ],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key="watchlist_editor",
    )

    if "ID" not in edited_df.columns:
        edited_df = edited_df.copy()
        edited_df["ID"] = editor_df["ID"].values

    col1, col2 = st.columns([1, 3])
    if col1.button("변경사항 저장", type="primary", use_container_width=True):
        save_editor_changes(user_id, edited_df)

    csv_df = make_csv_table(editor_df)
    col2.download_button(
        "CSV 다운로드",
        data=csv_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="stock_pullback_dashboard.csv",
        mime="text/csv",
        use_container_width=True,
    )

    return edited_df


def render_delete_panel(user_id: str, watchlist: pd.DataFrame) -> None:
    """선택한 종목 삭제 UI를 표시합니다."""
    st.subheader("종목 삭제")
    if watchlist.empty:
        st.info("삭제할 종목이 없습니다.")
        return

    options = {
        f"{row['name']} / {row['stock_code']}": row["id"]
        for _, row in watchlist.iterrows()
    }
    selected_label = st.selectbox("삭제 대상 선택", list(options.keys()))
    selected_id = options[selected_label]

    if st.button("선택한 종목 삭제", type="secondary"):
        try:
            delete_stock(user_id, selected_id)
            st.warning("선택한 종목이 삭제되었습니다.")
            st.rerun()
        except Exception as exc:
            st.error(f"삭제 중 오류가 발생했습니다: {exc}")


def render_price_chart(dashboard_df: pd.DataFrame) -> None:
    """선택한 종목의 최근 6개월 일봉 차트를 표시합니다."""
    st.subheader("최근 6개월 일봉 차트")
    if dashboard_df.empty:
        st.info("차트를 볼 종목을 먼저 등록해 주세요.")
        return

    options = {
        f"{row['name']} / {row['stock_code']}": row
        for _, row in dashboard_df.iterrows()
    }
    selected_label = st.selectbox("차트 종목 선택", list(options.keys()))
    selected = options[selected_label]

    history = fetch_price_history(selected["stock_code"])
    if history.empty:
        st.warning("차트 조회 실패: 종목번호 또는 네트워크 상태를 확인해 주세요.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history["Date"],
            y=history["Close"],
            mode="lines",
            name="종가",
            line={"color": "#2563eb", "width": 2},
        )
    )
    fig.add_hline(
        y=float(selected["target_price"]),
        line_dash="dash",
        line_color="#16a34a",
        annotation_text="목표가",
        annotation_position="bottom left",
    )

    fig.update_layout(
        height=460,
        margin={"l": 20, "r": 20, "t": 24, "b": 20},
        xaxis_title="날짜",
        yaxis_title="가격",
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.05},
    )
    fig.update_yaxes(tickformat=",")
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    """Streamlit 앱 진입점입니다."""
    init_db()

    st.title("주식 목표가 추적 웹 대시보드")
    st.caption(
        "직접 입력한 되돌림 목표가에 현재가가 얼마나 가까워졌는지 확인합니다. "
        "현재가 조회 실패 시 N/A와 조회 실패 상태로 표시됩니다."
    )

    user_id = render_user_id_input()
    if not user_id:
        st.info("왼쪽 사이드바에서 사용자 ID를 입력하면 Supabase watchlist를 불러옵니다.")
        return

    try:
        theme_available = is_theme_column_available()
    except Exception as exc:
        st.error("Supabase watchlist 테이블 정보를 확인하지 못했습니다.")
        st.code(str(exc), language="text")
        return

    if not theme_available:
        st.warning(
            "Supabase watchlist 테이블에 theme 컬럼이 아직 없습니다. "
            "README의 SQL을 실행하면 테마를 저장할 수 있습니다. "
            "현재는 테마가 빈칸으로 표시되고 저장 시 테마 값은 생략됩니다."
        )

    render_add_form(user_id)

    try:
        watchlist = get_stocks(user_id)
    except Exception as exc:
        st.error("Supabase watchlist 데이터를 불러오지 못했습니다.")
        st.info(
            "Supabase에서 anon 역할이 watchlist 테이블을 조회할 수 있는지 "
            "GRANT 권한과 RLS 정책을 확인해 주세요."
        )
        st.code(str(exc), language="text")
        return
    if watchlist.empty:
        st.info("왼쪽 사이드바에서 첫 종목을 등록해 주세요. 예: 005930, 000660, 042700")
        return

    dashboard_df = build_dashboard_data(watchlist)
    render_summary_cards(dashboard_df)

    render_dashboard_editor(user_id, dashboard_df)

    st.divider()
    render_price_chart(dashboard_df)

    st.divider()
    render_delete_panel(user_id, watchlist)


if __name__ == "__main__":
    main()
