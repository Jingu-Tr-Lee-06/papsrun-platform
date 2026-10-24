"""[2단계 UI] 학급 도로망 위상(Topology) 진단 및 네트워크 무결성 검사 모듈.

- 좌측 HUD 사이드바(3.2): 위상 진단 지표, 결함 노드/컴포넌트 리포트, 단절 복구 브릿지 추천
- 우측 풀사이즈 지도(6.8): 결함 간선(형광 핑크) 및 고립 노드 강조 시각화
- 1단계 작도 탭과의 일관된 네이버 지도 뷰포트 및 줌/시점 상태 동기화 지원
"""

from typing import Any, Dict, List, Tuple
import networkx as nx
import streamlit as st
from streamlit_folium import st_folium

from src.components.map_canvas import (
    create_interactive_campus_map,
    render_graph_overlay,
)
from src.db.road_repository import get_all_edges
from src.graph.graph_builder import build_campus_multidigraph
from src.graph.topology_analyzer import analyze_graph_topology, find_bridge_candidates


def render_tab2_topology_checker(class_code: str) -> None:
    """2단계 도로망 위상 검사 화면 렌더러 (풀스크린 HUD 레이아웃)."""
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 0rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            max-width: 100% !important;
        }
        iframe {
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.12);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    edges = get_all_edges(class_code)
    if not edges:
        st.warning("⚠️ 등록된 도로 간선이 없습니다. 1단계 작도 탭에서 도로를 먼저 작도해 주세요.")
        return

    # 1. MultiDiGraph 합성 및 위상 진단 수행
    G, nodes_dict = build_campus_multidigraph(edges)
    topo_report = analyze_graph_topology(G)

    total_nodes = topo_report.get("total_nodes", len(G.nodes))
    total_edges = topo_report.get("total_edges", len(G.edges))
    comp_count = topo_report.get("component_count", 1)
    is_fully_connected = topo_report.get("is_fully_connected", False)
    isolated_nodes = topo_report.get("isolated_nodes", [])
    dead_ends = topo_report.get("dead_ends", [])
    health_score = topo_report.get("health_score", 100)

    # 2. 뷰포트 세션 동기화
    if "map_view_center" not in st.session_state:
        st.session_state["map_view_center"] = [36.4675, 127.1405]
    if "map_view_zoom" not in st.session_state:
        st.session_state["map_view_zoom"] = 17

    col_panel, col_map = st.columns([3.2, 6.8])

    # ==========================================================================
    # [좌측] HUD 위상 진단 리포트 패널
    # ==========================================================================
    with col_panel:
        st.markdown(f"#### 🕸️ 위상(Topology) 진단 관제")
        st.caption(f"학급 코드: `{class_code}` | 그래프 무결성 점수: **`{health_score}점`**")

        if is_fully_connected:
            st.success("🎉 도로망 완전 연결 상태 (다익스트라 탐색 가능)")
        else:
            st.error(f"⚠️ 네트워크 단절: **{comp_count}개 독립 구역** 분리됨")

        # 메트릭 카드 4종
        m1, m2 = st.columns(2)
        with m1:
            st.metric("총 교차점 (Nodes)", f"{total_nodes}개")
            st.metric("고립 결함점 (Isolates)", f"{len(isolated_nodes)}개", delta_color="inverse")
        with m2:
            st.metric("총 도로 간선 (Edges)", f"{total_edges}개")
            st.metric("막다른 길 (Dead-ends)", f"{len(dead_ends)}개", delta_color="inverse")

        st.divider()

        # 세부 분석 서브 탭
        tab_comp, tab_bridge, tab_guide = st.tabs([
            f"분리 구역 ({comp_count})",
            "💡 연결 추천 (Bridge)",
            "📋 수학 탐구 가이드",
        ])

        with tab_comp:
            st.caption("각각 떨어져 있는 독립 도로 네트워크 덩어리 목록:")
            components_list = list(nx.weakly_connected_components(G))
            for idx, comp in enumerate(components_list, start=1):
                badge_color = "🟢" if idx == 1 else "🔴"
                with st.expander(f"{badge_color} 컴포넌트 #{idx} ({len(comp)}개 노드)", expanded=(idx <= 2)):
                    st.code(", ".join(list(comp)[:12]) + ("..." if len(comp) > 12 else ""))

        with tab_bridge:
            st.caption("서로 다른 분리 구역을 잇는 최단 거리 노드 쌍 탐색:")
            bridges = find_bridge_candidates(G, max_gap_meters=45.0)
            if bridges:
                for b in bridges:
                    st.info(
                        f"**추천 연결로**: `{b['u']}` ➔ `{b['v']}`\n\n"
                        f"• 이격 거리: **{b['distance_m']:.1f}m**\n\n"
                        "💡 *1단계 작도 탭의 [수동 연결]에서 두 노드를 이어주세요.*"
                    )
            else:
                if comp_count > 1:
                    st.warning("45m 이내 인접한 노드 쌍이 없습니다. 1단계에서 사잇길을 더 작도해야 합니다.")
                else:
                    st.success("모든 구역이 연결되어 추가 연결 추천이 필요하지 않습니다.")

        with tab_guide:
            st.markdown(
                "**수학(그래프 이론) 개념 안내:**\n"
                "- **차수(Degree)**: 한 노드에 연결된 도로의 수입니다.\n"
                "- **약한 연결성(Weakly Connected)**: 도로의 방향을 고려하지 않았을 때 모든 지점이 이어져 있는 상태입니다.\n"
                "- **브릿지(Bridge)**: 제거했을 때 네트워크가 두 개 이상으로 쪼개지는 핵심 연결 도로입니다."
            )

    # ==========================================================================
    # [우측] 결함 노드/간선 강조 풀사이즈 지도
    # ==========================================================================
    with col_map:
        # 단절 및 결함 부위 강조 대상 산출
        highlight_edges = []
        for u, v, _ in G.edges(data=True):
            if u in dead_ends or v in dead_ends or u in isolated_nodes or v in isolated_nodes:
                highlight_edges.append(f"{u}_{v}")

        base_map = create_interactive_campus_map(
            center_lat=st.session_state["map_view_center"][0],
            center_lon=st.session_state["map_view_center"][1],
            zoom_start=st.session_state["map_view_zoom"],
        )

        rendered_map = render_graph_overlay(
            base_map,
            edges,
            nodes_dict,
            highlight_edges=highlight_edges,
        )

        map_output = st_folium(
            rendered_map,
            width="100%",
            height=780,
            returned_objects=["zoom", "center"],
            key="tab2_topology_folium_map",
        )

        c_zoom = map_output.get("zoom")
        c_center = map_output.get("center")
        if c_zoom is not None:
            st.session_state["map_view_zoom"] = c_zoom
        if c_center is not None and isinstance(c_center, dict):
            st.session_state["map_view_center"] = [
                c_center.get("lat", st.session_state["map_view_center"][0]),
                c_center.get("lng", st.session_state["map_view_center"][1]),
            ]