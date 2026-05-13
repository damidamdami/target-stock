"""
되돌림 목표가 대시보드의 계산 로직입니다.

앱의 목표가는 자동 계산하지 않습니다. 사용자가 직접 입력한 목표가와
현재가를 비교해서 차이, 조정 진행률, 상태만 계산합니다.
"""

from __future__ import annotations


def calculate_price_gap(
    current_price: float | None, target_price: float | None
) -> float | None:
    """목표가와의 차이 = 현재가 - 목표가"""
    if current_price is None or target_price is None or target_price <= 0:
        return None
    return current_price - target_price


def calculate_adjustment_rate(
    current_price: float | None, target_price: float | None
) -> float | None:
    """조정 진행률(%) = (현재가 - 목표가) / 목표가 * 100"""
    if current_price is None or target_price is None or target_price <= 0:
        return None
    return ((current_price - target_price) / target_price) * 100


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

