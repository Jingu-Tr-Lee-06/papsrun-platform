"""
[학생 08] Alice Stats 다중 선형 회귀(OLS) 기반 심박수 추론 모듈

- 역할: 6차시 OLS 회귀분석으로 도출된 편회귀계수를 적용하여,
        임의의 도로 간선 통과 시 발생하는 추가 심박 상승치(ΔHR) 및 예상 심박수를 산출함.
- 회귀 방정식:
    ΔHR = -2.99 + (0.10 * 체중) + (7.63 * PAPS등급) + (1.20 * 경사도) + (0.03 * 복사에너지)
"""

from typing import Dict, Any


def predict_ml_bpm_gain(
    slope_pct: float,
    rad_w_m2: float,
    weight_kg: float,
    paps_grade: int,
    rest_hr: float = 70.0
) -> Dict[str, Any]:
    """
    구간 환경 속성과 러너의 신체 프로필을 입력받아 예상 심박 부하를 추론합니다.

    Args:
        slope_pct (float): 도로 구간 경사도 (%)
        rad_w_m2 (float): 노면 지표 흡수 복사에너지 (W/m²)
        weight_kg (float): 러너 체중 (kg)
        paps_grade (int): PAPS 체력 등급 (1~5등급)
        rest_hr (float, optional): 러너의 안정 시 심박수 (기본값: 70.0 BPM)

    Returns:
        Dict[str, Any]:
            - delta_hr (float): 예상 심박 상승치 (BPM)
            - predicted_bpm (float): 220 BPM 생체 안전 인터락이 적용된 최종 심박수 (BPM)
    """
    # 1. 6차시 Alice Stats OLS 회귀 모델 편회귀계수 대입
    # ΔHR = -2.99 + 0.10*weight + 7.63*grade + 1.20*slope + 0.03*rad
    raw_delta_hr = (
        -2.99
        + (0.10 * float(weight_kg))
        + (7.63 * int(paps_grade))
        + (1.20 * float(slope_pct))
        + (0.03 * float(rad_w_m2))
    )

    # 2. 음수 및 기저치 방어 (보행 최소 생체 부하 5.0 BPM 보장)
    safe_delta_hr = max(5.0, raw_delta_hr)

    # 3. 러너의 최종 예상 심박수 계산 (안정시 심박수 + 상승치)
    raw_predicted_bpm = float(rest_hr) + safe_delta_hr

    # 4. 생체 안전 인터락: 최대 심박수(220 BPM) 초과 방지 클램핑
    clamped_bpm = min(220.0, max(float(rest_hr), raw_predicted_bpm))

    return {
        "delta_hr": round(safe_delta_hr, 2),
        "predicted_bpm": round(clamped_bpm, 1)
    }


# 단독 실행 테스트 (단위 테스트용)
if __name__ == "__main__":
    # 테스트 케이스: 체력 4등급, 체중 62kg인 학생이 급경사 땡볕 오르막을 주행할 때
    test_result = predict_ml_bpm_gain(
        slope_pct=9.2,
        rad_w_m2=490.0,
        weight_kg=62.0,
        paps_grade=4,
        rest_hr=75.0
    )
    print("▶ 8번 학생 ML 추론 테스트 결과:")
    print(f"   - 예상 심박 상승치: +{test_result['delta_hr']} BPM")
    print(f"   - 최종 클램핑 심박수: {test_result['predicted_bpm']} BPM")