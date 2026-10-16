"""기상청 API허브 연동 및 캠퍼스 위치(위·경도) 기반 지표 복사에너지 연산 모듈.

지도의 중심 위·경도 좌표를 기반으로 가장 인접한 기상청 관측소를 자동 매핑하며,
실시간 기온과 일사량을 수신하여 노면 피복별 지표면 순흡수 복사에너지(R_abs)를 계산합니다.
수업 안전장치(Fail-Safe)로 교사 관제 대시보드의 Override 설정을 1순위로 보장합니다.
"""

from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Optional
import requests
import streamlit as st


# ==============================================================================
# 1. 노면 피복별 표준 알베도(Albedo) 및 백업 상수
# ==============================================================================
SURFACE_ALBEDO_MAP: Dict[str, float] = {
    "asphalt": 0.10,       # 신설/일반 아스팔트
    "urethane": 0.20,      # 우레탄 트랙
    "concrete": 0.30,      # 콘크리트 보도블록
    "dirt": 0.25,          # 흙길
    "shaded_dirt": 0.25,   # 수관 차광 녹지 흙길
    "grass": 0.22,         # 잔디밭
}

FALLBACK_WEATHER: Dict[str, Any] = {
    "temp_c": 31.5,
    "solar_w_m2": 750.0,
    "status": "FALLBACK_MOCK",
    "station_name": "기본 관측소",
    "updated_at": "DEFAULT",
}

# 대전(133), 천안(232) 등 확실한 일사량 관측소를 우선 배치
KMA_STATIONS: List[Dict[str, Any]] = [
    {"stn_id": "133", "name": "대전", "lat": 36.3719, "lng": 127.3721},
    {"stn_id": "239", "name": "세종", "lat": 36.4862, "lng": 127.2474},
    {"stn_id": "232", "name": "천안", "lat": 36.7614, "lng": 127.1214},
    {"stn_id": "236", "name": "부여", "lat": 36.2719, "lng": 126.9208},
    {"stn_id": "177", "name": "홍성", "lat": 36.6578, "lng": 126.6878},
    {"stn_id": "131", "name": "청주", "lat": 36.6392, "lng": 127.4407},
    {"stn_id": "108", "name": "서울", "lat": 37.5714, "lng": 126.9658},
    {"stn_id": "119", "name": "수원", "lat": 37.2723, "lng": 126.9853},
]


def find_nearest_kma_station(lat: float, lng: float) -> Dict[str, Any]:
    """지도 중심 좌표에서 거리가 가장 가까운 기상청 ASOS 관측소를 탐색합니다."""
    def calc_dist(station: Dict[str, Any]) -> float:
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


def _raw_request_kma_api(station_id: str, api_key: str, tm_str: Optional[str] = None) -> Dict[str, Any]:
    """기상청 서버에 직접 HTTP 요청을 수행합니다."""
    url = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php"
    params = {
        "stn": station_id,
        "help": "0",
        "authKey": api_key,
    }
    # tm이 있으면 전달, 없으면 서버가 가장 최신 관측값 반환
    if tm_str:
        params["tm"] = tm_str

    response = requests.get(url, params=params, timeout=(4.0, 6.0))
    return {
        "status_code": response.status_code,
        "text": response.text,
    }


def _parse_kma_text(text: str) -> Optional[List[str]]:
    """기상청 전문에서 주석과 마커를 제거하고 실제 관측 행을 추출합니다."""
    valid_rows = []
    for line in text.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean.startswith("#") or "7777END" in line_clean or line_clean.startswith("7777"):
            continue
        tokens = line_clean.split()
        if len(tokens) >= 5:
            valid_rows.append(tokens)
    return valid_rows[-1] if valid_rows else None


def fetch_kma_weather_data(
    lat: float = 36.4678,
    lng: float = 127.1325,
    station_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """인접 관측소에서 실시간 기온과 전일사량을 수신합니다 (빈 데이터 시 대전 ASOS 자동 폴백)."""
    key = api_key or st.secrets.get("KMA_API_KEY", "")
    if not key:
        return {
            **FALLBACK_WEATHER,
            "status": "NO_API_KEY_MOCK",
            "msg": "st.secrets에 KMA_API_KEY가 없습니다.",
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    # 1. 1차 타겟 관측소 결정
    stn_info = find_nearest_kma_station(lat, lng) if not station_id else {"stn_id": station_id, "name": f"지점 {station_id}", "distance_km": 0.0}
    target_stn_id = stn_info["stn_id"]
    stn_name = stn_info.get("name", "지정 관측소")
    dist_km = stn_info.get("distance_km", 0.0)

    try:
        # tm을 생략하여 기상청 최신 관측값을 직접 요청
        res = _raw_request_kma_api(target_stn_id, key.strip(), tm_str=None)
        text = res.get("text", "")

        target_tokens = _parse_kma_text(text)

        # 2. 만약 해당 지점에 관측값이 비어있다면, 대전 ASOS(133, 충청권 대표 거점)로 자동 폴백
        if not target_tokens and target_stn_id != "133":
            res = _raw_request_kma_api("133", key.strip(), tm_str=None)
            text = res.get("text", "")
            target_tokens = _parse_kma_text(text)
            if target_tokens:
                stn_name = "대전 (충청 대표 ASOS)"
                target_stn_id = "133"

        if target_tokens:
            # 기온(TA) 파싱: 기본 11번 인덱스 또는 유효 범위 숫자 탐색
            temp = 18.0
            if len(target_tokens) > 11 and target_tokens[11] not in ["-99.0", "-99", "-50.0"]:
                try:
                    temp = float(target_tokens[11])
                except ValueError:
                    pass
            else:
                for tok in target_tokens[2:12]:
                    try:
                        v = float(tok)
                        if -30.0 <= v <= 45.0:
                            temp = v
                            break
                    except ValueError:
                        continue

            # 일사량(SI) 파싱 (1 MJ/m² = 277.78 W/m²)
            solar_w = 0.0
            for idx in [15, 14, 13]:
                if len(target_tokens) > idx and target_tokens[idx] not in ["-99.0", "-99", "-"]:
                    try:
                        raw_solar = float(target_tokens[idx])
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
                "station_name": f"{stn_name} ({dist_km}km)",
                "raw_tokens": target_tokens[:12],
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }

        return {
            **FALLBACK_WEATHER,
            "status": "API_EMPTY_DATA",
            "station_name": f"{stn_name} ({dist_km}km)",
            "raw_preview": text[:300],
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

    return fetch_kma_weather_data(lat=lat, lng=lng)


def calculate_absorbed_radiation(
    solar_w_m2: float,
    surface_type: str,
    tree_canopy_cover: float = 0.0,
) -> Dict[str, float]:
    """R_abs = I_eff * (1 - albedo) 단위면적당 지표 순흡수 복사에너지 연산"""
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
    """간선(Edge) 딕셔너리에 지표 흡수 복사에너지 속성을 일괄 주입합니다."""
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