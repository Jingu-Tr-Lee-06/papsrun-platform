"""지오펜싱 및 공간 메타데이터 기반 도로 노면 재질 자동 분류 엔진.

학생들이 작도한 도로 세그먼트의 위경도 좌표가 캠퍼스 내 특정 영역
(예: 대운동장 트랙 구역, 잔디 광장, 숲길 산책로)에 속하는지 광선 투사(Ray Casting)
알고리즘으로 검사하고, 공간 메타데이터와 결합하여 적정 노면 재질을 자동으로 추정합니다.
"""

from typing import Any, Dict, List, Optional, Tuple

# 캠퍼스 주요 구역 지오펜싱 폴리곤 정의 (기본값: 공주대 신관캠퍼스 대운동장 등)
CAMPUS_ZONES: Dict[str, Dict[str, Any]] = {
    "stadium_track": {
        "surface_type": "urethane_track",
        "description": "대운동장 우레탄 러닝 트랙",
        # [위도, 경도] 순서의 닫힌 다각형 좌표 리스트
        "polygon": [
            [36.4682, 127.1390],
            [36.4682, 127.1415],
            [36.4668, 127.1415],
            [36.4668, 127.1390],
        ],
    },
    "central_lawn": {
        "surface_type": "lawn_grass",
        "description": "중앙 잔디 광장",
        "polygon": [
            [36.4690, 127.1410],
            [36.4690, 127.1430],
            [36.4678, 127.1430],
            [36.4678, 127.1410],
        ],
    },
    "campus_trail": {
        "surface_type": "soil_trail",
        "description": "후문 뒷산 흙길 산책로",
        "polygon": [
            [36.4710, 127.1380],
            [36.4710, 127.1405],
            [36.4698, 127.1405],
            [36.4698, 127.1380],
        ],
    },
}


def is_point_in_polygon(
    lat: float,
    lon: float,
    polygon: List[List[float]],
) -> bool:
    """광선 투사(Ray-Casting) 알고리즘을 사용하여 점의 다각형 내부 포함 여부를 판정합니다.

    Args:
        lat: 검사할 점의 위도
        lon: 검사할 점의 경도
        polygon: [[lat, lon], ...] 형태의 다각형 꼭짓점 좌표 리스트

    Returns:
        내부 포함 여부 (bool)
    """
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    p1_lat, p1_lon = polygon[0]

    for i in range(1, n + 1):
        p2_lat, p2_lon = polygon[i % n]
        if min(p1_lat, p2_lat) < lat <= max(p1_lat, p2_lat):
            if lon <= max(p1_lon, p2_lon):
                if p1_lat != p2_lat:
                    x_inters = (lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat) + p1_lon
                else:
                    x_inters = p1_lon
                if p1_lon == p2_lon or lon <= x_inters:
                    inside = not inside
        p1_lat, p1_lon = p2_lat, p2_lon

    return inside


def classify_surface_by_geometry(
    u_coords: Tuple[float, float],
    v_coords: Tuple[float, float],
    custom_zones: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """도로 세그먼트 양 끝점 및 중점의 위치를 지오펜싱 영역과 대조하여 노면 재질을 결정합니다.

    Args:
        u_coords: 시작 노드 (lat, lon)
        v_coords: 끝 노드 (lat, lon)
        custom_zones: 사용자 정의 구역 사전 (선택 사항)

    Returns:
        분류된 노면 타입 문자열 (기본: 'concrete_walkway')
    """
    zones = custom_zones or CAMPUS_ZONES

    lat_u, lon_u = u_coords
    lat_v, lon_v = v_coords
    lat_mid = (lat_u + lat_v) / 2.0
    lon_mid = (lon_u + lon_v) / 2.0

    # 1. 중점이 특정 지오펜싱 영역에 들어가는지 우선 확인
    for _, zone_info in zones.items():
        poly = zone_info.get("polygon", [])
        if is_point_in_polygon(lat_mid, lon_mid, poly):
            return zone_info.get("surface_type", "concrete_walkway")

    # 2. 시작점이나 끝점이 포함되는지 확인
    for _, zone_info in zones.items():
        poly = zone_info.get("polygon", [])
        if is_point_in_polygon(lat_u, lon_u, poly) or is_point_in_polygon(lat_v, lon_v, poly):
            return zone_info.get("surface_type", "concrete_walkway")

    # 3. 일치하는 영역이 없을 경우 기본 도보용 보도블록 반환
    return "concrete_walkway"


def infer_surface_with_osm_fallback(
    u_coords: Tuple[float, float],
    v_coords: Tuple[float, float],
    osm_highway_tag: Optional[str] = None,
    osm_surface_tag: Optional[str] = None,
) -> str:
    """OSM 메타데이터 태그와 지오펜싱 판정을 융합하여 최종 노면을 확정합니다.

    Args:
        u_coords: 시작 노드 (lat, lon)
        v_coords: 끝 노드 (lat, lon)
        osm_highway_tag: OSM 도로 종류 (예: 'footway', 'track', 'primary')
        osm_surface_tag: OSM 명시적 노면 태그 (예: 'asphalt', 'paved', 'ground')

    Returns:
        표준 노면 코드 식별자
    """
    # 1. OSM 명시적 태그가 유효하면 우선 채택
    if osm_surface_tag:
        tag_low = osm_surface_tag.lower().strip()
        if tag_low in ("tartan", "synthetic", "rubber"):
            return "urethane_track"
        if tag_low in ("grass", "lawn"):
            return "lawn_grass"
        if tag_low in ("ground", "dirt", "earth", "sand", "gravel"):
            return "soil_trail"
        if tag_low in ("paving_stones", "concrete", "cobblestone"):
            return "concrete_walkway"
        if tag_low in ("asphalt", "bitumen"):
            return "asphalt_dark"

    # 2. 지오펜싱 영역 검사
    geo_inferred = classify_surface_by_geometry(u_coords, v_coords)
    if geo_inferred != "concrete_walkway":
        return geo_inferred

    # 3. highway 태그 기반 휴리스틱 추정
    if osm_highway_tag:
        hw_low = osm_highway_tag.lower().strip()
        if hw_low in ("motorway", "trunk", "primary", "secondary", "tertiary"):
            return "asphalt_dark"
        if hw_low in ("service", "residential"):
            return "asphalt_aged"
        if hw_low in ("track", "path"):
            return "soil_trail"

    return "concrete_walkway"