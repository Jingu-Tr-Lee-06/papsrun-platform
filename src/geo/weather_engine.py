"""기상청 API허브 연동 및 지표 흡수 복사에너지 연산 모듈.

실시간 기상 데이터(기온, 일사량) 수신 및 노면 피복별 알베도(Albedo) 수리 계산을 수행합니다.
네트워크 오류나 수업 시뮬레이션 필요 시 교사 Override 값을 우선 적용하는 Fail-Safe를 내장합니다.
"""

from datetime import datetime
from typing import Any, Dict, Optional
import requests
import streamlit as st


# 1. 노면 피복별 표준 알베도(Albedo, 반사율) 상수 정의
SURFACE_ALBEDO_MAP: Dict[str, float] = {
    "asphalt": 0.10,       # 신설/일반 아스팔트 (흡수율 90%)
    "urethane": 0.20,      # 우레탄 탄성 포장 트랙
    "concrete": 0.30,      # 콘크리트 보도블록
    "dirt": 0.25,          # 흙길/비포장
    "shaded_dirt": 0.25,   # 수관 차광 녹지 흙길 (일사량 80% 차감 보정)
    "grass": 0.22,         # 잔디밭
}

# 기본 기상 백업값 (한여름 폭염 시뮬레이션 기준)
FALLBACK_WEATHER: Dict[str, Any] = {
    "temp_c": 31.5,
    "solar_w_m2": 750.0,
    "status": "FALLBACK_MOCK",
    "updated_at": "DEFAULT",
}


def fetch_kma_weather_data(
    station_id: str = "108",  # 기본 108: 서울 (공주/충남 등 타 지역 관측소 코드로 변경 가능)
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """기상청 API허브에서 실시간 기온과 전일사량 데이터를 수신합니다."""
    key = api_key or st.secrets.get("KMA_API_KEY", "")
    if not key:
        return {
            **FALLBACK_WEATHER,
            "status": "NO_API_KEY_MOCK",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
            "msg": "st.secrets에 KMA_API_KEY가 설정되지 않았습니다.",
        }

    url = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php"
    params = {
        "stn": station_id,
        "help": "0",
        "authKey": key,
    }

    try:
        # 타임아웃을 6.0초로 여유 있게 설정
        response = requests.get(url, params=params, timeout=6.0)
        
        # 기상청 에러 메시지 검출 (인증 실패 등)
        if "INVALID" in response.text or "ERROR" in response.text:
            return {
                **FALLBACK_WEATHER,
                "status": "API_AUTH_ERROR",
                "raw_response": response.text[:150],
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }

        if response.status_code == 200:
            lines = [line.strip() for line in response.text.split("\n") if line.strip() and not line.startswith("#")]
            if lines:
                tokens = lines[-1].split()
                # 기상청 ASOS 전문: tokens[11] = 기온, tokens[14] or [15] = 일사량
                temp = 31.0
                if len(tokens) > 11 and tokens[11] not in ["-99.0", "-99"]:
                    temp = float(tokens[11])

                solar_w = 700.0
                # 일사량 컬럼 탐색 (기상청 일사량 결측치 대응)
                if len(tokens) > 15 and tokens[15] not in ["-99.0", "-99"]:
                    raw_solar_mj = float(tokens[15])
                    solar_w = round(raw_solar_mj * 277.78, 1) if raw_solar_mj > 0 else 700.0
                elif len(tokens) > 14 and tokens[14] not in ["-99.0", "-99"]:
                    raw_solar_mj = float(tokens[14])
                    solar_w = round(raw_solar_mj * 277.78, 1) if raw_solar_mj > 0 else 700.0

                return {
                    "temp_c": temp,
                    "solar_w_m2": solar_w,
                    "status": "LIVE_KMA_API",
                    "station_id": station_id,
                    "updated_at": datetime.now().strftime("%H:%M:%S"),
                }
    except requests.exceptions.Timeout:
        return {
            **FALLBACK_WEATHER,
            "status": "API_TIMEOUT_MOCK",
            "msg": "기상청 서버 응답 지연 (6초 초과)",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }
    except Exception as e:
        return {
            **FALLBACK_WEATHER,
            "status": "API_PARSE_ERROR",
            "error_detail": str(e),
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    return {
        **FALLBACK_WEATHER,
        "status": "API_EMPTY_RESPONSE",
        "updated_at": datetime.now().strftime("%H:%M:%S"),
    }


def get_effective_weather_data(override_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """교사 강제 주입(Override) 활성화 여부를 판별하여 최종 기상 환경을 반환합니다."""
    # 1. 교사 대시보드에서 강제 주입이 활성화된 경우 (1순위 우선권)
    if override_config and override_config.get("active"):
        return {
            "temp_c": float(override_config.get("temp_c", 31.5)),
            "solar_w_m2": float(override_config.get("solar_w_m2", 750.0)),
            "status": "TEACHER_OVERRIDE",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    # 2. 세션 상태에 저장된 교사 설정 확인
    teacher_override = st.session_state.get("weather_override")
    if teacher_override and teacher_override.get("active"):
        return {
            "temp_c": float(teacher_override.get("temp_c", 31.5)),
            "solar_w_m2": float(teacher_override.get("solar_w_m2", 750.0)),
            "status": "TEACHER_OVERRIDE",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    # 3. 실시간 기상청 API 호출
    return fetch_kma_weather_data()


def calculate_absorbed_radiation(
    solar_w_m2: float,
    surface_type: str,
    tree_canopy_cover: float = 0.0,
) -> Dict[str, float]:
    """
    노면 피복과 차광률을 적용하여 순흡수 복사에너지(R_abs)를 계산합니다.
    수식: R_abs = I_effective * (1 - albedo)
    """
    albedo = SURFACE_ALBEDO_MAP.get(surface_type.lower(), 0.15)

    # 수관 차광(나무 그늘)에 따른 유효 도달 일사량 감쇄 (차광률 0.0 ~ 0.95)
    effective_solar = solar_w_m2 * (1.0 - max(0.0, min(0.95, tree_canopy_cover)))

    # 지표면 흡수 복사에너지 계산
    absorbed_rad = effective_solar * (1.0 - albedo)

    return {
        "albedo": albedo,
        "effective_solar_w_m2": round(effective_solar, 1),
        "absorbed_rad_w_m2": round(absorbed_rad, 1),
    }


def inject_radiation_to_edges(
    edges: Dict[str, Dict[str, Any]],
    current_weather: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """모둠별 도로망 간선(Edge) 딕셔너리에 지표 흡수 복사에너지 속성을 일괄 주입합니다."""
    solar_w = float(current_weather.get("solar_w_m2", 750.0))
    temp_c = float(current_weather.get("temp_c", 31.5))

    updated_edges = {}
    for edge_id, edge in edges.items():
        edge_data = dict(edge)
        surface = edge_data.get("surface_type", "asphalt")
        canopy = float(edge_data.get("tree_canopy_cover", 0.0))

        rad_info = calculate_absorbed_radiation(solar_w, surface, canopy)
        edge_data["albedo"] = rad_info["albedo"]
        edge_data["effective_solar_w_m2"] = rad_info["effective_solar_w_m2"]
        edge_data["absorbed_rad_w_m2"] = rad_info["absorbed_rad_w_m2"]
        edge_data["ambient_temp_c"] = temp_c

        updated_edges[edge_id] = edge_data

    return updated_edges