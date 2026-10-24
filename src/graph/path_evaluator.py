"""PAPSrun 최적 러닝 경로 다면 평가 엔진 모듈.

다익스트라 알고리즘에 의해 도출된 노드 시퀀스(Node Path)를 순회하며
총 연장 거리, 누적 상승/하강 고도, 평균 경사도, 그늘 구간 비율,
노면 재질 구성비 및 기상청 연동 순흡수 복사에너지(R_abs),
PAPS 심폐소생 러닝 부하(추정 심박수, 소모 칼로리, 열부하 지수)를 종합 산출합니다.
"""

from typing import Any, Dict, List, Optional
import networkx as nx


def evaluate_route_metrics(
    G: nx.MultiDiGraph,
    path_nodes: List[str],
    weather_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """경로 노드 리스트를 바탕으로 종합 생체역학 및 환경 지표를 산출합니다.

    Args:
        G: 도로망 MultiDiGraph
        path_nodes: 순서대로 정렬된 노드 ID 리스트 (예: ["N1", "N2", "N3"])
        weather_info: 기상청/교사 Override 기상 정보 (기온, 일사량 등)

    Returns:
        종합 물리·생체역학 지표 딕셔너리
    """
    metrics: Dict[str, Any] = {
        "is_valid": False,
        "node_count": len(path_nodes) if path_nodes else 0,
        "total_distance_m": 0.0,
        "elevation_gain_m": 0.0,
        "elevation_loss_m": 0.0,
        "avg_slope_pct": 0.0,
        "max_slope_pct": 0.0,
        "shaded_ratio_pct": 0.0,
        "shade_ratio_pct": 0.0,  # 하위 호환
        "surface_distribution": {},
        "avg_absorbed_radiation": 0.0,
        "avg_net_radiation_rn": 0.0,  # 하위 호환
        "ambient_temp_c": 20.0,
        "estimated_avg_bpm": 135,
        "calories_burned_kcal": 0.0,
        "thermal_stress_index": 0.0,
    }

    if not path_nodes or len(path_nodes) < 2:
        return metrics

    # 기상 환경 반영
    weather = weather_info or {}
    ambient_temp = float(weather.get("air_temp_c", weather.get("temp_c", 20.0)))
    solar_rad = float(weather.get("solar_rad", weather.get("solar_w_m2", 700.0)))
    metrics["ambient_temp_c"] = ambient_temp

    total_dist = 0.0
    total_gain = 0.0
    total_loss = 0.0
    slopes: List[float] = []
    shaded_dist = 0.0
    surface_dist_map: Dict[str, float] = {}
    total_rabs_weighted = 0.0

    for i in range(len(path_nodes) - 1):
        u = path_nodes[i]
        v = path_nodes[i + 1]

        if not G.has_edge(u, v):
            continue

        edge_data = G.get_edge_data(u, v)[0]

        length = float(edge_data.get("length", 0.0))
        slope = float(edge_data.get("slope", 0.0))
        is_shaded = bool(edge_data.get("is_shaded", False))
        surface = str(edge_data.get("surface_type", "asphalt_road"))

        # 💡 지표 순흡수 복사에너지(R_abs): 간선 데이터 우선, 없으면 기상청 기반 산출
        r_abs = float(edge_data.get("absorbed_rad_w_m2", edge_data.get("net_radiation", 0.0)))
        if r_abs <= 0.0 and solar_rad > 0.0:
            albedo = float(edge_data.get("albedo", 0.15))
            canopy = 0.70 if is_shaded else 0.0
            r_abs = solar_rad * (1.0 - canopy) * (1.0 - albedo)

        total_dist += length
        slopes.append(slope)

        # 경사도에 따른 수직 고도 증감 산출
        elev_change = (slope / 100.0) * length
        if elev_change > 0:
            total_gain += elev_change
        else:
            total_loss += abs(elev_change)

        if is_shaded:
            shaded_dist += length

        surface_dist_map[surface] = surface_dist_map.get(surface, 0.0) + length
        total_rabs_weighted += r_abs * length

    if total_dist > 0.0:
        metrics["is_valid"] = True
        metrics["total_distance_m"] = round(total_dist, 2)
        metrics["elevation_gain_m"] = round(total_gain, 2)
        metrics["elevation_loss_m"] = round(total_loss, 2)
        metrics["avg_slope_pct"] = round(sum(slopes) / len(slopes), 2) if slopes else 0.0
        metrics["max_slope_pct"] = round(max([abs(s) for s in slopes]), 2) if slopes else 0.0

        shade_pct = round((shaded_dist / total_dist) * 100.0, 1)
        metrics["shaded_ratio_pct"] = shade_pct
        metrics["shade_ratio_pct"] = shade_pct

        metrics["surface_distribution"] = {
            surf: round((dist / total_dist) * 100.0, 1)
            for surf, dist in surface_dist_map.items()
        }

        avg_rabs = round(total_rabs_weighted / total_dist, 1)
        metrics["avg_absorbed_radiation"] = avg_rabs
        metrics["avg_net_radiation_rn"] = avg_rabs

        # 💡 PAPS 생체역학 연산: 러닝 추정 심박수 및 칼로리 (체육-지구과학 융합 수리 모델)
        # 기본 평지 러닝 심박수 135 BPM 기준, 경사도와 기온, 복사에너지 가산
        slope_penalty = max(0.0, metrics["avg_slope_pct"]) * 2.2
        heat_penalty = max(0.0, (ambient_temp - 24.0)) * 1.5 + (avg_rabs / 250.0) * 3.0
        estimated_bpm = int(round(135.0 + slope_penalty + heat_penalty))
        metrics["estimated_avg_bpm"] = min(190, max(110, estimated_bpm))

        # 추정 칼로리 (체중 60kg 고등학생 기준 평지 러닝 METs 8.0 + 경사도 반영)
        duration_hours = (total_dist / 1000.0) / 9.0  # 평균 시속 9km/h 러닝 가정
        mets = 8.0 + (metrics["avg_slope_pct"] * 0.15)
        calories = mets * 60.0 * duration_hours * 1.05
        metrics["calories_burned_kcal"] = round(calories, 1)

        # 열부하 지수 (Thermal Stress Index)
        thermal_stress = (ambient_temp * 0.6) + ((avg_rabs / 100.0) * 0.4)
        metrics["thermal_stress_index"] = round(thermal_stress, 1)

    return metrics


# 상호 호환 별칭 (tab3, tab5 및 외부 호출 호환)
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
        f"그늘 비율: {metrics['shaded_ratio_pct']}% | "
        f"평균 흡수 복사에너지: {metrics['avg_absorbed_radiation']:.1f} W/m² | "
        f"예상 심박수: {metrics['estimated_avg_bpm']} BPM | "
        f"소모 열량: {metrics['calories_burned_kcal']:.1f} kcal"
    )
    return summary