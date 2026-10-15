"""PAPS 체력 지표 및 경로 비교 평가 시각화 카드 컴포넌트.

최단거리 경로, 쾌적 경로, 바이브 코딩 최적화 경로의 정량 지표
(총 거리, 획득 고도, 소모 열량, 평균 심박수, 열복사 노출량)를
다채널 비교 카드 및 노면 피복 비율 게이지 바 형태로 시각화합니다.
"""

from typing import Any, Dict, List, Optional
import streamlit as st


def render_paps_fitness_card(metrics: Dict[str, Any], path_name: str = "선택된 경로") -> None:
    """단일 경로의 핵심 생체역학/물리 환경 지표를 4분할 카드로 렌더링합니다.

    Args:
        metrics: evaluate_running_path()에서 도출된 결과 딕셔너리
        path_name: 경로 명칭
    """
    total_dist = metrics.get("total_distance_m", 0.0)
    elev_gain = metrics.get("elevation_gain_m", 0.0)
    calories = metrics.get("calories_burned_kcal", 0.0)
    est_bpm = metrics.get("estimated_avg_bpm", 0)
    avg_rn = metrics.get("avg_net_rn", 0.0)
    shaded_ratio = metrics.get("shaded_ratio_pct", 0.0)

    st.markdown(f"##### 📊 {path_name} 운동역학 지표")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="총 이동 거리", value=f"{total_dist:.1f} m")
    with col2:
        st.metric(label="누적 획득 고도", value=f"{elev_gain:.1f} m")
    with col3:
        st.metric(label="예상 소모 열량", value=f"{calories:.1f} kcal")
    with col4:
        st.metric(label="추정 평균 심박수", value=f"{est_bpm} BPM")

    env_col1, env_col2 = st.columns(2)
    with env_col1:
        st.info(f"☀️ **평균 순복사에너지 (Rn):** `{avg_rn:.1f} W/m²`")
    with env_col2:
        st.success(f"🌳 **그늘 구간 비율:** `{shaded_ratio:.1f} %`")


def render_comparative_metrics_card(
    shortest_metrics: Optional[Dict[str, Any]],
    comfort_metrics: Optional[Dict[str, Any]],
    vibe_metrics: Optional[Dict[str, Any]],
) -> None:
    """최단거리, 쾌적, 바이브 코딩 경로의 주요 지표를 3단 대조표 형식으로 렌더링합니다.

    Args:
        shortest_metrics: 최단거리 경로 평가 결과
        comfort_metrics: 쾌적 경로 평가 결과
        vibe_metrics: 바이브 코딩 최적화 경로 평가 결과
    """
    st.markdown("#### ⚖️ 다익스트라 경로 특성 3방향 대조 분석")

    col_labels = ["지표 항목", "1. 최단거리 경로", "2. 쾌적 경로 (그늘/평지)", "3. 바이브 코딩 최적화"]
    
    def _extract_row(m: Optional[Dict[str, Any]]) -> Dict[str, str]:
        if not m:
            return {"dist": "-", "elev": "-", "cal": "-", "bpm": "-", "shade": "-", "rn": "-"}
        return {
            "dist": f"{m.get('total_distance_m', 0.0):.1f} m",
            "elev": f"{m.get('elevation_gain_m', 0.0):.1f} m",
            "cal": f"{m.get('calories_burned_kcal', 0.0):.1f} kcal",
            "bpm": f"{m.get('estimated_avg_bpm', 0)} BPM",
            "shade": f"{m.get('shaded_ratio_pct', 0.0):.1f} %",
            "rn": f"{m.get('avg_net_rn', 0.0):.1f} W/m²",
        }

    s_row = _extract_row(shortest_metrics)
    c_row = _extract_row(comfort_metrics)
    v_row = _extract_row(vibe_metrics)

    comparison_data = [
        {"항목": "총 이동 거리", "최단거리": s_row["dist"], "쾌적 경로": c_row["dist"], "바이브 코딩": v_row["dist"]},
        {"항목": "누적 오르막(고도)", "최단거리": s_row["elev"], "쾌적 경로": c_row["elev"], "바이브 코딩": v_row["elev"]},
        {"항목": "추정 소모 열량", "최단거리": s_row["cal"], "쾌적 경로": c_row["cal"], "바이브 코딩": v_row["cal"]},
        {"항목": "추정 평균 심박수", "최단거리": s_row["bpm"], "쾌적 경로": c_row["bpm"], "바이브 코딩": v_row["bpm"]},
        {"항목": "그늘 구간 비율", "최단거리": s_row["shade"], "쾌적 경로": c_row["shade"], "바이브 코딩": v_row["shade"]},
        {"항목": "순복사에너지 노출량", "최단거리": s_row["rn"], "쾌적 경로": c_row["rn"], "바이브 코딩": v_row["rn"]},
    ]

    st.table(comparison_data)


def render_surface_breakdown_widget(surface_dist: Dict[str, float]) -> None:
    """노면 재질별 구성비를 프로그레스 바 형태로 시각화합니다.

    Args:
        surface_dist: {노면타입: 백분율(%)} 딕셔너리
    """
    if not surface_dist:
        st.caption("경로 상에 등록된 노면 데이터가 없습니다.")
        return

    st.markdown("##### 🛣️ 통과 노면 재질 구성비")

    name_map = {
        "urethane_track": "우레탄 트랙",
        "soil_trail": "흙길 산책로",
        "lawn_grass": "잔디",
        "concrete_walkway": "보도블록/콘크리트",
        "asphalt_aged": "노후 아스팔트",
        "asphalt_dark": "신설 아스팔트",
    }

    cols = st.columns(len(surface_dist))
    for idx, (surf_key, pct) in enumerate(surface_dist.items()):
        label = name_map.get(surf_key, surf_key)
        with cols[idx]:
            st.metric(label=label, value=f"{pct:.1f}%")
            norm_val = min(1.0, max(0.0, pct / 100.0))
            st.progress(norm_val)