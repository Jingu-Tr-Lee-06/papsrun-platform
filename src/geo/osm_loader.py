"""OpenStreetMap(OSM) 공간 데이터 로더 및 노면 속성 파서.

학교 캠퍼스 주변의 OSM 지리공간 도로망 데이터를 캐싱하여 로드하고,
주어진 좌표의 태그(surface, highway, leisure 등)를 분석하여
노면 피복 재질(surface_type), 기본 도로명, 차광 가능성을 자동 판별합니다.
"""

from typing import Any, Dict, Optional
import requests

from src.geo.snap_engine import haversine_distance

# 기본 노면 매핑 사전 (OSM surface 태그 -> 내부 식별자)
OSM_SURFACE_MAP = {
    "asphalt": "asphalt_dark",
    "paved": "asphalt_aged",
    "concrete": "concrete_walkway",
    "paving_stones": "concrete_walkway",
    "sett": "concrete_walkway",
    "tartan": "urethane_track",
    "rubber": "urethane_track",
    "ground": "soil_trail",
    "dirt": "soil_trail",
    "earth": "soil_trail",
    "grass": "lawn_grass",
    "sand": "soil_trail",
}

# 기본 캠퍼스 주요 거점 레퍼런스 (공주대학교 신관캠퍼스 기준 지오펜싱 프리셋)
CAMPUS_POI_PRESETS = [
    {
        "name": "대운동장 우레탄 트랙",
        "lat": 36.4691,
        "lon": 127.1408,
        "radius_m": 80.0,
        "surface": "urethane_track",
        "shaded": False,
    },
    {
        "name": "중앙 잔디광장 보도",
        "lat": 36.4678,
        "lon": 127.1398,
        "radius_m": 70.0,
        "surface": "concrete_walkway",
        "shaded": True,
    },
    {
        "name": "학생회관 앞 아스팔트 도로",
        "lat": 36.4665,
        "lon": 127.1415,
        "radius_m": 60.0,
        "surface": "asphalt_dark",
        "shaded": False,
    },
    {
        "name": "사범관 숲길 산책로",
        "lat": 36.4655,
        "lon": 127.1385,
        "radius_m": 75.0,
        "surface": "soil_trail",
        "shaded": True,
    },
]


def fetch_osm_elements_around(
    lat: float,
    lon: float,
    radius_meters: float = 40.0,
) -> Optional[Dict[str, Any]]:
    """지정 좌표 주변의 OSM 도로 및 보행로 피처를 Overpass API로 질의합니다.

    네트워크 지연이나 타임아웃 발생 시 안전하게 None을 반환하도록 예외 처리됩니다.

    Args:
        lat: 중심 위도
        lon: 중심 경도
        radius_meters: 검색 반경 (m)

    Returns:
        OSM 질의 결과 딕셔너리 또는 None
    """
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:3];
    (
      way(around:{radius_meters},{lat},{lon})["highway"];
      way(around:{radius_meters},{lat},{lon})["leisure"];
    );
    out tags 5;
    """
    try:
        response = requests.post(
            overpass_url,
            data={"data": query},
            headers={"User-Agent": "PAPSrun-STEAM-App/1.0"},
            timeout=3.5,
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def infer_surface_type(lat: float, lon: float) -> Dict[str, Any]:
    """위경도 좌표를 분석하여 노면 피복 재질, 도로명, 차광 여부를 추론합니다.

    1순위: 학교 캠퍼스 지오펜싱 프리셋(정밀 POI 매칭)
    2순위: 실시간 OpenStreetMap 태그 파싱
    3순위: 기본 보행로(콘크리트/보도블록) 폴백

    Args:
        lat: 검사할 지점의 위도
        lon: 검사할 지점의 경도

    Returns:
        {
            "surface_type": str,
            "detected_name": str,
            "is_shaded": bool,
            "confidence": str
        }
    """
    # 1. 지오펜싱 프리셋 검사
    for poi in CAMPUS_POI_PRESETS:
        dist = haversine_distance(lat, lon, poi["lat"], poi["lon"])
        if dist <= poi["radius_m"]:
            return {
                "surface_type": poi["surface"],
                "detected_name": poi["name"],
                "is_shaded": poi["shaded"],
                "confidence": "CAMPUS_PRESET_HIGH",
            }

    # 2. OSM 실시간 태그 분석 시도
    osm_data = fetch_osm_elements_around(lat, lon, radius_meters=35.0)
    if osm_data and "elements" in osm_data:
        elements = osm_data.get("elements", [])
        for el in elements:
            tags = el.get("tags", {})
            osm_surface = tags.get("surface", "").lower()
            osm_highway = tags.get("highway", "").lower()
            osm_name = tags.get("name", "")

            # 노면 태그가 명시된 경우
            if osm_surface in OSM_SURFACE_MAP:
                mapped_surface = OSM_SURFACE_MAP[osm_surface]
                is_shaded = tags.get("covered") == "yes" or tags.get("tunnel") == "yes"
                return {
                    "surface_type": mapped_surface,
                    "detected_name": osm_name or f"캠퍼스 {osm_highway or '보도'}",
                    "is_shaded": is_shaded,
                    "confidence": "OSM_TAG_EXACT",
                }

            # highway 유형별 기본 추정
            if osm_highway in ("footway", "pedestrian", "path"):
                return {
                    "surface_type": "concrete_walkway",
                    "detected_name": osm_name or "캠퍼스 보행로",
                    "is_shaded": True,
                    "confidence": "OSM_HIGHWAY_INFERRED",
                }
            elif osm_highway in ("service", "secondary", "residential"):
                return {
                    "surface_type": "asphalt_dark",
                    "detected_name": osm_name or "캠퍼스 내부 도로",
                    "is_shaded": False,
                    "confidence": "OSM_HIGHWAY_INFERRED",
                }

    # 3. 안전 기본값 폴백
    return {
        "surface_type": "concrete_walkway",
        "detected_name": "캠퍼스 연결로",
        "is_shaded": False,
        "confidence": "FALLBACK_DEFAULT",
    }