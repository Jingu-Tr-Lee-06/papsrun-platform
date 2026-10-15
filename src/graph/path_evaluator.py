"""PAPSrun 최적 러닝 경로 다면 평가 엔진 모듈.

다익스트라 알고리즘에 의해 도출된 노드 시퀀스(Node Path)를 순회하며
총 연장 거리, 누적 상승/하강 고도, 평균 경사도, 그늘 구간 비율,
노면 재질 구성비 및 열환경 지표를 종합 산출하고 요약 보고서를 생성합니다.
"""

from typing import Any, Dict, List, Optional
import networkx as nx


def evaluate_route_metrics(G: nx.MultiDiGraph, path_nodes: List[str]) -> Dict[str, Any]:
    """경로 노드 리스트를 바탕으로 종합 러닝 환경 지표를 산출합니다.

    Args:
        G: 도로망 MultiDiGraph
        path_nodes: 순서대로 정렬된 노드 ID 리스트 (예: ["N1", "N2", "N3"])

    Returns:
        종합 물리 지표 딕셔너리
    """
    metrics: Dict[str, Any] = {
        "is_valid": False,
        "node_count": len(path_nodes),
        "total_distance_m": 0.0,
        "elevation_gain_m": 0.0,
        "elevation_loss_m": 0.0,
        "avg_slope_pct": 0.0,
        "max_slope_pct": 0.0,
        "shade_ratio_pct": 0.0,
        "surface_distribution": {},
        "avg_net_radiation_rn": 0.0,
    }

    if not path_nodes or len(path_nodes) < 2:
        return metrics

    total_dist = 0.0
    total_gain = 0.0
    total_loss = 0.0
    slopes: List[float] = []
    shaded_dist = 0.0
    surface_dist_map: Dict[str, float] = {}
    total_rn_weighted = 0.0

    for i in range(len(path_nodes) - 1):
        u = path_nodes[i]
        v = path_nodes[i + 1]

        if not G.has_edge(u, v):
            continue

        # 다중 간선 중 첫 번째 간선 데이터 참조
        edge_data = G.get_edge_data(u, v)[0]

        length = float(edge_data.get("length", 0.0))
        slope = float(edge_data.get("slope", 0.0))
        is_shaded = bool(edge_data.get("is_shaded", False))
        surface = str(edge_data.get("surface_type", "asphalt_road"))
        rn = float(edge_data.get("net_radiation", 0.0))

        total_dist += length
        slopes.append(slope)

        # 고도 변화량 산출 (경사도 = 수직고도 / 수평거리 * 100)
        elev_change = (slope / 100.0) * length
        if elev_change > 0:
            total_gain += elev_change
        else:
            total_loss += abs(elev_change)

        if is_shaded:
            shaded_dist += length

        surface_dist_map[surface] = surface_dist_map.get(surface, 0.0) + length
        total_rn_weighted += rn * length

    if total_dist > 0.0:
        metrics["is_valid"] = True
        metrics["total_distance_m"] = round(total_dist, 2)
        metrics["elevation_gain_m"] = round(total_gain, 2)
        metrics["elevation_loss_m"] = round(total_loss, 2)
        metrics["avg_slope_pct"] = round(sum(slopes) / len(slopes), 2) if slopes else 0.0
        metrics["max_slope_pct"] = round(max([abs(s) for s in slopes]), 2) if slopes else 0.0
        metrics["shade_ratio_pct"] = round((shaded_dist / total_dist) * 100.0, 1)

        # 노면 구성 비율 계산
        metrics["surface_distribution"] = {
            surf: round((dist / total_dist) * 100.0, 1)
            for surf, dist in surface_dist_map.items()
        }

        metrics["avg_net_radiation_rn"] = round(total_rn_weighted / total_dist, 2)

    return metrics


# 상호 호환 별칭 (tab3_vibe_optimizer 및 외부 호출부 대응)
evaluate_running_path = evaluate_route_metrics
evaluate_path = evaluate_route_metrics


def format_route_summary(metrics: Dict[str, Any]) -> str:
    """산출된 지표 딕셔너리를 학생 피드백용 텍스트 요약본으로 변환합니다."""
    if not metrics.get("is_valid", False):
        return "유효한 경로가 형성되지 않았거나 노드 수가 부족합니다."

    dist_km = metrics["total_distance_m"] / 1000.0
    summary = (
        f"총 거리: {metrics['total_distance_m']:.1f}m ({dist_km:.2f}km) | "
        f"누적 상승: +{metrics['elevation_gain_m']:.1f}m | "
        f"누적 하강: -{metrics['elevation_loss_m']:.1f}m | "
        f"그늘 비율: {metrics['shade_ratio_pct']}% | "
        f"평균 순복사(Rn): {metrics['avg_net_radiation_rn']:.1f} W/m²"
    )
    return summary