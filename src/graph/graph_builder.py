"""PAPSrun NetworkX 캠퍼스 도로망 그래프 합성 모듈.

수집된 도로 간선(Edges) 및 노드(Nodes) 데이터를 바탕으로
방향성 다중 그래프(MultiDiGraph)를 생성하고,
최단경로 및 바이브 코딩 비용 계산에 필요한 지리·물리 메타데이터를 속성으로 주입합니다.
"""

from typing import Any, Dict, List, Optional, Tuple
import networkx as nx

from src.geo.snap_engine import calculate_haversine_distance


def build_campus_multidigraph(
    edges: List[Dict[str, Any]],
) -> Tuple[nx.MultiDiGraph, Dict[str, Tuple[float, float]]]:
    """도로 간선 리스트를 입력받아 NetworkX MultiDiGraph와 노드 좌표 딕셔너리를 반환합니다.

    Args:
        edges: 도로 간선 딕셔너리 리스트.

    Returns:
        (G, nodes_dict) 튜플:
        - G: 노드 좌표 및 환경물리 속성이 주입된 nx.MultiDiGraph
        - nodes_dict: {node_id: (lat, lon)} 매핑 테이블
    """
    G = nx.MultiDiGraph()
    nodes_dict: Dict[str, Tuple[float, float]] = {}

    for edge in edges:
        u = str(edge.get("u", "")).strip()
        v = str(edge.get("v", "")).strip()

        if not u or not v:
            continue

        # 신/구버전 키 호환 (u_coords 또는 coord_u)
        coord_u = edge.get("u_coords") or edge.get("coord_u")
        coord_v = edge.get("v_coords") or edge.get("coord_v")

        # 노드 좌표 속성 주입 및 nodes_dict 기록
        if coord_u and isinstance(coord_u, (list, tuple)) and len(coord_u) >= 2:
            lat_u, lon_u = float(coord_u[0]), float(coord_u[1])
            nodes_dict[u] = (lat_u, lon_u)
            if u not in G.nodes:
                G.add_node(u, pos=(lat_u, lon_u), lat=lat_u, lon=lon_u)

        if coord_v and isinstance(coord_v, (list, tuple)) and len(coord_v) >= 2:
            lat_v, lon_v = float(coord_v[0]), float(coord_v[1])
            nodes_dict[v] = (lat_v, lon_v)
            if v not in G.nodes:
                G.add_node(v, pos=(lat_v, lon_v), lat=lat_v, lon=lon_v)

        # 길이(m) 누락 시 하버사인 거리 자동 산출
        length = edge.get("length_m") or edge.get("length")
        if length is None or float(length) <= 0.0:
            if coord_u and coord_v:
                length = calculate_haversine_distance(
                    (float(coord_u[0]), float(coord_u[1])),
                    (float(coord_v[0]), float(coord_v[1])),
                )
            else:
                length = 10.0
        else:
            length = float(length)

        slope = float(edge.get("slope_pct", edge.get("slope", 0.0)))
        surface = str(edge.get("surface_type", "concrete_walkway"))
        is_shaded = bool(edge.get("is_shaded", False))
        net_radiation = float(edge.get("absorbed_rad_w_m2", edge.get("net_radiation", 0.0)))
        albedo = float(edge.get("albedo", 0.15))
        is_bidirectional = bool(edge.get("is_bidirectional", True))

        edge_attrs = {
            "edge_id": edge.get("edge_id", f"{u}__{v}"),
            "length": length,
            "slope": slope,
            "surface_type": surface,
            "is_shaded": is_shaded,
            "net_radiation": net_radiation,
            "absorbed_rad_w_m2": net_radiation,
            "albedo": albedo,
            "coord_u": coord_u,
            "coord_v": coord_v,
        }

        # 정방향 (u -> v) 간선 추가
        G.add_edge(u, v, **edge_attrs)

        # 양방향 구간인 경우 역방향 (v -> u) 추가 (경사도는 역부호)
        if is_bidirectional:
            rev_attrs = dict(edge_attrs)
            rev_attrs["edge_id"] = f"{v}__{u}"
            rev_attrs["slope"] = -slope
            rev_attrs["coord_u"] = coord_v
            rev_attrs["coord_v"] = coord_u
            G.add_edge(v, u, **rev_attrs)

    return G, nodes_dict


# 별칭(Alias) 등록: build_graph_from_edges 호출 호환
build_graph_from_edges = build_campus_multidigraph