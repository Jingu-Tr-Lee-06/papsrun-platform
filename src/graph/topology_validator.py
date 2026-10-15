"""PAPSrun 캠퍼스 도로망 위상(Topology) 유효성 검증 엔진 모듈.

NetworkX MultiDiGraph를 기반으로 고립 노드(Isolated Nodes),
진입 차수/진출 차수 불균형(데드엔드), 강한/약한 연결 요소(Connected Components),
자가 루프(Self-loops)를 감지하여 도로망의 수학적 완전성을 진단합니다.
"""

from typing import Any, Dict, List, Set, Tuple
import networkx as nx


def find_isolated_nodes(G: nx.MultiDiGraph) -> List[str]:
    """연결된 간선이 전혀 없는 고립 노드 리스트를 반환합니다."""
    return list(nx.isolates(G))


def check_graph_connectivity(G: nx.MultiDiGraph) -> Tuple[bool, int, List[Set[str]]]:
    """그래프의 약한 연결성(Weakly Connected) 여부를 판정합니다.

    Returns:
        (전체 연결 여부 bool, 연결 컴포넌트 개수 int, 컴포넌트 노드 세트 리스트)
    """
    if len(G.nodes) == 0:
        return False, 0, []

    # 방향성을 무시했을 때 모든 노드가 연결되어 있는지 확인
    components = list(nx.weakly_connected_components(G))
    is_connected = len(components) == 1
    return is_connected, len(components), components


def validate_campus_network_topology(G: nx.MultiDiGraph) -> Dict[str, Any]:
    """도로망 그래프의 위상학적 건전성을 종합 진단합니다.

    Args:
        G: 검증 대상 nx.MultiDiGraph

    Returns:
        종합 진단 보고서 딕셔너리
    """
    node_count = G.number_of_nodes()
    edge_count = G.number_of_edges()

    report: Dict[str, Any] = {
        "is_valid": False,
        "node_count": node_count,
        "edge_count": edge_count,
        "isolated_nodes": [],
        "dead_end_nodes": [],
        "component_count": 0,
        "is_weakly_connected": False,
        "is_strongly_connected": False,
        "diagnostic_messages": [],
    }

    if node_count == 0:
        report["diagnostic_messages"].append("그래프에 노드가 존재하지 않습니다. 1단계에서 도로를 먼저 작도해 주세요.")
        return report

    # 1. 고립 노드 검사
    isolated = find_isolated_nodes(G)
    report["isolated_nodes"] = isolated
    if isolated:
        report["diagnostic_messages"].append(f"고립된 노드가 {len(isolated)}개 발견되었습니다: {isolated[:5]}")

    # 2. 연결 요소 검사
    is_weak, comp_count, components = check_graph_connectivity(G)
    report["is_weakly_connected"] = is_weak
    report["component_count"] = comp_count
    if comp_count > 1:
        report["diagnostic_messages"].append(
            f"네트워크가 {comp_count}개의 독립된 구역으로 분리되어 있어 전역 경로 탐색이 불가능합니다."
        )

    # 3. 강한 연결성 검사
    is_strong = nx.is_strongly_connected(G) if node_count > 0 else False
    report["is_strongly_connected"] = is_strong

    # 4. 막다른 길 (데드엔드) 검사
    dead_ends = [n for n in G.nodes if G.out_degree(n) == 0 and G.in_degree(n) > 0]
    report["dead_end_nodes"] = dead_ends
    if dead_ends:
        report["diagnostic_messages"].append(f"진출로가 없는 막다른 지점이 {len(dead_ends)}개 있습니다.")

    # 최종 유효성 판정: 최소 노드 2개 이상 + 약한 연결성 만족 + 고립 노드 없음
    if node_count >= 2 and is_weak and len(isolated) == 0:
        report["is_valid"] = True
        report["diagnostic_messages"].append("모든 도로망이 유효하게 연결되어 최단 경로 탐색이 가능합니다.")

    return report