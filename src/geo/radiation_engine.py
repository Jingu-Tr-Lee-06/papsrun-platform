"""지표면 열복사 역학(Thermal Radiation) 및 열부하 지수 산출 엔진.

단파 복사(하향 일사, 반사)와 장파 복사(대기 방출, 지표면 방출)의 복사 평형식을 적용하여
지표 순복사에너지(Net Radiation, Rn)를 물리적으로 계산하고,
지형 경사도와 결합하여 러너의 체감 열 스트레스 지수(Heat Stress Index)를 산출합니다.
"""

import math
from typing import Any, Dict, Tuple

# 스테판-볼츠만 상수 (W/(m^2 * K^4))
STEFAN_BOLTZMANN_CONSTANT = 5.670374419e-8

# 노면 재질별 고유 열물리 파라미터 사전
# albedo: 단파 일사 반사율 (0.0 ~ 1.0)
# emissivity: 열적외선 방출율 (0.0 ~ 1.0)
# thermal_inertia_factor: 열용량 및 열관류율에 따른 노면 가열 배수
SURFACE_PROPERTIES: Dict[str, Dict[str, float]] = {
    "asphalt_dark": {
        "albedo": 0.08,
        "emissivity": 0.95,
        "thermal_inertia_factor": 1.45,
    },
    "asphalt_aged": {
        "albedo": 0.15,
        "emissivity": 0.93,
        "thermal_inertia_factor": 1.30,
    },
    "concrete_walkway": {
        "albedo": 0.30,
        "emissivity": 0.90,
        "thermal_inertia_factor": 1.15,
    },
    "urethane_track": {
        "albedo": 0.12,
        "emissivity": 0.92,
        "thermal_inertia_factor": 1.35,
    },
    "soil_trail": {
        "albedo": 0.22,
        "emissivity": 0.94,
        "thermal_inertia_factor": 1.05,
    },
    "lawn_grass": {
        "albedo": 0.25,
        "emissivity": 0.98,
        "thermal_inertia_factor": 0.85,
    },
}


def get_surface_parameters(surface_type: str) -> Dict[str, float]:
    """노면 재질 유형에 따른 열물리 상수 세트를 반환합니다.

    Args:
        surface_type: 노면 식별 문자열 (예: 'asphalt_dark', 'urethane_track')

    Returns:
        {'albedo': float, 'emissivity': float, 'thermal_inertia_factor': float}
    """
    return SURFACE_PROPERTIES.get(
        surface_type,
        {
            "albedo": 0.20,
            "emissivity": 0.92,
            "thermal_inertia_factor": 1.00,
        },
    )


def calculate_net_radiation(
    shortwave_down: float = 750.0,
    albedo: float = 0.15,
    air_temp_c: float = 30.0,
    is_shaded: bool = False,
    emissivity: float = 0.93,
    relative_humidity_pct: float = 60.0,
) -> float:
    """단파 및 장파 복사 플럭스를 결합하여 지표 순복사에너지(Rn)를 계산합니다.

    물리 공식:
        Rn = (1 - alpha) * S_down + L_down - L_up
        - 단파 순복사: S_net = (1 - alpha) * S_down
        - 대기 하향 장파: L_down = eps_air * sigma * T_air^4
        - 지표 상향 장파: L_up = eps_surf * sigma * T_surf^4

    Args:
        shortwave_down: 전천 하향 단파 일사량 (W/m^2, 맑은 날 정오 기준 통상 700~900)
        albedo: 지표 반사율 (0.0 ~ 1.0)
        air_temp_c: 현재 대기 기온 (°C)
        is_shaded: 수목 또는 건물에 의한 차광 여부 (차광 시 하향 일사 투과율 20%로 급감)
        emissivity: 지표 방출율 (0.0 ~ 1.0)
        relative_humidity_pct: 상대습도 (%)

    Returns:
        순복사에너지 Rn (W/m^2, 소수점 2자리 반올림)
    """
    # 차광 시 일사량 감쇄 적용 (직달일사 차단, 산란광 약 20%만 도달)
    effective_s_down = shortwave_down * 0.20 if is_shaded else shortwave_down

    # 1. 단파 순복사 (Net Shortwave Radiation)
    net_shortwave = (1.0 - albedo) * effective_s_down

    # 절대온도(K) 환산
    t_air_k = air_temp_c + 273.15

    # 수증기압(e_a, hPa) 산출 (Tetens 공식)
    sat_vapor_press = 6.1078 * (10.0 ** ((7.5 * air_temp_c) / (237.3 + air_temp_c)))
    actual_vapor_press = sat_vapor_press * (relative_humidity_pct / 100.0)

    # 대기 유효 방출율 (Brunt 공식 변형)
    eps_air = 0.605 + 0.048 * math.sqrt(max(0.1, actual_vapor_press))

    # 2. 하향 장파 복사 (Atmospheric Longwave Radiation Down)
    l_down = eps_air * STEFAN_BOLTZMANN_CONSTANT * (t_air_k**4)

    # 지표 온도 추정: 일사량과 알베도에 따라 대기 기온보다 상승
    # 차광이 없을 경우 노면 온도는 기온보다 최대 8~18도 상승 가능
    temp_excess = 0.0
    if not is_shaded:
        temp_excess = (effective_s_down * (1.0 - albedo)) * 0.025

    t_surf_k = (air_temp_c + temp_excess) + 273.15

    # 3. 상향 장파 복사 (Surface Longwave Radiation Up)
    l_up = emissivity * STEFAN_BOLTZMANN_CONSTANT * (t_surf_k**4)

    # 최종 순복사에너지
    net_rn = net_shortwave + l_down - l_up
    return round(float(net_rn), 2)


def calculate_heat_stress_index(
    net_radiation: float,
    air_temp_c: float,
    slope_pct: float = 0.0,
) -> Tuple[float, str]:
    """순복사에너지(Rn), 기온, 경사도를 종합하여 러너 열부하 지수를 산출합니다.

    Args:
        net_radiation: 지표 순복사에너지 (W/m^2)
        air_temp_c: 현재 기온 (°C)
        slope_pct: 도로 구간 경사도 (%)

    Returns:
        (heat_stress_index, suitability_description) 튜플
    """
    # 기본 환경 스트레스 지수 베이스라인
    base_env_stress = air_temp_c * 0.8 + (max(0.0, net_radiation) / 45.0)

    # 경사도에 따른 추가 대사율(심박 부하) 가중치 (오르막 1%당 2.5% 체감 부하 증가)
    slope_penalty = 1.0 + (max(0.0, slope_pct) * 0.025)

    final_heat_index = round(base_env_stress * slope_penalty, 1)

    # 러닝 적합성 분류
    if final_heat_index < 28.0:
        suitability = "쾌적 구간 (러닝 최적)"
    elif final_heat_index < 34.0:
        suitability = "보통 구간 (안정 페이스)"
    elif final_heat_index < 40.0:
        suitability = "주의 구간 (수분 섭취 필요)"
    else:
        suitability = "위험 구간 (고열부하·우회 권장)"

    return final_heat_index, suitability