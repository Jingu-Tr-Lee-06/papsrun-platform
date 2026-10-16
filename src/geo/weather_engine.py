"""기상청 API허브 연동 및 지표 흡수 복사에너지 연산 모듈."""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import requests
import streamlit as st

SURFACE_ALBEDO_MAP: Dict[str, float] = {
    "asphalt": 0.10,
    "urethane": 0.20,
    "concrete": 0.30,
    "dirt": 0.25,
    "shaded_dirt": 0.25,
    "grass": 0.22,
}

FALLBACK_WEATHER: Dict[str, Any] = {
    "temp_c": 31.5,
    "solar_w_m2": 750.0,
    "status": "FALLBACK_MOCK",
    "updated_at": "DEFAULT",
}


@st.cache_data(ttl=600)  # 10분 캐싱 (불필요한 반복 호출 및 타임아웃 방지)
def _request_kma_api(station_id: str, api_key: str, tm_str: str) -> Dict[str, Any]:
    # 기상청 API허브 종관기상관측(ASOS) 단일 관측지점 실시간 조회
    url = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php"
    params = {
        "tm": tm_str,
        "stn": station_id,
        "help": "0",
        "authKey": api_key,
    }
    
    # connect timeout 3초, read timeout 5초 분리
    response = requests.get(url, params=params, timeout=(3.0, 5.0))
    return {
        "status_code": response.status_code,
        "text": response.text,
    }


def fetch_kma_weather_data(
    station_id: str = "108",  # 108: 서울 (공주는 235 등 관측소 번호 지정 가능)
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """기상청 API허브에서 실시간 기온 및 전일사량을 수신합니다."""
    key = api_key or st.secrets.get("KMA_API_KEY", "")
    if not key:
        return {
            **FALLBACK_WEATHER,
            "status": "NO_API_KEY_MOCK",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
            "msg": "st.secrets에 KMA_API_KEY가 없습니다.",
        }

    # 최근 10~20분 전 데이터 조회 (기상청 정시/10분 단위 집계 지연 고려)
    now = datetime.now() - timedelta(minutes=15)
    minute_bucket = (now.minute // 10) * 10
    target_time = now.replace(minute=minute_bucket, second=0, microsecond=0)
    tm_str = target_time.strftime("%Y%m%d%H%M")

    try:
        res = _request_kma_api(station_id, key.strip(), tm_str)
        text = res.get("text", "")

        if "INVALID" in text or "AUTH" in text or "DISALLOW" in text:
            return {
                **FALLBACK_WEATHER,
                "status": "API_AUTH_ERROR",
                "raw_preview": text[:200],
                "request_tm": tm_str,
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }

        lines = [line.strip() for line in text.split("\n") if line.strip() and not line.startswith("#")]
        if lines:
            tokens = lines[-1].split()
            # ASOS 관측 포맷: tokens[11]=기온, tokens[14] or [15]=일사량
            temp = 31.5
            if len(tokens) > 11 and tokens[11] not in ["-99.0", "-99"]:
                try:
                    temp = float(tokens[11])
                except ValueError:
                    pass

            solar_w = 750.0
            for idx in [15, 14]:
                if len(tokens) > idx and tokens[idx] not in ["-99.0", "-99"]:
                    try:
                        raw_solar = float(tokens[idx])
                        solar_w = round(raw_solar * 277.78, 1) if raw_solar > 0 else 0.0
                        break
                    except ValueError:
                        pass

            return {
                "temp_c": temp,
                "solar_w_m2": solar_w,
                "status": "LIVE_KMA_API",
                "station_id": station_id,
                "request_tm": tm_str,
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }

        return {
            **FALLBACK_WEATHER,
            "status": "API_EMPTY_DATA",
            "raw_preview": text[:200],
            "request_tm": tm_str,
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    except requests.exceptions.Timeout:
        return {
            **FALLBACK_WEATHER,
            "status": "API_TIMEOUT_MOCK",
            "msg": "기상청 서버 응답 지연 (해외 클라우드 IP 지연 또는 네트워크 타임아웃)",
            "request_tm": tm_str,
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }
    except Exception as e:
        return {
            **FALLBACK_WEATHER,
            "status": "API_ERROR",
            "error_detail": str(e),
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }


def get_effective_weather_data(override_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """교사 강제 주입(Override) 활성화 여부를 판별하여 최종 기상 환경을 반환합니다."""
    # 1. 인자로 넘어온 Override
    if override_config and override_config.get("active"):
        return {
            "temp_c": float(override_config.get("temp_c", 31.5)),
            "solar_w_m2": float(override_config.get("solar_w_m2", 750.0)),
            "status": "TEACHER_OVERRIDE",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    # 2. 교사 대시보드 세션에 기록된 Override
    teacher_override = st.session_state.get("weather_override")
    if teacher_override and teacher_override.get("active"):
        return {
            "temp_c": float(teacher_override.get("temp_c", 31.5)),
            "solar_w_m2": float(teacher_override.get("solar_w_m2", 750.0)),
            "status": "TEACHER_OVERRIDE",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    # 3. 실시간 기상청 API
    return fetch_kma_weather_data()


def calculate_absorbed_radiation(
    solar_w_m2: float,
    surface_type: str,
    tree_canopy_cover: float = 0.0,
) -> Dict[str, float]:
    """지표면 흡수 복사에너지 R_abs = I_eff * (1 - alpha) 계산"""
    albedo = SURFACE_ALBEDO_MAP.get(surface_type.lower(), 0.15)
    effective_solar = solar_w_m2 * (1.0 - max(0.0, min(0.95, tree_canopy_cover)))
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