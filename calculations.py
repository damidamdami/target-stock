"""
되돌림 목표가 대시보드의 계산 로직입니다.

앱의 목표가는 자동 계산하지 않습니다. 사용자가 직접 입력한 목표가와
현재가를 비교해서 차이, 괴리율, 조정 진행률, 상태만 계산합니다.
"""

from __future__ import annotations


def calculate_price_gap(
    current_price: float | None, target_price: float | None
) -> float | None:
    """목표가와의 차이 = 현재가 - 목표가"""
    if current_price is None or target_price is None or target_price <= 0:
        return None
    return current_price - target_price


def calculate_target_gap_rate(
    current_price: float | None, target_price: float | None
) -> float | None:
    """목표가 대비 괴리율(%) = (현재가 - 목표가) / 목표가 * 100"""
    if current_price is None or target_price is None or target_price <= 0:
        return None
    return ((current_price - target_price) / target_price) * 100


def calculate_pullback_progress(
    current_price: float | None,
    recent_high: float | None,
    target_price: float | None,
) -> float | None:
    """
    조정 진행률(%) = (최근 고점 - 현재가) / (최근 고점 - 목표가) * 100

    최근 고점과 목표가가 같으면 분모가 0이 되므로 N/A 처리를 위해 None을
    반환합니다.
    """
    if (
        current_price is None
        or recent_high is None
        or target_price is None
        or target_price <= 0
        or recent_high == target_price
    ):
        return None
    return ((recent_high - current_price) / (recent_high - target_price)) * 100


def classify_status(
    current_price: float | None, target_price: float | None
) -> str:
    """현재가와 사용자가 입력한 목표가를 기준으로 상태를 분류합니다."""
    if current_price is None:
        return "조회 실패"
    if target_price is None or target_price <= 0:
        return "목표가 확인"
    if current_price > target_price * 1.10:
        return "대기"
    if target_price * 1.03 < current_price <= target_price * 1.10:
        return "조정 중"
    if target_price < current_price <= target_price * 1.03:
        return "목표 근접"
    if target_price * 0.95 <= current_price <= target_price:
        return "목표 도달"
    return "하방 이탈"


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
