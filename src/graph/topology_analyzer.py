"""도로망 그래프 위상(Topology) 진단 및 무결성 검증 모듈.

NetworkX MultiDiGraph의 구조적 무결성을 분석하여,
1) 다른 경로와 단절된 고립 노드(Isolated Nodes)
2) 네트워크가 분리된 개별 서브그래프(Connected Components)
3) 진입/진출만 가능한 편도 및 막다른 길(Dead-ends)
등을 탐지하고 시각화 및 디버깅을 위한 진단 리포트를 생성합니다.
"""

from typing import Any, Dict, List, Set, Tuple
import networkx as nx


def analyze_graph_topology(g: nx.MultiDiGraph) -> Dict[str, Any]:
    """그래프의 위상 연결성을 다각도로 분석하여 진단 지표를 도출합니다.

    Args:
        g: 분석 대상 nx.MultiDiGraph 인스턴스

    Returns:
        {
            "total_nodes": int,
            "total_edges": int,
            "is_fully_connected": bool,
            "component_count": int,
            "components": List[List[str]],
            "isolated_nodes": List[str],
            "dead_ends": List[str],
            "diagnosis_message": str,
            "health_score": int (0~100)
        }
    """
    total_nodes = g.number_of_nodes()
    total_edges = g.number_of_edges()

    if total_nodes == 0:
        return {
            "total_nodes": 0,
            "total_edges": 0,
            "is_fully_connected": False,
            "component_count": 0,
            "components": [],
            "isolated_nodes": [],
            "dead_ends": [],
            "diagnosis_message": "등록된 노드와 도로가 없습니다. 1단계에서 도로를 작도해 주세요.",
            "health_score": 0,
        }

    # 1. 고립 노드 검출 (차수가 0인 노드)
    isolated_nodes = list(nx.isolates(g))

    # 2. 약한 연결 컴포넌트(Weakly Connected Components) 분할
    # 보행로는 무방향 통행으로 간주하여 연결성을 판정
    weak_components = [list(c) for c in nx.weakly_connected_components(g)]
    component_count = len(weak_components)
    is_fully_connected = component_count == 1 and len(isolated_nodes) == 0

    # 3. 막다른 노드(Dead-ends) 검출: 연결된 간선이 1개뿐인 끝점
    dead_ends: List[str] = []
    for node in g.nodes():
        # 순방향 기준 진입 차수와 진출 차수 종합 점검
        degree = g.degree(node)
        # 양방향 등록 구조이므로 degree가 2이면 실제로는 1개의 물리적 도로에만 붙어있는 끝점
        if degree <= 2 and node not in isolated_nodes:
            dead_ends.append(node)

    # 4. 건강도 점수(Health Score, 0~100) 및 진단 피드백 산출
    health_score = 100
    diagnostic_notes = []

    if component_count > 1:
        penalty = min(50, (component_count - 1) * 15)
        health_score -= penalty
        diagnostic_notes.append(
            f"네트워크가 {component_count}개의 분리된 구역으로 단절되어 있습니다. 모둠 간 경계 도로를 연결해 주세요."
        )

    if isolated_nodes:
        penalty = min(30, len(isolated_nodes) * 10)
        health_score -= penalty
        diagnostic_notes.append(
            f"완전히 단절된 고립 노드가 {len(isolated_nodes)}개 발견되었습니다."
        )

    if not diagnostic_notes:
        diagnostic_notes.append("모든 도로망이 유기적으로 잘 연결되어 있습니다. 다익스트라 최적화 수행이 가능합니다.")

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "is_fully_connected": is_fully_connected,
        "component_count": component_count,
        "components": weak_components,
        "isolated_nodes": isolated_nodes,
        "dead_ends": dead_ends,
        "diagnosis_message": " ".join(diagnostic_notes),
        "health_score": max(0, health_score),
    }


def find_bridge_candidates(
    g: nx.MultiDiGraph,
    max_gap_meters: float = 30.0,
) -> List[Dict[str, Any]]:
    """서로 단절된 컴포넌트 간에 가장 가까운 노드 쌍을 탐색하여 연결 후보를 제시합니다.

    Args:
        g: 대상 nx.MultiDiGraph
        max_gap_meters: 다리(Bridge)로 연결 가능한 최대 간격 (m)

    Returns:
        추천 연결 간선 딕셔너리 리스트:
        [{'u': node_id_1, 'v': node_id_2, 'distance_m': float, 'u_pos': tuple, 'v_pos': tuple}]
    """
    from src.geo.snap_engine import haversine_distance

    components = [list(c) for c in nx.weakly_connected_components(g)]
    if len(components) <= 1:
        return []

    bridge_candidates: List[Dict[str, Any]] = []

    # 주 컴포넌트(가장 큰 구역)와 부 컴포넌트들 간의 최단 거리 노드 쌍 탐색
    components.sort(key=len, reverse=True)
    main_comp = components[0]

    for other_comp in components[1:]:
        best_pair = None
        min_dist = float("inf")

        for u in main_comp:
            u_data = g.nodes[u]
            u_lat, u_lon = u_data.get("lat"), u_data.get("lon")
            if u_lat is None or u_lon is None:
                continue

            for v in other_comp:
                v_data = g.nodes[v]
                v_lat, v_lon = v_data.get("lat"), v_data.get("lon")
                if v_lat is None or v_lon is None:
                    continue

                d = haversine_distance(u_lat, u_lon, v_lat, v_lon)
                if d < min_dist:
                    min_dist = d
                    best_pair = {
                        "u": u,
                        "v": v,
                        "distance_m": round(d, 2),
                        "u_coords": (u_lat, u_lon),
                        "v_coords": (v_lat, v_lon),
                    }

        if best_pair and min_dist <= max_gap_meters:
            bridge_candidates.append(best_pair)

    return bridge_candidates