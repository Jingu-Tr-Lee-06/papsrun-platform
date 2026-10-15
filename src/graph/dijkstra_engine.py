"""PAPSrun NetworkX 기반 다익스트라(Dijkstra) 다목적 경로 최적화 엔진 모듈.

순수 물리 거리 경로뿐만 아니라 일사량(그늘), 노면 충격 흡수율(우레탄/트랙),
경사도 페널티를 종합 반영한 쾌적 러닝 경로(Comfort Path) 및
학생 커스텀 가중치 경로를 계산합니다.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import networkx as nx

from src.graph.dijkstra_router import run_dijkstra_with_custom_weight


def calculate_distance_cost(u: str, v: str, edge_dict: Dict[str, Any]) -> float:
    """순수 거리(m) 기준 가중치."""
    length = float(edge_dict.get("length", 1.0))
    return max(0.1, length)


def calculate_comfort_cost(u: str, v: str, edge_dict: Dict[str, Any]) -> float:
    """쾌적 러닝 기준 종합 가중치 비용을 산출합니다.

    - 그늘 구간: 가중치 30% 감면
    - 우레탄/흙길 노면: 충격 흡수로 가중치 감면 (아스팔트/콘크리트 대비 우대)
    - 급경사 오르막: 에너지 소모 페널티 가산
    - 순복사에너지(Rn): 열부하 페널티 가산
    """
    length = float(edge_dict.get("length", 1.0))
    slope = float(edge_dict.get("slope", 0.0))
    is_shaded = bool(edge_dict.get("is_shaded", False))
    surface = str(edge_dict.get("surface_type", "asphalt_road"))
    rn = float(edge_dict.get("net_radiation", 0.0))

    cost = length

    # 1. 일사 및 그늘 보정
    if is_shaded:
        cost *= 0.7
    elif rn > 400:  # 고열환경 직사광선 노출 시 페널티
        cost *= 1.25

    # 2. 노면 충격 완화 보정
    surface_multipliers = {
        "urethane_track": 0.75,
        "clay_ground": 0.85,
        "asphalt_road": 1.0,
        "concrete_walkway": 1.1,
        "block_pavement": 1.15,
    }
    cost *= surface_multipliers.get(surface, 1.0)

    # 3. 경사도 보정 (오르막 페널티, 가파른 내리막 무릎 부담 페널티)
    if slope > 3.0:
        cost *= (1.0 + (slope / 10.0))
    elif slope < -8.0:
        cost *= 1.15

    return max(0.1, cost)


def find_shortest_path(
    G: nx.MultiDiGraph,
    source_node: str,
    target_node: str,
) -> Tuple[List[str], float]:
    """최단 거리 기준 경로를 탐색합니다."""
    return run_dijkstra_with_custom_weight(
        G=G,
        source_node=source_node,
        target_node=target_node,
        weight_func=calculate_distance_cost,
    )


def find_comfort_path(
    G: nx.MultiDiGraph,
    source_node: str,
    target_node: str,
) -> Tuple[List[str], float]:
    """열부하 및 관절 부담을 최소화하는 쾌적 경로(Comfort Path)를 탐색합니다."""
    return run_dijkstra_with_custom_weight(
        G=G,
        source_node=source_node,
        target_node=target_node,
        weight_func=calculate_comfort_cost,
    )


def find_custom_weight_path(
    G: nx.MultiDiGraph,
    source_node: str,
    target_node: str,
    custom_func: Callable[[str, str, Dict[str, Any]], float],
) -> Tuple[List[str], float]:
    """학생이 직접 작성한 바이브 코딩 가중치 함수를 주입하여 최적 경로를 탐색합니다."""
    return run_dijkstra_with_custom_weight(
        G=G,
        source_node=source_node,
        target_node=target_node,
        weight_func=custom_func,
    )


# 호출 별칭 (과거/현재 명칭 양방향 호환)
find_custom_weighted_path = find_custom_weight_path