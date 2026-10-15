"""지리공간(GIS) 및 환경물리 계산 엔진 패키지.

하버사인 거리, 노드 자석 스냅, OSM 노면 판정, 순복사에너지(Rn) 및 경사도 계산 모듈을 노출합니다.
"""

from src.geo.elevation_engine import (
    calculate_segment_elevation_metrics,
    get_point_elevation,
    query_online_elevation,
)
from src.geo.osm_loader import (
    fetch_osm_elements_around,
    infer_surface_type,
)
from src.geo.radiation_engine import (
    SURFACE_PROPERTIES,
    calculate_heat_stress_index,
    calculate_net_radiation,
    get_surface_parameters,
)
from src.geo.snap_engine import (
    EARTH_RADIUS_METERS,
    extract_unique_nodes_from_edges,
    haversine_distance,
    snap_to_existing_nodes,
)

__all__ = [
    # 거리 및 스냅 엔진
    "EARTH_RADIUS_METERS",
    "haversine_distance",
    "extract_unique_nodes_from_edges",
    "snap_to_existing_nodes",
    # OSM 노면 파서
    "fetch_osm_elements_around",
    "infer_surface_type",
    # 복사열 및 열부하 엔진
    "SURFACE_PROPERTIES",
    "get_surface_parameters",
    "calculate_net_radiation",
    "calculate_heat_stress_index",
    # 고도 및 경사도 엔진
    "query_online_elevation",
    "get_point_elevation",
    "calculate_segment_elevation_metrics",
]