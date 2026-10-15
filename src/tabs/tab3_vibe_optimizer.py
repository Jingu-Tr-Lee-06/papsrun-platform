"""[3단계 UI] 바이브 코딩 경로 최적화 및 3방향 다익스트라 탐색 컨트롤러 모듈.

Gemini 바이브 코딩 패널(vibe_chat_panel)과 연계하여 실시간 AST 검증을 거친
가중치 함수를 NetworkX 그래프에 주입하고, 최단거리 경로, 쾌적 경로(그늘/경사 완화),
바이브 코딩 경로를 동시 탐색하여 시각적·정량적으로 비교 분석합니다.
"""

from typing import Any, Dict, List, Optional, Tuple
import streamlit as st
from streamlit_folium import st_folium

from src.ai.sandbox_runner import execute_weight_function_sandbox
from src.components.map_canvas import (
    create_interactive_campus_map,
    render_dynamic_path_layer,
    render_graph_overlay,
)
from src.components.metrics_card import (
    render_comparative_metrics_card,
    render_paps_fitness_card,
    render_surface_breakdown_widget,
)
from src.components.vibe_chat_panel import render_vibe_chat_sidebar
from src.db.class_session_manager import get_class_session_config
from src.db.road_repository import get_all_edges
from src.graph.dijkstra_engine import (
    find_comfort_path,
    find_custom_weight_path,
    find_shortest_path,
)
from src.graph.graph_builder import build_campus_multidigraph
from src.graph.path_evaluator import evaluate_running_path


def render_tab3_vibe_optimizer(class_code: str, team_id: str) -> None:
    """3단계 바이브 코딩 및 다익스트라 경로 최적화 화면을 렌더링합니다.

    Args:
        class_code: 현재 접속한 학급 코드
        team_id: 현재 로그인한 모둠 식별자
    """
    st.markdown("### ⚡ 3단계: AI 바이브 코딩 & 다익스트라 경로 최적화")
    st.caption(
        "자연어 프롬프트로 다익스트라 가중치 함수(Weight Function)를 설계하고, "
        "일반 최단거리 경로와 체력 맞춤형 최적 경로를 다각도로 비교해 봅니다."
    )

    edges = get_all_edges(class_code)
    if not edges:
        st.warning("⚠️ 도로 데이터가 없습니다. 1단계에서 먼저 도로망을 구성해 주세요.")
        return

    # 그래프 빌드
    G, nodes_dict = build_campus_multidigraph(edges)
    available_nodes = sorted(list(G.nodes))
    if len(available_nodes) < 2:
        st.error("최소 2개 이상의 노드가 필요합니다.")
        return

    # 학급 환경 변수 로드
    session_cfg = get_class_session_config(class_code)
    weather_info = {
        "air_temp_c": session_cfg.get("air_temp_c", 30.0),
        "solar_rad": session_cfg.get("solar_rad", 750.0),
    }

    # 레이아웃: 좌측(지도 및 경로 비교) / 우측(바이브 코딩 대화창 및 에디터)
    col_main, col_chat = st.columns([3, 2])

    with col_main:
        st.markdown("##### 🏁 경로 탐색 출발점 및 도착점 지정")
        n_col1, n_col2 = st.columns(2)
        with n_col1:
            start_node = st.selectbox("출발 노드 (Start Node)", options=available_nodes, index=0)
        with n_col2:
            default_end_idx = len(available_nodes) - 1 if len(available_nodes) > 1 else 0
            end_node = st.selectbox("도착 노드 (End Node)", options=available_nodes, index=default_end_idx)

        if start_node == end_node:
            st.warning("출발 노드와 도착 노드를 서로 다르게 설정해 주세요.")

    with col_chat:
        # 우측 바이브 코딩 패널
        code_str, apply_clicked = render_vibe_chat_sidebar(
            student_profile={"team_id": team_id, "paps_grade": "2등급 (심폐지구력 집중)"},
            weather_info=weather_info,
        )

    # 경로 탐색 연산 처리
    if "latest_paths" not in st.session_state:
        st.session_state["latest_paths"] = {}

    if apply_clicked and start_node != end_node:
        with st.spinner("다익스트라 알고리즘으로 경로를 다각도 탐색 중입니다..."):
            # 1. 일반 최단거리 경로
            s_path, s_cost = find_shortest_path(G, start_node, end_node)
            s_eval = evaluate_running_path(G, s_path, weather_info) if s_path else None

            # 2. 쾌적 경로 (그늘 가중치 반영)
            c_path, c_cost = find_comfort_path(G, start_node, end_node)
            c_eval = evaluate_running_path(G, c_path, weather_info) if c_path else None

            # 3. 바이브 코딩 동적 가중치 경로
            func_obj, compile_err = execute_weight_function_sandbox(code_str)
            v_path, v_cost, v_eval = None, 0.0, None

            if func_obj:
                v_path, v_cost = find_custom_weight_path(G, start_node, end_node, func_obj)
                v_eval = evaluate_running_path(G, v_path, weather_info) if v_path else None
            else:
                st.error(f"동적 가중치 함수 실행 실패: {compile_err}")

            st.session_state["latest_paths"] = {
                "shortest": {"nodes": s_path, "cost": s_cost, "eval": s_eval},
                "comfort": {"nodes": c_path, "cost": c_cost, "eval": c_eval},
                "vibe": {"nodes": v_path, "cost": v_cost, "eval": v_eval},
            }

    # 결과 지도 및 비교 뷰 렌더링
    paths_data = st.session_state.get("latest_paths", {})
    s_info = paths_data.get("shortest", {})
    c_info = paths_data.get("comfort", {})
    v_info = paths_data.get("vibe", {})

    with col_main:
        st.markdown("##### 🗺️ 경로 탐색 결과 맵")
        base_map = create_interactive_campus_map(center_lat=36.4675, center_lon=127.1405, zoom_start=17)
        render_graph_overlay(base_map, edges, nodes_dict)

        # 경로 레이어 오버레이
        if s_info.get("nodes"):
            render_dynamic_path_layer(base_map, s_info["nodes"], nodes_dict, label="최단거리", color="#6C757D", is_dashed=True)
        if c_info.get("nodes"):
            render_dynamic_path_layer(base_map, c_info["nodes"], nodes_dict, label="쾌적 경로", color="#2A9D8F")
        if v_info.get("nodes"):
            render_dynamic_path_layer(base_map, v_info["nodes"], nodes_dict, label="바이브 코딩 최적 경로", color="#E63946")

        st_folium(base_map, width="100%", height=500)

    # 하단: 다채널 메트릭 비교 카드 출력
    st.divider()
    if s_info.get("eval") or c_info.get("eval") or v_info.get("eval"):
        render_comparative_metrics_card(
            shortest_metrics=s_info.get("eval"),
            comfort_metrics=c_info.get("eval"),
            vibe_metrics=v_info.get("eval"),
        )

        st.divider()
        v_eval_data = v_info.get("eval")
        if v_eval_data:
            st.markdown("#### 🎯 내가 만든 바이브 코딩 경로 세부 분석")
            render_paps_fitness_card(v_eval_data, path_name="바이브 코딩 맞춤 경로")
            render_surface_breakdown_widget(v_eval_data.get("surface_distribution", {}))
    else:
        st.info("우측 바이브 코딩 패널에서 조건을 입력하고 [가중치 함수 적용 및 경로 탐색 실행] 버튼을 눌러보세요.")