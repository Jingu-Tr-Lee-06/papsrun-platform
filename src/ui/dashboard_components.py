"""대시보드 공통 UI 컴포넌트 및 시각화 모듈.

Streamlit 대시보드에서 활용되는 지표 카드, 노면 구성 비율 차트,
경로 고도 프로파일 요약, 위상 건강도 배지 등 재사용 가능한 시각화 요소를 렌더링합니다.
"""

from typing import Any, Dict, List
import streamlit as st


def render_metric_cards(metrics: Dict[str, Any]) -> None:
    """러닝 경로 평가 핵심 지표(거리, 고도, 칼로리, 심박수)를 4분할 카드로 표시합니다.

    Args:
        metrics: evaluate_running_path()에서 도출된 결과 딕셔너리
    """
    col1, col2, col3, col4 = st.columns(4)

    total_dist = metrics.get("total_distance_m", 0.0)
    elev_gain = metrics.get("elevation_gain_m", 0.0)
    calories = metrics.get("calories_burned_kcal", 0.0)
    est_bpm = metrics.get("estimated_avg_bpm", 0)

    with col1:
        st.metric(
            label="총 이동 거리",
            value=f"{total_dist:.1f} m",
            help="도로 곡선 및 경사도를 반영한 총 지표 이동 거리입니다.",
        )
    with col2:
        st.metric(
            label="누적 획득 고도",
            value=f"{elev_gain:.1f} m",
            help="경로 중 오르막 구간의 누적 수직 표고 상승량입니다.",
        )
    with col3:
        st.metric(
            label="추정 소모 열량",
            value=f"{calories:.1f} kcal",
            help="체중 65kg, 6분/km 페이스 및 지형 경사도 기반 대사 소모량입니다.",
        )
    with col4:
        st.metric(
            label="예상 평균 심박수",
            value=f"{est_bpm} BPM",
            help="기온, 열복사 플럭스(Rn), 경사도 부하를 통합한 추정 심박수입니다.",
        )


def render_environmental_summary(metrics: Dict[str, Any]) -> None:
    """순복사에너지(Rn)와 차광 비율 등 미기상 환경 지표를 렌더링합니다.

    Args:
        metrics: evaluate_running_path() 결과 딕셔너리
    """
    avg_rn = metrics.get("avg_net_rn", 0.0)
    shaded_ratio = metrics.get("shaded_ratio_pct", 0.0)

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"☀️ **평균 순복사에너지 (Rn):** `{avg_rn:.1f} W/m²`")
    with col2:
        st.success(f"🌳 **그늘 구간 비율:** `{shaded_ratio:.1f} %`")


def render_surface_distribution_bar(surface_dist: Dict[str, float]) -> None:
    """노면 재질별 구성비를 프로그레스 바 형태로 렌더링합니다.

    Args:
        surface_dist: {노면타입: 백분율(%)} 딕셔너리
    """
    if not surface_dist:
        st.caption("노면 데이터가 없습니다.")
        return

    st.markdown("##### 🛣️ 노면 피복 구성비")

    surface_labels = {
        "urethane_track": "우레탄 트랙",
        "soil_trail": "흙길 산책로",
        "lawn_grass": "잔디",
        "concrete_walkway": "보도블록/콘크리트",
        "asphalt_aged": "노후 아스팔트",
        "asphalt_dark": "신설 아스팔트",
    }

    cols = st.columns(len(surface_dist))
    for i, (surf_key, pct) in enumerate(surface_dist.items()):
        label = surface_labels.get(surf_key, surf_key)
        with cols[i]:
            st.metric(label=label, value=f"{pct:.1f}%")
            st.progress(min(1.0, max(0.0, pct / 100.0)))


def render_topology_health_card(topology_report: Dict[str, Any]) -> None:
    """학급 도로망 위상(Topology) 진단 결과를 카드 형태로 안내합니다.

    Args:
        topology_report: analyze_graph_topology() 결과 딕셔너리
    """
    health_score = topology_report.get("health_score", 0)
    is_connected = topology_report.get("is_fully_connected", False)
    comp_count = topology_report.get("component_count", 0)
    isolates = topology_report.get("isolated_nodes", [])
    msg = topology_report.get("diagnosis_message", "")

    st.markdown("#### 🌐 학급 도로망 위상 건강도")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric(label="네트워크 무결성 점수", value=f"{health_score} / 100")
        if is_connected:
            st.success("✅ 완전 연결망 구축 완료")
        else:
            st.warning(f"⚠️ {comp_count}개 분리 구역 감지")

    with col2:
        st.markdown(f"**진단 소견:** {msg}")
        if isolates:
            st.caption(f"고립 노드 목록: {', '.join(isolates)}")