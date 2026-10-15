"""지리공간(GIS) 하버사인 거리 계산 및 노드 자석 스냅(Snap) 엔진 모듈.

지구 구면체 상의 두 위경도 좌표 간 대원거리(Haversine Distance)를 미터(m) 단위로 정밀 산출하고,
학생이 작도한 좌표가 기존 노드 반경 임계치(기본 15m) 내에 위치할 경우
자동으로 기존 노드에 자석처럼 달라붙게 하여 도로망의 위상학적 단절을 방지합니다.
"""

from typing import Any, Dict, List, Optional, Tuple
import math

# 지구 평균 반경 (WGS-84 기준 미터 단위)
EARTH_RADIUS_METERS: float = 6371000.0

# 기본 자석 스냅 반경 (미터 단위)
DEFAULT_SNAP_THRESHOLD_METERS: float = 15.0


def calculate_haversine_distance(
    coord1: Tuple[float, float],
    coord2: Tuple[float, float],
) -> float:
    """하버사인 공식을 사용하여 두 위경도 좌표 간의 구면 거리(m)를 계산합니다.

    Args:
        coord1: (위도1, 경도1)
        coord2: (위도2, 경도2)

    Returns:
        두 지점 사이의 지표면 거리 (미터 단위, float)
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(EARTH_RADIUS_METERS * c, 2)


# 하위 호환 및 단축 명칭 별칭
haversine_distance = calculate_haversine_distance


def snap_to_existing_node(
    raw_coord: Tuple[float, float],
    existing_nodes: Dict[str, Tuple[float, float]],
    threshold_m: float = DEFAULT_SNAP_THRESHOLD_METERS,
) -> Tuple[str, Tuple[float, float]]:
    """입력된 좌표를 기존 노드 집합과 비교하여 임계 거리 이내면 기존 노드로 스냅합니다.

    Args:
        raw_coord: 새로 입력된 (위도, 경도)
        existing_nodes: {"node_id": (위도, 경도)} 형태의 기존 노드 딕셔너리
        threshold_m: 자석 스냅 유효 반경 (기본 15.0m)

    Returns:
        (노드 식별자, 최종 (위도, 경도))
    """
    if not existing_nodes:
        new_node_id = f"N_{raw_coord[0]:.5f}_{raw_coord[1]:.5f}"
        return new_node_id, raw_coord

    closest_node_id: Optional[str] = None
    min_distance = float("inf")

    for node_id, coord in existing_nodes.items():
        dist = calculate_haversine_distance(raw_coord, coord)
        if dist < min_distance:
            min_distance = dist
            closest_node_id = node_id

    # 가장 가까운 노드가 임계거리(15m) 이내인 경우 기존 노드로 스냅
    if min_distance <= threshold_m and closest_node_id is not None:
        return closest_node_id, existing_nodes[closest_node_id]

    # 임계거리 밖이면 신규 노드로 취급
    new_node_id = f"N_{raw_coord[0]:.5f}_{raw_coord[1]:.5f}"
    return new_node_id, raw_coord


# 복수형/단수형 호출 호환성 별칭
snap_to_existing_nodes = snap_to_existing_node


def extract_unique_nodes_from_edges(
    edges: List[Dict[str, Any]],
) -> Dict[str, Tuple[float, float]]:
    """간선 리스트를 순회하며 중복 없는 노드 ID와 위경도 좌표 딕셔너리를 추출합니다.

    Args:
        edges: 도로 간선 딕셔너리 리스트 (각 원소는 u, v, coord_u, coord_v 등을 포함)

    Returns:
        {node_id: (lat, lon)} 형태의 딕셔너리
    """
    nodes_dict: Dict[str, Tuple[float, float]] = {}

    for edge in edges:
        u = str(edge.get("u", "")).strip()
        v = str(edge.get("v", "")).strip()

        coord_u = edge.get("coord_u")
        if u and coord_u and isinstance(coord_u, (list, tuple)) and len(coord_u) >= 2:
            nodes_dict[u] = (float(coord_u[0]), float(coord_u[1]))

        coord_v = edge.get("coord_v")
        if v and coord_v and isinstance(coord_v, (list, tuple)) and len(coord_v) >= 2:
            nodes_dict[v] = (float(coord_v[0]), float(coord_v[1]))

    return nodes_dict