"""기상청 API허브 연동 및 캠퍼스 위치(위·경도) 기반 지표 복사에너지 연산 모듈.

지도의 중심 위·경도 좌표를 기반으로 가장 인접한 기상청 관측소를 자동 매핑하며,
실시간 기온과 일사량을 수신하여 노면 피복별 지표면 순흡수 복사에너지(R_abs)를 계산합니다.
"""

from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Optional, Tuple
import requests
import streamlit as st

# 1. 노면 피복별 표준 알베도(Albedo) 상수
SURFACE_ALBEDO_MAP: Dict[str, float] = {
    "asphalt": 0.10,       # 신설/일반 아스팔트
    "urethane": 0.20,      # 우레탄 탄성 트랙
    "concrete": 0.30,      # 콘크리트/보도블록
    "dirt": 0.25,          # 흙길
    "shaded_dirt": 0.25,   # 수관 차광 흙길
    "grass": 0.22,         # 잔디
}

# 2. 전국 주요 일사량/기온 측정 거점 관측소(ASOS) 좌표 데이터베이스
# (학교 좌표에서 가장 가까운 관측소를 자동 탐색하는 기준 테이블)
KMA_STATIONS: List[Dict[str, Any]] = [
    {"stn_id": "133", "name": "대전", "lat": 36.3719, "lng": 127.3721},
    {"stn_id": "232", "name": "천안", "lat": 36.7614, "lng": 127.1214},
    {"stn_id": "236", "name": "부여", "lat": 36.2719, "lng": 126.9208},
    {"stn_id": "177", "name": "홍성", "lat": 36.6578, "lng": 126.6878},
    {"stn_id": "239", "name": "세종", "lat": 36.4862, "lng": 127.2474},
    {"stn_id": "108", "name": "서울", "lat": 37.5714, "lng": 126.9658},
    {"stn_id": "119", "name": "수원", "lat": 37.2723, "lng": 126.9853},
    {"stn_id": "112", "name": "인천", "lat": 37.4776, "lng": 126.6245},
    {"stn_id": "131", "name": "청주", "lat": 36.6392, "lng": 127.4407},
    {"stn_id": "143", "name": "대구", "lat": 35.8779, "lng": 128.6529},
    {"stn_id": "159", "name": "부산", "lat": 35.1047, "lng": 129.0320},
    {"stn_id": "156", "name": "광주", "lat": 35.1729, "lng": 126.8916},
]

FALLBACK_WEATHER: Dict[str, Any] = {
    "temp_c": 31.5,
    "solar_w_m2": 750.0,
    "status": "FALLBACK_MOCK",
    "station_name": "기본 관측소",
    "updated_at": "DEFAULT",
}


def find_nearest_kma_station(lat: float, lng: float) -> Dict[str, Any]:
    """지도 중심 좌표(위도, 경도)에서 유클리드 거리가 가장 가까운 기상청 관측소를 반환합니다."""
    def calc_dist(station: Dict[str, Any]) -> float:
        # 위도 1도 ≈ 111km, 경도 1도 ≈ 88km 가중 반영
        d_lat = (station["lat"] - lat) * 111.0
        d_lng = (station["lng"] - lng) * 88.0
        return math.sqrt(d_lat**2 + d_lng**2)

    nearest = min(KMA_STATIONS, key=calc_dist)
    dist_km = round(calc_dist(nearest), 1)
    return {
        "stn_id": nearest["stn_id"],
        "name": nearest["name"],
        "lat": nearest["lat"],
        "lng": nearest["lng"],
        "distance_km": dist_km,
    }


@st.cache_data(ttl=600)
def _request_kma_api(station_id: str, api_key: str, tm_str: str) -> Dict[str, Any]:
    url = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php"
    params = {
        "tm": tm_str,
        "stn": station_id,
        "help": "0",
        "authKey": api_key,
    }
    response = requests.get(url, params=params, timeout=(3.0, 5.0))
    return {
        "status_code": response.status_code,
        "text": response.text,
    }


def fetch_kma_weather_data(
    lat: float = 36.4678,   # 기본값: 공주 캠퍼스 중심 좌표
    lng: float = 127.1325,
    station_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """주어진 지도 좌표에 가장 가까운 관측소를 자동으로 찾아 실시간 기상자료를 조회합니다."""
    # 1. 인접 관측소 자동 탐색
    if station_id:
        stn_info = next((s for s in KMA_STATIONS if s["stn_id"] == station_id), {"stn_id": station_id, "name": f"지점 {station_id}", "distance_km": 0.0})
    else:
        stn_info = find_nearest_kma_station(lat, lng)

    target_stn_id = stn_info["stn_id"]
    stn_name = stn_info.get("name", "지정 관측소")
    dist_km = stn_info.get("distance_km", 0.0)

    key = api_key or st.secrets.get("KMA_API_KEY", "")
    if not key:
        return {
            **FALLBACK_WEATHER,
            "status": "NO_API_KEY_MOCK",
            "station_name": f"{stn_name} ({dist_km}km)",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
            "msg": "st.secrets에 KMA_API_KEY가 없습니다.",
        }

    now = datetime.now() - timedelta(minutes=15)
    minute_bucket = (now.minute // 10) * 10
    target_time = now.replace(minute=minute_bucket, second=0, microsecond=0)
    tm_str = target_time.strftime("%Y%m%d%H%M")

    try:
        res = _request_kma_api(target_stn_id, key.strip(), tm_str)
        text = res.get("text", "")

        if "활용신청" in text or "403" in text:
            return {
                **FALLBACK_WEATHER,
                "status": "API_NEED_APPLICATION",
                "station_name": f"{stn_name} ({dist_km}km)",
                "msg": "기상청 API허브에서 '종관기상관측(ASOS) 자료' 서비스 활용신청이 필요합니다.",
                "raw_preview": text[:200],
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }

        if "INVALID" in text or "AUTH" in text or "DISALLOW" in text:
            return {
                **FALLBACK_WEATHER,
                "status": "API_AUTH_ERROR",
                "station_name": f"{stn_name} ({dist_km}km)",
                "raw_preview": text[:200],
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }

        valid_lines = []
        for line in text.split("\n"):
            line_str = line.strip()
            if not line_str or line_str.startswith("#") or "7777END" in line_str or "END" in line_str:
                continue
            parts = line_str.split()
            if len(parts) >= 12:
                valid_lines.append(parts)

        if valid_lines:
            tokens = valid_lines[-1]
            temp = 20.0
            try:
                if tokens[11] not in ["-99.0", "-99", "-50.0"]:
                    temp = float(tokens[11])
            except (ValueError, IndexError):
                pass

            solar_w = 0.0
            for idx in [15, 14]:
                if len(tokens) > idx and tokens[idx] not in ["-99.0", "-99", "-"]:
                    try:
                        raw_solar = float(tokens[idx])
                        if raw_solar > 0:
                            solar_w = round(raw_solar * 277.78, 1)
                            break
                    except ValueError:
                        pass

            return {
                "temp_c": temp,
                "solar_w_m2": solar_w,
                "status": "LIVE_KMA_API",
                "station_id": target_stn_id,
                "station_name": f"{stn_name} 관측소 (학교에서 약 {dist_km}km)",
                "request_tm": tm_str,
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }

        return {
            **FALLBACK_WEATHER,
            "status": "API_EMPTY_DATA",
            "station_name": f"{stn_name} ({dist_km}km)",
            "raw_preview": text[:200],
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    except requests.exceptions.Timeout:
        return {
            **FALLBACK_WEATHER,
            "status": "API_TIMEOUT_MOCK",
            "station_name": f"{stn_name} ({dist_km}km)",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }
    except Exception as e:
        return {
            **FALLBACK_WEATHER,
            "status": "API_ERROR",
            "station_name": f"{stn_name} ({dist_km}km)",
            "error_detail": str(e),
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }


def get_effective_weather_data(
    lat: float = 36.4678,
    lng: float = 127.1325,
    override_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """교사 강제 주입(Override) 활성화 여부를 판별하여 최종 기상 환경을 반환합니다."""
    if override_config and override_config.get("active"):
        return {
            "temp_c": float(override_config.get("temp_c", 31.5)),
            "solar_w_m2": float(override_config.get("solar_w_m2", 750.0)),
            "status": "TEACHER_OVERRIDE",
            "station_name": "가상 환경 강제 주입 (교사 Override)",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    teacher_override = st.session_state.get("weather_override")
    if teacher_override and teacher_override.get("active"):
        return {
            "temp_c": float(teacher_override.get("temp_c", 31.5)),
            "solar_w_m2": float(teacher_override.get("solar_w_m2", 750.0)),
            "status": "TEACHER_OVERRIDE",
            "station_name": "가상 환경 강제 주입 (교사 Override)",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    # 좌표 기반 자동 인접 관측소 탐색
    return fetch_kma_weather_data(lat=lat, lng=lng)


def calculate_absorbed_radiation(
    solar_w_m2: float,
    surface_type: str,
    tree_canopy_cover: float = 0.0,
) -> Dict[str, float]:
    """R_abs = I_eff * (1 - albedo) 지표 순흡수 복사에너지 수리 연산"""
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
    """간선(Edge) 딕셔너리에 지표 흡수 복사에너지를 일괄 주입합니다."""
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