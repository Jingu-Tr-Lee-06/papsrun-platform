"""NetworkX 기반 다익스트라(Dijkstra) 경로 최적화 라우터 모듈.

학생이 AI 바이브 코딩 및 VS Code 워크스페이스에서 정의한 동적 가중치 함수
custom_weight_function(u, v, edge_dict)을 NetworkX 그래프 탐색 시 주입하여,
거리·경사도·그늘·노면 특성이 복합 반영된 최적 러닝 경로 노드 시퀀스를 산출합니다.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import networkx as nx


def _default_weight_function(u: str, v: str, edge_dict: Dict[str, Any]) -> float:
    """기본 거리 기반 가중치 함수 (폴백용)."""
    length = float(edge_dict.get("length", 1.0))
    return max(0.1, length)


def run_dijkstra_with_custom_weight(
    G: nx.MultiDiGraph,
    source_node: str,
    target_node: str,
    weight_func: Optional[Callable[[str, str, Dict[str, Any]], float]] = None,
) -> Tuple[List[str], float]:
    """커스텀 가중치 함수를 적용하여 시작 노드부터 도착 노드까지의 최적 경로를 산출합니다.

    Args:
        G: 캠퍼스 도로망 nx.MultiDiGraph
        source_node: 출발 노드 ID
        target_node: 도착 노드 ID
        weight_func: (u, v, edge_dict) -> float 형태의 가중치 산출 함수

    Returns:
        (노드 ID 경로 리스트, 총 누적 가중치 비용)
    """
    if source_node not in G or target_node not in G:
        raise ValueError(f"출발 노드({source_node}) 또는 도착 노드({target_node})가 그래프에 존재하지 않습니다.")

    effective_weight_func = weight_func if callable(weight_func) else _default_weight_function

    def nx_edge_weight(u: str, v: str, edge_dict: Dict[str, Any]) -> float:
        try:
            val = float(effective_weight_func(u, v, edge_dict))
            return max(0.001, val)
        except Exception:
            return float(edge_dict.get("length", 1.0))

    try:
        path = nx.shortest_path(
            G,
            source=source_node,
            target=target_node,
            weight=nx_edge_weight,
            method="dijkstra",
        )
        cost = nx.shortest_path_length(
            G,
            source=source_node,
            target=target_node,
            weight=nx_edge_weight,
            method="dijkstra",
        )
        return path, float(cost)
    except nx.NetworkXNoPath:
        return [], float("inf")


# 별칭 등록: find_optimal_path 호출 호환
find_optimal_path = run_dijkstra_with_custom_weight