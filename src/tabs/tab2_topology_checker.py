"""[2단계 UI] 학급 도로망 위상 및 연결성 검사 화면 컨트롤러 모듈.

수집된 모든 노드와 간선을 NetworkX 그래프로 변환하여 위상학적 무결성
(약한 연결성, 강한 연결성, 고립 노드, 막다른 길, 미연결 컴포넌트)을 검사하고,
학생들이 다익스트라 최적화 단계로 넘어가기 전 끊어진 길을 보정할 수 있도록 피드백합니다.
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
from src.graph.topology_analyzer import analyze_graph_topology


def render_tab2_topology_checker(class_code: str) -> None:
    """2단계 도로망 위상 검사 탭을 렌더링합니다.

    Args:
        class_code: 현재 접속한 학급 코드
    """
    st.markdown("### 🕸️ 2단계: 학급 도로망 위상(Topology) 및 연결성 진단")
    st.caption(
        "다익스트라 알고리즘이 캠퍼스 전역을 탐색할 수 있으려면 도로망이 끊김 없이 연결되어 있어야 합니다. "
        "그래프 이론(Graph Theory) 기반의 컴포넌트 분석과 결함 노드를 확인해 보세요."
    )

    edges = get_all_edges(class_code)
    if not edges:
        st.warning("⚠️ 등록된 도로 간선이 없습니다. 1단계 작도 탭에서 도로를 먼저 입력해 주세요.")
        return

    # 1. NetworkX MultiDiGraph 구성
    G, nodes_dict = build_campus_multidigraph(edges)

    # 2. 위상학적 진단 수행
    topo_report = analyze_graph_topology(G)

    is_strongly_conn = topo_report.get("is_strongly_connected", False)
    is_weakly_conn = topo_report.get("is_weakly_connected", False)
    num_components = topo_report.get("number_of_components", 1)
    isolated_nodes = topo_report.get("isolated_nodes", [])
    dead_ends = topo_report.get("dead_ends", [])
    total_nodes = len(G.nodes)
    total_edges = len(G.edges)

    # 3. 위상 건전성 요약 메트릭 카드
    st.markdown("##### 🔍 위상 건전성 핵심 지표")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric(label="총 노드(교차점) 수", value=f"{total_nodes} 개")
    with m_col2:
        st.metric(label="총 간선(도로 세그먼트) 수", value=f"{total_edges} 개")
    with m_col3:
        st.metric(label="분리된 네트워크 덩어리", value=f"{num_components} 개")
    with m_col4:
        conn_label = "완전 연결" if is_weakly_conn else "네트워크 분단"
        st.metric(label="네트워크 연결 상태", value=conn_label)

    # 종합 판정 배너
    if is_weakly_conn and not isolated_nodes:
        st.success("🎉 도로망 위상 검사 합격: 모든 캠퍼스 구간이 성공적으로 연결되어 있어 다익스트라 경로 탐색이 가능합니다!")
    else:
        st.error(
            f"⚠️ 도로망에 단절 구간이 존재합니다. {num_components}개의 독립된 구역으로 나뉘어 있어 "
            "출발점과 도착점이 서로 다른 구역에 위치할 경우 경로를 찾지 못할 수 있습니다."
        )

    col_view, col_diag = st.columns([3, 2])

    with col_view:
        st.markdown("##### 🗺️ 결함 노드 강조 지도")
        base_map = create_interactive_campus_map(
            center_lat=36.4675,
            center_lon=127.1405,
            zoom_start=17,
        )

        # 강조할 간선(막다른 길 및 단절 부위)
        highlight_edges = []
        for u, v, _ in G.edges(data=True):
            if u in dead_ends or v in dead_ends or u in isolated_nodes or v in isolated_nodes:
                highlight_edges.append(f"{u}_{v}")

        rendered_map = render_graph_overlay(
            base_map, edges, nodes_dict, highlight_edges=highlight_edges
        )
        st_folium(rendered_map, width="100%", height=500)

    with col_diag:
        st.markdown("##### 🛠️ 결함 진단 상세 리포트")

        tab_iso, tab_dead, tab_comp = st.tabs(["고립 노드", "막다른 길(Dead-end)", "독립 컴포넌트"])

        with tab_iso:
            if isolated_nodes:
                st.warning(f"고립 노드 {len(isolated_nodes)}개 발견: 연결된 도로가 전혀 없는 노드입니다.")
                st.write(isolated_nodes)
            else:
                st.info("고립된 노드가 없습니다. 👍")

        with tab_dead:
            if dead_ends:
                st.warning(f"막다른 길 {len(dead_ends)}개 발견: 진입만 가능하고 나갈 수 없거나 한쪽 방향만 개설된 노드입니다.")
                st.write(dead_ends)
            else:
                st.info("단방향 막다른 길이 없습니다.")

        with tab_comp:
            st.markdown(f"**총 {num_components}개의 연결 요소(Component) 목록**")
            components_list = list(nx.weakly_connected_components(G))
            for idx, comp in enumerate(components_list, start=1):
                st.caption(f"**컴포넌트 #{idx}** ({len(comp)}개 노드 포함):")
                st.code(", ".join(list(comp)[:10]) + ("..." if len(comp) > 10 else ""))

    st.divider()
    st.info(
        "💡 **학습 가이드:** 네트워크가 분단되어 있다면 1단계 작도 화면으로 돌아가서 "
        "서로 다른 컴포넌트 사이에 도로 간선을 추가해 연결해 주세요."
    )